"""
GPU-Accelerated Grid Optimizer

Hybrid GPU/CPU optimization using CuPy for NVIDIA GPUs.
RSI calculation and signal generation on GPU, portfolio metrics on CPU.

Performance targets:
- 100K combinations: ~5-10 seconds
- 1M combinations: ~30-60 seconds
- 10M combinations: ~5-10 minutes

Requirements:
- NVIDIA GPU with CUDA support
- CuPy installed (pip install cupy-cuda12x)

NOTE: Metric calculations (Sharpe, Sortino, Calmar, etc.) should use
backend.core.metrics_calculator as the single source of truth.
This ensures consistency across all optimizers and backtest engine.

REFACTOR NEEDED: Replace inline metric formulas with
`MetricsCalculator.calculate_metrics_numba()` calls to keep
Sharpe/Sortino/Calmar consistent with FallbackEngineV4.
Scope: ~200 lines in _run_cpu_grid_search() and _run_gpu_grid_search().
"""

import atexit
import os
import time
import warnings
from dataclasses import dataclass
from multiprocessing import Pool, shared_memory
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore", category=FutureWarning)

# Joblib availability check (for potential future use)
try:
    import joblib  # noqa: F401

    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False

# Number of parallel workers
N_WORKERS = os.cpu_count() or 4

# Safety limit to avoid runaway grids that exhaust memory/time
MAX_COMBINATIONS = 50_000_000

# Global warm worker pool (initialized once, reused)
_WARM_POOL = None
_SHARED_MEMORY_BLOCKS = []  # Track for cleanup


# =============================================================================
# LAZY GPU INITIALIZATION
# CuPy is loaded only when GPU is actually needed to speed up startup
# =============================================================================

# GPU state - initialized lazily on first use
GPU_AVAILABLE = None  # None = not checked yet, True/False after check
cp = None
GPU_NAME = "Not initialized"
_gpu_init_done = False


def _setup_cuda_path():
    """Add CUDA bin to PATH for NVRTC libraries"""
    cuda_paths = [
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
    ]

    current_path = os.environ.get("PATH", "")
    for cuda_bin in cuda_paths:
        if os.path.exists(cuda_bin) and cuda_bin not in current_path:
            os.environ["PATH"] = cuda_bin + os.pathsep + current_path
            logger.debug(f"Added CUDA to PATH: {cuda_bin}")
            return cuda_bin
    return None


def _init_gpu():
    """
    Initialize GPU/CuPy on first use (lazy loading).
    Returns True if GPU is available, False otherwise.
    """
    global GPU_AVAILABLE, cp, GPU_NAME, _gpu_init_done

    if _gpu_init_done:
        return GPU_AVAILABLE

    _gpu_init_done = True
    _setup_cuda_path()

    try:
        import cupy as _cp

        # Test actual GPU operations
        _test = _cp.array([1.0, 2.0, 3.0], dtype=_cp.float64)
        _result = _cp.diff(_test)
        _cp.cuda.Stream.null.synchronize()
        del _test, _result

        cp = _cp
        GPU_AVAILABLE = True

        try:
            device = _cp.cuda.Device()
            mem_info = device.mem_info
            GPU_NAME = f"GPU {device.id} ({mem_info[1] / 1024**3:.1f}GB)"
        except Exception:
            GPU_NAME = "NVIDIA GPU"

        logger.info(f"🚀 GPU acceleration enabled: {GPU_NAME}")
        return True

    except Exception as e:
        cp = None
        GPU_AVAILABLE = False
        GPU_NAME = "None"
        logger.info(f"GPU not available (using CPU): {e}")
        return False


def is_gpu_available():
    """Check if GPU is available, initializing if needed."""
    if GPU_AVAILABLE is None:
        _init_gpu()
    return GPU_AVAILABLE


# Fallback to Numba for CPU
try:
    from numba import njit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False


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


# =============================================================================
# Warm Process Pool with Shared Memory (DeepSeek optimized pattern)
# =============================================================================

# Worker global state (initialized once per worker)
_worker_data = {}


def _worker_init(shm_name: str, shape: tuple, dtype: str, close_len: int):
    """
    Worker initialization function. Runs once per worker process.
    Attaches to shared memory and pre-warms Numba JIT compilation.
    """
    global _worker_data

    try:
        # Attach to shared memory
        shm = shared_memory.SharedMemory(name=shm_name)
        _worker_data["shm"] = shm

        # Reconstruct arrays from shared memory
        total_size = close_len * 3  # close, high, low
        all_data = np.ndarray((total_size,), dtype=np.float64, buffer=shm.buf)
        _worker_data["close"] = all_data[:close_len].copy()
        _worker_data["high"] = all_data[close_len : 2 * close_len].copy()
        _worker_data["low"] = all_data[2 * close_len :].copy()
        _worker_data["close_len"] = close_len

        # Pre-warm Numba JIT compilation with dummy data (happens only on first call)
        if NUMBA_AVAILABLE:
            dummy_close = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0] * 5, dtype=np.float64)
            dummy_high = dummy_close * 1.01
            dummy_low = dummy_close * 0.99
            dummy_entries = np.array([False, True, False, False] * 10, dtype=np.bool_)
            dummy_exits = np.array([False, False, True, False] * 10, dtype=np.bool_)

            # Trigger RSI compilation
            _fast_calculate_rsi(dummy_close, 3)

            # Trigger backtest compilation
            _fast_simulate_backtest(
                dummy_close,
                dummy_high,
                dummy_low,
                dummy_entries,
                dummy_exits,
                0.02,
                0.04,
                10000.0,
                0.001,
                0.0005,  # slippage
                1.0,  # position_size
            )

        logger.debug(f"Worker initialized, data attached ({close_len} candles)")

    except Exception as e:
        logger.error(f"Worker init error: {e}")
        raise


def _worker_process_period(args: tuple):
    """
    Process a single RSI period using data from shared memory.
    This function runs in a worker process.
    """
    (
        period,
        overbought_levels,
        oversold_levels,
        stop_losses,
        take_profits,
        initial_capital,
        leverage,
        commission,
        slippage,
        direction,
    ) = args

    global _worker_data
    close = _worker_data["close"]
    high = _worker_data["high"]
    low = _worker_data["low"]

    results = []

    # Calculate RSI for this period (Numba JIT already compiled)
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
                        slippage,
                        1.0,  # position_size - 100% in worker (leverage already applied to capital)
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


class WarmProcessPool:
    """
    Pre-warmed process pool with shared memory for zero-copy data transfer.
    Workers are initialized once and reused, Numba functions are pre-compiled.
    """

    def __init__(self, n_workers: int | None = None):
        self.n_workers = n_workers or N_WORKERS
        self.pool = None
        self.shm = None
        self.close_len = 0
        logger.info(f"WarmProcessPool created with {self.n_workers} workers")

    def initialize(self, close: np.ndarray, high: np.ndarray, low: np.ndarray):
        """Initialize pool with shared memory containing price data."""
        self.close_len = len(close)

        # Create shared memory block for all price data (contiguous)
        total_size = self.close_len * 3 * 8  # 3 arrays, float64 = 8 bytes
        self.shm = shared_memory.SharedMemory(create=True, size=total_size)
        _SHARED_MEMORY_BLOCKS.append(self.shm)

        # Copy data into shared memory
        all_data = np.ndarray((self.close_len * 3,), dtype=np.float64, buffer=self.shm.buf)
        all_data[: self.close_len] = close
        all_data[self.close_len : 2 * self.close_len] = high
        all_data[2 * self.close_len :] = low

        # Create pool with initializer (workers pre-warm Numba)
        logger.info(f"Starting {self.n_workers} workers with shared memory ({total_size / 1024 / 1024:.2f} MB)...")
        start_init = time.time()

        self.pool = Pool(
            processes=self.n_workers,
            initializer=_worker_init,
            initargs=(self.shm.name, (self.close_len * 3,), "float64", self.close_len),
        )

        init_time = time.time() - start_init
        logger.info(f"Pool initialized in {init_time:.2f}s (workers pre-warmed)")

    def map_periods(
        self,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        slippage: float,
        direction: str,
        top_k: int = 1000,
        gpu_dtype: str = "float64",
    ) -> list[dict]:
        """Process all RSI periods in parallel."""
        if self.pool is None:
            raise RuntimeError("Pool not initialized. Call initialize() first.")

        # Prepare arguments for each period
        tasks = [
            (
                period,
                list(overbought_levels),
                list(oversold_levels),
                list(stop_losses),
                list(take_profits),
                initial_capital,
                leverage,
                commission,
                slippage,
                direction,
            )
            for period in rsi_periods
        ]

        # Process in parallel
        all_results = self.pool.map(_worker_process_period, tasks)

        # Flatten results
        results = []
        for period_results in all_results:
            results.extend(period_results)

        return results

    def close(self):
        """Close pool and release shared memory."""
        if self.pool:
            self.pool.close()
            self.pool.join()
            self.pool = None
        if self.shm:
            try:
                self.shm.close()
                self.shm.unlink()
            except Exception as e:
                logger.debug(f"Shared memory cleanup: {e}")
            self.shm = None


def _cleanup_shared_memory():
    """Cleanup any remaining shared memory blocks on exit."""
    global _WARM_POOL, _SHARED_MEMORY_BLOCKS
    if _WARM_POOL:
        _WARM_POOL.close()
        _WARM_POOL = None
    for shm in _SHARED_MEMORY_BLOCKS:
        try:
            shm.close()
            shm.unlink()
        except Exception:
            pass
    _SHARED_MEMORY_BLOCKS.clear()


# Register cleanup on exit
atexit.register(_cleanup_shared_memory)


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


@dataclass
class GPUOptimizationResult:
    """Result of GPU-accelerated optimization"""

    status: str
    total_combinations: int
    tested_combinations: int
    execution_time_seconds: float
    best_params: dict[str, Any]
    best_score: float
    best_metrics: dict[str, Any]
    top_results: list[dict[str, Any]]
    performance_stats: dict[str, Any]
    execution_mode: str
    fallback_reason: str | None = None


class GPUGridOptimizer:
    """
    High-performance grid optimizer using GPU acceleration.

    Uses CuPy for:
    - RSI calculation (vectorized on GPU)
    - Signal generation (boolean operations on GPU)
    - Metric aggregation (reductions on GPU)

    Falls back to Numba JIT on CPU if GPU unavailable.
    """

    def __init__(self, position_size: float = 1.0, force_cpu: bool = False):
        self.use_gpu = GPU_AVAILABLE and not force_cpu
        self.position_size = position_size
        if self.use_gpu:
            logger.info("GPUGridOptimizer initialized with GPU acceleration")
        else:
            logger.info("GPUGridOptimizer using CPU fallback")

    def optimize(
        self,
        candles: pd.DataFrame,
        rsi_period_range: list[int],
        rsi_overbought_range: list[int],
        rsi_oversold_range: list[int],
        stop_loss_range: list[float],
        take_profit_range: list[float],
        initial_capital: float = 10000.0,
        leverage: int = 1,
        commission: float = 0.0007,  # 0.07% TradingView parity
        slippage: float = 0.0005,
        optimize_metric: str = "sharpe_ratio",
        direction: str = "long",
        position_size: float | None = None,
        top_k: int = 1000,
        gpu_dtype: str = "float64",
        **kwargs,
    ) -> GPUOptimizationResult:
        """
        Run GPU-accelerated grid search optimization.
        """
        execution_mode = "gpu" if self.use_gpu else "cpu"
        fallback_reason: str | None = None

        # Use provided position_size or instance default
        if position_size is not None:
            self.position_size = position_size

        start_time = time.time()

        # Validate inputs early to avoid wasted work
        if candles is None or candles.empty:
            raise ValueError("Candles dataframe is empty")

        required_cols = {"close", "high", "low"}
        if not required_cols.issubset(candles.columns):
            missing = required_cols - set(candles.columns)
            raise ValueError(f"Candles missing required columns: {missing}")

        if not rsi_period_range or not rsi_overbought_range or not rsi_oversold_range:
            raise ValueError("RSI ranges must be non-empty")
        if not stop_loss_range or not take_profit_range:
            raise ValueError("Stop loss / take profit ranges must be non-empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if gpu_dtype not in {"float64", "float32"}:
            raise ValueError("gpu_dtype must be 'float64' or 'float32'")

        # Calculate total combinations
        total_combinations = (
            len(rsi_period_range)
            * len(rsi_overbought_range)
            * len(rsi_oversold_range)
            * len(stop_loss_range)
            * len(take_profit_range)
        )

        # Extract position_mode from kwargs (default: block)
        position_mode = kwargs.get("position_mode", "block")

        if total_combinations == 0:
            raise ValueError("No parameter combinations to evaluate")
        if total_combinations > MAX_COMBINATIONS:
            raise ValueError(
                f"Too many combinations ({total_combinations:,}). Reduce the grid below {MAX_COMBINATIONS:,}."
            )

        logger.info("🚀 GPU Grid Optimizer starting")
        logger.info(f"   Total combinations: {total_combinations:,}")
        logger.info(f"   Numba JIT: {NUMBA_AVAILABLE}, Joblib: {JOBLIB_AVAILABLE}")
        logger.info(f"   Workers: {N_WORKERS}")

        # Prepare data
        close = candles["close"].values.astype(np.float64)
        high = candles["high"].values.astype(np.float64)
        low = candles["low"].values.astype(np.float64)
        n_candles = len(close)

        if n_candles < 2:
            raise ValueError("Not enough candles to run optimization")

        if not (np.isfinite(close).all() and np.isfinite(high).all() and np.isfinite(low).all()):
            raise ValueError("Candles contain NaN or infinite values")

        # Use parallel processing for large parameter spaces (joblib works on Windows)
        # Single-threaded Numba achieves ~25,000-30,000 combinations/second
        # Parallel processing has ~25s overhead for worker initialization on Windows
        # Break-even point is approximately 10M+ combinations
        # For most practical cases, single-threaded is faster
        use_parallel = (
            JOBLIB_AVAILABLE
            and NUMBA_AVAILABLE
            and total_combinations > 10000000  # Only for 10M+ combinations
            and len(rsi_period_range) >= N_WORKERS
        )

        # NEW: Use vectorized optimization (DeepSeek recommendation - 14x faster)
        # This processes ALL parameters simultaneously with parallel prange
        use_vectorized = NUMBA_AVAILABLE and total_combinations <= 10000000

        if use_vectorized:
            execution_mode = "cpu_vectorized"
            logger.info("   Using VECTORIZED optimization (DeepSeek - 14x faster)")
            results = self._optimize_vectorized(
                close,
                high,
                low,
                rsi_period_range,
                rsi_overbought_range,
                rsi_oversold_range,
                stop_loss_range,
                take_profit_range,
                initial_capital,
                leverage,
                commission,
                slippage,
                direction,
                position_mode,  # NEW: Pass position mode
                top_k,
                gpu_dtype,
            )
        elif use_parallel:
            execution_mode = "cpu_parallel"
            logger.info(f"   Using parallel processing ({N_WORKERS} workers)")
            results = self._optimize_parallel(
                close,
                high,
                low,
                rsi_period_range,
                rsi_overbought_range,
                rsi_oversold_range,
                stop_loss_range,
                take_profit_range,
                initial_capital,
                leverage,
                commission,
                slippage,
                direction,
                top_k,
                gpu_dtype,
            )
        elif self.use_gpu:
            try:
                execution_mode = "gpu"
                results = self._optimize_gpu(
                    close,
                    high,
                    low,
                    n_candles,
                    rsi_period_range,
                    rsi_overbought_range,
                    rsi_oversold_range,
                    stop_loss_range,
                    take_profit_range,
                    initial_capital,
                    leverage,
                    commission,
                    slippage,
                    direction,
                    top_k,
                    gpu_dtype,
                )
            except Exception as e:
                fallback_reason = f"GPU path failed: {e}"
                logger.warning(f"GPU failed, falling back to CPU: {e}")
                execution_mode = "cpu_fallback"
                results = self._optimize_cpu(
                    close,
                    high,
                    low,
                    n_candles,
                    rsi_period_range,
                    rsi_overbought_range,
                    rsi_oversold_range,
                    stop_loss_range,
                    take_profit_range,
                    initial_capital,
                    leverage,
                    commission,
                    slippage,
                    direction,
                    top_k,
                    gpu_dtype,
                )
        else:
            execution_mode = "cpu"
            results = self._optimize_cpu(
                close,
                high,
                low,
                n_candles,
                rsi_period_range,
                rsi_overbought_range,
                rsi_oversold_range,
                stop_loss_range,
                take_profit_range,
                initial_capital,
                leverage,
                commission,
                slippage,
                direction,
                top_k,
                gpu_dtype,
            )

        # Calculate scores
        results = self._calculate_scores(results, optimize_metric)

        # Sort by score
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        execution_time = time.time() - start_time
        combinations_per_second = total_combinations / execution_time if execution_time > 0 else 0

        logger.info(f"✅ Optimization completed in {execution_time:.2f}s")
        logger.info(f"   Speed: {combinations_per_second:,.0f} combinations/second")
        logger.info(f"   Valid results: {len(results):,} (top 1000 returned)")

        best = results[0] if results else {}

        return GPUOptimizationResult(
            status="completed",
            total_combinations=total_combinations,
            tested_combinations=total_combinations,  # All combinations are tested
            execution_time_seconds=round(execution_time, 2),
            best_params=best.get("params", {}),
            best_score=best.get("score", 0),
            best_metrics={
                "total_return": best.get("total_return", 0),
                "sharpe_ratio": best.get("sharpe_ratio", 0),
                "max_drawdown": best.get("max_drawdown", 0),
                "win_rate": best.get("win_rate", 0),
                "total_trades": best.get("total_trades", 0),
                "profit_factor": best.get("profit_factor", 0),
                # Long/Short breakdown
                "long_trades": best.get("long_trades", 0),
                "long_winning_trades": best.get("long_winning_trades", 0),
                "long_gross_profit": best.get("long_gross_profit", 0),
                "short_trades": best.get("short_trades", 0),
                "short_winning_trades": best.get("short_winning_trades", 0),
                "short_gross_profit": best.get("short_gross_profit", 0),
            },
            top_results=results[:20],
            performance_stats={
                "combinations_per_second": round(combinations_per_second, 0),
                "gpu_enabled": self.use_gpu,
                "acceleration": "GPU (CuPy)" if execution_mode.startswith("gpu") else "CPU (Numba)",
                "gpu_memory_used_mb": self._get_gpu_memory() if self.use_gpu else 0,
                "execution_mode": execution_mode,
                "fallback_reason": fallback_reason,
            },
            execution_mode=execution_mode,
            fallback_reason=fallback_reason,
        )

    def _optimize_gpu(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        n_candles: int,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        slippage: float,
        direction: str,
        top_k: int = 1000,
        gpu_dtype: str = "float64",
    ) -> list[dict]:
        """GPU-accelerated optimization using CuPy for signals, Numba for RSI & backtest"""

        results = []

        # Transfer data to GPU once
        close_gpu = cp.asarray(close, dtype=cp.float64)
        high_gpu = cp.asarray(high, dtype=cp.float64)
        low_gpu = cp.asarray(low, dtype=cp.float64)

        logger.debug(f"Data transferred to GPU: {close_gpu.nbytes / 1024 / 1024:.2f} MB")

        # Pre-calculate RSI for all periods using NUMBA (much faster than GPU for sequential EMA)
        rsi_cache = {}
        if NUMBA_AVAILABLE:
            for period in rsi_periods:
                rsi_cache[period] = _fast_calculate_rsi(close, period)
        else:
            for period in rsi_periods:
                rsi_cache[period] = cp.asnumpy(self._calculate_rsi_gpu(close_gpu, period))

        logger.debug(f"RSI calculated for {len(rsi_periods)} periods (Numba: {NUMBA_AVAILABLE})")

        # Generate all combinations and test
        total = len(rsi_periods) * len(overbought_levels) * len(oversold_levels) * len(stop_losses) * len(take_profits)
        processed = 0

        for period in rsi_periods:
            rsi = rsi_cache[period]  # Already numpy array from Numba

            for overbought in overbought_levels:
                for oversold in oversold_levels:
                    if oversold >= overbought:
                        continue

                    # Generate signals on CPU (numpy is fast for comparisons)
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
                            # Run backtest simulation with Numba
                            metrics = self._simulate_backtest(
                                close,
                                high,
                                low,
                                entries,
                                exits,
                                sl / 100.0 if sl else None,
                                tp / 100.0 if tp else None,
                                initial_capital * leverage,
                                commission,
                                slippage,
                                self.position_size,
                            )

                            if metrics["total_trades"] > 0:
                                results.append(
                                    {
                                        "params": {
                                            "rsi_period": period,
                                            "rsi_overbought": overbought,
                                            "rsi_oversold": oversold,
                                            "stop_loss_pct": sl,
                                            "take_profit_pct": tp,
                                        },
                                        **metrics,
                                    }
                                )

                            processed += 1
                            if processed % 10000 == 0:
                                logger.info(f"   Progress: {processed:,}/{total:,} ({processed / total * 100:.1f}%)")

        # Free GPU memory
        del close_gpu, high_gpu, low_gpu
        cp.get_default_memory_pool().free_all_blocks()

        return results

    def _optimize_parallel(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        slippage: float,
        direction: str,
        top_k: int = 1000,
        gpu_dtype: str = "float64",
    ) -> list[dict]:
        """
        Parallel optimization using WarmProcessPool with shared memory.
        Workers are pre-initialized with Numba JIT compiled, data in shared memory.
        """
        # Create warm pool (workers will pre-compile Numba)
        pool = WarmProcessPool(n_workers=N_WORKERS)

        try:
            # Initialize with shared memory data
            pool.initialize(close, high, low)

            # Process all periods in parallel
            results = pool.map_periods(
                rsi_periods,
                overbought_levels,
                oversold_levels,
                stop_losses,
                take_profits,
                initial_capital,
                leverage,
                commission,
                slippage,
                direction,
            )

            return results

        finally:
            # Always cleanup
            pool.close()

    def _calculate_rsi_gpu(self, close_gpu: "cp.ndarray", period: int) -> "cp.ndarray":
        """Calculate RSI on GPU using CuPy"""
        n = len(close_gpu)

        # Price changes
        delta = cp.diff(close_gpu, prepend=close_gpu[0])

        # Gains and losses
        gains = cp.where(delta > 0, delta, 0)
        losses = cp.where(delta < 0, -delta, 0)

        # Initialize RSI
        rsi = cp.full(n, 50.0, dtype=cp.float64)

        if n <= period:
            return rsi

        # Calculate using Wilder's smoothing
        # Use cumsum for efficiency on GPU
        avg_gain = cp.zeros(n, dtype=cp.float64)
        avg_loss = cp.zeros(n, dtype=cp.float64)

        # Initial SMA
        avg_gain[period] = cp.mean(gains[1 : period + 1])
        avg_loss[period] = cp.mean(losses[1 : period + 1])

        # Wilder's EMA (sequential, but still on GPU)
        alpha = 1.0 / period
        for i in range(period + 1, n):
            avg_gain[i] = alpha * gains[i] + (1 - alpha) * avg_gain[i - 1]
            avg_loss[i] = alpha * losses[i] + (1 - alpha) * avg_loss[i - 1]

        # Calculate RSI - avoid where= argument (not supported in CuPy)
        rs = cp.zeros_like(avg_gain)
        non_zero_mask = avg_loss != 0
        rs[non_zero_mask] = avg_gain[non_zero_mask] / avg_loss[non_zero_mask]
        rsi = 100 - (100 / (1 + rs))
        rsi[:period] = 50

        return rsi

    def _simulate_backtest(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        entries: np.ndarray,
        exits: np.ndarray,
        stop_loss: float | None,
        take_profit: float | None,
        capital: float,
        commission: float,
        slippage: float = 0.0005,
        position_size: float = 1.0,
    ) -> dict[str, float]:
        """
        Fast backtest simulation using Numba JIT.
        """
        if NUMBA_AVAILABLE:
            # Use ultra-fast Numba version
            sl = stop_loss if stop_loss is not None else 0.0
            tp = take_profit if take_profit is not None else 0.0

            total_return, sharpe, max_dd, win_rate, total_trades, pf = _fast_simulate_backtest(
                close,
                high,
                low,
                entries.astype(np.bool_),
                exits.astype(np.bool_),
                sl,
                tp,
                capital,
                commission,
                slippage,
                position_size,
            )

            return {
                "total_return": round(total_return, 2),
                "sharpe_ratio": round(sharpe, 2),
                "max_drawdown": round(max_dd, 2),
                "win_rate": round(win_rate, 4),
                "total_trades": int(total_trades),
                "profit_factor": round(pf, 2),
            }

        # Fallback to slow Python version
        n = len(close)
        equity = capital
        peak_equity = capital
        max_drawdown = 0.0

        trades = []
        in_position = False
        entry_price = 0.0
        entry_idx = 0

        for i in range(1, n):
            if not in_position:
                # Check for entry
                if entries[i]:
                    in_position = True
                    entry_price = close[i]
                    entry_idx = i
                    # Deduct commission
                    equity *= 1 - commission
            else:
                # Check for exit conditions
                current_price = close[i]
                pnl_pct = (current_price - entry_price) / entry_price

                # Check SL/TP using high/low for more realistic simulation
                hit_sl = False
                hit_tp = False
                exit_price = current_price

                if stop_loss is not None:
                    sl_price = entry_price * (1 - stop_loss)
                    if low[i] <= sl_price:
                        hit_sl = True
                        exit_price = sl_price

                if take_profit is not None:
                    tp_price = entry_price * (1 + take_profit)
                    if high[i] >= tp_price:
                        hit_tp = True
                        exit_price = tp_price

                # Check signal exit
                should_exit = exits[i] or hit_sl or hit_tp

                if should_exit:
                    # Calculate P&L
                    if hit_sl:
                        pnl_pct = -stop_loss
                    elif hit_tp:
                        pnl_pct = take_profit
                    else:
                        pnl_pct = (exit_price - entry_price) / entry_price

                    # Update equity with position_size
                    position_pnl = equity * position_size * pnl_pct
                    equity += position_pnl
                    equity *= 1 - commission  # Exit commission

                    # Track trade
                    trades.append(
                        {
                            "pnl_pct": pnl_pct,
                            "duration": i - entry_idx,
                        }
                    )

                    # Update peak and drawdown
                    if equity > peak_equity:
                        peak_equity = equity
                    drawdown = (peak_equity - equity) / peak_equity
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown

                    in_position = False

        # Calculate metrics
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "total_return": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "win_rate": 0,
                "total_trades": 0,
                "profit_factor": 0,
            }

        total_return = (equity - capital) / capital * 100

        # Win rate
        winning_trades = [t for t in trades if t["pnl_pct"] > 0]
        win_rate = len(winning_trades) / total_trades

        # Profit factor
        gross_profit = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0)
        gross_loss = abs(sum(t["pnl_pct"] for t in trades if t["pnl_pct"] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 10.0

        # Sharpe ratio (simplified)
        if len(trades) > 1:
            returns = [t["pnl_pct"] for t in trades]
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
        else:
            sharpe = 0

        return {
            "total_return": round(total_return, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "win_rate": round(win_rate, 4),
            "total_trades": total_trades,
            "profit_factor": round(profit_factor, 2),
        }

    def _optimize_vectorized(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        slippage: float,
        direction: str,
        position_mode: str = "block",  # NEW: block, close_and_open, hedge
        top_k: int = 1000,
        gpu_dtype: str = "float64",
    ) -> list[dict]:
        """
        Vectorized optimization using DeepSeek recommendations.
        V2: Uses _backtest_all_with_params to eliminate Python dict bottleneck.
        Expected speedup: 2-3x over V1.
        """
        import time

        start = time.time()
        top_k = int(top_k)

        # Convert to numpy arrays (match Numba JIT signature exactly)
        # Signature: int64[:], float64[:], float64[:], float64[:], float64[:]
        periods_arr = np.array(rsi_periods, dtype=np.int64)
        overbought_arr = np.array(overbought_levels, dtype=np.float64)
        oversold_arr = np.array(oversold_levels, dtype=np.float64)
        sl_arr = np.array(stop_losses, dtype=np.float64)
        tp_arr = np.array(take_profits, dtype=np.float64)

        # Direction: 1=long, -1=short, 0=both
        dir_int = 1 if direction == "long" else (-1 if direction == "short" else 0)

        # Position mode: 0=block, 1=close_and_open, 2=hedge
        mode_map = {"block": 0, "close_and_open": 1, "hedge": 2}
        mode_int = mode_map.get(position_mode, 0)  # Default to block

        # AUTO-SWITCH: When direction=both (0) and mode=block (0), use hedge (2)
        # Block mode would cause one direction to completely block the other
        if dir_int == 0 and mode_int == 0:
            mode_int = 2  # Force Hedge for bidirectional
            logger.info("   Auto-switched to Hedge mode for bidirectional trading")

        # Step 1: Calculate ALL RSI at once
        rsi_start = time.time()
        rsi_all = _calculate_all_rsi_vectorized(close, periods_arr)
        rsi_time = time.time() - rsi_start
        logger.debug(f"   RSI calculation: {rsi_time:.3f}s")

        # Step 2: Backtest ALL combinations with params inline (DeepSeek optimization)
        bt_start = time.time()
        results_matrix = _backtest_all_with_params(
            close,
            high,
            low,
            rsi_all,
            periods_arr,
            overbought_arr,
            oversold_arr,
            sl_arr,
            tp_arr,
            initial_capital * leverage,
            commission,
            slippage,
            dir_int,
            mode_int,  # NEW: position_mode as int
        )
        bt_time = time.time() - bt_start
        logger.debug(f"   Backtest: {bt_time:.3f}s")

        # Step 3: Optimized conversion - only top results need full dict
        # DeepSeek Priority 1: Avoid Python loop for ALL results
        conv_start = time.time()

        # Filter valid results (trades > 0)
        valid_mask = results_matrix[:, 9] > 0  # trades column
        valid_results = results_matrix[valid_mask]

        n_valid = len(valid_results)
        n_periods = len(periods_arr)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)
        total_combinations = n_periods * n_ob * n_os * n_sl * n_tp

        # Partial sort by total_return (column 5) descending using argpartition
        top_n = min(top_k, len(valid_results))
        if top_n == 0:
            return []

        scores = valid_results[:, 5]
        if top_n < len(valid_results):
            top_partition = np.argpartition(-scores, top_n - 1)[:top_n]
            # Order selected indices by score desc
            top_indices = top_partition[np.argsort(-scores[top_partition])]
        else:
            top_indices = np.argsort(-scores)

        top_results_arr = valid_results[top_indices]

        # BATCH DICT CREATION (DeepSeek Priority 2)
        # Extract columns as contiguous arrays (faster than row iteration)
        periods_col = top_results_arr[:, 0].astype(np.int32)
        ob_col = top_results_arr[:, 1].astype(np.int32)
        os_col = top_results_arr[:, 2].astype(np.int32)
        sl_col = np.round(top_results_arr[:, 3], 1)
        tp_col = np.round(top_results_arr[:, 4], 1)
        returns_col = np.round(top_results_arr[:, 5], 2)
        sharpe_col = np.round(top_results_arr[:, 6], 2)
        # Cap Sharpe ratio to reasonable range [-100, 100] to avoid overflow values
        sharpe_col = np.clip(sharpe_col, -100.0, 100.0)
        dd_col = np.round(top_results_arr[:, 7], 2)
        wr_col = np.round(top_results_arr[:, 8], 4)
        trades_col = top_results_arr[:, 9].astype(np.int32)
        pf_col = np.round(top_results_arr[:, 10], 2)
        # Cap Profit Factor to reasonable range [0, 100]
        pf_col = np.clip(pf_col, 0.0, 100.0)

        # Long/Short specific stats (columns 11-16)
        long_trades_col = top_results_arr[:, 11].astype(np.int32)
        long_wins_col = top_results_arr[:, 12].astype(np.int32)
        long_gp_col = np.round(top_results_arr[:, 13], 4)
        short_trades_col = top_results_arr[:, 14].astype(np.int32)
        short_wins_col = top_results_arr[:, 15].astype(np.int32)
        short_gp_col = np.round(top_results_arr[:, 16], 4)

        # Build list of dicts using pre-extracted columns
        results = [
            {
                "params": {
                    "rsi_period": int(periods_col[i]),
                    "rsi_overbought": int(ob_col[i]),
                    "rsi_oversold": int(os_col[i]),
                    "stop_loss_pct": float(sl_col[i]),
                    "take_profit_pct": float(tp_col[i]),
                },
                "total_return": float(returns_col[i]),
                "sharpe_ratio": float(sharpe_col[i]),
                "max_drawdown": float(dd_col[i]),
                "win_rate": float(wr_col[i]),
                "total_trades": int(trades_col[i]),
                "profit_factor": float(pf_col[i]),
                # Long/Short breakdown
                "long_trades": int(long_trades_col[i]),
                "long_winning_trades": int(long_wins_col[i]),
                "long_gross_profit": float(long_gp_col[i]),
                "short_trades": int(short_trades_col[i]),
                "short_winning_trades": int(short_wins_col[i]),
                "short_gross_profit": float(short_gp_col[i]),
            }
            for i in range(len(top_results_arr))
        ]

        conv_time = time.time() - conv_start
        logger.debug(f"   Conversion: {conv_time:.3f}s ({n_valid:,} valid -> {top_n} top)")

        total_time = time.time() - start
        speed = total_combinations / total_time
        logger.info(f"   Vectorized V2: {total_time:.2f}s, {speed:,.0f} comb/sec, {n_valid:,} valid")

        return results

    def _optimize_vectorized_v3(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        direction: str,
        top_k: int = 1000,
        gpu_dtype: str = "float64",
    ) -> list[dict]:
        """
        V3 Vectorized optimization with HOISTED signal generation.
        DeepSeek Priority 1: Pre-compute ALL signals before SL/TP loops.
        Expected speedup: 30-50% over V2.
        """
        import time

        start = time.time()
        top_k = int(top_k)

        # Convert to numpy arrays (match Numba JIT signature exactly)
        # Signature: int64[:], float64[:], float64[:], float64[:], float64[:]
        periods_arr = np.array(rsi_periods, dtype=np.int64)
        overbought_arr = np.array(overbought_levels, dtype=np.float64)
        oversold_arr = np.array(oversold_levels, dtype=np.float64)
        sl_arr = np.array(stop_losses, dtype=np.float64)
        tp_arr = np.array(take_profits, dtype=np.float64)

        # Direction: 1=long, -1=short, 0=both
        dir_int = 1 if direction == "long" else (-1 if direction == "short" else 0)

        # Step 1: Calculate ALL RSI at once
        rsi_start = time.time()
        rsi_all = _calculate_all_rsi_vectorized(close, periods_arr)
        rsi_time = time.time() - rsi_start
        logger.debug(f"   [V3] RSI calculation: {rsi_time:.3f}s")

        # Step 2: PRE-COMPUTE ALL SIGNALS (DeepSeek Priority 1: Hoist Signal Generation)
        sig_start = time.time()
        entries_all, exits_all = _precompute_all_signals(rsi_all, periods_arr, overbought_arr, oversold_arr, dir_int)
        sig_time = time.time() - sig_start
        logger.debug(f"   [V3] Signal precompute: {sig_time:.3f}s")

        # Step 3: Backtest with PRE-COMPUTED signals (no signal generation in inner loops)
        bt_start = time.time()
        results_matrix = _backtest_all_v3_hoisted(
            close,
            high,
            low,
            entries_all,
            exits_all,
            periods_arr,
            overbought_arr,
            oversold_arr,
            sl_arr,
            tp_arr,
            initial_capital * leverage,
            commission,
        )
        bt_time = time.time() - bt_start
        logger.debug(f"   [V3] Backtest: {bt_time:.3f}s")

        # Step 4: Optimized conversion with Top-N filtering
        conv_start = time.time()

        # Filter valid results (trades > 0)
        valid_mask = results_matrix[:, 9] > 0
        valid_results = results_matrix[valid_mask]

        n_valid = len(valid_results)
        n_periods = len(periods_arr)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)
        total_combinations = n_periods * n_ob * n_os * n_sl * n_tp

        # Partial sort by total_return (column 5) descending
        top_n = min(top_k, len(valid_results))
        if top_n == 0:
            return []

        scores = valid_results[:, 5]
        if top_n < len(valid_results):
            top_partition = np.argpartition(-scores, top_n - 1)[:top_n]
            top_indices = top_partition[np.argsort(-scores[top_partition])]
        else:
            top_indices = np.argsort(-scores)

        top_results_arr = valid_results[top_indices]

        # BATCH DICT CREATION (DeepSeek Priority 2) - same as V2
        # Extract columns as contiguous arrays (faster than row iteration)
        periods_col = top_results_arr[:, 0].astype(np.int32)
        ob_col = top_results_arr[:, 1].astype(np.int32)
        os_col = top_results_arr[:, 2].astype(np.int32)
        sl_col = np.round(top_results_arr[:, 3], 1)
        tp_col = np.round(top_results_arr[:, 4], 1)
        returns_col = np.round(top_results_arr[:, 5], 2)
        sharpe_col = np.round(top_results_arr[:, 6], 2)
        dd_col = np.round(top_results_arr[:, 7], 2)
        wr_col = np.round(top_results_arr[:, 8], 4)
        trades_col = top_results_arr[:, 9].astype(np.int32)
        pf_col = np.round(top_results_arr[:, 10], 2)

        # Build list of dicts using pre-extracted columns
        results = [
            {
                "params": {
                    "rsi_period": int(periods_col[i]),
                    "rsi_overbought": int(ob_col[i]),
                    "rsi_oversold": int(os_col[i]),
                    "stop_loss_pct": float(sl_col[i]),
                    "take_profit_pct": float(tp_col[i]),
                },
                "total_return": float(returns_col[i]),
                "sharpe_ratio": float(sharpe_col[i]),
                "max_drawdown": float(dd_col[i]),
                "win_rate": float(wr_col[i]),
                "total_trades": int(trades_col[i]),
                "profit_factor": float(pf_col[i]),
            }
            for i in range(len(top_results_arr))
        ]

        conv_time = time.time() - conv_start
        logger.debug(f"   [V3] Conversion: {conv_time:.3f}s ({n_valid:,} valid -> {top_n} top)")

        total_time = time.time() - start
        speed = total_combinations / total_time
        logger.info(f"   Vectorized V3: {total_time:.2f}s, {speed:,.0f} comb/sec, {n_valid:,} valid")

        return results

    def _optimize_vectorized_v4(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        direction: str,
        min_signals: int = 5,
        max_loss_pct: float = 50.0,
        top_k: int = 1000,
    ) -> list[dict]:
        """
        V4 Vectorized optimization with EARLY TERMINATION.
        DeepSeek Recommendation: 40-70% speedup for large parameter spaces.

        Args:
            min_signals: Minimum required entry signals (default 5)
            max_loss_pct: Maximum loss before early exit (default 50%)
        """
        import time

        start = time.time()
        top_k = int(top_k)

        # Convert to numpy arrays (match Numba JIT signature exactly)
        # Signature: int64[:], float64[:], float64[:], float64[:], float64[:]
        periods_arr = np.array(rsi_periods, dtype=np.int64)
        overbought_arr = np.array(overbought_levels, dtype=np.float64)
        oversold_arr = np.array(oversold_levels, dtype=np.float64)
        sl_arr = np.array(stop_losses, dtype=np.float64)
        tp_arr = np.array(take_profits, dtype=np.float64)

        # Direction: 1=long, -1=short, 0=both
        dir_int = 1 if direction == "long" else (-1 if direction == "short" else 0)

        # Step 1: Calculate ALL RSI at once
        rsi_start = time.time()
        rsi_all = _calculate_all_rsi_vectorized(close, periods_arr)
        rsi_time = time.time() - rsi_start
        logger.debug(f"   [V4] RSI calculation: {rsi_time:.3f}s")

        # Step 2: Backtest with EARLY TERMINATION
        bt_start = time.time()
        results_matrix = _backtest_all_v4_early_exit(
            close,
            high,
            low,
            rsi_all,
            periods_arr,
            overbought_arr,
            oversold_arr,
            sl_arr,
            tp_arr,
            initial_capital * leverage,
            commission,
            dir_int,
            min_signals,
            max_loss_pct,
        )
        bt_time = time.time() - bt_start
        logger.debug(f"   [V4] Backtest: {bt_time:.3f}s")

        # Step 3: Optimized conversion with Top-N filtering
        conv_start = time.time()

        # Filter valid results (trades > 0)
        valid_mask = results_matrix[:, 9] > 0
        valid_results = results_matrix[valid_mask]

        n_valid = len(valid_results)
        n_periods = len(periods_arr)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)
        total_combinations = n_periods * n_ob * n_os * n_sl * n_tp

        # Count skipped (0 trades)
        n_skipped = total_combinations - n_valid

        # Partial sort by total_return (column 5) descending
        top_n = min(top_k, len(valid_results))
        if top_n == 0:
            return []

        scores = valid_results[:, 5]
        if top_n < len(valid_results):
            top_partition = np.argpartition(-scores, top_n - 1)[:top_n]
            top_indices = top_partition[np.argsort(-scores[top_partition])]
        else:
            top_indices = np.argsort(-scores)

        top_results_arr = valid_results[top_indices]

        # BATCH DICT CREATION
        periods_col = top_results_arr[:, 0].astype(np.int32)
        ob_col = top_results_arr[:, 1].astype(np.int32)
        os_col = top_results_arr[:, 2].astype(np.int32)
        sl_col = np.round(top_results_arr[:, 3], 1)
        tp_col = np.round(top_results_arr[:, 4], 1)
        returns_col = np.round(top_results_arr[:, 5], 2)
        sharpe_col = np.round(top_results_arr[:, 6], 2)
        dd_col = np.round(top_results_arr[:, 7], 2)
        wr_col = np.round(top_results_arr[:, 8], 4)
        trades_col = top_results_arr[:, 9].astype(np.int32)
        pf_col = np.round(top_results_arr[:, 10], 2)

        results = [
            {
                "params": {
                    "rsi_period": int(periods_col[i]),
                    "rsi_overbought": int(ob_col[i]),
                    "rsi_oversold": int(os_col[i]),
                    "stop_loss_pct": float(sl_col[i]),
                    "take_profit_pct": float(tp_col[i]),
                },
                "total_return": float(returns_col[i]),
                "sharpe_ratio": float(sharpe_col[i]),
                "max_drawdown": float(dd_col[i]),
                "win_rate": float(wr_col[i]),
                "total_trades": int(trades_col[i]),
                "profit_factor": float(pf_col[i]),
            }
            for i in range(len(top_results_arr))
        ]

        conv_time = time.time() - conv_start
        logger.debug(f"   [V4] Conversion: {conv_time:.3f}s ({n_valid:,} valid -> {top_n} top)")

        total_time = time.time() - start
        speed = total_combinations / total_time
        skip_pct = n_skipped / total_combinations * 100 if total_combinations > 0 else 0
        logger.info(
            f"   Vectorized V4: {total_time:.2f}s, {speed:,.0f} comb/sec, "
            f"{n_valid:,} valid, {n_skipped:,} skipped ({skip_pct:.1f}%)"
        )

        return results

    def _optimize_vectorized_v5(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        direction: str,
        top_k: int = 1000,
        gpu_dtype: str = "float64",
    ) -> list[dict]:
        """
        V5 Vectorized optimization with TRANSPOSED memory layout.
        DeepSeek Recommendation: 1.2-1.5x speedup from better cache locality.

        Uses results_T[11, n_combos] layout for SIMD-friendly column access.
        """
        import time

        start = time.time()
        top_k = int(top_k)

        # Convert to numpy arrays with explicit dtypes for JIT
        periods_arr = np.array(rsi_periods, dtype=np.int64)
        overbought_arr = np.array(overbought_levels, dtype=np.float64)
        oversold_arr = np.array(oversold_levels, dtype=np.float64)
        sl_arr = np.array(stop_losses, dtype=np.float64)
        tp_arr = np.array(take_profits, dtype=np.float64)

        # Direction: 1=long, -1=short
        dir_int = 1 if direction == "long" else (-1 if direction == "short" else 1)

        # Step 1: Calculate ALL RSI at once
        rsi_start = time.time()
        rsi_all = _calculate_all_rsi_vectorized(close, periods_arr)
        rsi_time = time.time() - rsi_start
        logger.debug(f"   [V5] RSI calculation: {rsi_time:.3f}s")

        # Step 2: Backtest with TRANSPOSED layout
        bt_start = time.time()
        results_T = _backtest_all_v5_transposed(
            close,
            high,
            low,
            rsi_all,
            periods_arr,
            overbought_arr,
            oversold_arr,
            sl_arr,
            tp_arr,
            initial_capital * leverage,
            commission,
            dir_int,
        )
        bt_time = time.time() - bt_start
        logger.debug(f"   [V5] Backtest (transposed): {bt_time:.3f}s")

        # Step 3: Optimized conversion from TRANSPOSED layout
        conv_start = time.time()

        # Transpose back for filtering (column 9 = trades)
        trades_row = results_T[9]
        valid_mask = trades_row > 0
        n_valid = np.sum(valid_mask)

        n_periods = len(periods_arr)
        n_ob = len(overbought_arr)
        n_os = len(oversold_arr)
        n_sl = len(sl_arr)
        n_tp = len(tp_arr)
        total_combinations = n_periods * n_ob * n_os * n_sl * n_tp

        # Get indices of valid results and select top_k by return (row 5) descending
        valid_indices = np.where(valid_mask)[0]
        valid_returns = results_T[5, valid_indices]

        top_n = min(top_k, len(valid_returns))
        if top_n == 0:
            return []

        if top_n < len(valid_returns):
            top_partition = np.argpartition(-valid_returns, top_n - 1)[:top_n]
            top_indices = valid_indices[top_partition]
            order = np.argsort(-valid_returns[top_partition])
            top_indices = top_indices[order]
        else:
            order = np.argsort(-valid_returns)
            top_indices = valid_indices[order]

        # Extract columns from transposed layout (fast row access)
        periods_col = results_T[0, top_indices].astype(np.int32)
        ob_col = results_T[1, top_indices].astype(np.int32)
        os_col = results_T[2, top_indices].astype(np.int32)
        sl_col = np.round(results_T[3, top_indices], 1)
        tp_col = np.round(results_T[4, top_indices], 1)
        returns_col = np.round(results_T[5, top_indices], 2)
        sharpe_col = np.round(results_T[6, top_indices], 2)
        dd_col = np.round(results_T[7, top_indices], 2)
        wr_col = np.round(results_T[8, top_indices], 4)
        trades_col = results_T[9, top_indices].astype(np.int32)
        pf_col = np.round(results_T[10, top_indices], 2)

        # Build list of dicts
        results = [
            {
                "params": {
                    "rsi_period": int(periods_col[i]),
                    "rsi_overbought": int(ob_col[i]),
                    "rsi_oversold": int(os_col[i]),
                    "stop_loss_pct": float(sl_col[i]),
                    "take_profit_pct": float(tp_col[i]),
                },
                "total_return": float(returns_col[i]),
                "sharpe_ratio": float(sharpe_col[i]),
                "max_drawdown": float(dd_col[i]),
                "win_rate": float(wr_col[i]),
                "total_trades": int(trades_col[i]),
                "profit_factor": float(pf_col[i]),
            }
            for i in range(len(top_indices))
        ]

        conv_time = time.time() - conv_start
        logger.debug(f"   [V5] Conversion: {conv_time:.3f}s ({n_valid:,} valid -> {top_n} top)")

        total_time = time.time() - start
        speed = total_combinations / total_time
        logger.info(f"   Vectorized V5 (transposed): {total_time:.2f}s, {speed:,.0f} comb/sec, {n_valid:,} valid")

        return results

    def _optimize_gpu(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        direction: str,
        top_k: int = 1000,
        gpu_dtype: str = "float64",
    ) -> list[dict]:
        """
        GPU-accelerated optimization using CuPy + Numba hybrid.

        Strategy:
        1. RSI calculation: GPU (vectorized)
        2. Signal generation: GPU (boolean ops)
        3. Backtest simulation: CPU/Numba (sequential trading)
        4. Filtering/sorting: GPU

        Best for: Large grids (100K+ combinations)
        """
        import time

        if not GPU_AVAILABLE:
            logger.warning("GPU not available, falling back to CPU V2")
            return self._optimize_vectorized(
                close,
                high,
                low,
                rsi_periods,
                overbought_levels,
                oversold_levels,
                stop_losses,
                take_profits,
                initial_capital,
                leverage,
                commission,
                direction,
                top_k,
                gpu_dtype,
            )

        start = time.time()
        cp_dtype = cp.float32 if gpu_dtype == "float32" else cp.float64

        # Convert to numpy arrays (match Numba JIT signature exactly)
        # Signature: int64[:], float64[:], float64[:], float64[:], float64[:]
        periods_arr = np.array(rsi_periods, dtype=np.int64)
        overbought_arr = np.array(overbought_levels, dtype=np.float64)
        oversold_arr = np.array(oversold_levels, dtype=np.float64)
        sl_arr = np.array(stop_losses, dtype=np.float64)
        tp_arr = np.array(take_profits, dtype=np.float64)

        dir_int = 1 if direction == "long" else (-1 if direction == "short" else 0)

        # Step 1: Calculate RSI on GPU
        rsi_start = time.time()
        rsi_all = _calculate_all_rsi_gpu(close, periods_arr)
        rsi_time = time.time() - rsi_start
        logger.debug(f"   [GPU] RSI calculation: {rsi_time:.3f}s")

        # Step 2: Backtest with GPU-generated signals
        bt_start = time.time()
        results_matrix = _backtest_all_gpu(
            close,
            high,
            low,
            rsi_all,
            periods_arr,
            overbought_arr,
            oversold_arr,
            sl_arr,
            tp_arr,
            initial_capital * leverage,
            commission,
            dir_int,
            cp_dtype,
        )
        bt_time = time.time() - bt_start
        logger.debug(f"   [GPU] Backtest: {bt_time:.3f}s")

        # Step 3: Filter and convert
        conv_start = time.time()

        valid_mask = results_matrix[:, 9] > 0
        valid_results = results_matrix[valid_mask]

        n_valid = len(valid_results)
        total_combinations = len(periods_arr) * len(overbought_arr) * len(oversold_arr) * len(sl_arr) * len(tp_arr)

        scores = valid_results[:, 5]
        top_n = min(top_k, len(valid_results))
        if top_n == 0:
            return []

        if top_n < len(valid_results):
            top_partition = np.argpartition(-scores, top_n - 1)[:top_n]
            top_indices = top_partition[np.argsort(-scores[top_partition])]
        else:
            top_indices = np.argsort(-scores)

        top_results_arr = valid_results[top_indices]

        # BATCH DICT CREATION
        periods_col = top_results_arr[:, 0].astype(np.int32)
        ob_col = top_results_arr[:, 1].astype(np.int32)
        os_col = top_results_arr[:, 2].astype(np.int32)
        sl_col = np.round(top_results_arr[:, 3], 1)
        tp_col = np.round(top_results_arr[:, 4], 1)
        returns_col = np.round(top_results_arr[:, 5], 2)
        sharpe_col = np.round(top_results_arr[:, 6], 2)
        dd_col = np.round(top_results_arr[:, 7], 2)
        wr_col = np.round(top_results_arr[:, 8], 4)
        trades_col = top_results_arr[:, 9].astype(np.int32)
        pf_col = np.round(top_results_arr[:, 10], 2)

        results = [
            {
                "params": {
                    "rsi_period": int(periods_col[i]),
                    "rsi_overbought": int(ob_col[i]),
                    "rsi_oversold": int(os_col[i]),
                    "stop_loss_pct": float(sl_col[i]),
                    "take_profit_pct": float(tp_col[i]),
                },
                "total_return": float(returns_col[i]),
                "sharpe_ratio": float(sharpe_col[i]),
                "max_drawdown": float(dd_col[i]),
                "win_rate": float(wr_col[i]),
                "total_trades": int(trades_col[i]),
                "profit_factor": float(pf_col[i]),
            }
            for i in range(len(top_results_arr))
        ]

        conv_time = time.time() - conv_start
        logger.debug(f"   [GPU] Conversion: {conv_time:.3f}s ({n_valid:,} valid -> {top_n} top)")

        total_time = time.time() - start
        speed = total_combinations / total_time
        logger.info(f"   GPU: {total_time:.2f}s, {speed:,.0f} comb/sec, {n_valid:,} valid")

        return results

    def _optimize_cpu(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        n_candles: int,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        slippage: float,
        direction: str,
        top_k: int = 1000,
        gpu_dtype: str = "float64",
    ) -> list[dict]:
        """CPU fallback using Numba"""

        results = []

        # Pre-calculate RSI for all periods
        rsi_cache = {}
        for period in rsi_periods:
            rsi_cache[period] = self._calculate_rsi_cpu(close, period)

        for period in rsi_periods:
            rsi = rsi_cache[period]

            for overbought in overbought_levels:
                for oversold in oversold_levels:
                    if oversold >= overbought:
                        continue

                    # Generate signals
                    if direction == "long":
                        entries = rsi < oversold
                        exits = rsi > overbought
                    else:
                        entries = rsi > overbought
                        exits = rsi < oversold

                    for sl in stop_losses:
                        for tp in take_profits:
                            metrics = self._simulate_backtest(
                                close,
                                high,
                                low,
                                entries,
                                exits,
                                sl / 100.0 if sl else None,
                                tp / 100.0 if tp else None,
                                initial_capital * leverage,
                                commission,
                                slippage,
                                self.position_size,
                            )

                            if metrics["total_trades"] > 0:
                                results.append(
                                    {
                                        "params": {
                                            "rsi_period": period,
                                            "rsi_overbought": overbought,
                                            "rsi_oversold": oversold,
                                            "stop_loss_pct": sl,
                                            "take_profit_pct": tp,
                                        },
                                        **metrics,
                                    }
                                )

        return results

    def _calculate_rsi_cpu(self, close: np.ndarray, period: int) -> np.ndarray:
        """Calculate RSI on CPU using NumPy"""
        delta = np.diff(close, prepend=close[0])
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)

        n = len(close)
        rsi = np.full(n, 50.0)

        if n <= period:
            return rsi

        avg_gain = np.zeros(n)
        avg_loss = np.zeros(n)

        avg_gain[period] = np.mean(gains[1 : period + 1])
        avg_loss[period] = np.mean(losses[1 : period + 1])

        alpha = 1.0 / period
        for i in range(period + 1, n):
            avg_gain[i] = alpha * gains[i] + (1 - alpha) * avg_gain[i - 1]
            avg_loss[i] = alpha * losses[i] + (1 - alpha) * avg_loss[i - 1]

        rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0)
        rsi = 100 - (100 / (1 + rs))
        rsi[:period] = 50

        return rsi

    def _calculate_scores(self, results: list[dict], metric: str) -> list[dict]:
        """Calculate optimization scores based on selected metric"""
        for r in results:
            if metric == "sharpe_ratio":
                r["score"] = r.get("sharpe_ratio", 0)
            elif metric == "total_return":
                r["score"] = r.get("total_return", 0)
            elif metric == "win_rate":
                r["score"] = r.get("win_rate", 0)
            elif metric == "calmar_ratio":
                dd = abs(r.get("max_drawdown", 0.01)) or 0.01
                r["score"] = r.get("total_return", 0) / dd
            elif metric == "net_profit":
                # Net profit = gross profit - gross loss (in absolute value)
                # If not available, calculate from return and capital
                r["score"] = r.get("net_profit", r.get("total_return", 0) * 100)  # Scale to absolute value
            elif metric == "profit_factor":
                r["score"] = r.get("profit_factor", 0)
            elif metric == "risk_adjusted_return":
                # Risk-adjusted return: return / max_drawdown * sharpe
                dd = abs(r.get("max_drawdown", 0.01)) or 0.01
                sharpe = r.get("sharpe_ratio", 0) or 1
                r["score"] = r.get("total_return", 0) / dd * max(sharpe, 0.1)
            elif metric == "custom_score":
                # Custom weighted score (weights should be passed but fallback to defaults)
                r["score"] = (
                    r.get("total_return", 0) * 0.4
                    + r.get("sharpe_ratio", 0) * 20  # Scale sharpe to percentage-like
                    + (100 - abs(r.get("max_drawdown", 0))) * 0.3
                    + r.get("win_rate", 0) * 100 * 0.1
                )
            else:
                r["score"] = r.get("sharpe_ratio", 0)

        return results

    def _get_gpu_memory(self) -> float:
        """Get current GPU memory usage in MB"""
        if not self.use_gpu:
            return 0
        try:
            mempool = cp.get_default_memory_pool()
            return mempool.used_bytes() / 1024 / 1024
        except Exception:
            return 0


# =============================================================================
# API Endpoint Integration
# =============================================================================


def run_gpu_optimization(
    candles: pd.DataFrame,
    rsi_period_range: list[int],
    rsi_overbought_range: list[int],
    rsi_oversold_range: list[int],
    stop_loss_range: list[float],
    take_profit_range: list[float],
    initial_capital: float = 10000.0,
    leverage: int = 1,
    commission: float = 0.0007,  # 0.07% TradingView parity
    optimize_metric: str = "sharpe_ratio",
    direction: str = "long",
    **kwargs,
) -> GPUOptimizationResult:
    """
    Convenience function to run GPU optimization.

    Example:
        result = run_gpu_optimization(
            candles=df,
            rsi_period_range=[7, 14, 21],
            rsi_overbought_range=[65, 70, 75, 80],
            rsi_oversold_range=[20, 25, 30, 35],
            stop_loss_range=[1, 2, 3, 5],
            take_profit_range=[1, 2, 3, 5],
        )
    """
    optimizer = GPUGridOptimizer()
    return optimizer.optimize(
        candles=candles,
        rsi_period_range=rsi_period_range,
        rsi_overbought_range=rsi_overbought_range,
        rsi_oversold_range=rsi_oversold_range,
        stop_loss_range=stop_loss_range,
        take_profit_range=take_profit_range,
        initial_capital=initial_capital,
        leverage=leverage,
        commission=commission,
        optimize_metric=optimize_metric,
        direction=direction,
        **kwargs,
    )
