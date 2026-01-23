"""
Bayesian Optimizer using Optuna TPE

High-performance Bayesian optimization for strategy parameter tuning.
Uses Tree-structured Parzen Estimator (TPE) sampler.

Features:
- Supports int, float, and categorical parameters
- Negative values support
- High precision floats (0.01, 0.001, etc.)
- Log-scale sampling option
- Parallel optimization with n_jobs
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

try:
    import optuna
    from optuna.samplers import TPESampler

    OPTUNA_AVAILABLE = True
except ImportError:
    optuna = None
    TPESampler = None
    OPTUNA_AVAILABLE = False
    logger.warning("Optuna not installed. Install with: pip install optuna")


class BayesianOptimizer:
    """
    Bayesian Optimization using Optuna's TPE sampler.

    Supports:
    - Integer parameters with step
    - Float parameters with precision (0.01, 0.001, etc.)
    - Negative value ranges
    - Categorical parameters
    - Log-scale sampling
    """

    def __init__(
        self,
        data: pd.DataFrame,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        n_trials: int = 100,
        n_jobs: int = 1,
        random_state: Optional[int] = None,
    ):
        """
        Initialize Bayesian Optimizer.

        Args:
            data: OHLCV DataFrame for backtesting
            initial_capital: Starting capital
            commission: Trading commission rate
            n_trials: Number of optimization trials
            n_jobs: Number of parallel jobs
            random_state: Random seed for reproducibility
        """
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna is required. Install with: pip install optuna")

        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.n_trials = n_trials
        self.n_jobs = n_jobs
        self.random_state = random_state

        self.study: Optional[optuna.Study] = None
        self._best_params: Optional[Dict[str, Any]] = None
        self._best_value: Optional[float] = None

        # Suppress Optuna logs for cleaner output
        optuna.logging.set_verbosity(optuna.logging.WARNING)

    def _create_sampler(self) -> TPESampler:
        """Create TPE sampler with optional seed."""
        return TPESampler(
            seed=self.random_state,
            n_startup_trials=10,  # Exploration before exploitation
            multivariate=True,  # Consider parameter correlations
        )

    def _suggest_param(
        self, trial: "optuna.Trial", param_name: str, param_spec: Dict[str, Any]
    ) -> Any:
        """
        Suggest a parameter value based on specification.

        Supports:
        - type: "int", "float", "categorical"
        - low: minimum value (can be negative)
        - high: maximum value (can be negative)
        - step: step size (default 1 for int, 0.01 for float)
        - precision: decimal places for rounding
        - log: use log scale
        - values: explicit list of values
        """
        param_type = param_spec.get("type", "float")
        low = param_spec.get("low")
        high = param_spec.get("high")
        step = param_spec.get("step")
        precision = param_spec.get("precision")
        log_scale = param_spec.get("log", False)
        values = param_spec.get("values")

        # Categorical or explicit values
        if values:
            return trial.suggest_categorical(param_name, values)

        if low is None or high is None:
            logger.warning(f"Parameter {param_name} has no low/high bounds, skipping")
            return None

        # Integer parameter
        if param_type == "int":
            int_step = int(step) if step and step >= 1 else 1
            return trial.suggest_int(
                param_name,
                int(low),
                int(high),
                step=int_step,
                log=log_scale and low > 0,  # Log only for positive ranges
            )

        # Float parameter
        if param_type == "float":
            # Determine step size
            if step is None:
                step = 0.01  # Default for floats

            # For very small steps, Optuna doesn't have native step support for floats
            # We'll sample uniformly and then round to the step
            if step < 0.01 or precision:
                # Use uniform sampling and round
                value = trial.suggest_float(
                    param_name, float(low), float(high), log=log_scale and low > 0
                )
                # Round to step or precision
                if precision:
                    return round(value, precision)
                else:
                    return round(value / step) * step
            else:
                # Standard float suggestion
                return trial.suggest_float(
                    param_name,
                    float(low),
                    float(high),
                    step=step,
                    log=log_scale and low > 0,
                )

        # Default to float
        return trial.suggest_float(param_name, float(low), float(high))

    async def optimize_async(
        self,
        strategy_config: Dict[str, Any],
        param_space: Dict[str, Dict[str, Any]],
        metric: str = "sharpe_ratio",
        direction: str = "maximize",
        show_progress: bool = True,
    ) -> Dict[str, Any]:
        """
        Run Bayesian optimization asynchronously.

        Args:
            strategy_config: Base strategy configuration
            param_space: Parameter search space
                Format: {param_name: {type, low, high, step, precision, log, values}}
            metric: Metric to optimize
            direction: "maximize" or "minimize"
            show_progress: Show progress callback

        Returns:
            Optimization results with best params and statistics
        """
        from backend.core.engine_adapter import get_engine

        engine = get_engine()

        # Prepare backtest configuration
        base_config = {
            "symbol": strategy_config.get("symbol", "BTCUSDT"),
            "interval": strategy_config.get("interval", "1h"),
            "initial_capital": self.initial_capital,
            "leverage": strategy_config.get("leverage", 1),
            "commission": self.commission,
            **strategy_config,
        }

        def objective(trial: optuna.Trial) -> float:
            """Objective function for Optuna."""
            # Suggest parameters
            params = {}
            for param_name, param_spec in param_space.items():
                value = self._suggest_param(trial, param_name, param_spec)
                if value is not None:
                    params[param_name] = value

            # Merge with base config
            config = {**base_config, **params}

            try:
                # Run backtest
                result = engine.run_backtest(
                    df=self.data.copy(),
                    config=config,
                )

                if result is None:
                    return float("-inf") if direction == "maximize" else float("inf")

                # Extract metric
                metrics = result.get("metrics", result)
                value = metrics.get(metric, 0)

                if value is None or np.isnan(value) or np.isinf(value):
                    return float("-inf") if direction == "maximize" else float("inf")

                return float(value)

            except Exception as e:
                logger.warning(f"Trial failed: {e}")
                return float("-inf") if direction == "maximize" else float("inf")

        # Create study
        self.study = optuna.create_study(
            direction=direction,
            sampler=self._create_sampler(),
            study_name=f"bayesian_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )

        # Progress callback
        completed_trials = [0]

        def progress_callback(study: optuna.Study, trial: optuna.trial.FrozenTrial):
            completed_trials[0] += 1
            if show_progress and completed_trials[0] % 10 == 0:
                best = study.best_value if study.best_trial else None
                logger.info(
                    f"🔄 Trial {completed_trials[0]}/{self.n_trials}, "
                    f"best {metric}={best:.4f}"
                    if best
                    else ""
                )

        # Run optimization
        self.study.optimize(
            objective,
            n_trials=self.n_trials,
            n_jobs=self.n_jobs,
            callbacks=[progress_callback] if show_progress else None,
            show_progress_bar=False,
        )

        # Extract results
        self._best_params = self.study.best_params
        self._best_value = self.study.best_value

        # Get top trials
        top_trials = sorted(
            [
                t
                for t in self.study.trials
                if t.state == optuna.trial.TrialState.COMPLETE
            ],
            key=lambda t: t.value if direction == "maximize" else -t.value,
            reverse=True,
        )[:10]

        return {
            "best_params": self._best_params,
            "best_value": self._best_value,
            "best_trial_number": self.study.best_trial.number,
            "top_results": [
                {
                    "trial": t.number,
                    "params": t.params,
                    "value": t.value,
                }
                for t in top_trials
            ],
            "statistics": {
                "completed_trials": len(
                    [
                        t
                        for t in self.study.trials
                        if t.state == optuna.trial.TrialState.COMPLETE
                    ]
                ),
                "failed_trials": len(
                    [
                        t
                        for t in self.study.trials
                        if t.state == optuna.trial.TrialState.FAIL
                    ]
                ),
                "pruned_trials": len(
                    [
                        t
                        for t in self.study.trials
                        if t.state == optuna.trial.TrialState.PRUNED
                    ]
                ),
                "total_trials": len(self.study.trials),
            },
        }

    def get_importance(self) -> Dict[str, float]:
        """
        Calculate parameter importance using Optuna's built-in evaluator.

        Returns:
            Dictionary of parameter names to importance scores (0-1)
        """
        if self.study is None:
            return {}

        try:
            importance = optuna.importance.get_param_importances(self.study)
            return dict(importance)
        except Exception as e:
            logger.warning(f"Could not calculate param importance: {e}")
            return {}

    @property
    def best_params(self) -> Optional[Dict[str, Any]]:
        """Get best parameters found."""
        return self._best_params

    @property
    def best_value(self) -> Optional[float]:
        """Get best metric value found."""
        return self._best_value


def generate_param_range(
    low: float,
    high: float,
    step: float = 0.01,
    param_type: str = "float",
    precision: Optional[int] = None,
) -> List[Any]:
    """
    Generate parameter values for grid search.

    Supports:
    - Negative ranges (low=-50, high=50)
    - Fractional steps (0.01, 0.001)
    - High precision

    Args:
        low: Minimum value
        high: Maximum value
        step: Step size
        param_type: "int" or "float"
        precision: Decimal places for rounding

    Returns:
        List of parameter values
    """
    if precision is None:
        if step >= 1:
            precision = 0
        else:
            step_str = f"{step:.10f}".rstrip("0")
            precision = len(step_str.split(".")[-1]) if "." in step_str else 2

    values = []
    val = low

    while val <= high + step * 0.001:
        if param_type == "int":
            values.append(int(round(val)))
        else:
            values.append(round(val, precision) if precision > 0 else round(val))
        val += step

        if len(values) >= 10000:
            logger.warning("Range truncated to 10000 values")
            break

    # Remove duplicates
    return list(dict.fromkeys(values))
