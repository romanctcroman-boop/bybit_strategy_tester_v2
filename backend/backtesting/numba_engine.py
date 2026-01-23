"""
Numba JIT-compiled Fallback Engine Core

This module contains the performance-critical inner loop of the Fallback engine,
compiled with Numba for 10-50x speedup over pure Python.

DeepSeek/Perplexity Recommendation:
- Numba @njit compiles Python to LLVM machine code
- Avoid Python objects inside JIT functions (use numpy arrays)
- Pre-allocate all output arrays
"""

import numpy as np
from numba import njit, prange
from typing import Tuple

# Trade result structure for Numba
# Each trade is a tuple of: (entry_idx, exit_idx, is_long, entry_price, exit_price,
#                            pnl, pnl_pct, mfe, mae, mfe_pct, mae_pct, exit_reason)
# exit_reason: 0=signal, 1=stop_loss, 2=take_profit


@njit(cache=True, fastmath=True)
def simulate_trades_numba(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    long_entries: np.ndarray,
    long_exits: np.ndarray,
    short_entries: np.ndarray,
    short_exits: np.ndarray,
    initial_capital: float,
    position_size_frac: float,
    taker_fee: float,
    slippage: float,
    stop_loss: float,
    take_profit: float,
    leverage: float,
    direction: int,  # 0=long, 1=short, 2=both
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """
    Numba JIT-compiled trading simulation.

    Args:
        close, high, low: Price arrays
        long_entries, long_exits: Boolean arrays for long signals
        short_entries, short_exits: Boolean arrays for short signals
        initial_capital: Starting capital
        position_size_frac: Fraction of capital per trade (0.0-1.0)
        taker_fee: Trading fee (e.g., 0.0004 for 0.04%)
        slippage: Slippage (e.g., 0.0001 for 0.01%)
        stop_loss: Stop loss as decimal (e.g., 0.03 for 3%)
        take_profit: Take profit as decimal (e.g., 0.06 for 6%)
        leverage: Trading leverage
        direction: 0=long only, 1=short only, 2=both

    Returns:
        trades: 2D array of trade data (max 1000 trades)
        equity: Array of equity values at each bar
        trade_count: Number of actual trades
    """
    n_bars = len(close)

    # Pre-allocate outputs
    max_trades = 1000
    # Trade columns: entry_idx, exit_idx, is_long, entry_price, exit_price,
    #                pnl, pnl_pct, size, mfe, mae, mfe_pct, mae_pct, exit_reason
    trades = np.zeros((max_trades, 13), dtype=np.float64)
    equity = np.zeros(n_bars, dtype=np.float64)

    # Simulation state (cash-based tracking for position sizing)
    cash = initial_capital
    position = 0.0
    is_long = True
    trade_count = 0

    # Equity tracking (cumulative PnL approach - matches Fallback)
    cumulative_realized_pnl = 0.0

    entry_price = 0.0
    entry_size = 0.0
    entry_idx = 0
    max_favorable_price = 0.0
    max_adverse_price = 0.0

    for i in range(n_bars):
        price = close[i]
        current_high = high[i]
        current_low = low[i]

        # Check for entry (when not in position)
        # Don't enter in last 5 bars to avoid unclosed positions affecting equity
        if position == 0.0 and i < n_bars - 5:
            # Long entry
            if (direction == 0 or direction == 2) and long_entries[i]:
                entry_price = price * (1.0 + slippage)
                allocated_capital = cash * position_size_frac
                entry_size = allocated_capital / (entry_price * (1.0 + taker_fee))

                position_value = entry_size * entry_price
                fees = position_value * taker_fee

                cash -= position_value + fees
                position = entry_size
                is_long = True
                entry_idx = i
                max_favorable_price = current_high
                max_adverse_price = current_low

            # Short entry
            elif (direction == 1 or direction == 2) and short_entries[i]:
                entry_price = price * (1.0 - slippage)
                allocated_capital = cash * position_size_frac
                entry_size = allocated_capital / (entry_price * (1.0 + taker_fee))

                position_value = entry_size * entry_price
                fees = position_value * taker_fee

                cash -= position_value + fees
                position = entry_size
                is_long = False
                entry_idx = i
                max_favorable_price = current_low
                max_adverse_price = current_high

        # While in position: update MFE/MAE and check exits
        elif position > 0.0:
            # Update MFE/MAE
            if is_long:
                if current_high > max_favorable_price:
                    max_favorable_price = current_high
                if current_low < max_adverse_price:
                    max_adverse_price = current_low
            else:
                if current_low < max_favorable_price:
                    max_favorable_price = current_low
                if current_high > max_adverse_price:
                    max_adverse_price = current_high

            # Calculate worst/best P/L within bar
            if is_long:
                worst_price = current_low
                best_price = current_high
                worst_pnl_pct = (worst_price - entry_price) / entry_price * leverage
                best_pnl_pct = (best_price - entry_price) / entry_price * leverage
            else:
                worst_price = current_high
                best_price = current_low
                worst_pnl_pct = (entry_price - worst_price) / entry_price * leverage
                best_pnl_pct = (entry_price - best_price) / entry_price * leverage

            should_exit = False
            exit_reason = 0  # 0=signal, 1=stop_loss, 2=take_profit
            exit_price = price
            apply_slippage = True

            # Check Stop Loss
            if stop_loss > 0.0 and worst_pnl_pct <= -stop_loss:
                should_exit = True
                exit_reason = 1  # stop_loss
                if is_long:
                    exit_price = entry_price * (1.0 - stop_loss / leverage)
                else:
                    exit_price = entry_price * (1.0 + stop_loss / leverage)
                # Clamp to bar range
                if exit_price < current_low:
                    exit_price = current_low
                if exit_price > current_high:
                    exit_price = current_high
                apply_slippage = True

            # Check Take Profit
            if not should_exit and take_profit > 0.0 and best_pnl_pct >= take_profit:
                should_exit = True
                exit_reason = 2  # take_profit
                if is_long:
                    exit_price = entry_price * (1.0 + take_profit / leverage)
                else:
                    exit_price = entry_price * (1.0 - take_profit / leverage)
                # Clamp to bar range
                if exit_price < current_low:
                    exit_price = current_low
                if exit_price > current_high:
                    exit_price = current_high
                apply_slippage = False

            # Check signal exit
            if not should_exit:
                if is_long and long_exits[i]:
                    should_exit = True
                    exit_reason = 0  # signal
                    exit_price = price
                elif not is_long and short_exits[i]:
                    should_exit = True
                    exit_reason = 0  # signal
                    exit_price = price

            if should_exit:
                # Apply slippage
                if apply_slippage:
                    if is_long:
                        exit_price = exit_price * (1.0 - slippage)
                    else:
                        exit_price = exit_price * (1.0 + slippage)

                # Calculate P/L
                position_value = position * exit_price
                fees = position_value * taker_fee

                if is_long:
                    pnl = (exit_price - entry_price) * entry_size * leverage - fees
                    pnl_pct = (
                        (exit_price - entry_price) / entry_price * leverage * 100.0
                    )
                    mfe_pct = (max_favorable_price - entry_price) / entry_price * 100.0
                    mae_pct = (entry_price - max_adverse_price) / entry_price * 100.0
                    mfe = (max_favorable_price - entry_price) * entry_size * leverage
                    mae = (entry_price - max_adverse_price) * entry_size * leverage
                else:
                    pnl = (entry_price - exit_price) * entry_size * leverage - fees
                    pnl_pct = (
                        (entry_price - exit_price) / entry_price * leverage * 100.0
                    )
                    mfe_pct = (entry_price - max_favorable_price) / entry_price * 100.0
                    mae_pct = (max_adverse_price - entry_price) / entry_price * 100.0
                    mfe = (entry_price - max_favorable_price) * entry_size * leverage
                    mae = (max_adverse_price - entry_price) * entry_size * leverage

                # Update cash (for position sizing)
                if is_long:
                    # Long: return position value minus exit fees
                    cash += position_value - fees
                else:
                    # Short: return position value + P&L (pnl already includes -fees)
                    cash += position_value + pnl

                # Track cumulative realized PnL for equity
                cumulative_realized_pnl += pnl

                # Record trade
                if trade_count < max_trades:
                    trades[trade_count, 0] = entry_idx
                    trades[trade_count, 1] = i  # exit_idx
                    trades[trade_count, 2] = 1.0 if is_long else 0.0
                    trades[trade_count, 3] = entry_price
                    trades[trade_count, 4] = exit_price
                    trades[trade_count, 5] = pnl
                    trades[trade_count, 6] = pnl_pct
                    trades[trade_count, 7] = entry_size
                    trades[trade_count, 8] = mfe
                    trades[trade_count, 9] = mae
                    trades[trade_count, 10] = mfe_pct
                    trades[trade_count, 11] = mae_pct
                    trades[trade_count, 12] = exit_reason
                    trade_count += 1

                position = 0.0
                entry_price = 0.0
                entry_size = 0.0

        # Update equity using cumulative PnL approach (matches Fallback)
        # Equity = initial_capital + cumulative_realized_pnl + unrealized_pnl
        if position > 0.0:
            if is_long:
                unrealized_pnl = (price - entry_price) * position * leverage
            else:
                unrealized_pnl = (entry_price - price) * position * leverage
            equity[i] = initial_capital + cumulative_realized_pnl + unrealized_pnl
        else:
            equity[i] = initial_capital + cumulative_realized_pnl

    return trades, equity, trades[:trade_count], trade_count


@njit(cache=True, fastmath=True, parallel=True)
def batch_simulate_numba(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    long_entries: np.ndarray,
    long_exits: np.ndarray,
    short_entries: np.ndarray,
    short_exits: np.ndarray,
    initial_capital: float,
    position_size_frac: float,
    taker_fee: float,
    slippage: float,
    stop_loss_array: np.ndarray,
    take_profit_array: np.ndarray,
    leverage: float,
    direction: int,
) -> np.ndarray:
    """
    Batch simulate multiple SL/TP combinations in parallel using Numba.

    Returns array of shape (n_sl, n_tp, 4) with [total_return, sharpe, max_dd, n_trades]
    """
    n_sl = len(stop_loss_array)
    n_tp = len(take_profit_array)
    n_bars = len(close)

    # Output: [total_return, sharpe_approx, max_drawdown, n_trades]
    results = np.zeros((n_sl, n_tp, 4), dtype=np.float64)

    for i_sl in prange(n_sl):
        for i_tp in range(n_tp):
            sl = stop_loss_array[i_sl]
            tp = take_profit_array[i_tp]

            # Run simulation
            trades, equity, _, n_trades = simulate_trades_numba(
                close,
                high,
                low,
                long_entries,
                long_exits,
                short_entries,
                short_exits,
                initial_capital,
                position_size_frac,
                taker_fee,
                slippage,
                sl,
                tp,
                leverage,
                direction,
            )

            # Calculate metrics
            final_equity = equity[-1] if n_bars > 0 else initial_capital
            total_return = (final_equity - initial_capital) / initial_capital * 100.0

            # Approximate Sharpe (simplified)
            if n_trades > 1:
                # Calculate returns
                returns_sum = 0.0
                returns_sq_sum = 0.0
                for t in range(n_trades):
                    ret = trades[t, 6]  # pnl_pct
                    returns_sum += ret
                    returns_sq_sum += ret * ret

                mean_ret = returns_sum / n_trades
                variance = returns_sq_sum / n_trades - mean_ret * mean_ret
                std_ret = np.sqrt(variance) if variance > 0 else 1.0
                sharpe = mean_ret / std_ret if std_ret > 0 else 0.0
            else:
                sharpe = 0.0

            # Max drawdown
            peak = initial_capital
            max_dd = 0.0
            for j in range(n_bars):
                if equity[j] > peak:
                    peak = equity[j]
                dd = (peak - equity[j]) / peak if peak > 0 else 0.0
                if dd > max_dd:
                    max_dd = dd

            results[i_sl, i_tp, 0] = total_return
            results[i_sl, i_tp, 1] = sharpe
            results[i_sl, i_tp, 2] = max_dd * 100.0
            results[i_sl, i_tp, 3] = n_trades

    return results


def warmup_numba():
    """Warm up Numba JIT compilation with dummy data."""
    dummy_close = np.random.randn(100).astype(np.float64) + 100
    dummy_high = dummy_close + 0.5
    dummy_low = dummy_close - 0.5
    dummy_entries = np.zeros(100, dtype=np.bool_)
    dummy_exits = np.zeros(100, dtype=np.bool_)
    dummy_entries[10] = True
    dummy_exits[20] = True

    # Trigger compilation
    simulate_trades_numba(
        dummy_close,
        dummy_high,
        dummy_low,
        dummy_entries,
        dummy_exits,
        dummy_entries,
        dummy_exits,
        10000.0,
        1.0,
        0.0004,
        0.0001,
        0.03,
        0.06,
        1.0,
        2,
    )

    # Warm up batch
    sl_arr = np.array([0.01, 0.02, 0.03], dtype=np.float64)
    tp_arr = np.array([0.02, 0.04, 0.06], dtype=np.float64)
    batch_simulate_numba(
        dummy_close,
        dummy_high,
        dummy_low,
        dummy_entries,
        dummy_exits,
        dummy_entries,
        dummy_exits,
        10000.0,
        1.0,
        0.0004,
        0.0001,
        sl_arr,
        tp_arr,
        1.0,
        2,
    )


# Warm up on import if numba is available
try:
    warmup_numba()
except Exception:
    pass
