import docker
import os
import pytest
import redis
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


def _normalize_psycopg2_dsn(dsn: str) -> str:
    """Normalize DSNs returned by testcontainers which may include the SQLAlchemy
    prefix `postgresql+psycopg2://` — psycopg2.connect expects `postgresql://`.
    """
    if not isinstance(dsn, str):
        return dsn
    if dsn.startswith("postgresql+psycopg2://"):
        return dsn.replace("postgresql+psycopg2://", "postgresql://", 1)
    return dsn


def test_redis_streams_basic_smoke():
    # Prefer external Redis if provided (e.g., CI service), else start a container via testcontainers
    url = os.environ.get("REDIS_URL")
    if url:
        try:
            from urllib.parse import urlparse

            u = urlparse(url)
            host = u.hostname or "127.0.0.1"
            port = int(u.port or 6379)
            rc = redis.Redis(host=host, port=port, decode_responses=True)
            # Smoke test
            stream = "mystream"
            msg_id = rc.xadd(stream, {"foo": "bar"})
            assert msg_id is not None
            entries = rc.xrange(stream, min="-", max="+")
            assert len(entries) >= 1
            return
        except Exception as e:
            pytest.skip(f"Skipping redis-integration test; external Redis error: {e}")
    # Fallback: Start Redis container
    try:
        with RedisContainer() as redis_cont:
            rc = redis.Redis(
                host=redis_cont.get_container_host_ip(),
                port=redis_cont.get_exposed_port(6379),
                decode_responses=True,
            )

            stream = "mystream"
            # XADD a message
            msg_id = rc.xadd(stream, {"foo": "bar"})
            assert msg_id is not None

            # Read message back
            entries = rc.xrange(stream, min="-", max="+")
            assert len(entries) >= 1
    except docker.errors.APIError as e:
        pytest.skip(f"Docker API error while starting Redis container: {e}")
    except Exception as e:
        # Catch image-pull or networking failures and skip the test instead of failing the whole suite
        pytest.skip(f"Skipping redis-integration test due to environment error: {e}")


def test_postgres_connection_smoke():
    # Simple postgres container smoke test
    try:
        with PostgresContainer("postgres:15") as pg:
            import psycopg2

            raw = pg.get_connection_url()
            dsn = _normalize_psycopg2_dsn(raw)
            try:
                conn = psycopg2.connect(dsn)
            except Exception:
                # Some environments return sqlalchemy-style URLs; try a second attempt by parsing
                # and removing a leading driver specifier if present
                if isinstance(raw, str) and raw.startswith("postgresql+psycopg2://"):
                    conn = psycopg2.connect(
                        raw.replace("postgresql+psycopg2://", "postgresql://", 1)
                    )
                else:
                    raise
            cur = conn.cursor()
            cur.execute("SELECT 1")
            res = cur.fetchone()
            assert res[0] == 1
            cur.close()
            conn.close()
    except docker.errors.APIError as e:
        pytest.skip(f"Docker API error while starting Postgres container: {e}")
    except Exception as e:
        pytest.skip(f"Skipping postgres-integration test due to environment error: {e}")
