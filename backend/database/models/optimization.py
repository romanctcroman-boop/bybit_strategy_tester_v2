"""
Optimization ORM Model

SQLAlchemy model for storing optimization runs and results.
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


class OptimizationStatus(str, enum.Enum):
    """Status of an optimization run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OptimizationType(str, enum.Enum):
    """Type of optimization algorithm."""

    GRID_SEARCH = "grid_search"
    WALK_FORWARD = "walk_forward"
    BAYESIAN = "bayesian"
    RANDOM_SEARCH = "random_search"
    GENETIC = "genetic"


class Optimization(Base):
    """
    SQLAlchemy model for optimization runs.

    Stores configuration, progress, and results of parameter optimization.
    """

    __tablename__ = "optimizations"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to strategy
    strategy_id = Column(
        Integer,
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optimization configuration
    optimization_type = Column(
        Enum(OptimizationType),
        default=OptimizationType.GRID_SEARCH,
        nullable=False,
    )
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(16), nullable=False)  # 1m, 5m, 15m, 1h, 4h, 1d

    # Date range
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)

    # Parameter ranges (JSON)
    param_ranges = Column(JSON, nullable=True, default=dict)

    # Optimization settings
    metric = Column(String(64), default="sharpe_ratio")  # Target metric to optimize
    initial_capital = Column(Float, default=10000.0)
    total_combinations = Column(Integer, default=0)
    evaluated_combinations = Column(Integer, default=0)

    # Status
    status = Column(
        Enum(OptimizationStatus),
        default=OptimizationStatus.QUEUED,
        nullable=False,
        index=True,
    )
    progress = Column(Float, default=0.0)  # 0.0 - 1.0

    # Results
    best_params = Column(JSON, nullable=True)  # Best parameters found
    best_score = Column(Float, nullable=True)  # Best metric value
    results = Column(JSON, nullable=True)  # Full results (all combinations)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)

    # Config and metadata
    config = Column(JSON, nullable=True, default=dict)  # Additional config

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    strategy = relationship("Strategy", back_populates="optimizations")

    def __repr__(self) -> str:
        return (
            f"<Optimization(id={self.id}, strategy_id={self.strategy_id}, "
            f"type={self.optimization_type.value}, status={self.status.value})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "optimization_type": (
                self.optimization_type.value
                if isinstance(self.optimization_type, OptimizationType)
                else self.optimization_type
            ),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "param_ranges": self.param_ranges,
            "metric": self.metric,
            "initial_capital": self.initial_capital,
            "total_combinations": self.total_combinations,
            "evaluated_combinations": self.evaluated_combinations,
            "status": (
                self.status.value
                if isinstance(self.status, OptimizationStatus)
                else self.status
            ),
            "progress": self.progress,
            "best_params": self.best_params,
            "best_score": self.best_score,
            "results": self.results,
            "error_message": self.error_message,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    def update_progress(self, evaluated: int) -> None:
        """Update optimization progress."""
        self.evaluated_combinations = evaluated
        if self.total_combinations > 0:
            self.progress = min(1.0, evaluated / self.total_combinations)
        self.updated_at = datetime.now(UTC)

    def mark_started(self) -> None:
        """Mark optimization as started."""
        self.status = OptimizationStatus.RUNNING
        self.started_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def mark_completed(
        self, best_params: dict[str, Any], best_score: float, results: dict[str, Any]
    ) -> None:
        """Mark optimization as completed with results."""
        self.status = OptimizationStatus.COMPLETED
        self.best_params = best_params
        self.best_score = best_score
        self.results = results
        self.progress = 1.0
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def mark_failed(self, error: str, traceback: str | None = None) -> None:
        """Mark optimization as failed."""
        self.status = OptimizationStatus.FAILED
        self.error_message = error
        self.error_traceback = traceback
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
