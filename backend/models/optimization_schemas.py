"""
Pydantic Models для Optimization API

Модели запросов и ответов для endpoints оптимизации.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field, validator


class OptimizationMethod(str, Enum):
    """Методы оптимизации"""
    GRID_SEARCH = "grid_search"
    WALK_FORWARD = "walk_forward"
    BAYESIAN = "bayesian"


class TaskStatus(str, Enum):
    """Статусы Celery задач"""
    PENDING = "PENDING"       # Задача ожидает выполнения
    STARTED = "STARTED"       # Задача начала выполнение
    PROGRESS = "PROGRESS"     # Задача в процессе (с прогрессом)
    SUCCESS = "SUCCESS"       # Задача выполнена успешно
    FAILURE = "FAILURE"       # Задача завершилась с ошибкой
    RETRY = "RETRY"           # Задача будет повторена
    REVOKED = "REVOKED"       # Задача отменена


class ParameterRange(BaseModel):
    """Диапазон значений параметра для Grid Search"""
    min: float = Field(..., description="Минимальное значение")
    max: float = Field(..., description="Максимальное значение")
    step: float = Field(..., description="Шаг изменения")
    
    @validator('step')
    def step_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('step must be positive')
        return v
    
    @validator('max')
    def max_must_be_greater_than_min(cls, v, values):
        if 'min' in values and v <= values['min']:
            raise ValueError('max must be greater than min')
        return v


class GridSearchRequest(BaseModel):
    """Запрос на Grid Search оптимизацию"""
    
    strategy_class: str = Field(
        ..., 
        description="Класс стратегии (например, 'SMAStrategy')",
        example="SMAStrategy"
    )
    
    symbol: str = Field(
        ..., 
        description="Торговая пара",
        example="BTCUSDT"
    )
    
    timeframe: str = Field(
        ..., 
        description="Таймфрейм",
        example="1h"
    )
    
    start_date: datetime = Field(
        ..., 
        description="Дата начала бэктеста",
        example="2024-01-01T00:00:00"
    )
    
    end_date: datetime = Field(
        ..., 
        description="Дата окончания бэктеста",
        example="2024-12-31T23:59:59"
    )
    
    parameters: Dict[str, ParameterRange] = Field(
        ...,
        description="Параметры для оптимизации с диапазонами",
        example={
            "fast_period": {"min": 5, "max": 20, "step": 5},
            "slow_period": {"min": 20, "max": 50, "step": 10}
        }
    )
    
    initial_capital: float = Field(
        default=10000.0,
        gt=0,
        description="Начальный капитал",
        example=10000.0
    )
    
    commission: float = Field(
        default=0.001,
        ge=0,
        le=1,
        description="Комиссия (0.001 = 0.1%)",
        example=0.001
    )
    
    metric: str = Field(
        default="total_return",
        description="Метрика для оптимизации",
        example="total_return"
    )
    
    max_combinations: Optional[int] = Field(
        default=1000,
        gt=0,
        description="Максимальное количество комбинаций параметров",
        example=1000
    )
    
    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
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
        }


class WalkForwardRequest(BaseModel):
    """Запрос на Walk-Forward оптимизацию"""
    
    strategy_class: str = Field(..., description="Класс стратегии")
    symbol: str = Field(..., description="Торговая пара")
    timeframe: str = Field(..., description="Таймфрейм")
    start_date: datetime = Field(..., description="Дата начала")
    end_date: datetime = Field(..., description="Дата окончания")
    
    parameters: Dict[str, ParameterRange] = Field(
        ..., 
        description="Параметры для оптимизации"
    )
    
    in_sample_period: int = Field(
        ...,
        gt=0,
        description="Период in-sample в днях",
        example=60
    )
    
    out_sample_period: int = Field(
        ...,
        gt=0,
        description="Период out-of-sample в днях",
        example=30
    )
    
    initial_capital: float = Field(default=10000.0, gt=0)
    commission: float = Field(default=0.001, ge=0, le=1)
    metric: str = Field(default="total_return")


class BayesianParameter(BaseModel):
    """Параметр для Bayesian optimization"""
    
    type: str = Field(
        ...,
        description="Тип параметра: 'int', 'float', 'categorical'",
        example="int"
    )
    low: Optional[float] = Field(None, description="Минимальное значение (для int/float)")
    high: Optional[float] = Field(None, description="Максимальное значение (для int/float)")
    step: Optional[float] = Field(None, description="Шаг (опционально)")
    log: bool = Field(False, description="Логарифмическая шкала (для float)")
    choices: Optional[List[Any]] = Field(None, description="Варианты (для categorical)")


class BayesianRequest(BaseModel):
    """Запрос на Bayesian оптимизацию"""
    
    strategy_class: str = Field(..., description="Класс стратегии")
    symbol: str = Field(..., description="Торговая пара")
    timeframe: str = Field(..., description="Таймфрейм")
    start_date: datetime = Field(..., description="Дата начала")
    end_date: datetime = Field(..., description="Дата окончания")
    
    parameters: Dict[str, BayesianParameter] = Field(
        ..., 
        description="Параметры для оптимизации с типами"
    )
    
    n_trials: int = Field(
        default=100,
        gt=0,
        le=1000,
        description="Количество попыток оптимизации",
        example=100
    )
    
    metric: str = Field(
        default="sharpe_ratio",
        description="Метрика для оптимизации"
    )
    
    direction: str = Field(
        default="maximize",
        description="Направление оптимизации: 'maximize' или 'minimize'",
        pattern="^(maximize|minimize)$"
    )
    
    n_jobs: int = Field(
        default=1,
        ge=1,
        description="Количество параллельных процессов"
    )
    
    random_state: Optional[int] = Field(
        None,
        description="Seed для воспроизводимости результатов"
    )
    
    initial_capital: float = Field(default=10000.0, gt=0)
    commission: float = Field(default=0.001, ge=0, le=1)


class OptimizationTaskResponse(BaseModel):
    """Ответ при создании задачи оптимизации"""
    
    task_id: str = Field(..., description="ID задачи Celery")
    status: TaskStatus = Field(..., description="Текущий статус задачи")
    method: OptimizationMethod = Field(..., description="Метод оптимизации")
    message: str = Field(..., description="Сообщение о статусе")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "a9d20bfc-8cbf-4e24-b221-6c5d6fc2513d",
                "status": "PENDING",
                "method": "grid_search",
                "message": "Optimization task created successfully"
            }
        }


class TaskProgressInfo(BaseModel):
    """Информация о прогрессе задачи"""
    
    current: int = Field(..., description="Текущий шаг")
    total: int = Field(..., description="Всего шагов")
    percent: float = Field(..., description="Процент выполнения")
    best_score: Optional[float] = Field(None, description="Лучший результат")
    best_params: Optional[Dict[str, Any]] = Field(None, description="Лучшие параметры")
    elapsed_time: Optional[float] = Field(None, description="Прошедшее время (сек)")
    eta: Optional[float] = Field(None, description="Оставшееся время (сек)")


class TaskStatusResponse(BaseModel):
    """Ответ со статусом задачи"""
    
    task_id: str = Field(..., description="ID задачи")
    status: TaskStatus = Field(..., description="Статус задачи")
    method: Optional[OptimizationMethod] = Field(None, description="Метод оптимизации")
    
    progress: Optional[TaskProgressInfo] = Field(
        None, 
        description="Прогресс выполнения (если доступен)"
    )
    
    result: Optional[Any] = Field(
        None, 
        description="Результат (если задача завершена)"
    )
    
    error: Optional[str] = Field(
        None, 
        description="Сообщение об ошибке (если задача провалилась)"
    )
    
    traceback: Optional[str] = Field(
        None,
        description="Traceback ошибки (если задача провалилась)"
    )
    
    created_at: Optional[datetime] = Field(None, description="Время создания")
    started_at: Optional[datetime] = Field(None, description="Время начала")
    completed_at: Optional[datetime] = Field(None, description="Время завершения")


class OptimizationResult(BaseModel):
    """Один результат оптимизации"""
    
    params: Dict[str, Any] = Field(..., description="Параметры стратегии")
    metrics: Dict[str, float] = Field(..., description="Метрики бэктеста")
    score: float = Field(..., description="Значение целевой метрики")
    rank: Optional[int] = Field(None, description="Ранг результата")


class OptimizationResultsResponse(BaseModel):
    """Ответ с результатами оптимизации"""
    
    task_id: str = Field(..., description="ID задачи")
    status: TaskStatus = Field(..., description="Статус задачи")
    method: OptimizationMethod = Field(..., description="Метод оптимизации")
    
    best_params: Dict[str, Any] = Field(..., description="Лучшие параметры")
    best_score: float = Field(..., description="Лучший результат")
    
    top_results: List[OptimizationResult] = Field(
        ..., 
        description="Топ результатов (до 10)",
        max_length=10
    )
    
    total_combinations: int = Field(..., description="Всего комбинаций")
    tested_combinations: int = Field(..., description="Протестировано комбинаций")
    
    execution_time: float = Field(..., description="Время выполнения (сек)")
    
    strategy_class: str = Field(..., description="Класс стратегии")
    symbol: str = Field(..., description="Торговая пара")
    timeframe: str = Field(..., description="Таймфрейм")
    start_date: datetime = Field(..., description="Дата начала")
    end_date: datetime = Field(..., description="Дата окончания")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "a9d20bfc-8cbf-4e24-b221-6c5d6fc2513d",
                "status": "SUCCESS",
                "method": "grid_search",
                "best_params": {"fast_period": 10, "slow_period": 30},
                "best_score": 1.45,
                "top_results": [
                    {
                        "params": {"fast_period": 10, "slow_period": 30},
                        "metrics": {"total_return": 1.45, "sharpe_ratio": 1.8},
                        "score": 1.45,
                        "rank": 1
                    }
                ],
                "total_combinations": 100,
                "tested_combinations": 100,
                "execution_time": 125.5,
                "strategy_class": "SMAStrategy",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "start_date": "2024-01-01T00:00:00",
                "end_date": "2024-12-31T23:59:59"
            }
        }
