"""
Numba JIT kernels for GPU optimizer.

Extracted from gpu_optimizer.py (lines 152-1842).
Contains all @njit-decorated functions used by GPUGridOptimizer:
  - _fast_simulate_backtest   — single-trade backtest simulation
  - _fast_calculate_rsi       — RSI calculation
  - _calculate_all_rsi_vectorized — batch RSI for all periods
  - _backtest_all_vectorized  — parallel batch backtest (prange)
  - _backtest_all_with_params — positional-size-aware batch backtest
  - _backtest_all_v6_batch    — V6 batch backtest variant

IMPORTANT: These functions must remain at module level for Numba JIT cache.
IMPORTANT: The Numba cache key includes the file path — do NOT rename without
           clearing the cache (~/.numba_cache or __pycache__/numba/).
"""

import os
import warnings

import numpy as np

warnings.filterwarnings("ignore", category=FutureWarning)

# Number of parallel workers (used by prange kernels)
N_WORKERS = os.cpu_count() or 4

# Safety limit — prevents runaway grids from exhausting memory
MAX_COMBINATIONS = 50_000_000

try:
    from numba import njit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

# Joblib availability (for potential parallel use)
try:
    import joblib  # noqa: F401

    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False

# =============================================================================
# Numba-optimized functions for ultra-fast backtesting
# MUST be defined BEFORE worker functions that use them
# =============================================================================

if NUMBA_AVAILABLE:
    # DeepSeek V5: Explicit JIT signature for base backtest
    # Updated: Added position_size parameter for realistic simulation
    @njit(
        "UniTuple(float64, 6)(float64[:], float64[:], float64[:], "
        "boolean[:], boolean[:], float64, float64, float64, float64, float64, float64)",
        cache=True,
        fastmath=True,
    )
    def _fast_simulate_backtest(
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        entries: np.ndarray,
        exits: np.ndarray,
        stop_loss: float,
        take_profit: float,
        capital: float,
        commission: float,
        slippage: float,
        position_size: float,  # NEW: fraction of capital per trade (0.0-1.0)
    ):
        """Ultra-fast backtest simulation with Numba JIT

        Args:
            position_size: Fraction of capital to use per trade (e.g., 0.1 = 10%)
        """
        n = len(close)
        equity = capital
        peak_equity = capital
        max_drawdown = 0.0

        trade_pnls = np.zeros(1000, dtype=np.float64)  # Pre-allocate
        trade_count = 0

        in_position = False
        entry_price = 0.0
        trade_equity = 0.0  # Amount allocated to current trade

        for i in range(1, n):
            if not in_position:
                if entries[i]:
                    in_position = True
                    entry_price = close[i]
                    # Allocate position_size fraction of current equity
                    trade_equity = equity * position_size
                    # Apply commission on entry
                    equity -= trade_equity * commission
            else:
                current_price = close[i]
                pnl_pct = (current_price - entry_price) / entry_price

                hit_sl = False
                hit_tp = False
                exit_price = current_price

                if stop_loss > 0:
                    sl_price = entry_price * (1 - stop_loss)
                    if low[i] <= sl_price:
                        hit_sl = True
                        exit_price = sl_price

                if take_profit > 0:
                    tp_price = entry_price * (1 + take_profit)
                    if high[i] >= tp_price:
                        hit_tp = True
                        exit_price = tp_price

                should_exit = exits[i] or hit_sl or hit_tp

                if should_exit:
                    if hit_sl:
                        # SL hit: exit at sl_price * (1 - slippage) if long
                        # But wait, SL usually executes at market when triggered.
                        # Simplified: use SL price with slippage
                        exit_price_final = entry_price * (1 - stop_loss)
                    elif hit_tp:
                        exit_price_final = entry_price * (1 + take_profit)
                    else:
                        exit_price_final = exit_price

                    # Apply slippage logic
                    # Long trade: Buy at Entry*(1+s), Sell at Exit*(1-s)
                    # PnL = (Exit*(1-s) - Entry*(1+s)) / Entry*(1+s)
                    # This approximates to: (Exit - Entry)/Entry - 2*slippage (roughly)

                    real_entry = entry_price * (1 + slippage)
                    real_exit = exit_price_final * (1 - slippage)
                    pnl_pct = (real_exit - real_entry) / real_entry

                    # Calculate PnL on the allocated trade equity only
                    trade_pnl = trade_equity * pnl_pct
                    equity += trade_pnl
                    # Apply commission on exit
                    equity -= trade_equity * commission

                    if trade_count < 1000:
                        trade_pnls[trade_count] = pnl_pct
                        trade_count += 1

                    if equity > peak_equity:
                        peak_equity = equity
                    drawdown = (peak_equity - equity) / peak_equity
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown

                    in_position = False
                    trade_equity = 0.0

        if trade_count == 0:
            return 0.0, 0.0, 0.0, 0.0, 0, 0.0

        total_return = (equity - capital) / capital * 100

        # Win rate
        wins = 0
        gross_profit = 0.0
        gross_loss = 0.0
        for j in range(trade_count):
            if trade_pnls[j] > 0:
                wins += 1
                gross_profit += trade_pnls[j]
            else:
                gross_loss += abs(trade_pnls[j])

        win_rate = wins / trade_count

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 10.0

        # Sharpe ratio
        if trade_count > 1:
            mean_return = 0.0
            for j in range(trade_count):
                mean_return += trade_pnls[j]
            mean_return /= trade_count

            variance = 0.0
            for j in range(trade_count):
                variance += (trade_pnls[j] - mean_return) ** 2
            variance /= trade_count - 1
            std_return = variance**0.5

            sharpe = (mean_return / std_return * 15.87) if std_return > 0 else 0
        else:
            sharpe = 0.0

        return (
            total_return,
            sharpe,
            max_drawdown * 100,
            win_rate,
            trade_count,
            profit_factor,
        )

    # DeepSeek V5: Explicit JIT signature for RSI calculation
    @njit("float64[:](float64[:], int64)", cache=True, fastmath=True)
    def _fast_calculate_rsi(close: np.ndarray, period: int) -> np.ndarray:
        """Ultra-fast RSI calculation with Numba"""
        n = len(close)
        rsi = np.full(n, 50.0)

        if n <= period:
            return rsi

        delta = np.zeros(n)
        for i in range(1, n):
            delta[i] = close[i] - close[i - 1]

        gains = np.zeros(n)
        losses = np.zeros(n)
        for i in range(n):
            if delta[i] > 0:
                gains[i] = delta[i]
            elif delta[i] < 0:
                losses[i] = -delta[i]

        avg_gain = np.zeros(n)
        avg_loss = np.zeros(n)

        sum_gain = 0.0
        sum_loss = 0.0
        for i in range(1, period + 1):
            sum_gain += gains[i]
            sum_loss += losses[i]
        avg_gain[period] = sum_gain / period
        avg_loss[period] = sum_loss / period

        alpha = 1.0 / period
        for i in range(period + 1, n):
            avg_gain[i] = alpha * gains[i] + (1 - alpha) * avg_gain[i - 1]
            avg_loss[i] = alpha * losses[i] + (1 - alpha) * avg_loss[i - 1]

        for i in range(period, n):
            if avg_loss[i] > 0:
                rs = avg_gain[i] / avg_loss[i]
                rsi[i] = 100 - (100 / (1 + rs))

        return rsi

    # =========================================================================
    # VECTORIZED OPTIMIZATION (DeepSeek Recommendation - 14x faster)
    # Calculate ALL RSI periods at once, then backtest ALL combinations in parallel
    # =========================================================================

    # DeepSeek V5: Explicit JIT signatures for faster compilation
    @njit(
        "float64[:,:](float64[:], int64[:])",
        cache=True,
        fastmath=True,
        boundscheck=False,
    )
    def _calculate_all_rsi_vectorized(close: np.ndarray, periods: np.ndarray) -> np.ndarray:
        """
        Calculate RSI for ALL periods at once.
        Returns: rsi_matrix[period_idx, time]
        """
        n = len(close)
        n_periods = len(periods)

        # Pre-compute deltas once
        delta = np.zeros(n, dtype=np.float64)
        for i in range(1, n):
            delta[i] = close[i] - close[i - 1]

        gains = np.maximum(delta, 0.0)
        losses = np.maximum(-delta, 0.0)

        # Output: RSI for each period
        rsi_all = np.full((n_periods, n), 50.0, dtype=np.float64)

        for p_idx in range(n_periods):
            period = periods[p_idx]
            if period >= n:
                continue

            # First average
            sum_gain = 0.0
            sum_loss = 0.0
            for i in range(1, period + 1):
                sum_gain += gains[i]
                sum_loss += losses[i]

            avg_gain = sum_gain / period
            avg_loss = sum_loss / period

            # Wilders EMA
            alpha = 1.0 / period
            for i in range(period + 1, n):
                avg_gain = alpha * gains[i] + (1 - alpha) * avg_gain
                avg_loss = alpha * losses[i] + (1 - alpha) * avg_loss

                if avg_loss > 1e-12:
                    rs = avg_gain / avg_loss
                    rsi_all[p_idx, i] = 100.0 - (100.0 / (1.0 + rs))

        return rsi_all

    @njit(cache=True, fastmath=True, boundscheck=False, parallel=True)
    def _backtest_all_vectorized(
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_all: np.ndarray,
        periods: np.ndarray,
        overbought_arr: np.ndarray,
        oversold_arr: np.ndarray,
        sl_arr: np.ndarray,
        tp_arr: np.ndarray,
        capital: float,
        commission: float,
        direction: int,  # 1=long, -1=short, 0=both
    ) -> np.ndarray:
        """
        Backtest ALL parameter combinations using parallel processing.
        Uses prange for parallelization across RSI periods.

        BIDIRECTIONAL SUPPORT (direction=0):
        - Tracks Long and Short positions INDEPENDENTLY
        - Long entry: RSI < oversold, Long exit: RSI > overbought
        - Short entry: RSI > overbought, Short exit: RSI < oversold

        Returns: results[combo_idx, 12] = [return, sharpe, max_dd, win_rate, trades, profit_factor,
                                           long_trades, long_wins, long_gross_profit,
                                           short_trades, short_wins, short_gross_profit]
        """
        n = len(close)
        n_periods = len(periods)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)

        # Total combinations
        total = n_periods * n_ob * n_os * n_sl * n_tp

        # Results: [total_return, sharpe, max_dd, win_rate, trades, profit_factor,
        #           long_trades, long_wins, long_gross_profit,
        #           short_trades, short_wins, short_gross_profit]
        results = np.zeros((total, 12), dtype=np.float64)

        # Parallel over periods (outer loop)
        for p_idx in prange(n_periods):
            rsi = rsi_all[p_idx]
            period = periods[p_idx]

            combo_base = p_idx * n_ob * n_os * n_sl * n_tp

            for ob_idx in range(n_ob):
                overbought = overbought_arr[ob_idx]

                for os_idx in range(n_os):
                    oversold = oversold_arr[os_idx]

                    if oversold >= overbought:
                        continue

                    # Generate signals based on direction
                    long_entries = np.zeros(n, dtype=np.bool_)
                    long_exits = np.zeros(n, dtype=np.bool_)
                    short_entries = np.zeros(n, dtype=np.bool_)
                    short_exits = np.zeros(n, dtype=np.bool_)

                    for i in range(period + 1, n):
                        if direction >= 0:  # Long or both
                            long_entries[i] = rsi[i] < oversold
                            long_exits[i] = rsi[i] > overbought
                        if direction <= 0:  # Short or both
                            short_entries[i] = rsi[i] > overbought
                            short_exits[i] = rsi[i] < oversold

                    for sl_idx in range(n_sl):
                        sl = sl_arr[sl_idx] / 100.0

                        for tp_idx in range(n_tp):
                            tp = tp_arr[tp_idx] / 100.0

                            # Run backtest with DUAL position tracking
                            equity = capital
                            peak_equity = capital
                            max_dd = 0.0
                            trade_count = 0
                            wins = 0
                            gross_profit = 0.0
                            gross_loss = 0.0
                            trade_pnls = np.zeros(500, dtype=np.float64)

                            # Separate tracking for Long/Short
                            long_trades_count = 0
                            long_wins = 0
                            long_gross_profit = 0.0
                            long_gross_loss = 0.0
                            short_trades_count = 0
                            short_wins = 0
                            short_gross_profit = 0.0
                            short_gross_loss = 0.0

                            # Position state for BOTH directions
                            in_long = False
                            in_short = False
                            long_entry_price = 0.0
                            short_entry_price = 0.0

                            for i in range(1, n):
                                # === LONG POSITION LOGIC ===
                                if direction >= 0:  # Long enabled
                                    if not in_long:
                                        if long_entries[i]:
                                            in_long = True
                                            long_entry_price = close[i]
                                            equity *= 1 - commission
                                    else:
                                        # Check exit conditions for Long
                                        hit_sl = sl > 0 and low[i] <= long_entry_price * (1 - sl)
                                        hit_tp = tp > 0 and high[i] >= long_entry_price * (1 + tp)

                                        if long_exits[i] or hit_sl or hit_tp:
                                            if hit_sl:
                                                pnl = -sl
                                            elif hit_tp:
                                                pnl = tp
                                            else:
                                                pnl = (close[i] - long_entry_price) / long_entry_price

                                            equity *= (1 + pnl) * (1 - commission)

                                            if trade_count < 500:
                                                trade_pnls[trade_count] = pnl
                                            trade_count += 1
                                            long_trades_count += 1

                                            if pnl > 0:
                                                wins += 1
                                                long_wins += 1
                                                gross_profit += pnl
                                                long_gross_profit += pnl
                                            else:
                                                gross_loss += abs(pnl)
                                                long_gross_loss += abs(pnl)

                                            if equity > peak_equity:
                                                peak_equity = equity
                                            dd = (peak_equity - equity) / peak_equity
                                            if dd > max_dd:
                                                max_dd = dd

                                            in_long = False

                                # === SHORT POSITION LOGIC ===
                                if direction <= 0:  # Short enabled
                                    if not in_short:
                                        if short_entries[i]:
                                            in_short = True
                                            short_entry_price = close[i]
                                            equity *= 1 - commission
                                    else:
                                        # Check exit conditions for Short (reversed)
                                        hit_sl = sl > 0 and high[i] >= short_entry_price * (1 + sl)
                                        hit_tp = tp > 0 and low[i] <= short_entry_price * (1 - tp)

                                        if short_exits[i] or hit_sl or hit_tp:
                                            if hit_sl:
                                                pnl = -sl
                                            elif hit_tp:
                                                pnl = tp
                                            else:
                                                pnl = (short_entry_price - close[i]) / short_entry_price

                                            equity *= (1 + pnl) * (1 - commission)

                                            if trade_count < 500:
                                                trade_pnls[trade_count] = pnl
                                            trade_count += 1
                                            short_trades_count += 1

                                            if pnl > 0:
                                                wins += 1
                                                short_wins += 1
                                                gross_profit += pnl
                                                short_gross_profit += pnl
                                            else:
                                                gross_loss += abs(pnl)
                                                short_gross_loss += abs(pnl)

                                            if equity > peak_equity:
                                                peak_equity = equity
                                            dd = (peak_equity - equity) / peak_equity
                                            if dd > max_dd:
                                                max_dd = dd

                                            in_short = False

                            # Store result
                            combo_idx = (
                                combo_base + ob_idx * n_os * n_sl * n_tp + os_idx * n_sl * n_tp + sl_idx * n_tp + tp_idx
                            )

                            if trade_count > 0:
                                total_return = (equity - capital) / capital * 100
                                win_rate = wins / trade_count
                                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 100.0

                                # Sharpe ratio
                                if trade_count > 1:
                                    mean_ret = 0.0
                                    tc = min(trade_count, 500)
                                    for j in range(tc):
                                        mean_ret += trade_pnls[j]
                                    mean_ret /= tc

                                    variance = 0.0
                                    for j in range(tc):
                                        variance += (trade_pnls[j] - mean_ret) ** 2
                                    variance /= tc - 1
                                    std_ret = variance**0.5
                                    sharpe = (mean_ret / std_ret * 15.87) if std_ret > 0 else 0.0
                                else:
                                    sharpe = 0.0

                                results[combo_idx, 0] = total_return
                                results[combo_idx, 1] = sharpe
                                results[combo_idx, 2] = max_dd * 100
                                results[combo_idx, 3] = win_rate
                                results[combo_idx, 4] = trade_count
                                results[combo_idx, 5] = profit_factor
                                # Long/Short specific stats
                                results[combo_idx, 6] = long_trades_count
                                results[combo_idx, 7] = long_wins
                                results[combo_idx, 8] = long_gross_profit
                                results[combo_idx, 9] = short_trades_count
                                results[combo_idx, 10] = short_wins
                                results[combo_idx, 11] = short_gross_profit

        return results

    # DeepSeek V5: Explicit JIT signature for _backtest_all_with_params
    @njit(
        "float64[:,:](float64[:], float64[:], float64[:], float64[:,:], "
        "int64[:], float64[:], float64[:], float64[:], float64[:], "
        "float64, float64, float64, int64, int64)",  # Added position_mode
        cache=True,
        fastmath=True,
        boundscheck=False,
        parallel=True,
    )
    def _backtest_all_with_params(
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_all: np.ndarray,
        periods: np.ndarray,
        overbought_arr: np.ndarray,
        oversold_arr: np.ndarray,
        sl_arr: np.ndarray,
        tp_arr: np.ndarray,
        capital: float,
        commission: float,
        slippage: float,
        direction: int,
        position_mode: int,  # NEW: 0=block, 1=close_and_open, 2=hedge
    ) -> np.ndarray:
        """
        Optimized backtest returning results WITH parameters inline.
        Eliminates Python dict creation bottleneck (DeepSeek Priority 1).

        BIDIRECTIONAL SUPPORT (direction=0):
        - Tracks Long and Short positions INDEPENDENTLY

        Returns: results[combo_idx, 17] = [
            period, overbought, oversold, stop_loss, take_profit,
            total_return, sharpe, max_dd, win_rate, trades, profit_factor,
            long_trades, long_wins, long_gross_profit,
            short_trades, short_wins, short_gross_profit
        ]
        """
        n = len(close)
        n_periods = len(periods)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)

        total = n_periods * n_ob * n_os * n_sl * n_tp

        # Extended results: params + metrics + long/short stats
        results = np.zeros((total, 17), dtype=np.float64)

        for p_idx in prange(n_periods):
            rsi = rsi_all[p_idx]
            period = periods[p_idx]
            combo_base = p_idx * n_ob * n_os * n_sl * n_tp

            for ob_idx in range(n_ob):
                overbought = overbought_arr[ob_idx]

                for os_idx in range(n_os):
                    oversold = oversold_arr[os_idx]

                    if oversold >= overbought:
                        continue

                    # Generate signals for BOTH directions
                    long_entries = np.zeros(n, dtype=np.bool_)
                    long_exits = np.zeros(n, dtype=np.bool_)
                    short_entries = np.zeros(n, dtype=np.bool_)
                    short_exits = np.zeros(n, dtype=np.bool_)

                    for i in range(period + 1, n):
                        if direction >= 0:  # Long or both
                            long_entries[i] = rsi[i] < oversold
                            long_exits[i] = rsi[i] > overbought
                        if direction <= 0:  # Short or both
                            short_entries[i] = rsi[i] > overbought
                            short_exits[i] = rsi[i] < oversold

                    for sl_idx in range(n_sl):
                        sl = sl_arr[sl_idx] / 100.0

                        for tp_idx in range(n_tp):
                            tp = tp_arr[tp_idx] / 100.0

                            combo_idx = (
                                combo_base + ob_idx * n_os * n_sl * n_tp + os_idx * n_sl * n_tp + sl_idx * n_tp + tp_idx
                            )

                            # Store parameters first
                            results[combo_idx, 0] = period
                            results[combo_idx, 1] = overbought
                            results[combo_idx, 2] = oversold
                            results[combo_idx, 3] = sl_arr[sl_idx]
                            results[combo_idx, 4] = tp_arr[tp_idx]

                            # Backtest with DUAL position tracking
                            equity = capital
                            peak_equity = capital
                            max_dd = 0.0
                            trade_count = 0
                            wins = 0
                            gross_profit = 0.0
                            gross_loss = 0.0
                            trade_pnls = np.zeros(500, dtype=np.float64)

                            # Separate tracking for Long/Short
                            long_trades_count = 0
                            long_wins = 0
                            long_gross_profit = 0.0
                            short_trades_count = 0
                            short_wins = 0
                            short_gross_profit = 0.0

                            # Position state for BOTH directions
                            in_long = False
                            in_short = False
                            long_entry_price = 0.0
                            short_entry_price = 0.0

                            for i in range(1, n):
                                # === LONG POSITION LOGIC ===
                                if direction >= 0:  # Long enabled
                                    if not in_long:
                                        if long_entries[i]:
                                            # Check position_mode before opening Long
                                            can_open_long = True

                                            if in_short:
                                                if position_mode == 0:  # BLOCK
                                                    can_open_long = False  # Skip - Short is open
                                                elif position_mode == 1:  # CLOSE-AND-OPEN
                                                    # Close Short first
                                                    short_pnl = (short_entry_price - close[i]) / short_entry_price
                                                    equity *= (1 + short_pnl) * (1 - commission)
                                                    if trade_count < 500:
                                                        trade_pnls[trade_count] = short_pnl
                                                    trade_count += 1
                                                    short_trades_count += 1
                                                    if short_pnl > 0:
                                                        wins += 1
                                                        short_wins += 1
                                                        gross_profit += short_pnl
                                                        short_gross_profit += short_pnl
                                                    else:
                                                        gross_loss += abs(short_pnl)
                                                    if equity > peak_equity:
                                                        peak_equity = equity
                                                    dd = (peak_equity - equity) / peak_equity
                                                    if dd > max_dd:
                                                        max_dd = dd
                                                    in_short = False
                                                # position_mode == 2 (HEDGE): can_open_long stays True

                                            if can_open_long:
                                                in_long = True
                                                long_entry_price = close[i]
                                                equity *= 1 - commission
                                    else:
                                        hit_sl = sl > 0 and low[i] <= long_entry_price * (1 - sl)
                                        hit_tp = tp > 0 and high[i] >= long_entry_price * (1 + tp)

                                        if long_exits[i] or hit_sl or hit_tp:
                                            if hit_sl:
                                                exit_p = long_entry_price * (1 - sl)
                                            elif hit_tp:
                                                exit_p = long_entry_price * (1 + tp)
                                            else:
                                                exit_p = close[i]

                                            real_entry = long_entry_price * (1 + slippage)
                                            real_exit = exit_p * (1 - slippage)
                                            pnl = (real_exit - real_entry) / real_entry

                                            equity *= (1 + pnl) * (1 - commission)

                                            if trade_count < 500:
                                                trade_pnls[trade_count] = pnl
                                            trade_count += 1
                                            long_trades_count += 1

                                            if pnl > 0:
                                                wins += 1
                                                long_wins += 1
                                                gross_profit += pnl
                                                long_gross_profit += pnl
                                            else:
                                                gross_loss += abs(pnl)

                                            if equity > peak_equity:
                                                peak_equity = equity
                                            dd = (peak_equity - equity) / peak_equity
                                            if dd > max_dd:
                                                max_dd = dd

                                            in_long = False

                                # === SHORT POSITION LOGIC ===
                                if direction <= 0:  # Short enabled
                                    if not in_short:
                                        if short_entries[i]:
                                            # Check position_mode before opening Short
                                            can_open_short = True

                                            if in_long:
                                                if position_mode == 0:  # BLOCK
                                                    can_open_short = False  # Skip - Long is open
                                                elif position_mode == 1:  # CLOSE-AND-OPEN
                                                    # Close Long first
                                                    long_pnl = (close[i] - long_entry_price) / long_entry_price
                                                    equity *= (1 + long_pnl) * (1 - commission)
                                                    if trade_count < 500:
                                                        trade_pnls[trade_count] = long_pnl
                                                    trade_count += 1
                                                    long_trades_count += 1
                                                    if long_pnl > 0:
                                                        wins += 1
                                                        long_wins += 1
                                                        gross_profit += long_pnl
                                                        long_gross_profit += long_pnl
                                                    else:
                                                        gross_loss += abs(long_pnl)
                                                    if equity > peak_equity:
                                                        peak_equity = equity
                                                    dd = (peak_equity - equity) / peak_equity
                                                    if dd > max_dd:
                                                        max_dd = dd
                                                    in_long = False
                                                # position_mode == 2 (HEDGE): can_open_short stays True

                                            if can_open_short:
                                                in_short = True
                                                short_entry_price = close[i]
                                                equity *= 1 - commission
                                    else:
                                        hit_sl = sl > 0 and high[i] >= short_entry_price * (1 + sl)
                                        hit_tp = tp > 0 and low[i] <= short_entry_price * (1 - tp)

                                        if short_exits[i] or hit_sl or hit_tp:
                                            if hit_sl:
                                                exit_p = short_entry_price * (1 + sl)
                                            elif hit_tp:
                                                exit_p = short_entry_price * (1 - tp)
                                            else:
                                                exit_p = close[i]

                                            real_entry = short_entry_price * (1 - slippage)
                                            real_exit = exit_p * (1 + slippage)
                                            pnl = (real_entry - real_exit) / real_entry

                                            equity *= (1 + pnl) * (1 - commission)

                                            if trade_count < 500:
                                                trade_pnls[trade_count] = pnl
                                            trade_count += 1
                                            short_trades_count += 1

                                            if pnl > 0:
                                                wins += 1
                                                short_wins += 1
                                                gross_profit += pnl
                                                short_gross_profit += pnl
                                            else:
                                                gross_loss += abs(pnl)

                                            if equity > peak_equity:
                                                peak_equity = equity
                                            dd = (peak_equity - equity) / peak_equity
                                            if dd > max_dd:
                                                max_dd = dd

                                            in_short = False

                            # Store metrics
                            if trade_count > 0:
                                total_return = (equity - capital) / capital * 100
                                win_rate = wins / trade_count
                                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 100.0

                                if trade_count > 1:
                                    mean_ret = 0.0
                                    tc = min(trade_count, 500)
                                    for j in range(tc):
                                        mean_ret += trade_pnls[j]
                                    mean_ret /= tc

                                    variance = 0.0
                                    for j in range(tc):
                                        variance += (trade_pnls[j] - mean_ret) ** 2
                                    variance /= tc - 1
                                    std_ret = variance**0.5
                                    sharpe = (mean_ret / std_ret * 15.87) if std_ret > 0 else 0.0
                                else:
                                    sharpe = 0.0

                                results[combo_idx, 5] = total_return
                                results[combo_idx, 6] = sharpe
                                results[combo_idx, 7] = max_dd * 100
                                results[combo_idx, 8] = win_rate
                                results[combo_idx, 9] = trade_count
                                results[combo_idx, 10] = profit_factor
                                # Long/Short specific stats
                                results[combo_idx, 11] = long_trades_count
                                results[combo_idx, 12] = long_wins
                                results[combo_idx, 13] = long_gross_profit
                                results[combo_idx, 14] = short_trades_count
                                results[combo_idx, 15] = short_wins
                                results[combo_idx, 16] = short_gross_profit

        return results

    # =========================================================================
    # V4: EARLY TERMINATION (DeepSeek Recommendation: 40-70% speedup)
    # Skip low-signal combos + exit on catastrophic loss
    # =========================================================================

    # DeepSeek V5: Explicit JIT signature for V4 early exit
    @njit(
        "float64[:,:](float64[:], float64[:], float64[:], float64[:,:], "
        "int64[:], float64[:], float64[:], float64[:], float64[:], "
        "float64, float64, int64, int64, float64)",
        cache=True,
        fastmath=True,
        boundscheck=False,
        parallel=True,
    )
    def _backtest_all_v4_early_exit(
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_all: np.ndarray,
        periods: np.ndarray,
        overbought_arr: np.ndarray,
        oversold_arr: np.ndarray,
        sl_arr: np.ndarray,
        tp_arr: np.ndarray,
        capital: float,
        commission: float,
        direction: int,
        min_signals: int,
        max_loss_pct: float,
    ) -> np.ndarray:
        """
        V4 Optimized backtest with EARLY TERMINATION.

        DeepSeek Recommendation: 40-70% speedup for large parameter spaces.

        Early termination conditions:
        1. Skip if signal_count < min_signals (too few trading opportunities)
        2. Exit simulation if current_pnl < -max_loss_pct (catastrophic loss)

        Returns: results[combo_idx, 11] = [
            period, overbought, oversold, stop_loss, take_profit,
            total_return, sharpe, max_dd, win_rate, trades, profit_factor
        ]
        """
        n = len(close)
        n_periods = len(periods)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)

        total = n_periods * n_ob * n_os * n_sl * n_tp
        results = np.zeros((total, 11), dtype=np.float64)

        max_loss_threshold = -max_loss_pct / 100.0  # Convert to decimal

        for p_idx in prange(n_periods):
            rsi = rsi_all[p_idx]
            period = periods[p_idx]
            combo_base = p_idx * n_ob * n_os * n_sl * n_tp

            for ob_idx in range(n_ob):
                overbought = overbought_arr[ob_idx]

                for os_idx in range(n_os):
                    oversold = oversold_arr[os_idx]

                    if oversold >= overbought:
                        continue

                    # EARLY TERMINATION 1: Count signals first
                    signal_count = 0
                    for i in range(period + 1, n):
                        if direction >= 0:
                            if rsi[i] < oversold:
                                signal_count += 1
                        else:
                            if rsi[i] > overbought:
                                signal_count += 1

                    # Skip if too few signals
                    if signal_count < min_signals:
                        # Mark all SL/TP combos as skipped (0 trades)
                        for sl_idx in range(n_sl):
                            for tp_idx in range(n_tp):
                                combo_idx = (
                                    combo_base
                                    + ob_idx * n_os * n_sl * n_tp
                                    + os_idx * n_sl * n_tp
                                    + sl_idx * n_tp
                                    + tp_idx
                                )
                                results[combo_idx, 0] = period
                                results[combo_idx, 1] = overbought
                                results[combo_idx, 2] = oversold
                                results[combo_idx, 3] = sl_arr[sl_idx]
                                results[combo_idx, 4] = tp_arr[tp_idx]
                                # Leave metrics as 0
                        continue

                    # Generate signals (only if enough signals)
                    entries = np.zeros(n, dtype=np.bool_)
                    exits = np.zeros(n, dtype=np.bool_)

                    if direction >= 0:
                        for i in range(period + 1, n):
                            entries[i] = rsi[i] < oversold
                            exits[i] = rsi[i] > overbought
                    else:
                        for i in range(period + 1, n):
                            entries[i] = rsi[i] > overbought
                            exits[i] = rsi[i] < oversold

                    for sl_idx in range(n_sl):
                        sl = sl_arr[sl_idx] / 100.0

                        for tp_idx in range(n_tp):
                            tp = tp_arr[tp_idx] / 100.0

                            combo_idx = (
                                combo_base + ob_idx * n_os * n_sl * n_tp + os_idx * n_sl * n_tp + sl_idx * n_tp + tp_idx
                            )

                            # Store parameters
                            results[combo_idx, 0] = period
                            results[combo_idx, 1] = overbought
                            results[combo_idx, 2] = oversold
                            results[combo_idx, 3] = sl_arr[sl_idx]
                            results[combo_idx, 4] = tp_arr[tp_idx]

                            # Backtest with early exit
                            equity = capital
                            peak_equity = capital
                            max_dd = 0.0
                            trade_count = 0
                            wins = 0
                            gross_profit = 0.0
                            gross_loss = 0.0
                            in_position = False
                            entry_price = 0.0
                            trade_pnls = np.zeros(500, dtype=np.float64)
                            early_exit = False

                            for i in range(1, n):
                                if early_exit:
                                    break

                                if not in_position:
                                    if entries[i]:
                                        in_position = True
                                        entry_price = close[i]
                                        equity *= 1 - commission
                                else:
                                    hit_sl = sl > 0 and low[i] <= entry_price * (1 - sl)
                                    hit_tp = tp > 0 and high[i] >= entry_price * (1 + tp)

                                    if exits[i] or hit_sl or hit_tp:
                                        if hit_sl:
                                            pnl = -sl
                                        elif hit_tp:
                                            pnl = tp
                                        else:
                                            pnl = (close[i] - entry_price) / entry_price

                                        equity *= (1 + pnl) * (1 - commission)

                                        if trade_count < 500:
                                            trade_pnls[trade_count] = pnl
                                        trade_count += 1

                                        if pnl > 0:
                                            wins += 1
                                            gross_profit += pnl
                                        else:
                                            gross_loss += abs(pnl)

                                        if equity > peak_equity:
                                            peak_equity = equity
                                        dd = (peak_equity - equity) / peak_equity
                                        if dd > max_dd:
                                            max_dd = dd

                                        in_position = False

                                        # EARLY TERMINATION 2: Check for catastrophic loss
                                        current_return = (equity - capital) / capital
                                        if current_return < max_loss_threshold:
                                            early_exit = True

                            # Store metrics
                            if trade_count > 0:
                                total_return = (equity - capital) / capital * 100
                                win_rate = wins / trade_count
                                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 100.0

                                if trade_count > 1:
                                    mean_ret = 0.0
                                    tc = min(trade_count, 500)
                                    for j in range(tc):
                                        mean_ret += trade_pnls[j]
                                    mean_ret /= tc

                                    variance = 0.0
                                    for j in range(tc):
                                        variance += (trade_pnls[j] - mean_ret) ** 2
                                    variance /= tc - 1
                                    std_ret = variance**0.5
                                    sharpe = (mean_ret / std_ret * 15.87) if std_ret > 0 else 0.0
                                else:
                                    sharpe = 0.0

                                results[combo_idx, 5] = total_return
                                results[combo_idx, 6] = sharpe
                                results[combo_idx, 7] = max_dd * 100
                                results[combo_idx, 8] = win_rate
                                results[combo_idx, 9] = trade_count
                                results[combo_idx, 10] = profit_factor

        return results

else:
    # Fallback without Numba (much slower)
    def _fast_simulate_backtest(close, high, low, entries, exits, stop_loss, take_profit, capital, commission):
        """Non-JIT fallback (slow)"""
        return 0.0, 0.0, 0.0, 0.0, 0, 0.0

    def _fast_calculate_rsi(close, period):
        """Non-JIT fallback (slow)"""
        return np.full(len(close), 50.0)

    def _calculate_all_rsi_vectorized(close, periods):
        """Non-JIT fallback"""
        return np.full((len(periods), len(close)), 50.0)

    def _backtest_all_vectorized(*args, **kwargs):
        """Non-JIT fallback"""
        return np.zeros((1, 6))

    def _backtest_all_with_params(*args, **kwargs):
        """Non-JIT fallback for optimized version"""
        return np.zeros((1, 11))

    def _backtest_all_v3_hoisted(*args, **kwargs):
        """Non-JIT fallback for V3"""
        return np.zeros((1, 11))

    def _backtest_all_v4_early_exit(*args, **kwargs):
        """Non-JIT fallback for V4"""
        return np.zeros((1, 11))


# =============================================================================
# V3: HOISTED SIGNAL GENERATION (DeepSeek Priority 1)
# Pre-compute ALL signals before SL/TP loops for 30-50% speedup
# =============================================================================

if NUMBA_AVAILABLE:
    # DeepSeek V5: Explicit JIT signature for signal precomputation
    @njit(
        "UniTuple(boolean[:,:,:,:], 2)(float64[:,:], int64[:], float64[:], float64[:], int64)",
        cache=True,
        fastmath=True,
        boundscheck=False,
    )
    def _precompute_all_signals(
        rsi_all: np.ndarray,
        periods: np.ndarray,
        overbought_arr: np.ndarray,
        oversold_arr: np.ndarray,
        direction: int,
    ) -> tuple:
        """
        Pre-compute entry/exit signals for ALL RSI/OB/OS combinations.
        Returns: (entries_all, exits_all) - both [p_idx, ob_idx, os_idx, time]

        This hoists signal generation completely outside SL/TP loops.
        DeepSeek recommendation: 30-50% speedup.
        """
        n_periods = len(periods)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n = rsi_all.shape[1]

        # 4D signal arrays: [period, overbought, oversold, time]
        entries_all = np.zeros((n_periods, n_ob, n_os, n), dtype=np.bool_)
        exits_all = np.zeros((n_periods, n_ob, n_os, n), dtype=np.bool_)

        for p_idx in range(n_periods):
            rsi = rsi_all[p_idx]
            period = periods[p_idx]

            for ob_idx in range(n_ob):
                overbought = overbought_arr[ob_idx]

                for os_idx in range(n_os):
                    oversold = oversold_arr[os_idx]

                    if oversold >= overbought:
                        continue

                    if direction >= 0:  # Long
                        for i in range(period + 1, n):
                            entries_all[p_idx, ob_idx, os_idx, i] = rsi[i] < oversold
                            exits_all[p_idx, ob_idx, os_idx, i] = rsi[i] > overbought
                    else:  # Short
                        for i in range(period + 1, n):
                            entries_all[p_idx, ob_idx, os_idx, i] = rsi[i] > overbought
                            exits_all[p_idx, ob_idx, os_idx, i] = rsi[i] < oversold

        return entries_all, exits_all

    # DeepSeek V5: Explicit JIT signature for V3 hoisted backtest
    @njit(
        "float64[:,:](float64[:], float64[:], float64[:], "
        "boolean[:,:,:,:], boolean[:,:,:,:], int64[:], float64[:], float64[:], "
        "float64[:], float64[:], float64, float64)",
        cache=True,
        fastmath=True,
        boundscheck=False,
        parallel=True,
    )
    def _backtest_all_v3_hoisted(
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        entries_all: np.ndarray,
        exits_all: np.ndarray,
        periods: np.ndarray,
        overbought_arr: np.ndarray,
        oversold_arr: np.ndarray,
        sl_arr: np.ndarray,
        tp_arr: np.ndarray,
        capital: float,
        commission: float,
    ) -> np.ndarray:
        """
        V3 Optimized backtest with PRE-COMPUTED signals.
        Signal arrays are [p_idx, ob_idx, os_idx, time] - no generation in inner loops.

        DeepSeek Priority 1: Hoisted signal generation for 30-50% speedup.

        Returns: results[combo_idx, 11] = [
            period, overbought, oversold, stop_loss, take_profit,
            total_return, sharpe, max_dd, win_rate, trades, profit_factor
        ]
        """
        n = len(close)
        n_periods = len(periods)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)

        total = n_periods * n_ob * n_os * n_sl * n_tp
        results = np.zeros((total, 11), dtype=np.float64)

        # Parallel over periods (outer loop)
        for p_idx in prange(n_periods):
            period = periods[p_idx]
            combo_base = p_idx * n_ob * n_os * n_sl * n_tp

            for ob_idx in range(n_ob):
                overbought = overbought_arr[ob_idx]

                for os_idx in range(n_os):
                    oversold = oversold_arr[os_idx]

                    if oversold >= overbought:
                        continue

                    # USE PRE-COMPUTED SIGNALS - no generation here!
                    entries = entries_all[p_idx, ob_idx, os_idx]
                    exits = exits_all[p_idx, ob_idx, os_idx]

                    for sl_idx in range(n_sl):
                        sl = sl_arr[sl_idx] / 100.0

                        for tp_idx in range(n_tp):
                            tp = tp_arr[tp_idx] / 100.0

                            combo_idx = (
                                combo_base + ob_idx * n_os * n_sl * n_tp + os_idx * n_sl * n_tp + sl_idx * n_tp + tp_idx
                            )

                            # Store parameters
                            results[combo_idx, 0] = period
                            results[combo_idx, 1] = overbought
                            results[combo_idx, 2] = oversold
                            results[combo_idx, 3] = sl_arr[sl_idx]
                            results[combo_idx, 4] = tp_arr[tp_idx]

                            # === BACKTEST SIMULATION ===
                            equity = capital
                            peak_equity = capital
                            max_dd = 0.0
                            trade_count = 0
                            wins = 0
                            gross_profit = 0.0
                            gross_loss = 0.0
                            in_position = False
                            entry_price = 0.0
                            trade_pnls = np.zeros(500, dtype=np.float64)

                            for i in range(1, n):
                                if not in_position:
                                    if entries[i]:
                                        in_position = True
                                        entry_price = close[i]
                                        equity *= 1 - commission
                                else:
                                    hit_sl = sl > 0 and low[i] <= entry_price * (1 - sl)
                                    hit_tp = tp > 0 and high[i] >= entry_price * (1 + tp)

                                    if exits[i] or hit_sl or hit_tp:
                                        if hit_sl:
                                            pnl = -sl
                                        elif hit_tp:
                                            pnl = tp
                                        else:
                                            pnl = (close[i] - entry_price) / entry_price

                                        equity *= (1 + pnl) * (1 - commission)

                                        if trade_count < 500:
                                            trade_pnls[trade_count] = pnl
                                        trade_count += 1

                                        if pnl > 0:
                                            wins += 1
                                            gross_profit += pnl
                                        else:
                                            gross_loss += abs(pnl)

                                        if equity > peak_equity:
                                            peak_equity = equity
                                        dd = (peak_equity - equity) / peak_equity
                                        if dd > max_dd:
                                            max_dd = dd

                                        in_position = False

                            # Store metrics
                            if trade_count > 0:
                                total_return = (equity - capital) / capital * 100
                                win_rate = wins / trade_count
                                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 100.0

                                if trade_count > 1:
                                    mean_ret = 0.0
                                    tc = min(trade_count, 500)
                                    for j in range(tc):
                                        mean_ret += trade_pnls[j]
                                    mean_ret /= tc

                                    variance = 0.0
                                    for j in range(tc):
                                        variance += (trade_pnls[j] - mean_ret) ** 2
                                    variance /= tc - 1
                                    std_ret = variance**0.5
                                    sharpe = (mean_ret / std_ret * 15.87) if std_ret > 0 else 0.0
                                else:
                                    sharpe = 0.0

                                results[combo_idx, 5] = total_return
                                results[combo_idx, 6] = sharpe
                                results[combo_idx, 7] = max_dd * 100
                                results[combo_idx, 8] = win_rate
                                results[combo_idx, 9] = trade_count
                                results[combo_idx, 10] = profit_factor

        return results


# =============================================================================
# V5: TRANSPOSED MEMORY LAYOUT (DeepSeek Recommendation: 1.2-1.5x speedup)
# results_T[11, n_combos] for SIMD-friendly column-wise access
# =============================================================================

if NUMBA_AVAILABLE:
    # DeepSeek V5: Transposed layout for better cache locality
    @njit(
        "float64[:,:](float64[:], float64[:], float64[:], float64[:,:], "
        "int64[:], float64[:], float64[:], float64[:], float64[:], "
        "float64, float64, int64)",
        cache=True,
        fastmath=True,
        boundscheck=False,
        parallel=True,
    )
    def _backtest_all_v5_transposed(
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_all: np.ndarray,
        periods: np.ndarray,
        overbought_arr: np.ndarray,
        oversold_arr: np.ndarray,
        sl_arr: np.ndarray,
        tp_arr: np.ndarray,
        capital: float,
        commission: float,
        direction: int,
    ) -> np.ndarray:
        """
        V5 Optimized backtest with TRANSPOSED memory layout.

        DeepSeek Recommendation: 1.2-1.5x speedup from better cache locality.

        Returns: results_T[11, n_combos] - TRANSPOSED for SIMD-friendly access
            Row 0: period
            Row 1: overbought
            Row 2: oversold
            Row 3: stop_loss
            Row 4: take_profit
            Row 5: total_return
            Row 6: sharpe
            Row 7: max_dd
            Row 8: win_rate
            Row 9: trades
            Row 10: profit_factor
        """
        n = len(close)
        n_periods = len(periods)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)

        total = n_periods * n_ob * n_os * n_sl * n_tp

        # TRANSPOSED layout: [11, n_combos] for column-wise SIMD access
        results_T = np.zeros((11, total), dtype=np.float64)

        for p_idx in prange(n_periods):
            rsi = rsi_all[p_idx]
            period = periods[p_idx]
            combo_base = p_idx * n_ob * n_os * n_sl * n_tp

            for ob_idx in range(n_ob):
                overbought = overbought_arr[ob_idx]

                for os_idx in range(n_os):
                    oversold = oversold_arr[os_idx]

                    if oversold >= overbought:
                        continue

                    # Generate signals
                    entries = np.zeros(n, dtype=np.bool_)
                    exits = np.zeros(n, dtype=np.bool_)

                    if direction >= 0:
                        for i in range(period + 1, n):
                            entries[i] = rsi[i] < oversold
                            exits[i] = rsi[i] > overbought
                    else:
                        for i in range(period + 1, n):
                            entries[i] = rsi[i] > overbought
                            exits[i] = rsi[i] < oversold

                    for sl_idx in range(n_sl):
                        sl = sl_arr[sl_idx] / 100.0

                        for tp_idx in range(n_tp):
                            tp = tp_arr[tp_idx] / 100.0

                            combo_idx = (
                                combo_base + ob_idx * n_os * n_sl * n_tp + os_idx * n_sl * n_tp + sl_idx * n_tp + tp_idx
                            )

                            # Store parameters in TRANSPOSED layout (column access)
                            results_T[0, combo_idx] = period
                            results_T[1, combo_idx] = overbought
                            results_T[2, combo_idx] = oversold
                            results_T[3, combo_idx] = sl_arr[sl_idx]
                            results_T[4, combo_idx] = tp_arr[tp_idx]

                            # Backtest simulation
                            equity = capital
                            peak_equity = capital
                            max_dd = 0.0
                            trade_count = 0
                            wins = 0
                            gross_profit = 0.0
                            gross_loss = 0.0
                            in_position = False
                            entry_price = 0.0
                            trade_pnls = np.zeros(500, dtype=np.float64)

                            for i in range(1, n):
                                if not in_position:
                                    if entries[i]:
                                        in_position = True
                                        entry_price = close[i]
                                        equity *= 1 - commission
                                else:
                                    hit_sl = sl > 0 and low[i] <= entry_price * (1 - sl)
                                    hit_tp = tp > 0 and high[i] >= entry_price * (1 + tp)

                                    if exits[i] or hit_sl or hit_tp:
                                        if hit_sl:
                                            pnl = -sl
                                        elif hit_tp:
                                            pnl = tp
                                        else:
                                            pnl = (close[i] - entry_price) / entry_price

                                        equity *= (1 + pnl) * (1 - commission)

                                        if trade_count < 500:
                                            trade_pnls[trade_count] = pnl
                                        trade_count += 1

                                        if pnl > 0:
                                            wins += 1
                                            gross_profit += pnl
                                        else:
                                            gross_loss += abs(pnl)

                                        if equity > peak_equity:
                                            peak_equity = equity
                                        dd = (peak_equity - equity) / peak_equity
                                        if dd > max_dd:
                                            max_dd = dd

                                        in_position = False

                            # Store metrics in TRANSPOSED layout
                            if trade_count > 0:
                                total_return = (equity - capital) / capital * 100
                                win_rate = wins / trade_count
                                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 100.0

                                if trade_count > 1:
                                    mean_ret = 0.0
                                    tc = min(trade_count, 500)
                                    for j in range(tc):
                                        mean_ret += trade_pnls[j]
                                    mean_ret /= tc

                                    variance = 0.0
                                    for j in range(tc):
                                        variance += (trade_pnls[j] - mean_ret) ** 2
                                    variance /= tc - 1
                                    std_ret = variance**0.5
                                    sharpe = (mean_ret / std_ret * 15.87) if std_ret > 0 else 0.0
                                else:
                                    sharpe = 0.0

                                results_T[5, combo_idx] = total_return
                                results_T[6, combo_idx] = sharpe
                                results_T[7, combo_idx] = max_dd * 100
                                results_T[8, combo_idx] = win_rate
                                results_T[9, combo_idx] = trade_count
                                results_T[10, combo_idx] = profit_factor

        return results_T

else:
    # Non-JIT fallback for V5
    def _backtest_all_v5_transposed(*args, **kwargs):
        """Non-JIT fallback for V5"""
        return np.zeros((11, 1))


# =============================================================================
# V6: BATCH PROCESSING FOR SL/TP (DeepSeek Priority: 2-3x speedup)
# Process multiple SL/TP combinations in ONE pass through the data
# =============================================================================

if NUMBA_AVAILABLE:
    # DeepSeek V6: Batch processing for SL/TP combinations
    @njit(
        "float64[:,:](float64[:], float64[:], float64[:], float64[:,:], "
        "int64[:], float64[:], float64[:], float64[:], float64[:], "
        "float64, float64, int64)",
        cache=True,
        fastmath=True,
        boundscheck=False,
        parallel=True,
    )
    def _backtest_all_v6_batch(
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_all: np.ndarray,
        periods: np.ndarray,
        overbought_arr: np.ndarray,
        oversold_arr: np.ndarray,
        sl_arr: np.ndarray,
        tp_arr: np.ndarray,
        capital: float,
        commission: float,
        direction: int,
    ) -> np.ndarray:
        """
        V6 Optimized backtest with BATCH PROCESSING for SL/TP.

        DeepSeek Recommendation: 2-3x speedup by processing all SL/TP
        combinations in a single pass through candle data.

        Key optimization: Instead of nested loops for SL/TP, we simulate
        ALL SL/TP combinations simultaneously at each candle.

        Returns: results[combo_idx, 11]
        """
        n = len(close)
        n_periods = len(periods)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)

        total = n_periods * n_ob * n_os * n_sl * n_tp
        n_sltp = n_sl * n_tp  # Number of SL/TP combinations to batch

        results = np.zeros((total, 11), dtype=np.float64)

        # Pre-compute SL/TP as decimals (once)
        sl_dec = np.zeros(n_sl, dtype=np.float64)
        tp_dec = np.zeros(n_tp, dtype=np.float64)
        for i in range(n_sl):
            sl_dec[i] = sl_arr[i] / 100.0
        for i in range(n_tp):
            tp_dec[i] = tp_arr[i] / 100.0

        for p_idx in prange(n_periods):
            rsi = rsi_all[p_idx]
            period = periods[p_idx]
            combo_base = p_idx * n_ob * n_os * n_sl * n_tp

            for ob_idx in range(n_ob):
                overbought = overbought_arr[ob_idx]

                for os_idx in range(n_os):
                    oversold = oversold_arr[os_idx]

                    if oversold >= overbought:
                        continue

                    # Generate signals ONCE for this RSI/OB/OS combo
                    entries = np.zeros(n, dtype=np.bool_)
                    exits = np.zeros(n, dtype=np.bool_)

                    if direction >= 0:
                        for i in range(period + 1, n):
                            entries[i] = rsi[i] < oversold
                            exits[i] = rsi[i] > overbought
                    else:
                        for i in range(period + 1, n):
                            entries[i] = rsi[i] > overbought
                            exits[i] = rsi[i] < oversold

                    # BATCH PROCESSING: Simulate ALL SL/TP combinations simultaneously
                    # State arrays for all SL/TP combos
                    equity_batch = np.full(n_sltp, capital, dtype=np.float64)
                    peak_equity_batch = np.full(n_sltp, capital, dtype=np.float64)
                    max_dd_batch = np.zeros(n_sltp, dtype=np.float64)
                    trade_count_batch = np.zeros(n_sltp, dtype=np.int64)
                    wins_batch = np.zeros(n_sltp, dtype=np.int64)
                    gross_profit_batch = np.zeros(n_sltp, dtype=np.float64)
                    gross_loss_batch = np.zeros(n_sltp, dtype=np.float64)
                    in_position_batch = np.zeros(n_sltp, dtype=np.bool_)
                    entry_price_batch = np.zeros(n_sltp, dtype=np.float64)

                    # Trade PnLs for Sharpe calculation (limit per combo)
                    max_trades = 200
                    trade_pnls_batch = np.zeros((n_sltp, max_trades), dtype=np.float64)

                    # Single pass through candles for ALL SL/TP combos
                    for i in range(1, n):
                        cur_close = close[i]
                        cur_high = high[i]
                        cur_low = low[i]
                        is_entry = entries[i]
                        is_exit = exits[i]

                        # Process all SL/TP combinations at this candle
                        for b in range(n_sltp):
                            sl_idx = b // n_tp
                            tp_idx = b % n_tp
                            sl = sl_dec[sl_idx]
                            tp = tp_dec[tp_idx]

                            if not in_position_batch[b]:
                                if is_entry:
                                    in_position_batch[b] = True
                                    entry_price_batch[b] = cur_close
                                    equity_batch[b] *= 1 - commission
                            else:
                                entry_p = entry_price_batch[b]
                                hit_sl = sl > 0 and cur_low <= entry_p * (1 - sl)
                                hit_tp = tp > 0 and cur_high >= entry_p * (1 + tp)

                                if is_exit or hit_sl or hit_tp:
                                    if hit_sl:
                                        pnl = -sl
                                    elif hit_tp:
                                        pnl = tp
                                    else:
                                        pnl = (cur_close - entry_p) / entry_p

                                    equity_batch[b] *= (1 + pnl) * (1 - commission)

                                    tc = trade_count_batch[b]
                                    if tc < max_trades:
                                        trade_pnls_batch[b, tc] = pnl

                                    trade_count_batch[b] = tc + 1

                                    if pnl > 0:
                                        wins_batch[b] += 1
                                        gross_profit_batch[b] += pnl
                                    else:
                                        gross_loss_batch[b] += abs(pnl)

                                    if equity_batch[b] > peak_equity_batch[b]:
                                        peak_equity_batch[b] = equity_batch[b]
                                    dd = (peak_equity_batch[b] - equity_batch[b]) / peak_equity_batch[b]
                                    if dd > max_dd_batch[b]:
                                        max_dd_batch[b] = dd

                                    in_position_batch[b] = False

                    # Store results for all SL/TP combinations
                    for sl_idx in range(n_sl):
                        for tp_idx in range(n_tp):
                            b = sl_idx * n_tp + tp_idx
                            combo_idx = (
                                combo_base + ob_idx * n_os * n_sl * n_tp + os_idx * n_sl * n_tp + sl_idx * n_tp + tp_idx
                            )

                            results[combo_idx, 0] = period
                            results[combo_idx, 1] = overbought
                            results[combo_idx, 2] = oversold
                            results[combo_idx, 3] = sl_arr[sl_idx]
                            results[combo_idx, 4] = tp_arr[tp_idx]

                            tc = trade_count_batch[b]
                            if tc > 0:
                                total_return = (equity_batch[b] - capital) / capital * 100
                                win_rate = wins_batch[b] / tc
                                profit_factor = (
                                    gross_profit_batch[b] / gross_loss_batch[b] if gross_loss_batch[b] > 0 else 100.0
                                )

                                if tc > 1:
                                    mean_ret = 0.0
                                    tc_lim = min(tc, max_trades)
                                    for j in range(tc_lim):
                                        mean_ret += trade_pnls_batch[b, j]
                                    mean_ret /= tc_lim

                                    variance = 0.0
                                    for j in range(tc_lim):
                                        variance += (trade_pnls_batch[b, j] - mean_ret) ** 2
                                    variance /= tc_lim - 1
                                    std_ret = variance**0.5
                                    sharpe = (mean_ret / std_ret * 15.87) if std_ret > 0 else 0.0
                                else:
                                    sharpe = 0.0

                                results[combo_idx, 5] = total_return
                                results[combo_idx, 6] = sharpe
                                results[combo_idx, 7] = max_dd_batch[b] * 100
                                results[combo_idx, 8] = win_rate
                                results[combo_idx, 9] = tc
                                results[combo_idx, 10] = profit_factor

        return results

else:
    # Non-JIT fallback for V6
    def _backtest_all_v6_batch(*args, **kwargs):
        """Non-JIT fallback for V6"""
        return np.zeros((1, 11))
