"""Add strategy_versions table for versioning

Revision ID: 20260201_strategy_versions
Revises: 20260129_strategy_builder
Create Date: 2026-02-01

Stores version history of Strategy Builder strategies.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260201_strategy_versions"
down_revision = "20260129_strategy_builder"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("graph_json", sa.JSON, nullable=True),
        sa.Column("blocks_json", sa.JSON, nullable=True),
        sa.Column("connections_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_strategy_versions_strategy_id",
        "strategy_versions",
        ["strategy_id"],
    )
    op.create_index(
        "ix_strategy_versions_strategy_version",
        "strategy_versions",
        ["strategy_id", "version"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_strategy_versions_strategy_version", table_name="strategy_versions")
    op.drop_index("ix_strategy_versions_strategy_id", table_name="strategy_versions")
    op.drop_table("strategy_versions")
