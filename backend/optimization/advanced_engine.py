"""
🚀 Advanced Optimization Engine
Integrates all new optimization modules into a unified interface
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

# Import new modules
from backend.core.extended_metrics import (
    ExtendedMetricsCalculator,
    ExtendedMetricsResult,
)
from backend.ml.regime_detection import RegimeDetectionResult, get_regime_detector
from backend.optimization.optuna_optimizer import (
    OPTUNA_AVAILABLE,
    OptunaOptimizationResult,
    OptunaOptimizer,
)
from backend.optimization.ray_optimizer import (
    RAY_AVAILABLE,
    MultiprocessingOptimizer,
    RayParallelOptimizer,
    get_parallel_optimizer,
)
from backend.validation.walk_forward import WalkForwardResult, WalkForwardValidator


@dataclass
class AdvancedOptimizationResult:
    """Complete result from advanced optimization"""

    # Basic optimization results
    best_params: dict[str, Any]
    best_sharpe: float
    best_sortino: float
    best_calmar: float

    # Extended metrics for best params
    extended_metrics: ExtendedMetricsResult

    # Walk-forward validation (if performed)
    walk_forward_result: WalkForwardResult | None = None
    is_robust: bool = False
    robustness_score: float = 0.0

    # Regime analysis (if performed)
    regime_result: RegimeDetectionResult | None = None
    current_regime: str = "Unknown"

    # Optimization statistics
    total_combinations_tested: int = 0
    optimization_time_seconds: float = 0.0
    optimization_method: str = "grid"

    # Top N results
    top_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_params": self.best_params,
            "best_sharpe": round(self.best_sharpe, 4),
            "best_sortino": round(self.best_sortino, 4),
            "best_calmar": round(self.best_calmar, 4),
            "extended_metrics": self.extended_metrics.to_dict()
            if self.extended_metrics
            else {},
            "is_robust": self.is_robust,
            "robustness_score": round(self.robustness_score, 2),
            "current_regime": self.current_regime,
            "total_combinations": self.total_combinations_tested,
            "optimization_time": round(self.optimization_time_seconds, 2),
            "optimization_method": self.optimization_method,
        }


class AdvancedOptimizationEngine:
    """
    Advanced Optimization Engine combining all new features.

    Features:
    - Multiple optimization methods (Grid, Bayesian/Optuna, Genetic)
    - Extended risk metrics (Sortino, Calmar, Omega)
    - Walk-forward validation
    - Regime detection and adaptive parameters
    - Parallel/distributed execution
    """

    def __init__(
        self,
        backtest_engine,
        use_extended_metrics: bool = True,
        use_walk_forward: bool = True,
        use_regime_detection: bool = True,
        optimization_method: str = "optuna",
        parallel_backend: str = "auto",
    ):
        """
        Initialize advanced optimization engine.

        Args:
            backtest_engine: Backtest engine instance
            use_extended_metrics: Calculate extended risk metrics
            use_walk_forward: Perform walk-forward validation
            use_regime_detection: Detect market regimes
            optimization_method: 'grid', 'optuna', 'random'
            parallel_backend: 'ray', 'multiprocessing', 'auto'
        """
        self.engine = backtest_engine
        self.use_extended_metrics = use_extended_metrics
        self.use_walk_forward = use_walk_forward
        self.use_regime_detection = use_regime_detection
        self.optimization_method = optimization_method
        self.parallel_backend = parallel_backend

        # Initialize components
        self.metrics_calculator = ExtendedMetricsCalculator()

        if OPTUNA_AVAILABLE and optimization_method == "optuna":
            self.optuna_optimizer = OptunaOptimizer()
        else:
            self.optuna_optimizer = None

        self.walk_forward = WalkForwardValidator() if use_walk_forward else None

        if use_regime_detection:
            try:
                self.regime_detector = get_regime_detector(method="kmeans")
            except Exception:
                self.regime_detector = None
        else:
            self.regime_detector = None

        # Parallel optimizer
        if parallel_backend == "auto":
            self.parallel_optimizer = get_parallel_optimizer(prefer_ray=True)
        elif parallel_backend == "ray" and RAY_AVAILABLE:
            self.parallel_optimizer = RayParallelOptimizer()
        else:
            self.parallel_optimizer = MultiprocessingOptimizer()

    def optimize(
        self,
        data: pd.DataFrame,
        strategy_class,
        param_space: dict[str, Any],
        base_config: dict[str, Any],
        n_trials: int = 100,
        metric: str = "sharpe_ratio",
        validate: bool = True,
    ) -> AdvancedOptimizationResult:
        """
        Run full optimization pipeline.

        Args:
            data: Market data DataFrame
            strategy_class: Strategy class to optimize
            param_space: Parameter search space
            base_config: Base backtest configuration
            n_trials: Number of optimization trials
            metric: Primary metric to optimize
            validate: Run walk-forward validation

        Returns:
            AdvancedOptimizationResult with comprehensive results
        """
        start_time = datetime.now()

        logger.info("Starting advanced optimization")
        logger.info(f"Method: {self.optimization_method}, Trials: {n_trials}")

        # Step 1: Regime Detection (if enabled)
        regime_result = None
        if self.use_regime_detection and self.regime_detector:
            try:
                regime_result = self.regime_detector.fit_predict(data)
                logger.info(f"Detected {regime_result.n_regimes} regimes")
                logger.info(f"Current regime: {regime_result.current_regime_name}")
            except Exception as e:
                logger.warning(f"Regime detection failed: {e}")

        # Step 2: Optimization
        if self.optimization_method == "optuna" and self.optuna_optimizer:
            opt_result = self._optimize_optuna(
                data, strategy_class, param_space, base_config, n_trials, metric
            )
            best_params = opt_result.best_params
            best_value = opt_result.best_value
            total_tested = opt_result.n_trials
            top_results = (
                opt_result.top_results if hasattr(opt_result, "top_results") else []
            )
        else:
            # Fallback to grid/random
            opt_result = self._optimize_grid(
                data, strategy_class, param_space, base_config, metric
            )
            best_params = opt_result["best_params"]
            best_value = opt_result["best_value"]
            total_tested = opt_result["total_tested"]
            top_results = opt_result.get("top_results", [])

        # Step 3: Run final backtest with best params
        final_result = self._run_backtest(
            data, strategy_class, best_params, base_config
        )

        # Step 4: Calculate extended metrics
        if self.use_extended_metrics and hasattr(final_result, "equity_curve"):
            equity = np.array(final_result.equity_curve.equity)
            trades = final_result.trades if hasattr(final_result, "trades") else []
            extended_metrics = self.metrics_calculator.calculate_all(equity, trades)
        else:
            extended_metrics = None

        # Step 5: Walk-Forward Validation (if enabled)
        wf_result = None
        is_robust = False
        robustness_score = 0

        if validate and self.use_walk_forward and self.walk_forward:
            try:
                wf_result = self._run_walk_forward(
                    data, strategy_class, param_space, base_config
                )
                is_robust = wf_result.is_robust
                robustness_score = wf_result.robustness_score
                logger.info(f"Walk-Forward: {wf_result.validation_status.value}")
            except Exception as e:
                logger.warning(f"Walk-forward validation failed: {e}")

        end_time = datetime.now()
        optimization_time = (end_time - start_time).total_seconds()

        logger.info(f"Optimization complete in {optimization_time:.1f}s")
        logger.info(f"Best {metric}: {best_value:.4f}")

        # Create result
        result = AdvancedOptimizationResult(
            best_params=best_params,
            best_sharpe=extended_metrics.sharpe_ratio
            if extended_metrics
            else best_value,
            best_sortino=extended_metrics.sortino_ratio if extended_metrics else 0,
            best_calmar=extended_metrics.calmar_ratio if extended_metrics else 0,
            extended_metrics=extended_metrics,
            walk_forward_result=wf_result,
            is_robust=is_robust,
            robustness_score=robustness_score,
            regime_result=regime_result,
            current_regime=regime_result.current_regime_name
            if regime_result
            else "Unknown",
            total_combinations_tested=total_tested,
            optimization_time_seconds=optimization_time,
            optimization_method=self.optimization_method,
            top_results=top_results[:10],
        )

        return result

    def _optimize_optuna(
        self,
        data: pd.DataFrame,
        strategy_class,
        param_space: dict[str, Any],
        base_config: dict[str, Any],
        n_trials: int,
        metric: str,
    ) -> OptunaOptimizationResult:
        """Run Optuna optimization"""

        def objective(params):
            result = self._run_backtest(data, strategy_class, params, base_config)
            return getattr(result.metrics, metric, 0)

        return self.optuna_optimizer.optimize_strategy(
            objective_fn=objective,
            param_space=param_space,
            n_trials=n_trials,
            show_progress=True,
        )

    def _optimize_grid(
        self,
        data: pd.DataFrame,
        strategy_class,
        param_space: dict[str, Any],
        base_config: dict[str, Any],
        metric: str,
    ) -> dict[str, Any]:
        """Run grid search optimization"""
        from itertools import product

        # Generate all combinations
        param_names = list(param_space.keys())
        param_values = []

        for _name, spec in param_space.items():
            if spec["type"] == "int":
                values = list(range(spec["low"], spec["high"] + 1, spec.get("step", 1)))
            elif spec["type"] == "float":
                step = spec.get("step", (spec["high"] - spec["low"]) / 10)
                values = list(np.arange(spec["low"], spec["high"] + step, step))
            else:
                values = spec.get("choices", [])
            param_values.append(values)

        combinations = list(product(*param_values))

        # Run backtests
        results = []
        for combo in combinations:
            params = dict(zip(param_names, combo, strict=False))
            try:
                result = self._run_backtest(data, strategy_class, params, base_config)
                value = getattr(result.metrics, metric, 0)
                results.append({"params": params, "value": value})
            except Exception:
                pass

        # Find best
        results.sort(key=lambda x: x["value"], reverse=True)

        return {
            "best_params": results[0]["params"] if results else {},
            "best_value": results[0]["value"] if results else 0,
            "total_tested": len(results),
            "top_results": results[:10],
        }

    def _run_backtest(
        self,
        data: pd.DataFrame,
        strategy_class,
        params: dict[str, Any],
        base_config: dict[str, Any],
    ):
        """Run single backtest"""
        from backend.backtesting.models import BacktestConfig

        # Merge configs
        full_config = {**base_config}

        # Separate strategy params from config params
        strategy_params = {}
        config_params = {}

        config_keys = {"stop_loss", "take_profit", "position_size", "leverage"}

        for k, v in params.items():
            if k in config_keys:
                config_params[k] = v
            else:
                strategy_params[k] = v

        full_config.update(config_params)
        full_config["strategy_params"] = strategy_params

        config = BacktestConfig(**full_config)

        strategy = strategy_class(params=strategy_params)
        signals = strategy.generate_signals(data)

        return self.engine._run_fallback(config, data, signals)

    def _run_walk_forward(
        self,
        data: pd.DataFrame,
        strategy_class,
        param_space: dict[str, Any],
        base_config: dict[str, Any],
    ) -> WalkForwardResult:
        """Run walk-forward validation"""

        def optimizer_fn(is_data, ps):
            # Simple grid optimization on IS period
            result = self._optimize_grid(
                is_data, strategy_class, ps, base_config, "sharpe_ratio"
            )
            return result["best_params"]

        def backtest_fn(data_slice, strategy, params):
            return self._run_backtest(data_slice, strategy_class, params, base_config)

        return self.walk_forward.validate(
            data=data,
            strategy_class=strategy_class,
            optimizer=optimizer_fn,
            backtest_fn=backtest_fn,
            param_space=param_space,
            strategy_name=strategy_class.__name__,
        )


def create_advanced_optimizer(backtest_engine, **kwargs) -> AdvancedOptimizationEngine:
    """Factory function to create advanced optimizer"""
    return AdvancedOptimizationEngine(backtest_engine, **kwargs)
