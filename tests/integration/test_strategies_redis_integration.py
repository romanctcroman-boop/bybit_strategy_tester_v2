"""Integration-style test for strategies router with real Redis if available.

Attempts to start or connect to a local Redis instance. If Docker / Redis not
available, test is skipped gracefully.

Focus:
  - Ensure oversized config is rejected (limits added in schemas)
  - (Placeholder) Future: verify cache set/get against real Redis backend
"""

import os
import socket
import subprocess
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers import strategies as strategies_module
from backend.api.schemas import StrategyCreate

REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def ensure_redis():
    """Ensure Redis is available; try docker run if not. Skip on failure."""
    if _port_open(REDIS_HOST, REDIS_PORT):
        yield
        return

    # Attempt to start ephemeral redis via docker (if docker CLI present)
    docker = subprocess.run(["docker", "--version"], capture_output=True, text=True)
    if docker.returncode != 0:
        pytest.skip("Docker not available; skipping Redis integration test")

    container_name = "test_redis_strategies"
    run = subprocess.run([
        "docker", "run", "-d", "--rm", "-p", f"{REDIS_PORT}:6379", "--name", container_name, "redis:7-alpine"
    ], capture_output=True, text=True)
    if run.returncode != 0:
        pytest.skip("Failed to start redis container; skipping")

    # Wait a bit for Redis to be ready
    for _ in range(10):
        if _port_open(REDIS_HOST, REDIS_PORT):
            break
        time.sleep(0.5)
    else:
        pytest.skip("Redis did not become ready in time")

    yield

    subprocess.run(["docker", "stop", container_name])


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(strategies_module.router, prefix="/strategies", tags=["strategies"])
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestStrategyConfigLimitsIntegration:
    def test_oversized_config_rejected(self, client, ensure_redis):
        # 21 keys exceeds MAX_KEYS=20
        big_config = {f"k{i}": i for i in range(21)}
        payload = {
            "name": "Cfg Limit",
            "description": "Oversized config keys",
            "strategy_type": "sr_rsi",
            "config": big_config,
            "is_active": True,
        }
        response = client.post("/strategies/", json=payload)
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("too many keys" in str(err.get("msg", "")) for err in detail)

    def test_value_length_limit(self, client, ensure_redis):
        long_value = "x" * 201
        payload = {
            "name": "Cfg Value Limit",
            "description": "Oversized value",
            "strategy_type": "sr_rsi",
            "config": {"rsi_period": 14, "overbought": 70, "oversold": 30, "extra": long_value},
            "is_active": True,
        }
        response = client.post("/strategies/", json=payload)
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("exceeds max length" in str(err.get("msg", "")) for err in detail)
