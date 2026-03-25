"""
MLflow Integration for Backtest Tracking.

This module integrates MLflow experiment tracking into the backtest workflow.
It logs backtest parameters, metrics, and artifacts for analysis and reproducibility.

Usage:
    from backend.backtesting.mlflow_tracking import BacktestTracker

    tracker = BacktestTracker(experiment_name="backtest-optimization")

    with tracker.track_backtest(config) as run:
        result = engine.run(config, ohlcv)
        tracker.log_result(result)
"""

from __future__ import annotations

import json
import logging
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.backtesting.models import BacktestConfig, BacktestResult

logger = logging.getLogger(__name__)

# Import MLflow adapter
try:
    from backend.ml.mlflow_adapter import MLflowAdapter

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    MLflowAdapter = None  # type: ignore


class BacktestTracker:
    """
    MLflow-based backtest tracking for experiment management.

    Features:
    - Automatic experiment creation
    - Parameter logging (strategy, symbol, dates, etc.)
    - Metric logging (returns, Sharpe, drawdown, etc.)
    - Artifact logging (equity curves, trade logs)
    - Run comparison and analysis
    """

    def __init__(
        self,
        experiment_name: str = "backtest-experiments",
        tracking_uri: str | None = None,
        auto_log: bool = True,
    ):
        """
        Initialize backtest tracker.

        Args:
            experiment_name: MLflow experiment name
            tracking_uri: MLflow tracking server URI (defaults to localhost:5000)
            auto_log: Whether to automatically log metrics after backtest
        """
        self.experiment_name = experiment_name
        self.auto_log = auto_log
        self._current_run = None
        self._run_id = None

        # Initialize MLflow adapter
        if MLFLOW_AVAILABLE:
            self.adapter = MLflowAdapter(tracking_uri=tracking_uri)
            if self.adapter.is_available:
                self.adapter.set_experiment(experiment_name)
                logger.info(f"MLflow tracking enabled: experiment='{experiment_name}'")
            else:
                logger.warning("MLflow server not available, tracking disabled")
        else:
            self.adapter = None
            logger.warning("MLflow not installed, tracking disabled")

    @property
    def is_available(self) -> bool:
        """Check if MLflow tracking is available."""
        return self.adapter is not None and self.adapter.is_available

    @contextmanager
    def track_backtest(self, config: BacktestConfig, run_name: str | None = None):
        """
        Context manager for tracking a backtest run.

        Args:
            config: Backtest configuration
            run_name: Optional name for the run

        Yields:
            Run ID if MLflow available, None otherwise

        Example:
            with tracker.track_backtest(config) as run_id:
                result = engine.run(config, data)
                tracker.log_result(result)
        """
        if not self.is_available:
            yield None
            return

        # Generate run name if not provided
        if run_name is None:
            run_name = self._generate_run_name(config)

        try:
            # Start MLflow run
            self._run_id = self.adapter.start_run(run_name=run_name)
            self._current_run = True

            # Log configuration as parameters
            self._log_config_params(config)

            yield self._run_id

        except Exception as e:
            logger.error(f"Error in MLflow tracking: {e}")
            yield None

        finally:
            # End run
            if self._current_run:
                self.adapter.end_run()
                self._current_run = None
                self._run_id = None

    def log_result(self, result: BacktestResult) -> bool:
        """
        Log backtest result metrics and artifacts.

        Args:
            result: Backtest result object

        Returns:
            True if logging successful, False otherwise
        """
        if not self.is_available or not self._current_run:
            return False

        try:
            # Log performance metrics
            self._log_metrics(result)

            # Log artifacts (equity curve, trade log)
            self._log_artifacts(result)

            logger.info(f"Logged backtest result: run_id={self._run_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to log backtest result: {e}")
            return False

    def _generate_run_name(self, config: BacktestConfig) -> str:
        """Generate a descriptive run name from config."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{config.symbol}_{config.strategy_type}_{config.interval}_{timestamp}"

    def _log_config_params(self, config: BacktestConfig) -> None:
        """Log backtest configuration as MLflow parameters."""
        params = {
            # Strategy params
            "symbol": config.symbol,
            "interval": config.interval,
            "strategy_type": config.strategy_type,
            # Date range
            "start_date": str(config.start_date),
            "end_date": str(config.end_date),
            # Capital & leverage
            "initial_capital": config.initial_capital,
            "leverage": getattr(config, "leverage", 1),
            # Risk management
            "stop_loss": getattr(config, "stop_loss", None),
            "take_profit": getattr(config, "take_profit", None),
            "trailing_stop": getattr(config, "trailing_stop_activation", None),
            # Direction
            "direction": getattr(config, "direction", "both"),
            # Commission
            "commission_rate": getattr(config, "commission_rate", 0.0007),
        }

        # Add strategy-specific params
        if config.strategy_params:
            for key, value in config.strategy_params.items():
                params[f"strategy_{key}"] = value

        # Filter out None values
        params = {k: v for k, v in params.items() if v is not None}

        self.adapter.log_params(params)

    def _log_metrics(self, result: BacktestResult) -> None:
        """Log performance metrics from backtest result."""
        metrics = result.metrics
        if metrics is None:
            return

        # Core performance metrics
        metric_values = {
            # Returns
            "total_return": metrics.total_return,
            "net_profit": metrics.net_profit,
            "total_return_pct": metrics.total_return_pct,
            # Risk metrics
            "sharpe_ratio": metrics.sharpe_ratio,
            "sortino_ratio": metrics.sortino_ratio,
            "calmar_ratio": metrics.calmar_ratio,
            "max_drawdown": metrics.max_drawdown,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            # Trade statistics
            "total_trades": metrics.total_trades,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "win_rate": metrics.win_rate,
            "profit_factor": metrics.profit_factor,
            # Average trade metrics
            "avg_trade": metrics.avg_trade,
            "avg_winning_trade": metrics.avg_winning_trade,
            "avg_losing_trade": metrics.avg_losing_trade,
            # Risk-adjusted
            "expectancy": metrics.expectancy,
            "payoff_ratio": metrics.payoff_ratio,
        }

        # Filter out None and NaN values
        metric_values = {
            k: v
            for k, v in metric_values.items()
            if v is not None and not (isinstance(v, float) and (v != v))  # NaN check
        }

        self.adapter.log_metrics(metric_values)

    def _log_artifacts(self, result: BacktestResult) -> None:
        """Log artifacts (equity curve, trades) from backtest result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Log equity curve as CSV
            if result.equity_curve:
                equity_data = [
                    {
                        "timestamp": str(p.timestamp),
                        "equity": p.equity,
                        "drawdown": p.drawdown,
                        "drawdown_pct": p.drawdown_pct,
                    }
                    for p in result.equity_curve
                ]
                equity_file = tmppath / "equity_curve.json"
                equity_file.write_text(json.dumps(equity_data, indent=2))
                self.adapter.log_artifact(str(equity_file))

            # Log trades as JSON
            if result.trades:
                trades_data = [
                    {
                        "id": t.id,
                        "entry_time": str(t.entry_time),
                        "exit_time": str(t.exit_time) if t.exit_time else None,
                        "side": t.side.value if hasattr(t.side, "value") else str(t.side),
                        "entry_price": t.entry_price,
                        "exit_price": t.exit_price,
                        "size": t.size,
                        "pnl": t.pnl,
                        "pnl_pct": t.pnl_pct,
                        "commission": t.commission,
                    }
                    for t in result.trades
                ]
                trades_file = tmppath / "trades.json"
                trades_file.write_text(json.dumps(trades_data, indent=2))
                self.adapter.log_artifact(str(trades_file))

            # Log summary as JSON
            summary = {
                "backtest_id": result.id,
                "symbol": result.config.symbol if result.config else "N/A",
                "strategy": result.config.strategy_type if result.config else "N/A",
                "status": str(result.status),
                "created_at": str(result.created_at),
                "completed_at": str(result.completed_at),
                "total_trades": len(result.trades) if result.trades else 0,
            }
            summary_file = tmppath / "summary.json"
            summary_file.write_text(json.dumps(summary, indent=2))
            self.adapter.log_artifact(str(summary_file))

    def log_optimization_result(
        self,
        best_params: dict[str, Any],
        best_metrics: dict[str, float],
        all_results: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        Log optimization results (best parameters and metrics).

        Args:
            best_params: Best parameter combination found
            best_metrics: Metrics for best parameters
            all_results: Optional list of all parameter combinations tested

        Returns:
            True if logging successful
        """
        if not self.is_available or not self._current_run:
            return False

        try:
            # Log best params with "best_" prefix
            best_params_prefixed = {f"best_{k}": v for k, v in best_params.items()}
            self.adapter.log_params(best_params_prefixed)

            # Log best metrics with "best_" prefix
            best_metrics_prefixed = {f"best_{k}": v for k, v in best_metrics.items()}
            self.adapter.log_metrics(best_metrics_prefixed)

            # Log all results as artifact
            if all_results:
                with tempfile.TemporaryDirectory() as tmpdir:
                    results_file = Path(tmpdir) / "optimization_results.json"
                    results_file.write_text(json.dumps(all_results, indent=2))
                    self.adapter.log_artifact(str(results_file))

            return True

        except Exception as e:
            logger.error(f"Failed to log optimization result: {e}")
            return False


# Global tracker instance (lazy initialization)
_global_tracker: BacktestTracker | None = None


def get_tracker(experiment_name: str = "backtest-experiments") -> BacktestTracker:
    """
    Get or create global backtest tracker.

    Args:
        experiment_name: MLflow experiment name

    Returns:
        BacktestTracker instance
    """
    global _global_tracker

    if _global_tracker is None:
        _global_tracker = BacktestTracker(experiment_name=experiment_name)

    return _global_tracker


def track_backtest(config: BacktestConfig, run_name: str | None = None):
    """
    Convenience function to track a backtest.

    Args:
        config: Backtest configuration
        run_name: Optional run name

    Returns:
        Context manager for tracking

    Example:
        with track_backtest(config) as run_id:
            result = engine.run(config, data)
            get_tracker().log_result(result)
    """
    return get_tracker().track_backtest(config, run_name)
