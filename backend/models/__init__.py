"""SQLAlchemy ORM models for backtesting system."""

from datetime import UTC, datetime
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.database import Base


class Strategy(Base):
    """Trading strategy configuration."""

    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(100), nullable=False, index=True)
    config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    backtests = relationship("Backtest", back_populates="strategy", cascade="all, delete-orphan")
    optimizations = relationship(
        "Optimization", back_populates="strategy", cascade="all, delete-orphan"
    )


class Backtest(Base):
    """Backtest run record."""

    __tablename__ = "backtests"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(50), nullable=False, index=True)
    timeframe = Column(String(20), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    initial_capital = Column(Float, nullable=False)
    leverage = Column(Integer, default=1, nullable=False)
    commission = Column(Float, default=0.0, nullable=False)
    config = Column(JSON, nullable=True)
    status = Column(String(50), default="queued", nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    final_capital = Column(Float, nullable=True)
    total_return = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)
    winning_trades = Column(Integer, nullable=True)
    losing_trades = Column(Integer, nullable=True)
    win_rate = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    results = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    strategy = relationship("Strategy", back_populates="backtests")
    trades = relationship("Trade", back_populates="backtest", cascade="all, delete-orphan")


class Trade(Base):
    """Individual trade record."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(Integer, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    side = Column(String(20), nullable=False, index=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)  # PnL percentage
    run_up = Column(Float, nullable=True)  # Peak gain (Run-up USDT)
    run_up_pct = Column(Float, nullable=True)  # Peak gain %
    drawdown = Column(Float, nullable=True)  # Max drawdown USDT
    drawdown_pct = Column(Float, nullable=True)  # Max drawdown %
    cumulative_pnl = Column(Float, nullable=True)  # Cumulative P&L
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    backtest = relationship("Backtest", back_populates="trades")


class Optimization(Base):
    """Optimization run record."""

    __tablename__ = "optimizations"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    optimization_type = Column(String(50), nullable=False)
    symbol = Column(String(50), nullable=False, index=True)
    timeframe = Column(String(20), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    param_ranges = Column(JSON, nullable=True)
    metric = Column(String(50), nullable=False)
    initial_capital = Column(Float, nullable=False)
    total_combinations = Column(Integer, nullable=True)
    status = Column(String(50), default="queued", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    strategy = relationship("Strategy", back_populates="optimizations")
    results = relationship(
        "OptimizationResult", back_populates="optimization", cascade="all, delete-orphan"
    )


class OptimizationResult(Base):
    """Single parameter combination result."""

    __tablename__ = "optimization_results"

    id = Column(Integer, primary_key=True, index=True)
    optimization_id = Column(
        Integer, ForeignKey("optimizations.id", ondelete="CASCADE"), nullable=False
    )
    parameters = Column(JSON, nullable=False)
    metric_value = Column(Float, nullable=False)
    backtest_id = Column(Integer, ForeignKey("backtests.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    optimization = relationship("Optimization", back_populates="results")


class User(Base):
    """User account for authentication."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=True, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)


class MarketData(Base):
    """Market OHLCV candles."""

    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    interval = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
