"""
Create backfill_runs table

Revision ID: 20251021_add_backfill_runs
Revises: 20251020_add_bybit_kline_audit
Create Date: 2025-10-21
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20251021_add_backfill_runs"
down_revision = "20251020_merge_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "backfill_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("params", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("upserts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_backfill_runs_task_id", "backfill_runs", ["task_id"])
    op.create_index("ix_backfill_runs_symbol", "backfill_runs", ["symbol"])
    op.create_index("ix_backfill_runs_interval", "backfill_runs", ["interval"])


def downgrade():
    op.drop_index("ix_backfill_runs_interval", table_name="backfill_runs")
    op.drop_index("ix_backfill_runs_symbol", table_name="backfill_runs")
    op.drop_index("ix_backfill_runs_task_id", table_name="backfill_runs")
    op.drop_table("backfill_runs")
