"""
Helpers to generate safe SQL for converting timestamp columns to timestamptz and back.

Extracted from the original template migration to avoid Alembic branching when tests
import helpers by path. Tests should import these functions instead of loading a
versioned migration file directly.
"""


def upgrade_sqls():
    """Return SQL statements that safely convert candidate timestamp columns to timestamptz.

    Each statement checks information_schema first so running the migration against different schemas
    or partial installations is safe (no-op when the column/table does not exist or is already timestamptz).
    """
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
    """Return SQL statements that revert timestamptz columns back to timestamp (without time zone)."""
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
