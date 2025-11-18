"""add interval field to bybit_kline_audit for MTF support

Revision ID: 20251029_add_interval_to_kline_audit
Revises: 20251022_consolidate_heads
Create Date: 2025-10-29 14:00:00.000000

This migration adds the 'interval' field to bybit_kline_audit to support
multi-timeframe data storage. The unique constraint is updated to prevent
duplicates across (symbol, interval, open_time) instead of just (symbol, open_time).

IMPORTANT: This migration handles existing data by:
1. Adding 'interval' column with default '15' (most common timeframe)
2. Dropping old unique constraint
3. Creating new unique constraint with interval
4. Creating composite index for efficient queries

After migration, update existing data to correct intervals if needed.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20251029_add_interval_to_kline_audit"
down_revision = "20251022_backfill_open_time_dt"
branch_labels = None
depends_on = None


def upgrade():
    """Add interval field and update constraints for MTF support."""
    
    # Step 1: Add interval column with default value '15'
    # This ensures existing rows get a valid interval value
    op.add_column(
        "bybit_kline_audit",
        sa.Column("interval", sa.String(10), nullable=False, server_default="15"),
    )
    
    # Step 2: Create index on interval for better query performance
    op.create_index(
        "ix_bybit_kline_audit_interval",
        "bybit_kline_audit",
        ["interval"],
    )
    
    # Step 3: Drop old unique constraint (symbol, open_time)
    op.drop_constraint(
        "uix_symbol_open_time",
        "bybit_kline_audit",
        type_="unique",
    )
    
    # Step 4: Create new unique constraint (symbol, interval, open_time)
    op.create_unique_constraint(
        "uix_symbol_interval_open_time",
        "bybit_kline_audit",
        ["symbol", "interval", "open_time"],
    )
    
    # Step 5: Create composite index for efficient MTF queries
    # This index supports queries filtering by symbol, interval, and time range
    op.create_index(
        "ix_bybit_kline_audit_symbol_interval_time",
        "bybit_kline_audit",
        ["symbol", "interval", "open_time"],
    )


def downgrade():
    """Revert to single-timeframe schema (remove interval field)."""
    
    # Step 1: Drop composite index
    op.drop_index("ix_bybit_kline_audit_symbol_interval_time", "bybit_kline_audit")
    
    # Step 2: Drop new unique constraint
    op.drop_constraint("uix_symbol_interval_open_time", "bybit_kline_audit", type_="unique")
    
    # Step 3: Recreate old unique constraint (symbol, open_time)
    op.create_unique_constraint(
        "uix_symbol_open_time",
        "bybit_kline_audit",
        ["symbol", "open_time"],
    )
    
    # Step 4: Drop interval index
    op.drop_index("ix_bybit_kline_audit_interval", "bybit_kline_audit")
    
    # Step 5: Drop interval column
    op.drop_column("bybit_kline_audit", "interval")

