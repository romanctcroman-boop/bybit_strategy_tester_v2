"""
Strategy SQLAlchemy Model
Defines the Strategy table for storing trading strategies.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from backend.database import Base


class StrategyType(str, enum.Enum):
    """Strategy type enumeration"""

    SMA_CROSSOVER = "sma_crossover"
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER_BANDS = "bollinger_bands"
    # Pyramiding strategies
    GRID = "grid"
    DCA = "dca"
    MARTINGALE = "martingale"
    CUSTOM = "custom"
    ADVANCED = "advanced"


class StrategyStatus(str, enum.Enum):
    """Strategy status enumeration"""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Strategy(Base):
    """
    SQLAlchemy model for trading strategies.

    Stores strategy configuration, parameters, and metadata.
    Links to backtests and trades for performance tracking.
    """

    __tablename__ = "strategies"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Basic info
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    strategy_type = Column(SQLEnum(StrategyType), nullable=False, default=StrategyType.SMA_CROSSOVER)
    status = Column(SQLEnum(StrategyStatus), nullable=False, default=StrategyStatus.DRAFT)

    # Strategy parameters (JSON for flexibility)
    parameters = Column(JSON, nullable=False, default=dict)

    # Trading configuration
    symbol = Column(String(20), nullable=True)  # e.g., "BTCUSDT"
    timeframe = Column(String(10), nullable=True)  # e.g., "1h", "4h", "1d"
    market_type = Column(String(10), nullable=True, default="linear")  # linear or spot
    direction = Column(String(10), nullable=True, default="both")  # both, long, short
    initial_capital = Column(Float, nullable=True, default=10000.0)
    position_size = Column(Float, nullable=True, default=1.0)  # Position size multiplier

    # Risk management
    stop_loss_pct = Column(Float, nullable=True)  # Stop loss percentage
    take_profit_pct = Column(Float, nullable=True)  # Take profit percentage
    max_drawdown_pct = Column(Float, nullable=True)  # Maximum allowed drawdown

    # Performance metrics (updated after backtests)
    total_return = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True, default=0)
    backtest_count = Column(Integer, nullable=True, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_backtest_at = Column(DateTime, nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # User/ownership (for multi-user support)
    user_id = Column(String(36), nullable=True, index=True)

    # Tags for organization
    tags = Column(JSON, nullable=True, default=list)

    # Version control
    version = Column(Integer, nullable=False, default=1)

    # Strategy Builder fields (for visual block-based strategies)
    builder_graph = Column(JSON, nullable=True, default=None)  # Full strategy graph: blocks + connections
    builder_blocks = Column(JSON, nullable=True, default=None)  # Array of block objects (for quick access)
    builder_connections = Column(JSON, nullable=True, default=None)  # Array of connection objects
    is_builder_strategy = Column(Boolean, nullable=False, default=False)  # True if created via Strategy Builder

    # Relationships
    backtests = relationship("Backtest", back_populates="strategy", cascade="all, delete-orphan")
    optimizations = relationship("Optimization", back_populates="strategy", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Strategy(id={self.id}, name='{self.name}', type={self.strategy_type})>"

    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "strategy_type": self.strategy_type.value if self.strategy_type else None,
            "status": self.status.value if self.status else None,
            "parameters": self.parameters,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "initial_capital": self.initial_capital,
            "position_size": self.position_size,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "backtest_count": self.backtest_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_backtest_at": self.last_backtest_at.isoformat() if self.last_backtest_at else None,
            "tags": self.tags,
            "version": self.version,
            "builder_graph": self.builder_graph,
            "builder_blocks": self.builder_blocks,
            "builder_connections": self.builder_connections,
            "is_builder_strategy": self.is_builder_strategy,
        }

    @classmethod
    def get_default_parameters(cls, strategy_type: StrategyType) -> dict:
        """Get default parameters for a strategy type"""
        defaults = {
            StrategyType.SMA_CROSSOVER: {
                "fast_period": 10,
                "slow_period": 30,
            },
            StrategyType.RSI: {
                "period": 14,
                "overbought": 70,
                "oversold": 30,
            },
            StrategyType.MACD: {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            },
            StrategyType.BOLLINGER_BANDS: {
                "period": 20,
                "std_dev": 2.0,
            },
            StrategyType.CUSTOM: {},
        }
        return defaults.get(strategy_type, {})
