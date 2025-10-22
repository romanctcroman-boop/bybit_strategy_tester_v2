from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from backend.database import Base


class BackfillRun(Base):
    __tablename__ = 'backfill_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(128), nullable=True, index=True)
    symbol = Column(String(64), nullable=False, index=True)
    interval = Column(String(16), nullable=False, index=True)
    params = Column(Text, nullable=True)  # JSON string of request params
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False, default='PENDING')  # PENDING|RUNNING|SUCCEEDED|FAILED|CANCELED
    upserts = Column(Integer, nullable=False, default=0)
    pages = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
