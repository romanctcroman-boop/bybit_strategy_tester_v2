"""
A/B Testing Framework for Trading Strategies

Provides infrastructure for running controlled experiments on trading strategies,
comparing performance metrics, and making data-driven decisions.

Features:
- Experiment definition and management
- Traffic splitting (by user, symbol, time)
- Statistical significance testing
- Automatic winner detection
- Metrics collection and reporting
"""

import hashlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy import stats


class ExperimentStatus(str, Enum):
    """Experiment lifecycle states."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AllocationStrategy(str, Enum):
    """How to allocate traffic between variants."""

    RANDOM = "random"  # Pure random allocation
    DETERMINISTIC = "deterministic"  # Hash-based, consistent allocation
    TIME_BASED = "time_based"  # Alternate by time windows
    SYMBOL_BASED = "symbol_based"  # Split by trading symbols


class MetricType(str, Enum):
    """Types of metrics to track."""

    CONTINUOUS = "continuous"  # e.g., PnL, Sharpe ratio
    BINARY = "binary"  # e.g., win/loss
    COUNT = "count"  # e.g., number of trades
    RATIO = "ratio"  # e.g., win rate


@dataclass
class Variant:
    """Represents a variant in an A/B test."""

    name: str
    weight: float = 0.5  # Traffic allocation weight
    config: Dict[str, Any] = field(default_factory=dict)
    is_control: bool = False

    # Runtime metrics
    samples: int = 0
    metrics: Dict[str, List[float]] = field(default_factory=dict)

    def add_metric(self, name: str, value: float) -> None:
        """Record a metric value for this variant."""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)
        self.samples += 1

    def get_metric_stats(self, name: str) -> Dict[str, float]:
        """Get statistical summary for a metric."""
        if name not in self.metrics or not self.metrics[name]:
            return {"mean": 0, "std": 0, "count": 0}

        values = np.array(self.metrics[name])
        return {
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "median": float(np.median(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "count": len(values),
            "sum": float(np.sum(values)),
        }


@dataclass
class ExperimentConfig:
    """Configuration for an A/B experiment."""

    name: str
    description: str = ""

    # Variants
    variants: List[Variant] = field(default_factory=list)

    # Allocation
    allocation_strategy: AllocationStrategy = AllocationStrategy.DETERMINISTIC

    # Duration
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    min_samples_per_variant: int = 100

    # Statistical settings
    confidence_level: float = 0.95  # 95% confidence
    minimum_detectable_effect: float = 0.05  # 5% MDE

    # Primary metric for decision
    primary_metric: str = "pnl"

    # Guardrail metrics (experiment stops if violated)
    guardrail_metrics: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    # Targeting
    target_symbols: Optional[Set[str]] = None
    target_users: Optional[Set[str]] = None


@dataclass
class ExperimentResult:
    """Results of a completed experiment."""

    experiment_id: str
    status: ExperimentStatus
    winner: Optional[str] = None
    confidence: float = 0.0
    p_value: float = 1.0
    effect_size: float = 0.0

    variant_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    duration: Optional[timedelta] = None
    total_samples: int = 0

    recommendation: str = ""
    warnings: List[str] = field(default_factory=list)


class StatisticalAnalyzer:
    """Performs statistical analysis on experiment data."""

    @staticmethod
    def t_test(
        control_values: List[float],
        treatment_values: List[float],
        alternative: str = "two-sided",
    ) -> Tuple[float, float]:
        """
        Perform Welch's t-test for independent samples.

        Returns:
            (t_statistic, p_value)
        """
        if len(control_values) < 2 or len(treatment_values) < 2:
            return 0.0, 1.0

        t_stat, p_value = stats.ttest_ind(
            control_values, treatment_values, equal_var=False, alternative=alternative
        )
        return float(t_stat), float(p_value)

    @staticmethod
    def mann_whitney_u(
        control_values: List[float],
        treatment_values: List[float],
        alternative: str = "two-sided",
    ) -> Tuple[float, float]:
        """
        Perform Mann-Whitney U test (non-parametric).

        Returns:
            (u_statistic, p_value)
        """
        if len(control_values) < 2 or len(treatment_values) < 2:
            return 0.0, 1.0

        u_stat, p_value = stats.mannwhitneyu(
            control_values, treatment_values, alternative=alternative
        )
        return float(u_stat), float(p_value)

    @staticmethod
    def chi_squared_test(
        control_successes: int,
        control_total: int,
        treatment_successes: int,
        treatment_total: int,
    ) -> Tuple[float, float]:
        """
        Perform chi-squared test for binary outcomes.

        Returns:
            (chi2_statistic, p_value)
        """
        observed = np.array(
            [
                [control_successes, control_total - control_successes],
                [treatment_successes, treatment_total - treatment_successes],
            ]
        )

        if observed.min() < 5:
            # Use Fisher's exact test for small samples
            _, p_value = stats.fisher_exact(observed)
            return 0.0, float(p_value)

        chi2, p_value, _, _ = stats.chi2_contingency(observed)
        return float(chi2), float(p_value)

    @staticmethod
    def calculate_effect_size(
        control_values: List[float], treatment_values: List[float]
    ) -> float:
        """Calculate Cohen's d effect size."""
        if len(control_values) < 2 or len(treatment_values) < 2:
            return 0.0

        control_mean = np.mean(control_values)
        treatment_mean = np.mean(treatment_values)

        pooled_std = np.sqrt((np.var(control_values) + np.var(treatment_values)) / 2)

        if pooled_std == 0:
            return 0.0

        return float((treatment_mean - control_mean) / pooled_std)

    @staticmethod
    def calculate_relative_uplift(control_mean: float, treatment_mean: float) -> float:
        """Calculate relative improvement percentage."""
        if control_mean == 0:
            return 0.0 if treatment_mean == 0 else float("inf")
        return (treatment_mean - control_mean) / abs(control_mean) * 100

    @staticmethod
    def required_sample_size(
        baseline_mean: float,
        baseline_std: float,
        minimum_detectable_effect: float,
        alpha: float = 0.05,
        power: float = 0.8,
    ) -> int:
        """
        Calculate required sample size per variant.

        Uses the formula for two-sample t-test.
        """
        from scipy.stats import norm

        z_alpha = norm.ppf(1 - alpha / 2)
        z_beta = norm.ppf(power)

        effect = baseline_mean * minimum_detectable_effect

        if effect == 0 or baseline_std == 0:
            return 1000  # Default fallback

        n = 2 * ((z_alpha + z_beta) ** 2) * (baseline_std**2) / (effect**2)
        return int(np.ceil(n))


class ABExperiment:
    """Manages a single A/B experiment."""

    def __init__(self, config: ExperimentConfig):
        self.id = str(uuid.uuid4())
        self.config = config
        self.status = ExperimentStatus.DRAFT
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None

        # Validate config
        self._validate_config()

        # Initialize variants
        self._normalize_weights()

        # Analyzer
        self.analyzer = StatisticalAnalyzer()

    def _validate_config(self) -> None:
        """Validate experiment configuration."""
        if len(self.config.variants) < 2:
            raise ValueError("Experiment must have at least 2 variants")

        control_count = sum(1 for v in self.config.variants if v.is_control)
        if control_count != 1:
            raise ValueError("Experiment must have exactly 1 control variant")

        if self.config.confidence_level <= 0 or self.config.confidence_level >= 1:
            raise ValueError("Confidence level must be between 0 and 1")

    def _normalize_weights(self) -> None:
        """Normalize variant weights to sum to 1."""
        total = sum(v.weight for v in self.config.variants)
        if total > 0:
            for v in self.config.variants:
                v.weight /= total

    def start(self) -> None:
        """Start the experiment."""
        if self.status != ExperimentStatus.DRAFT:
            raise ValueError(f"Cannot start experiment in {self.status} state")

        self.status = ExperimentStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        self.config.start_time = self.started_at

    def pause(self) -> None:
        """Pause the experiment."""
        if self.status != ExperimentStatus.RUNNING:
            raise ValueError(f"Cannot pause experiment in {self.status} state")
        self.status = ExperimentStatus.PAUSED

    def resume(self) -> None:
        """Resume a paused experiment."""
        if self.status != ExperimentStatus.PAUSED:
            raise ValueError(f"Cannot resume experiment in {self.status} state")
        self.status = ExperimentStatus.RUNNING

    def stop(self) -> None:
        """Stop the experiment and calculate results."""
        if self.status not in [ExperimentStatus.RUNNING, ExperimentStatus.PAUSED]:
            raise ValueError(f"Cannot stop experiment in {self.status} state")

        self.status = ExperimentStatus.COMPLETED
        self.ended_at = datetime.now(timezone.utc)

    def cancel(self) -> None:
        """Cancel the experiment without results."""
        self.status = ExperimentStatus.CANCELLED
        self.ended_at = datetime.now(timezone.utc)

    def allocate(
        self,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> Variant:
        """
        Allocate a request to a variant.

        Returns the variant that should handle this request.
        """
        if self.status != ExperimentStatus.RUNNING:
            # Return control if not running
            return next(v for v in self.config.variants if v.is_control)

        # Check targeting
        if self.config.target_symbols and symbol not in self.config.target_symbols:
            return next(v for v in self.config.variants if v.is_control)

        if self.config.target_users and user_id not in self.config.target_users:
            return next(v for v in self.config.variants if v.is_control)

        # Allocate based on strategy
        if self.config.allocation_strategy == AllocationStrategy.RANDOM:
            return self._allocate_random()
        elif self.config.allocation_strategy == AllocationStrategy.DETERMINISTIC:
            return self._allocate_deterministic(user_id or symbol or str(uuid.uuid4()))
        elif self.config.allocation_strategy == AllocationStrategy.TIME_BASED:
            return self._allocate_time_based(timestamp or datetime.now(timezone.utc))
        elif self.config.allocation_strategy == AllocationStrategy.SYMBOL_BASED:
            return self._allocate_symbol_based(symbol or "default")

        return self._allocate_random()

    def _allocate_random(self) -> Variant:
        """Random allocation based on weights."""
        r = random.random()
        cumulative = 0.0
        for variant in self.config.variants:
            cumulative += variant.weight
            if r < cumulative:
                return variant
        return self.config.variants[-1]

    def _allocate_deterministic(self, key: str) -> Variant:
        """Hash-based deterministic allocation."""
        hash_value = (
            int(hashlib.md5(f"{self.id}:{key}".encode()).hexdigest(), 16) % 1000
        )

        cumulative = 0.0
        for variant in self.config.variants:
            cumulative += variant.weight * 1000
            if hash_value < cumulative:
                return variant
        return self.config.variants[-1]

    def _allocate_time_based(self, timestamp: datetime) -> Variant:
        """Allocate based on time windows (e.g., hourly rotation)."""
        hour = timestamp.hour
        idx = hour % len(self.config.variants)
        return self.config.variants[idx]

    def _allocate_symbol_based(self, symbol: str) -> Variant:
        """Allocate based on symbol hash."""
        return self._allocate_deterministic(symbol)

    def record_metric(self, variant_name: str, metric_name: str, value: float) -> None:
        """Record a metric value for a variant."""
        variant = next(
            (v for v in self.config.variants if v.name == variant_name), None
        )
        if variant:
            variant.add_metric(metric_name, value)

            # Check guardrails
            self._check_guardrails(variant, metric_name, value)

    def _check_guardrails(
        self, variant: Variant, metric_name: str, value: float
    ) -> None:
        """Check if guardrail metrics are violated."""
        if metric_name not in self.config.guardrail_metrics:
            return

        min_val, max_val = self.config.guardrail_metrics[metric_name]
        stats = variant.get_metric_stats(metric_name)

        if stats["mean"] < min_val or stats["mean"] > max_val:
            # Auto-pause experiment on guardrail violation
            self.pause()

    def get_results(self) -> ExperimentResult:
        """Calculate and return experiment results."""
        control = next(v for v in self.config.variants if v.is_control)
        treatments = [v for v in self.config.variants if not v.is_control]

        result = ExperimentResult(
            experiment_id=self.id,
            status=self.status,
            total_samples=sum(v.samples for v in self.config.variants),
            variant_stats={},
        )

        if self.started_at:
            result.duration = (
                self.ended_at or datetime.now(timezone.utc)
            ) - self.started_at

        # Get stats for all variants
        for variant in self.config.variants:
            result.variant_stats[variant.name] = {
                "samples": variant.samples,
                "is_control": variant.is_control,
                "metrics": {
                    name: variant.get_metric_stats(name) for name in variant.metrics
                },
            }

        # Statistical analysis against control
        primary = self.config.primary_metric
        control_values = control.metrics.get(primary, [])

        best_treatment = None
        best_p_value = 1.0
        best_effect = 0.0

        for treatment in treatments:
            treatment_values = treatment.metrics.get(primary, [])

            if len(control_values) < 10 or len(treatment_values) < 10:
                result.warnings.append(f"Insufficient samples for {treatment.name}")
                continue

            # Perform t-test
            _, p_value = self.analyzer.t_test(control_values, treatment_values)
            effect_size = self.analyzer.calculate_effect_size(
                control_values, treatment_values
            )

            if p_value < best_p_value and effect_size > 0:
                best_treatment = treatment.name
                best_p_value = p_value
                best_effect = effect_size

        # Determine winner
        alpha = 1 - self.config.confidence_level
        if best_p_value < alpha and best_treatment:
            result.winner = best_treatment
            result.confidence = 1 - best_p_value
            result.p_value = best_p_value
            result.effect_size = best_effect

            control_mean = np.mean(control_values) if control_values else 0
            treatment_mean = result.variant_stats[best_treatment]["metrics"][primary][
                "mean"
            ]
            uplift = self.analyzer.calculate_relative_uplift(
                control_mean, treatment_mean
            )

            result.recommendation = (
                f"Winner: {best_treatment} with {uplift:.1f}% improvement "
                f"(p={best_p_value:.4f}, effect size={best_effect:.2f})"
            )
        else:
            result.recommendation = (
                "No statistically significant winner detected. "
                "Consider running longer or increasing sample size."
            )

        return result


class ExperimentManager:
    """
    Manages multiple A/B experiments.

    Provides:
    - Experiment lifecycle management
    - Conflict detection (overlapping experiments)
    - Central metrics recording
    - Reporting and dashboards
    """

    def __init__(self):
        self.experiments: Dict[str, ABExperiment] = {}
        self._active_by_symbol: Dict[str, List[str]] = {}  # symbol -> experiment_ids

    def create_experiment(self, config: ExperimentConfig) -> ABExperiment:
        """Create a new experiment."""
        experiment = ABExperiment(config)
        self.experiments[experiment.id] = experiment
        return experiment

    def start_experiment(self, experiment_id: str) -> None:
        """Start an experiment."""
        exp = self.experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Check for conflicts
        self._check_conflicts(exp)

        exp.start()

        # Track by symbol
        if exp.config.target_symbols:
            for symbol in exp.config.target_symbols:
                if symbol not in self._active_by_symbol:
                    self._active_by_symbol[symbol] = []
                self._active_by_symbol[symbol].append(experiment_id)

    def _check_conflicts(self, experiment: ABExperiment) -> None:
        """Check for conflicting active experiments."""
        if not experiment.config.target_symbols:
            return

        for symbol in experiment.config.target_symbols:
            active = self._active_by_symbol.get(symbol, [])
            for exp_id in active:
                other = self.experiments.get(exp_id)
                if other and other.status == ExperimentStatus.RUNNING:
                    raise ValueError(
                        f"Symbol {symbol} already has active experiment: {exp_id}"
                    )

    def stop_experiment(self, experiment_id: str) -> ExperimentResult:
        """Stop an experiment and get results."""
        exp = self.experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        exp.stop()

        # Clean up tracking
        if exp.config.target_symbols:
            for symbol in exp.config.target_symbols:
                if symbol in self._active_by_symbol:
                    self._active_by_symbol[symbol] = [
                        eid
                        for eid in self._active_by_symbol[symbol]
                        if eid != experiment_id
                    ]

        return exp.get_results()

    def get_variant_for_request(
        self, symbol: str, user_id: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[Variant]]:
        """
        Get the variant for a trading request.

        Returns:
            (experiment_id, variant) or (None, None) if no active experiment
        """
        active_exp_ids = self._active_by_symbol.get(symbol, [])

        for exp_id in active_exp_ids:
            exp = self.experiments.get(exp_id)
            if exp and exp.status == ExperimentStatus.RUNNING:
                variant = exp.allocate(user_id=user_id, symbol=symbol)
                return exp_id, variant

        return None, None

    def record_trade_result(
        self,
        experiment_id: str,
        variant_name: str,
        pnl: float,
        win: bool,
        metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """Record trading metrics for an experiment variant."""
        exp = self.experiments.get(experiment_id)
        if not exp:
            return

        exp.record_metric(variant_name, "pnl", pnl)
        exp.record_metric(variant_name, "win", 1.0 if win else 0.0)

        if metrics:
            for name, value in metrics.items():
                exp.record_metric(variant_name, name, value)

    def list_experiments(
        self, status: Optional[ExperimentStatus] = None
    ) -> List[Dict[str, Any]]:
        """List all experiments, optionally filtered by status."""
        results = []
        for exp in self.experiments.values():
            if status and exp.status != status:
                continue

            results.append(
                {
                    "id": exp.id,
                    "name": exp.config.name,
                    "status": exp.status.value,
                    "variants": [v.name for v in exp.config.variants],
                    "total_samples": sum(v.samples for v in exp.config.variants),
                    "created_at": exp.created_at.isoformat(),
                    "started_at": exp.started_at.isoformat()
                    if exp.started_at
                    else None,
                }
            )

        return results

    def get_dashboard_data(self, experiment_id: str) -> Dict[str, Any]:
        """Get real-time dashboard data for an experiment."""
        exp = self.experiments.get(experiment_id)
        if not exp:
            return {}

        results = exp.get_results()

        return {
            "experiment_id": exp.id,
            "name": exp.config.name,
            "status": exp.status.value,
            "duration_seconds": results.duration.total_seconds()
            if results.duration
            else 0,
            "total_samples": results.total_samples,
            "variants": [
                {
                    "name": v.name,
                    "is_control": v.is_control,
                    "samples": v.samples,
                    "metrics": {name: v.get_metric_stats(name) for name in v.metrics},
                }
                for v in exp.config.variants
            ],
            "winner": results.winner,
            "confidence": results.confidence,
            "p_value": results.p_value,
            "recommendation": results.recommendation,
            "warnings": results.warnings,
        }


# Singleton instance
_experiment_manager: Optional[ExperimentManager] = None


def get_experiment_manager() -> ExperimentManager:
    """Get the global experiment manager instance."""
    global _experiment_manager
    if _experiment_manager is None:
        _experiment_manager = ExperimentManager()
    return _experiment_manager


# Example usage and factory functions
def create_strategy_ab_test(
    name: str,
    control_config: Dict[str, Any],
    treatment_config: Dict[str, Any],
    target_symbols: Optional[List[str]] = None,
    traffic_split: float = 0.5,
) -> ABExperiment:
    """
    Factory function to create a strategy A/B test.

    Args:
        name: Experiment name
        control_config: Configuration for control (current) strategy
        treatment_config: Configuration for treatment (new) strategy
        target_symbols: List of symbols to include in test
        traffic_split: Percentage of traffic for treatment (0-1)

    Returns:
        Configured ABExperiment ready to start
    """
    config = ExperimentConfig(
        name=name,
        description="A/B test comparing strategy configurations",
        variants=[
            Variant(
                name="control",
                weight=1 - traffic_split,
                config=control_config,
                is_control=True,
            ),
            Variant(
                name="treatment",
                weight=traffic_split,
                config=treatment_config,
                is_control=False,
            ),
        ],
        allocation_strategy=AllocationStrategy.DETERMINISTIC,
        min_samples_per_variant=100,
        confidence_level=0.95,
        primary_metric="pnl",
        guardrail_metrics={
            "max_drawdown": (-0.2, 0.0),  # Max 20% drawdown
        },
        target_symbols=set(target_symbols) if target_symbols else None,
    )

    manager = get_experiment_manager()
    return manager.create_experiment(config)
