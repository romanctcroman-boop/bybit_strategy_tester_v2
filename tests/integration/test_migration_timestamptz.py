import psycopg2
from datetime import datetime, timezone

from testcontainers.postgres import PostgresContainer


def get_column_type(conn, table_name, column_name):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT format_type(a.atttypid, a.atttypmod) AS coltype
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE c.relname = %s AND a.attname = %s AND a.attnum > 0;
        """,
        (table_name, column_name),
    )
    res = cur.fetchone()
    cur.close()
    return res[0] if res else None


def test_convert_timestamps_to_timestamptz():
    with PostgresContainer("postgres:15") as pg:
        # testcontainers returns a SQLAlchemy-style URL like
        # postgresql+psycopg2://user:pass@host:port/db
        # psycopg2 accepts a plain postgresql:// URI or a DSN; normalize accordingly.
        raw = pg.get_connection_url()
        if raw.startswith("postgresql+psycopg2://"):
            dsn = raw.replace("postgresql+psycopg2://", "postgresql://", 1)
        else:
            dsn = raw

        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()

        # Create a sample table with timestamp without time zone
        cur.execute("DROP TABLE IF EXISTS backtests;")
        cur.execute(
            """
            CREATE TABLE backtests (
                id SERIAL PRIMARY KEY,
                started_at timestamp,
                updated_at timestamp,
                completed_at timestamp
            );
            """
        )

        # Insert a row with timezone-aware UTC datetime (avoid deprecated utcnow usage)
        now_utc = datetime.now(timezone.utc)
        cur.execute(
            "INSERT INTO backtests (started_at, updated_at, completed_at) VALUES (%s, %s, %s)",
            (now_utc, now_utc, now_utc),
        )

        # Confirm initial column types are timestamp without time zone
        t1 = get_column_type(conn, "backtests", "started_at")
        assert "timestamp without time zone" in t1

        # Apply migration SQL (like the Alembic template)
        cur.execute("ALTER TABLE backtests ALTER COLUMN started_at TYPE timestamptz USING started_at AT TIME ZONE 'UTC';")
        cur.execute("ALTER TABLE backtests ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'UTC';")
        cur.execute("ALTER TABLE backtests ALTER COLUMN completed_at TYPE timestamptz USING completed_at AT TIME ZONE 'UTC';")

        # Verify the column type changed to timestamptz
        t2 = get_column_type(conn, "backtests", "started_at")
        assert "timestamp with time zone" in t2

        # Clean up
        cur.close()
        conn.close()
