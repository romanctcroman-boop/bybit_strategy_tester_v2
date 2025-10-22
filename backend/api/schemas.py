from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class StrategyOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    strategy_type: str
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BacktestOut(BaseModel):
    id: int
    strategy_id: int
    symbol: str
    timeframe: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_capital: float
    leverage: Optional[int] = None
    commission: Optional[float] = None
    config: Optional[Dict[str, Any]] = None
    class BacktestStatus(str, Enum):
        queued = "queued"
        running = "running"
        completed = "completed"
        failed = "failed"

    status: BacktestStatus
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    final_capital: Optional[float] = None
    results: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class TradeOut(BaseModel):
    id: int
    backtest_id: int
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    price: float
    qty: float
    side: str
    pnl: Optional[float] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class ApiListResponse(BaseModel, Generic[T]):
    items: List[T]
    total: Optional[int] = None


# ========================
# Marketdata Schemas
# ========================


class BybitKlineAuditOut(BaseModel):
    symbol: str
    open_time: int
    open_time_dt: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    raw: Optional[str] = None


class BybitKlineFetchRowOut(BaseModel):
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    turnover: Optional[float] = None


class RecentTradeOut(BaseModel):
    time: int  # ms
    price: float
    qty: float
    side: str


class WorkingSetCandleOut(BaseModel):
    time: int  # seconds
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class MtfResponseOut(BaseModel):
    symbol: str
    intervals: List[str]
    data: Dict[str, List[WorkingSetCandleOut]]


# ========================
# Admin Schemas
# ========================


class BackfillAsyncResponse(BaseModel):
    mode: str
    task_id: str
    run_id: Optional[int] = None


class BackfillSyncResponse(BaseModel):
    mode: str
    symbol: str
    interval: str
    upserts: int
    pages: int
    elapsed_sec: float
    rows_per_sec: float
    eta_sec: Optional[float] = None
    est_pages_left: Optional[int] = None
    run_id: Optional[int] = None


class ArchiveAsyncResponse(BaseModel):
    mode: str
    task_id: str


class ArchiveSyncResponse(BaseModel):
    mode: str
    archived_rows: int
    output_dir: str


class RestoreAsyncResponse(BaseModel):
    mode: str
    task_id: str


class RestoreSyncResponse(BaseModel):
    mode: str
    restored_rows: int
    input_dir: str


class ArchiveFileOut(BaseModel):
    path: str
    size: int
    modified: float


class ArchivesListOut(BaseModel):
    dir: str
    files: List[ArchiveFileOut]


class DeleteArchiveResponse(BaseModel):
    deleted: Union[str, List[str]]


class TaskStatusOut(BaseModel):
    task_id: str
    state: str
    ready: bool
    successful: bool
    failed: bool
    info: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BackfillRunOut(BaseModel):
    id: int
    task_id: Optional[str] = None
    symbol: str
    interval: str
    class BackfillStatus(str, Enum):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"
        CANCELED = "CANCELED"

    status: BackfillStatus
    upserts: Optional[int] = None
    pages: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    params: Optional[str] = None
    error: Optional[str] = None


# ========================
# Request Schemas (create/update)
# ========================


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    strategy_type: str
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    strategy_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class BacktestCreate(BaseModel):
    strategy_id: int
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    leverage: Optional[int] = 1
    commission: Optional[float] = 0.0006
    config: Optional[Dict[str, Any]] = None


class BacktestUpdate(BaseModel):
    # allow partial updates
    strategy_id: Optional[int] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_capital: Optional[float] = None
    leverage: Optional[int] = None
    commission: Optional[float] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class BacktestResultsUpdate(BaseModel):
    final_capital: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    results: Optional[Dict[str, Any]] = None


class BacktestClaimResponse(BaseModel):
    status: str
    backtest: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


# ========================
# Optimization Schemas (future HTTP exposure)
# ========================


class OptimizationOut(BaseModel):
    id: int
    strategy_id: int
    optimization_type: str
    symbol: str
    timeframe: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    param_ranges: Optional[Dict[str, Any]] = None
    metric: str
    initial_capital: float
    total_combinations: int
    class OptimizationStatus(str, Enum):
        queued = "queued"
        running = "running"
        completed = "completed"
        failed = "failed"

    status: OptimizationStatus
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    best_params: Optional[Dict[str, Any]] = None
    best_score: Optional[float] = None
    results: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class OptimizationCreate(BaseModel):
    strategy_id: int
    optimization_type: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    param_ranges: Dict[str, Any]
    metric: str
    initial_capital: float
    total_combinations: int
    config: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy_id": 1,
                "optimization_type": "grid_search",
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T23:59:59Z",
                "param_ranges": {
                    "rsi_period": [7, 14, 21],
                    "ema_fast": [9, 12],
                    "ema_slow": [26, 30],
                },
                "metric": "sharpe_ratio",
                "initial_capital": 10000.0,
                "total_combinations": 18,
                "config": {"commission": 0.0006},
            }
        }
    )


class OptimizationUpdate(BaseModel):
    status: Optional[str] = None
    best_params: Optional[Dict[str, Any]] = None
    best_score: Optional[float] = None
    results: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "completed",
                "best_params": {"rsi_period": 14, "ema_fast": 12, "ema_slow": 26},
                "best_score": 1.23,
                "results": {"top_10": [{"params": {"rsi_period": 14}, "score": 1.2}]},
                "completed_at": "2024-02-01T00:00:00Z",
            }
        }
    )


class OptimizationResultOut(BaseModel):
    id: int
    optimization_id: int
    params: Dict[str, Any]
    score: float
    total_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    metrics: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# ========================
# Optimization Run Request/Response Schemas
# ========================


class OptimizationEnqueueResponse(BaseModel):
    task_id: str
    optimization_id: int
    queue: str = Field(default="optimizations")
    class EnqueueStatus(str, Enum):
        queued = "queued"

    status: EnqueueStatus = Field(default=EnqueueStatus.queued)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "5f1b7a34-2e40-4f7e-9f07-f2b17b8f5e4a",
                "optimization_id": 42,
                "queue": "optimizations",
                "status": "queued",
            }
        }
    )


class OptimizationRunGridRequest(BaseModel):
    strategy_config: Dict[str, Any] = Field(default_factory=dict)
    param_space: Optional[Dict[str, List[Any]]] = None
    metric: Optional[str] = Field(default="sharpe_ratio")
    queue: Optional[str] = Field(default="optimizations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy_config": {"initial_capital": 10000, "commission": 0.0006},
                "param_space": {"rsi_period": [7, 14, 21], "ema_fast": [9, 12]},
                "metric": "sharpe_ratio",
                "queue": "optimizations",
            }
        }
    )


class OptimizationRunWalkForwardRequest(BaseModel):
    strategy_config: Dict[str, Any] = Field(default_factory=dict)
    param_space: Optional[Dict[str, List[Any]]] = None
    train_size: int = 120
    test_size: int = 60
    step_size: int = 30
    metric: Optional[str] = Field(default="sharpe_ratio")
    queue: Optional[str] = Field(default="optimizations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy_config": {"initial_capital": 10000, "commission": 0.0006},
                "param_space": {"rsi_period": [7, 14], "ema_fast": [9, 12]},
                "train_size": 120,
                "test_size": 60,
                "step_size": 30,
                "metric": "sharpe_ratio",
                "queue": "optimizations",
            }
        }
    )


class OptimizationRunBayesianRequest(BaseModel):
    strategy_config: Dict[str, Any] = Field(default_factory=dict)
    param_space: Dict[str, Dict[str, Any]]
    n_trials: int = 100
    metric: Optional[str] = Field(default="sharpe_ratio")
    direction: str = Field(default="maximize")
    n_jobs: int = 1
    random_state: Optional[int] = None
    queue: Optional[str] = Field(default="optimizations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy_config": {"initial_capital": 10000, "commission": 0.0006},
                "param_space": {
                    "rsi_period": {"type": "int", "low": 7, "high": 21},
                    "ema_fast": {"type": "int", "low": 8, "high": 15},
                },
                "n_trials": 50,
                "metric": "sharpe_ratio",
                "direction": "maximize",
                "n_jobs": 1,
                "queue": "optimizations",
            }
        }
    )


# ========================
# Admin/Backfill examples (OpenAPI)
# ========================

BackfillAsyncResponse.model_config = ConfigDict(
    json_schema_extra={"example": {"mode": "async", "task_id": "1e2d3c"}}
)
BackfillSyncResponse.model_config = ConfigDict(
    json_schema_extra={
        "example": {
            "mode": "sync",
            "symbol": "BTCUSDT",
            "interval": "1",
            "upserts": 1000,
            "pages": 10,
            "elapsed_sec": 2.34,
            "rows_per_sec": 427.35,
        }
    }
)
TaskStatusOut.model_config = ConfigDict(
    json_schema_extra={
        "example": {
            "task_id": "abc-123",
            "state": "PROGRESS",
            "ready": False,
            "successful": False,
            "failed": False,
            "info": {"current": 20, "total": 100},
        }
    }
)
