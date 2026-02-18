"""
Backtest SQLAlchemy Model
Defines the Backtest table for storing backtest results.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from backend.database import Base


class BacktestStatus(str, enum.Enum):
    """Backtest execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Backtest(Base):
    """
    SQLAlchemy model for backtest results.

    Stores backtest configuration, execution status, and results.
    Links to strategy and stores detailed performance metrics.
    """

    __tablename__ = "backtests"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Strategy reference
    strategy_id = Column(String(36), ForeignKey("strategies.id"), nullable=True, index=True)
    strategy_type = Column(String(50), nullable=False)  # Strategy type used

    # Execution status
    status: Column[BacktestStatus] = Column(SQLEnum(BacktestStatus), nullable=False, default=BacktestStatus.PENDING)
    error_message = Column(Text, nullable=True)

    # Configuration
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(Float, nullable=False, default=10000.0)

    # Strategy parameters used
    parameters = Column(JSON, nullable=False, default=dict)

    # Performance metrics
    total_return = Column(Float, nullable=True)
    annual_return = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    calmar_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)

    # Trade statistics
    total_trades = Column(Integer, nullable=True, default=0)
    winning_trades = Column(Integer, nullable=True, default=0)
    losing_trades = Column(Integer, nullable=True, default=0)
    avg_trade_pnl = Column(Float, nullable=True)
    best_trade = Column(Float, nullable=True)
    worst_trade = Column(Float, nullable=True)

    # Portfolio statistics
    final_capital = Column(Float, nullable=True)
    peak_capital = Column(Float, nullable=True)

    # ===== NEW METRICS (TradingView compatible) =====
    # Profit metrics
    net_profit = Column(Float, nullable=True)
    net_profit_pct = Column(Float, nullable=True)
    gross_profit = Column(Float, nullable=True)
    gross_loss = Column(Float, nullable=True)
    total_commission = Column(Float, nullable=True)

    # Buy & Hold comparison
    buy_hold_return = Column(Float, nullable=True)
    buy_hold_return_pct = Column(Float, nullable=True)

    # CAGR metrics
    cagr = Column(Float, nullable=True)
    cagr_long = Column(Float, nullable=True)
    cagr_short = Column(Float, nullable=True)

    # Advanced risk metrics
    recovery_factor = Column(Float, nullable=True)
    expectancy = Column(Float, nullable=True)
    volatility = Column(Float, nullable=True)
    ulcer_index = Column(Float, nullable=True)

    # Streak analysis
    max_consecutive_wins = Column(Integer, nullable=True)
    max_consecutive_losses = Column(Integer, nullable=True)

    # Long/Short statistics
    long_trades = Column(Integer, nullable=True, default=0)
    short_trades = Column(Integer, nullable=True, default=0)
    long_pnl = Column(Float, nullable=True)
    short_pnl = Column(Float, nullable=True)
    long_win_rate = Column(Float, nullable=True)
    short_win_rate = Column(Float, nullable=True)

    # Trade duration
    avg_bars_in_trade = Column(Float, nullable=True)
    exposure_time = Column(Float, nullable=True)

    # Equity curve (stored as JSON array)
    equity_curve = Column(JSON, nullable=True)

    # Trade list (stored as JSON array)
    trades = Column(JSON, nullable=True)

    # Store full metrics JSON to support new fields without schema migration
    metrics_json = Column(JSON, nullable=True)

    # Execution timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # User/ownership
    user_id = Column(String(36), nullable=True, index=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Relationships
    strategy = relationship("Strategy", back_populates="backtests", foreign_keys=[strategy_id])
    trade_records = relationship("Trade", back_populates="backtest", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Backtest(id={self.id}, strategy_type='{self.strategy_type}', status={self.status})>"

    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        base_dict = {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type,
            "status": self.status.value if self.status else None,
            "error_message": self.error_message,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_capital": self.initial_capital,
            "parameters": self.parameters,
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_pnl": self.avg_trade_pnl,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "final_capital": self.final_capital,
            "peak_capital": self.peak_capital,
            # New TradingView-compatible metrics
            "net_profit": self.net_profit,
            "net_profit_pct": self.net_profit_pct,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "total_commission": self.total_commission,
            "buy_hold_return": self.buy_hold_return,
            "buy_hold_return_pct": self.buy_hold_return_pct,
            "cagr": self.cagr,
            "cagr_long": self.cagr_long,
            "cagr_short": self.cagr_short,
            "recovery_factor": self.recovery_factor,
            "expectancy": self.expectancy,
            "volatility": self.volatility,
            "ulcer_index": self.ulcer_index,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "long_pnl": self.long_pnl,
            "short_pnl": self.short_pnl,
            "long_win_rate": self.long_win_rate,
            "short_win_rate": self.short_win_rate,
            "avg_bars_in_trade": self.avg_bars_in_trade,
            "exposure_time": self.exposure_time,
            # Timestamps
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "notes": self.notes,
        }
        # Merge full metrics if available
        if self.metrics_json:
            # We prioritize explicit columns if we want, but metrics_json is source of truth for details
            # Updating base_dict means key collisions will be overwritten by metrics_json values
            # This is desirable as metrics_json is the complete dataset
            base_dict.update(self.metrics_json)

        return base_dict

    def get_metrics_dict(self) -> dict:
        """Get performance metrics as dictionary"""
        metrics = {
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_pnl": self.avg_trade_pnl,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "final_capital": self.final_capital,
            "peak_capital": self.peak_capital,
            # New TradingView-compatible metrics
            "net_profit": self.net_profit,
            "net_profit_pct": self.net_profit_pct,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "total_commission": self.total_commission,
            "buy_hold_return": self.buy_hold_return,
            "buy_hold_return_pct": self.buy_hold_return_pct,
            "cagr": self.cagr,
            "cagr_long": self.cagr_long,
            "cagr_short": self.cagr_short,
            "recovery_factor": self.recovery_factor,
            "expectancy": self.expectancy,
            "volatility": self.volatility,
            "ulcer_index": self.ulcer_index,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "long_pnl": self.long_pnl,
            "short_pnl": self.short_pnl,
            "long_win_rate": self.long_win_rate,
            "short_win_rate": self.short_win_rate,
            "avg_bars_in_trade": self.avg_bars_in_trade,
            "exposure_time": self.exposure_time,
        }
        if self.metrics_json:
            metrics.update(self.metrics_json)
        return metrics
