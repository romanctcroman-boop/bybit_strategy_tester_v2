"""Add genetic_jobs table for genetic algorithm optimization

Revision ID: 20260227_genetic_jobs
Revises: 20260201_strategy_versions
Create Date: 2026-02-27

Stores genetic algorithm optimization jobs and results.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260227_genetic_jobs"
down_revision = "20260201_strategy_versions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "genetic_jobs",
        # Primary key
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_uuid", sa.String(36), nullable=False),
        # Status
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="geneticjobstatus"),
            nullable=False,
            default="PENDING",
        ),
        sa.Column("progress", sa.Float(), default=0.0),
        sa.Column("current_generation", sa.Integer(), default=0),
        # Request configuration
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("end_date", sa.String(10), nullable=False),
        sa.Column("strategy_type", sa.String(64), nullable=False),
        # Genetic algorithm parameters
        sa.Column("param_ranges", sa.JSON(), nullable=True),
        sa.Column("fitness_function", sa.String(64), default="sharpe"),
        sa.Column("population_size", sa.Integer(), default=50),
        sa.Column("n_generations", sa.Integer(), default=100),
        sa.Column("selection_strategy", sa.String(32), default="tournament"),
        sa.Column("crossover_operator", sa.String(32), default="arithmetic"),
        sa.Column("mutation_operator", sa.String(32), default="gaussian"),
        sa.Column("elitism_rate", sa.Float(), default=0.1),
        sa.Column("crossover_rate", sa.Float(), default=0.8),
        sa.Column("mutation_rate", sa.Float(), default=0.1),
        sa.Column("multi_objective_weights", sa.JSON(), nullable=True),
        sa.Column("n_workers", sa.Integer(), default=1),
        sa.Column("random_state", sa.Integer(), nullable=True),
        # Results
        sa.Column("best_fitness", sa.Float(), nullable=True),
        sa.Column("best_params", sa.JSON(), nullable=True),
        sa.Column("n_evaluations", sa.Integer(), default=0),
        sa.Column("execution_time", sa.Float(), nullable=True),
        sa.Column("generations_completed", sa.Integer(), default=0),
        sa.Column("improvement_percent", sa.Float(), default=0.0),
        sa.Column("history", sa.JSON(), nullable=True),
        sa.Column("pareto_front", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        # Error handling
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), default=False),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes
    op.create_index("ix_genetic_jobs_job_uuid", "genetic_jobs", ["job_uuid"], unique=True)
    op.create_index("ix_genetic_jobs_status", "genetic_jobs", ["status"])
    op.create_index("ix_genetic_jobs_created_at", "genetic_jobs", ["created_at"])
    op.create_index("ix_genetic_jobs_symbol", "genetic_jobs", ["symbol"])
    op.create_index("ix_genetic_jobs_status_created", "genetic_jobs", ["status", "created_at"])


def downgrade():
    # Drop indexes
    op.drop_index("ix_genetic_jobs_status_created", table_name="genetic_jobs")
    op.drop_index("ix_genetic_jobs_symbol", table_name="genetic_jobs")
    op.drop_index("ix_genetic_jobs_created_at", table_name="genetic_jobs")
    op.drop_index("ix_genetic_jobs_status", table_name="genetic_jobs")
    op.drop_index("ix_genetic_jobs_job_uuid", table_name="genetic_jobs")

    # Drop table
    op.drop_table("genetic_jobs")

    # Drop enum type (PostgreSQL only)
    # Note: SQLAlchemy creates the enum type automatically, but we need to drop it manually
    # This is safe to run on SQLite as it will be ignored
    op.execute("DROP TYPE IF EXISTS geneticjobstatus")
