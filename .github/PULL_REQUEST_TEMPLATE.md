## Summary

This PR contains changes to finalize Alembic configuration and CI for migration testing:

- `alembic.ini` updated to prefer `DATABASE_URL` env var and document usage
- `backend/migrations/env.py` robustified to prefer env var and avoid configparser interpolation
- Canonical migration file `backend/migrations/versions/1a2b3c4d5e6f_convert_timestamps_to_timestamptz.py`
- README updated with Alembic usage snippet
- CI workflow `.github/workflows/integration-migrations.yml` added (manual dispatch)

## How to test

1. Ensure Docker is running.
2. Set `DATABASE_URL` to a running Postgres and run `alembic upgrade head`.
3. Run `pytest tests/integration/test_migration_timestamptz.py`.

## Notes

- Autogenerate instructions are in `docs/AUTOGENERATE_ALEMBIC.md` if you want to convert to an autogen workflow.
