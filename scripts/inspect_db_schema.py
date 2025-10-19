"""Inspect DB schema: list tables and show alembic_version"""
from backend.core.config import settings
from sqlalchemy import create_engine, text

engine = create_engine(settings.database_url)
with engine.connect() as conn:
    print('Database URL:', settings.database_url)
    print('\nTables in public schema:')
    res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"))
    for row in res:
        print('-', row[0])

    print('\nCheck alembic_version:')
    try:
        r = conn.execute(text("SELECT version_num FROM alembic_version;"))
        row = r.fetchone()
        if row:
            print('alembic_version:', row[0])
        else:
            print('alembic_version table empty')
    except Exception as e:
        print('alembic_version not present or error:', e)

    print('\nCheck market_data columns:')
    try:
        rc = conn.execute(text("SELECT column_name, column_default FROM information_schema.columns WHERE table_name='market_data' ORDER BY ordinal_position;"))
        rows = rc.fetchall()
        if not rows:
            print('No columns for market_data (table may not exist)')
        else:
            for r in rows:
                print(r[0], 'default=', r[1])
    except Exception as e:
        print('Error inspecting market_data:', e)
