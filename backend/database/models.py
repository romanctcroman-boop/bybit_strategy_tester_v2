"""
Database models for PostgreSQL using Pydantic

These models represent database tables and are used for validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ==============================================================================
# Enums
# ==============================================================================

class BacktestStatus(str, Enum):
    """Backtest run status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TradeStatus(str, Enum):
    """Trade status"""
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TradeSide(str, Enum):
    """Trade side"""
    LONG = "long"
    SHORT = "short"


# ==============================================================================
# User Models
# ==============================================================================

class UserBase(BaseModel):
    """Base user model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=100)


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=8)


class User(UserBase):
    """User model with all fields"""
    id: int
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==============================================================================
# Strategy Models
# ==============================================================================

class StrategyBase(BaseModel):
    """Base strategy model"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    strategy_type: str = Field(..., max_length=50)
    config: Dict[str, Any] = Field(default_factory=dict)


class StrategyCreate(StrategyBase):
    """Strategy creation model"""
    user_id: Optional[int] = None


class StrategyUpdate(BaseModel):
    """Strategy update model"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    strategy_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class Strategy(StrategyBase):
    """Strategy model with all fields"""
    id: int
    user_id: Optional[int] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==============================================================================
# Backtest Models
# ==============================================================================

class BacktestBase(BaseModel):
    """Base backtest model"""
    strategy_id: int
    user_id: Optional[int] = None
    symbol: str = Field(..., max_length=20)
    timeframe: str = Field(..., max_length=10)
    start_date: datetime
    end_date: datetime
    initial_capital: float = Field(..., gt=0)
    leverage: int = Field(default=1, ge=1, le=100)
    commission: float = Field(default=0.0006, ge=0, lt=1)


class BacktestCreate(BacktestBase):
    """Backtest creation model"""
    config: Optional[Dict[str, Any]] = None


class BacktestUpdate(BaseModel):
    """Backtest update model"""
    final_capital: Optional[float] = None
    total_return: Optional[float] = None
    total_trades: Optional[int] = None
    winning_trades: Optional[int] = None
    losing_trades: Optional[int] = None
    win_rate: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_duration: Optional[int] = None
    profit_factor: Optional[float] = None
    avg_trade_return: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    largest_win: Optional[float] = None
    largest_loss: Optional[float] = None
    avg_trade_duration: Optional[int] = None
    results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    status: Optional[BacktestStatus] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Backtest(BacktestBase):
    """Backtest model with all fields"""
    id: int
    user_id: Optional[int] = None
    final_capital: Optional[float] = None
    total_return: Optional[float] = None
    total_trades: Optional[int] = None
    winning_trades: Optional[int] = None
    losing_trades: Optional[int] = None
    win_rate: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_duration: Optional[int] = None
    profit_factor: Optional[float] = None
    avg_trade_return: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    largest_win: Optional[float] = None
    largest_loss: Optional[float] = None
    avg_trade_duration: Optional[int] = None
    config: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    status: BacktestStatus = BacktestStatus.PENDING
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==============================================================================
# Trade Models
# ==============================================================================

class TradeBase(BaseModel):
    """Base trade model"""
    backtest_id: int
    entry_time: datetime
    side: TradeSide
    entry_price: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)


class TradeCreate(TradeBase):
    """Trade creation model"""
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    return_pct: Optional[float] = None
    commission: Optional[float] = None
    status: TradeStatus = TradeStatus.OPEN


class TradeUpdate(BaseModel):
    """Trade update model"""
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    return_pct: Optional[float] = None
    commission: Optional[float] = None
    status: Optional[TradeStatus] = None


class Trade(TradeBase):
    """Trade model with all fields"""
    id: int
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    return_pct: Optional[float] = None
    commission: Optional[float] = None
    status: TradeStatus = TradeStatus.OPEN

    class Config:
        from_attributes = True


# ==============================================================================
# Optimization Models
# ==============================================================================

class OptimizationBase(BaseModel):
    """Base optimization model"""
    strategy_id: int
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    param_grid: Dict[str, Any]


class OptimizationCreate(OptimizationBase):
    """Optimization creation model"""
    config: Optional[Dict[str, Any]] = None


class Optimization(OptimizationBase):
    """Optimization model with all fields"""
    id: int
    total_combinations: Optional[int] = None
    completed_combinations: Optional[int] = None
    best_params: Optional[Dict[str, Any]] = None
    best_return: Optional[float] = None
    best_sharpe: Optional[float] = None
    results: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    status: str = "pending"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==============================================================================
# Response Models
# ==============================================================================

class StrategyList(BaseModel):
    """List of strategies with pagination"""
    total: int
    strategies: List[Strategy]


class BacktestList(BaseModel):
    """List of backtests with pagination"""
    total: int
    backtests: List[Backtest]


class TradeList(BaseModel):
    """List of trades with pagination"""
    total: int
    trades: List[Trade]


class BacktestSummary(BaseModel):
    """Summary statistics for backtests"""
    total_backtests: int
    completed_backtests: int
    avg_return: Optional[float] = None
    avg_sharpe: Optional[float] = None
    best_strategy_id: Optional[int] = None
    best_strategy_name: Optional[str] = None
    best_return: Optional[float] = None


class StrategyPerformance(BaseModel):
    """Strategy performance statistics"""
    strategy_id: int
    strategy_name: str
    total_backtests: int
    avg_return: Optional[float] = None
    avg_sharpe: Optional[float] = None
    avg_win_rate: Optional[float] = None
    best_return: Optional[float] = None
    worst_return: Optional[float] = None
    last_backtest: Optional[datetime] = None
