"""
Alembic revision to convert timestamp columns to timestamptz (Postgres).

This revision is a machine-generated companion to the existing template and is
safe/idempotent: each statement checks information_schema before altering a
column. It is chained to the previous revision `1a2b3c4d5e6f` so it can be
applied safely even if the previous template was already applied.

Revision ID: 2f4e6a7b8c9d
Revises: 1a2b3c4d5e6f
Create Date: 2025-10-20
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "2f4e6a7b8c9d"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade():
    for sql in upgrade_sqls():
        op.execute(sql)


def downgrade():
    for sql in downgrade_sqls():
        op.execute(sql)


def upgrade_sqls():
    candidates = {
        "backtests": ["started_at", "updated_at", "completed_at", "created_at"],
        "optimizations": ["started_at", "updated_at", "completed_at", "created_at"],
        "trades": ["entry_time", "exit_time", "created_at"],
        "market_data": ["timestamp"],
        "strategies": ["created_at", "updated_at"],
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
    candidates = {
        "backtests": ["started_at", "updated_at", "completed_at", "created_at"],
        "optimizations": ["started_at", "updated_at", "completed_at", "created_at"],
        "trades": ["entry_time", "exit_time", "created_at"],
        "market_data": ["timestamp"],
        "strategies": ["created_at", "updated_at"],
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
