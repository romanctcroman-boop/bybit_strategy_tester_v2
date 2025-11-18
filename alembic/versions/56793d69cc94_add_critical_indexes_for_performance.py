"""add_critical_indexes_for_performance

Revision ID: 56793d69cc94
Revises: 
Create Date: 2025-11-12 08:25:13.503791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56793d69cc94'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add critical database indexes for performance optimization.
    
    Based on DeepSeek API audit recommendations:
    - Expected 95-97% query speedup for high-traffic queries
    
    ACTUAL SCHEMA:
    - BackfillProgress: symbol, interval, current_cursor_ms, updated_at
    - BybitKlineAudit: symbol, interval, open_time, open_time_dt, ...
    """
    
    # Priority 1: BackfillProgress Indexes
    # Pattern: symbol + interval queries (backfill status checks every 10s)
    op.create_index(
        'idx_backfill_progress_symbol_interval',
        'backfill_progress',
        ['symbol', 'interval'],
        unique=False
    )
    
    op.create_index(
        'idx_backfill_progress_updated',
        'backfill_progress',
        [sa.text('updated_at DESC')],
        unique=False
    )
    
    # Priority 2: Bybit Klines Time-Series Access (CRITICAL)
    # Pattern: symbol + interval + open_time DESC (main trading data access)
    # Note: open_time already has index, but composite will be much faster
    op.create_index(
        'idx_bybit_kline_symbol_interval_time',
        'bybit_kline_audit',
        ['symbol', 'interval', sa.text('open_time DESC')],
        unique=False
    )
    
    # Recent data queries (last 30 days - most common pattern)
    op.create_index(
        'idx_bybit_kline_recent',
        'bybit_kline_audit',
        ['symbol', 'interval', sa.text('inserted_at DESC')],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes."""
    
    # Drop in reverse order
    op.drop_index('idx_bybit_kline_recent', table_name='bybit_kline_audit')
    op.drop_index('idx_bybit_kline_symbol_interval_time', table_name='bybit_kline_audit')
    op.drop_index('idx_backfill_progress_updated', table_name='backfill_progress')
    op.drop_index('idx_backfill_progress_symbol_interval', table_name='backfill_progress')
