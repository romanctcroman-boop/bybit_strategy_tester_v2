import psycopg2
from testcontainers.postgres import PostgresContainer
import importlib.util
from pathlib import Path

# Load migration module by file path because its filename starts with digits and
# cannot be imported via a normal dotted import.
repo_root = Path(__file__).resolve().parents[2]
mig_path = repo_root / 'backend' / 'migrations' / 'versions' / '0001_convert_timestamps_to_timestamptz.py'
spec = importlib.util.spec_from_file_location('mig_mod', str(mig_path))
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)


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


def test_migration_upgrade_and_downgrade():
    with PostgresContainer("postgres:15") as pg:
        raw = pg.get_connection_url()
        if raw.startswith("postgresql+psycopg2://"):
            dsn = raw.replace("postgresql+psycopg2://", "postgresql://", 1)
        else:
            dsn = raw
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()

        # Create sample tables
        cur.execute("DROP TABLE IF EXISTS backtests; DROP TABLE IF EXISTS trades; DROP TABLE IF EXISTS market_data;")
        cur.execute("CREATE TABLE backtests (id serial primary key, started_at timestamp, updated_at timestamp, completed_at timestamp, created_at timestamp);")
        cur.execute("CREATE TABLE trades (id serial primary key, entry_time timestamp, exit_time timestamp, created_at timestamp);")
        cur.execute("CREATE TABLE market_data (id serial primary key, timestamp timestamp);")

        # Confirm initial types
        assert 'timestamp without time zone' in get_column_type(conn, 'backtests', 'started_at')
        assert 'timestamp without time zone' in get_column_type(conn, 'trades', 'entry_time')
        assert 'timestamp without time zone' in get_column_type(conn, 'market_data', 'timestamp')

        # Run upgrade SQLs
        for sql in mig.upgrade_sqls():
            cur.execute(sql)

        # Verify converted
        assert 'timestamp with time zone' in get_column_type(conn, 'backtests', 'started_at')
        assert 'timestamp with time zone' in get_column_type(conn, 'trades', 'entry_time')
        assert 'timestamp with time zone' in get_column_type(conn, 'market_data', 'timestamp')

        # Run downgrade SQLs
        for sql in mig.downgrade_sqls():
            cur.execute(sql)

        # Verify reverted
        assert 'timestamp without time zone' in get_column_type(conn, 'backtests', 'started_at')
        assert 'timestamp without time zone' in get_column_type(conn, 'trades', 'entry_time')
        assert 'timestamp without time zone' in get_column_type(conn, 'market_data', 'timestamp')

        cur.close()
        conn.close()
