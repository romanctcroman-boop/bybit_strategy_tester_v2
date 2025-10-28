"""
Тесты для RBAC модуля

Проверяет:
1. UserLevel enum
2. get_user_level() функцию
3. check_level_permission() логику
4. require_level() декоратор
5. get_available_features() маппинг
"""

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from backend.core.rbac import (
    UserLevel,
    get_user_level,
    check_level_permission,
    require_level,
    get_available_features,
    is_basic_or_higher,
    is_advanced_or_higher,
    is_expert,
)


def test_user_level_enum():
    """Тест UserLevel enum values"""
    assert UserLevel.BASIC.value == "basic"
    assert UserLevel.ADVANCED.value == "advanced"
    assert UserLevel.EXPERT.value == "expert"
    
    # Проверка создания из строки
    assert UserLevel("basic") == UserLevel.BASIC
    assert UserLevel("advanced") == UserLevel.ADVANCED
    assert UserLevel("expert") == UserLevel.EXPERT


def test_get_user_level():
    """Тест получения уровня из заголовка"""
    # Default level
    assert get_user_level(None) == UserLevel.BASIC
    
    # Valid levels
    assert get_user_level("basic") == UserLevel.BASIC
    assert get_user_level("advanced") == UserLevel.ADVANCED
    assert get_user_level("expert") == UserLevel.EXPERT
    
    # Case insensitive
    assert get_user_level("BASIC") == UserLevel.BASIC
    assert get_user_level("Advanced") == UserLevel.ADVANCED
    
    # Invalid level -> fallback to BASIC
    assert get_user_level("invalid") == UserLevel.BASIC
    assert get_user_level("") == UserLevel.BASIC


def test_check_level_permission():
    """Тест проверки иерархии уровней"""
    # BASIC level tests
    assert check_level_permission(UserLevel.BASIC, UserLevel.BASIC) is True
    assert check_level_permission(UserLevel.BASIC, UserLevel.ADVANCED) is True
    assert check_level_permission(UserLevel.BASIC, UserLevel.EXPERT) is True
    
    # ADVANCED level tests
    assert check_level_permission(UserLevel.ADVANCED, UserLevel.BASIC) is False
    assert check_level_permission(UserLevel.ADVANCED, UserLevel.ADVANCED) is True
    assert check_level_permission(UserLevel.ADVANCED, UserLevel.EXPERT) is True
    
    # EXPERT level tests
    assert check_level_permission(UserLevel.EXPERT, UserLevel.BASIC) is False
    assert check_level_permission(UserLevel.EXPERT, UserLevel.ADVANCED) is False
    assert check_level_permission(UserLevel.EXPERT, UserLevel.EXPERT) is True


def test_convenience_functions():
    """Тест вспомогательных функций"""
    # is_basic_or_higher
    assert is_basic_or_higher(UserLevel.BASIC) is True
    assert is_basic_or_higher(UserLevel.ADVANCED) is True
    assert is_basic_or_higher(UserLevel.EXPERT) is True
    
    # is_advanced_or_higher
    assert is_advanced_or_higher(UserLevel.BASIC) is False
    assert is_advanced_or_higher(UserLevel.ADVANCED) is True
    assert is_advanced_or_higher(UserLevel.EXPERT) is True
    
    # is_expert
    assert is_expert(UserLevel.BASIC) is False
    assert is_expert(UserLevel.ADVANCED) is False
    assert is_expert(UserLevel.EXPERT) is True


def test_get_available_features():
    """Тест получения доступных функций для уровня"""
    # BASIC level
    basic_features = get_available_features(UserLevel.BASIC)
    assert basic_features['view_strategies'] is True
    assert basic_features['run_backtest'] is True
    assert basic_features['export_csv'] is True
    assert basic_features['grid_optimization'] is False
    assert basic_features['walk_forward'] is False
    assert basic_features['monte_carlo'] is False
    assert basic_features['custom_strategies'] is False
    
    # ADVANCED level
    advanced_features = get_available_features(UserLevel.ADVANCED)
    assert advanced_features['view_strategies'] is True
    assert advanced_features['grid_optimization'] is True
    assert advanced_features['walk_forward'] is True
    assert advanced_features['multi_timeframe'] is True
    assert advanced_features['monte_carlo'] is False
    assert advanced_features['custom_strategies'] is False
    
    # EXPERT level
    expert_features = get_available_features(UserLevel.EXPERT)
    assert expert_features['view_strategies'] is True
    assert expert_features['grid_optimization'] is True
    assert expert_features['walk_forward'] is True
    assert expert_features['monte_carlo'] is True
    assert expert_features['custom_strategies'] is True
    assert expert_features['api_access'] is True


def test_require_level_decorator():
    """Тест декоратора require_level с FastAPI"""
    app = FastAPI()
    
    @app.get("/basic")
    @require_level(UserLevel.BASIC)
    async def basic_endpoint(user_level: UserLevel = Depends(get_user_level)):
        return {"level": user_level.value}
    
    @app.get("/advanced")
    @require_level(UserLevel.ADVANCED)
    async def advanced_endpoint(user_level: UserLevel = Depends(get_user_level)):
        return {"level": user_level.value}
    
    @app.get("/expert")
    @require_level(UserLevel.EXPERT)
    async def expert_endpoint(user_level: UserLevel = Depends(get_user_level)):
        return {"level": user_level.value}
    
    client = TestClient(app)
    
    # BASIC endpoint - доступен всем
    response = client.get("/basic")
    assert response.status_code == 200
    
    response = client.get("/basic", headers={"X-User-Level": "advanced"})
    assert response.status_code == 200
    
    response = client.get("/basic", headers={"X-User-Level": "expert"})
    assert response.status_code == 200
    
    # ADVANCED endpoint - только advanced и expert
    response = client.get("/advanced", headers={"X-User-Level": "basic"})
    assert response.status_code == 403
    
    response = client.get("/advanced", headers={"X-User-Level": "advanced"})
    assert response.status_code == 200
    
    response = client.get("/advanced", headers={"X-User-Level": "expert"})
    assert response.status_code == 200
    
    # EXPERT endpoint - только expert
    response = client.get("/expert", headers={"X-User-Level": "basic"})
    assert response.status_code == 403
    
    response = client.get("/expert", headers={"X-User-Level": "advanced"})
    assert response.status_code == 403
    
    response = client.get("/expert", headers={"X-User-Level": "expert"})
    assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
