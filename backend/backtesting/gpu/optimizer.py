"""
GPUGridOptimizer class and run_gpu_optimization() entry point.

Extracted from gpu_optimizer.py (lines 2544-4122).
The main optimizer class that orchestrates:
  - vectorized CPU optimization (Numba prange, default for <10M combos)
  - parallel CPU optimization (multiprocessing, for 10M+ combos)
  - GPU optimization (CuPy, when GPU available)
"""

import time

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.gpu.device import GPU_AVAILABLE, cp
from backend.backtesting.gpu.kernels import (
    JOBLIB_AVAILABLE,
    MAX_COMBINATIONS,
    N_WORKERS,
    NUMBA_AVAILABLE,
    _backtest_all_v3_hoisted,
    _backtest_all_v4_early_exit,
    _backtest_all_v5_transposed,
    _backtest_all_with_params,
    _calculate_all_rsi_vectorized,
    _fast_calculate_rsi,
    _fast_simulate_backtest,
    _precompute_all_signals,
)
from backend.backtesting.gpu.parallel import (
    _backtest_all_gpu,
    _calculate_all_rsi_gpu,
)
from backend.backtesting.gpu.pool import WarmProcessPool
from backend.backtesting.gpu.result import GPUOptimizationResult


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

        logger.info("рџљЂ GPU Grid Optimizer starting")
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

        logger.info(f"вњ… Optimization completed in {execution_time:.2f}s")
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
