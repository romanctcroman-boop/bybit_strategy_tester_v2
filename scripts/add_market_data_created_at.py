"""Add created_at column to market_data if missing and set default to now()

This script will:
 - ALTER TABLE ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
 - UPDATE existing rows to set created_at = now() where NULL
"""
from backend.core.config import settings
from sqlalchemy import create_engine, text

engine = create_engine(settings.database_url)
with engine.connect() as conn:
    print('Database URL:', settings.database_url)
    try:
        conn.execute(text("ALTER TABLE market_data ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();"))
        conn.commit()
        print('ALTER TABLE add column executed (if not exists).')
    except Exception as e:
        print('ALTER TABLE add column failed:', e)

    try:
        res = conn.execute(text("UPDATE market_data SET created_at = now() WHERE created_at IS NULL;"))
        conn.commit()
        print('UPDATE executed (rows updated):', res.rowcount)
    except Exception as e:
        print('UPDATE failed:', e)
