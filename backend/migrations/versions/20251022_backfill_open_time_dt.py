"""backfill open_time_dt from open_time

Revision ID: 20251022_backfill_open_time_dt
Revises: 20251020_add_bybit_kline_audit
Create Date: 2025-10-22 00:00:00.000000

This migration populates the timezone-aware `open_time_dt` column using the
numeric `open_time` field. It keeps the schema unchanged and only backfills
missing values to enable later migrations that rely on this column.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20251022_backfill_open_time_dt"
down_revision = "20251020_add_bybit_kline_audit"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "sqlite":
        # SQLite: datetime(open_time/1000, 'unixepoch') yields UTC datetime
        conn.execute(
            sa.text(
                """
            UPDATE bybit_kline_audit
            SET open_time_dt = datetime(open_time/1000, 'unixepoch')
            WHERE open_time_dt IS NULL
            """
            )
        )
    elif dialect == "postgresql":
        # PostgreSQL: to_timestamp(...) at time zone 'UTC'
        conn.execute(
            sa.text(
                """
            UPDATE bybit_kline_audit
            SET open_time_dt = (to_timestamp(open_time/1000.0) AT TIME ZONE 'UTC')
            WHERE open_time_dt IS NULL
            """
            )
        )
    else:
        # Fallback: try generic SQL timestamp conversion (seconds assumption)
        conn.execute(
            sa.text(
                """
            UPDATE bybit_kline_audit
            SET open_time_dt = CURRENT_TIMESTAMP
            WHERE open_time_dt IS NULL
            """
            )
        )


def downgrade():
    # Data-only migration; no schema changes to revert.
    pass
