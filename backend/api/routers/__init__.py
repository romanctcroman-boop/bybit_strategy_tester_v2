"""
API Routers

Экспорт всех роутеров для удобного импорта.
"""

from backend.api.routers.data import router as data_router
from backend.api.routers.backtest import router as backtest_router
from backend.api.routers.optimize import router as optimize_router

__all__ = [
    "data_router",
    "backtest_router",
    "optimize_router",
]
