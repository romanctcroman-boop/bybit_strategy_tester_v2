"""
Agent Task Scheduler — Asyncio-Based Periodic Job Execution.

Lightweight scheduler built on top of ``asyncio``.  Does NOT require
APScheduler or any external library.

Features:
- Add/remove tasks at runtime
- Interval-based scheduling (seconds, minutes, hours)
- Cron-like daily scheduling (run at HH:MM UTC)
- Maximum concurrent tasks guard
- Automatic retry with exponential backoff
- Task history & status tracking
- Graceful shutdown

Usage::

    scheduler = TaskScheduler()

    # Run health check every 5 minutes
    scheduler.add_interval_task(
        name="health_check",
        coroutine_factory=check_system_health,
        interval_seconds=300,
    )

    # Run evolution every day at 03:00 UTC
    scheduler.add_daily_task(
        name="nightly_evolution",
        coroutine_factory=lambda: run_nightly_evolution(),
        hour=3,
        minute=0,
    )

    await scheduler.start()
    # … later …
    await scheduler.stop()

Added 2026-02-12 per Agent Ecosystem Audit — Additional Directions.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger

# =============================================================================
# DATA MODELS
# =============================================================================


class TaskType(str, Enum):
    INTERVAL = "interval"
    DAILY = "daily"
    ONE_SHOT = "one_shot"


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    IDLE = "idle"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ScheduledTask:
    """A single registered task."""

    name: str
    task_type: TaskType
    coroutine_factory: Any  # Callable[[], Coroutine]

    # Interval-based
    interval_seconds: float = 0.0

    # Daily (cron-like)
    hour: int = 0
    minute: int = 0

    # Retry
    max_retries: int = 2
    retry_backoff_s: float = 5.0

    # Runtime state
    state: TaskState = TaskState.PENDING
    run_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_run: datetime | None = None
    last_error: str | None = None
    next_run: datetime | None = None

    # Internal handle
    _handle: asyncio.Task | None = field(default=None, repr=False)  # type: ignore[assignment]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "task_type": self.task_type.value,
            "state": self.state.value,
            "interval_seconds": self.interval_seconds,
            "hour": self.hour,
            "minute": self.minute,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_error": self.last_error,
            "next_run": self.next_run.isoformat() if self.next_run else None,
        }


@dataclass
class TaskHistoryEntry:
    """Record of a single task execution."""

    task_name: str
    started_at: datetime
    finished_at: datetime | None = None
    success: bool = False
    duration_s: float = 0.0
    error: str | None = None


# =============================================================================
# SCHEDULER ENGINE
# =============================================================================


class TaskScheduler:
    """
    Asyncio-based task scheduler for autonomous agent operations.

    Manages periodic and daily tasks in the background.
    """

    def __init__(self, max_concurrent: int = 3, history_maxlen: int = 200):
        """
        Args:
            max_concurrent: Maximum tasks running simultaneously
            history_maxlen: Number of execution records to keep
        """
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._sem = asyncio.Semaphore(max_concurrent)
        self._history: deque[TaskHistoryEntry] = deque(maxlen=history_maxlen)
        self._loop_handle: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Task registration
    # ------------------------------------------------------------------

    def add_interval_task(
        self,
        name: str,
        coroutine_factory: Any,
        interval_seconds: float,
        max_retries: int = 2,
    ) -> None:
        """
        Register a task that runs every ``interval_seconds``.

        Args:
            name: Unique task name
            coroutine_factory: Async callable (no args) returning a coroutine
            interval_seconds: Repeat interval in seconds
            max_retries: Max retry on failure
        """
        if name in self._tasks:
            logger.warning(f"Task '{name}' already registered — replacing")
        self._tasks[name] = ScheduledTask(
            name=name,
            task_type=TaskType.INTERVAL,
            coroutine_factory=coroutine_factory,
            interval_seconds=interval_seconds,
            max_retries=max_retries,
        )
        logger.info(f"Registered interval task '{name}' (every {interval_seconds}s)")

    def add_daily_task(
        self,
        name: str,
        coroutine_factory: Any,
        hour: int = 0,
        minute: int = 0,
        max_retries: int = 2,
    ) -> None:
        """
        Register a task that runs daily at a fixed UTC time.

        Args:
            name: Unique task name
            coroutine_factory: Async callable
            hour: UTC hour (0-23)
            minute: UTC minute (0-59)
            max_retries: Max retry on failure
        """
        if name in self._tasks:
            logger.warning(f"Task '{name}' already registered — replacing")
        self._tasks[name] = ScheduledTask(
            name=name,
            task_type=TaskType.DAILY,
            coroutine_factory=coroutine_factory,
            hour=hour,
            minute=minute,
            max_retries=max_retries,
        )
        logger.info(f"Registered daily task '{name}' (at {hour:02d}:{minute:02d} UTC)")

    def add_one_shot_task(
        self,
        name: str,
        coroutine_factory: Any,
        delay_seconds: float = 0.0,
    ) -> None:
        """
        Register a task that runs once after ``delay_seconds``.

        Args:
            name: Unique task name
            coroutine_factory: Async callable
            delay_seconds: Seconds to wait before running
        """
        task = ScheduledTask(
            name=name,
            task_type=TaskType.ONE_SHOT,
            coroutine_factory=coroutine_factory,
            interval_seconds=delay_seconds,
            max_retries=0,
        )
        task.next_run = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        self._tasks[name] = task
        logger.info(f"Registered one-shot task '{name}' (delay {delay_seconds}s)")

    def remove_task(self, name: str) -> bool:
        """Remove a registered task by name."""
        task = self._tasks.pop(name, None)
        if task and task._handle:
            task._handle.cancel()
            task.state = TaskState.STOPPED
        return task is not None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scheduler loop (runs until stop() is called)."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        logger.info(f"🕒 Task scheduler started with {len(self._tasks)} tasks")

        # Schedule all tasks
        for task in self._tasks.values():
            task._handle = asyncio.create_task(self._run_task_loop(task))

    async def stop(self) -> None:
        """Gracefully stop the scheduler."""
        self._running = False
        for task in self._tasks.values():
            if task._handle:
                task._handle.cancel()
            task.state = TaskState.STOPPED

        # Wait a bit for in-flight tasks
        await asyncio.sleep(0.5)
        logger.info("🕒 Task scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Status & history
    # ------------------------------------------------------------------

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all registered tasks with their status."""
        return [t.to_dict() for t in self._tasks.values()]

    def get_task(self, name: str) -> dict[str, Any] | None:
        """Get a specific task's status."""
        task = self._tasks.get(name)
        return task.to_dict() if task else None

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent task execution history."""
        entries = list(self._history)[-limit:]
        return [
            {
                "task_name": e.task_name,
                "started_at": e.started_at.isoformat(),
                "finished_at": e.finished_at.isoformat() if e.finished_at else None,
                "success": e.success,
                "duration_s": round(e.duration_s, 2),
                "error": e.error,
            }
            for e in entries
        ]

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run_task_loop(self, task: ScheduledTask) -> None:
        """Run the scheduling loop for a single task."""
        try:
            if task.task_type == TaskType.INTERVAL:
                await self._run_interval(task)
            elif task.task_type == TaskType.DAILY:
                await self._run_daily(task)
            elif task.task_type == TaskType.ONE_SHOT:
                await self._run_one_shot(task)
        except asyncio.CancelledError:
            task.state = TaskState.STOPPED
        except Exception as exc:
            task.state = TaskState.FAILED
            task.last_error = str(exc)
            logger.error(f"Task '{task.name}' loop crashed: {exc}")

    async def _run_interval(self, task: ScheduledTask) -> None:
        """Run a task at a fixed interval."""
        while self._running:
            task.next_run = datetime.now(UTC) + timedelta(seconds=task.interval_seconds)
            await asyncio.sleep(task.interval_seconds)
            if not self._running:
                break
            await self._execute_with_retry(task)

    async def _run_daily(self, task: ScheduledTask) -> None:
        """Run a task once per day at a fixed UTC time."""
        while self._running:
            now = datetime.now(UTC)
            target = now.replace(hour=task.hour, minute=task.minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)

            task.next_run = target
            wait_s = (target - now).total_seconds()
            logger.debug(f"Task '{task.name}' next run at {target.isoformat()} (in {wait_s:.0f}s)")

            await asyncio.sleep(wait_s)
            if not self._running:
                break
            await self._execute_with_retry(task)

    async def _run_one_shot(self, task: ScheduledTask) -> None:
        """Run a task once after an initial delay."""
        if task.interval_seconds > 0:
            await asyncio.sleep(task.interval_seconds)
        if self._running:
            await self._execute_with_retry(task)
        task.state = TaskState.STOPPED

    async def _execute_with_retry(self, task: ScheduledTask) -> None:
        """Execute a task with retry and backoff."""
        retries = 0
        while retries <= task.max_retries:
            entry = TaskHistoryEntry(
                task_name=task.name,
                started_at=datetime.now(UTC),
            )

            try:
                async with self._sem:
                    task.state = TaskState.RUNNING
                    task.last_run = datetime.now(UTC)
                    task.run_count += 1

                    logger.debug(f"Executing task '{task.name}' (attempt {retries + 1})")
                    await task.coroutine_factory()

                    task.state = TaskState.IDLE
                    task.success_count += 1
                    task.last_error = None

                    entry.success = True
                    entry.finished_at = datetime.now(UTC)
                    entry.duration_s = (entry.finished_at - entry.started_at).total_seconds()
                    self._history.append(entry)
                    return

            except Exception as exc:
                retries += 1
                task.fail_count += 1
                task.last_error = str(exc)
                task.state = TaskState.FAILED

                entry.success = False
                entry.error = str(exc)
                entry.finished_at = datetime.now(UTC)
                entry.duration_s = (entry.finished_at - entry.started_at).total_seconds()
                self._history.append(entry)

                if retries <= task.max_retries:
                    backoff = task.retry_backoff_s * (2 ** (retries - 1))
                    logger.warning(f"Task '{task.name}' failed (attempt {retries}): {exc}. Retrying in {backoff:.1f}s…")
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"Task '{task.name}' exhausted all retries ({task.max_retries + 1} attempts): {exc}")


# =============================================================================
# PRE-BUILT TASK FACTORIES
# =============================================================================


async def health_check_task() -> None:
    """Pre-built task: run system health check."""
    from backend.agents.mcp.trading_tools import check_system_health

    result = await check_system_health()
    logger.info(f"Health check: {result.get('overall', 'unknown')}")


async def pattern_extraction_task() -> None:
    """Pre-built task: run pattern extraction."""
    from backend.agents.self_improvement.pattern_extractor import PatternExtractor

    extractor = PatternExtractor()
    result = await extractor.extract()
    logger.info(f"Pattern extraction: {len(result.patterns)} patterns, {result.total_backtests_analysed} backtests")


def create_default_scheduler() -> TaskScheduler:
    """
    Create a scheduler with sensible defaults.

    Returns a scheduler with health check (5 min) and
    pattern extraction (1 hour) pre-configured.
    """
    scheduler = TaskScheduler()

    scheduler.add_interval_task(
        name="health_check",
        coroutine_factory=health_check_task,
        interval_seconds=300,  # 5 minutes
    )

    scheduler.add_interval_task(
        name="pattern_extraction",
        coroutine_factory=pattern_extraction_task,
        interval_seconds=3600,  # 1 hour
    )

    return scheduler
