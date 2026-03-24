"""
backend/api/routers/backtests/ — Backtests router package.

Modules:
    router.py      — All FastAPI route handlers (HTTP only)
    formatters.py  — Pure helpers: safe type conversion + build_equity_curve_response
    schemas.py     — Pydantic request/response models

Public API (backward-compatible with the original backtests.py module):
    router         — APIRouter instance, imported by app.py
"""

from backend.api.routers.backtests.formatters import (
    _ensure_utc,
    _get_side_value,
    _safe_float,
    _safe_int,
    _safe_str,
    build_equity_curve_response,
    downsample_list,
)
from backend.api.routers.backtests.router import router
from backend.api.routers.backtests.schemas import (
    MTFBacktestRequest,
    MTFBacktestResponse,
    RunFromStrategyRequest,
    RunFromStrategyResponse,
    SaveOptimizationResultRequest,
    SaveOptimizationResultResponse,
)

__all__ = [
    "MTFBacktestRequest",
    "MTFBacktestResponse",
    "RunFromStrategyRequest",
    "RunFromStrategyResponse",
    "SaveOptimizationResultRequest",
    "SaveOptimizationResultResponse",
    "_ensure_utc",
    "_get_side_value",
    "_safe_float",
    "_safe_int",
    "_safe_str",
    "build_equity_curve_response",
    "downsample_list",
    "router",
]
