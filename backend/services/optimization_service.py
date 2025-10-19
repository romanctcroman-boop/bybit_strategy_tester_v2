"""
Optimization Service

Сервис для управления задачами оптимизации через Celery.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from celery.result import AsyncResult
from loguru import logger

from backend.celery_app import celery_app
from backend.models.optimization_schemas import (
    GridSearchRequest,
    OptimizationMethod,
    OptimizationResultsResponse,
    OptimizationResult,
    TaskStatus,
    TaskStatusResponse,
    TaskProgressInfo,
    WalkForwardRequest,
    BayesianRequest
)


class OptimizationService:
    """Сервис для работы с задачами оптимизации"""
    
    @staticmethod
    def start_grid_search(request: GridSearchRequest) -> Dict[str, Any]:
        """
        Запуск Grid Search оптимизации
        
        Args:
            request: Параметры оптимизации
            
        Returns:
            Dict с task_id и статусом
        """
        from backend.tasks.optimize_tasks import grid_search_task
        
        # Формируем параметры для Celery задачи
        task_params = {
            "strategy_class": request.strategy_class,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "parameters": {
                name: {
                    "min": param.min,
                    "max": param.max,
                    "step": param.step
                }
                for name, param in request.parameters.items()
            },
            "initial_capital": request.initial_capital,
            "commission": request.commission,
            "metric": request.metric,
            "max_combinations": request.max_combinations
        }
        
        logger.info(f"Starting Grid Search optimization for {request.strategy_class}")
        logger.debug(f"Parameters: {task_params}")
        
        # Запуск Celery задачи
        result = grid_search_task.apply_async(
            kwargs=task_params,
            queue="optimization"
        )
        
        logger.success(f"Grid Search task created: {result.id}")
        
        return {
            "task_id": result.id,
            "status": TaskStatus.PENDING,
            "method": OptimizationMethod.GRID_SEARCH,
            "message": "Grid Search optimization task created successfully"
        }
    
    @staticmethod
    def start_walk_forward(request: WalkForwardRequest) -> Dict[str, Any]:
        """
        Запуск Walk-Forward оптимизации
        
        Args:
            request: Параметры оптимизации
            
        Returns:
            Dict с task_id и статусом
        """
        from backend.tasks.optimize_tasks import walk_forward_task
        
        task_params = {
            "strategy_class": request.strategy_class,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "parameters": {
                name: {
                    "min": param.min,
                    "max": param.max,
                    "step": param.step
                }
                for name, param in request.parameters.items()
            },
            "in_sample_period": request.in_sample_period,
            "out_sample_period": request.out_sample_period,
            "initial_capital": request.initial_capital,
            "commission": request.commission,
            "metric": request.metric
        }
        
        logger.info(f"Starting Walk-Forward optimization for {request.strategy_class}")
        
        result = walk_forward_task.apply_async(
            kwargs=task_params,
            queue="optimization"
        )
        
        logger.success(f"Walk-Forward task created: {result.id}")
        
        return {
            "task_id": result.id,
            "status": TaskStatus.PENDING,
            "method": OptimizationMethod.WALK_FORWARD,
            "message": "Walk-Forward optimization task created successfully"
        }
    
    @staticmethod
    def start_bayesian(request: "BayesianRequest") -> Dict[str, Any]:
        """
        Запуск Bayesian оптимизации
        
        Args:
            request: Параметры оптимизации
            
        Returns:
            Dict с task_id и статусом
        """
        from backend.tasks.optimize_tasks import bayesian_optimization_task
        
        # Преобразуем параметры в формат для Optuna
        param_space = {}
        for name, param in request.parameters.items():
            param_dict = {
                "type": param.type,
            }
            
            if param.type in ["int", "float"]:
                param_dict["low"] = param.low
                param_dict["high"] = param.high
                if param.step is not None:
                    param_dict["step"] = param.step
                if param.type == "float" and param.log:
                    param_dict["log"] = True
            elif param.type == "categorical":
                param_dict["choices"] = param.choices
            
            param_space[name] = param_dict
        
        task_params = {
            "strategy_class": request.strategy_class,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "param_space": param_space,
            "n_trials": request.n_trials,
            "metric": request.metric,
            "direction": request.direction,
            "n_jobs": request.n_jobs,
            "random_state": request.random_state,
            "initial_capital": request.initial_capital,
            "commission": request.commission,
        }
        
        logger.info(
            f"Starting Bayesian optimization for {request.strategy_class}, "
            f"{request.n_trials} trials"
        )
        
        result = bayesian_optimization_task.apply_async(
            kwargs=task_params,
            queue="optimization"
        )
        
        logger.success(f"Bayesian task created: {result.id}")
        
        return {
            "task_id": result.id,
            "status": TaskStatus.PENDING,
            "method": OptimizationMethod.BAYESIAN,
            "message": f"Bayesian optimization task created successfully ({request.n_trials} trials)"
        }
    
    @staticmethod
    def get_task_status(task_id: str) -> TaskStatusResponse:
        """
        Получить статус задачи оптимизации
        
        Args:
            task_id: ID задачи Celery
            
        Returns:
            TaskStatusResponse с информацией о статусе
        """
        result = AsyncResult(task_id, app=celery_app)
        
        # Базовый ответ
        response = TaskStatusResponse(
            task_id=task_id,
            status=TaskStatus(result.state)
        )
        
        # Если задача в процессе выполнения
        if result.state == "PROGRESS":
            info = result.info or {}
            
            # Извлекаем метод оптимизации из metadata
            method_str = info.get("method")
            if method_str:
                try:
                    response.method = OptimizationMethod(method_str)
                except ValueError:
                    pass
            
            # Формируем информацию о прогрессе
            if "current" in info and "total" in info:
                response.progress = TaskProgressInfo(
                    current=info["current"],
                    total=info["total"],
                    percent=round(info["current"] / info["total"] * 100, 2),
                    best_score=info.get("best_score"),
                    best_params=info.get("best_params"),
                    elapsed_time=info.get("elapsed_time"),
                    eta=info.get("eta")
                )
        
        # Если задача успешно завершена
        elif result.state == "SUCCESS":
            response.result = result.result
            if isinstance(result.result, dict):
                method_str = result.result.get("method")
                if method_str:
                    try:
                        response.method = OptimizationMethod(method_str)
                    except ValueError:
                        pass
        
        # Если задача провалилась
        elif result.state == "FAILURE":
            response.error = str(result.info)
            response.traceback = result.traceback
        
        logger.debug(f"Task {task_id} status: {result.state}")
        
        return response
    
    @staticmethod
    def get_task_result(task_id: str) -> Optional[OptimizationResultsResponse]:
        """
        Получить результат завершенной оптимизации
        
        Args:
            task_id: ID задачи Celery
            
        Returns:
            OptimizationResultsResponse или None если задача не завершена
        """
        result = AsyncResult(task_id, app=celery_app)
        
        if result.state != "SUCCESS":
            logger.warning(f"Task {task_id} not completed yet (state: {result.state})")
            return None
        
        task_result = result.result
        
        if not isinstance(task_result, dict):
            logger.error(f"Invalid task result format for {task_id}")
            return None
        
        # Формируем топ результатов
        top_results = []
        for idx, res in enumerate(task_result.get("results", [])[:10], 1):
            top_results.append(
                OptimizationResult(
                    params=res["params"],
                    metrics=res["metrics"],
                    score=res["score"],
                    rank=idx
                )
            )
        
        # Формируем финальный ответ
        response = OptimizationResultsResponse(
            task_id=task_id,
            status=TaskStatus.SUCCESS,
            method=OptimizationMethod(task_result["method"]),
            best_params=task_result["best_params"],
            best_score=task_result["best_score"],
            top_results=top_results,
            total_combinations=task_result["total_combinations"],
            tested_combinations=task_result["tested_combinations"],
            execution_time=task_result["execution_time"],
            strategy_class=task_result["strategy_class"],
            symbol=task_result["symbol"],
            timeframe=task_result["timeframe"],
            start_date=datetime.fromisoformat(task_result["start_date"]),
            end_date=datetime.fromisoformat(task_result["end_date"])
        )
        
        logger.info(f"Retrieved result for task {task_id}: {len(top_results)} results")
        
        return response
    
    @staticmethod
    def cancel_task(task_id: str) -> Dict[str, Any]:
        """
        Отменить задачу оптимизации
        
        Args:
            task_id: ID задачи Celery
            
        Returns:
            Dict с результатом отмены
        """
        result = AsyncResult(task_id, app=celery_app)
        
        if result.state in ["SUCCESS", "FAILURE", "REVOKED"]:
            return {
                "success": False,
                "message": f"Task already completed with state: {result.state}"
            }
        
        result.revoke(terminate=True)
        logger.info(f"Task {task_id} revoked")
        
        return {
            "success": True,
            "message": "Task cancelled successfully",
            "task_id": task_id
        }
