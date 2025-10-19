"""Check and (optionally) fix market_data.created_at default

This script uses SQLAlchemy settings from the project config to connect
and check information_schema. If the column_default does not contain
now(), it will ALTER the table to set DEFAULT now().
"""
from backend.core.config import settings
from sqlalchemy import create_engine, text

engine = create_engine(settings.database_url)

with engine.connect() as conn:
    result = conn.execute(text("SELECT column_default FROM information_schema.columns WHERE table_name='market_data' AND column_name='created_at';"))
    row = result.fetchone()
    current = row[0] if row else None
    print('current_default:', repr(current))

    if current is None or 'now(' not in (current or '').lower():
        print('Default not set to now(), applying ALTER TABLE ...')
        try:
            conn.execute(text("ALTER TABLE market_data ALTER COLUMN created_at SET DEFAULT now();"))
            conn.commit()
            print('ALTER applied')
            result = conn.execute(text("SELECT column_default FROM information_schema.columns WHERE table_name='market_data' AND column_name='created_at';"))
            print('new_default:', repr(result.fetchone()[0]))
        except Exception as e:
            print('Failed to apply ALTER:', e)
    else:
        print('Default is already using now(); no action needed')
