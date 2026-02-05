"""
⚡ Ray Parallel Optimizer Module
Implements distributed computing using Ray framework
Based on Goldman Sachs and industry best practices 2024-2026
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

# Ray is optional dependency
try:
    import ray
    from ray.util.multiprocessing import Pool as RayPool  # noqa: F401

    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None

from loguru import logger


@dataclass
class ParallelOptimizationResult:
    """Result container for parallel optimization"""

    best_params: dict[str, Any]
    best_value: float
    total_combinations: int
    completed_combinations: int
    failed_combinations: int
    execution_time_seconds: float

    # All results
    all_results: list[dict[str, Any]] = field(default_factory=list)

    # Top N results
    top_n: int = 10
    top_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_params": self.best_params,
            "best_value": round(self.best_value, 6),
            "total_combinations": self.total_combinations,
            "completed_combinations": self.completed_combinations,
            "failed_combinations": self.failed_combinations,
            "execution_time_seconds": round(self.execution_time_seconds, 2),
            "top_results": self.top_results[: self.top_n],
        }


class RayParallelOptimizer:
    """
    Ray-based parallel optimizer for trading strategies.

    "Goldman Sachs have leveraged Ray to enhance machine learning models
    in finance, including backtesting workflows." - Ray Summit

    Features:
    - Distributed computing across multiple cores/nodes
    - Efficient memory management with shared objects
    - Fault tolerance for long-running optimizations
    - GPU support for hybrid workloads
    """

    def __init__(
        self,
        num_cpus: int | None = None,
        num_gpus: int = 0,
        memory_per_worker: int | None = None,
        dashboard: bool = False,
    ):
        """
        Initialize Ray parallel optimizer.

        Args:
            num_cpus: Number of CPUs to use (None = all available)
            num_gpus: Number of GPUs to use
            memory_per_worker: Memory in bytes per worker
            dashboard: Enable Ray dashboard (http://localhost:8265)
        """
        if not RAY_AVAILABLE:
            raise ImportError("Ray is not installed. Install with: pip install ray")

        self.num_cpus = num_cpus or os.cpu_count()
        self.num_gpus = num_gpus
        self.memory_per_worker = memory_per_worker
        self.dashboard = dashboard
        self._initialized = False

    def _ensure_initialized(self):
        """Initialize Ray if not already done"""
        if not self._initialized:
            if not ray.is_initialized():
                ray.init(
                    num_cpus=self.num_cpus,
                    num_gpus=self.num_gpus,
                    include_dashboard=self.dashboard,
                    ignore_reinit_error=True,
                    logging_level="warning",
                )
                logger.info(
                    f"Ray initialized with {self.num_cpus} CPUs, {self.num_gpus} GPUs"
                )
            self._initialized = True

    def shutdown(self):
        """Shutdown Ray"""
        if ray.is_initialized():
            ray.shutdown()
            self._initialized = False
            logger.info("Ray shutdown complete")

    def parallel_backtest(
        self,
        configs: list[dict[str, Any]],
        backtest_fn: Callable,
        data,
        metric: str = "sharpe_ratio",
        chunk_size: int = 100,
        show_progress: bool = True,
    ) -> ParallelOptimizationResult:
        """
        Run parallel backtests across multiple configurations.

        Args:
            configs: List of configuration dictionaries
            backtest_fn: Function(config, data) -> result
            data: Market data (will be placed in Ray object store)
            metric: Metric to optimize
            chunk_size: Number of configs per batch
            show_progress: Show progress bar

        Returns:
            ParallelOptimizationResult with best and all results
        """
        self._ensure_initialized()

        start_time = datetime.now()
        total = len(configs)

        logger.info(f"Starting parallel optimization: {total} configurations")

        # Put data in Ray object store for efficient sharing
        data_ref = ray.put(data)

        # Define remote backtest function
        @ray.remote
        def remote_backtest(config, data_ref, metric):
            data = ray.get(data_ref)
            try:
                result = backtest_fn(config, data)
                metric_value = getattr(result.metrics, metric, None)
                if metric_value is None:
                    metric_value = getattr(result, metric, 0)
                return {
                    "config": config,
                    "value": float(metric_value) if metric_value else 0,
                    "success": True,
                }
            except Exception as e:
                return {
                    "config": config,
                    "value": float("-inf"),
                    "success": False,
                    "error": str(e),
                }

        # Submit all tasks
        futures = []
        for config in configs:
            future = remote_backtest.remote(config, data_ref, metric)
            futures.append(future)

        # Collect results with progress tracking
        results = []
        completed = 0
        failed = 0

        if show_progress:
            # Process in batches for progress updates
            while futures:
                batch_size = min(chunk_size, len(futures))
                ready, futures = ray.wait(futures, num_returns=batch_size, timeout=60)

                for result in ray.get(ready):
                    results.append(result)
                    completed += 1
                    if not result.get("success", False):
                        failed += 1

                progress = completed / total * 100
                logger.info(f"Progress: {completed}/{total} ({progress:.1f}%)")
        else:
            results = ray.get(futures)
            completed = len(results)
            failed = sum(1 for r in results if not r.get("success", False))

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # Find best result
        successful_results = [r for r in results if r.get("success", False)]

        if not successful_results:
            logger.error("All backtests failed!")
            return ParallelOptimizationResult(
                best_params={},
                best_value=0,
                total_combinations=total,
                completed_combinations=completed,
                failed_combinations=failed,
                execution_time_seconds=execution_time,
            )

        # Sort by value (descending for maximize)
        sorted_results = sorted(
            successful_results, key=lambda x: x["value"], reverse=True
        )
        best = sorted_results[0]

        # Top N results
        top_results = [
            {"params": r["config"], "value": r["value"]} for r in sorted_results[:10]
        ]

        logger.info(f"Optimization complete in {execution_time:.1f}s")
        logger.info(f"Best {metric}: {best['value']:.6f}")
        logger.info(f"Failed: {failed}/{total}")

        return ParallelOptimizationResult(
            best_params=best["config"],
            best_value=best["value"],
            total_combinations=total,
            completed_combinations=completed,
            failed_combinations=failed,
            execution_time_seconds=execution_time,
            all_results=results,
            top_results=top_results,
        )

    def parallel_walk_forward(
        self,
        data,
        strategy_class,
        param_space: dict[str, Any],
        walk_forward_config: dict[str, int],
        optimizer_fn: Callable,
        backtest_fn: Callable,
    ) -> dict[str, Any]:
        """
        Parallel walk-forward optimization.

        Each period's optimization runs in parallel.

        Args:
            data: Full historical data
            strategy_class: Strategy class
            param_space: Parameter search space
            walk_forward_config: {'is_size': X, 'oos_size': Y, 'step': Z}
            optimizer_fn: Function to optimize parameters
            backtest_fn: Function to run backtest

        Returns:
            Walk-forward results with all periods
        """
        self._ensure_initialized()

        is_size = walk_forward_config.get("is_size", 720)
        oos_size = walk_forward_config.get("oos_size", 168)
        step = walk_forward_config.get("step", 168)

        n_bars = len(data)
        total_window = is_size + oos_size

        # Generate periods
        periods = []
        start = 0
        while start + total_window <= n_bars:
            periods.append(
                {
                    "is_start": start,
                    "is_end": start + is_size,
                    "oos_start": start + is_size,
                    "oos_end": start + is_size + oos_size,
                }
            )
            start += step

        logger.info(f"Walk-forward: {len(periods)} periods to process")

        # Put shared data in object store
        data_ref = ray.put(data)
        param_space_ref = ray.put(param_space)

        @ray.remote
        def process_period(
            period_info,
            data_ref,
            param_space_ref,
            strategy_class,
            optimizer_fn,
            backtest_fn,
        ):
            data = ray.get(data_ref)
            param_space = ray.get(param_space_ref)

            is_data = data.iloc[period_info["is_start"] : period_info["is_end"]]
            oos_data = data.iloc[period_info["oos_start"] : period_info["oos_end"]]

            # Optimize on in-sample
            best_params = optimizer_fn(is_data, param_space)

            # Validate on out-of-sample
            strategy = strategy_class(params=best_params)
            is_result = backtest_fn(is_data, strategy, best_params)
            oos_result = backtest_fn(oos_data, strategy, best_params)

            return {
                "period": period_info,
                "best_params": best_params,
                "is_sharpe": getattr(is_result.metrics, "sharpe_ratio", 0),
                "oos_sharpe": getattr(oos_result.metrics, "sharpe_ratio", 0),
                "is_return": getattr(is_result.metrics, "total_return", 0),
                "oos_return": getattr(oos_result.metrics, "total_return", 0),
            }

        # Submit all periods in parallel
        futures = [
            process_period.remote(
                p, data_ref, param_space_ref, strategy_class, optimizer_fn, backtest_fn
            )
            for p in periods
        ]

        results = ray.get(futures)

        # Aggregate results
        is_sharpes = [r["is_sharpe"] for r in results]
        oos_sharpes = [r["oos_sharpe"] for r in results]

        return {
            "n_periods": len(periods),
            "avg_is_sharpe": np.mean(is_sharpes),
            "avg_oos_sharpe": np.mean(oos_sharpes),
            "avg_degradation": np.mean(is_sharpes) - np.mean(oos_sharpes),
            "profitable_pct": sum(1 for r in results if r["oos_return"] > 0)
            / len(results)
            * 100,
            "periods": results,
        }


class MultiprocessingOptimizer:
    """
    Fallback optimizer using Python's multiprocessing.

    Used when Ray is not available.
    """

    def __init__(self, n_workers: int | None = None):
        """
        Initialize multiprocessing optimizer.

        Args:
            n_workers: Number of worker processes (None = cpu_count)
        """
        import multiprocessing as mp

        self.n_workers = n_workers or mp.cpu_count()

    def parallel_backtest(
        self,
        configs: list[dict[str, Any]],
        backtest_fn: Callable,
        data,
        metric: str = "sharpe_ratio",
    ) -> ParallelOptimizationResult:
        """
        Run parallel backtests using multiprocessing.

        Args:
            configs: List of configurations
            backtest_fn: Backtest function
            data: Market data
            metric: Metric to optimize

        Returns:
            ParallelOptimizationResult
        """
        import multiprocessing as mp

        start_time = datetime.now()
        total = len(configs)

        logger.info(
            f"Starting multiprocessing optimization: {total} configs, {self.n_workers} workers"
        )

        # Create worker function
        def worker(config):
            try:
                result = backtest_fn(config, data)
                metric_value = getattr(result.metrics, metric, 0)
                return {
                    "config": config,
                    "value": float(metric_value) if metric_value else 0,
                    "success": True,
                }
            except Exception as e:
                return {
                    "config": config,
                    "value": float("-inf"),
                    "success": False,
                    "error": str(e),
                }

        # Run parallel
        with mp.Pool(self.n_workers) as pool:
            results = pool.map(worker, configs)

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # Process results
        successful = [r for r in results if r.get("success", False)]
        failed = len(results) - len(successful)

        if not successful:
            return ParallelOptimizationResult(
                best_params={},
                best_value=0,
                total_combinations=total,
                completed_combinations=len(results),
                failed_combinations=failed,
                execution_time_seconds=execution_time,
            )

        sorted_results = sorted(successful, key=lambda x: x["value"], reverse=True)
        best = sorted_results[0]

        return ParallelOptimizationResult(
            best_params=best["config"],
            best_value=best["value"],
            total_combinations=total,
            completed_combinations=len(results),
            failed_combinations=failed,
            execution_time_seconds=execution_time,
            all_results=results,
            top_results=[
                {"params": r["config"], "value": r["value"]}
                for r in sorted_results[:10]
            ],
        )


def get_parallel_optimizer(prefer_ray: bool = True) -> Any:
    """
    Factory function to get the best available parallel optimizer.

    Args:
        prefer_ray: Prefer Ray if available

    Returns:
        RayParallelOptimizer or MultiprocessingOptimizer
    """
    if prefer_ray and RAY_AVAILABLE:
        logger.info("Using Ray for parallel optimization")
        return RayParallelOptimizer()
    else:
        logger.info(
            "Using multiprocessing for parallel optimization (Ray not available)"
        )
        return MultiprocessingOptimizer()
