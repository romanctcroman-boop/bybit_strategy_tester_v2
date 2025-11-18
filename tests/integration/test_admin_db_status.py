import os

from alembic import command
from alembic.config import Config
from testcontainers.postgres import PostgresContainer


def test_admin_db_status_reports_version():
    # Start ephemeral Postgres
    with PostgresContainer("postgres:15") as pg:
        # Normalize DSN for psycopg3 / SQLAlchemy
        raw = pg.get_connection_url()
        if raw.startswith("postgresql+psycopg2://"):
            dsn = raw.replace("postgresql+psycopg2://", "postgresql://", 1)
        else:
            dsn = raw

        # Apply Alembic migrations to this DB
        os.environ["DATABASE_URL"] = dsn
        cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "..", "alembic.ini"))
        command.upgrade(cfg, "head")

        # Import app after DATABASE_URL is set so engine binds to this DB
        from fastapi.testclient import TestClient

        from backend.api.app import app

        client = TestClient(app)

        # Basic auth admi:admin (per default in admin router)
        auth = ("admi", "admin")
        r = client.get("/api/v1/admin/db/status", auth=auth)
        assert r.status_code == 200
        payload = r.json()
        assert payload.get("ok") is True
        assert payload.get("connectivity") is True
        # Expect some alembic version string present
        assert isinstance(payload.get("alembic_version"), str) and payload["alembic_version"]
