"""Add market_type column to bybit_kline_audit

Revision ID: 20260121_market_type
Revises:
Create Date: 2026-01-21

This migration adds the market_type column to distinguish between
SPOT and LINEAR (perpetual) market data. This enables:
1. Parallel loading of both market types
2. TradingView parity (which uses SPOT data)
3. Better data organization
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "20260121_market_type"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add market_type column with default 'linear' for existing data."""
    # Add column with default value
    op.add_column(
        "bybit_kline_audit",
        sa.Column(
            "market_type", sa.String(16), nullable=False, server_default="linear"
        ),
    )

    # Update unique constraint to include market_type
    # First drop old constraint
    try:
        op.drop_constraint(
            "uix_symbol_interval_open_time", "bybit_kline_audit", type_="unique"
        )
    except Exception:
        pass  # Constraint might not exist

    # Create new constraint including market_type
    op.create_unique_constraint(
        "uix_symbol_interval_market_open_time",
        "bybit_kline_audit",
        ["symbol", "interval", "market_type", "open_time"],
    )

    # Add index for market_type queries
    op.create_index("ix_kline_market_type", "bybit_kline_audit", ["market_type"])


def downgrade():
    """Remove market_type column."""
    op.drop_index("ix_kline_market_type", "bybit_kline_audit")
    op.drop_constraint(
        "uix_symbol_interval_market_open_time", "bybit_kline_audit", type_="unique"
    )
    op.drop_column("bybit_kline_audit", "market_type")

    # Restore original constraint
    op.create_unique_constraint(
        "uix_symbol_interval_open_time",
        "bybit_kline_audit",
        ["symbol", "interval", "open_time"],
    )
