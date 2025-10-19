import time
import redis
import pytest

from testcontainers.redis import RedisContainer
from testcontainers.postgres import PostgresContainer


def test_redis_streams_basic_smoke():
    # Start Redis container
    with RedisContainer() as redis_cont:
        rc = redis.Redis(host=redis_cont.get_container_host_ip(), port=redis_cont.get_exposed_port(6379), decode_responses=True)

        stream = "mystream"
        # XADD a message
        msg_id = rc.xadd(stream, {"foo": "bar"})
        assert msg_id is not None

        # Read message back
        entries = rc.xrange(stream, min='-', max='+')
        assert len(entries) >= 1


def test_postgres_connection_smoke():
    # Simple postgres container smoke test
    with PostgresContainer("postgres:15") as pg:
        import psycopg2
        conn = psycopg2.connect(pg.get_connection_url())
        cur = conn.cursor()
        cur.execute("SELECT 1")
        res = cur.fetchone()
        assert res[0] == 1
        cur.close()
        conn.close()
