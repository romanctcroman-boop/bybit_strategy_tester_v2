"""Add performance indexes for kline queries

Revision ID: 20251220_add_performance_indexes
Revises: 20251029_add_interval_to_kline_audit
Create Date: 2025-12-20

This migration adds critical indexes identified by DeepSeek expert review:
1. Main query pattern: (symbol, interval, open_time DESC) for get_klines()
2. Coverage check: (symbol, interval, open_time ASC) for aggregations
3. Gap detection: (open_time) for window function queries

Performance impact:
- Eliminates full table scans for common queries
- Improves get_klines() from O(n) to O(log n)
- Speeds up gap detection queries significantly
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251220_add_performance_indexes"
down_revision = "20251029_add_interval_to_kline_audit"
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes."""

    # Index 1: Main query pattern
    # Used by: get_klines(), get_latest(), SmartKlineService.get_candles()
    # Pattern: SELECT ... WHERE symbol=? AND interval=? ORDER BY open_time DESC LIMIT ?
    op.create_index(
        "idx_kline_main_query",
        "bybit_kline_audit",
        ["symbol", "interval", "open_time"],
    )

    # Index 2: Gap detection
    # Used by: find_gaps(), find_timestamp_gaps()
    # Pattern: LEAD(open_time) OVER (ORDER BY open_time) WHERE symbol=? AND interval=?
    op.create_index(
        "idx_kline_gap_detection",
        "bybit_kline_audit",
        ["open_time"],
    )

    # Index 3: Freshness check (for MAX queries)
    # Used by: check_freshness(), _ensure_data_freshness()
    # Pattern: SELECT MAX(open_time) WHERE symbol=? AND interval=?
    # Note: Covered by idx_kline_main_query, but explicit for clarity
    op.create_index(
        "idx_kline_freshness",
        "bybit_kline_audit",
        ["symbol", "interval"],
        postgresql_where="open_time IS NOT NULL",
    )


def downgrade():
    """Remove performance indexes."""
    op.drop_index("idx_kline_freshness", "bybit_kline_audit")
    op.drop_index("idx_kline_gap_detection", "bybit_kline_audit")
    op.drop_index("idx_kline_main_query", "bybit_kline_audit")
