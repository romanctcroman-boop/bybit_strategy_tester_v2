"""
Optimization API Router

REST API endpoints для запуска и управления задачами оптимизации.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from loguru import logger

from backend.models.optimization_schemas import (
    GridSearchRequest,
    WalkForwardRequest,
    BayesianRequest,
    OptimizationTaskResponse,
    TaskStatusResponse,
    OptimizationResultsResponse
)
from backend.services.optimization_service import OptimizationService


router = APIRouter(
    prefix="/optimize",
    tags=["optimization"],
    responses={
        404: {"description": "Task not found"},
        500: {"description": "Internal server error"}
    }
)


@router.post(
    "/grid",
    response_model=OptimizationTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Grid Search Optimization",
    description="""
    Запускает Grid Search оптимизацию стратегии.
    
    Grid Search перебирает все комбинации параметров в заданных диапазонах,
    запускает бэктест для каждой комбинации и находит оптимальные параметры.
    
    **Пример использования:**
    ```python
    {
        "strategy_class": "SMAStrategy",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-12-31T23:59:59",
        "parameters": {
            "fast_period": {"min": 5, "max": 20, "step": 5},
            "slow_period": {"min": 20, "max": 50, "step": 10}
        },
        "initial_capital": 10000.0,
        "commission": 0.001,
        "metric": "total_return",
        "max_combinations": 100
    }
    ```
    
    **Ограничения:**
    - Максимум 1000 комбинаций (по умолчанию)
    - Используется очередь 'optimization'
    - Задача может занять несколько минут в зависимости от количества комбинаций
    """
)
async def start_grid_search(request: GridSearchRequest) -> OptimizationTaskResponse:
    """
    Запуск Grid Search оптимизации
    
    Args:
        request: Параметры оптимизации
        
    Returns:
        OptimizationTaskResponse с task_id
        
    Raises:
        HTTPException 500: Если произошла ошибка при создании задачи
    """
    try:
        logger.info(f"Received Grid Search request for {request.strategy_class}")
        
        result = OptimizationService.start_grid_search(request)
        
        return OptimizationTaskResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to start Grid Search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start optimization: {str(e)}"
        )


@router.post(
    "/walk-forward",
    response_model=OptimizationTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Walk-Forward Optimization",
    description="""
    Запускает Walk-Forward оптимизацию стратегии.
    
    Walk-Forward анализ разбивает данные на периоды in-sample (обучение) и 
    out-of-sample (тестирование), последовательно оптимизируя и проверяя стратегию.
    
    **Статус:** ✅ Реализовано
    """
)
async def start_walk_forward(request: WalkForwardRequest) -> OptimizationTaskResponse:
    """
    Запуск Walk-Forward оптимизации
    
    Args:
        request: Параметры оптимизации
        
    Returns:
        OptimizationTaskResponse с task_id
        
    Raises:
        HTTPException 500: Ошибка при создании задачи
    """
    try:
        logger.info(f"Received Walk-Forward request for {request.strategy_class}")
        
        result = OptimizationService.start_walk_forward(request)
        
        return OptimizationTaskResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to start Walk-Forward: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start optimization: {str(e)}"
        )


@router.post(
    "/bayesian",
    response_model=OptimizationTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Bayesian Optimization",
    description="""
    Запускает Bayesian оптимизацию стратегии используя Optuna.
    
    Bayesian optimization использует Tree-structured Parzen Estimator (TPE) для
    умного поиска оптимальных параметров. Значительно быстрее Grid Search.
    
    **Преимущества:**
    - Меньше итераций для нахождения оптимума
    - Использует информацию из предыдущих попыток
    - Поддержка int, float, categorical параметров
    - Автоматическое вычисление важности параметров
    
    **Статус:** ✅ Реализовано
    """
)
async def start_bayesian(request: BayesianRequest) -> OptimizationTaskResponse:
    """
    Запуск Bayesian оптимизации
    
    Args:
        request: Параметры оптимизации
        
    Returns:
        OptimizationTaskResponse с task_id
        
    Raises:
        HTTPException 500: Ошибка при создании задачи
    """
    try:
        logger.info(
            f"Received Bayesian request for {request.strategy_class}, "
            f"{request.n_trials} trials"
        )
        
        result = OptimizationService.start_bayesian(request)
        
        return OptimizationTaskResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to start Bayesian optimization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start optimization: {str(e)}"
        )


@router.get(
    "/{task_id}/status",
    response_model=TaskStatusResponse,
    summary="Get Task Status",
    description="""
    Получить текущий статус задачи оптимизации.
    
    **Возможные статусы:**
    - `PENDING`: Задача ожидает выполнения
    - `STARTED`: Задача начала выполнение
    - `PROGRESS`: Задача в процессе (доступен прогресс)
    - `SUCCESS`: Задача завершена успешно
    - `FAILURE`: Задача завершилась с ошибкой
    - `REVOKED`: Задача отменена
    
    **Прогресс:**
    Для задач в статусе `PROGRESS` возвращается информация:
    - Текущий шаг и общее количество
    - Процент выполнения
    - Лучший результат на текущий момент
    - Оставшееся время (ETA)
    """
)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Получить статус задачи
    
    Args:
        task_id: ID задачи Celery
        
    Returns:
        TaskStatusResponse со статусом и прогрессом
        
    Raises:
        HTTPException 404: Если задача не найдена
    """
    try:
        logger.debug(f"Getting status for task {task_id}")
        
        result = OptimizationService.get_task_status(task_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.get(
    "/{task_id}/result",
    response_model=OptimizationResultsResponse,
    summary="Get Optimization Results",
    description="""
    Получить результаты завершенной оптимизации.
    
    **Требования:**
    - Задача должна быть в статусе `SUCCESS`
    - Если задача еще выполняется, вернется 404
    
    **Результат включает:**
    - Лучшие параметры и их значение метрики
    - Топ-10 результатов с ранжированием
    - Общую статистику (всего комбинаций, время выполнения)
    - Параметры бэктеста (символ, таймфрейм, даты)
    """
)
async def get_task_result(task_id: str) -> OptimizationResultsResponse:
    """
    Получить результат оптимизации
    
    Args:
        task_id: ID задачи Celery
        
    Returns:
        OptimizationResultsResponse с результатами
        
    Raises:
        HTTPException 404: Если задача не завершена или не найдена
    """
    try:
        logger.debug(f"Getting result for task {task_id}")
        
        result = OptimizationService.get_task_result(task_id)
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not completed yet or not found. Check task status first."
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task result: {str(e)}"
        )


@router.delete(
    "/{task_id}",
    response_model=Dict[str, Any],
    summary="Cancel Task",
    description="""
    Отменить выполняющуюся задачу оптимизации.
    
    **Ограничения:**
    - Можно отменить только задачи в статусе PENDING, STARTED или PROGRESS
    - Завершенные задачи (SUCCESS, FAILURE) нельзя отменить
    """
)
async def cancel_task(task_id: str) -> Dict[str, Any]:
    """
    Отменить задачу оптимизации
    
    Args:
        task_id: ID задачи Celery
        
    Returns:
        Dict с результатом отмены
        
    Raises:
        HTTPException 400: Если задача уже завершена
    """
    try:
        logger.info(f"Cancelling task {task_id}")
        
        result = OptimizationService.cancel_task(task_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Failed to cancel task")
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )
