from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import (
    ApiListResponse,
    OptimizationCreate,
    OptimizationEnqueueResponse,
    OptimizationOut,
    OptimizationResultOut,
    OptimizationRunBayesianRequest,
    OptimizationRunGridRequest,
    OptimizationRunWalkForwardRequest,
    OptimizationUpdate,
)


def _get_data_service():
    try:
        from backend.services.data_service import DataService

        return DataService
    except Exception:
        return None


router = APIRouter()


def _to_iso_dict(obj) -> dict:
    d = obj.__dict__.copy()
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _map_result(r) -> dict:
    # Project ORM result to the public schema fields; normalize datetimes to ISO strings if present in metrics
    d = {
        "id": getattr(r, "id", None),
        "optimization_id": getattr(r, "optimization_id", None),
        "params": getattr(r, "params", None),
        "score": getattr(r, "score", None),
        "total_return": getattr(r, "total_return", None),
        "sharpe_ratio": getattr(r, "sharpe_ratio", None),
        "max_drawdown": getattr(r, "max_drawdown", None),
        "win_rate": getattr(r, "win_rate", None),
        "total_trades": getattr(r, "total_trades", None),
        "metrics": getattr(r, "metrics", None),
    }
    # If metrics may contain datetimes, best-effort ISO convert nested top-level values
    if isinstance(d.get("metrics"), dict):
        m = {}
        for k, v in d["metrics"].items():
            if isinstance(v, datetime):
                m[k] = v.isoformat()
            else:
                m[k] = v
        d["metrics"] = m
    return d


def _choose_queue(default_queue: str | None, algo: str) -> str:
    if default_queue and default_queue.strip():
        return default_queue.strip()
    mapping = {
        "grid_search": "optimizations.grid",
        "walk_forward": "optimizations.walk",
        "bayesian": "optimizations.bayes",
    }
    return mapping.get(algo, "optimizations")


@router.get("/", response_model=ApiListResponse[OptimizationOut])
def list_optimizations(
    strategy_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = 100,
    offset: int = 0,
):
    DS = _get_data_service()
    if DS is None:
        return {"items": [], "total": 0}
    with DS() as ds:
        items = ds.get_optimizations(
            strategy_id=strategy_id, status=status, limit=limit, offset=offset
        )
        total = len(items)
        return {"items": [_to_iso_dict(i) for i in items], "total": total}


@router.get("/{optimization_id}", response_model=OptimizationOut)
def get_optimization(optimization_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        opt = ds.get_optimization(optimization_id)
        if not opt:
            raise HTTPException(status_code=404, detail="Optimization not found")
        return _to_iso_dict(opt)


@router.post("/", response_model=OptimizationOut)
def create_optimization(payload: OptimizationCreate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        opt = ds.create_optimization(**payload.model_dump())
        return _to_iso_dict(opt)


@router.put("/{optimization_id}", response_model=OptimizationOut)
def update_optimization(optimization_id: int, payload: OptimizationUpdate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        opt = ds.update_optimization(
            optimization_id, **{k: v for k, v in payload.model_dump(exclude_none=True).items()}
        )
        if not opt:
            raise HTTPException(status_code=404, detail="Optimization not found")
        return _to_iso_dict(opt)


@router.get(
    "/{optimization_id}/results",
    response_model=list[OptimizationResultOut],
)
def list_optimization_results(optimization_id: int, limit: int = 100, offset: int = 0):
    DS = _get_data_service()
    if DS is None:
        return []
    with DS() as ds:
        results = ds.get_optimization_results(
            optimization_id=optimization_id, limit=limit, offset=offset
        )
        return [_map_result(r) for r in results]


@router.get(
    "/{optimization_id}/best",
    response_model=OptimizationResultOut,
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "id": 101,
                        "optimization_id": 42,
                        "params": {"rsi_period": 14, "ema_fast": 12, "ema_slow": 26},
                        "score": 1.2345,
                        "total_return": 0.35,
                        "sharpe_ratio": 1.1,
                        "max_drawdown": -0.12,
                        "win_rate": 0.56,
                        "total_trades": 240,
                        "metrics": {"profit_factor": 1.8},
                    }
                }
            }
        }
    },
)
def best_optimization_result(optimization_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        r = ds.get_best_optimization_result(optimization_id)
        if not r:
            raise HTTPException(status_code=404, detail="not found")
        return _map_result(r)


# ========================
# Enqueue optimization tasks
# ========================


def _iso(v) -> str:
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


@router.post(
    "/{optimization_id}/run/grid",
    response_model=OptimizationEnqueueResponse,
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "5f1b7a34-2e40-4f7e-9f07-f2b17b8f5e4a",
                        "optimization_id": 42,
                        "queue": "optimizations.grid",
                        "status": "queued",
                    }
                }
            }
        }
    },
)
def enqueue_grid_search(optimization_id: int, payload: OptimizationRunGridRequest):
    # Lazy imports to avoid impacting environments without Celery
    try:
        from backend.tasks.optimize_tasks import grid_search_task
    except Exception as exc:
        raise HTTPException(status_code=501, detail=f"Celery tasks not available: {exc}")

    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )

    with DS() as ds:
        opt = ds.get_optimization(optimization_id)
        if not opt:
            raise HTTPException(status_code=404, detail="Optimization not found")

        # Build arguments from DB record and payload overrides
        symbol = getattr(opt, "symbol", None)
        interval = getattr(opt, "timeframe", None)
        start_date = _iso(getattr(opt, "start_date", None))
        end_date = _iso(getattr(opt, "end_date", None))
        metric = payload.metric or getattr(opt, "metric", "sharpe_ratio")
        strategy_config = payload.strategy_config or (getattr(opt, "config", {}) or {})
        param_space = payload.param_space or (getattr(opt, "param_ranges", None) or {})

        queue = _choose_queue(payload.queue, "grid_search")

        # Update status to queued
        try:
            ds.update_optimization(optimization_id, status="queued")
        except Exception:
            pass

        # Enqueue task
        async_result = grid_search_task.apply_async(
            kwargs=dict(
                optimization_id=optimization_id,
                strategy_config=strategy_config,
                param_space=param_space,
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                metric=metric,
            ),
            queue=queue,
        )

        return {
            "task_id": async_result.id,
            "optimization_id": optimization_id,
            "queue": queue,
            "status": "queued",
        }


@router.post(
    "/{optimization_id}/run/walk-forward",
    response_model=OptimizationEnqueueResponse,
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "7a2b915a-1c2d-4f89-9a0e-3e6d0e2b1c5f",
                        "optimization_id": 42,
                        "queue": "optimizations.walk",
                        "status": "queued",
                    }
                }
            }
        }
    },
)
def enqueue_walk_forward(optimization_id: int, payload: OptimizationRunWalkForwardRequest):
    try:
        from backend.tasks.optimize_tasks import walk_forward_task
    except Exception as exc:
        raise HTTPException(status_code=501, detail=f"Celery tasks not available: {exc}")

    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )

    with DS() as ds:
        opt = ds.get_optimization(optimization_id)
        if not opt:
            raise HTTPException(status_code=404, detail="Optimization not found")

        symbol = getattr(opt, "symbol", None)
        interval = getattr(opt, "timeframe", None)
        start_date = _iso(getattr(opt, "start_date", None))
        end_date = _iso(getattr(opt, "end_date", None))
        metric = payload.metric or getattr(opt, "metric", "sharpe_ratio")
        strategy_config = payload.strategy_config or (getattr(opt, "config", {}) or {})
        param_space = payload.param_space or (getattr(opt, "param_ranges", None) or {})
        queue = _choose_queue(payload.queue, "walk_forward")

        # Update status to queued
        try:
            ds.update_optimization(optimization_id, status="queued")
        except Exception:
            pass

        async_result = walk_forward_task.apply_async(
            kwargs=dict(
                optimization_id=optimization_id,
                strategy_config=strategy_config,
                param_space=param_space,
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                train_size=payload.train_size,
                test_size=payload.test_size,
                step_size=payload.step_size,
                metric=metric,
            ),
            queue=queue,
        )

        return {
            "task_id": async_result.id,
            "optimization_id": optimization_id,
            "queue": queue,
            "status": "queued",
        }


@router.post(
    "/{optimization_id}/run/bayesian",
    response_model=OptimizationEnqueueResponse,
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "1a2b3c4d-5e6f-7091-2233-445566778899",
                        "optimization_id": 42,
                        "queue": "optimizations.bayes",
                        "status": "queued",
                    }
                }
            }
        }
    },
)
def enqueue_bayesian(optimization_id: int, payload: OptimizationRunBayesianRequest):
    try:
        from backend.tasks.optimize_tasks import bayesian_optimization_task
    except Exception as exc:
        raise HTTPException(status_code=501, detail=f"Celery tasks not available: {exc}")

    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )

    with DS() as ds:
        opt = ds.get_optimization(optimization_id)
        if not opt:
            raise HTTPException(status_code=404, detail="Optimization not found")

        symbol = getattr(opt, "symbol", None)
        interval = getattr(opt, "timeframe", None)
        start_date = _iso(getattr(opt, "start_date", None))
        end_date = _iso(getattr(opt, "end_date", None))
        metric = payload.metric or getattr(opt, "metric", "sharpe_ratio")
        strategy_config = payload.strategy_config or (getattr(opt, "config", {}) or {})
        queue = _choose_queue(payload.queue, "bayesian")

        # Update status to queued
        try:
            ds.update_optimization(optimization_id, status="queued")
        except Exception:
            pass

        async_result = bayesian_optimization_task.apply_async(
            kwargs=dict(
                optimization_id=optimization_id,
                strategy_config=strategy_config,
                param_space=payload.param_space,
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                n_trials=payload.n_trials,
                metric=metric,
                direction=payload.direction,
                n_jobs=payload.n_jobs,
                random_state=payload.random_state,
            ),
            queue=queue,
        )

        return {
            "task_id": async_result.id,
            "optimization_id": optimization_id,
            "queue": queue,
            "status": "queued",
        }
