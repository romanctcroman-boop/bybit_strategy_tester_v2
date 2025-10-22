from sqlalchemy import Column, Integer, BigInteger, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from backend.database import Base


class BackfillProgress(Base):
    __tablename__ = 'backfill_progress'
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(64), nullable=False)
    interval = Column(String(16), nullable=False)
    current_cursor_ms = Column(BigInteger, nullable=True)  # walk-back cursor (<= this)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('symbol', 'interval', name='uix_backfill_progress_key'),
    )
