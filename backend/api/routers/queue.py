"""Queue Router - API endpoints for managing the Redis task queue."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from backend.api.schemas import BacktestCreate
from backend.queue import queue_adapter

DataServiceFactory = Callable[[], Any]
QueueAdapterDependency = Any


router = APIRouter(prefix="/queue", tags=["queue"])


class TaskResponse(BaseModel):
    """Ответ при отправке задачи"""
    task_id: str
    status: str = "submitted"
    message: str


class QueueMetricsResponse(BaseModel):
    """Метрики очереди"""
    tasks_submitted: int
    tasks_completed: int
    tasks_failed: int
    tasks_timeout: int
    active_tasks: int


class BacktestRunRequest(BaseModel):
    """Запрос на запуск бэктеста"""
    backtest_id: int
    priority: int = 5  # 1-20, где 20 = highest


class OptimizationRunRequest(BaseModel):
    """Запрос на запуск оптимизации"""
    optimization_id: int
    optimization_type: str  # 'grid', 'walk_forward', 'bayesian'
    priority: int = 5


def get_queue_adapter_dependency() -> QueueAdapterDependency:
    """Return the default queue adapter module (override-friendly for tests)."""
    return queue_adapter


def get_data_service_factory() -> DataServiceFactory:
    """Return a callable that yields a DataService context manager."""
    from backend.services.data_service import DataService

    def _factory() -> Any:
        return DataService()

    return _factory


def _ensure_entity(entity: Any, *, not_found_message: str) -> Any:
    if entity is None:
        raise HTTPException(status_code=404, detail=not_found_message)
    return entity


@router.post("/backtest/run", response_model=TaskResponse)
async def run_backtest(
    request: BacktestRunRequest,
    data_service_factory: DataServiceFactory = Depends(get_data_service_factory),
    queue: QueueAdapterDependency = Depends(get_queue_adapter_dependency),
):
    """
    Запустить бэктест через Redis Queue
    
    Args:
        request: Параметры запуска (backtest_id, priority)
        
    Returns:
        task_id и статус
        
    Example:
        POST /queue/backtest/run
        {
            "backtest_id": 123,
            "priority": 10
        }
    """
    try:
        # Получить backtest из БД
        with data_service_factory() as ds:
            backtest = _ensure_entity(
                ds.get_backtest(request.backtest_id),
                not_found_message=f"Backtest {request.backtest_id} not found",
            )

            _ensure_entity(
                ds.get_strategy(backtest.strategy_id),
                not_found_message=f"Strategy {backtest.strategy_id} not found",
            )

        task_id = await queue.submit_backtest(
            backtest_id=request.backtest_id,
            strategy_config=backtest.config or {},
            symbol=backtest.symbol,
            interval=backtest.timeframe,
            start_date=backtest.start_date.isoformat(),
            end_date=backtest.end_date.isoformat(),
            initial_capital=backtest.initial_capital,
            priority=request.priority,
        )
        
        logger.info(
            f"📤 Submitted backtest {request.backtest_id} to queue: {task_id}"
        )
        
        return TaskResponse(
            task_id=task_id,
            status="submitted",
            message=f"Backtest {request.backtest_id} submitted to queue"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit backtest: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit backtest: {str(e)}"
        )


@router.post("/backtest/create-and-run", response_model=dict[str, Any])
async def create_and_run_backtest(
    payload: BacktestCreate,
    data_service_factory: DataServiceFactory = Depends(get_data_service_factory),
    queue: QueueAdapterDependency = Depends(get_queue_adapter_dependency),
):
    """
    Создать backtest и сразу запустить через очередь
    
    Комбинированный endpoint который:
    1. Создаёт backtest в БД
    2. Отправляет его в очередь на выполнение
    
    Args:
        payload: Параметры бэктеста
        
    Returns:
        backtest_id, task_id и статус
    """
    try:
        # 1. Создать backtest
        with data_service_factory() as ds:
            # Проверить strategy
            _ensure_entity(
                ds.get_strategy(payload.strategy_id),
                not_found_message=f"Strategy {payload.strategy_id} not found",
            )
            
            # ✅ FIX: Filter payload to only include fields accepted by create_backtest()
            backtest_params = {
                "strategy_id": payload.strategy_id,
                "symbol": payload.symbol,
                "timeframe": payload.timeframe,
                "start_date": payload.start_date,
                "end_date": payload.end_date,
                "initial_capital": payload.initial_capital,
                "leverage": payload.leverage or 1,
                "commission": payload.commission or 0.0006,
                "config": payload.config,
                "status": "queued",  # Initial status
            }
            
            # Создать backtest
            backtest = ds.create_backtest(**backtest_params)

        backtest_id = backtest.id

        task_id = await queue.submit_backtest(
            backtest_id=backtest_id,
            strategy_config=backtest.config or {},
            symbol=backtest.symbol,
            interval=backtest.timeframe,
            start_date=backtest.start_date.isoformat(),
            end_date=backtest.end_date.isoformat(),
            initial_capital=backtest.initial_capital,
            priority=10,  # HIGH priority для новых
        )
        
        logger.info(
            f"✅ Created backtest {backtest_id} and submitted to queue: {task_id}"
        )
        
        return {
            "backtest_id": backtest_id,
            "task_id": task_id,
            "status": "submitted",
            "message": "Backtest created and submitted to queue"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create and run backtest: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create and run backtest: {str(e)}"
        )


@router.post("/optimization/run", response_model=TaskResponse)
async def run_optimization(
    request: OptimizationRunRequest,
    data_service_factory: DataServiceFactory = Depends(get_data_service_factory),
    queue: QueueAdapterDependency = Depends(get_queue_adapter_dependency),
):
    """
    Запустить оптимизацию через Redis Queue
    
    Args:
        request: Параметры запуска (optimization_id, type, priority)
        
    Returns:
        task_id и статус
    """
    try:
        # Получить optimization из БД
        with data_service_factory() as ds:
            optimization = _ensure_entity(
                ds.get_optimization(request.optimization_id),
                not_found_message=f"Optimization {request.optimization_id} not found",
            )

        # Отправить в очередь (в зависимости от типа)
        if request.optimization_type == "grid":
            task_id = await queue.submit_grid_search(
                optimization_id=request.optimization_id,
                strategy_config=optimization.strategy_config or {},
                param_space=optimization.param_space or {},
                symbol=optimization.symbol,
                interval=optimization.timeframe,
                start_date=optimization.start_date.isoformat(),
                end_date=optimization.end_date.isoformat(),
                metric=optimization.metric or "sharpe_ratio",
                priority=request.priority,
            )
        elif request.optimization_type == "walk_forward":
            task_id = await queue.submit_walk_forward(
                optimization_id=request.optimization_id,
                strategy_config=optimization.strategy_config or {},
                param_space=optimization.param_space or {},
                symbol=optimization.symbol,
                interval=optimization.timeframe,
                start_date=optimization.start_date.isoformat(),
                end_date=optimization.end_date.isoformat(),
                metric=optimization.metric or "sharpe_ratio",
                priority=request.priority,
            )
        elif request.optimization_type == "bayesian":
            task_id = await queue.submit_bayesian(
                optimization_id=request.optimization_id,
                strategy_config=optimization.strategy_config or {},
                param_space=optimization.param_space or {},
                symbol=optimization.symbol,
                interval=optimization.timeframe,
                start_date=optimization.start_date.isoformat(),
                end_date=optimization.end_date.isoformat(),
                metric=optimization.metric or "sharpe_ratio",
                priority=request.priority,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid optimization type: {request.optimization_type}"
            )
        
        logger.info(
            f"📤 Submitted {request.optimization_type} optimization "
            f"{request.optimization_id} to queue: {task_id}"
        )
        
        return TaskResponse(
            task_id=task_id,
            status="submitted",
            message=f"Optimization {request.optimization_id} submitted to queue"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit optimization: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit optimization: {str(e)}"
        )


@router.get("/metrics", response_model=QueueMetricsResponse)
def get_queue_metrics(
    queue: QueueAdapterDependency = Depends(get_queue_adapter_dependency),
):
    """
    Получить метрики очереди
    
    Returns:
        Статистика по задачам в очереди
    """
    try:
        metrics = queue.get_metrics()
        return QueueMetricsResponse(**metrics)
    except Exception as e:
        logger.error(f"Failed to get queue metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get queue metrics: {str(e)}"
        )


@router.get("/health")
def queue_health(queue: QueueAdapterDependency = Depends(get_queue_adapter_dependency)):
    """
    Проверка состояния очереди
    
    Returns:
        Статус подключения к Redis и метрики
    """
    try:
        metrics = queue.get_metrics()
        return {
            "status": "healthy",
            "redis_connected": getattr(queue, "_qm", None) is not None,
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"Queue health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }
