Autogenerate Alembic revision

This repository currently contains a safe, hand-written migration in
`backend/migrations/versions/1a2b3c4d5e6f_convert_timestamps_to_timestamptz.py`.

If you want to use `alembic --autogenerate` to create revisions automatically, do the following:

1) Ensure your SQLAlchemy metadata is importable from `backend` (example):

   # in your models package
   from sqlalchemy.orm import declarative_base
   Base = declarative_base()

   # define models that attach to Base

2) Update `backend/migrations/env.py` to expose `target_metadata`:

   from backend.models import Base
   target_metadata = Base.metadata

   (The current `env.py` prefers DATABASE_URL from environment. Add the import above in the online/offline configuration branch.)

3) Run the autogenerate command in your virtualenv with DATABASE_URL set to a dev DB:

   $env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/postgres'
   D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe -m alembic revision --autogenerate -m "describe change"

4) Review the generated migration script carefully. Autogenerate can miss edge cases and may need manual edits (especially for data migrations, timezone conversions, and conditional checks).

Notes:
- Because a migration to change timestamp types is sensitive, prefer to keep the tested manual template unless you have a complete metadata and strong test coverage.
- If you need help wiring `Base` into env.py, include the path to your models (module and variable name) and I can patch `env.py` for you and run `alembic revision --autogenerate`.
