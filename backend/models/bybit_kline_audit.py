import json

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.database import Base


class BybitKlineAudit(Base):
    __tablename__ = "bybit_kline_audit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(64), nullable=False)
    interval = Column(
        String(16), nullable=True, default="1", server_default="1"
    )  # timeframe: 1, 5, 15, 60, D, etc.
    market_type = Column(
        String(16), nullable=False, default="linear", server_default="linear"
    )  # 'spot' or 'linear' (perpetual)
    open_time = Column(BigInteger, nullable=False, index=True)  # milliseconds
    open_time_dt = Column(DateTime(timezone=True), nullable=True)
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    turnover = Column(Float, nullable=True)
    raw = Column(Text, nullable=False)  # JSON text of original row/payload
    inserted_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Unique constraint including market_type for SPOT/LINEAR distinction
        # Allows same symbol+interval+open_time for different market types
        UniqueConstraint(
            "symbol",
            "interval",
            "market_type",
            "open_time",
            name="uix_symbol_interval_market_open_time",
        ),
    )

    def set_raw(self, raw_obj):
        self.raw = json.dumps(raw_obj, ensure_ascii=False)
