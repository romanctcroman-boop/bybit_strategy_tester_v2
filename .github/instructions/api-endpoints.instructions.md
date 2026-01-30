---
applyTo: "**/api/**/*.py"
---

# FastAPI Endpoint Rules


## Router Structure

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from loguru import logger

router = APIRouter(
    prefix="/api/v1/feature",
    tags=["Feature Name"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)
```

## Request/Response Models (Pydantic)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class BacktestRequest(BaseModel):
    """Request model for backtest endpoint"""
    symbol: str = Field(..., description="Trading pair (e.g., BTCUSDT)")
    interval: str = Field(..., description="Timeframe (e.g., 15m, 1h)")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(10000.0, ge=100, description="Starting capital")
    strategy_type: str = Field(..., description="Strategy to use")
    strategy_params: dict = Field(default_factory=dict)

    @validator('symbol')
    def validate_symbol(cls, v):
        if not v.endswith('USDT'):
            raise ValueError('Symbol must end with USDT')
        return v.upper()

    @validator('interval')
    def validate_interval(cls, v):
        valid = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        if v not in valid:
            raise ValueError(f'Invalid interval. Must be one of: {valid}')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "interval": "15m",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "initial_capital": 10000,
                "strategy_type": "rsi",
                "strategy_params": {"period": 14, "overbought": 70}
            }
        }

class BacktestResponse(BaseModel):
    """Response model for backtest endpoint"""
    success: bool
    backtest_id: str
    metrics: dict
    trades: List[dict]
    equity_curve: List[float]
    created_at: datetime
```

## Endpoint Pattern

```python
from backend.services.backtest_service import BacktestService
from backend.api.dependencies import get_backtest_service

@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    service: BacktestService = Depends(get_backtest_service)
):
    """
    Run a backtest with the specified parameters.

    - **symbol**: Trading pair (BTCUSDT, ETHUSDT, etc.)
    - **interval**: Timeframe for candles
    - **strategy_type**: Which strategy to use
    - **strategy_params**: Strategy-specific parameters

    Returns complete backtest results with metrics and trades.
    """
    try:
        logger.info(f"Backtest request: {request.symbol} | {request.strategy_type}")

        result = await service.run_backtest(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            strategy_type=request.strategy_type,
            strategy_params=request.strategy_params
        )

        logger.info(f"Backtest completed: {result.backtest_id}")
        return BacktestResponse(
            success=True,
            backtest_id=result.backtest_id,
            metrics=result.metrics,
            trades=result.trades,
            equity_curve=result.equity_curve,
            created_at=result.created_at
        )

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

## Dependency Injection

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.services.backtest_service import BacktestService

def get_backtest_service(db: Session = Depends(get_db)) -> BacktestService:
    return BacktestService(db)
```

## Error Handling

```python
from fastapi import HTTPException, status

# Standard error responses
class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None

# Use specific status codes
raise HTTPException(status_code=400, detail="Invalid parameters")
raise HTTPException(status_code=404, detail="Resource not found")
raise HTTPException(status_code=422, detail="Validation failed")
raise HTTPException(status_code=500, detail="Internal server error")
```

## Middleware & CORS

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Background Tasks

```python
from fastapi import BackgroundTasks

@router.post("/long-running")
async def long_running_task(
    request: Request,
    background_tasks: BackgroundTasks
):
    task_id = str(uuid.uuid4())
    background_tasks.add_task(process_task, task_id, request.data)
    return {"task_id": task_id, "status": "queued"}
```

## Documentation

- All endpoints MUST have docstrings
- Use Pydantic examples for request/response
- Tag endpoints by feature area
- Document all status codes

## DO NOT

- Return raw exceptions to clients
- Skip input validation
- Use sync database operations
- Forget logging for requests
- Expose internal error details in production
