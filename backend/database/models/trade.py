"""
Trade ORM Model

SQLAlchemy model for storing individual trades from backtests.
"""

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from backend.database import Base


class TradeSide(str, enum.Enum):
    """Trade direction."""

    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, enum.Enum):
    """Trade status."""

    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class Trade(Base):
    """
    SQLAlchemy model for individual trades.

    Stores entry/exit details, PnL, and metadata for each trade.
    """

    __tablename__ = "trades"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to backtest
    backtest_id = Column(
        Integer,
        ForeignKey("backtests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Trade identification
    trade_id = Column(String(64), nullable=True, index=True)  # External trade ID
    symbol = Column(String(32), nullable=False, index=True)

    # Trade direction and status
    side = Column(Enum(TradeSide), nullable=False)  # type: ignore[var-annotated]
    status = Column(Enum(TradeStatus), default=TradeStatus.CLOSED, nullable=False)  # type: ignore[var-annotated]

    # Entry details
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False, index=True)
    entry_size = Column(Float, nullable=False)  # Position size in base currency
    entry_value = Column(Float, nullable=True)  # Position value in quote currency

    # Exit details
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime(timezone=True), nullable=True, index=True)
    exit_size = Column(Float, nullable=True)
    exit_value = Column(Float, nullable=True)

    # PnL
    pnl = Column(Float, nullable=True)  # Absolute PnL
    pnl_percent = Column(Float, nullable=True)  # Percentage PnL
    realized_pnl = Column(Float, nullable=True)  # Realized PnL (after fees)

    # Fees
    fees = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)

    # Risk management
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    leverage = Column(Float, default=1.0)

    # Trade metrics
    # duration_seconds: 0 = trade still open or instant fill; never NULL (default=0)
    duration_seconds = Column(Integer, nullable=False, default=0)  # Trade duration in seconds
    max_favorable_excursion = Column(Float, nullable=True)  # MFE
    max_adverse_excursion = Column(Float, nullable=True)  # MAE

    # Signal info
    entry_signal = Column(String(128), nullable=True)  # What triggered entry
    exit_signal = Column(String(128), nullable=True)  # What triggered exit
    notes = Column(Text, nullable=True)

    # Extra metadata (renamed from 'metadata' which is reserved)
    extra_data = Column(JSON, nullable=True, default=dict)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    backtest = relationship("Backtest", back_populates="trade_records")

    def __repr__(self) -> str:
        return f"<Trade(id={self.id}, symbol={self.symbol}, side={self.side.value}, pnl={self.pnl})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "backtest_id": self.backtest_id,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side.value if isinstance(self.side, TradeSide) else self.side,
            "status": (self.status.value if isinstance(self.status, TradeStatus) else self.status),
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "entry_size": self.entry_size,
            "entry_value": self.entry_value,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_size": self.exit_size,
            "exit_value": self.exit_value,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "realized_pnl": self.realized_pnl,
            "fees": self.fees,
            "commission": self.commission,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "leverage": self.leverage,
            "duration_seconds": self.duration_seconds,
            "max_favorable_excursion": self.max_favorable_excursion,
            "max_adverse_excursion": self.max_adverse_excursion,
            "entry_signal": self.entry_signal,
            "exit_signal": self.exit_signal,
            "notes": self.notes,
            "extra_data": self.extra_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def calculate_duration(self) -> int | None:
        """Calculate trade duration in seconds."""
        if self.entry_time and self.exit_time:
            delta = self.exit_time - self.entry_time
            self.duration_seconds = int(delta.total_seconds())  # type: ignore[assignment]
            return self.duration_seconds  # type: ignore[return-value]
        return None

    def calculate_pnl(self) -> float | None:
        """Calculate PnL based on entry/exit prices."""
        if self.entry_price and self.exit_price and self.entry_size:
            if self.side in (TradeSide.BUY, TradeSide.LONG):
                self.pnl = (self.exit_price - self.entry_price) * self.entry_size  # type: ignore[assignment]
            else:
                self.pnl = (self.entry_price - self.exit_price) * self.entry_size  # type: ignore[assignment]

            # Subtract fees
            self.realized_pnl = self.pnl - (self.fees or 0) - (self.commission or 0)  # type: ignore[assignment]

            # Calculate percentage
            if self.entry_value and self.entry_value > 0:
                self.pnl_percent = (self.pnl / self.entry_value) * 100  # type: ignore[assignment]

            return self.pnl  # type: ignore[return-value]
        return None

    def close(self, exit_price: float, exit_time: datetime, exit_signal: str | None = None) -> None:
        """Close the trade."""
        self.exit_price = exit_price  # type: ignore[assignment]
        self.exit_time = exit_time  # type: ignore[assignment]
        self.exit_size = self.entry_size
        self.exit_value = exit_price * self.entry_size  # type: ignore[assignment]
        self.exit_signal = exit_signal  # type: ignore[assignment]
        self.status = TradeStatus.CLOSED  # type: ignore[assignment]
        self.calculate_pnl()
        self.calculate_duration()
