"""
Performance Benchmark Suite

Comprehensive performance testing for AI agent system:
- Response time benchmarks
- Throughput testing
- Load testing
- Bottleneck detection
- Performance regression detection

Usage:
    from backend.benchmarking import BenchmarkSuite
    suite = BenchmarkSuite()
    results = suite.run_benchmarks()
    report = suite.generate_report(results)
"""

from __future__ import annotations

import asyncio
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger


@dataclass
class BenchmarkResult:
    """Result of a single benchmark."""

    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    median_time: float
    std_dev: float
    p95_time: float
    p99_time: float
    success_rate: float
    errors: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time": self.total_time,
            "avg_time": self.avg_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "median_time": self.median_time,
            "std_dev": self.std_dev,
            "p95_time": self.p95_time,
            "p99_time": self.p99_time,
            "success_rate": self.success_rate,
            "errors": self.errors,
            "metadata": self.metadata,
        }


@dataclass
class LoadTestResult:
    """Result of load testing."""

    concurrent_users: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    error_rate: float
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "concurrent_users": self.concurrent_users,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "requests_per_second": self.requests_per_second,
            "avg_response_time": self.avg_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "error_rate": self.error_rate,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class BenchmarkReport:
    """Comprehensive benchmark report."""

    timestamp: str
    total_benchmarks: int
    passed_benchmarks: int
    failed_benchmarks: int
    results: list[BenchmarkResult] = field(default_factory=list)
    load_tests: list[LoadTestResult] = field(default_factory=list)
    bottlenecks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "timestamp": self.timestamp,
            "total_benchmarks": self.total_benchmarks,
            "passed_benchmarks": self.passed_benchmarks,
            "failed_benchmarks": self.failed_benchmarks,
            "results": [r.to_dict() for r in self.results],
            "load_tests": [lt.to_dict() for lt in self.load_tests],
            "bottlenecks": self.bottlenecks,
            "recommendations": self.recommendations,
        }


class BenchmarkSuite:
    """
    Comprehensive performance benchmark suite.

    Features:
    - Response time benchmarks
    - Throughput testing
    - Load testing
    - Bottleneck detection
    - Performance regression detection
    - Detailed reporting

    Example:
        suite = BenchmarkSuite()
        results = suite.run_benchmarks()
        report = suite.generate_report(results)
    """

    def __init__(self):
        """Initialize benchmark suite."""
        self._results: list[BenchmarkResult] = []
        self._load_test_results: list[LoadTestResult] = []
        self._baseline_results: dict[str, BenchmarkResult] = {}

        logger.info("🏁 BenchmarkSuite initialized")

    async def run_benchmark(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        warmup_iterations: int = 10,
        **kwargs,
    ) -> BenchmarkResult:
        """
        Run a benchmark.

        Args:
            name: Benchmark name
            func: Function to benchmark
            iterations: Number of iterations
            warmup_iterations: Warmup iterations
            **kwargs: Arguments for function

        Returns:
            Benchmark result
        """
        times = []
        errors = 0

        # Warmup
        for _ in range(warmup_iterations):
            try:
                if asyncio.iscoroutinefunction(func):
                    await func(**kwargs)
                else:
                    func(**kwargs)
            except Exception:
                pass  # Ignore warmup errors

        # Run benchmark
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                if asyncio.iscoroutinefunction(func):
                    await func(**kwargs)
                else:
                    func(**kwargs)
                times.append(time.perf_counter() - start)
            except Exception:
                errors += 1

        # Calculate statistics
        if times:
            sorted_times = sorted(times)
            avg_time = statistics.mean(times)
            std_dev = statistics.stdev(times) if len(times) > 1 else 0
            p95_idx = int(len(sorted_times) * 0.95)
            p99_idx = int(len(sorted_times) * 0.99)

            result = BenchmarkResult(
                name=name,
                iterations=iterations,
                total_time=sum(times),
                avg_time=avg_time,
                min_time=min(times),
                max_time=max(times),
                median_time=statistics.median(times),
                std_dev=std_dev,
                p95_time=sorted_times[p95_idx] if p95_idx < len(sorted_times) else sorted_times[-1],
                p99_time=sorted_times[p99_idx] if p99_idx < len(sorted_times) else sorted_times[-1],
                success_rate=(iterations - errors) / iterations,
                errors=errors,
            )
        else:
            result = BenchmarkResult(
                name=name,
                iterations=iterations,
                total_time=0,
                avg_time=0,
                min_time=0,
                max_time=0,
                median_time=0,
                std_dev=0,
                p95_time=0,
                p99_time=0,
                success_rate=0,
                errors=errors,
            )

        self._results.append(result)

        logger.info(
            f"🏁 Benchmark '{name}': avg={result.avg_time * 1000:.2f}ms, "
            f"p95={result.p95_time * 1000:.2f}ms, "
            f"success={result.success_rate:.0%}"
        )

        return result

    async def run_load_test(
        self,
        func: Callable,
        concurrent_users: int = 10,
        duration_seconds: int = 60,
        **kwargs,
    ) -> LoadTestResult:
        """
        Run load test.

        Args:
            func: Function to test
            concurrent_users: Number of concurrent users
            duration_seconds: Test duration
            **kwargs: Arguments for function

        Returns:
            Load test result
        """
        start_time = time.time()
        end_time = start_time + duration_seconds

        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        response_times = []

        async def worker():
            """Worker coroutine."""
            nonlocal total_requests, successful_requests, failed_requests

            while time.time() < end_time:
                total_requests += 1
                start = time.perf_counter()

                try:
                    if asyncio.iscoroutinefunction(func):
                        await func(**kwargs)
                    else:
                        func(**kwargs)
                    successful_requests += 1
                    response_times.append(time.perf_counter() - start)
                except Exception:
                    failed_requests += 1

        # Run workers
        workers = [worker() for _ in range(concurrent_users)]
        await asyncio.gather(*workers, return_exceptions=True)

        # Calculate results
        actual_duration = time.time() - start_time
        rps = successful_requests / actual_duration if actual_duration > 0 else 0

        if response_times:
            sorted_times = sorted(response_times)
            avg_time = statistics.mean(response_times)
            p95_idx = int(len(sorted_times) * 0.95)
            p99_idx = int(len(sorted_times) * 0.99)

            result = LoadTestResult(
                concurrent_users=concurrent_users,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                requests_per_second=rps,
                avg_response_time=avg_time,
                p95_response_time=sorted_times[p95_idx] if p95_idx < len(sorted_times) else sorted_times[-1],
                p99_response_time=sorted_times[p99_idx] if p99_idx < len(sorted_times) else sorted_times[-1],
                error_rate=failed_requests / total_requests if total_requests > 0 else 0,
                duration_seconds=actual_duration,
            )
        else:
            result = LoadTestResult(
                concurrent_users=concurrent_users,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                requests_per_second=rps,
                avg_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                error_rate=failed_requests / total_requests if total_requests > 0 else 0,
                duration_seconds=actual_duration,
            )

        self._load_test_results.append(result)

        logger.info(f"🏁 Load test: {concurrent_users} users, {rps:.1f} req/s, error_rate={result.error_rate:.0%}")

        return result

    def set_baseline(self, name: str, result: BenchmarkResult) -> None:
        """
        Set baseline for regression detection.

        Args:
            name: Benchmark name
            result: Baseline result
        """
        self._baseline_results[name] = result
        logger.info(f"📊 Baseline set for '{name}': avg={result.avg_time * 1000:.2f}ms")

    def check_regression(
        self,
        name: str,
        current_result: BenchmarkResult,
        threshold_percent: float = 0.2,
    ) -> tuple[bool, str]:
        """
        Check for performance regression.

        Args:
            name: Benchmark name
            current_result: Current result
            threshold_percent: Regression threshold (0.2 = 20%)

        Returns:
            Tuple of (is_regression, message)
        """
        if name not in self._baseline_results:
            return False, "No baseline available"

        baseline = self._baseline_results[name]

        # Check if avg time increased beyond threshold
        if baseline.avg_time == 0:
            return False, "Baseline time is zero"

        change_percent = (current_result.avg_time - baseline.avg_time) / baseline.avg_time

        if change_percent > threshold_percent:
            return True, f"Regression detected: +{change_percent * 100:.1f}%"
        elif change_percent < -threshold_percent:
            return False, f"Improvement: {abs(change_percent) * 100:.1f}%"
        else:
            return False, f"Within threshold: {change_percent * 100:+.1f}%"

    def detect_bottlenecks(self) -> list[str]:
        """
        Detect performance bottlenecks.

        Returns:
            List of bottleneck descriptions
        """
        bottlenecks = []

        for result in self._results:
            # High standard deviation indicates inconsistency
            if result.std_dev > result.avg_time * 0.5:
                bottlenecks.append(f"{result.name}: High variance (std_dev={result.std_dev * 1000:.2f}ms)")

            # High p99 indicates tail latency issues
            if result.p99_time > result.avg_time * 3:
                bottlenecks.append(f"{result.name}: High tail latency (p99={result.p99_time * 1000:.2f}ms)")

            # Low success rate indicates stability issues
            if result.success_rate < 0.95:
                bottlenecks.append(f"{result.name}: Low success rate ({result.success_rate:.0%})")

        for load_result in self._load_test_results:
            # High error rate under load
            if load_result.error_rate > 0.05:
                bottlenecks.append(
                    f"Load test: High error rate at {load_result.concurrent_users} users ({load_result.error_rate:.0%})"
                )

            # Degraded response time under load
            if load_result.p95_response_time > load_result.avg_response_time * 2:
                bottlenecks.append(f"Load test: Response time degradation at {load_result.concurrent_users} users")

        return bottlenecks

    def generate_recommendations(self) -> list[str]:
        """
        Generate performance recommendations.

        Returns:
            List of recommendations
        """
        recommendations = []

        for result in self._results:
            # Slow benchmarks
            if result.avg_time > 1.0:  # > 1 second
                recommendations.append(f"Optimize '{result.name}': avg={result.avg_time * 1000:.0f}ms")

            # High variance
            if result.std_dev > result.avg_time * 0.3:
                recommendations.append(f"Stabilize '{result.name}': reduce variance")

        for load_result in self._load_test_results:
            # Low throughput
            if load_result.requests_per_second < 10:
                recommendations.append(f"Increase throughput: {load_result.requests_per_second:.1f} req/s")

            # High error rate
            if load_result.error_rate > 0.01:
                recommendations.append(f"Reduce error rate: {load_result.error_rate:.0%}")

        return recommendations

    def generate_report(self) -> BenchmarkReport:
        """
        Generate comprehensive benchmark report.

        Returns:
            Benchmark report
        """
        # Count passed/failed
        passed = sum(1 for r in self._results if r.success_rate >= 0.95)
        failed = len(self._results) - passed

        # Detect bottlenecks
        bottlenecks = self.detect_bottlenecks()

        # Generate recommendations
        recommendations = self.generate_recommendations()

        report = BenchmarkReport(
            timestamp=datetime.utcnow().isoformat(),
            total_benchmarks=len(self._results),
            passed_benchmarks=passed,
            failed_benchmarks=failed,
            results=self._results,
            load_tests=self._load_test_results,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
        )

        logger.info(
            f"📊 Report: {passed}/{len(self._results)} benchmarks passed, {len(bottlenecks)} bottlenecks detected"
        )

        return report

    def get_summary(self) -> dict[str, Any]:
        """Get benchmark summary."""
        if not self._results:
            return {"total_benchmarks": 0}

        return {
            "total_benchmarks": len(self._results),
            "avg_response_time": statistics.mean(r.avg_time for r in self._results),
            "p95_response_time": statistics.mean(r.p95_time for r in self._results),
            "avg_success_rate": statistics.mean(r.success_rate for r in self._results),
            "total_load_tests": len(self._load_test_results),
        }

    def clear_results(self) -> None:
        """Clear all results."""
        self._results.clear()
        self._load_test_results.clear()
        logger.info("🗑️ Benchmark results cleared")


# Global benchmark suite instance
_suite: BenchmarkSuite | None = None


def get_benchmark_suite() -> BenchmarkSuite:
    """Get or create benchmark suite (singleton)."""
    global _suite
    if _suite is None:
        _suite = BenchmarkSuite()
    return _suite
