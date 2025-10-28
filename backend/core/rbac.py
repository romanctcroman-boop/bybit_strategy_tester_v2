"""
RBAC (Role-Based Access Control) Module

Реализация уровней доступа согласно ТЗ:
- BASIC: Базовый уровень (просмотр, простой бэктест)
- ADVANCED: Продвинутый (оптимизация, walk-forward)
- EXPERT: Экспертный (Monte Carlo, кастомные стратегии)

Исправление аномалии #2: Отсутствие уровней доступа
Дата: 27.10.2025
"""

from enum import Enum
from functools import wraps
from typing import Callable, Optional

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


class UserLevel(str, Enum):
    """
    Уровни доступа пользователей
    
    BASIC - Базовый уровень:
      - Просмотр стратегий
      - Запуск простых бэктестов
      - Просмотр результатов
      - Экспорт CSV
      
    ADVANCED - Продвинутый уровень:
      - Все из BASIC
      - Grid Search оптимизация
      - Walk-Forward Optimization
      - Multiple timeframes
      - Кастомные параметры
      
    EXPERT - Экспертный уровень:
      - Все из ADVANCED
      - Monte Carlo симуляция
      - Кастомные стратегии (код)
      - API доступ
      - Массовые операции
    """
    BASIC = "basic"
    ADVANCED = "advanced"
    EXPERT = "expert"


# Mapping endpoints to required levels
ENDPOINT_PERMISSIONS = {
    # Basic level endpoints
    "/api/v1/strategies": UserLevel.BASIC,
    "/api/v1/backtests": UserLevel.BASIC,
    "/api/v1/marketdata": UserLevel.BASIC,
    
    # Advanced level endpoints
    "/api/v1/optimizations": UserLevel.ADVANCED,
    "/api/v1/strategies/*/walk-forward": UserLevel.ADVANCED,
    
    # Expert level endpoints
    "/api/v1/monte-carlo": UserLevel.EXPERT,
    "/api/v1/strategies/custom": UserLevel.EXPERT,
    "/api/v1/bulk": UserLevel.EXPERT,
}


def get_user_level(x_user_level: Optional[str] = Header(None)) -> UserLevel:
    """
    Получить уровень пользователя из заголовка
    
    Args:
        x_user_level: Заголовок X-User-Level (basic/advanced/expert)
        
    Returns:
        UserLevel enum
        
    Примеры:
        >>> # В запросе:
        >>> headers = {"X-User-Level": "advanced"}
        >>> level = get_user_level(headers["X-User-Level"])
    """
    if x_user_level is None:
        # По умолчанию - базовый уровень
        return UserLevel.BASIC
    
    try:
        return UserLevel(x_user_level.lower())
    except ValueError:
        # Неизвестный уровень - вернуть базовый
        return UserLevel.BASIC


def check_level_permission(required_level: UserLevel, user_level: UserLevel) -> bool:
    """
    Проверить имеет ли пользователь необходимый уровень доступа
    
    Иерархия: EXPERT >= ADVANCED >= BASIC
    
    Args:
        required_level: Требуемый уровень для операции
        user_level: Уровень пользователя
        
    Returns:
        True если доступ разрешен
        
    Examples:
        >>> check_level_permission(UserLevel.BASIC, UserLevel.ADVANCED)
        True  # ADVANCED >= BASIC
        
        >>> check_level_permission(UserLevel.EXPERT, UserLevel.BASIC)
        False  # BASIC < EXPERT
    """
    level_hierarchy = {
        UserLevel.BASIC: 1,
        UserLevel.ADVANCED: 2,
        UserLevel.EXPERT: 3,
    }
    
    return level_hierarchy[user_level] >= level_hierarchy[required_level]


def require_level(required_level: UserLevel):
    """
    Декоратор для проверки уровня доступа к endpoint
    
    Args:
        required_level: Минимальный требуемый уровень
        
    Raises:
        HTTPException: 403 если доступ запрещен
        
    Example:
        >>> @app.get("/api/v1/expert-feature")
        >>> @require_level(UserLevel.EXPERT)
        >>> async def expert_endpoint(user_level: UserLevel = Depends(get_user_level)):
        >>>     return {"message": "Expert only"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Получаем user_level из kwargs (FastAPI dependency)
            user_level = kwargs.get('user_level')
            
            if user_level is None:
                # Если не передан, пытаемся получить из заголовков
                request: Request = kwargs.get('request')
                if request:
                    level_header = request.headers.get('x-user-level', 'basic')
                    user_level = UserLevel(level_header.lower())
                else:
                    user_level = UserLevel.BASIC
            
            # Проверка доступа
            if not check_level_permission(required_level, user_level):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Insufficient permissions",
                        "required_level": required_level.value,
                        "your_level": user_level.value,
                        "message": f"This endpoint requires {required_level.value} level or higher. "
                                   f"Your current level: {user_level.value}"
                    }
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class RBACMiddleware(BaseHTTPMiddleware):
    """
    Middleware для автоматической проверки RBAC на всех запросах
    
    Проверяет заголовок X-User-Level и сопоставляет с требуемым уровнем для endpoint.
    
    Использование:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.add_middleware(RBACMiddleware)
    """
    
    async def dispatch(self, request: Request, call_next):
        # Получаем уровень пользователя из заголовка
        user_level_header = request.headers.get('x-user-level', 'basic')
        
        try:
            user_level = UserLevel(user_level_header.lower())
        except ValueError:
            user_level = UserLevel.BASIC
        
        # Добавляем уровень в state для доступа в endpoints
        request.state.user_level = user_level
        
        # Проверяем доступ к endpoint
        path = request.url.path
        
        # Находим требуемый уровень для endpoint
        required_level = None
        for endpoint_pattern, level in ENDPOINT_PERMISSIONS.items():
            # Простое сопоставление (можно улучшить с regex)
            if endpoint_pattern in path or path.startswith(endpoint_pattern.replace('*', '')):
                required_level = level
                break
        
        # Если endpoint требует проверки уровня
        if required_level and not check_level_permission(required_level, user_level):
            return HTTPException(
                status_code=403,
                detail={
                    "error": "Insufficient permissions",
                    "required_level": required_level.value,
                    "your_level": user_level.value,
                    "endpoint": path,
                }
            )
        
        # Продолжаем обработку запроса
        response = await call_next(request)
        
        # Добавляем заголовок с уровнем доступа в ответ
        response.headers["X-User-Level"] = user_level.value
        
        return response


# Convenience functions для проверки конкретных уровней

def is_basic_or_higher(user_level: UserLevel) -> bool:
    """Проверка что пользователь имеет уровень BASIC или выше"""
    return check_level_permission(UserLevel.BASIC, user_level)


def is_advanced_or_higher(user_level: UserLevel) -> bool:
    """Проверка что пользователь имеет уровень ADVANCED или выше"""
    return check_level_permission(UserLevel.ADVANCED, user_level)


def is_expert(user_level: UserLevel) -> bool:
    """Проверка что пользователь имеет уровень EXPERT"""
    return user_level == UserLevel.EXPERT


# Feature flags based on user level

def get_available_features(user_level: UserLevel) -> dict[str, bool]:
    """
    Получить список доступных функций для уровня пользователя
    
    Args:
        user_level: Уровень пользователя
        
    Returns:
        Словарь с флагами доступных функций
        
    Example:
        >>> features = get_available_features(UserLevel.ADVANCED)
        >>> features['monte_carlo']
        False
        >>> features['walk_forward']
        True
    """
    return {
        # Basic features
        'view_strategies': is_basic_or_higher(user_level),
        'run_backtest': is_basic_or_higher(user_level),
        'export_csv': is_basic_or_higher(user_level),
        'view_charts': is_basic_or_higher(user_level),
        
        # Advanced features
        'grid_optimization': is_advanced_or_higher(user_level),
        'walk_forward': is_advanced_or_higher(user_level),
        'multi_timeframe': is_advanced_or_higher(user_level),
        'custom_parameters': is_advanced_or_higher(user_level),
        
        # Expert features
        'monte_carlo': is_expert(user_level),
        'custom_strategies': is_expert(user_level),
        'api_access': is_expert(user_level),
        'bulk_operations': is_expert(user_level),
    }
