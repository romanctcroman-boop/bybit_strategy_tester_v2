"""
Tests for Smoke Tests

Run: pytest tests/deployment/test_smoke_tests.py -v
"""

import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from scripts.smoke_tests import (
    SmokeTests,
    TestResult,
)


class TestTestResult:
    """Tests for TestResult."""

    def test_to_dict(self):
        """Test conversion to dict."""
        result = TestResult(
            name="test_health",
            passed=True,
            duration_ms=50.5,
        )

        data = result.to_dict()

        assert data["name"] == "test_health"
        assert data["passed"] is True
        assert data["duration_ms"] == 50.5
        assert data["error"] is None

    def test_to_dict_with_error(self):
        """Test conversion with error."""
        result = TestResult(
            name="test_failed",
            passed=False,
            duration_ms=100.0,
            error="Connection timeout",
        )

        data = result.to_dict()

        assert data["passed"] is False
        assert data["error"] == "Connection timeout"


class TestSmokeTests:
    """Tests for SmokeTests."""

    @pytest.fixture
    def smoke_tests(self):
        """Create smoke tests instance."""
        return SmokeTests(base_url="http://test-server:8000", timeout=5)

    @patch("scripts.smoke_tests.requests.get")
    def test_test_health_endpoint(self, mock_get, smoke_tests):
        """Test health endpoint test."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_response

        # Should not raise
        smoke_tests.test_health_endpoint()

        mock_get.assert_called_once()

    @patch("scripts.smoke_tests.requests.get")
    def test_test_health_endpoint_fails(self, mock_get, smoke_tests):
        """Test health endpoint test failure."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "unhealthy"}
        mock_get.return_value = mock_response

        with pytest.raises(AssertionError):
            smoke_tests.test_health_endpoint()

    @patch("scripts.smoke_tests.requests.get")
    def test_test_liveness_probe(self, mock_get, smoke_tests):
        """Test liveness probe test."""
        mock_get.return_value = MagicMock()

        # Should not raise
        smoke_tests.test_liveness_probe()

    @patch("scripts.smoke_tests.requests.get")
    def test_test_readiness_probe(self, mock_get, smoke_tests):
        """Test readiness probe test."""
        mock_get.return_value = MagicMock()

        # Should not raise
        smoke_tests.test_readiness_probe()

    @patch("scripts.smoke_tests.requests.get")
    def test_test_database_health(self, mock_get, smoke_tests):
        """Test database health test."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_response

        # Should not raise
        smoke_tests.test_database_health()

    @patch("scripts.smoke_tests.requests.get")
    def test_test_api_docs(self, mock_get, smoke_tests):
        """Test API docs test."""
        mock_response = MagicMock()
        mock_response.text = "<html><title>Swagger UI</title></html>"
        mock_get.return_value = mock_response

        # Should not raise
        smoke_tests.test_api_docs()

    @patch("scripts.smoke_tests.requests.get")
    def test_test_openapi_schema(self, mock_get, smoke_tests):
        """Test OpenAPI schema test."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"openapi": "3.0.0", "paths": {"/health": {}}}
        mock_get.return_value = mock_response

        # Should not raise
        smoke_tests.test_openapi_schema()

    @patch("scripts.smoke_tests.requests.get")
    def test_test_backtest_endpoint(self, mock_get, smoke_tests):
        """Test backtest endpoint test."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        # Should not raise
        smoke_tests.test_backtest_endpoint()

    @patch("scripts.smoke_tests.requests.get")
    def test_test_metrics_endpoint(self, mock_get, smoke_tests):
        """Test metrics endpoint test."""
        mock_response = MagicMock()
        mock_response.text = "# HELP process_uptime_seconds\n# TYPE gauge"
        mock_get.return_value = mock_response

        # Should not raise
        smoke_tests.test_metrics_endpoint()

    @patch("scripts.smoke_tests.requests.get")
    def test_run_test_success(self, mock_get, smoke_tests):
        """Test running a successful test."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_response

        result = smoke_tests.run_test("Test health", smoke_tests.test_health_endpoint)

        assert result.name == "Test health"
        assert result.passed is True
        assert result.error is None
        assert result.duration_ms >= 0

    @patch("scripts.smoke_tests.requests.get")
    def test_run_test_failure(self, mock_get, smoke_tests):
        """Test running a failed test."""
        mock_get.side_effect = Exception("Connection refused")

        result = smoke_tests.run_test("Test health", smoke_tests.test_health_endpoint)

        assert result.name == "Test health"
        assert result.passed is False
        assert "Connection refused" in result.error

    @patch("scripts.smoke_tests.requests.get")
    def test_run_all_tests_all_pass(self, mock_get, smoke_tests):
        """Test running all tests (all pass)."""

        # Mock different responses for different endpoints
        def mock_response(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            mock = MagicMock()

            if "/health" in url or "database" in url:
                mock.json.return_value = {"status": "healthy"}
                mock.text = "# HELP test\n# TYPE gauge"
            elif "/docs" in url:
                mock.text = "<html><title>Swagger UI</title></html>"
            elif "/openapi" in url:
                mock.json.return_value = {"openapi": "3.0.0", "paths": {"/health": {}}}
            elif "/backtest" in url or "/strategy" in url or "/market" in url:
                mock.json.return_value = []
            else:
                mock.json.return_value = {"status": "healthy"}
                mock.text = "# HELP test\n# TYPE gauge"

            return mock

        mock_get.side_effect = mock_response

        success = smoke_tests.run_all_tests()

        assert success is True
        assert len(smoke_tests.results) > 0
        assert all(r.passed for r in smoke_tests.results)

    @patch("scripts.smoke_tests.requests.get")
    def test_run_all_tests_some_fail(self, mock_get, smoke_tests):
        """Test running all tests (some fail)."""

        def side_effect(*args, **kwargs):
            raise Exception("Test error")

        mock_get.side_effect = side_effect

        success = smoke_tests.run_all_tests()

        assert success is False
        assert all(not r.passed for r in smoke_tests.results)

    def test_get_report(self, smoke_tests):
        """Test report generation."""
        # Add some results
        smoke_tests.results = [
            TestResult("test1", True, 50.0),
            TestResult("test2", False, 100.0, "Error"),
            TestResult("test3", True, 75.0),
        ]

        report = smoke_tests.get_report()

        assert report["total_tests"] == 3
        assert report["passed_tests"] == 2
        assert report["failed_tests"] == 1
        assert report["success_rate"] == pytest.approx(2 / 3)
        assert len(report["results"]) == 3

    def test_get_report_empty(self, smoke_tests):
        """Test report with no results."""
        report = smoke_tests.get_report()

        assert report["total_tests"] == 0
        assert report["passed_tests"] == 0
        assert report["success_rate"] == 0


class TestSmokeTestIntegration:
    """Integration tests for smoke tests."""

    @patch("scripts.smoke_tests.requests.get")
    def test_full_smoke_test_workflow(self, mock_get):
        """Test full smoke test workflow."""

        # Mock different responses for different endpoints
        def mock_response(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            mock = MagicMock()

            if "/health" in url or "database" in url:
                mock.json.return_value = {"status": "healthy"}
                mock.text = "# HELP test\n# TYPE gauge"
            elif "/docs" in url:
                mock.text = "<html><title>Swagger UI</title></html>"
            elif "/openapi" in url:
                mock.json.return_value = {"openapi": "3.0.0", "paths": {"/health": {}}}
            elif "/backtest" in url or "/strategy" in url or "/market" in url:
                mock.json.return_value = []
            else:
                mock.json.return_value = {"status": "healthy"}
                mock.text = "# HELP test\n# TYPE gauge"

            return mock

        mock_get.side_effect = mock_response

        # Create smoke tests
        tests = SmokeTests("http://test:8000")

        # Run all tests
        success = tests.run_all_tests()

        # Verify
        assert success is True

        # Get report
        report = tests.get_report()

        assert report["total_tests"] > 0
        assert report["success_rate"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
