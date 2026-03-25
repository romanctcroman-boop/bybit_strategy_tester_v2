"""Strategy Version model for version history."""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String

from backend.database import Base


class StrategyVersion(Base):
    """Version snapshot of a Strategy Builder strategy."""

    __tablename__ = "strategy_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String(36), ForeignKey("strategies.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    graph_json = Column(JSON, nullable=True)
    blocks_json = Column(JSON, nullable=True)
    connections_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
