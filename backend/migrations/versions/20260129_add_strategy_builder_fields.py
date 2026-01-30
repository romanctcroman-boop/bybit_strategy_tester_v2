"""Add Strategy Builder fields to strategies table

Revision ID: 20260129_strategy_builder
Revises: 20260121_market_type
Create Date: 2026-01-29

This migration adds fields to support the visual Strategy Builder:
- builder_graph: Full strategy graph (JSON)
- builder_blocks: Array of blocks (JSON)
- builder_connections: Array of connections (JSON)
- is_builder_strategy: Flag to identify builder-created strategies

These fields allow storing visual block-based strategies in the database.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers
revision = "20260129_strategy_builder"
down_revision = "20260121_market_type"  # After market_type migration
branch_labels = None
depends_on = None


def upgrade():
    """Add Strategy Builder fields to strategies table."""
    # Add builder_graph column (JSON)
    op.add_column(
        "strategies",
        sa.Column("builder_graph", sa.JSON, nullable=True),
    )

    # Add builder_blocks column (JSON)
    op.add_column(
        "strategies",
        sa.Column("builder_blocks", sa.JSON, nullable=True),
    )

    # Add builder_connections column (JSON)
    op.add_column(
        "strategies",
        sa.Column("builder_connections", sa.JSON, nullable=True),
    )

    # Add is_builder_strategy column (Boolean, default False)
    op.add_column(
        "strategies",
        sa.Column("is_builder_strategy", sa.Boolean(), nullable=False, server_default="0"),
    )

    # Create index on is_builder_strategy for faster queries
    op.create_index(
        "ix_strategies_is_builder_strategy",
        "strategies",
        ["is_builder_strategy"],
    )


def downgrade():
    """Remove Strategy Builder fields from strategies table."""
    # Drop index
    op.drop_index("ix_strategies_is_builder_strategy", table_name="strategies")

    # Drop columns
    op.drop_column("strategies", "is_builder_strategy")
    op.drop_column("strategies", "builder_connections")
    op.drop_column("strategies", "builder_blocks")
    op.drop_column("strategies", "builder_graph")
