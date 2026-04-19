"""
🧬 Genetic Optimization ORM Model

SQLAlchemy model for genetic algorithm optimization jobs.
"""

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON

from backend.database import Base


class GeneticJobStatus(str, enum.Enum):
    """Status of a genetic optimization job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GeneticJob(Base):
    """
    SQLAlchemy model for genetic optimization jobs.

    Stores configuration, progress, and results of genetic algorithm optimizations.
    """

    __tablename__ = "genetic_jobs"

    # Primary key - UUID for distributed systems compatibility
    id = Column(
        String(36),  # String UUID for SQLite/MySQL compatibility
        primary_key=True,
        default=lambda: str(datetime.now(UTC).timestamp()),
    )

    # Job identification
    job_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(UUID(int=0)),  # Will be set by application
    )

    # Status
    status: Column[str] = Column(
        Enum(GeneticJobStatus),
        default=GeneticJobStatus.PENDING,
        nullable=False,
        index=True,
    )
    progress = Column(Float, default=0.0)  # 0.0 - 100.0
    current_generation = Column(Integer, default=0)

    # Request configuration
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(16), nullable=False)
    start_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    end_date = Column(String(10), nullable=False)
    strategy_type = Column(String(64), nullable=False)

    # Genetic algorithm parameters
    param_ranges = Column(JSON, nullable=True, default=dict)
    fitness_function = Column(String(64), default="sharpe")
    population_size = Column(Integer, default=50)
    n_generations = Column(Integer, default=100)
    selection_strategy = Column(String(32), default="tournament")
    crossover_operator = Column(String(32), default="arithmetic")
    mutation_operator = Column(String(32), default="gaussian")
    elitism_rate = Column(Float, default=0.1)
    crossover_rate = Column(Float, default=0.8)
    mutation_rate = Column(Float, default=0.1)
    multi_objective_weights = Column(JSON, nullable=True)
    n_workers = Column(Integer, default=1)
    random_state = Column(Integer, nullable=True)

    # Results
    best_fitness = Column(Float, nullable=True)
    best_params = Column(JSON, nullable=True)
    n_evaluations = Column(Integer, default=0)
    execution_time = Column(Float, nullable=True)  # seconds
    generations_completed = Column(Integer, default=0)
    improvement_percent = Column(Float, default=0.0)
    history = Column(JSON, nullable=True)  # Evolution history
    pareto_front = Column(JSON, nullable=True)  # For multi-objective
    metrics = Column(JSON, nullable=True)  # Final metrics

    # Error handling
    error_message = Column(Text, nullable=True)
    cancel_requested = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_genetic_jobs_status_created", "status", "created_at"),
        Index("idx_genetic_jobs_symbol", "symbol"),
    )

    def __repr__(self) -> str:
        return (
            f"<GeneticJob(job_uuid={self.job_uuid}, status={self.status.value}, "
            f"symbol={self.symbol}, progress={self.progress})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "job_id": self.job_uuid,
            "status": self.status.value if isinstance(self.status, GeneticJobStatus) else self.status,
            "progress": self.progress,
            "current_generation": self.current_generation,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "strategy_type": self.strategy_type,
            "best_fitness": self.best_fitness,
            "best_params": self.best_params,
            "n_evaluations": self.n_evaluations,
            "execution_time": self.execution_time,
            "generations_completed": self.generations_completed,
            "improvement_percent": self.improvement_percent,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def to_result_dict(self) -> dict[str, Any]:
        """Convert to result dictionary for API response."""
        return {
            "job_id": self.job_uuid,
            "status": self.status.value if isinstance(self.status, GeneticJobStatus) else self.status,
            "best_fitness": self.best_fitness,
            "best_params": self.best_params,
            "n_evaluations": self.n_evaluations,
            "execution_time": self.execution_time,
            "generations": self.generations_completed,
            "improvement_percent": self.improvement_percent,
            "history": self.history,
            "pareto_front": self.pareto_front,
            "metrics": self.metrics,
        }

    def mark_running(self) -> None:
        """Mark job as running."""
        self.status = GeneticJobStatus.RUNNING  # type: ignore[assignment]
        self.started_at = datetime.now(UTC)  # type: ignore[assignment]
        self.updated_at = datetime.now(UTC)  # type: ignore[assignment]

    def update_progress(self, generation: int, best_fitness: float | None = None) -> None:
        """Update job progress."""
        self.current_generation = generation  # type: ignore[assignment]
        self.progress = min(100.0, (generation / max(self.n_generations, 1)) * 100)  # type: ignore[assignment]
        if best_fitness is not None:
            self.best_fitness = best_fitness  # type: ignore[assignment]
        self.updated_at = datetime.now(UTC)  # type: ignore[assignment]

    def mark_completed(
        self,
        best_fitness: float,
        best_params: dict[str, Any],
        n_evaluations: int,
        execution_time: float,
        generations: int,
        improvement_percent: float,
        history: dict[str, Any],
        pareto_front: list | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Mark job as completed with results."""
        self.status = GeneticJobStatus.COMPLETED  # type: ignore[assignment]
        self.best_fitness = best_fitness  # type: ignore[assignment]
        self.best_params = best_params  # type: ignore[assignment]
        self.n_evaluations = n_evaluations  # type: ignore[assignment]
        self.execution_time = execution_time  # type: ignore[assignment]
        self.generations_completed = generations  # type: ignore[assignment]
        self.improvement_percent = improvement_percent  # type: ignore[assignment]
        self.history = history  # type: ignore[assignment]
        self.pareto_front = pareto_front  # type: ignore[assignment]
        self.metrics = metrics  # type: ignore[assignment]
        self.progress = 100.0  # type: ignore[assignment]
        self.completed_at = datetime.now(UTC)  # type: ignore[assignment]
        self.updated_at = datetime.now(UTC)  # type: ignore[assignment]

    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed."""
        self.status = GeneticJobStatus.FAILED  # type: ignore[assignment]
        self.error_message = error_message  # type: ignore[assignment]
        self.progress = min(self.progress, 100.0)  # type: ignore[assignment]
        self.completed_at = datetime.now(UTC)  # type: ignore[assignment]
        self.updated_at = datetime.now(UTC)  # type: ignore[assignment]

    def mark_cancelled(self) -> None:
        """Mark job as cancelled."""
        self.status = GeneticJobStatus.CANCELLED  # type: ignore[assignment]
        self.cancel_requested = True  # type: ignore[assignment]
        self.completed_at = datetime.now(UTC)  # type: ignore[assignment]
        self.updated_at = datetime.now(UTC)  # type: ignore[assignment]

    def request_cancel(self) -> None:
        """Request cancellation of running job."""
        self.cancel_requested = True  # type: ignore[assignment]
        self.updated_at = datetime.now(UTC)  # type: ignore[assignment]
