"""
WarmProcessPool and worker functions for GPU optimizer.

Extracted from gpu_optimizer.py (lines 1843-2107).
Contains:
  - _worker_data          — per-worker global state dict
  - _worker_init()        — Pool initializer: attaches shared memory, pre-warms Numba
  - _worker_process_period() — processes one RSI period in a Pool worker
  - WarmProcessPool       — pre-warmed multiprocessing.Pool with shared memory
  - _cleanup_shared_memory() — atexit cleanup
"""

import atexit
import time
from multiprocessing import Pool, shared_memory

import numpy as np
from loguru import logger

from backend.backtesting.gpu.kernels import N_WORKERS, NUMBA_AVAILABLE, _fast_calculate_rsi, _fast_simulate_backtest

# Track shared memory blocks for cleanup
_SHARED_MEMORY_BLOCKS: list = []

# Global warm pool (initialized once, reused)
_WARM_POOL = None


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
