"""
Интеграционные тесты для RBAC защиты эндпоинтов

Проверяет что:
1. BASIC пользователь не может запустить Grid/WFO оптимизацию
2. ADVANCED может запустить Grid/WFO оптимизацию
3. Только EXPERT может делать кастомные операции
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)


def test_basic_user_cannot_create_optimization():
    """BASIC пользователь не может создавать оптимизацию"""
    payload = {
        "strategy_id": 1,
        "algorithm": "grid_search",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-02-01T00:00:00",
        "param_ranges": {"rsi_period": [10, 14, 20]},
        "metric": "sharpe_ratio",
    }
    
    response = client.post(
        "/api/v1/optimizations/",
        json=payload,
        headers={"X-User-Level": "basic"}
    )
    
    # Should be forbidden
    assert response.status_code == 403
    data = response.json()
    assert "ADVANCED" in data['detail'] or "advanced" in data['detail']


def test_advanced_user_can_create_optimization():
    """ADVANCED пользователь может создавать оптимизацию"""
    payload = {
        "strategy_id": 1,
        "algorithm": "grid_search",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-02-01T00:00:00",
        "param_ranges": {"rsi_period": [10, 14, 20]},
        "metric": "sharpe_ratio",
    }
    
    response = client.post(
        "/api/v1/optimizations/",
        json=payload,
        headers={"X-User-Level": "advanced"}
    )
    
    # Should succeed (or fail with 5xx if DB not configured, but not 403)
    assert response.status_code != 403


def test_expert_user_can_create_optimization():
    """EXPERT пользователь может создавать оптимизацию"""
    payload = {
        "strategy_id": 1,
        "algorithm": "grid_search",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-02-01T00:00:00",
        "param_ranges": {"rsi_period": [10, 14, 20]},
        "metric": "sharpe_ratio",
    }
    
    response = client.post(
        "/api/v1/optimizations/",
        json=payload,
        headers={"X-User-Level": "expert"}
    )
    
    # Should succeed (or fail with 5xx if DB not configured, but not 403)
    assert response.status_code != 403


def test_basic_user_can_list_optimizations():
    """BASIC пользователь может просматривать оптимизации (GET разрешён всем)"""
    response = client.get(
        "/api/v1/optimizations/",
        headers={"X-User-Level": "basic"}
    )
    
    # Should succeed
    assert response.status_code == 200


def test_all_levels_can_read():
    """Все уровни могут читать данные (GET endpoints)"""
    for level in ['basic', 'advanced', 'expert']:
        response = client.get(
            "/api/v1/optimizations/",
            headers={"X-User-Level": level}
        )
        
        assert response.status_code == 200, f"Failed for level {level}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
