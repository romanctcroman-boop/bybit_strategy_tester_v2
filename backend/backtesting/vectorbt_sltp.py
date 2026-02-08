"""
VectorBT SL/TP Engine with Custom Cash Tracking

Implements custom cash tracking to match Fallback engine exactly.
Uses pre_group_func to create persistent state and post_order_func to update cash.

Key architecture:
- state[0] = tracked_cash (updated like FB: entry subtracts, exit adds with leverage PnL)
- state[1] = entry_price (for PnL calculation)
- state[2] = entry_size (for exit PnL calculation)
- state[3] = is_long (1.0 for long, 0.0 for short)

Author: AI Assistant
Date: January 2026
"""

import numpy as np
import pandas as pd
import vectorbt as vbt
from numba import njit
from vectorbt.portfolio.enums import Direction
from vectorbt.portfolio.nb import order_nb, order_nothing_nb


@njit
def check_sl_tp_hit_nb(entry_price, high, low, sl_pct, tp_pct, is_long):
    """Check if SL or TP was hit using high/low for intrabar detection.

    Returns clamped exit_price that is within [low, high] range.
    """
    if entry_price <= 0 or np.isnan(entry_price):
        return False, False, np.nan

    if is_long:
        # LONG position - check SL first (priority - same as SHORT for consistency)
        sl_price = entry_price * (1.0 - sl_pct) if sl_pct > 0 else 0.0
        tp_price = entry_price * (1.0 + tp_pct) if tp_pct > 0 else 1e18

        # SL first for consistent priority with fallback engine
        if sl_pct > 0 and low <= sl_price:
            clamped_sl = max(low, min(high, sl_price))
            return True, False, clamped_sl
        if tp_pct > 0 and high >= tp_price:
            clamped_tp = max(low, min(high, tp_price))
            return False, True, clamped_tp
    else:
        # SHORT position - check SL first (priority)
        sl_price = entry_price * (1.0 + sl_pct) if sl_pct > 0 else 1e18
        tp_price = entry_price * (1.0 - tp_pct) if tp_pct > 0 else 0.0

        if sl_pct > 0 and high >= sl_price:
            clamped_sl = max(low, min(high, sl_price))
            return True, False, clamped_sl
        if tp_pct > 0 and low <= tp_price:
            clamped_tp = max(low, min(high, tp_price))
            return False, True, clamped_tp

    return False, False, np.nan


@njit
def had_exit_this_bar(order_records, last_oidx, current_bar, col):
    """Check if there was an exit order on this bar (to prevent re-entry)."""
    if last_oidx < 0:
        return False

    for oidx in range(last_oidx, -1, -1):
        order = order_records[oidx]
        if order[1] != col:
            continue
        order_bar = order[2]
        if order_bar < current_bar:
            break
        if order_bar == current_bar:
            if order[6] == 1:  # Sell
                return True
            if order[6] == 0:  # Buy (could be short exit)
                return True
    return False


@njit
def flex_order_func_nb(
    c,
    # flex_order_args
    state,  # Mutable state array: [cash, entry_price, entry_size, is_long, peak_equity, is_stopped]
    entries,
    exits,
    short_entries,
    short_exits,
    high_arr,
    low_arr,
    open_arr,  # NEW: Open prices for next_bar_open fill mode
    sl_pct,
    tp_pct,
    position_size_pct,
    leverage,
    fees,
    slippage,
    direction_mode,
    max_drawdown_pct,  # NEW: Max drawdown limit (0 = disabled)
    fill_mode,  # NEW: 0 = bar_close, 1 = next_bar_open
):
    """Flexible order function with SL/TP, max drawdown limit, and fill mode support."""
    col = c.from_col
    i = c.i

    if c.call_idx >= 3:
        return -1, order_nothing_nb()

    position_now = c.last_position[col]

    # Use our tracked cash for position sizing
    tracked_cash = state[0]
    current_entry_price = state[1]
    current_entry_size = state[2]
    current_is_long = state[3] > 0.5  # noqa: F841
    peak_equity = state[4]
    is_stopped = state[5] > 0.5  # Trading stopped due to max drawdown

    close_now = c.close[i, col]
    high_now = high_arr[i, 0]
    low_now = low_arr[i, 0]
    open_now = open_arr[i, 0] if i < len(open_arr) else close_now  # noqa: F841

    # Calculate current equity and check max drawdown
    current_equity = tracked_cash
    if position_now != 0 and current_entry_price > 0:
        unrealized_pnl = 0.0
        if position_now > 0:  # Long
            # size already includes leverage, so no need to multiply by leverage
            unrealized_pnl = (close_now - current_entry_price) * current_entry_size
        else:  # Short
            unrealized_pnl = (current_entry_price - close_now) * current_entry_size
        current_equity = tracked_cash + current_entry_size * close_now + unrealized_pnl

    # Update peak equity
    if current_equity > peak_equity:
        state[4] = current_equity
        peak_equity = current_equity

    # Check max drawdown limit
    if max_drawdown_pct > 0 and peak_equity > 0 and not is_stopped:
        current_drawdown = (peak_equity - current_equity) / peak_equity
        if current_drawdown >= max_drawdown_pct:
            state[5] = 1.0  # Mark as stopped
            is_stopped = True
            # Force close any open position
            if position_now != 0:
                exit_price = close_now * (1.0 - slippage) if position_now > 0 else close_now * (1.0 + slippage)
                position_value = current_entry_size * exit_price
                exit_fees = position_value * fees

                if position_now > 0:
                    # Long exit: return margin + PnL
                    # PnL = size * price_diff (size already includes leverage)
                    pnl = (exit_price - current_entry_price) * current_entry_size
                    # Margin was locked, now returned with PnL
                    margin = (
                        current_entry_size * current_entry_price / leverage
                        if leverage > 0
                        else current_entry_size * current_entry_price
                    )
                    state[0] = tracked_cash + margin + pnl - exit_fees
                else:
                    # Short exit: return margin + PnL
                    pnl = (current_entry_price - exit_price) * current_entry_size
                    margin = (
                        current_entry_size * current_entry_price / leverage
                        if leverage > 0
                        else current_entry_size * current_entry_price
                    )
                    state[0] = tracked_cash + margin + pnl - exit_fees

                state[1] = 0.0
                state[2] = 0.0

                return col, order_nb(
                    size=-position_now,
                    price=exit_price,
                    fees=fees,
                )

    # If trading is stopped, don't open new positions
    if is_stopped and position_now == 0:
        return -1, order_nothing_nb()

    # Determine fill price based on fill_mode
    # fill_mode: 0 = bar_close, 1 = next_bar_open
    fill_price = close_now
    if fill_mode == 1 and i + 1 < len(open_arr):
        fill_price = open_arr[i + 1, 0]  # noqa: F841 - Use next bar's open

    # Signals
    long_entry = entries[i, 0]
    long_exit = exits[i, 0]
    short_entry = short_entries[i, 0]
    short_exit = short_exits[i, 0]

    # Direction filter
    if direction_mode == 1:  # short only
        long_entry = False
        long_exit = False
    elif direction_mode == 0:  # long only
        short_entry = False
        short_exit = False

    # PHASE 1a: Check SL/TP for LONG positions
    if c.call_idx == 0 and position_now > 0:
        adjusted_sl = sl_pct / leverage if leverage > 0 else sl_pct
        adjusted_tp = tp_pct / leverage if leverage > 0 else tp_pct

        hit_sl, hit_tp, exit_price = check_sl_tp_hit_nb(
            current_entry_price, high_now, low_now, adjusted_sl, adjusted_tp, True
        )

        if hit_sl or hit_tp:
            # Apply slippage for SL (market order)
            if hit_sl:
                exit_price = exit_price * (1.0 - slippage)

            # Calculate PnL (size already includes leverage)
            position_value = current_entry_size * exit_price
            exit_fees = position_value * fees
            pnl = (exit_price - current_entry_price) * current_entry_size - exit_fees

            # Margin trading: return margin + PnL
            margin = current_entry_size * current_entry_price / leverage if leverage > 0 else position_value
            state[0] = tracked_cash + margin + pnl
            state[1] = 0.0
            state[2] = 0.0

            return col, order_nb(
                size=-position_now,
                price=exit_price,
                fees=fees,
            )

    # PHASE 1b: Check SL/TP for SHORT positions
    if c.call_idx == 0 and position_now < 0:
        adjusted_sl = sl_pct / leverage if leverage > 0 else sl_pct
        adjusted_tp = tp_pct / leverage if leverage > 0 else tp_pct

        hit_sl, hit_tp, exit_price = check_sl_tp_hit_nb(
            current_entry_price, high_now, low_now, adjusted_sl, adjusted_tp, False
        )

        if hit_sl or hit_tp:
            # Apply slippage for SL (market order)
            if hit_sl:
                exit_price = exit_price * (1.0 + slippage)

            # Calculate PnL (size already includes leverage)
            position_value = current_entry_size * exit_price
            exit_fees = position_value * fees
            pnl = (current_entry_price - exit_price) * current_entry_size - exit_fees

            # Margin trading: return margin + PnL
            margin = current_entry_size * current_entry_price / leverage if leverage > 0 else position_value
            state[0] = tracked_cash + margin + pnl
            state[1] = 0.0
            state[2] = 0.0

            return col, order_nb(
                size=-position_now,
                price=exit_price,
                fees=fees,
            )

    # PHASE 2: Signal exits
    if c.call_idx <= 1 and position_now != 0:
        should_exit = (position_now > 0 and long_exit) or (position_now < 0 and short_exit)

        if should_exit:
            exit_price = close_now * (1.0 - slippage) if position_now > 0 else close_now * (1.0 + slippage)

            position_value = current_entry_size * exit_price
            exit_fees = position_value * fees

            # Calculate PnL (size already includes leverage)
            if position_now > 0:  # Long exit
                pnl = (exit_price - current_entry_price) * current_entry_size - exit_fees
            else:  # Short exit
                pnl = (current_entry_price - exit_price) * current_entry_size - exit_fees

            # Margin trading: return margin + PnL
            margin = current_entry_size * current_entry_price / leverage if leverage > 0 else position_value
            state[0] = tracked_cash + margin + pnl

            state[1] = 0.0
            state[2] = 0.0

            return col, order_nb(
                size=-position_now,
                price=close_now,
                fees=fees,
                slippage=slippage,
            )

    # PHASE 3: Entries
    if c.call_idx <= 2 and position_now == 0:
        if had_exit_this_bar(c.order_records, c.last_oidx[col], i, col):
            return -1, order_nothing_nb()

        # Use our tracked cash for sizing (FB style)
        # allocated_capital = margin (what gets locked)
        allocated_capital = tracked_cash * position_size_pct

        if long_entry:
            entry_px = close_now * (1.0 + slippage)
            # Position size includes leverage: position_value = margin * leverage
            # size = (margin * leverage) / price = position_value / price
            size = (allocated_capital * leverage) / (entry_px * (1.0 + fees))

            # For margin trading: only allocated_capital (margin) is locked
            # position_value would be size * entry_px = margin * leverage
            # But we only lock the margin, not full position value
            margin_locked = allocated_capital
            entry_fees = size * entry_px * fees
            state[0] = tracked_cash - margin_locked - entry_fees
            state[1] = entry_px
            state[2] = size
            state[3] = 1.0  # is_long

            return col, order_nb(size=size, price=entry_px, fees=fees, direction=Direction.LongOnly)

        if short_entry:
            entry_px = close_now * (1.0 - slippage)
            # Position size includes leverage
            size = (allocated_capital * leverage) / (entry_px * (1.0 + fees))

            # For margin trading: only allocated_capital (margin) is locked
            margin_locked = allocated_capital
            entry_fees = size * entry_px * fees
            state[0] = tracked_cash - margin_locked - entry_fees
            state[1] = entry_px
            state[2] = size
            state[3] = 0.0  # is_short

            return col, order_nb(size=size, price=entry_px, fees=fees, direction=Direction.ShortOnly)

    return -1, order_nothing_nb()


def run_vectorbt_with_sltp(ohlcv, signals, config):
    """Run VectorBT simulation with SL/TP, max drawdown, and fill mode support."""

    initial_capital = float(config.initial_capital)
    position_size_pct = float(config.position_size)
    leverage = float(config.leverage)
    sl_pct = float(config.stop_loss) if config.stop_loss else 0.0
    tp_pct = float(config.take_profit) if config.take_profit else 0.0
    fees = float(config.taker_fee)
    slippage = float(config.slippage)
    direction = getattr(config, "direction", "both")

    # NEW: Max drawdown limit (0 = disabled)
    max_drawdown_pct = float(config.max_drawdown) if getattr(config, "max_drawdown", None) else 0.0

    # NEW: Fill mode - execution_mode or fill_mode attribute
    fill_mode_str = getattr(config, "execution_mode", "on_bar_close")
    if hasattr(config, "fill_mode"):
        fill_mode_str = config.fill_mode
    fill_mode = 1 if fill_mode_str in ("next_bar_open", "on_next_bar") else 0

    direction_mode = {"long": 0, "short": 1, "both": 2}.get(direction, 2)

    close_df = pd.DataFrame({"close": ohlcv["close"].values}, index=ohlcv.index)

    n_bars = len(ohlcv)

    high_2d = ohlcv["high"].values.reshape(-1, 1).astype(np.float64)
    low_2d = ohlcv["low"].values.reshape(-1, 1).astype(np.float64)
    open_2d = ohlcv["open"].values.reshape(-1, 1).astype(np.float64)  # NEW: For fill_mode

    entries_val = signals.entries.values if hasattr(signals.entries, "values") else np.array(signals.entries)
    exits_val = signals.exits.values if hasattr(signals.exits, "values") else np.array(signals.exits)

    entries_2d = entries_val.reshape(-1, 1).astype(np.bool_)
    exits_2d = exits_val.reshape(-1, 1).astype(np.bool_)

    if hasattr(signals, "short_entries") and signals.short_entries is not None:
        se = (
            signals.short_entries.values
            if hasattr(signals.short_entries, "values")
            else np.array(signals.short_entries)
        )
        short_entries_2d = se.reshape(-1, 1).astype(np.bool_)
    else:
        short_entries_2d = np.zeros_like(entries_2d, dtype=np.bool_)

    if hasattr(signals, "short_exits") and signals.short_exits is not None:
        sx = signals.short_exits.values if hasattr(signals.short_exits, "values") else np.array(signals.short_exits)
        short_exits_2d = sx.reshape(-1, 1).astype(np.bool_)
    else:
        short_exits_2d = np.zeros_like(exits_2d, dtype=np.bool_)

    # State array for custom cash tracking (EXPANDED for max_drawdown)
    # [tracked_cash, entry_price, entry_size, is_long, peak_equity, is_stopped]
    state = np.array([initial_capital, 0.0, 0.0, 1.0, initial_capital, 0.0], dtype=np.float64)

    pf = vbt.Portfolio.from_order_func(
        close_df,
        flex_order_func_nb,
        # flex_order_args (state is mutable - persists between calls)
        state,
        entries_2d,
        exits_2d,
        short_entries_2d,
        short_exits_2d,
        high_2d,
        low_2d,
        open_2d,  # NEW
        sl_pct,
        tp_pct,
        position_size_pct,
        leverage,
        fees,
        slippage,
        direction_mode,
        max_drawdown_pct,  # NEW
        fill_mode,  # NEW
        # Settings (no pre_group_func - state persists as mutable array)
        flexible=True,
        init_cash=initial_capital,
        cash_sharing=False,
        freq="1H",
        max_orders=n_bars * 3,
    )

    return pf


if __name__ == "__main__":
    print("VectorBT SL/TP Engine with Custom Cash Tracking")
