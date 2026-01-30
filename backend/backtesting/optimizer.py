"""
🚀 Universal Optimizer - Unified API for GPU and CPU optimization

⚠️ DEPRECATED: This module is deprecated for new development.

This optimizer is RSI-only and doesn't support:
- Pyramiding
- ATR-based SL/TP
- Multi-level TP
- Trailing stop
- Custom strategies

For new projects, use NumbaEngineV2 directly with parameter grid:

    from backend.backtesting.engine_selector import get_engine
    from backend.backtesting.interfaces import BacktestInput
    import itertools

    engine = get_engine("numba")  # NumbaEngineV2 with full V4 support

    param_grid = itertools.product(
        rsi_periods, stop_losses, take_profits, ...
    )

    results = []
    for params in param_grid:
        input_data = BacktestInput(...params...)
        output = engine.run(input_data)
        results.append(output.metrics)

    best = max(results, key=lambda x: x["sharpe_ratio"])

For RSI-only optimization (legacy), this module still works:
- GPU (CuPy + CUDA): ~200K combinations/sec - for large grids (>10K combinations)
- CPU (Numba JIT): ~1K combinations/sec - fallback when GPU unavailable

Usage (deprecated):
    from backend.backtesting.optimizer import UniversalOptimizer, optimize

    # Auto-select best backend
    result = optimize(candles, rsi_periods=[7,14,21], ...)

    # Or use explicitly
    optimizer = UniversalOptimizer(backend="auto")  # auto, gpu, cpu
    result = optimizer.optimize(candles, ...)
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Literal

import pandas as pd
from loguru import logger

# Check GPU availability
try:
    from backend.backtesting.gpu_optimizer import (
        GPU_AVAILABLE,
        GPUGridOptimizer,
        GPUOptimizationResult,
    )

    _GPU_OPTIMIZER_AVAILABLE = True
except ImportError:
    _GPU_OPTIMIZER_AVAILABLE = False
    GPU_AVAILABLE = False
    logger.warning("GPU optimizer not available")

# Check Numba availability
try:
    from backend.backtesting.fast_optimizer import (
        NUMBA_AVAILABLE,
        FastGridOptimizer,
        FastOptimizationResult,
    )

    _NUMBA_OPTIMIZER_AVAILABLE = True
except ImportError:
    _NUMBA_OPTIMIZER_AVAILABLE = False
    NUMBA_AVAILABLE = False
    logger.warning("Fast (Numba) optimizer not available")


@dataclass
class OptimizationResult:
    """
    Unified optimization result with consistent API.

    Provides a single interface regardless of which backend was used.
    """

    status: str
    total_combinations: int
    tested_combinations: int
    execution_time_seconds: float
    best_params: Dict[str, Any]
    best_score: float
    best_metrics: Dict[str, Any]
    top_results: List[Dict[str, Any]]  # Unified name (was best_results/top_results)
    performance_stats: Dict[str, Any]
    backend_used: str  # "gpu" or "cpu"
    combinations_per_second: float = 0.0

    # Aliases for backwards compatibility
    @property
    def best_results(self) -> List[Dict[str, Any]]:
        """Alias for top_results (FastOptimizer compatibility)"""
        return self.top_results

    @property
    def results(self) -> List[Dict[str, Any]]:
        """Alias for top_results"""
        return self.top_results


class UniversalOptimizer:
    """
    Universal optimizer that automatically selects the best backend.

    Performance comparison (5000 candles, 5000 combinations):
    - GPU: 0.024s (~210,000 combinations/sec) - 170x faster!
    - CPU: 4.0s (~1,200 combinations/sec)

    Args:
        backend: Which backend to use
            - "auto": GPU if available, else CPU (recommended)
            - "gpu": Force GPU (raises error if unavailable)
            - "cpu": Force CPU (Numba JIT)
    """

    def __init__(self, backend: Literal["auto", "gpu", "cpu"] = "auto"):
        import warnings
        warnings.warn(
            "UniversalOptimizer is deprecated (RSI-only). "
            "Use NumbaEngineV2 with BacktestInput for full V4 support "
            "(pyramiding, ATR, multi-TP, trailing).",
            DeprecationWarning,
            stacklevel=2,
        )
        self.backend = backend
        self._gpu_optimizer = None
        self._cpu_optimizer = None

        # Determine which backend to use
        if backend == "auto":
            if _GPU_OPTIMIZER_AVAILABLE and GPU_AVAILABLE:
                self._use_gpu = True
                logger.info("🚀 UniversalOptimizer: Using GPU backend (auto-detected)")
            elif _NUMBA_OPTIMIZER_AVAILABLE:
                self._use_gpu = False
                logger.info(
                    "⚡ UniversalOptimizer: Using CPU/Numba backend (GPU not available)"
                )
            else:
                raise RuntimeError(
                    "No optimizer backend available! Install CuPy or Numba."
                )
        elif backend == "gpu":
            if not _GPU_OPTIMIZER_AVAILABLE or not GPU_AVAILABLE:
                raise RuntimeError(
                    "GPU backend requested but not available. Check CUDA/CuPy installation."
                )
            self._use_gpu = True
            logger.info("🚀 UniversalOptimizer: Using GPU backend (forced)")
        elif backend == "cpu":
            if not _NUMBA_OPTIMIZER_AVAILABLE:
                raise RuntimeError("CPU backend requested but Numba not available.")
            self._use_gpu = False
            logger.info("⚡ UniversalOptimizer: Using CPU/Numba backend (forced)")
        else:
            raise ValueError(
                f"Invalid backend: {backend}. Use 'auto', 'gpu', or 'cpu'."
            )

    def _get_gpu_optimizer(self) -> "GPUGridOptimizer":
        """Lazy-load GPU optimizer"""
        if self._gpu_optimizer is None:
            self._gpu_optimizer = GPUGridOptimizer()
        return self._gpu_optimizer

    def _get_cpu_optimizer(self) -> "FastGridOptimizer":
        """Lazy-load CPU optimizer"""
        if self._cpu_optimizer is None:
            self._cpu_optimizer = FastGridOptimizer()
        return self._cpu_optimizer

    def optimize(
        self,
        candles: pd.DataFrame,
        rsi_period_range: List[int],
        rsi_overbought_range: List[int],
        rsi_oversold_range: List[int],
        stop_loss_range: List[float],
        take_profit_range: List[float],
        initial_capital: float = 10000.0,
        leverage: int = 10,
        commission: float = 0.0006,
        slippage: float = 0.0005,
        optimize_metric: str = "sharpe_ratio",
        direction: str = "both",
        top_k: int = 100,
        **kwargs,
    ) -> OptimizationResult:
        """
        Run strategy optimization with the selected backend.

        Args:
            candles: DataFrame with OHLCV data (columns: timestamp, open, high, low, close, volume)
            rsi_period_range: List of RSI periods to test
            rsi_overbought_range: List of RSI overbought levels
            rsi_oversold_range: List of RSI oversold levels
            stop_loss_range: List of stop loss percentages
            take_profit_range: List of take profit percentages
            initial_capital: Starting capital
            leverage: Trading leverage
            commission: Commission rate per trade
            slippage: Slippage rate per trade (e.g. 0.0005 for 0.05%)
            optimize_metric: Metric to optimize ("sharpe_ratio", "total_return", "calmar_ratio")
            direction: Trade direction ("long", "short", "both")
            top_k: Number of top results to return

        Returns:
            OptimizationResult with unified API
        """
        total_combinations = (
            len(rsi_period_range)
            * len(rsi_overbought_range)
            * len(rsi_oversold_range)
            * len(stop_loss_range)
            * len(take_profit_range)
        )

        start_time = time.perf_counter()

        if self._use_gpu:
            result = self._optimize_gpu(
                candles=candles,
                rsi_period_range=rsi_period_range,
                rsi_overbought_range=rsi_overbought_range,
                rsi_oversold_range=rsi_oversold_range,
                stop_loss_range=stop_loss_range,
                take_profit_range=take_profit_range,
                initial_capital=initial_capital,
                leverage=leverage,
                commission=commission,
                slippage=slippage,
                optimize_metric=optimize_metric,
                direction=direction,
                top_k=top_k,
                **kwargs,
            )
            backend_used = "gpu"
        else:
            result = self._optimize_cpu(
                candles=candles,
                rsi_period_range=rsi_period_range,
                rsi_overbought_range=rsi_overbought_range,
                rsi_oversold_range=rsi_oversold_range,
                stop_loss_range=stop_loss_range,
                take_profit_range=take_profit_range,
                initial_capital=initial_capital,
                leverage=leverage,
                commission=commission,
                slippage=slippage,
                optimize_metric=optimize_metric,
                direction=direction,
                **kwargs,
            )
            backend_used = "cpu"

        elapsed = time.perf_counter() - start_time
        comb_per_sec = total_combinations / elapsed if elapsed > 0 else 0

        return OptimizationResult(
            status=result.status,
            total_combinations=result.total_combinations,
            tested_combinations=result.tested_combinations,
            execution_time_seconds=elapsed,
            best_params=result.best_params,
            best_score=result.best_score,
            best_metrics=result.best_metrics,
            top_results=result.top_results,
            performance_stats=result.performance_stats,
            backend_used=backend_used,
            combinations_per_second=comb_per_sec,
        )

    def _optimize_gpu(self, **kwargs) -> GPUOptimizationResult:
        """Run GPU optimization"""
        optimizer = self._get_gpu_optimizer()
        return optimizer.optimize(**kwargs)

    def _optimize_cpu(self, **kwargs) -> FastOptimizationResult:
        """Run CPU optimization"""
        # Remove top_k as FastOptimizer doesn't support it
        kwargs.pop("top_k", None)
        optimizer = self._get_cpu_optimizer()
        return optimizer.optimize(**kwargs)


def optimize(
    candles: pd.DataFrame,
    rsi_period_range: List[int],
    rsi_overbought_range: List[int],
    rsi_oversold_range: List[int],
    stop_loss_range: List[float],
    take_profit_range: List[float],
    backend: Literal["auto", "gpu", "cpu"] = "auto",
    **kwargs,
) -> OptimizationResult:
    """
    Convenience function to run optimization with auto backend selection.

    Example:
        result = optimize(
            candles=df,
            rsi_period_range=[7, 14, 21],
            rsi_overbought_range=[65, 70, 75, 80],
            rsi_oversold_range=[20, 25, 30, 35],
            stop_loss_range=[1, 2, 3],
            take_profit_range=[1.5, 3, 5],
        )

        print(f"Best params: {result.best_params}")
        print(f"Best sharpe: {result.best_score}")
        print(f"Backend: {result.backend_used}")
        print(f"Speed: {result.combinations_per_second:,.0f} comb/sec")
    """
    optimizer = UniversalOptimizer(backend=backend)
    return optimizer.optimize(
        candles=candles,
        rsi_period_range=rsi_period_range,
        rsi_overbought_range=rsi_overbought_range,
        rsi_oversold_range=rsi_oversold_range,
        stop_loss_range=stop_loss_range,
        take_profit_range=take_profit_range,
        **kwargs,
    )


# Module-level info
def get_available_backends() -> Dict[str, bool]:
    """Return which backends are available"""
    return {
        "gpu": _GPU_OPTIMIZER_AVAILABLE and GPU_AVAILABLE,
        "cpu": _NUMBA_OPTIMIZER_AVAILABLE and NUMBA_AVAILABLE,
    }


def get_recommended_backend() -> str:
    """Return the recommended backend for current system"""
    backends = get_available_backends()
    if backends["gpu"]:
        return "gpu"
    elif backends["cpu"]:
        return "cpu"
    else:
        return "none"
