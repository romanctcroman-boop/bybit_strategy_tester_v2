"""
Comprehensive tests for wizard.py endpoints.

Testing Strategy:
- Strategy version listing and schema retrieval
- Preset management and filtering
- Quick backtest simulation
- Bot creation through wizard
- Input validation and edge cases
"""
import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


class TestStrategyVersionsEndpoint:
    """Test /api/wizard/strategy-versions endpoint"""
    
    def test_list_strategy_versions_success(self, client: TestClient):
        """GET /strategy-versions returns all available versions"""
        response = client.get("/api/v1/wizard/strategy-versions")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] == len(data["items"])
    
    def test_list_strategy_versions_contains_expected_data(self, client: TestClient):
        """Verify strategy versions contain required fields"""
        response = client.get("/api/v1/wizard/strategy-versions")
        data = response.json()
        
        assert data["total"] >= 2  # At least 2 mock versions
        
        # Check first version structure
        version = data["items"][0]
        assert "id" in version
        assert "strategy_id" in version
        assert "name" in version
        assert isinstance(version["id"], int)
        assert isinstance(version["name"], str)
    
    def test_list_strategy_versions_returns_mock_data(self, client: TestClient):
        """Verify mock data matches expected values"""
        response = client.get("/api/v1/wizard/strategy-versions")
        data = response.json()
        
        # Check for known mock versions
        version_ids = [v["id"] for v in data["items"]]
        assert 101 in version_ids
        assert 102 in version_ids
        
        # Check version names
        version_names = [v["name"] for v in data["items"]]
        assert any("Dimkud BIG2" in name for name in version_names)
    
    def test_list_strategy_versions_total_matches_items(self, client: TestClient):
        """Total count should match items length"""
        response = client.get("/api/v1/wizard/strategy-versions")
        data = response.json()
        
        assert data["total"] == len(data["items"])
        assert data["total"] == 2  # We have 2 mock versions


class TestStrategyVersionSchemaEndpoint:
    """Test /api/wizard/strategy-version/{version_id}/schema endpoint"""
    
    def test_get_schema_for_valid_version(self, client: TestClient):
        """GET schema for existing version ID returns JSON schema"""
        response = client.get("/api/v1/wizard/strategy-version/101/schema")
        
        assert response.status_code == 200
        schema = response.json()
        
        # Verify it's a valid JSON schema
        assert "$schema" in schema or "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
    
    def test_get_schema_contains_parameters(self, client: TestClient):
        """Schema should contain strategy parameters"""
        response = client.get("/api/v1/wizard/strategy-version/101/schema")
        schema = response.json()
        
        properties = schema["properties"]
        
        # Check expected parameters for version 101
        assert "rsi_period" in properties
        assert "ema_fast" in properties
        assert "ema_slow" in properties
        assert "take_profit_pct" in properties
        assert "stop_loss_pct" in properties
    
    def test_get_schema_parameter_constraints(self, client: TestClient):
        """Schema parameters should have proper constraints"""
        response = client.get("/api/v1/wizard/strategy-version/101/schema")
        schema = response.json()
        
        rsi = schema["properties"]["rsi_period"]
        
        # Check type and constraints
        assert rsi["type"] == "integer"
        assert "minimum" in rsi
        assert "maximum" in rsi
        assert "default" in rsi
        assert rsi["minimum"] == 2
        assert rsi["maximum"] == 100
        assert rsi["default"] == 14
    
    def test_get_schema_required_fields(self, client: TestClient):
        """Schema should specify required fields"""
        response = client.get("/api/v1/wizard/strategy-version/101/schema")
        schema = response.json()
        
        assert "required" in schema
        assert isinstance(schema["required"], list)
        assert "rsi_period" in schema["required"]
        assert "ema_fast" in schema["required"]
        assert "ema_slow" in schema["required"]
    
    def test_get_schema_for_different_version(self, client: TestClient):
        """Different versions should return different schemas"""
        response_101 = client.get("/api/v1/wizard/strategy-version/101/schema")
        response_102 = client.get("/api/v1/wizard/strategy-version/102/schema")
        
        assert response_101.status_code == 200
        assert response_102.status_code == 200
        
        schema_101 = response_101.json()
        schema_102 = response_102.json()
        
        # Version 101 has take_profit_pct, version 102 doesn't
        assert "take_profit_pct" in schema_101["properties"]
        assert "take_profit_pct" not in schema_102["properties"]
    
    def test_get_schema_for_nonexistent_version(self, client: TestClient):
        """Non-existent version should return empty schema"""
        response = client.get("/api/v1/wizard/strategy-version/999/schema")
        
        assert response.status_code == 200
        schema = response.json()
        
        # Should return fallback empty schema
        assert schema["type"] == "object"
        assert schema["properties"] == {}
    
    def test_get_schema_with_zero_version_id(self, client: TestClient):
        """Version ID 0 should return empty schema"""
        response = client.get("/api/v1/wizard/strategy-version/0/schema")
        
        assert response.status_code == 200
        schema = response.json()
        assert schema["type"] == "object"
        assert schema["properties"] == {}
    
    def test_get_schema_with_negative_version_id(self, client: TestClient):
        """Negative version ID should return empty schema"""
        response = client.get("/api/v1/wizard/strategy-version/-1/schema")
        
        assert response.status_code == 200
        schema = response.json()
        assert schema["type"] == "object"


class TestPresetsEndpoint:
    """Test /api/wizard/presets endpoint"""
    
    def test_list_all_presets_without_filter(self, client: TestClient):
        """GET /presets without version_id returns all presets"""
        response = client.get("/api/v1/wizard/presets")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] == len(data["items"])
        assert data["total"] >= 3  # We have 3 mock presets total
    
    def test_list_presets_filtered_by_version(self, client: TestClient):
        """GET /presets?version_id=101 returns only presets for that version"""
        response = client.get("/api/v1/wizard/presets?version_id=101")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert data["total"] == 2  # Version 101 has 2 presets
        
        # Check preset names
        preset_names = [p["name"] for p in data["items"]]
        assert "Default" in preset_names
        assert "Aggressive" in preset_names
    
    def test_list_presets_for_version_102(self, client: TestClient):
        """Version 102 should have its own presets"""
        response = client.get("/api/v1/wizard/presets?version_id=102")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 1  # Version 102 has 1 preset
        assert data["items"][0]["name"] == "Conservative"
    
    def test_list_presets_for_nonexistent_version(self, client: TestClient):
        """Non-existent version should return empty list"""
        response = client.get("/api/v1/wizard/presets?version_id=999")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_preset_structure(self, client: TestClient):
        """Presets should have required structure"""
        response = client.get("/api/v1/wizard/presets?version_id=101")
        data = response.json()
        
        preset = data["items"][0]
        
        # Check required fields
        assert "id" in preset
        assert "name" in preset
        assert "params" in preset
        assert isinstance(preset["params"], dict)
    
    def test_preset_parameters(self, client: TestClient):
        """Preset parameters should match schema"""
        response = client.get("/api/v1/wizard/presets?version_id=101")
        data = response.json()
        
        default_preset = next(p for p in data["items"] if p["name"] == "Default")
        params = default_preset["params"]
        
        # Check parameters exist
        assert "rsi_period" in params
        assert "ema_fast" in params
        assert "ema_slow" in params
        
        # Check default values
        assert params["rsi_period"] == 14
        assert params["ema_fast"] == 12
        assert params["ema_slow"] == 26
    
    def test_all_presets_total_count(self, client: TestClient):
        """Total count without filter should include all presets"""
        response = client.get("/api/v1/wizard/presets")
        data = response.json()
        
        # We have 2 presets for v101 + 1 for v102 = 3 total
        assert data["total"] == 3
        assert len(data["items"]) == 3
    
    def test_preset_ids_unique(self, client: TestClient):
        """All preset IDs should be unique"""
        response = client.get("/api/v1/wizard/presets")
        data = response.json()
        
        preset_ids = [p["id"] for p in data["items"]]
        assert len(preset_ids) == len(set(preset_ids))  # No duplicates


class TestQuickBacktestEndpoint:
    """Test /api/wizard/backtests/quick endpoint"""
    
    def test_quick_backtest_success(self, client: TestClient):
        """POST /backtests/quick returns mock results"""
        payload = {
            "version_id": 101,
            "params": {
                "rsi_period": 14,
                "ema_fast": 12,
                "ema_slow": 26
            },
            "symbol": "BTCUSDT",
            "timeframe": "1h"
        }
        
        response = client.post("/api/v1/wizard/backtests/quick", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "metrics" in data
        assert "equity_preview" in data
        assert "warnings" in data
    
    def test_quick_backtest_metrics(self, client: TestClient):
        """Quick backtest should return performance metrics"""
        payload = {"test": "data"}
        
        response = client.post("/api/v1/wizard/backtests/quick", json=payload)
        data = response.json()
        
        metrics = data["metrics"]
        
        # Check expected metrics
        assert "win_rate" in metrics
        assert "profit_factor" in metrics
        assert "max_dd" in metrics
        
        # Check metric types
        assert isinstance(metrics["win_rate"], (int, float))
        assert isinstance(metrics["profit_factor"], (int, float))
        assert isinstance(metrics["max_dd"], (int, float))
    
    def test_quick_backtest_equity_preview(self, client: TestClient):
        """Equity preview should be a list of values"""
        payload = {"strategy": "test"}
        
        response = client.post("/api/v1/wizard/backtests/quick", json=payload)
        data = response.json()
        
        equity = data["equity_preview"]
        
        assert isinstance(equity, list)
        assert len(equity) > 0
        assert all(isinstance(v, (int, float)) for v in equity)
    
    def test_quick_backtest_warnings(self, client: TestClient):
        """Warnings should be a list"""
        payload = {}
        
        response = client.post("/api/v1/wizard/backtests/quick", json=payload)
        data = response.json()
        
        assert isinstance(data["warnings"], list)
    
    def test_quick_backtest_with_empty_payload(self, client: TestClient):
        """Empty payload should still return mock results"""
        response = client.post("/api/v1/wizard/backtests/quick", json={})
        
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "equity_preview" in data
    
    def test_quick_backtest_with_complex_payload(self, client: TestClient):
        """Complex payload should be accepted"""
        payload = {
            "version_id": 101,
            "params": {
                "rsi_period": 21,
                "ema_fast": 9,
                "ema_slow": 21,
                "take_profit_pct": 2.0,
                "stop_loss_pct": 1.0
            },
            "symbol": "ETHUSDT",
            "timeframe": "4h",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
        
        response = client.post("/api/v1/wizard/backtests/quick", json=payload)
        assert response.status_code == 200


class TestCreateBotEndpoint:
    """Test /api/wizard/bots endpoint"""
    
    def test_create_bot_success(self, client: TestClient):
        """POST /bots creates new bot"""
        payload = {
            "name": "My Trading Bot",
            "version_id": 101,
            "params": {
                "rsi_period": 14,
                "ema_fast": 12,
                "ema_slow": 26
            },
            "symbol": "BTCUSDT",
            "timeframe": "1h"
        }
        
        response = client.post("/api/v1/wizard/bots", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "bot_id" in data
        assert "status" in data
    
    def test_create_bot_returns_id(self, client: TestClient):
        """Bot creation should return bot ID"""
        payload = {"name": "Test Bot"}
        
        response = client.post("/api/v1/wizard/bots", json=payload)
        data = response.json()
        
        assert isinstance(data["bot_id"], int)
        assert data["bot_id"] > 0
    
    def test_create_bot_status(self, client: TestClient):
        """Bot should be created with status"""
        payload = {"test": "data"}
        
        response = client.post("/api/v1/wizard/bots", json=payload)
        data = response.json()
        
        assert data["status"] == "created"
    
    def test_create_bot_with_empty_payload(self, client: TestClient):
        """Empty payload should still create bot"""
        response = client.post("/api/v1/wizard/bots", json={})
        
        assert response.status_code == 200
        data = response.json()
        assert "bot_id" in data
    
    def test_create_bot_with_full_config(self, client: TestClient):
        """Complete configuration should be accepted"""
        payload = {
            "name": "Advanced Bot",
            "version_id": 102,
            "params": {
                "rsi_period": 21,
                "ema_fast": 10,
                "ema_slow": 30
            },
            "symbol": "SOLUSDT",
            "timeframe": "15m",
            "leverage": 3,
            "capital": 1000.0,
            "max_positions": 3
        }
        
        response = client.post("/api/v1/wizard/bots", json=payload)
        assert response.status_code == 200
        assert response.json()["bot_id"] == 9001


class TestWizardEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_get_schema_with_very_large_version_id(self, client: TestClient):
        """Very large version ID should handle gracefully"""
        response = client.get("/api/v1/wizard/strategy-version/999999999/schema")
        assert response.status_code == 200
        assert response.json()["type"] == "object"
    
    def test_presets_with_zero_version_id(self, client: TestClient):
        """version_id=0 should return empty presets"""
        response = client.get("/api/v1/wizard/presets?version_id=0")
        assert response.status_code == 200
        assert response.json()["total"] == 0
    
    def test_multiple_preset_queries(self, client: TestClient):
        """Multiple calls should return consistent results"""
        response1 = client.get("/api/v1/wizard/presets?version_id=101")
        response2 = client.get("/api/v1/wizard/presets?version_id=101")
        
        assert response1.json() == response2.json()
    
    def test_quick_backtest_no_content_type(self, client: TestClient):
        """Request without proper content type should fail gracefully"""
        # Note: TestClient handles this, but endpoint accepts any payload
        response = client.post("/api/v1/wizard/backtests/quick", json={})
        assert response.status_code == 200


class TestWizardIntegration:
    """Test integration scenarios across endpoints"""
    
    def test_full_wizard_flow(self, client: TestClient):
        """Complete workflow: list versions → get schema → get presets → quick backtest → create bot"""
        
        # Step 1: List strategy versions
        versions_response = client.get("/api/v1/wizard/strategy-versions")
        assert versions_response.status_code == 200
        versions = versions_response.json()["items"]
        version_id = versions[0]["id"]
        
        # Step 2: Get schema for selected version
        schema_response = client.get(f"/api/v1/wizard/strategy-version/{version_id}/schema")
        assert schema_response.status_code == 200
        schema = schema_response.json()
        assert "properties" in schema
        
        # Step 3: Get presets for version
        presets_response = client.get(f"/api/v1/wizard/presets?version_id={version_id}")
        assert presets_response.status_code == 200
        presets = presets_response.json()["items"]
        assert len(presets) > 0
        
        # Step 4: Run quick backtest with preset params
        preset_params = presets[0]["params"]
        backtest_payload = {
            "version_id": version_id,
            "params": preset_params,
            "symbol": "BTCUSDT"
        }
        backtest_response = client.post("/api/v1/wizard/backtests/quick", json=backtest_payload)
        assert backtest_response.status_code == 200
        assert "metrics" in backtest_response.json()
        
        # Step 5: Create bot with tested params
        bot_payload = {
            "version_id": version_id,
            "params": preset_params,
            "name": "Test Bot"
        }
        bot_response = client.post("/api/v1/wizard/bots", json=bot_payload)
        assert bot_response.status_code == 200
        assert "bot_id" in bot_response.json()
    
    def test_version_consistency(self, client: TestClient):
        """Versions, schemas, and presets should be consistent"""
        # Get all versions
        versions = client.get("/api/v1/wizard/strategy-versions").json()["items"]
        
        for version in versions:
            version_id = version["id"]
            
            # Each version should have a schema
            schema = client.get(f"/api/v1/wizard/strategy-version/{version_id}/schema").json()
            assert "properties" in schema
            
            # Each version should have presets (or empty list)
            presets = client.get(f"/api/v1/wizard/presets?version_id={version_id}").json()
            assert "items" in presets
    
    def test_preset_params_match_schema(self, client: TestClient):
        """Preset parameters should match schema requirements"""
        # Get version 101 schema and presets
        schema = client.get("/api/v1/wizard/strategy-version/101/schema").json()
        presets = client.get("/api/v1/wizard/presets?version_id=101").json()["items"]
        
        required_fields = schema.get("required", [])
        
        for preset in presets:
            params = preset["params"]
            
            # Check all required fields are present
            for field in required_fields:
                assert field in params, f"Preset {preset['name']} missing required field {field}"


class TestWizardResponseFormats:
    """Test response format consistency"""
    
    def test_all_list_endpoints_have_items_and_total(self, client: TestClient):
        """All list endpoints should return {items: [], total: N} format"""
        endpoints = [
            "/api/v1/wizard/strategy-versions",
            "/api/v1/wizard/presets",
            "/api/v1/wizard/presets?version_id=101"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            data = response.json()
            
            assert "items" in data, f"{endpoint} missing 'items'"
            assert "total" in data, f"{endpoint} missing 'total'"
            assert isinstance(data["items"], list), f"{endpoint} items not a list"
            assert isinstance(data["total"], int), f"{endpoint} total not an int"
    
    def test_quick_backtest_response_format(self, client: TestClient):
        """Quick backtest should have consistent response format"""
        response = client.post("/api/v1/wizard/backtests/quick", json={})
        data = response.json()
        
        assert "metrics" in data
        assert "equity_preview" in data
        assert "warnings" in data
        assert isinstance(data["metrics"], dict)
        assert isinstance(data["equity_preview"], list)
        assert isinstance(data["warnings"], list)
    
    def test_create_bot_response_format(self, client: TestClient):
        """Bot creation should have consistent response format"""
        response = client.post("/api/v1/wizard/bots", json={})
        data = response.json()
        
        assert "bot_id" in data
        assert "status" in data
        assert isinstance(data["bot_id"], int)
        assert isinstance(data["status"], str)
