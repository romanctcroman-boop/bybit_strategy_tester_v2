"""
Circuit Breaker Manager for Agent System
Provides circuit breaker pattern for handling failures gracefully

Features:
- Adaptive thresholds based on latency percentiles
- Graceful degradation with fallback responses
- Self-healing with exponential backoff
- Prometheus metrics integration
"""

import asyncio
import logging
import os
import statistics
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """States for circuit breaker pattern"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit breaker is open (failing)
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""

    pass


class AdaptiveMetrics:
    """Tracks latency metrics for adaptive thresholds."""

    def __init__(self, window_size: int = 100):
        self.latencies: deque = deque(maxlen=window_size)
        self.errors: deque = deque(maxlen=window_size)
        self.window_size = window_size
        self._last_p95: float = 0.0
        self._last_p99: float = 0.0
        self._error_rate: float = 0.0

    def record_latency(self, latency_ms: float):
        """Record a latency measurement."""
        self.latencies.append(latency_ms)
        self.errors.append(0)
        self._update_percentiles()

    def record_error(self):
        """Record an error."""
        self.errors.append(1)
        self._update_error_rate()

    def _update_percentiles(self):
        """Update latency percentiles."""
        if len(self.latencies) >= 10:
            sorted_latencies = sorted(self.latencies)
            n = len(sorted_latencies)
            self._last_p95 = sorted_latencies[int(n * 0.95)]
            self._last_p99 = sorted_latencies[int(n * 0.99)]

    def _update_error_rate(self):
        """Update error rate."""
        if self.errors:
            self._error_rate = sum(self.errors) / len(self.errors)

    @property
    def p95_latency(self) -> float:
        return self._last_p95

    @property
    def p99_latency(self) -> float:
        return self._last_p99

    @property
    def error_rate(self) -> float:
        return self._error_rate

    @property
    def avg_latency(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0.0

    def get_adaptive_threshold(self, base_threshold: int) -> int:
        """Calculate adaptive threshold based on error rate."""
        if self._error_rate > 0.5:
            # High error rate - lower threshold (trip faster)
            return max(2, base_threshold // 2)
        elif self._error_rate > 0.2:
            # Medium error rate - slightly lower threshold
            return max(3, int(base_threshold * 0.7))
        elif self._error_rate < 0.05 and len(self.latencies) > 50:
            # Low error rate - can be more lenient
            return min(base_threshold * 2, 15)
        return base_threshold

    def get_adaptive_timeout(self, base_timeout: int) -> int:
        """Calculate adaptive recovery timeout based on metrics."""
        if self._error_rate > 0.5:
            # High error rate - longer recovery time
            return min(base_timeout * 3, 300)
        elif self._error_rate > 0.2:
            return min(base_timeout * 2, 180)
        elif self._error_rate < 0.05:
            # Low error rate - faster recovery
            return max(base_timeout // 2, 15)
        return base_timeout


class CircuitBreaker:
    """Advanced circuit breaker with adaptive thresholds and graceful degradation."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        enable_adaptive: bool = True,
        fallback_handler: Callable | None = None,
    ):
        self.name = name
        self.base_failure_threshold = failure_threshold
        self.base_recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.enable_adaptive = enable_adaptive
        self.fallback_handler = fallback_handler

        self.failure_count = 0
        self.success_count = 0
        self.total_calls = 0
        self.last_failure_time: datetime | None = None
        self.state = CircuitState.CLOSED
        self.consecutive_successes = 0
        self.trip_count = 0  # How many times circuit has tripped

        # Adaptive metrics
        self.metrics = AdaptiveMetrics()

        # Exponential backoff for recovery
        self._current_backoff_multiplier = 1.0
        self._max_backoff_multiplier = 8.0

        # Load from environment if available
        env_threshold = os.getenv(f"CB_{name.upper()}_THRESHOLD")
        env_timeout = os.getenv(f"CB_{name.upper()}_TIMEOUT")
        if env_threshold:
            self.base_failure_threshold = int(env_threshold)
        if env_timeout:
            self.base_recovery_timeout = int(env_timeout)

    @property
    def failure_threshold(self) -> int:
        """Get current failure threshold (adaptive or base)."""
        if self.enable_adaptive:
            return self.metrics.get_adaptive_threshold(self.base_failure_threshold)
        return self.base_failure_threshold

    @property
    def recovery_timeout(self) -> int:
        """Get current recovery timeout (adaptive or base)."""
        base = self.base_recovery_timeout
        if self.enable_adaptive:
            base = self.metrics.get_adaptive_timeout(base)
        # Apply exponential backoff
        return int(base * self._current_backoff_multiplier)

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        self.total_calls += 1
        start_time = time.time()

        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.consecutive_successes = 0
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                # Try fallback if available
                if self.fallback_handler:
                    logger.info(f"Circuit '{self.name}' OPEN - using fallback")
                    return self.fallback_handler(*args, **kwargs)
                raise CircuitBreakerError(f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = func(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.record_latency(latency_ms)
            self._on_success()
            return result
        except self.expected_exception:
            self.metrics.record_error()
            self._on_failure()
            # Try fallback on failure if in HALF_OPEN or after threshold
            if self.fallback_handler and self.state == CircuitState.OPEN:
                logger.info(f"Circuit '{self.name}' tripped - using fallback")
                return self.fallback_handler(*args, **kwargs)
            raise

    async def call_async(self, func, *args, **kwargs):
        """Execute async function with circuit breaker protection"""
        self.total_calls += 1
        start_time = time.time()

        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.consecutive_successes = 0
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                if self.fallback_handler:
                    logger.info(f"Circuit '{self.name}' OPEN - using fallback")
                    result = self.fallback_handler(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        return await result
                    return result
                raise CircuitBreakerError(f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = await func(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.record_latency(latency_ms)
            self._on_success()
            return result
        except self.expected_exception:
            self.metrics.record_error()
            self._on_failure()
            if self.fallback_handler and self.state == CircuitState.OPEN:
                logger.info(f"Circuit '{self.name}' tripped - using fallback")
                result = self.fallback_handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            raise

    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.success_count += 1
        self.consecutive_successes += 1

        if self.state == CircuitState.HALF_OPEN:
            # Require multiple successes in HALF_OPEN before closing
            required_successes = min(3, self.trip_count + 1)
            if self.consecutive_successes >= required_successes:
                self.state = CircuitState.CLOSED
                # Reduce backoff on successful recovery
                self._current_backoff_multiplier = max(
                    1.0, self._current_backoff_multiplier / 2
                )
                logger.info(
                    f"Circuit breaker '{self.name}' recovered and CLOSED "
                    f"(after {self.consecutive_successes} successes)"
                )

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.consecutive_successes = 0
        self.last_failure_time = datetime.now(UTC)

        current_threshold = self.failure_threshold
        if self.failure_count >= current_threshold:
            self.state = CircuitState.OPEN
            self.trip_count += 1
            # Increase backoff on each trip
            self._current_backoff_multiplier = min(
                self._current_backoff_multiplier * 1.5, self._max_backoff_multiplier
            )
            backoff = self._current_backoff_multiplier
            logger.warning(
                f"Circuit breaker '{self.name}' is now OPEN "
                f"(failures: {self.failure_count}/{current_threshold}, "
                f"trip #{self.trip_count}, backoff: {backoff:.1f}x)"
            )

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit"""
        if self.last_failure_time is None:
            return True

        timeout_elapsed = (
            datetime.now(UTC) - self.last_failure_time
        ).total_seconds() >= self.recovery_timeout

        return timeout_elapsed

    def set_fallback(self, handler: Callable):
        """Set fallback handler for graceful degradation."""
        self.fallback_handler = handler

    def get_health_info(self) -> dict[str, Any]:
        """Get detailed health information."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "trip_count": self.trip_count,
            "current_threshold": self.failure_threshold,
            "current_timeout": self.recovery_timeout,
            "backoff_multiplier": self._current_backoff_multiplier,
            "metrics": {
                "avg_latency_ms": round(self.metrics.avg_latency, 2),
                "p95_latency_ms": round(self.metrics.p95_latency, 2),
                "p99_latency_ms": round(self.metrics.p99_latency, 2),
                "error_rate": round(self.metrics.error_rate, 4),
            },
            "adaptive_enabled": self.enable_adaptive,
            "has_fallback": self.fallback_handler is not None,
        }


class CircuitBreakerManager:
    """Manager for multiple circuit breakers"""

    def __init__(self):
        self.breakers: dict[str, CircuitBreaker] = {}
        self._last_adapt_time: datetime | None = None
        self._persistence_enabled: bool = False
        self._persistence_redis = None
        self._persistence_task: asyncio.Task | None = None
        self._autosave_interval: int = 60  # default autosave interval
        self._configs: dict[str, Any] = {}  # configurations tracked

    def get_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        return self.breakers[name]

    def register_breaker(
        self,
        name: str,
        fail_max: int = 5,
        timeout_duration: int = 60,
        expected_exception: type = Exception,
    ) -> CircuitBreaker:
        """Register a circuit breaker with pybreaker-compatible parameters"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=fail_max,
                recovery_timeout=timeout_duration,
                expected_exception=expected_exception,
            )
        return self.breakers[name]

    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self.breakers.values():
            breaker.state = CircuitState.CLOSED
            breaker.failure_count = 0
            breaker.success_count = 0
            logger.info(f"Reset circuit breaker '{breaker.name}'")

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all circuit breakers"""
        return {
            name: {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
                "success_count": breaker.success_count,
            }
            for name, breaker in self.breakers.items()
        }

    def get_all_breakers(self) -> list[str]:
        """Return a list of registered breaker names."""
        return list(self.breakers.keys())

    async def enable_persistence(
        self, redis_url: str, autosave_interval: int = 60
    ) -> bool:
        """Attempt to enable persistence of circuit-breaker state into Redis.

        Returns True if persistence was successfully enabled, False otherwise.
        This is a best-effort helper: if redis is not available or import fails,
        it returns False and leaves manager operational without persistence.
        """
        try:
            # import redis.asyncio lazily; support environments without it
            try:
                import redis.asyncio as aioredis  # type: ignore
            except Exception:
                # fallback to sync redis client if present (will be wrapped)
                try:
                    import redis as syncredis  # type: ignore

                    aioredis = None
                except Exception:
                    return False

            # create client appropriately
            if aioredis is not None:
                client = aioredis.from_url(redis_url)
                # test connection
                await client.ping()
                self._persistence_redis = client
            else:
                # sync client present; try simple ping
                client = syncredis.from_url(redis_url)
                client.ping()
                self._persistence_redis = client

            self._persistence_enabled = True
            self._autosave_interval = autosave_interval  # store for later reference

            # start autosave loop if asyncio available and we have aioredis
            try:
                import asyncio as _asyncio

                if aioredis is not None:
                    # schedule background autosave task
                    loop = _asyncio.get_event_loop()
                    if self._persistence_task is None or self._persistence_task.done():
                        self._persistence_task = loop.create_task(
                            self._autosave_loop(autosave_interval)
                        )
            except Exception:
                # ignore background scheduling failures; persistence still enabled
                pass

            return True
        except Exception:
            # best-effort: do not fail startup if redis/persistence isn't available
            self._persistence_enabled = False
            self._persistence_redis = None
            return False

    async def _autosave_loop(self, interval_seconds: int = 60) -> None:
        """Background task that periodically stores breaker state into Redis.

        This is best-effort and will silently stop on errors.
        """
        try:
            while True:
                try:
                    if not self._persistence_enabled or self._persistence_redis is None:
                        return
                    # prepare snapshot
                    snapshot = {
                        name: {
                            "state": b.state.value,
                            "failure_count": b.failure_count,
                            "success_count": b.success_count,
                            "last_failure_time": b.last_failure_time.isoformat()
                            if b.last_failure_time
                            else None,
                        }
                        for name, b in self.breakers.items()
                    }
                    # store as JSON string under a fixed key
                    try:
                        import json as _json

                        key = "circuit_breakers_state"
                        if hasattr(self._persistence_redis, "set"):
                            # aioredis or sync redis
                            await self._persistence_redis.set(
                                key, _json.dumps(snapshot)
                            )
                    except Exception:
                        # ignore write errors
                        pass
                except Exception:
                    # swallow snapshot errors
                    pass
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            return

    def get_breaker_state(self, name: str) -> CircuitState | None:
        """Return the CircuitState for a named breaker, or None if missing."""
        b = self.breakers.get(name)
        return b.state if b is not None else None

    def get_breaker_metrics(self, name: str) -> dict[str, Any] | None:
        """Return detailed metrics for a specific circuit breaker by name.

        Args:
            name: The name of the circuit breaker

        Returns:
            Dictionary with metrics including:
            - state: Current circuit state
            - failure_count: Number of failures
            - success_count: Number of successes
            - error_rate: Error rate as percentage
            - latency_p95_ms: P95 latency in milliseconds (if available)
            - last_failure_time: Timestamp of last failure
            - last_success_time: Timestamp of last success
        """
        breaker = self.breakers.get(name)
        if breaker is None:
            return None

        total_calls = breaker.success_count + breaker.failure_count
        error_rate = (
            (breaker.failure_count / total_calls * 100) if total_calls > 0 else 0.0
        )

        return {
            "state": breaker.state.value,
            "failure_count": breaker.failure_count,
            "success_count": breaker.success_count,
            "total_calls": total_calls,
            "error_rate": round(error_rate, 2),
            "latency_p95_ms": getattr(breaker, "latency_p95_ms", 0),
            "last_failure_time": getattr(breaker, "last_failure_time", None),
            "last_success_time": getattr(breaker, "last_success_time", None),
            "trip_count": getattr(breaker, "trip_count", 0),
        }

    async def call_with_breaker(self, name: str, func, *args, **kwargs):
        """Execute async or sync callable under a named circuit breaker.

        This method will create the breaker if missing and track failures/successes.
        It accepts coroutine functions or regular callables.
        """
        breaker = self.get_breaker(name)

        # If breaker is open and not ready to attempt reset, raise
        if breaker.state == CircuitState.OPEN and not breaker._should_attempt_reset():
            raise CircuitBreakerError(f"Circuit breaker '{name}' is OPEN")

        try:
            # support coroutine functions
            result = func(*args, **kwargs)
            if hasattr(result, "__await__"):
                result = await result

            # record success
            breaker._on_success()
            return result
        except Exception:
            # record failure and re-raise
            breaker._on_failure()
            raise

    def get_metrics(self):
        """Return a lightweight metrics wrapper expected by callers.

        Supports .to_dict() and .breakers attribute to match existing usage.
        """

        class _Metrics:
            def __init__(self, data: dict[str, Any], breakers_dict: dict[str, Any]):
                self._data = data
                self.breakers = breakers_dict

            def to_dict(self) -> dict[str, Any]:
                return self._data

        data = {
            name: {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
                "success_count": breaker.success_count,
            }
            for name, breaker in self.breakers.items()
        }

        # Build breakers dict with full metrics for health check
        breakers_dict = {
            name: {
                "total_calls": breaker.success_count + breaker.failure_count,
                "failed_calls": breaker.failure_count,
                "successful_calls": breaker.success_count,
                "total_trips": getattr(breaker, "trip_count", 0),
                "current_state": breaker.state.value,
                "success_rate_24h": round(
                    (
                        breaker.success_count
                        / (breaker.success_count + breaker.failure_count)
                        * 100
                    )
                    if (breaker.success_count + breaker.failure_count) > 0
                    else 100.0,
                    2,
                ),
            }
            for name, breaker in self.breakers.items()
        }

        return _Metrics(data, breakers_dict)

    def maybe_adapt_breakers(
        self, force: bool = False, min_interval_seconds: int = 300
    ) -> dict[str, Any]:
        """Adaptive tuning hook.

        Currently a safe, idempotent no-op that records last adapt time and returns any
        adaptations performed (empty dict by default). Callers may use `force=True` to
        bypass the interval.
        """
        now = datetime.now(UTC)
        if not force and self._last_adapt_time is not None:
            delta = (now - self._last_adapt_time).total_seconds()
            if delta < min_interval_seconds:
                return {}

        # Placeholder for adaptive logic. For now we don't change thresholds.
        self._last_adapt_time = now
        return {}


# Global circuit breaker manager instance
_circuit_manager: CircuitBreakerManager | None = None


def get_circuit_manager() -> CircuitBreakerManager:
    """Get or create the global circuit breaker manager"""
    global _circuit_manager
    if _circuit_manager is None:
        _circuit_manager = CircuitBreakerManager()
    return _circuit_manager


def on_config_change(config: Any) -> None:
    """
    Callback for config hot-reload. Updates circuit breakers based on new config.

    Called by agent_config when agents.yaml changes.

    Args:
        config: New AgentConfig instance from agent_config module
    """
    try:
        manager = get_circuit_manager()

        # Update circuit breaker settings from config
        cb_config = getattr(config, "circuit_breaker", None)
        if cb_config:
            # Update failure threshold for all breakers
            new_threshold = getattr(cb_config, "failure_threshold", 5)
            new_timeout = getattr(cb_config, "recovery_timeout", 60)

            for name, breaker in manager._breakers.items():
                breaker.failure_threshold = new_threshold
                breaker.recovery_time = new_timeout

            logger.info(
                f"🔄 Circuit breakers updated: threshold={new_threshold}, "
                f"timeout={new_timeout}s, breakers={len(manager._breakers)}"
            )
        else:
            logger.debug("No circuit_breaker config section in reload")

    except Exception as e:
        logger.error(f"Error updating circuit breakers on config change: {e}")


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitBreakerManager",
    "CircuitState",
    "get_circuit_manager",
    "on_config_change",
]
