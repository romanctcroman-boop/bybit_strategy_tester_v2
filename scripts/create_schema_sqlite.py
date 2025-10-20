"""Create local SQLite schema from SQLAlchemy models for quick development smoke tests.

Usage (PowerShell):
$env:DATABASE_URL="sqlite:///$(Resolve-Path .)\dev.db"; D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe scripts/create_schema_sqlite.py
"""
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database import engine, Base
# Import models so they are registered with Base.metadata
import backend.models.bybit_kline_audit  # noqa: F401


def main():
    print('Creating database schema using', engine)
    Base.metadata.create_all(bind=engine)
    print('Schema created')


if __name__ == '__main__':
    main()
