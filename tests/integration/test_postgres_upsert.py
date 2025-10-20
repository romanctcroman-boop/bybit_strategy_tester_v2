import os
import json
import time
import sys
import pathlib

# Ensure repo root is on sys.path so `backend` package imports work during pytest runs
repo_root = pathlib.Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import pytest


DB_URL = os.environ.get('DATABASE_URL')


def pytest_configure(config):
    # make sure tests can import backend package from repo root when run by CI
    import sys, pathlib
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


@pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set - integration test skipped")
def test_postgres_upsert_bybit_audit(tmp_path):
    """Integration test: verify INSERT ... ON CONFLICT updates existing row (upsert) in Postgres.

    This test expects a Postgres instance to be available at DATABASE_URL and Alembic migrations
    already applied (CI job should run migrations before tests).
    """
    from backend.models.bybit_kline_audit import Base, BybitKlineAudit
    from backend.services.adapters.bybit import BybitAdapter

    # Connect to DB
    engine = create_engine(DB_URL, future=True)
    SessionLocal = sessionmaker(bind=engine)

    # Ensure table exists (migrations should have run in CI, but be defensive)
    Base.metadata.create_all(bind=engine)

    # Prepare a sample normalized row
    symbol = 'TESTUSDT'
    open_time = 1609459200000  # 2021-01-01T00:00:00Z in ms
    open_time_dt = '2021-01-01T00:00:00+00:00'
    raw_payload = {"example": True}

    normalized = [{
        'symbol': symbol,
        'open_time': open_time,
        'open_time_dt': open_time_dt,
        'open_price': 100.0,
        'high_price': 110.0,
        'low_price': 90.0,
        'close_price': 105.0,
        'volume': 1.23,
        'turnover': 123.45,
        'raw': json.dumps(raw_payload),
    }]

    # Use the adapter persistence method to insert, then modify and insert again to test upsert
    adapter = BybitAdapter()

    # First insert
    adapter._persist_klines_to_db(symbol, normalized)

    # Modify the row: change close_price and raw
    normalized[0]['close_price'] = 200.5
    normalized[0]['raw'] = json.dumps({"example": "updated"})

    # Second insert should update existing row rather than create duplicate
    adapter._persist_klines_to_db(symbol, normalized)

    # Query DB to assert single row with updated values
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT symbol, open_time, close_price, raw FROM bybit_kline_audit WHERE symbol = :sym AND open_time = :ot"),
            {"sym": symbol, "ot": open_time},
        ).mappings().fetchone()

        assert row is not None, "expected a persisted row in Postgres"
        assert float(row['close_price']) == pytest.approx(200.5)
        assert json.loads(row['raw'])['example'] == 'updated'
