"""Execution management router with dependency-injected manager for testability."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class ExecutionType(str, Enum):
    """Supported execution flows."""

    BACKTEST = "backtest"
    OPTIMIZATION = "optimization"
    LIVE = "live"


class ExecutionStatus(str, Enum):
    """Lifecycle status for an execution request."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ExecutionSubmitRequest(BaseModel):
    """Payload used to submit a new execution."""

    strategy_id: int = Field(..., gt=0)
    execution_type: ExecutionType = Field(..., description="Type of execution flow")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution-specific parameters that downstream services consume.",
    )
    priority: int = Field(3, ge=1, le=5, description="1=highest, 5=lowest")
    tags: list[str] = Field(default_factory=list)

    @validator("tags", pre=True)
    def _ensure_unique_tags(cls, value: list[str]) -> list[str]:  # noqa: D417 - pydantic hook
        unique = list(dict.fromkeys(value or []))
        return unique


class ExecutionRecord(BaseModel):
    """Immutable view of an execution tracked by the router."""

    id: str
    strategy_id: int
    execution_type: ExecutionType
    status: ExecutionStatus
    priority: int
    submitted_at: datetime
    updated_at: datetime
    parameters: dict[str, Any]
    tags: list[str]
    result: dict[str, Any] | None = None
    error: str | None = None


class ExecutionListResponse(BaseModel):
    items: list[ExecutionRecord]
    total: int


class ExecutionMetrics(BaseModel):
    total: int
    by_status: dict[ExecutionStatus, int]
    avg_priority: float | None = None


class ExecutionManagerError(Exception):
    """Base error raised by execution manager implementations."""


class ExecutionNotFoundError(ExecutionManagerError):
    """Raised when an execution id cannot be located."""


class ExecutionValidationError(ExecutionManagerError):
    """Raised when an operation is invalid for a given execution."""


class ExecutionManagerProtocol(Protocol):
    """Interface implemented by execution manager dependencies."""

    async def submit_execution(self, payload: ExecutionSubmitRequest) -> ExecutionRecord: ...

    async def get_execution(self, execution_id: str) -> ExecutionRecord: ...

    async def list_executions(
        self,
        *,
        status: ExecutionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExecutionRecord]: ...

    async def cancel_execution(self, execution_id: str) -> ExecutionRecord: ...

    async def metrics(self) -> ExecutionMetrics: ...


class InMemoryExecutionManager(ExecutionManagerProtocol):
    """Default execution manager that retains requests in memory.

    It is intentionally simple but mirrors async behavior so tests can override it with mocks.
    """

    def __init__(self) -> None:
        self._records: dict[str, ExecutionRecord] = {}
        self._lock = asyncio.Lock()

    async def submit_execution(self, payload: ExecutionSubmitRequest) -> ExecutionRecord:
        async with self._lock:
            exec_id = str(uuid.uuid4())
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
            self._records[exec_id] = record
            logger.debug("Execution %s submitted", exec_id)
            return record

    async def get_execution(self, execution_id: str) -> ExecutionRecord:
        record = self._records.get(execution_id)
        if record is None:
            raise ExecutionNotFoundError(f"Execution {execution_id} was not found")
        return record

    async def list_executions(
        self,
        *,
        status: ExecutionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExecutionRecord]:
        items = list(self._records.values())
        if status:
            items = [rec for rec in items if rec.status == status]
        return items[offset : offset + limit]

    async def cancel_execution(self, execution_id: str) -> ExecutionRecord:
        async with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                raise ExecutionNotFoundError(f"Execution {execution_id} was not found")
            if record.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELED}:
                raise ExecutionValidationError(
                    f"Execution {execution_id} is already finished with status {record.status}"
                )
            updated = record.copy(
                update={
                    "status": ExecutionStatus.CANCELED,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._records[execution_id] = updated
            logger.info("Execution %s cancelled", execution_id)
            return updated

    async def metrics(self) -> ExecutionMetrics:
        counts: dict[ExecutionStatus, int] = {status: 0 for status in ExecutionStatus}
        for record in self._records.values():
            counts[record.status] += 1
        total = len(self._records)
        avg_priority = None
        if total > 0:
            avg_priority = sum(rec.priority for rec in self._records.values()) / total
        return ExecutionMetrics(total=total, by_status=counts, avg_priority=avg_priority)


router = APIRouter(prefix="/executions", tags=["executions"])

_DEFAULT_EXECUTIONS_MANAGER = InMemoryExecutionManager()


async def get_execution_manager_dependency() -> ExecutionManagerProtocol:
    """Default dependency factory that can be overridden in tests."""

    return _DEFAULT_EXECUTIONS_MANAGER


async def _resolve_manager(manager: ExecutionManagerProtocol | None) -> ExecutionManagerProtocol:
    if manager is None:
        logger.error("Execution manager dependency returned None")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Execution manager dependency returned None",
        )
    return manager


@router.post("/", response_model=ExecutionRecord, status_code=status.HTTP_201_CREATED)
async def submit_execution(
    payload: ExecutionSubmitRequest,
    manager: ExecutionManagerProtocol | None = Depends(get_execution_manager_dependency),
) -> ExecutionRecord:
    """Submit a new execution request."""

    mgr = await _resolve_manager(manager)
    try:
        return await mgr.submit_execution(payload)
    except ExecutionValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ExecutionManagerError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/{execution_id}", response_model=ExecutionRecord)
async def get_execution(
    execution_id: str = Path(..., description="Execution identifier"),
    manager: ExecutionManagerProtocol | None = Depends(get_execution_manager_dependency),
) -> ExecutionRecord:
    mgr = await _resolve_manager(manager)
    try:
        return await mgr.get_execution(execution_id)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/", response_model=ExecutionListResponse)
async def list_executions(
    status_filter: ExecutionStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    manager: ExecutionManagerProtocol | None = Depends(get_execution_manager_dependency),
) -> ExecutionListResponse:
    mgr = await _resolve_manager(manager)
    items = await mgr.list_executions(status=status_filter, limit=limit, offset=offset)
    return ExecutionListResponse(items=items, total=len(items))


@router.post("/{execution_id}/cancel", response_model=ExecutionRecord)
async def cancel_execution(
    execution_id: str,
    manager: ExecutionManagerProtocol | None = Depends(get_execution_manager_dependency),
) -> ExecutionRecord:
    mgr = await _resolve_manager(manager)
    try:
        return await mgr.cancel_execution(execution_id)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExecutionValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/metrics", response_model=ExecutionMetrics)
async def execution_metrics(
    manager: ExecutionManagerProtocol | None = Depends(get_execution_manager_dependency),
) -> ExecutionMetrics:
    mgr = await _resolve_manager(manager)
    return await mgr.metrics()