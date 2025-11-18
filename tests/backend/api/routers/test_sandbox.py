"""Tests for backend.api.routers.sandbox"""

import json
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers import sandbox as sandbox_module
from backend.core.code_validator import RiskLevel, ValidationResult
from backend.services.sandbox_executor import SandboxExecutionResult


# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------


class DummyExecutor:
    def __init__(self, result: SandboxExecutionResult | Exception):
        self._result = result
        self.cleaned = False
        self.calls: list[Dict[str, Any]] = []

    async def execute(self, code: str, timeout: int | None = None, env_vars: Dict[str, str] | None = None, working_dir: str = "/workspace"):
        self.calls.append({"code": code, "timeout": timeout, "env_vars": env_vars})
        if isinstance(self._result, Exception):
            raise self._result
        return self._result

    def cleanup(self):
        self.cleaned = True


class DummyExecutorFactory:
    def __init__(self, executor: DummyExecutor):
        self.executor = executor
        self.created_with: list[Dict[str, Any]] = []

    def create(self, *, timeout: int, memory_limit: str, cpu_limit: float):
        self.created_with.append(
            {"timeout": timeout, "memory_limit": memory_limit, "cpu_limit": cpu_limit}
        )
        return self.executor


class FakeDockerImages:
    def __init__(self, missing_image: bool, image_not_found_exception: type[Exception]):
        self._missing = missing_image
        self._exception = image_not_found_exception

    def get(self, image_name: str):
        if self._missing:
            raise self._exception("not found")


class FakeDockerClient:
    def __init__(self, missing_image: bool, image_not_found_exception: type[Exception]):
        self.images = FakeDockerImages(missing_image, image_not_found_exception)
        self.closed = False

    def version(self):
        return {
            "Version": "25.0",
            "ApiVersion": "1.44",
            "Os": "linux",
            "Arch": "amd64",
        }

    def close(self):
        self.closed = True


class FakeDockerProvider:
    class DockerUnavailable(Exception):
        pass

    class ImageMissing(Exception):
        pass

    def __init__(self, *, unavailable: bool = False, missing_image: bool = False):
        self.unavailable = unavailable
        self.missing_image = missing_image
        self.DockerException = FakeDockerProvider.DockerUnavailable
        self.ImageNotFound = FakeDockerProvider.ImageMissing

    def create_client(self):
        if self.unavailable:
            raise self.DockerException("docker offline")
        return FakeDockerClient(self.missing_image, self.ImageNotFound)


class StubValidator:
    def __init__(self, result: ValidationResult):
        self._result = result

    def validate(self, code: str) -> ValidationResult:  # pragma: no cover - simple passthrough
        return self._result


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


@pytest.fixture
def app():
    app = FastAPI()
    # Router already defines prefix/tags, avoid double-prefixing in tests
    app.include_router(sandbox_module.router)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------


def test_execute_code_success(client, app):
    validation_result = ValidationResult(
        is_valid=True,
        risk_score=5,
        risk_level=RiskLevel.LOW,
        violations=[],
        warnings=[],
        recommendations=["ok"],
    )
    sandbox_result = SandboxExecutionResult(
        success=True,
        exit_code=0,
        stdout="done",
        stderr="",
        execution_time=0.42,
        resource_usage={"memory_usage_mb": 12},
        validation_result=validation_result,
        error=None,
    )

    executor = DummyExecutor(sandbox_result)
    factory = DummyExecutorFactory(executor)
    app.dependency_overrides[sandbox_module.get_executor_factory_dependency] = lambda: factory

    payload = {
        "code": "print('hi')",
        "timeout": 120,
        "memory_limit": "256m",
        "cpu_limit": 1.5,
        "input_data": {"foo": "bar"},
    }

    response = client.post("/sandbox/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["stdout"] == "done"
    assert data["validation_result"]["risk_score"] == 5
    assert factory.created_with == [
        {"timeout": 120, "memory_limit": "256m", "cpu_limit": 1.5}
    ]
    assert executor.cleaned is True
    assert executor.calls[0]["env_vars"] == {"SANDBOX_INPUT": json.dumps({"foo": "bar"})}


def test_execute_code_executor_error(client, app):
    executor = DummyExecutor(RuntimeError("boom"))
    factory = DummyExecutorFactory(executor)
    app.dependency_overrides[sandbox_module.get_executor_factory_dependency] = lambda: factory

    payload = {
        "code": "print('hi')",
        "timeout": 60,
        "memory_limit": "256m",
        "cpu_limit": 1.0,
    }
    response = client.post("/sandbox/execute", json=payload)
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Execution failed")
    assert executor.cleaned is True


def test_validate_code_uses_dependency(client, app):
    fake_validator = StubValidator(
        ValidationResult(
            is_valid=False,
            risk_score=45,
            risk_level=RiskLevel.MEDIUM,
            violations=[{"message": "bad"}],
            warnings=["warn"],
            recommendations=["fix"],
        )
    )

    app.dependency_overrides[sandbox_module.get_code_validator_dependency] = lambda: fake_validator

    response = client.post(
        "/sandbox/validate",
        json={"code": "print('x')", "max_complexity": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert body["risk_score"] == 45
    assert body["violations"][0]["message"] == "bad"


def test_get_sandbox_status_success(client, app):
    provider = FakeDockerProvider(unavailable=False, missing_image=False)
    app.dependency_overrides[sandbox_module.get_docker_client_provider_dependency] = lambda: provider

    response = client.get("/sandbox/status")
    payload = response.json()
    assert response.status_code == 200
    assert payload["docker_available"] is True
    assert payload["sandbox_image_available"] is True


def test_get_sandbox_status_missing_image(client, app):
    provider = FakeDockerProvider(unavailable=False, missing_image=True)
    app.dependency_overrides[sandbox_module.get_docker_client_provider_dependency] = lambda: provider

    response = client.get("/sandbox/status")
    payload = response.json()
    assert payload["docker_available"] is True
    assert payload["sandbox_image_available"] is False


def test_get_sandbox_status_unavailable(client, app):
    provider = FakeDockerProvider(unavailable=True)
    app.dependency_overrides[sandbox_module.get_docker_client_provider_dependency] = lambda: provider

    response = client.get("/sandbox/status")
    payload = response.json()
    assert payload["docker_available"] is False
    assert payload["sandbox_image_available"] is False
    assert payload["system_info"]["error"] == "docker offline"


def test_get_sandbox_status_unexpected_error(client, app):
    class RaisingProvider(FakeDockerProvider):
        def __init__(self):
            super().__init__()

        def create_client(self):  # type: ignore[override]
            raise RuntimeError("boom")

    app.dependency_overrides[sandbox_module.get_docker_client_provider_dependency] = lambda: RaisingProvider()

    response = client.get("/sandbox/status")
    assert response.status_code == 500
    assert "Failed to get status" in response.json()["detail"]
