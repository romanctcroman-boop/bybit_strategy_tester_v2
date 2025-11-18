"""Regression tests ensuring Orchestrator routes stay registered."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import orchestrator


class MockPluginManager:
    """Minimal plugin manager stub for orchestrator router tests."""

    def __init__(self):
        self._plugins = [
            {
                "name": "demo-plugin",
                "version": "1.0.0",
                "status": "active",
                "description": "Mock plugin for regression tests",
            }
        ]

    def list_plugins(self):  # pragma: no cover - simple data return
        return self._plugins

    def get_statistics(self):  # pragma: no cover - simple data return
        return {"total": len(self._plugins)}

    def get_plugin_info(self, name):  # pragma: no cover - simple data return
        for plugin in self._plugins:
            if plugin["name"] == name:
                return plugin
        return None

    async def reload_plugin(self, name):  # pragma: no cover - unused but required
        return None


class MockTaskQueue:
    async def get_priority_statistics(self):  # pragma: no cover - simple data return
        return {"priorities": {"p0": 1, "p1": 2}}


@pytest.fixture
def app():
    orchestrator.set_dependencies(MockPluginManager(), MockTaskQueue())
    app = FastAPI()
    app.include_router(orchestrator.router, prefix="/api/orchestrator", tags=["orchestrator"])
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_orchestrator_system_status(client):
    response = client.get("/api/orchestrator/system-status")
    assert response.status_code == 200
    body = response.json()
    assert body["plugin_manager"]["initialized"] is True
    assert body["priority_system"]["features"]


def test_orchestrator_plugins_and_openapi(client):
    response = client.get("/api/orchestrator/plugins")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_plugins"] == 1
    assert payload["plugins"][0]["name"] == "demo-plugin"

    openapi = client.get("/openapi.json").json()
    orchestrator_paths = [
        path for path in openapi["paths"].keys() if path.startswith("/api/orchestrator/")
    ]
    assert orchestrator_paths, "Orchestrator routes missing from OpenAPI"


def test_priority_statistics_endpoint(client):
    response = client.get("/api/orchestrator/priority/statistics")
    assert response.status_code == 200
    payload = response.json()
    assert "statistics" in payload
    assert "priorities" in payload["statistics"]
