"""
RBAC Router - Endpoints для управления уровнями доступа

Предоставляет:
1. GET /features - получить доступные функции для текущего уровня
2. GET /level - получить текущий уровень пользователя
"""

from fastapi import APIRouter, Depends, Header
from typing import Optional

from backend.core.rbac import (
    UserLevel,
    get_user_level,
    get_available_features,
)

router = APIRouter()


@router.get("/rbac/features")
async def get_user_features(
    user_level: UserLevel = Depends(get_user_level)
):
    """
    Получить доступные функции для текущего уровня пользователя
    
    Headers:
        X-User-Level: basic | advanced | expert (optional, default: basic)
    
    Returns:
        dict: Маппинг функций на boolean (доступна/недоступна)
    
    Example:
        GET /api/rbac/features
        X-User-Level: advanced
        
        Response:
        {
            "view_strategies": true,
            "run_backtest": true,
            "export_csv": true,
            "grid_optimization": true,
            "walk_forward": true,
            "multi_timeframe": true,
            "monte_carlo": false,
            "custom_strategies": false,
            "api_access": false
        }
    """
    return get_available_features(user_level)


@router.get("/rbac/level")
async def get_current_level(
    x_user_level: Optional[str] = Header(None)
):
    """
    Получить текущий уровень доступа пользователя
    
    Headers:
        X-User-Level: basic | advanced | expert (optional, default: basic)
    
    Returns:
        dict: Информация об уровне доступа
    
    Example:
        GET /api/rbac/level
        X-User-Level: expert
        
        Response:
        {
            "level": "expert",
            "level_name": "EXPERT",
            "description": "Full access to all features"
        }
    """
    level = get_user_level(x_user_level)
    
    descriptions = {
        UserLevel.BASIC: "View strategies, simple backtesting, CSV export",
        UserLevel.ADVANCED: "All Basic features + Grid/WFO optimization, MTF analysis",
        UserLevel.EXPERT: "Full access to all features including Monte Carlo, custom strategies, API",
    }
    
    return {
        "level": level.value,
        "level_name": level.name,
        "description": descriptions[level],
    }
