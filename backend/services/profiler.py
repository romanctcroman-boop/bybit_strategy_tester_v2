"""
Performance Profiling Service.

Provides decorator-based profiling for production bottleneck detection
using py-spy (sampling) and memory_profiler (heap analysis).

Features:
- ``@profile_time`` decorator for wall-clock timing with loguru
- ``@profile_memory`` decorator for peak-memory tracking
- ``ProfilingSession`` context manager for ad-hoc profiling
- JSON-exportable profiling reports

Usage::

    from backend.services.profiler import profile_time, profile_memory

    @profile_time(threshold_ms=200)
    async def slow_function():
        ...

    @profile_memory(threshold_mb=50)
    def heavy_function():
        ...
"""

from __future__ import annotations

import functools
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROFILING_ENABLED = os.getenv("PROFILING_ENABLED", "0") == "1"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ProfileResult:
    """Single profiling measurement."""

    function_name: str
    elapsed_ms: float
    peak_memory_mb: float | None = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-friendly dict."""
        return {
            "function_name": self.function_name,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "peak_memory_mb": round(self.peak_memory_mb, 2) if self.peak_memory_mb else None,
            "timestamp": self.timestamp,
            **self.metadata,
        }


@dataclass
class ProfilingReport:
    """Aggregated profiling report."""

    results: list[ProfileResult] = field(default_factory=list)
    session_id: str = ""

    def add(self, result: ProfileResult) -> None:
        """Add a profiling result."""
        self.results.append(result)

    @property
    def total_ms(self) -> float:
        """Total elapsed time across all results."""
        return sum(r.elapsed_ms for r in self.results)

    @property
    def slowest(self) -> ProfileResult | None:
        """Return the slowest recorded call."""
        return max(self.results, key=lambda r: r.elapsed_ms) if self.results else None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full report."""
        return {
            "session_id": self.session_id,
            "total_ms": round(self.total_ms, 3),
            "count": len(self.results),
            "slowest": self.slowest.to_dict() if self.slowest else None,
            "results": [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def profile_time(threshold_ms: float = 100.0, label: str | None = None):
    """
    Decorator that logs wall-clock time for a function call.

    Only emits a warning log if elapsed time exceeds *threshold_ms*.
    Works with both sync and async functions.

    Args:
        threshold_ms: Minimum elapsed time (ms) to trigger a log entry.
        label: Optional human-readable label (defaults to function name).
    """

    def decorator(fn):
        fn_label = label or fn.__qualname__

        if _is_coroutine_function(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return await fn(*args, **kwargs)
                finally:
                    elapsed = (time.perf_counter() - start) * 1000
                    if elapsed >= threshold_ms:
                        logger.warning(
                            "SLOW %s took %.1fms (threshold=%.0fms)",
                            fn_label,
                            elapsed,
                            threshold_ms,
                        )
                    else:
                        logger.debug("%s completed in %.1fms", fn_label, elapsed)

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return fn(*args, **kwargs)
                finally:
                    elapsed = (time.perf_counter() - start) * 1000
                    if elapsed >= threshold_ms:
                        logger.warning(
                            "SLOW %s took %.1fms (threshold=%.0fms)",
                            fn_label,
                            elapsed,
                            threshold_ms,
                        )
                    else:
                        logger.debug("%s completed in %.1fms", fn_label, elapsed)

            return sync_wrapper

    return decorator


def profile_memory(threshold_mb: float = 50.0, label: str | None = None):
    """
    Decorator that tracks peak memory delta for a function call.

    Uses ``tracemalloc`` (stdlib) to avoid requiring ``memory_profiler``.

    Args:
        threshold_mb: Memory threshold (MB) to trigger a warning.
        label: Optional human-readable label.
    """

    def decorator(fn):
        fn_label = label or fn.__qualname__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            import tracemalloc

            tracemalloc.start()
            try:
                result = fn(*args, **kwargs)
            finally:
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                peak_mb = peak / (1024 * 1024)
                if peak_mb >= threshold_mb:
                    logger.warning(
                        "HIGH MEMORY %s peak=%.1fMB (threshold=%.0fMB)",
                        fn_label,
                        peak_mb,
                        threshold_mb,
                    )
                else:
                    logger.debug("%s peak memory=%.1fMB", fn_label, peak_mb)
            return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Context Manager
# ---------------------------------------------------------------------------


@contextmanager
def profiling_session(name: str = "default"):
    """
    Context manager for ad-hoc profiling sessions.

    Usage::

        with profiling_session("backtest") as session:
            run_backtest(...)
        print(session.elapsed_ms)
    """
    session = ProfileResult(function_name=name, elapsed_ms=0)
    start = time.perf_counter()
    try:
        yield session
    finally:
        session.elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Profiling session '%s' completed in %.1fms", name, session.elapsed_ms)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_coroutine_function(fn) -> bool:
    """Check if a function is a coroutine (async def)."""
    import asyncio
    import inspect

    return asyncio.iscoroutinefunction(fn) or inspect.iscoroutinefunction(fn)
