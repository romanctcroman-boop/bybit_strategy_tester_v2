"""
Reasoning A/B Testing Harness
Provides A/B testing framework for comparing different reasoning strategies.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ABTestConfig:
    """
    Configuration for A/B testing of reasoning strategies.

    Attributes:
        test_name: Name of the A/B test
        variant_a: Configuration for variant A
        variant_b: Configuration for variant B
        traffic_split: Percentage of traffic to variant B (0-100)
        metrics: Metrics to track
        duration_hours: Test duration in hours
    """

    test_name: str
    variant_a: dict[str, Any]
    variant_b: dict[str, Any]
    traffic_split: float = 50.0
    metrics: list[str] = field(default_factory=lambda: ["accuracy", "latency", "cost"])
    duration_hours: int = 24
    min_sample_size: int = 100

    def __post_init__(self):
        """Validate configuration"""
        if not 0 <= self.traffic_split <= 100:
            raise ValueError("traffic_split must be between 0 and 100")
        if self.duration_hours <= 0:
            raise ValueError("duration_hours must be positive")


@dataclass
class ABTestResult:
    """
    Results from an A/B test.

    Attributes:
        test_name: Name of the test
        variant_a_metrics: Metrics for variant A
        variant_b_metrics: Metrics for variant B
        winner: Winning variant ('A', 'B', or 'tie')
        confidence: Statistical confidence level
        sample_size_a: Sample size for variant A
        sample_size_b: Sample size for variant B
    """

    test_name: str
    variant_a_metrics: dict[str, float]
    variant_b_metrics: dict[str, float]
    winner: str
    confidence: float
    sample_size_a: int
    sample_size_b: int
    started_at: datetime
    completed_at: datetime


class ReasoningABHarness:
    """
    A/B testing harness for reasoning strategies.

    Manages A/B tests, traffic routing, and results analysis.
    """

    def __init__(self):
        """Initialize A/B testing harness"""
        self._active_tests: dict[str, ABTestConfig] = {}
        self._results: dict[str, list[dict[str, Any]]] = {}
        logger.info("Reasoning A/B Harness initialized")

    def start_test(self, config: ABTestConfig) -> str:
        """
        Start a new A/B test.

        Args:
            config: A/B test configuration

        Returns:
            Test ID
        """
        test_id = (
            f"abtest_{config.test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self._active_tests[test_id] = config
        self._results[test_id] = []

        logger.info(f"Started A/B test: {test_id}")
        logger.info(f"  Traffic split: {config.traffic_split}% to variant B")
        logger.info(f"  Duration: {config.duration_hours} hours")
        logger.info(f"  Metrics: {', '.join(config.metrics)}")

        return test_id

    def route_request(self, test_id: str) -> str:
        """
        Route a request to variant A or B based on traffic split.

        Args:
            test_id: Test ID

        Returns:
            Variant name ('A' or 'B')
        """
        import random

        if test_id not in self._active_tests:
            raise ValueError(f"Test {test_id} not found")

        config = self._active_tests[test_id]

        # Route based on traffic split
        if random.random() * 100 < config.traffic_split:
            return "B"
        return "A"

    def record_result(
        self,
        test_id: str,
        variant: str,
        metrics: dict[str, float],
        metadata: dict[str, Any] | None = None,
    ):
        """
        Record results for a test request.

        Args:
            test_id: Test ID
            variant: Variant name ('A' or 'B')
            metrics: Measured metrics
            metadata: Additional metadata
        """
        if test_id not in self._results:
            self._results[test_id] = []

        result = {
            "variant": variant,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        self._results[test_id].append(result)
        logger.debug(f"Recorded result for {test_id}, variant {variant}")

    def get_results(self, test_id: str) -> ABTestResult:
        """
        Get results for an A/B test.

        Args:
            test_id: Test ID

        Returns:
            AB test results
        """
        if test_id not in self._active_tests:
            raise ValueError(f"Test {test_id} not found")

        config = self._active_tests[test_id]
        results = self._results.get(test_id, [])

        # Separate results by variant
        variant_a_results = [r for r in results if r["variant"] == "A"]
        variant_b_results = [r for r in results if r["variant"] == "B"]

        # Calculate aggregate metrics
        variant_a_metrics = self._aggregate_metrics(variant_a_results)
        variant_b_metrics = self._aggregate_metrics(variant_b_results)

        # Determine winner (simplified - just compare first metric)
        winner = "tie"
        confidence = 0.0

        if variant_a_metrics and variant_b_metrics and config.metrics:
            primary_metric = config.metrics[0]
            a_value = variant_a_metrics.get(primary_metric, 0)
            b_value = variant_b_metrics.get(primary_metric, 0)

            if a_value > b_value * 1.05:  # 5% threshold
                winner = "A"
                confidence = 0.95
            elif b_value > a_value * 1.05:
                winner = "B"
                confidence = 0.95

        return ABTestResult(
            test_name=config.test_name,
            variant_a_metrics=variant_a_metrics,
            variant_b_metrics=variant_b_metrics,
            winner=winner,
            confidence=confidence,
            sample_size_a=len(variant_a_results),
            sample_size_b=len(variant_b_results),
            started_at=datetime.now(),  # Simplified
            completed_at=datetime.now(),
        )

    def _aggregate_metrics(self, results: list[dict[str, Any]]) -> dict[str, float]:
        """
        Aggregate metrics from multiple results.

        Args:
            results: List of result dictionaries

        Returns:
            Aggregated metrics
        """
        if not results:
            return {}

        # Get all metric keys
        metric_keys = set()
        for result in results:
            metric_keys.update(result.get("metrics", {}).keys())

        # Calculate averages
        aggregated = {}
        for key in metric_keys:
            values = [
                r["metrics"].get(key, 0) for r in results if key in r.get("metrics", {})
            ]
            if values:
                aggregated[key] = sum(values) / len(values)

        return aggregated

    def stop_test(self, test_id: str) -> ABTestResult:
        """
        Stop an active A/B test and return results.

        Args:
            test_id: Test ID

        Returns:
            Final test results
        """
        results = self.get_results(test_id)

        # Remove from active tests
        if test_id in self._active_tests:
            del self._active_tests[test_id]

        logger.info(f"Stopped A/B test: {test_id}")
        logger.info(
            f"  Winner: {results.winner} (confidence: {results.confidence:.2%})"
        )
        logger.info(
            f"  Sample sizes: A={results.sample_size_a}, B={results.sample_size_b}"
        )

        return results

    def list_active_tests(self) -> list[str]:
        """
        List all active test IDs.

        Returns:
            List of test IDs
        """
        return list(self._active_tests.keys())


# Alias for tests
ReasoningHarness = ReasoningABHarness


__all__ = ["ABTestConfig", "ABTestResult", "ReasoningABHarness", "ReasoningHarness"]
