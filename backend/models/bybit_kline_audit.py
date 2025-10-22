import json

from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from backend.database import Base


class BybitKlineAudit(Base):
    __tablename__ = "bybit_kline_audit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(64), nullable=False)
    open_time = Column(BigInteger, nullable=False, index=True)  # milliseconds
    open_time_dt = Column(DateTime(timezone=True), nullable=True)
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    turnover = Column(Float, nullable=True)
    raw = Column(Text, nullable=False)  # JSON text of original row/payload
    inserted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("symbol", "open_time", name="uix_symbol_open_time"),)

    def set_raw(self, raw_obj):
        self.raw = json.dumps(raw_obj, ensure_ascii=False)
