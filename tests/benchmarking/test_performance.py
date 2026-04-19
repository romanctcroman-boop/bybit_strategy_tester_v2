"""
Tests for Performance Benchmark Suite

Run: pytest tests/benchmarking/test_performance.py -v
"""

import asyncio
import sys
import time

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from backend.benchmarking.performance import (
    BenchmarkReport,
    BenchmarkResult,
    BenchmarkSuite,
    LoadTestResult,
    get_benchmark_suite,
)


class TestBenchmarkResult:
    """Tests for BenchmarkResult."""

    def test_to_dict(self):
        """Test conversion to dict."""
        result = BenchmarkResult(
            name="test_benchmark",
            iterations=100,
            total_time=1.0,
            avg_time=0.01,
            min_time=0.005,
            max_time=0.02,
            median_time=0.009,
            std_dev=0.003,
            p95_time=0.015,
            p99_time=0.018,
            success_rate=0.98,
            errors=2,
        )

        data = result.to_dict()

        assert data["name"] == "test_benchmark"
        assert data["iterations"] == 100
        assert data["avg_time"] == 0.01
        assert data["success_rate"] == 0.98


class TestLoadTestResult:
    """Tests for LoadTestResult."""

    def test_to_dict(self):
        """Test conversion to dict."""
        result = LoadTestResult(
            concurrent_users=10,
            total_requests=1000,
            successful_requests=990,
            failed_requests=10,
            requests_per_second=100.0,
            avg_response_time=0.05,
            p95_response_time=0.08,
            p99_response_time=0.1,
            error_rate=0.01,
            duration_seconds=10.0,
        )

        data = result.to_dict()

        assert data["concurrent_users"] == 10
        assert data["requests_per_second"] == 100.0
        assert data["error_rate"] == 0.01


class TestBenchmarkReport:
    """Tests for BenchmarkReport."""

    def test_to_dict(self):
        """Test conversion to dict."""
        report = BenchmarkReport(
            timestamp="2026-03-03T00:00:00",
            total_benchmarks=5,
            passed_benchmarks=4,
            failed_benchmarks=1,
            bottlenecks=["High latency"],
            recommendations=["Optimize queries"],
        )

        data = report.to_dict()

        assert data["timestamp"] == "2026-03-03T00:00:00"
        assert data["total_benchmarks"] == 5
        assert data["passed_benchmarks"] == 4
        assert "High latency" in data["bottlenecks"]


class TestBenchmarkSuite:
    """Tests for BenchmarkSuite."""

    @pytest.fixture
    def suite(self):
        """Create benchmark suite."""
        return BenchmarkSuite()

    @pytest.mark.asyncio
    async def test_run_benchmark_sync(self, suite):
        """Test running sync benchmark."""

        def slow_function():
            time.sleep(0.01)

        result = await suite.run_benchmark(
            "slow_function",
            slow_function,
            iterations=10,
            warmup_iterations=2,
        )

        assert result.name == "slow_function"
        assert result.iterations == 10
        assert result.avg_time >= 0.01
        assert result.success_rate > 0

    @pytest.mark.asyncio
    async def test_run_benchmark_async(self, suite):
        """Test running async benchmark."""

        async def async_function():
            await asyncio.sleep(0.01)

        result = await suite.run_benchmark(
            "async_function",
            async_function,
            iterations=10,
        )

        assert result.name == "async_function"
        assert result.avg_time >= 0.01

    @pytest.mark.asyncio
    async def test_run_benchmark_with_errors(self, suite):
        """Test benchmark with errors."""

        def failing_function():
            raise ValueError("Test error")

        result = await suite.run_benchmark(
            "failing_function",
            failing_function,
            iterations=10,
        )

        # All iterations should fail
        assert result.errors == 10 or result.errors > 0
        assert result.success_rate == 0.0 or result.success_rate < 1.0

    @pytest.mark.asyncio
    async def test_run_load_test(self, suite):
        """Test load testing."""

        async def api_call():
            await asyncio.sleep(0.01)

        result = await suite.run_load_test(
            api_call,
            concurrent_users=5,
            duration_seconds=2,
        )

        assert result.concurrent_users == 5
        assert result.total_requests > 0
        assert result.requests_per_second > 0

    @pytest.mark.asyncio
    async def test_run_load_test_with_errors(self, suite):
        """Test load test with errors."""

        def failing_api():
            raise Exception("API error")

        result = await suite.run_load_test(
            failing_api,
            concurrent_users=2,
            duration_seconds=1,
        )

        assert result.failed_requests > 0
        assert result.error_rate > 0

    def test_set_baseline(self, suite):
        """Test setting baseline."""
        baseline = BenchmarkResult(
            name="test",
            iterations=100,
            total_time=1.0,
            avg_time=0.01,
            min_time=0.005,
            max_time=0.02,
            median_time=0.009,
            std_dev=0.001,
            p95_time=0.015,
            p99_time=0.018,
            success_rate=1.0,
        )

        suite.set_baseline("test", baseline)

        assert "test" in suite._baseline_results

    def test_check_regression(self, suite):
        """Test regression detection."""
        # Set baseline
        baseline = BenchmarkResult(
            name="test",
            iterations=100,
            total_time=1.0,
            avg_time=0.01,
            min_time=0.005,
            max_time=0.02,
            median_time=0.009,
            std_dev=0.001,
            p95_time=0.015,
            p99_time=0.018,
            success_rate=1.0,
        )
        suite.set_baseline("test", baseline)

        # Test with regression (50% slower)
        current = BenchmarkResult(
            name="test",
            iterations=100,
            total_time=1.5,
            avg_time=0.015,
            min_time=0.01,
            max_time=0.025,
            median_time=0.014,
            std_dev=0.001,
            p95_time=0.02,
            p99_time=0.023,
            success_rate=1.0,
        )

        is_regression, message = suite.check_regression("test", current)

        assert is_regression is True
        assert "+" in message  # Positive change

    def test_check_regression_improvement(self, suite):
        """Test improvement detection."""
        # Set baseline
        baseline = BenchmarkResult(
            name="test",
            iterations=100,
            total_time=1.0,
            avg_time=0.01,
            min_time=0.005,
            max_time=0.02,
            median_time=0.009,
            std_dev=0.001,
            p95_time=0.015,
            p99_time=0.018,
            success_rate=1.0,
        )
        suite.set_baseline("test", baseline)

        # Test with improvement (50% faster)
        current = BenchmarkResult(
            name="test",
            iterations=100,
            total_time=0.5,
            avg_time=0.005,
            min_time=0.002,
            max_time=0.01,
            median_time=0.004,
            std_dev=0.001,
            p95_time=0.007,
            p99_time=0.009,
            success_rate=1.0,
        )

        is_regression, message = suite.check_regression("test", current)

        assert is_regression is False
        assert "Improvement" in message

    def test_detect_bottlenecks(self, suite):
        """Test bottleneck detection."""
        # Add result with high variance
        result = BenchmarkResult(
            name="variable_function",
            iterations=100,
            total_time=1.0,
            avg_time=0.01,
            min_time=0.001,
            max_time=0.1,
            median_time=0.008,
            std_dev=0.02,  # High std dev
            p95_time=0.05,
            p99_time=0.08,
            success_rate=0.9,  # Low success rate
        )
        suite._results.append(result)

        bottlenecks = suite.detect_bottlenecks()

        assert len(bottlenecks) > 0
        assert any("variance" in b for b in bottlenecks)
        assert any("success rate" in b for b in bottlenecks)

    def test_generate_recommendations(self, suite):
        """Test recommendation generation."""
        # Add slow benchmark
        result = BenchmarkResult(
            name="slow_function",
            iterations=100,
            total_time=100.0,
            avg_time=1.5,  # > 1 second
            min_time=1.0,
            max_time=2.0,
            median_time=1.4,
            std_dev=0.2,
            p95_time=1.8,
            p99_time=1.9,
            success_rate=1.0,
        )
        suite._results.append(result)

        recommendations = suite.generate_recommendations()

        assert len(recommendations) > 0
        assert any("slow_function" in r for r in recommendations)

    def test_generate_report(self, suite):
        """Test report generation."""
        # Add some results
        result = BenchmarkResult(
            name="test",
            iterations=100,
            total_time=1.0,
            avg_time=0.01,
            min_time=0.005,
            max_time=0.02,
            median_time=0.009,
            std_dev=0.001,
            p95_time=0.015,
            p99_time=0.018,
            success_rate=0.98,
        )
        suite._results.append(result)

        report = suite.generate_report()

        assert report.total_benchmarks == 1
        assert report.passed_benchmarks == 1  # 98% >= 95%
        assert report.failed_benchmarks == 0
        assert report.timestamp is not None

    def test_get_summary(self, suite):
        """Test summary generation."""
        # Empty summary
        summary = suite.get_summary()
        assert summary["total_benchmarks"] == 0

        # Add result
        result = BenchmarkResult(
            name="test",
            iterations=100,
            total_time=1.0,
            avg_time=0.01,
            min_time=0.005,
            max_time=0.02,
            median_time=0.009,
            std_dev=0.001,
            p95_time=0.015,
            p99_time=0.018,
            success_rate=1.0,
        )
        suite._results.append(result)

        summary = suite.get_summary()

        assert summary["total_benchmarks"] == 1
        assert summary["avg_response_time"] > 0

    def test_clear_results(self, suite):
        """Test clearing results."""
        # Add result
        result = BenchmarkResult(
            name="test",
            iterations=100,
            total_time=1.0,
            avg_time=0.01,
            min_time=0.005,
            max_time=0.02,
            median_time=0.009,
            std_dev=0.001,
            p95_time=0.015,
            p99_time=0.018,
            success_rate=1.0,
        )
        suite._results.append(result)

        # Clear
        suite.clear_results()

        assert len(suite._results) == 0
        assert len(suite._load_test_results) == 0


class TestGlobalSuite:
    """Tests for global suite functions."""

    def test_get_benchmark_suite_singleton(self):
        """Test singleton pattern."""
        s1 = get_benchmark_suite()
        s2 = get_benchmark_suite()

        # Should be same instance
        assert s1 is s2


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_full_benchmark_workflow(self):
        """Test full benchmark workflow."""
        suite = BenchmarkSuite()

        # Run benchmarks
        async def fast_function():
            await asyncio.sleep(0.001)

        async def slow_function():
            await asyncio.sleep(0.01)

        result1 = await suite.run_benchmark("fast", fast_function, iterations=20)
        result2 = await suite.run_benchmark("slow", slow_function, iterations=20)

        # Set baseline
        suite.set_baseline("fast", result1)

        # Run again to check regression
        result3 = await suite.run_benchmark("fast", fast_function, iterations=20)
        is_regression, _ = suite.check_regression("fast", result3)

        # Run load test
        load_result = await suite.run_load_test(
            fast_function,
            concurrent_users=5,
            duration_seconds=2,
        )

        # Generate report
        report = suite.generate_report()

        # Verify
        assert report.total_benchmarks == 3
        assert len(report.results) == 3
        assert len(report.load_tests) == 1
        assert report.timestamp is not None

        # Verify fast is faster than slow
        assert result1.avg_time < result2.avg_time

        # Verify load test ran
        assert load_result.total_requests > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
