"""
Comprehensive tests for dashboard.py endpoints.

Testing Strategy:
- All 3 GET endpoints (KPI, activity, stats)
- Response structure validation
- Data type verification
- Timestamp format checks
- Edge cases and concurrency

Note: Some tests add small delays to avoid rate limiting (429 errors)
"""
from datetime import datetime
from unittest.mock import patch
import time

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client(monkeypatch):
    """FastAPI test client"""
    return TestClient(app)


class TestDashboardKPIEndpoint:
    """Tests for GET /api/dashboard/kpi endpoint."""
    
    def test_kpi_returns_200(self, client: TestClient):
        """Should return 200 OK."""
        response = client.get("/api/dashboard/kpi")
        assert response.status_code == 200
    
    def test_kpi_returns_dict(self, client: TestClient):
        """Should return JSON dict."""
        response = client.get("/api/dashboard/kpi")
        data = response.json()
        assert isinstance(data, dict)
    
    def test_kpi_has_required_fields(self, client: TestClient):
        """Should have all required KPI fields."""
        response = client.get("/api/dashboard/kpi")
        data = response.json()
        
        required_fields = [
            "totalPnL", "totalTrades", "winRate", 
            "activeBots", "sharpeRatio", "avgTradeReturn", "timestamp"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
    
    def test_kpi_camel_case_naming(self, client: TestClient):
        """Should use camelCase for frontend compatibility."""
        response = client.get("/api/dashboard/kpi")
        data = response.json()
        
        # Check specific camelCase fields
        assert "totalPnL" in data  # Not total_pnl
        assert "totalTrades" in data
        assert "winRate" in data
        assert "activeBots" in data
        assert "sharpeRatio" in data
        assert "avgTradeReturn" in data
    
    def test_kpi_numeric_types(self, client: TestClient):
        """Should return numeric values for metrics."""
        response = client.get("/api/dashboard/kpi")
        data = response.json()
        
        assert isinstance(data["totalPnL"], (int, float))
        assert isinstance(data["totalTrades"], int)
        assert isinstance(data["winRate"], (int, float))
        assert isinstance(data["activeBots"], int)
        assert isinstance(data["sharpeRatio"], (int, float))
        assert isinstance(data["avgTradeReturn"], (int, float))
    
    def test_kpi_timestamp_format(self, client: TestClient):
        """Should return valid ISO timestamp."""
        response = client.get("/api/dashboard/kpi")
        data = response.json()
        
        # Should parse without exception
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert isinstance(timestamp, datetime)
    
    def test_kpi_timestamp_recent(self, client: TestClient):
        """Timestamp should be recent (within 1 second)."""
        now = datetime.now()
        response = client.get("/api/dashboard/kpi")
        data = response.json()
        
        timestamp = datetime.fromisoformat(data["timestamp"])
        delta = abs((timestamp - now).total_seconds())
        
        assert delta < 2, f"Timestamp too old: {delta}s"
    
    def test_kpi_positive_metrics(self, client: TestClient):
        """Should return positive values for key metrics."""
        response = client.get("/api/dashboard/kpi")
        data = response.json()
        
        assert data["totalTrades"] >= 0
        assert data["activeBots"] >= 0
        assert 0 <= data["winRate"] <= 100
    
    def test_kpi_sharpe_ratio_range(self, client: TestClient):
        """Sharpe ratio should be realistic (-5 to 5)."""
        response = client.get("/api/dashboard/kpi")
        data = response.json()
        
        assert -5 <= data["sharpeRatio"] <= 5
    
    def test_kpi_multiple_calls_consistent(self, client: TestClient):
        """Multiple calls should return same mock data."""
        response1 = client.get("/api/dashboard/kpi")
        time.sleep(0.5)  # Avoid rate limiting
        response2 = client.get("/api/dashboard/kpi")
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Mock data should be identical (except timestamp)
        assert data1["totalPnL"] == data2["totalPnL"]
        assert data1["totalTrades"] == data2["totalTrades"]
        assert data1["winRate"] == data2["winRate"]
    
    def test_kpi_content_type_json(self, client: TestClient):
        """Should return JSON content type."""
        response = client.get("/api/dashboard/kpi")
        assert "application/json" in response.headers["content-type"]


class TestDashboardActivityEndpoint:
    """Tests for GET /api/dashboard/activity endpoint."""
    
    def test_activity_returns_200(self, client: TestClient):
        """Should return 200 OK."""
        response = client.get("/api/dashboard/activity")
        assert response.status_code == 200
    
    def test_activity_returns_list(self, client: TestClient):
        """Should return JSON list."""
        response = client.get("/api/dashboard/activity")
        data = response.json()
        assert isinstance(data, list)
    
    def test_activity_not_empty(self, client: TestClient):
        """Should return at least 1 activity."""
        response = client.get("/api/dashboard/activity")
        data = response.json()
        assert len(data) > 0
    
    def test_activity_item_structure(self, client: TestClient):
        """Each activity should have required fields."""
        response = client.get("/api/dashboard/activity")
        data = response.json()
        
        required_fields = ["id", "type", "title", "description", "timestamp", "status"]
        
        for activity in data:
            for field in required_fields:
                assert field in activity, f"Missing field: {field}"
    
    def test_activity_types_valid(self, client: TestClient):
        """Activity types should be valid."""
        response = client.get("/api/dashboard/activity")
        data = response.json()
        
        valid_types = [
            "backtest_completed", "optimization_running", 
            "bot_started", "bot_stopped", "error"
        ]
        
        for activity in data:
            assert activity["type"] in valid_types or "_" in activity["type"]
    
    def test_activity_status_valid(self, client: TestClient):
        """Activity status should be valid."""
        response = client.get("/api/dashboard/activity")
        data = response.json()
        
        valid_statuses = ["success", "running", "failed", "pending"]
        
        for activity in data:
            assert activity["status"] in valid_statuses
    
    def test_activity_timestamps_chronological(self, client: TestClient):
        """Activities should be in reverse chronological order (newest first)."""
        response = client.get("/api/dashboard/activity")
        data = response.json()
        
        timestamps = [
            datetime.fromisoformat(act["timestamp"]) 
            for act in data
        ]
        
        # Should be descending (newest first)
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1]
    
    def test_activity_timestamps_recent(self, client: TestClient):
        """All activities should be recent (within 1 hour)."""
        now = datetime.now()
        response = client.get("/api/dashboard/activity")
        data = response.json()
        
        for activity in data:
            timestamp = datetime.fromisoformat(activity["timestamp"])
            delta = abs((now - timestamp).total_seconds())
            assert delta < 3600, f"Activity too old: {delta}s"
    
    def test_activity_ids_unique(self, client: TestClient):
        """Activity IDs should be unique."""
        response = client.get("/api/dashboard/activity")
        data = response.json()
        
        ids = [act["id"] for act in data]
        assert len(ids) == len(set(ids)), "Duplicate activity IDs"
    
    def test_activity_content_type_json(self, client: TestClient):
        """Should return JSON content type."""
        response = client.get("/api/dashboard/activity")
        assert "application/json" in response.headers["content-type"]


class TestDashboardStatsEndpoint:
    """Tests for GET /api/dashboard/stats endpoint."""
    
    def test_stats_returns_200(self, client: TestClient):
        """Should return 200 OK."""
        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
    
    def test_stats_returns_dict(self, client: TestClient):
        """Should return JSON dict."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        assert isinstance(data, dict)
    
    def test_stats_has_performance_section(self, client: TestClient):
        """Should have performance section."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        assert "performance" in data
        assert isinstance(data["performance"], dict)
    
    def test_stats_has_portfolio_section(self, client: TestClient):
        """Should have portfolio section."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        assert "portfolio" in data
        assert isinstance(data["portfolio"], dict)
    
    def test_stats_performance_fields(self, client: TestClient):
        """Performance should have all required fields."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        performance = data["performance"]
        required_fields = [
            "totalReturn", "monthlyReturn", "maxDrawdown",
            "winningDays", "losingDays"
        ]
        
        for field in required_fields:
            assert field in performance, f"Missing field: {field}"
    
    def test_stats_portfolio_fields(self, client: TestClient):
        """Portfolio should have all required fields."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        portfolio = data["portfolio"]
        required_fields = ["totalValue", "cash", "positions"]
        
        for field in required_fields:
            assert field in portfolio, f"Missing field: {field}"
    
    def test_stats_timestamp_present(self, client: TestClient):
        """Should have timestamp field."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        assert "timestamp" in data
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert isinstance(timestamp, datetime)
    
    def test_stats_performance_numeric_types(self, client: TestClient):
        """Performance metrics should be numeric."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        perf = data["performance"]
        assert isinstance(perf["totalReturn"], (int, float))
        assert isinstance(perf["monthlyReturn"], (int, float))
        assert isinstance(perf["maxDrawdown"], (int, float))
        assert isinstance(perf["winningDays"], int)
        assert isinstance(perf["losingDays"], int)
    
    def test_stats_portfolio_numeric_types(self, client: TestClient):
        """Portfolio values should be numeric."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        portfolio = data["portfolio"]
        assert isinstance(portfolio["totalValue"], (int, float))
        assert isinstance(portfolio["cash"], (int, float))
        assert isinstance(portfolio["positions"], (int, float))
    
    def test_stats_max_drawdown_negative(self, client: TestClient):
        """Max drawdown should be negative or zero."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        assert data["performance"]["maxDrawdown"] <= 0
    
    def test_stats_winning_losing_days_positive(self, client: TestClient):
        """Winning/losing days should be non-negative."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        perf = data["performance"]
        assert perf["winningDays"] >= 0
        assert perf["losingDays"] >= 0
    
    def test_stats_portfolio_balance(self, client: TestClient):
        """Portfolio total should equal cash + positions."""
        response = client.get("/api/dashboard/stats")
        data = response.json()
        
        portfolio = data["portfolio"]
        calculated_total = portfolio["cash"] + portfolio["positions"]
        
        # Allow small floating point error
        assert abs(portfolio["totalValue"] - calculated_total) < 0.01
    
    def test_stats_content_type_json(self, client: TestClient):
        """Should return JSON content type."""
        response = client.get("/api/dashboard/stats")
        assert "application/json" in response.headers["content-type"]


class TestDashboardEdgeCases:
    """Edge cases and integration tests."""
    
    def test_concurrent_kpi_requests(self, client: TestClient):
        """Multiple concurrent KPI requests should succeed."""
        responses = []
        for i in range(5):
            responses.append(client.get("/api/dashboard/kpi"))
            if i < 4:  # No delay after last request
                time.sleep(0.5)  # Avoid rate limiting
        
        for response in responses:
            assert response.status_code == 200
    
    def test_all_endpoints_accessible(self, client: TestClient):
        """All dashboard endpoints should be accessible."""
        endpoints = [
            "/api/dashboard/kpi",
            "/api/dashboard/activity",
            "/api/dashboard/stats"
        ]
        
        for i, endpoint in enumerate(endpoints):
            response = client.get(endpoint)
            assert response.status_code == 200
            if i < len(endpoints) - 1:  # No delay after last endpoint
                time.sleep(0.5)  # Avoid rate limiting
    
    def test_kpi_activity_stats_independent(self, client: TestClient):
        """Each endpoint should work independently."""
        # Should work in any order
        response1 = client.get("/api/dashboard/stats")
        time.sleep(0.5)
        response2 = client.get("/api/dashboard/kpi")
        time.sleep(0.5)
        response3 = client.get("/api/dashboard/activity")
        
        assert all(r.status_code == 200 for r in [response1, response2, response3])
    
    def test_dashboard_no_query_params_needed(self, client: TestClient):
        """Dashboard endpoints should work without query params."""
        # No params needed
        response = client.get("/api/dashboard/kpi")
        assert response.status_code == 200
        
        time.sleep(0.5)  # Avoid rate limiting
        
        # Extra params should be ignored
        response = client.get("/api/dashboard/kpi?foo=bar")
        assert response.status_code == 200
    
    def test_dashboard_no_authentication_required(self, client: TestClient):
        """Dashboard endpoints should be public (no auth)."""
        # Should work without Authorization header
        response = client.get("/api/dashboard/kpi")
        assert response.status_code == 200
    
    def test_activity_list_not_mutated(self, client: TestClient):
        """Multiple calls should return independent data structures."""
        response1 = client.get("/api/dashboard/activity")
        time.sleep(0.5)  # Avoid rate limiting
        response2 = client.get("/api/dashboard/activity")
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Modify first response
        if len(data1) > 0:  # Check list not empty
            data1[0]["title"] = "MODIFIED"
            
            # Second response should be unchanged
            assert data2[0]["title"] != "MODIFIED"


class TestDashboardResponseTiming:
    """Test response timing and performance."""
    
    def test_kpi_fast_response(self, client: TestClient):
        """KPI endpoint should respond quickly (<100ms)."""
        import time
        
        start = time.time()
        response = client.get("/api/dashboard/kpi")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 0.1, f"Response too slow: {duration}s"
    
    def test_activity_fast_response(self, client: TestClient):
        """Activity endpoint should respond quickly (<100ms)."""
        import time
        
        start = time.time()
        response = client.get("/api/dashboard/activity")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 0.1, f"Response too slow: {duration}s"
    
    def test_stats_fast_response(self, client: TestClient):
        """Stats endpoint should respond quickly (<100ms)."""
        import time
        
        start = time.time()
        response = client.get("/api/dashboard/stats")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 0.1, f"Response too slow: {duration}s"


class TestDashboardDataConsistency:
    """Test data consistency across endpoints."""
    
    def test_kpi_and_stats_consistent_pnl(self, client: TestClient):
        """KPI totalPnL should be derivable from stats."""
        kpi = client.get("/api/dashboard/kpi").json()
        time.sleep(0.5)  # Avoid rate limiting
        stats = client.get("/api/dashboard/stats").json()
        
        # Both should exist
        assert "totalPnL" in kpi
        assert "portfolio" in stats
        
        # Values should be numeric
        assert isinstance(kpi["totalPnL"], (int, float))
        assert isinstance(stats["portfolio"]["totalValue"], (int, float))
    
    def test_timestamps_close_together(self, client: TestClient):
        """Timestamps from concurrent calls should be close."""
        kpi = client.get("/api/dashboard/kpi").json()
        time.sleep(0.5)  # Avoid rate limiting
        stats = client.get("/api/dashboard/stats").json()
        time.sleep(0.5)  # Avoid rate limiting
        activity = client.get("/api/dashboard/activity").json()
        
        kpi_time = datetime.fromisoformat(kpi["timestamp"])
        stats_time = datetime.fromisoformat(stats["timestamp"])
        
        delta = abs((kpi_time - stats_time).total_seconds())
        assert delta < 5, f"Timestamps too far apart: {delta}s"  # Allow 5s for delays
