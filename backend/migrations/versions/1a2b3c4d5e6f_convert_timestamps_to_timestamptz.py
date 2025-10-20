"""
Alembic revision template to convert timestamp columns to timestamptz (Postgres).

IMPORTANT: This is a template. Adapt table and column names to your schema before running.

Revision ID: 0001_convert_timestamps_to_timestamptz
Revises: None
Create Date: 2025-10-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Run the conditional upgrade statements
    for sql in upgrade_sqls():
        op.execute(sql)


def downgrade():
        # Run the conditional downgrade statements
        for sql in downgrade_sqls():
                op.execute(sql)


def upgrade_sqls():
        """Return a list of SQL statements that safely convert candidate timestamp columns to timestamptz.

        Each statement checks information_schema first so running the migration against different schemas
        / partial installations is safe (no-op when the column/table does not exist or is already timestamptz).
        """
        candidates = {
                'backtests': ['started_at', 'updated_at', 'completed_at', 'created_at'],
                'optimizations': ['started_at', 'updated_at', 'completed_at', 'created_at'],
                'trades': ['entry_time', 'exit_time', 'created_at'],
                'market_data': ['timestamp'],
                'strategies': ['created_at', 'updated_at'],
        }

        stmts = []
        for table, cols in candidates.items():
                for col in cols:
                        stmt = f"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = '{table}' AND column_name = '{col}' AND data_type = 'timestamp without time zone'
    ) THEN
        EXECUTE 'ALTER TABLE {table} ALTER COLUMN {col} TYPE timestamptz USING {col} AT TIME ZONE ''UTC'';';
    END IF;
END$$;
"""
                        stmts.append(stmt)
        return stmts


def downgrade_sqls():
        """Return a list of SQL statements that revert timestamptz columns back to timestamp (without time zone).

        These statements only run when the column exists and is currently timestamptz.
        """
        candidates = {
                'backtests': ['started_at', 'updated_at', 'completed_at', 'created_at'],
                'optimizations': ['started_at', 'updated_at', 'completed_at', 'created_at'],
                'trades': ['entry_time', 'exit_time', 'created_at'],
                'market_data': ['timestamp'],
                'strategies': ['created_at', 'updated_at'],
        }

        stmts = []
        for table, cols in candidates.items():
                for col in cols:
                        stmt = f"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = '{table}' AND column_name = '{col}' AND data_type = 'timestamp with time zone'
    ) THEN
        EXECUTE 'ALTER TABLE {table} ALTER COLUMN {col} TYPE timestamp USING {col}::timestamp;';
    END IF;
END$$;
"""
                        stmts.append(stmt)
        return stmts
