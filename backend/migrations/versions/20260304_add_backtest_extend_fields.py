"""Add is_extended and source_backtest_id to backtests table

Revision ID: 20260304_backtest_extend
Revises: 20260227_genetic_jobs
Create Date: 2026-03-04

Supports "Extend Backtest to Now" (P2) feature:
- is_extended: marks a backtest created by extending an earlier one
- source_backtest_id: FK (soft, no constraint) to the original backtest
- market_type: optional market type stored per-backtest

NOTE: No FK constraint is created — SQLite does not support adding FK constraints
via ALTER TABLE, and we want both dialects to work without special handling.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260304_backtest_extend"
down_revision = "20260227_genetic_jobs"
branch_labels = None
depends_on = None


def upgrade():
    # is_extended: False for all existing rows
    op.add_column(
        "backtests",
        sa.Column(
            "is_extended",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # source_backtest_id: soft FK, no constraint (SQLite compat)
    op.add_column(
        "backtests",
        sa.Column("source_backtest_id", sa.String(36), nullable=True),
    )
    # market_type: context for which Bybit market the backtest was run on
    op.add_column(
        "backtests",
        sa.Column(
            "market_type",
            sa.String(16),
            nullable=True,
            server_default="linear",
        ),
    )


def downgrade():
    op.drop_column("backtests", "market_type")
    op.drop_column("backtests", "source_backtest_id")
    op.drop_column("backtests", "is_extended")
