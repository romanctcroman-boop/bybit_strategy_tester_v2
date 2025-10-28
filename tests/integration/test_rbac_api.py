"""
Интеграционные тесты для RBAC API endpoints

Проверяет:
1. GET /api/rbac/features - получение доступных функций
2. GET /api/rbac/level - получение текущего уровня
3. Корректную обработку заголовков X-User-Level
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)


def test_get_features_default_level():
    """Тест получения функций для уровня по умолчанию (BASIC)"""
    response = client.get("/api/rbac/features")
    
    assert response.status_code == 200
    features = response.json()
    
    # BASIC level features
    assert features['view_strategies'] is True
    assert features['run_backtest'] is True
    assert features['export_csv'] is True
    
    # Not available for BASIC
    assert features['grid_optimization'] is False
    assert features['walk_forward'] is False
    assert features['monte_carlo'] is False
    assert features['custom_strategies'] is False


def test_get_features_advanced_level():
    """Тест получения функций для ADVANCED уровня"""
    response = client.get(
        "/api/rbac/features",
        headers={"X-User-Level": "advanced"}
    )
    
    assert response.status_code == 200
    features = response.json()
    
    # ADVANCED level features
    assert features['view_strategies'] is True
    assert features['run_backtest'] is True
    assert features['export_csv'] is True
    assert features['grid_optimization'] is True
    assert features['walk_forward'] is True
    assert features['multi_timeframe'] is True
    
    # Not available for ADVANCED
    assert features['monte_carlo'] is False
    assert features['custom_strategies'] is False
    assert features['api_access'] is False


def test_get_features_expert_level():
    """Тест получения функций для EXPERT уровня"""
    response = client.get(
        "/api/rbac/features",
        headers={"X-User-Level": "expert"}
    )
    
    assert response.status_code == 200
    features = response.json()
    
    # All features available for EXPERT
    assert all(features.values()), "All features should be True for EXPERT"
    assert features['view_strategies'] is True
    assert features['monte_carlo'] is True
    assert features['custom_strategies'] is True
    assert features['api_access'] is True


def test_get_level_default():
    """Тест получения уровня по умолчанию"""
    response = client.get("/api/rbac/level")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['level'] == 'basic'
    assert data['level_name'] == 'BASIC'
    assert 'description' in data


def test_get_level_advanced():
    """Тест получения ADVANCED уровня"""
    response = client.get(
        "/api/rbac/level",
        headers={"X-User-Level": "advanced"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['level'] == 'advanced'
    assert data['level_name'] == 'ADVANCED'
    assert 'Grid/WFO' in data['description'] or 'MTF' in data['description']


def test_get_level_expert():
    """Тест получения EXPERT уровня"""
    response = client.get(
        "/api/rbac/level",
        headers={"X-User-Level": "expert"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['level'] == 'expert'
    assert data['level_name'] == 'EXPERT'
    assert 'Full access' in data['description'] or 'Monte Carlo' in data['description']


def test_invalid_level_fallback():
    """Тест fallback к BASIC при невалидном уровне"""
    response = client.get(
        "/api/rbac/features",
        headers={"X-User-Level": "invalid_level"}
    )
    
    assert response.status_code == 200
    features = response.json()
    
    # Should fallback to BASIC
    assert features['view_strategies'] is True
    assert features['grid_optimization'] is False
    assert features['monte_carlo'] is False


def test_case_insensitive_level():
    """Тест case-insensitive обработки уровня"""
    for level in ['EXPERT', 'Expert', 'eXpErT']:
        response = client.get(
            "/api/rbac/level",
            headers={"X-User-Level": level}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['level'] == 'expert'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
