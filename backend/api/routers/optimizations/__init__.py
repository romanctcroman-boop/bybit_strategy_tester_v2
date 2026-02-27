"""
Optimization API sub-router package.

Assembles all optimization sub-routers into a single ``router`` object
that the main application registers at ``/api/v1/optimizations``.

Sub-modules:
- models     : Pydantic models + DB-to-response helpers
- helpers    : Interval normalization, param value generation
- crud       : CRUD endpoints (create, list, get, status, results)
- results    : Results viewer, chart, action, stats endpoints
- workers    : Internal worker/helper functions
- grid_search: Sync grid-search + Optuna search endpoints
- vectorbt   : VectorBT grid-search endpoint
- two_stage  : SSE streaming + two-stage optimization endpoint
"""

from fastapi import APIRouter

# Re-export DB model for backward compatibility
from backend.database.models.optimization import OptimizationStatus  # noqa: F401

# Re-export external model classes used by tests
from backend.optimization.models import (  # noqa: F401
    OptunaSyncRequest,
    SyncOptimizationRequest,
)

from backend.api.routers.optimizations.crud import launch_optimization_task  # noqa: F401
from backend.api.routers.optimizations.crud import router as crud_router
from backend.api.routers.optimizations.grid_search import router as grid_search_router
from backend.api.routers.optimizations.models import (  # noqa: F401
    CreateOptimizationRequest,
    OptimizationResponse,
    OptimizationResultsResponse,
    OptimizationStatusResponse,
    ParamRangeSpec,
    calculate_total_combinations,
    optimization_to_response,
    parse_optimization_type,
)
from backend.api.routers.optimizations.results import (  # noqa: F401
    ApplyParamsRequest,
    ApplyParamsResponse,
    ConvergenceDataResponse,
    SensitivityDataResponse,
    router as results_router,
)
from backend.api.routers.optimizations.two_stage import router as two_stage_router
from backend.api.routers.optimizations.vectorbt import router as vectorbt_router
from backend.api.routers.optimizations.workers import (  # noqa: F401
    _apply_custom_sort_order,
    _calculate_composite_score,
    _compute_weighted_composite,
    _passes_dynamic_constraints,
    _passes_filters,
    _rank_by_multi_criteria,
)

router = APIRouter(tags=["Optimization"])  # Prefix set in app.py

# Order matters: more specific paths first
router.include_router(results_router)  # /stats/summary, /*/charts/*, /*/results/*, etc.
router.include_router(crud_router)  # POST /, GET /, GET /{id}, status, results
router.include_router(grid_search_router)  # /sync/grid-search, /sync/optuna-search
router.include_router(vectorbt_router)  # /vectorbt/grid-search
router.include_router(two_stage_router)  # /vectorbt/grid-search-stream, /two-stage/optimize