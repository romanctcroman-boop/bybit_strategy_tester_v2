"""Tests for the executions router dependency-injection contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers import executions
from backend.api.routers.executions import (
    ExecutionListResponse,
    ExecutionManagerProtocol,
    ExecutionMetrics,
    ExecutionNotFoundError,
    ExecutionRecord,
    ExecutionStatus,
    ExecutionSubmitRequest,
    ExecutionValidationError,
)


class FakeExecutionManager(ExecutionManagerProtocol):
    """Deterministic execution manager used for tests."""

    def __init__(self) -> None:
        self.records: Dict[str, ExecutionRecord] = {}
        self.submissions: List[ExecutionSubmitRequest] = []

    async def submit_execution(self, payload: ExecutionSubmitRequest) -> ExecutionRecord:
        self.submissions.append(payload)
        exec_id = f"exec-{len(self.records)+1}"
        now = datetime.now(UTC)
        record = ExecutionRecord(
            id=exec_id,
            strategy_id=payload.strategy_id,
            execution_type=payload.execution_type,
            status=ExecutionStatus.PENDING,
            priority=payload.priority,
            submitted_at=now,
            updated_at=now,
            parameters=payload.parameters,
            tags=payload.tags,
        )
        self.records[exec_id] = record
        return record

    async def get_execution(self, execution_id: str) -> ExecutionRecord:
        try:
            return self.records[execution_id]
        except KeyError as error:  # pragma: no cover - defensive
            raise ExecutionNotFoundError(execution_id) from error

    async def list_executions(
        self,
        *,
        status: ExecutionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ExecutionRecord]:
        items = list(self.records.values())
        if status:
            items = [item for item in items if item.status == status]
        return items[offset : offset + limit]

    async def cancel_execution(self, execution_id: str) -> ExecutionRecord:
        record = await self.get_execution(execution_id)
        if record.status == ExecutionStatus.CANCELED:
            raise ExecutionValidationError("already canceled")
        canceled = record.copy(update={"status": ExecutionStatus.CANCELED})
        self.records[execution_id] = canceled
        return canceled

    async def metrics(self) -> ExecutionMetrics:
        counts: Dict[ExecutionStatus, int] = {status: 0 for status in ExecutionStatus}
        for record in self.records.values():
            counts[record.status] += 1
        return ExecutionMetrics(total=len(self.records), by_status=counts, avg_priority=3)


@pytest.fixture()
def app(fake_manager: FakeExecutionManager) -> FastAPI:
    application = FastAPI()
    application.include_router(executions.router)
    application.dependency_overrides[executions.get_execution_manager_dependency] = lambda: fake_manager
    return application


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def fake_manager() -> FakeExecutionManager:
    return FakeExecutionManager()


def test_submit_execution_success(client: TestClient) -> None:
    payload = {
        "strategy_id": 42,
        "execution_type": "backtest",
        "priority": 2,
        "parameters": {"window": 14},
        "tags": ["smoke", "smoke"],
    }
    response = client.post("/executions/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["strategy_id"] == 42
    assert data["priority"] == 2
    # duplicated tags collapse due to validator
    assert data["tags"] == ["smoke"]


def test_list_executions_filters(client: TestClient, fake_manager: FakeExecutionManager) -> None:
    # seed two executions with different statuses
    for idx, status in enumerate((ExecutionStatus.PENDING, ExecutionStatus.CANCELED), start=1):
        exec_id = f"exec-{idx}"
        record = ExecutionRecord(
            id=exec_id,
            strategy_id=idx,
            execution_type=executions.ExecutionType.BACKTEST,
            status=status,
            priority=3,
            submitted_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            parameters={},
            tags=[],
        )
        fake_manager.records[exec_id] = record
    response = client.get("/executions/", params={"status": ExecutionStatus.CANCELED.value})
    assert response.status_code == 200
    payload = ExecutionListResponse(**response.json())
    assert payload.total == 1
    assert payload.items[0].status == ExecutionStatus.CANCELED


def test_get_execution_not_found(client: TestClient, app: FastAPI) -> None:
    def _raise_not_found() -> ExecutionManagerProtocol:
        class _Manager(FakeExecutionManager):
            async def get_execution(self, execution_id: str) -> ExecutionRecord:  # type: ignore[override]
                raise ExecutionNotFoundError(execution_id)
        return _Manager()

    app.dependency_overrides[executions.get_execution_manager_dependency] = _raise_not_found
    response = client.get("/executions/missing")
    assert response.status_code == 404


def test_cancel_execution_validation_error(client: TestClient) -> None:
    # first submission -> record id exec-1
    response = client.post(
        "/executions/",
        json={
            "strategy_id": 1,
            "execution_type": "live",
        },
    )
    assert response.status_code == 201
    exec_id = response.json()["id"]
    # cancel once
    assert client.post(f"/executions/{exec_id}/cancel").status_code == 200
    # cancel twice should 400
    response = client.post(f"/executions/{exec_id}/cancel")
    assert response.status_code == 400


def test_metrics_dependency_failure(client: TestClient, app: FastAPI) -> None:
    app.dependency_overrides[executions.get_execution_manager_dependency] = lambda: None
    response = client.get("/executions/metrics")
    assert response.status_code == 500
