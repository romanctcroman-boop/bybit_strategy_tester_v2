"""
Parallel worker function and GPU RSI/backtest helpers.

Extracted from gpu_optimizer.py (lines 2108-2528).
Contains:
  - _process_rsi_period()         — per-period parallel worker (joblib)
  - _calculate_all_rsi_gpu()      — GPU RSI (CuPy) or CPU fallback
  - _backtest_all_gpu()           — GPU backtest (CuPy) or CPU fallback
"""

import contextlib

import numpy as np

from backend.backtesting.gpu.device import GPU_AVAILABLE, cp
from backend.backtesting.gpu.kernels import (
    NUMBA_AVAILABLE,
    _backtest_all_with_params,
    _calculate_all_rsi_vectorized,
    _fast_calculate_rsi,
    _fast_simulate_backtest,
)

with contextlib.suppress(ImportError):
    from numba import njit, prange  # needed for inline GPU @njit blocks


# =============================================================================
# Parallel worker function (must be at module level for joblib)
# =============================================================================


def _process_rsi_period(
    period: int,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    overbought_levels: list[int],
    oversold_levels: list[int],
    stop_losses: list[float],
    take_profits: list[float],
    initial_capital: float,
    leverage: int,
    commission: float,
    direction: str,
) -> list[dict]:
    """
    Process a single RSI period with all parameter combinations.
    This runs in a separate process via joblib.
    """
    results = []

    # Calculate RSI for this period
    rsi = _fast_calculate_rsi(close, period)

    for overbought in overbought_levels:
        for oversold in oversold_levels:
            if oversold >= overbought:
                continue

            # Generate signals
            if direction == "long":
                entries = rsi < oversold
                exits = rsi > overbought
            elif direction == "short":
                entries = rsi > overbought
                exits = rsi < oversold
            else:
                entries = rsi < oversold
                exits = rsi > overbought

            for sl in stop_losses:
                for tp in take_profits:
                    sl_val = sl / 100.0 if sl else 0.0
                    tp_val = tp / 100.0 if tp else 0.0

                    total_return, sharpe, max_dd, win_rate, total_trades, pf = _fast_simulate_backtest(
                        close,
                        high,
                        low,
                        entries.astype(np.bool_),
                        exits.astype(np.bool_),
                        sl_val,
                        tp_val,
                        initial_capital * leverage,
                        commission,
                        1.0,  # position_size - 100% in parallel worker
                    )

                    if total_trades > 0:
                        results.append(
                            {
                                "params": {
                                    "rsi_period": period,
                                    "rsi_overbought": overbought,
                                    "rsi_oversold": oversold,
                                    "stop_loss_pct": sl,
                                    "take_profit_pct": tp,
                                },
                                "total_return": round(total_return, 2),
                                "sharpe_ratio": round(sharpe, 2),
                                "max_drawdown": round(max_dd, 2),
                                "win_rate": round(win_rate, 4),
                                "total_trades": int(total_trades),
                                "profit_factor": round(pf, 2),
                            }
                        )

    return results


# =============================================================================
# GPU-ACCELERATED FUNCTIONS (CuPy)
# For massive parallelization of RSI, signals, and backtest
# =============================================================================

if GPU_AVAILABLE and cp is not None:

    def _calculate_all_rsi_gpu(close: np.ndarray, periods: np.ndarray) -> np.ndarray:
        """
        GPU-accelerated RSI calculation for ALL periods at once.

        Uses CuPy for vectorized operations on GPU.
        Returns: rsi_matrix[n_periods, n_candles] as numpy array
        """
        n = len(close)
        n_periods = len(periods)

        # Transfer to GPU
        close_gpu = cp.asarray(close, dtype=cp.float64)

        # Pre-compute deltas once on GPU
        delta = cp.diff(close_gpu, prepend=close_gpu[0])
        gains = cp.maximum(delta, 0.0)
        losses = cp.maximum(-delta, 0.0)

        # Output matrix on GPU
        rsi_all_gpu = cp.full((n_periods, n), 50.0, dtype=cp.float64)

        for p_idx in range(n_periods):
            period = int(periods[p_idx])
            if period >= n:
                continue

            # First average using sum (GPU vectorized)
            sum_gain = cp.sum(gains[1 : period + 1])
            sum_loss = cp.sum(losses[1 : period + 1])

            avg_gain = sum_gain / period
            avg_loss = sum_loss / period

            # Wilders EMA - need to iterate (transfer small arrays)
            alpha = 1.0 / period

            # For EMA we need sequential computation, do on CPU
            avg_gain_cpu = float(avg_gain.get())
            avg_loss_cpu = float(avg_loss.get())
            gains_cpu = gains.get()
            losses_cpu = losses.get()

            rsi_row = np.full(n, 50.0, dtype=np.float64)

            for i in range(period + 1, n):
                avg_gain_cpu = alpha * gains_cpu[i] + (1 - alpha) * avg_gain_cpu
                avg_loss_cpu = alpha * losses_cpu[i] + (1 - alpha) * avg_loss_cpu

                if avg_loss_cpu > 1e-12:
                    rs = avg_gain_cpu / avg_loss_cpu
                    rsi_row[i] = 100.0 - (100.0 / (1.0 + rs))

            rsi_all_gpu[p_idx] = cp.asarray(rsi_row)

        # Transfer back to CPU
        return rsi_all_gpu.get()

    def _backtest_all_gpu(
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
        cp_dtype: "cp.dtype" = None,
    ) -> np.ndarray:
        """
        GPU-accelerated backtest for ALL parameter combinations.

        Strategy: Use GPU for signal generation and filtering,
        then run backtest simulation on CPU (sequential nature).

        Returns: results[combo_idx, 11]
        """
        n = len(close)
        n_periods = len(periods)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)

        total = n_periods * n_ob * n_os * n_sl * n_tp

        if cp_dtype is None:
            cp_dtype = cp.float64

        # Transfer RSI data to GPU for signal generation
        rsi_gpu = cp.asarray(rsi_all, dtype=cp_dtype)

        # Pre-generate ALL signals on GPU (massive parallelization)
        # Shape: [n_periods, n_ob, n_os, n_candles]
        entries_all = cp.zeros((n_periods, n_ob, n_os, n), dtype=cp.bool_)
        exits_all = cp.zeros((n_periods, n_ob, n_os, n), dtype=cp.bool_)

        for p_idx in range(n_periods):
            rsi = rsi_gpu[p_idx]
            period = int(periods[p_idx])

            for ob_idx in range(n_ob):
                overbought = float(overbought_arr[ob_idx])

                for os_idx in range(n_os):
                    oversold = float(oversold_arr[os_idx])

                    if oversold >= overbought:
                        continue

                    # Generate signals on GPU (vectorized boolean ops)
                    if direction >= 0:
                        entries_all[p_idx, ob_idx, os_idx, period + 1 :] = rsi[period + 1 :] < oversold
                        exits_all[p_idx, ob_idx, os_idx, period + 1 :] = rsi[period + 1 :] > overbought
                    else:
                        entries_all[p_idx, ob_idx, os_idx, period + 1 :] = rsi[period + 1 :] > overbought
                        exits_all[p_idx, ob_idx, os_idx, period + 1 :] = rsi[period + 1 :] < oversold

        # Transfer signals back to CPU for sequential backtest
        entries_cpu = entries_all.get()
        exits_cpu = exits_all.get()
        close_cpu = close
        high_cpu = high
        low_cpu = low

        # Results array
        results = np.zeros((total, 11), dtype=np.float64)

        # Run backtest on CPU (sequential nature of trading)
        # Use Numba parallel for combinations
        if NUMBA_AVAILABLE:
            results = _backtest_combinations_numba(
                close_cpu,
                high_cpu,
                low_cpu,
                entries_cpu,
                exits_cpu,
                periods,
                overbought_arr,
                oversold_arr,
                sl_arr,
                tp_arr,
                capital,
                commission,
            )
        else:
            # Fallback to pure Python (slow) - no actual backtest, just params
            combo_idx = 0
            for p_idx in range(n_periods):
                for ob_idx in range(n_ob):
                    for os_idx in range(n_os):
                        # Skip invalid combinations
                        if oversold_arr[os_idx] >= overbought_arr[ob_idx]:
                            continue

                        for sl_idx in range(n_sl):
                            for tp_idx in range(n_tp):
                                # Store params
                                results[combo_idx, 0] = periods[p_idx]
                                results[combo_idx, 1] = overbought_arr[ob_idx]
                                results[combo_idx, 2] = oversold_arr[os_idx]
                                results[combo_idx, 3] = sl_arr[sl_idx]
                                results[combo_idx, 4] = tp_arr[tp_idx]
                                # Metrics would be 0 (fallback)
                                combo_idx += 1

        return results

    # Numba helper for GPU version
    if NUMBA_AVAILABLE:

        @njit(cache=True, fastmath=True, boundscheck=False, parallel=True)
        def _backtest_combinations_numba(
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
            """Run backtest for all combinations with pre-computed signals."""
            n = len(close)
            n_periods = len(periods)
            n_ob = len(overbought_arr)
            n_os = len(oversold_arr)
            n_sl = len(sl_arr)
            n_tp = len(tp_arr)

            total = n_periods * n_ob * n_os * n_sl * n_tp
            results = np.zeros((total, 11), dtype=np.float64)

            for p_idx in prange(n_periods):
                period = periods[p_idx]
                combo_base = p_idx * n_ob * n_os * n_sl * n_tp

                for ob_idx in range(n_ob):
                    overbought = overbought_arr[ob_idx]

                    for os_idx in range(n_os):
                        oversold = oversold_arr[os_idx]

                        if oversold >= overbought:
                            continue

                        entries = entries_all[p_idx, ob_idx, os_idx]
                        exits = exits_all[p_idx, ob_idx, os_idx]

                        for sl_idx in range(n_sl):
                            sl = sl_arr[sl_idx] / 100.0

                            for tp_idx in range(n_tp):
                                tp = tp_arr[tp_idx] / 100.0

                                combo_idx = (
                                    combo_base
                                    + ob_idx * n_os * n_sl * n_tp
                                    + os_idx * n_sl * n_tp
                                    + sl_idx * n_tp
                                    + tp_idx
                                )

                                # Store params
                                results[combo_idx, 0] = period
                                results[combo_idx, 1] = overbought
                                results[combo_idx, 2] = oversold
                                results[combo_idx, 3] = sl_arr[sl_idx]
                                results[combo_idx, 4] = tp_arr[tp_idx]

                                # Backtest
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

else:
    # Fallback when GPU not available
    def _calculate_all_rsi_gpu(close, periods):
        return _calculate_all_rsi_vectorized(close, periods)

    def _backtest_all_gpu(*args, **kwargs):
        return _backtest_all_with_params(*args, **kwargs)
