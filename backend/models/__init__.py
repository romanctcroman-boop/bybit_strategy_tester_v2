"""
SQLAlchemy Models for Bybit Strategy Tester

Модели базы данных для хранения стратегий, бэктестов, трейдов и оптимизаций.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


# ============================================================================
# STRATEGIES MODEL
# ============================================================================
class Strategy(Base):
    """
    Модель торговой стратегии
    
    Хранит информацию о стратегиях пользователя, включая конфигурацию,
    параметры и метаданные.
    """
    __tablename__ = "strategies"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic info
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    strategy_type = Column(String(50), nullable=False, index=True)
    
    # Configuration (JSONB в PostgreSQL)
    config = Column(JSON, nullable=False)

    # Ownership
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    backtests = relationship("Backtest", back_populates="strategy", cascade="all, delete-orphan")
    optimizations = relationship("Optimization", back_populates="strategy", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
    Index('idx_strategies_name', 'name'),
    Index('idx_strategies_type', 'strategy_type'),
    Index('idx_strategies_active', 'is_active'),
    Index('idx_strategies_user_id', 'user_id'),
    )
    
    def __repr__(self):
        return f"<Strategy(id={self.id}, name='{self.name}', type='{self.strategy_type}')>"


# ============================================================================
# BACKTESTS MODEL
# ============================================================================
class Backtest(Base):
    """
    Модель бэктеста
    
    Хранит результаты бэктестирования стратегий на исторических данных.
    Включает метрики производительности, параметры и статистику трейдов.
    """
    __tablename__ = "backtests"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    strategy_id = Column(Integer, ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    
    # Market data parameters
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    
    # Trading parameters
    initial_capital = Column(Numeric(18, 2), nullable=False)
    leverage = Column(Integer, default=1)
    commission = Column(Numeric(5, 4), default=0.0006)  # 0.06% taker fee
    
    # Results
    final_capital = Column(Numeric(18, 2))
    total_return = Column(Numeric(10, 4))  # %
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    win_rate = Column(Numeric(5, 2))  # %
    
    # Performance metrics
    sharpe_ratio = Column(Numeric(10, 4))
    sortino_ratio = Column(Numeric(10, 4))
    calmar_ratio = Column(Numeric(10, 4))
    max_drawdown = Column(Numeric(10, 4))  # %
    max_drawdown_duration = Column(Integer)  # days
    profit_factor = Column(Numeric(10, 4))
    
    # Additional metrics
    avg_trade_return = Column(Numeric(10, 4))  # %
    avg_win = Column(Numeric(10, 4))
    avg_loss = Column(Numeric(10, 4))
    largest_win = Column(Numeric(18, 2))
    largest_loss = Column(Numeric(18, 2))
    avg_trade_duration = Column(Integer)  # minutes
    
    # Execution details
    config = Column(JSON)  # Параметры запуска
    results = Column(JSON)  # Детальные результаты
    error_message = Column(Text)
    status = Column(String(20), default='pending', index=True)  # 'pending', 'running', 'completed', 'failed'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    strategy = relationship("Strategy", back_populates="backtests")
    trades = relationship("Trade", back_populates="backtest", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('initial_capital > 0', name='positive_capital'),
        CheckConstraint('leverage >= 1 AND leverage <= 100', name='valid_leverage'),
        CheckConstraint('commission >= 0 AND commission < 1', name='valid_commission'),
    Index('idx_backtests_strategy_id', 'strategy_id'),
    Index('idx_backtests_user_id', 'user_id'),
        Index('idx_backtests_symbol', 'symbol'),
        Index('idx_backtests_status', 'status'),
        Index('idx_backtests_created_at', 'created_at'),
        Index('idx_backtests_performance', 'sharpe_ratio', 'total_return'),
    )
    
    def __repr__(self):
        return f"<Backtest(id={self.id}, strategy_id={self.strategy_id}, symbol='{self.symbol}', status='{self.status}')>"


# ============================================================================
# TRADES MODEL (Time-series data)
# ============================================================================
class Trade(Base):
    """
    Модель отдельного трейда
    
    Хранит информацию о каждом трейде в бэктесте: вход, выход, PnL, комиссии.
    Оптимизирована для time-series данных через TimescaleDB.
    """
    __tablename__ = "trades"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    backtest_id = Column(Integer, ForeignKey('backtests.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Trade details
    entry_time = Column(DateTime(timezone=True), nullable=False, index=True)
    exit_time = Column(DateTime(timezone=True))
    side = Column(String(10), nullable=False, index=True)  # 'LONG' or 'SHORT'
    
    # Prices
    entry_price = Column(Numeric(18, 8), nullable=False)
    exit_price = Column(Numeric(18, 8))
    
    # Quantities
    quantity = Column(Numeric(18, 8), nullable=False)
    position_size = Column(Numeric(18, 2), nullable=False)  # USDT value
    
    # Results
    pnl = Column(Numeric(18, 8))  # Profit/Loss (USDT)
    return_pct = Column("pnl_pct", Numeric(10, 4))  # Profit/Loss (%)
    commission = Column(Numeric(18, 8))
    status = Column(String(20), default='open', index=True)
    
    # Exit details
    exit_reason = Column(String(50), index=True)  # 'signal', 'take_profit', 'stop_loss', etc.
    
    # Metadata (renamed to 'meta' because 'metadata' is reserved by SQLAlchemy)
    meta = Column(JSON)
    
    # Relationships
    backtest = relationship("Backtest", back_populates="trades")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('quantity > 0', name='positive_quantity'),
        CheckConstraint('position_size > 0', name='positive_position_size'),
    CheckConstraint("side IN ('long', 'short')", name='valid_side'),
        Index('idx_trades_backtest_id', 'backtest_id'),
        Index('idx_trades_entry_time', 'entry_time'),
        Index('idx_trades_side', 'side'),
        Index('idx_trades_exit_reason', 'exit_reason'),
        Index('idx_trades_status', 'status'),
    )
    
    def __repr__(self):
        return f"<Trade(id={self.id}, backtest_id={self.backtest_id}, side='{self.side}', pnl={self.pnl})>"


# ============================================================================
# OPTIMIZATIONS MODEL
# ============================================================================
class Optimization(Base):
    """
    Модель оптимизации параметров стратегии
    
    Хранит результаты grid search / walk-forward оптимизации.
    Связывает стратегию с множеством запусков бэктестов с разными параметрами.
    """
    __tablename__ = "optimizations"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    strategy_id = Column(Integer, ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Optimization parameters
    optimization_type = Column(String(50), nullable=False)  # 'grid_search', 'walk_forward', 'genetic'
    
    # Market data parameters
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    
    # Parameters to optimize
    param_ranges = Column(JSON, nullable=False)  # {'param1': [min, max, step], 'param2': [...]}
    
    # Optimization settings
    metric = Column(String(50), default='sharpe_ratio')  # Метрика для оптимизации
    initial_capital = Column(Numeric(18, 2), nullable=False)
    
    # Results
    total_combinations = Column(Integer)
    completed_combinations = Column(Integer, default=0)
    best_params = Column(JSON)  # Лучшая комбинация параметров
    best_score = Column(Numeric(10, 4))  # Лучшее значение метрики
    
    # Results details
    results = Column(JSON)  # Полные результаты всех комбинаций
    
    # Execution details
    config = Column(JSON)
    error_message = Column(Text)
    status = Column(String(20), default='pending', index=True)  # 'pending', 'running', 'completed', 'failed'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    strategy = relationship("Strategy", back_populates="optimizations")
    optimization_results = relationship("OptimizationResult", back_populates="optimization", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_optimizations_strategy_id', 'strategy_id'),
        Index('idx_optimizations_status', 'status'),
        Index('idx_optimizations_created_at', 'created_at'),
        Index('idx_optimizations_metric', 'metric', 'best_score'),
    )
    
    def __repr__(self):
        return f"<Optimization(id={self.id}, strategy_id={self.strategy_id}, type='{self.optimization_type}', status='{self.status}')>"


# ============================================================================
# OPTIMIZATION RESULTS MODEL
# ============================================================================
class OptimizationResult(Base):
    """
    Модель результата отдельной комбинации параметров при оптимизации
    
    Хранит результаты каждого прогона бэктеста с уникальным набором параметров.
    """
    __tablename__ = "optimization_results"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    optimization_id = Column(Integer, ForeignKey('optimizations.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Parameters tested
    params = Column(JSON, nullable=False)  # {'param1': value1, 'param2': value2, ...}
    
    # Results
    total_return = Column(Numeric(10, 4))
    sharpe_ratio = Column(Numeric(10, 4))
    sortino_ratio = Column(Numeric(10, 4))
    max_drawdown = Column(Numeric(10, 4))
    profit_factor = Column(Numeric(10, 4))
    win_rate = Column(Numeric(5, 2))
    total_trades = Column(Integer)
    
    # Score (метрика для оптимизации)
    score = Column(Numeric(10, 4), index=True)
    
    # Detailed metrics
    metrics = Column(JSON)  # Все метрики бэктеста
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    optimization = relationship("Optimization", back_populates="optimization_results")
    
    # Indexes
    __table_args__ = (
        Index('idx_optimization_results_optimization_id', 'optimization_id'),
        Index('idx_optimization_results_score', 'score'),
    )
    
    def __repr__(self):
        return f"<OptimizationResult(id={self.id}, optimization_id={self.optimization_id}, score={self.score})>"


# ============================================================================
# MARKET DATA MODEL (Time-series)
# ============================================================================
class MarketData(Base):
    """
    Модель рыночных данных (OHLCV)
    
    Хранит исторические свечи для различных символов и таймфреймов.
    Оптимизирована для time-series данных через TimescaleDB.
    """
    __tablename__ = "market_data"
    
    # Primary key (composite: time + symbol + timeframe)
    id = Column(Integer, primary_key=True, index=True)
    
    # Market identification
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    
    # OHLCV data
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Numeric(18, 8), nullable=False)
    high = Column(Numeric(18, 8), nullable=False)
    low = Column(Numeric(18, 8), nullable=False)
    close = Column(Numeric(18, 8), nullable=False)
    volume = Column(Numeric(24, 8), nullable=False)
    
    # Additional data
    quote_volume = Column(Numeric(24, 8))  # Volume in quote currency (USDT)
    trades_count = Column(Integer)  # Number of trades in candle
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_market_data_symbol_timeframe', 'symbol', 'timeframe'),
        Index('idx_market_data_timestamp', 'timestamp'),
        Index('idx_market_data_unique', 'symbol', 'timeframe', 'timestamp', unique=True),
    )
    
    def __repr__(self):
        return f"<MarketData(symbol='{self.symbol}', timeframe='{self.timeframe}', timestamp={self.timestamp}, close={self.close})>"


# ============================================================================
# Export all models
# ============================================================================
__all__ = [
    'Strategy',
    'Backtest',
    'Trade',
    'Optimization',
    'OptimizationResult',
    'MarketData',
]
