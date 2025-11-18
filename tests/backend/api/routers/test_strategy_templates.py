"""
Tests for Strategy Template Library API

Tests cover:
- Template listing (all templates, filtered by category)
- Template retrieval (by ID)
- Parameter validation (type checking, range validation, required params)
- Categories endpoint
- Error handling (invalid template ID, validation errors)
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


client = TestClient(app)


# ============================================================================
# TESTS: List Strategy Templates
# ============================================================================

class TestListTemplates:
    """Tests for GET /api/v1/strategies/templates/"""
    
    def test_list_all_templates(self):
        """Should return all 3 strategy templates"""
        response = client.get("/api/v1/strategies/templates/")
        
        assert response.status_code == 200
        templates = response.json()
        
        assert isinstance(templates, list)
        assert len(templates) == 3
        
        # Verify template IDs
        template_ids = [t["id"] for t in templates]
        assert "bollinger_mean_reversion" in template_ids
        assert "rsi_oversold_overbought" in template_ids
        assert "ma_crossover" in template_ids
    
    def test_list_templates_with_category_filter(self):
        """Should filter templates by category"""
        response = client.get("/api/v1/strategies/templates/?category=Indicator-Based")
        
        assert response.status_code == 200
        templates = response.json()
        
        assert len(templates) == 3  # All templates are Indicator-Based
        assert all(t["category"] == "Indicator-Based" for t in templates)
    
    def test_list_templates_invalid_category(self):
        """Should return empty list for non-existent category"""
        response = client.get("/api/v1/strategies/templates/?category=NonExistent")
        
        assert response.status_code == 200
        templates = response.json()
        assert templates == []
    
    def test_template_structure(self):
        """Should return templates with complete structure"""
        response = client.get("/api/v1/strategies/templates/")
        templates = response.json()
        
        template = templates[0]
        
        # Verify required fields
        assert "id" in template
        assert "name" in template
        assert "description" in template
        assert "category" in template
        assert "parameters" in template
        assert "use_cases" in template
        assert "expected_performance" in template
        
        # Verify parameter structure
        assert isinstance(template["parameters"], list)
        assert len(template["parameters"]) > 0
        
        param = template["parameters"][0]
        assert "name" in param
        assert "type" in param
        assert "default" in param
        assert "description" in param


# ============================================================================
# TESTS: Get Specific Template
# ============================================================================

class TestGetTemplate:
    """Tests for GET /api/v1/strategies/templates/{template_id}"""
    
    def test_get_bollinger_template(self):
        """Should return Bollinger Bands template with all parameters"""
        response = client.get("/api/v1/strategies/templates/bollinger_mean_reversion")
        
        assert response.status_code == 200
        template = response.json()
        
        assert template["id"] == "bollinger_mean_reversion"
        assert template["name"] == "Bollinger Bands Mean Reversion"
        assert template["category"] == "Indicator-Based"
        
        # Verify parameters
        param_names = [p["name"] for p in template["parameters"]]
        assert "bb_period" in param_names
        assert "bb_std_dev" in param_names
        assert "entry_threshold_pct" in param_names
        assert "stop_loss_pct" in param_names
        assert "max_holding_bars" in param_names
    
    def test_get_rsi_template(self):
        """Should return RSI template with all parameters"""
        response = client.get("/api/v1/strategies/templates/rsi_oversold_overbought")
        
        assert response.status_code == 200
        template = response.json()
        
        assert template["id"] == "rsi_oversold_overbought"
        assert template["name"] == "RSI Oversold/Overbought"
        
        # Verify RSI-specific parameters
        param_names = [p["name"] for p in template["parameters"]]
        assert "rsi_period" in param_names
        assert "rsi_oversold" in param_names
        assert "rsi_overbought" in param_names
    
    def test_get_ma_crossover_template(self):
        """Should return MA Crossover template with all parameters"""
        response = client.get("/api/v1/strategies/templates/ma_crossover")
        
        assert response.status_code == 200
        template = response.json()
        
        assert template["id"] == "ma_crossover"
        assert template["name"] == "Moving Average Crossover"
        
        # Verify MA-specific parameters
        param_names = [p["name"] for p in template["parameters"]]
        assert "fast_period" in param_names
        assert "slow_period" in param_names
        assert "ma_type" in param_names
        
        # Verify ma_type has options
        ma_type_param = next(p for p in template["parameters"] if p["name"] == "ma_type")
        assert ma_type_param["options"] == ["SMA", "EMA", "WMA"]
    
    def test_get_template_not_found(self):
        """Should return 404 for non-existent template"""
        response = client.get("/api/v1/strategies/templates/invalid_template")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ============================================================================
# TESTS: Template Categories
# ============================================================================

class TestTemplateCategories:
    """Tests for GET /api/v1/strategies/templates/categories/list"""
    
    def test_list_categories(self):
        """Should return all template categories with counts"""
        response = client.get("/api/v1/strategies/templates/categories/list")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "categories" in data
        assert "total_templates" in data
        
        assert data["total_templates"] == 3
        assert "Indicator-Based" in data["categories"]
        assert data["categories"]["Indicator-Based"] == 3


# ============================================================================
# TESTS: Parameter Validation
# ============================================================================

class TestParameterValidation:
    """Tests for POST /api/v1/strategies/templates/validate"""
    
    def test_validate_valid_parameters(self):
        """Should accept valid parameters"""
        response = client.post(
            "/api/v1/strategies/templates/validate?template_id=bollinger_mean_reversion",
            json={
                "bb_period": 20,
                "bb_std_dev": 2.0,
                "entry_threshold_pct": 0.05,
                "stop_loss_pct": 0.8,
                "max_holding_bars": 48
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["normalized_parameters"] is not None
    
    def test_validate_with_defaults(self):
        """Should use default values for missing parameters"""
        response = client.post(
            "/api/v1/strategies/templates/validate?template_id=bollinger_mean_reversion",
            json={}  # Empty parameters
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["valid"] is True
        normalized = result["normalized_parameters"]
        
        # Should have default values
        assert normalized["bb_period"] == 20
        assert normalized["bb_std_dev"] == 2.0
        assert normalized["entry_threshold_pct"] == 0.05
    
    def test_validate_type_error(self):
        """Should reject invalid parameter types"""
        response = client.post(
            "/api/v1/strategies/templates/validate?template_id=bollinger_mean_reversion",
            json={
                "bb_period": "not_an_int",  # Should be int
                "bb_std_dev": 2.0
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("must be int" in error for error in result["errors"])
    
    def test_validate_range_error(self):
        """Should reject values outside allowed ranges"""
        response = client.post(
            "/api/v1/strategies/templates/validate?template_id=bollinger_mean_reversion",
            json={
                "bb_period": 200,  # Max is 100
                "bb_std_dev": 2.0
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["valid"] is False
        assert any("must be <=" in error for error in result["errors"])
    
    def test_validate_unknown_parameter(self):
        """Should reject unknown parameters"""
        response = client.post(
            "/api/v1/strategies/templates/validate?template_id=bollinger_mean_reversion",
            json={
                "bb_period": 20,
                "unknown_param": 123
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["valid"] is False
        assert any("Unknown parameter" in error for error in result["errors"])
    
    def test_validate_categorical_parameter(self):
        """Should validate categorical parameters against options list"""
        # Valid option
        response = client.post(
            "/api/v1/strategies/templates/validate?template_id=ma_crossover",
            json={"ma_type": "EMA"}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["valid"] is True
        
        # Invalid option
        response = client.post(
            "/api/v1/strategies/templates/validate?template_id=ma_crossover",
            json={"ma_type": "INVALID"}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["valid"] is False
        assert any("must be one of" in error for error in result["errors"])
    
    def test_validate_template_not_found(self):
        """Should return 404 for non-existent template"""
        response = client.post(
            "/api/v1/strategies/templates/validate?template_id=invalid_template",
            json={}
        )
        
        assert response.status_code == 404


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for template workflow"""
    
    def test_full_workflow(self):
        """Test complete workflow: list → get → validate"""
        # 1. List all templates
        response = client.get("/api/v1/strategies/templates/")
        assert response.status_code == 200
        templates = response.json()
        assert len(templates) > 0
        
        # 2. Get first template
        template_id = templates[0]["id"]
        response = client.get(f"/api/v1/strategies/templates/{template_id}")
        assert response.status_code == 200
        template = response.json()
        
        # 3. Extract default parameters
        default_params = {p["name"]: p["default"] for p in template["parameters"]}
        
        # 4. Validate default parameters
        response = client.post(
            f"/api/v1/strategies/templates/validate?template_id={template_id}",
            json=default_params
        )
        assert response.status_code == 200
        result = response.json()
        assert result["valid"] is True
    
    def test_template_consistency(self):
        """Verify all templates have consistent structure"""
        response = client.get("/api/v1/strategies/templates/")
        templates = response.json()
        
        for template in templates:
            # All templates should have these fields
            assert "id" in template
            assert "name" in template
            assert "description" in template
            assert "category" in template
            assert "parameters" in template
            assert "use_cases" in template
            assert "expected_performance" in template
            
            # All parameters should have required fields
            for param in template["parameters"]:
                assert "name" in param
                assert "type" in param
                assert "default" in param
                assert "description" in param
                
                # Numeric types should have min/max
                if param["type"] in ["int", "float"]:
                    assert "min" in param
                    assert "max" in param
