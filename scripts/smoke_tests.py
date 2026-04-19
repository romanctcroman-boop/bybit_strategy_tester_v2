"""
Smoke Tests for Deployment Validation

Run after deployment to verify basic functionality:
- Health checks
- API endpoints
- Database connectivity
- Redis connectivity
- AI agent connectivity

Usage:
    python scripts/smoke_tests.py --environment staging
    python scripts/smoke_tests.py --environment production
"""

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class TestResult:
    """Test result."""

    name: str
    passed: bool
    duration_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "name": self.name,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class SmokeTests:
    """Smoke test suite."""

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize smoke tests.

        Args:
            base_url: Base URL of the deployment
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.results: list[TestResult] = []

    def run_test(self, name: str, test_func: callable) -> TestResult:
        """
        Run a single test.

        Args:
            name: Test name
            test_func: Test function

        Returns:
            Test result
        """
        start = time.time()
        error = None
        passed = True

        try:
            test_func()
        except Exception as e:
            error = str(e)
            passed = False

        duration_ms = (time.time() - start) * 1000

        result = TestResult(
            name=name,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            error=error,
        )

        self.results.append(result)

        status = "✅" if passed else "❌"
        print(f"{status} {name}: {duration_ms:.0f}ms")

        if error:
            print(f"   Error: {error}")

        return result

    def test_health_endpoint(self) -> None:
        """Test health endpoint."""
        response = requests.get(f"{self.base_url}/health", timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        assert data.get("status") == "healthy", "Health check failed"

    def test_liveness_probe(self) -> None:
        """Test liveness probe."""
        response = requests.get(f"{self.base_url}/health/livez", timeout=self.timeout)
        response.raise_for_status()

    def test_readiness_probe(self) -> None:
        """Test readiness probe."""
        response = requests.get(f"{self.base_url}/health/readyz", timeout=self.timeout)
        response.raise_for_status()

    def test_database_health(self) -> None:
        """Test database connectivity."""
        response = requests.get(f"{self.base_url}/health/database", timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        assert data.get("status") == "healthy", "Database health check failed"

    def test_api_docs(self) -> None:
        """Test API documentation."""
        response = requests.get(f"{self.base_url}/docs", timeout=self.timeout)
        response.raise_for_status()
        assert "Swagger" in response.text or "OpenAPI" in response.text

    def test_openapi_schema(self) -> None:
        """Test OpenAPI schema."""
        response = requests.get(f"{self.base_url}/openapi.json", timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        assert "openapi" in data or "swagger" in data
        assert "paths" in data
        assert len(data["paths"]) > 0

    def test_backtest_endpoint(self) -> None:
        """Test backtest endpoint availability."""
        response = requests.get(f"{self.base_url}/api/v1/backtests/", timeout=self.timeout)
        response.raise_for_status()

        # Should return list (may be empty)
        assert isinstance(response.json(), list)

    def test_strategy_builder_endpoint(self) -> None:
        """Test strategy builder endpoint."""
        response = requests.get(f"{self.base_url}/api/v1/strategy-builder/strategies", timeout=self.timeout)
        response.raise_for_status()

        # Should return list
        assert isinstance(response.json(), list)

    def test_market_data_endpoint(self) -> None:
        """Test market data endpoint."""
        response = requests.get(f"{self.base_url}/api/v1/marketdata/symbols-list", timeout=self.timeout)
        response.raise_for_status()

        # Should return list
        assert isinstance(response.json(), list)

    def test_metrics_endpoint(self) -> None:
        """Test Prometheus metrics endpoint."""
        response = requests.get(f"{self.base_url}/health/metrics", timeout=self.timeout)
        response.raise_for_status()

        # Should contain Prometheus metrics
        assert "# HELP" in response.text
        assert "# TYPE" in response.text

    def run_all_tests(self) -> bool:
        """
        Run all smoke tests.

        Returns:
            True if all tests passed
        """
        print(f"\n🧪 Running smoke tests against {self.base_url}\n")

        tests = [
            ("Health endpoint", self.test_health_endpoint),
            ("Liveness probe", self.test_liveness_probe),
            ("Readiness probe", self.test_readiness_probe),
            ("Database health", self.test_database_health),
            ("API documentation", self.test_api_docs),
            ("OpenAPI schema", self.test_openapi_schema),
            ("Backtest endpoint", self.test_backtest_endpoint),
            ("Strategy builder endpoint", self.test_strategy_builder_endpoint),
            ("Market data endpoint", self.test_market_data_endpoint),
            ("Metrics endpoint", self.test_metrics_endpoint),
        ]

        for name, test_func in tests:
            self.run_test(name, test_func)

        # Summary
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        print(f"\n{'=' * 50}")
        print(f"Results: {passed}/{total} tests passed")

        if passed == total:
            print("✅ All smoke tests passed!")
            return True
        else:
            print(f"❌ {total - passed} test(s) failed")
            return False

    def get_report(self) -> dict[str, Any]:
        """Get test report."""
        return {
            "total_tests": len(self.results),
            "passed_tests": sum(1 for r in self.results if r.passed),
            "failed_tests": sum(1 for r in self.results if not r.passed),
            "results": [r.to_dict() for r in self.results],
            "success_rate": sum(1 for r in self.results if r.passed) / len(self.results) if self.results else 0,
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Smoke tests for deployment validation")
    parser.add_argument(
        "--environment", choices=["staging", "production", "local"], default="staging", help="Target environment"
    )
    parser.add_argument("--url", type=str, help="Custom URL (overrides environment)")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--output", type=str, help="Output file for report (JSON)")

    args = parser.parse_args()

    # Determine URL based on environment
    if args.url:
        base_url = args.url
    elif args.environment == "production":
        base_url = "https://api.bybit-strategy-tester.com"
    elif args.environment == "staging":
        base_url = "https://staging.bybit-strategy-tester.com"
    else:
        base_url = "http://localhost:8000"

    # Run tests
    tests = SmokeTests(base_url, timeout=args.timeout)
    success = tests.run_all_tests()

    # Generate report
    report = tests.get_report()

    if args.output:
        import json

        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Report saved to {args.output}")

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
