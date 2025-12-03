from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrategyOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    strategy_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BacktestOut(BaseModel):
    id: int
    strategy_id: int
    symbol: str
    timeframe: str
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float
    leverage: int | None = None
    commission: float | None = None
    config: dict[str, Any] | None = None

    class BacktestStatus(str, Enum):
        queued = "queued"
        running = "running"
        completed = "completed"
        failed = "failed"

    status: BacktestStatus
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    final_capital: float | None = None
    results: dict[str, Any] | None = None
    
    # MTF support (ТЗ 3.4.2)
    additional_timeframes: list[str] | None = Field(
        default=None,
        description="Additional timeframes used in multi-timeframe analysis"
    )
    htf_indicators: dict[str, Any] | None = Field(
        default=None,
        description="Higher timeframe indicator values for visualization"
    )

    model_config = ConfigDict(from_attributes=True)


class TradeOut(BaseModel):
    id: int
    backtest_id: int
    entry_time: str | None = None
    exit_time: str | None = None
    price: float
    qty: float
    side: str
    pnl: float | None = None
    created_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ApiListResponse[T](BaseModel):
    items: list[T]
    total: int | None = None


# ========================
# Marketdata Schemas
# ========================


class BybitKlineAuditOut(BaseModel):
    symbol: str
    interval: str
    open_time: int
    open_time_dt: str | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    turnover: float | None = None
    raw: str | None = None


class BybitKlineFetchRowOut(BaseModel):
    open_time: int
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    turnover: float | None = None


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
    volume: float | None = None


class MtfResponseOut(BaseModel):
    symbol: str
    intervals: list[str]
    data: dict[str, list[WorkingSetCandleOut]]


class DataUploadResponse(BaseModel):
    """Response returned by the market data upload endpoint."""

    upload_id: str
    filename: str
    size: int
    symbol: str
    interval: str
    stored_path: str


class UploadItem(BaseModel):
    upload_id: str
    filename: str
    size: int
    stored_path: str
    mtime: float | None = None


class UploadsListResponse(BaseModel):
    dir: str
    items: list[UploadItem]


class DataIngestResponse(BaseModel):
    """Response for uploaded file ingestion."""

    upload_id: str
    symbol: str
    interval: str
    format: str
    ingested: int
    skipped: int | None = None
    earliest_ms: int | None = None
    latest_ms: int | None = None
    updated_working_set: int | None = None


# ========================
# Admin Schemas
# ========================


class BackfillAsyncResponse(BaseModel):
    mode: str
    task_id: str
    run_id: int | None = None


class BackfillSyncResponse(BaseModel):
    mode: str
    symbol: str
    interval: str
    upserts: int
    pages: int
    elapsed_sec: float
    rows_per_sec: float
    eta_sec: float | None = None
    est_pages_left: int | None = None
    run_id: int | None = None


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
    files: list[ArchiveFileOut]


class DeleteArchiveResponse(BaseModel):
    deleted: str | list[str]


class TaskStatusOut(BaseModel):
    task_id: str
    state: str
    ready: bool
    successful: bool
    failed: bool
    info: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class BackfillRunOut(BaseModel):
    id: int
    task_id: str | None = None
    symbol: str
    interval: str

    class BackfillStatus(str, Enum):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"
        CANCELED = "CANCELED"

    status: BackfillStatus
    upserts: int | None = None
    pages: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    params: str | None = None
    error: str | None = None


# ========================
# Request Schemas (create/update)
# ========================


class StrategyCreate(BaseModel):
    # ✅ QUICK WIN #2: Input Validation
    name: str = Field(..., min_length=1, max_length=100, description="Strategy name (1-100 chars)")
    description: str | None = Field(None, max_length=500, description="Strategy description (max 500 chars)")
    strategy_type: str = Field(..., min_length=1, max_length=50)
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    
    @field_validator('strategy_type')
    @classmethod
    def validate_strategy_type(cls, v: str) -> str:
        """Validate strategy type against whitelist"""
        allowed = ['bollinger_rsi', 'sr_rsi', 'support_resistance', 'custom']
        if v not in allowed:
            raise ValueError(f'Strategy type must be one of: {allowed}')
        return v
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name doesn't contain dangerous characters"""
        if any(char in v for char in ['<', '>', '&', '"', "'"]):
            raise ValueError('Name contains invalid characters')
        return v.strip()


class StrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    strategy_type: str | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class BacktestCreate(BaseModel):
    # ✅ QUICK WIN #2: Input Validation with constraints
    strategy_id: int = Field(..., gt=0, description="Strategy ID must be positive")
    symbol: str = Field(..., min_length=1, max_length=20, pattern=r'^[A-Z0-9]+USDT$', description="Trading pair ending with USDT")
    timeframe: str = Field(..., pattern=r'^(1|3|5|15|30|60|120|240|D|W|M)$', description="Valid timeframe")
    start_date: datetime
    end_date: datetime
    initial_capital: float = Field(..., gt=0, le=1_000_000, description="Initial capital (0, 1M]")
    leverage: int | None = Field(1, ge=1, le=100, description="Leverage 1-100x")
    commission: float | None = Field(0.0006, ge=0, le=0.01, description="Commission 0-1%")
    config: dict[str, Any] | None = None
    
    # MTF support (ТЗ 3.4.2)
    additional_timeframes: list[str] | None = Field(
        default=None,
        description="Additional timeframes for multi-timeframe analysis (e.g., ['60', 'D'])",
        max_length=5
    )
    htf_filters: list[dict[str, Any]] | None = Field(
        default=None,
        description="Higher timeframe filters for entry conditions",
        max_length=10
    )
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase and ends with USDT"""
        v = v.upper()
        if not v.endswith('USDT'):
            raise ValueError('Symbol must end with USDT')
        return v
    
    @field_validator('end_date')
    @classmethod
    def validate_dates(cls, v: datetime, info) -> datetime:
        """Ensure end_date is after start_date"""
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class BacktestUpdate(BaseModel):
    # allow partial updates
    strategy_id: int | None = None
    symbol: str | None = None
    timeframe: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    initial_capital: float | None = None
    leverage: int | None = None
    commission: float | None = None
    config: dict[str, Any] | None = None
    status: str | None = None


class BacktestResultsUpdate(BaseModel):
    final_capital: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    results: dict[str, Any] | None = None


class BacktestClaimResponse(BaseModel):
    status: str
    backtest: dict[str, Any] | None = None
    message: str | None = None


# ========================
# Optimization Schemas (future HTTP exposure)
# ========================


class OptimizationOut(BaseModel):
    id: int
    strategy_id: int
    optimization_type: str
    symbol: str
    timeframe: str
    start_date: str | None = None
    end_date: str | None = None
    param_ranges: dict[str, Any] | None = None
    metric: str
    initial_capital: float
    total_combinations: int

    class OptimizationStatus(str, Enum):
        queued = "queued"
        running = "running"
        completed = "completed"
        failed = "failed"

    status: OptimizationStatus
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    best_params: dict[str, Any] | None = None
    best_score: float | None = None
    results: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class OptimizationCreate(BaseModel):
    strategy_id: int
    optimization_type: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    param_ranges: dict[str, Any]
    metric: str
    initial_capital: float
    total_combinations: int
    config: dict[str, Any] | None = None

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
    status: str | None = None
    best_params: dict[str, Any] | None = None
    best_score: float | None = None
    results: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

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
    params: dict[str, Any]
    score: float
    total_return: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    total_trades: int | None = None
    metrics: dict[str, Any] | None = None

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
    strategy_config: dict[str, Any] = Field(default_factory=dict)
    param_space: dict[str, list[Any]] | None = None
    metric: str | None = Field(default="sharpe_ratio")
    queue: str | None = Field(default="optimizations")

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
    strategy_config: dict[str, Any] = Field(default_factory=dict)
    param_space: dict[str, list[Any]] | None = None
    train_size: int = 120
    test_size: int = 60
    step_size: int = 30
    metric: str | None = Field(default="sharpe_ratio")
    queue: str | None = Field(default="optimizations")

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
    strategy_config: dict[str, Any] = Field(default_factory=dict)
    param_space: dict[str, dict[str, Any]]
    n_trials: int = 100
    metric: str | None = Field(default="sharpe_ratio")
    direction: str = Field(default="maximize")
    n_jobs: int = 1
    random_state: int | None = None
    queue: str | None = Field(default="optimizations")

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
