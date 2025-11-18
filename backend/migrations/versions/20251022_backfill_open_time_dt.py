"""
Backfill open_time_dt in bybit_kline_audit from open_time (milliseconds).

Revision ID: 20251022_backfill_open_time_dt
Revises: 20251022_consolidate_heads
Create Date: 2025-10-22
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251022_backfill_open_time_dt"
down_revision = "20251022_consolidate_heads"
branch_labels = None
depends_on = None


def upgrade():
    # Only set values where NULL; interpret epoch milliseconds as UTC
    op.execute(
        """
        UPDATE bybit_kline_audit
        SET open_time_dt = to_timestamp(open_time / 1000.0)
        WHERE open_time_dt IS NULL
        """
    )


def downgrade():
    # Revert backfill by clearing the computed column (safe because source data remains)
    op.execute(
        """
        UPDATE bybit_kline_audit
        SET open_time_dt = NULL
        """
    )
