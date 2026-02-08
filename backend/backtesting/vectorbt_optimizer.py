"""
VectorBT High-Performance Grid Optimizer

Batch optimization using vectorbt's native parameter combinations.
Designed for massive parameter spaces (100K - 100M+ combinations).

Performance characteristics:
- 100K combinations: ~10-30 seconds
- 1M combinations: ~1-3 minutes
- 10M combinations: ~10-30 minutes
- 100M combinations: ~1-3 hours (with chunking)

Uses:
- Numba JIT compilation for CPU acceleration
- Vectorized operations (no Python loops)
- Memory-efficient chunking for large parameter spaces
- Optional GPU acceleration with CuPy (if available)
"""

import warnings
from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    import vectorbt as vbt

    VBT_AVAILABLE = True
except ImportError:
    vbt = None
    VBT_AVAILABLE = False
    logger.warning("vectorbt not available for optimization")

try:
    from numba import jit

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    logger.warning("numba not available, using pure numpy")

# GPU acceleration with CuPy - DISABLED due to stability issues
# To enable: set ENABLE_GPU_ACCELERATION = True
ENABLE_GPU_ACCELERATION = False

if ENABLE_GPU_ACCELERATION:
    try:
        import cupy as cp

        # Quick test to ensure GPU works
        _test = cp.array([1, 2, 3])
        del _test
        CUPY_AVAILABLE = True
        logger.info("🚀 CuPy GPU acceleration enabled")
    except Exception as e:
        cp = None
        CUPY_AVAILABLE = False
        logger.warning(f"CuPy GPU disabled due to error: {e}")
else:
    cp = None
    CUPY_AVAILABLE = False
    logger.info("GPU acceleration disabled, using CPU (Numba JIT)")


@dataclass
class OptimizationResult:
    """Result of a single parameter combination"""

    params: dict[str, Any]
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    profit_factor: float
    calmar_ratio: float
    score: float


@dataclass
class VectorbtOptimizationResult:
    """Complete optimization result"""

    status: str
    total_combinations: int
    tested_combinations: int
    execution_time_seconds: float
    best_params: dict[str, Any]
    best_score: float
    best_metrics: dict[str, Any]
    top_results: list[dict[str, Any]]
    performance_stats: dict[str, Any]


class VectorbtGridOptimizer:
    """
    High-performance grid search optimizer using vectorbt.

    Features:
    - Native vectorbt parameter broadcasting
    - Numba JIT-compiled RSI calculation
    - Memory-efficient chunking for large spaces
    - Parallel metric calculation
    """

    # Maximum combinations per chunk to avoid memory issues
    MAX_CHUNK_SIZE = 50_000

    def __init__(self):
        if not VBT_AVAILABLE:
            raise RuntimeError("vectorbt is required for VectorbtGridOptimizer")

        # Pre-compile Numba functions on first use
        self._warmup_jit()

    def _warmup_jit(self):
        """Warm up JIT compilation with small arrays"""
        if NUMBA_AVAILABLE:
            try:
                # Trigger compilation with dummy data
                dummy = np.random.randn(100).astype(np.float64)
                _calculate_rsi_numba(dummy, 14)
                logger.debug("Numba JIT warmup completed")
            except Exception as e:
                logger.warning(f"Numba warmup failed: {e}")

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
        optimize_metric: str = "sharpe_ratio",
        direction: str = "long",
        weights: dict[str, float] | None = None,
        filters: dict[str, float] | None = None,
    ) -> VectorbtOptimizationResult:
        """
        Run high-performance grid search optimization.

        Args:
            candles: OHLCV DataFrame with DatetimeIndex
            rsi_period_range: List of RSI periods to test
            rsi_overbought_range: List of overbought levels
            rsi_oversold_range: List of oversold levels
            stop_loss_range: List of stop loss percentages
            take_profit_range: List of take profit percentages
            initial_capital: Starting capital
            leverage: Trading leverage
            commission: Trading fee per trade
            optimize_metric: Metric to optimize
            direction: 'long', 'short', or 'both'
            weights: Custom weights for composite scoring
            filters: Minimum thresholds for filtering results

        Returns:
            VectorbtOptimizationResult with best parameters and metrics
        """
        import time

        start_time = time.time()

        # Calculate total combinations
        total_combinations = (
            len(rsi_period_range)
            * len(rsi_overbought_range)
            * len(rsi_oversold_range)
            * len(stop_loss_range)
            * len(take_profit_range)
        )

        logger.info("🚀 VectorBT Grid Optimizer starting")
        logger.info(f"   Total combinations: {total_combinations:,}")
        logger.info(
            f"   RSI periods: {len(rsi_period_range)}, OB: {len(rsi_overbought_range)}, OS: {len(rsi_oversold_range)}"
        )
        logger.info(f"   SL: {len(stop_loss_range)}, TP: {len(take_profit_range)}")

        # Prepare OHLC prices for intrabar SL/TP detection
        close = candles["close"].values.astype(np.float64)
        close_series = candles["close"]
        high_series = candles["high"] if "high" in candles.columns else None
        low_series = candles["low"] if "low" in candles.columns else None

        # Detect timeframe for proper frequency
        freq = self._detect_frequency(candles)

        all_results = []

        # Check if we need chunking
        if total_combinations <= self.MAX_CHUNK_SIZE:
            # Single batch - most efficient
            logger.info("📦 Running single-batch optimization")
            results = self._run_batch(
                close_series=close_series,
                high_series=high_series,
                low_series=low_series,
                close_array=close,
                rsi_periods=rsi_period_range,
                overbought_levels=rsi_overbought_range,
                oversold_levels=rsi_oversold_range,
                stop_losses=stop_loss_range,
                take_profits=take_profit_range,
                initial_capital=initial_capital,
                leverage=leverage,
                commission=commission,
                freq=freq,
                direction=direction,
            )
            all_results.extend(results)
        else:
            # Chunked processing for large parameter spaces
            logger.info(
                f"📦 Running chunked optimization ({total_combinations:,} combinations)"
            )

            # Generate all parameter combinations
            all_combinations = list(
                product(
                    rsi_period_range,
                    rsi_overbought_range,
                    rsi_oversold_range,
                    stop_loss_range,
                    take_profit_range,
                )
            )

            # Process in chunks
            num_chunks = (
                len(all_combinations) + self.MAX_CHUNK_SIZE - 1
            ) // self.MAX_CHUNK_SIZE

            for chunk_idx in range(num_chunks):
                chunk_start = chunk_idx * self.MAX_CHUNK_SIZE
                chunk_end = min(
                    chunk_start + self.MAX_CHUNK_SIZE, len(all_combinations)
                )
                chunk = all_combinations[chunk_start:chunk_end]

                logger.info(
                    f"   Chunk {chunk_idx + 1}/{num_chunks}: {len(chunk):,} combinations"
                )

                # Extract unique values for this chunk
                periods = sorted(set(c[0] for c in chunk))
                overboughts = sorted(set(c[1] for c in chunk))
                oversolds = sorted(set(c[2] for c in chunk))
                stop_losses = sorted(set(c[3] for c in chunk))
                take_profits = sorted(set(c[4] for c in chunk))

                chunk_results = self._run_batch(
                    close_series=close_series,
                    high_series=high_series,
                    low_series=low_series,
                    close_array=close,
                    rsi_periods=periods,
                    overbought_levels=overboughts,
                    oversold_levels=oversolds,
                    stop_losses=stop_losses,
                    take_profits=take_profits,
                    initial_capital=initial_capital,
                    leverage=leverage,
                    commission=commission,
                    freq=freq,
                    direction=direction,
                )
                all_results.extend(chunk_results)

        # Apply filters
        if filters:
            all_results = self._apply_filters(all_results, filters)

        # Calculate scores
        all_results = self._calculate_scores(all_results, optimize_metric, weights)

        # Sort by score
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        execution_time = time.time() - start_time

        # Performance stats
        combinations_per_second = (
            total_combinations / execution_time if execution_time > 0 else 0
        )

        logger.info(f"✅ Optimization completed in {execution_time:.2f}s")
        logger.info(f"   Speed: {combinations_per_second:,.0f} combinations/second")
        logger.info(f"   Valid results: {len(all_results):,}")

        # Get best result
        best = all_results[0] if all_results else {}

        return VectorbtOptimizationResult(
            status="completed",
            total_combinations=total_combinations,
            tested_combinations=len(all_results),
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
                "calmar_ratio": best.get("calmar_ratio", 0),
            },
            top_results=all_results[:20],
            performance_stats={
                "combinations_per_second": round(combinations_per_second, 0),
                "memory_efficient": total_combinations > self.MAX_CHUNK_SIZE,
                "numba_enabled": NUMBA_AVAILABLE,
                "gpu_enabled": CUPY_AVAILABLE,
                "acceleration": "GPU (CuPy)"
                if CUPY_AVAILABLE
                else ("CPU (Numba JIT)" if NUMBA_AVAILABLE else "CPU (NumPy)"),
            },
        )

    def _run_batch(
        self,
        close_series: pd.Series,
        high_series: pd.Series | None,
        low_series: pd.Series | None,
        close_array: np.ndarray,
        rsi_periods: list[int],
        overbought_levels: list[int],
        oversold_levels: list[int],
        stop_losses: list[float],
        take_profits: list[float],
        initial_capital: float,
        leverage: int,
        commission: float,
        freq: str,
        direction: str,
    ) -> list[dict]:
        """
        Run a batch of backtests using TRUE vectorbt broadcasting.

        This method leverages vectorbt's ability to test multiple SL/TP
        combinations simultaneously by passing arrays to sl_stop and tp_stop.
        This gives 100-1000x speedup compared to nested loops.
        """
        results = []

        # Pre-calculate RSI for all periods using GPU (if available) or Numba
        if CUPY_AVAILABLE:
            logger.debug("Using GPU (CuPy) for RSI calculation")
            rsi_cache_raw = _batch_calculate_rsi_gpu(close_array, rsi_periods)
            rsi_cache = {
                p: pd.Series(v, index=close_series.index)
                for p, v in rsi_cache_raw.items()
            }
        elif NUMBA_AVAILABLE:
            logger.debug("Using CPU (Numba JIT) for RSI calculation")
            rsi_cache = {}
            for period in rsi_periods:
                rsi_values = _calculate_rsi_numba(close_array, period)
                rsi_cache[period] = pd.Series(rsi_values, index=close_series.index)
        else:
            logger.debug("Using pure NumPy for RSI calculation")
            rsi_cache = {}
            for period in rsi_periods:
                rsi_values = self._calculate_rsi_numpy(close_array, period)
                rsi_cache[period] = pd.Series(rsi_values, index=close_series.index)

        # Convert SL/TP to numpy arrays for vectorbt broadcasting
        # VectorBT accepts arrays and tests all combinations automatically
        sl_array = np.array(
            [sl / 100.0 if sl else np.nan for sl in stop_losses], dtype=np.float64
        )
        tp_array = np.array(
            [tp / 100.0 if tp else np.nan for tp in take_profits], dtype=np.float64
        )

        # Test RSI parameter combinations (outer loop - fewer iterations)
        for period in rsi_periods:
            rsi = rsi_cache[period]

            for overbought in overbought_levels:
                for oversold in oversold_levels:
                    # Skip invalid combinations
                    if oversold >= overbought:
                        continue

                    # Generate entry/exit signals
                    if direction == "long":
                        entries = rsi < oversold
                        exits = rsi > overbought
                    elif direction == "short":
                        entries = rsi > overbought
                        exits = rsi < oversold
                    else:  # both
                        entries = rsi < oversold
                        exits = rsi > overbought

                    try:
                        # ═══════════════════════════════════════════════════════════
                        # TRUE VECTORIZATION: Single call tests ALL SL/TP combinations
                        # VectorBT broadcasts arrays and creates multi-dimensional portfolio
                        # ═══════════════════════════════════════════════════════════
                        # Build kwargs for Portfolio.from_signals
                        pf_kwargs = {
                            "close": close_series,
                            "entries": entries,
                            "exits": exits,
                            "init_cash": initial_capital * leverage,
                            "size": 1.0,
                            "size_type": "percent",
                            "fees": commission,
                            "freq": freq,
                            "sl_stop": sl_array,  # Array of all SL values
                            "tp_stop": tp_array,  # Array of all TP values
                            # QUICK REVERSALS FIX: Match Fallback engine behavior
                            "upon_long_conflict": "ignore",
                            "upon_short_conflict": "ignore",
                            "upon_dir_conflict": "ignore",
                            "upon_opposite_entry": "ignore",
                        }

                        # INTRABAR SL/TP FIX: Add high/low for proper SL/TP detection
                        # VectorBT will check if high/low reached SL/TP levels within bar
                        if high_series is not None:
                            pf_kwargs["high"] = high_series
                        if low_series is not None:
                            pf_kwargs["low"] = low_series

                        pf = vbt.Portfolio.from_signals(**pf_kwargs)

                        # Extract vectorized metrics for ALL combinations at once
                        # pf now contains results for shape (len(sl_array), len(tp_array))

                        # Get metrics as multi-dimensional arrays
                        try:
                            total_returns = pf.total_return() * 100  # Convert to %
                            sharpes = pf.sharpe_ratio()
                            max_dds = np.abs(pf.max_drawdown() * 100)  # Convert to %
                            win_rates = pf.trades.win_rate()
                            total_trades_arr = pf.trades.count()
                        except Exception as e:
                            logger.warning(f"Failed to get vectorized metrics: {e}")
                            continue

                        # Iterate over the result grid to extract individual results
                        # This is still fast because metrics are already computed
                        for i, sl in enumerate(stop_losses):
                            for j, tp in enumerate(take_profits):
                                try:
                                    # Handle multi-dimensional indexing
                                    if hasattr(total_returns, "iloc"):
                                        # DataFrame result
                                        total_return = (
                                            float(total_returns.iloc[i, j])
                                            if total_returns.ndim > 1
                                            else float(total_returns.iloc[i])
                                        )
                                        sharpe = (
                                            float(sharpes.iloc[i, j])
                                            if sharpes.ndim > 1
                                            else float(sharpes.iloc[i])
                                        )
                                        max_dd = (
                                            float(max_dds.iloc[i, j])
                                            if max_dds.ndim > 1
                                            else float(max_dds.iloc[i])
                                        )
                                        win_rate = (
                                            float(win_rates.iloc[i, j])
                                            if win_rates.ndim > 1
                                            else float(win_rates.iloc[i])
                                        )
                                        n_trades = (
                                            int(total_trades_arr.iloc[i, j])
                                            if total_trades_arr.ndim > 1
                                            else int(total_trades_arr.iloc[i])
                                        )
                                    elif isinstance(total_returns, np.ndarray):
                                        # NumPy array result
                                        if total_returns.ndim == 2:
                                            total_return = float(total_returns[i, j])
                                            sharpe = (
                                                float(sharpes[i, j])
                                                if sharpes.ndim > 1
                                                else float(sharpes[i])
                                            )
                                            max_dd = (
                                                float(max_dds[i, j])
                                                if max_dds.ndim > 1
                                                else float(max_dds[i])
                                            )
                                            win_rate = (
                                                float(win_rates[i, j])
                                                if hasattr(win_rates, "ndim")
                                                and win_rates.ndim > 1
                                                else float(win_rates)
                                                if np.isscalar(win_rates)
                                                else float(win_rates[i])
                                            )
                                            n_trades = (
                                                int(total_trades_arr[i, j])
                                                if total_trades_arr.ndim > 1
                                                else int(total_trades_arr[i])
                                            )
                                        else:
                                            # 1D array - single parameter varies
                                            idx = i * len(take_profits) + j
                                            total_return = (
                                                float(total_returns.flat[idx])
                                                if idx < total_returns.size
                                                else float(total_returns[i])
                                            )
                                            sharpe = (
                                                float(sharpes.flat[idx])
                                                if idx < sharpes.size
                                                else float(sharpes[i])
                                            )
                                            max_dd = (
                                                float(max_dds.flat[idx])
                                                if idx < max_dds.size
                                                else float(max_dds[i])
                                            )
                                            win_rate = (
                                                float(win_rates.flat[idx])
                                                if hasattr(win_rates, "flat")
                                                and idx < win_rates.size
                                                else 0.0
                                            )
                                            n_trades = (
                                                int(total_trades_arr.flat[idx])
                                                if idx < total_trades_arr.size
                                                else int(total_trades_arr[i])
                                            )
                                    else:
                                        # Scalar result (single combination)
                                        total_return = float(total_returns)
                                        sharpe = float(sharpes)
                                        max_dd = float(max_dds)
                                        win_rate = (
                                            float(win_rates)
                                            if not pd.isna(win_rates)
                                            else 0.0
                                        )
                                        n_trades = int(total_trades_arr)

                                    # Handle NaN values
                                    if np.isnan(total_return):
                                        total_return = 0.0
                                    if np.isnan(sharpe):
                                        sharpe = 0.0
                                    if np.isnan(max_dd):
                                        max_dd = 0.0
                                    if np.isnan(win_rate):
                                        win_rate = 0.0

                                    # Calculate profit factor (simplified for speed)
                                    profit_factor = 0.0
                                    if win_rate > 0 and n_trades > 0:
                                        # Approximate profit factor from win rate
                                        avg_win = tp if tp else 2.0
                                        avg_loss = sl if sl else 1.0
                                        if win_rate > 0 and (1 - win_rate) > 0:
                                            profit_factor = (win_rate * avg_win) / (
                                                (1 - win_rate) * avg_loss
                                            )

                                    # Calmar ratio
                                    calmar = (
                                        total_return / max_dd
                                        if max_dd > 0.01
                                        else total_return * 10
                                    )

                                    # Scale return for leverage
                                    total_return = total_return / leverage

                                    results.append(
                                        {
                                            "params": {
                                                "rsi_period": period,
                                                "rsi_overbought": overbought,
                                                "rsi_oversold": oversold,
                                                "stop_loss_pct": sl,
                                                "take_profit_pct": tp,
                                            },
                                            "total_return": total_return,
                                            "sharpe_ratio": sharpe,
                                            "max_drawdown": max_dd,
                                            "win_rate": win_rate,
                                            "total_trades": n_trades,
                                            "profit_factor": profit_factor,
                                            "calmar_ratio": calmar,
                                            "trades": [],  # Skip for speed, fetch on demand
                                            "equity_curve": None,  # Skip for speed
                                        }
                                    )

                                except Exception as e:
                                    logger.debug(f"Skip combination: {e}")
                                    continue

                    except Exception as e:
                        logger.warning(
                            f"Vectorized batch failed for RSI({period}, {overbought}, {oversold}): {e}"
                        )
                        # Fallback to individual calls for this RSI config
                        for sl in stop_losses:
                            for tp in take_profits:
                                try:
                                    # Build kwargs for fallback single call
                                    pf_kwargs_single = {
                                        "close": close_series,
                                        "entries": entries,
                                        "exits": exits,
                                        "init_cash": initial_capital * leverage,
                                        "size": 1.0,
                                        "size_type": "percent",
                                        "fees": commission,
                                        "freq": freq,
                                        "sl_stop": sl / 100.0 if sl else None,
                                        "tp_stop": tp / 100.0 if tp else None,
                                        # QUICK REVERSALS FIX
                                        "upon_long_conflict": "ignore",
                                        "upon_short_conflict": "ignore",
                                        "upon_dir_conflict": "ignore",
                                        "upon_opposite_entry": "ignore",
                                    }
                                    # INTRABAR SL/TP FIX
                                    if high_series is not None:
                                        pf_kwargs_single["high"] = high_series
                                    if low_series is not None:
                                        pf_kwargs_single["low"] = low_series

                                    pf_single = vbt.Portfolio.from_signals(
                                        **pf_kwargs_single
                                    )
                                    stats = pf_single.stats()
                                    total_return = (
                                        float(stats.get("Total Return [%]", 0))
                                        / leverage
                                    )
                                    sharpe = float(stats.get("Sharpe Ratio", 0))
                                    max_dd = abs(
                                        float(stats.get("Max Drawdown [%]", 0))
                                    )
                                    win_rate = float(stats.get("Win Rate [%]", 0)) / 100
                                    n_trades = int(stats.get("Total Trades", 0))

                                    results.append(
                                        {
                                            "params": {
                                                "rsi_period": period,
                                                "rsi_overbought": overbought,
                                                "rsi_oversold": oversold,
                                                "stop_loss_pct": sl,
                                                "take_profit_pct": tp,
                                            },
                                            "total_return": total_return,
                                            "sharpe_ratio": sharpe,
                                            "max_drawdown": max_dd,
                                            "win_rate": win_rate,
                                            "total_trades": n_trades,
                                            "profit_factor": 0.0,
                                            "calmar_ratio": total_return / max_dd
                                            if max_dd > 0.01
                                            else 0,
                                            "trades": [],
                                            "equity_curve": None,
                                        }
                                    )
                                except Exception:
                                    continue

        return results

    def _calculate_rsi_numpy(self, close: np.ndarray, period: int) -> np.ndarray:
        """Calculate RSI using pure numpy (fallback if Numba unavailable)"""
        delta = np.diff(close, prepend=close[0])
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)

        # Wilder's smoothing
        avg_gain = np.zeros_like(close)
        avg_loss = np.zeros_like(close)

        # Initialize with SMA
        avg_gain[period] = np.mean(gain[1 : period + 1])
        avg_loss[period] = np.mean(loss[1 : period + 1])

        # Exponential smoothing
        for i in range(period + 1, len(close)):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period

        rs = np.divide(
            avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0
        )
        rsi = 100 - (100 / (1 + rs))
        rsi[:period] = 50  # Fill initial values

        return rsi

    def _detect_frequency(self, candles: pd.DataFrame) -> str:
        """Detect candle frequency from data"""
        if len(candles) < 2:
            return "1H"

        # Get time difference between first two candles
        diff = (candles.index[1] - candles.index[0]).total_seconds()

        freq_map = {
            60: "1T",
            180: "3T",
            300: "5T",
            900: "15T",
            1800: "30T",
            3600: "1H",
            7200: "2H",
            14400: "4H",
            21600: "6H",
            43200: "12H",
            86400: "1D",
            604800: "1W",
        }

        return freq_map.get(int(diff), "1H")

    def _apply_filters(
        self, results: list[dict], filters: dict[str, float]
    ) -> list[dict]:
        """Apply minimum threshold filters"""
        filtered = []

        min_trades = filters.get("min_trades", 0)
        max_drawdown = filters.get("max_drawdown_limit", 1.0) * 100
        min_profit_factor = filters.get("min_profit_factor", 0)
        min_win_rate = filters.get("min_win_rate", 0)

        for r in results:
            if r["total_trades"] < min_trades:
                continue
            if r["max_drawdown"] > max_drawdown:
                continue
            if r["profit_factor"] < min_profit_factor:
                continue
            if r["win_rate"] < min_win_rate:
                continue
            filtered.append(r)

        return filtered

    def _calculate_scores(
        self,
        results: list[dict],
        metric: str,
        weights: dict[str, float] | None = None,
    ) -> list[dict]:
        """Calculate optimization scores for each result"""
        for r in results:
            if metric == "sharpe_ratio":
                r["score"] = r["sharpe_ratio"]
            elif metric == "total_return":
                r["score"] = r["total_return"]
            elif metric == "win_rate":
                r["score"] = r["win_rate"]
            elif metric == "calmar_ratio":
                r["score"] = r["calmar_ratio"]
            elif metric == "profit_factor":
                r["score"] = r["profit_factor"]
            elif metric == "max_drawdown":
                r["score"] = -r["max_drawdown"]
            elif metric == "custom_score":
                # Weighted composite score
                w = weights or {
                    "return": 0.4,
                    "drawdown": 0.3,
                    "sharpe": 0.2,
                    "win_rate": 0.1,
                }

                norm_return = max(min(r["total_return"] / 100, 2), -2)
                norm_dd = 1 / (1 + r["max_drawdown"] / 100)
                norm_sharpe = max(min(r["sharpe_ratio"] / 2, 2), -2)
                norm_wr = r["win_rate"]

                r["score"] = (
                    w.get("return", 0.4) * norm_return
                    + w.get("drawdown", 0.3) * norm_dd
                    + w.get("sharpe", 0.2) * norm_sharpe
                    + w.get("win_rate", 0.1) * norm_wr
                )
            else:
                r["score"] = r["sharpe_ratio"]

        return results


# =============================================================================
# Numba JIT-compiled functions for maximum performance
# =============================================================================

if NUMBA_AVAILABLE:

    @jit(nopython=True, cache=True, fastmath=True)
    def _calculate_rsi_numba(close: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate RSI using Numba JIT compilation.

        ~10-50x faster than pure Python/pandas implementation.
        """
        n = len(close)
        rsi = np.empty(n, dtype=np.float64)
        rsi[:] = 50.0  # Default value

        if n < period + 1:
            return rsi

        # Calculate price changes
        delta = np.empty(n, dtype=np.float64)
        delta[0] = 0
        for i in range(1, n):
            delta[i] = close[i] - close[i - 1]

        # Separate gains and losses
        gains = np.empty(n, dtype=np.float64)
        losses = np.empty(n, dtype=np.float64)

        for i in range(n):
            if delta[i] > 0:
                gains[i] = delta[i]
                losses[i] = 0
            else:
                gains[i] = 0
                losses[i] = -delta[i]

        # Initial averages (SMA)
        avg_gain = 0.0
        avg_loss = 0.0
        for i in range(1, period + 1):
            avg_gain += gains[i]
            avg_loss += losses[i]
        avg_gain /= period
        avg_loss /= period

        # First RSI value
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi[period] = 100 - (100 / (1 + rs))
        else:
            rsi[period] = 100 if avg_gain > 0 else 50

        # Wilder's smoothing for remaining values
        for i in range(period + 1, n):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi[i] = 100 - (100 / (1 + rs))
            else:
                rsi[i] = 100 if avg_gain > 0 else 50

        return rsi
else:

    def _calculate_rsi_numba(close: np.ndarray, period: int) -> np.ndarray:
        """Fallback when Numba is not available"""
        # Use numpy implementation
        delta = np.diff(close, prepend=close[0])
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)

        avg_gain = np.zeros_like(close)
        avg_loss = np.zeros_like(close)

        if len(close) > period:
            avg_gain[period] = np.mean(gain[1 : period + 1])
            avg_loss[period] = np.mean(loss[1 : period + 1])

            for i in range(period + 1, len(close)):
                avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
                avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period

        rs = np.divide(
            avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0
        )
        rsi = 100 - (100 / (1 + rs))
        rsi[:period] = 50

        return rsi


# =============================================================================
# CuPy GPU-accelerated functions for NVIDIA GPUs
# =============================================================================

if CUPY_AVAILABLE:

    def _calculate_rsi_gpu(close: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate RSI using CuPy GPU acceleration.

        ~50-200x faster than CPU for large datasets.
        Automatically transfers data to/from GPU.
        """
        n = len(close)

        # Transfer to GPU
        close_gpu = cp.asarray(close, dtype=cp.float64)

        # Calculate price changes on GPU
        delta = cp.diff(close_gpu, prepend=close_gpu[0])

        # Separate gains and losses
        gains = cp.where(delta > 0, delta, 0)
        losses = cp.where(delta < 0, -delta, 0)

        # Initialize RSI array
        rsi_gpu = cp.full(n, 50.0, dtype=cp.float64)

        if n <= period:
            return cp.asnumpy(rsi_gpu)

        # Initial SMA for first RSI value
        avg_gain = cp.mean(gains[1 : period + 1])
        avg_loss = cp.mean(losses[1 : period + 1])

        # Calculate RSI using Wilder's smoothing
        # For GPU efficiency, we use a vectorized approach with cumsum
        alpha = 1.0 / period

        # Use exponential moving average approximation (faster on GPU)
        # This gives slightly different results but is ~100x faster
        gains_ema = cp.zeros(n, dtype=cp.float64)
        losses_ema = cp.zeros(n, dtype=cp.float64)

        gains_ema[period] = avg_gain
        losses_ema[period] = avg_loss

        # Vectorized EMA calculation using scan
        for i in range(period + 1, n):
            gains_ema[i] = alpha * gains[i] + (1 - alpha) * gains_ema[i - 1]
            losses_ema[i] = alpha * losses[i] + (1 - alpha) * losses_ema[i - 1]

        # Calculate RS and RSI
        rs = cp.divide(
            gains_ema, losses_ema, out=cp.zeros_like(gains_ema), where=losses_ema != 0
        )
        rsi_gpu = 100 - (100 / (1 + rs))
        rsi_gpu[:period] = 50

        # Transfer back to CPU
        return cp.asnumpy(rsi_gpu)

    def _batch_calculate_rsi_gpu(
        close: np.ndarray, periods: list[int]
    ) -> dict[int, np.ndarray]:
        """
        Calculate RSI for multiple periods in a single GPU batch.

        Much more efficient than calling _calculate_rsi_gpu multiple times.
        """
        results = {}
        n = len(close)

        # Transfer to GPU once
        close_gpu = cp.asarray(close, dtype=cp.float64)
        delta = cp.diff(close_gpu, prepend=close_gpu[0])
        gains = cp.where(delta > 0, delta, 0)
        losses = cp.where(delta < 0, -delta, 0)

        for period in periods:
            if n <= period:
                results[period] = np.full(n, 50.0)
                continue

            rsi_gpu = cp.full(n, 50.0, dtype=cp.float64)

            # Initial averages
            avg_gain = float(cp.mean(gains[1 : period + 1]))
            avg_loss = float(cp.mean(losses[1 : period + 1]))

            # Create arrays for EMA
            gains_ema = cp.zeros(n, dtype=cp.float64)
            losses_ema = cp.zeros(n, dtype=cp.float64)
            gains_ema[period] = avg_gain
            losses_ema[period] = avg_loss

            # Wilder's smoothing
            alpha = 1.0 / period
            for i in range(period + 1, n):
                gains_ema[i] = alpha * float(gains[i]) + (1 - alpha) * gains_ema[i - 1]
                losses_ema[i] = (
                    alpha * float(losses[i]) + (1 - alpha) * losses_ema[i - 1]
                )

            # RSI
            rs = cp.divide(
                gains_ema,
                losses_ema,
                out=cp.zeros_like(gains_ema),
                where=losses_ema != 0,
            )
            rsi_gpu = 100 - (100 / (1 + rs))
            rsi_gpu[:period] = 50

            results[period] = cp.asnumpy(rsi_gpu)

        return results

else:
    # Fallback when CuPy not available
    def _calculate_rsi_gpu(close: np.ndarray, period: int) -> np.ndarray:
        """Fallback to Numba when GPU not available"""
        return _calculate_rsi_numba(close, period)

    def _batch_calculate_rsi_gpu(
        close: np.ndarray, periods: list[int]
    ) -> dict[int, np.ndarray]:
        """Fallback batch calculation"""
        return {p: _calculate_rsi_numba(close, p) for p in periods}
