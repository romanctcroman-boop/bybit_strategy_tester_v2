"""
Unified Circuit Breaker Pattern Implementation

Production-ready circuit breaker for all external API calls with:
- Adaptive thresholds based on error rates
- Graceful degradation with fallback responses
- Self-healing with exponential backoff
- Prometheus metrics integration
- Retry logic with tenacity

Usage:
    from backend.core.circuit_breaker import circuit_breaker, with_retry

    @circuit_breaker("bybit_api")
    @with_retry(max_attempts=3)
    async def call_bybit_api():
        ...
"""

import asyncio
import functools
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar

from loguru import logger

# Try to import tenacity for retry logic
try:
    from tenacity import (
        AsyncRetrying,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential_jitter,
    )

    TENACITY_AVAILABLE = True
except ImportError:
    logger.warning("tenacity not installed - retry functionality limited")
    TENACITY_AVAILABLE = False

# Try to import prometheus for metrics
try:
    from prometheus_client import Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not installed - metrics disabled")
    PROMETHEUS_AVAILABLE = False


# =============================================================================
# ENUMS & EXCEPTIONS
# =============================================================================


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is tripped, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, circuit_name: str, message: str = "Circuit is open"):
        self.circuit_name = circuit_name
        super().__init__(f"{circuit_name}: {message}")


class RetryableError(Exception):
    """Base class for errors that should trigger retry."""

    pass


class RateLimitError(RetryableError):
    """Raised when rate limited by external API."""

    def __init__(self, retry_after: float = 60.0, message: str = "Rate limited"):
        self.retry_after = retry_after
        super().__init__(message)


class TimeoutError(RetryableError):
    """Raised when external call times out."""

    pass


class TransientError(RetryableError):
    """Raised for transient failures (network issues, 5xx errors)."""

    pass


# =============================================================================
# METRICS (if Prometheus available)
# =============================================================================

if PROMETHEUS_AVAILABLE:
    circuit_state_gauge = Gauge(
        "circuit_breaker_state",
        "Current state of circuit breaker (0=closed, 1=open, 2=half_open)",
        ["circuit_name"],
    )
    circuit_failures_total = Counter(
        "circuit_breaker_failures_total",
        "Total number of circuit breaker failures",
        ["circuit_name", "error_type"],
    )
    circuit_success_total = Counter(
        "circuit_breaker_success_total",
        "Total number of successful calls through circuit breaker",
        ["circuit_name"],
    )
    circuit_latency_histogram = Histogram(
        "circuit_breaker_latency_seconds",
        "Latency of calls through circuit breaker",
        ["circuit_name"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
    retry_attempts_total = Counter(
        "retry_attempts_total",
        "Total number of retry attempts",
        ["operation_name", "attempt"],
    )


# =============================================================================
# ADAPTIVE METRICS
# =============================================================================


@dataclass
class AdaptiveMetrics:
    """Tracks metrics for adaptive threshold adjustment."""

    latencies: deque = field(default_factory=lambda: deque(maxlen=100))
    errors: deque = field(default_factory=lambda: deque(maxlen=100))
    _last_p95: float = 0.0
    _last_p99: float = 0.0
    _error_rate: float = 0.0

    def record_latency(self, latency_ms: float) -> None:
        """Record a successful call latency."""
        self.latencies.append(latency_ms)
        self.errors.append(0)
        self._update_percentiles()

    def record_error(self) -> None:
        """Record an error."""
        self.errors.append(1)
        self._update_error_rate()

    def _update_percentiles(self) -> None:
        """Update latency percentiles."""
        if len(self.latencies) >= 10:
            sorted_latencies = sorted(self.latencies)
            n = len(sorted_latencies)
            self._last_p95 = sorted_latencies[int(n * 0.95)]
            self._last_p99 = sorted_latencies[int(n * 0.99)]

    def _update_error_rate(self) -> None:
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
            # High error rate - trip faster
            return max(2, base_threshold // 2)
        elif self._error_rate > 0.2:
            # Medium error rate
            return max(3, int(base_threshold * 0.7))
        elif self._error_rate < 0.05 and len(self.latencies) > 50:
            # Low error rate - more lenient
            return min(base_threshold * 2, 15)
        return base_threshold


# =============================================================================
# CIRCUIT BREAKER IMPLEMENTATION
# =============================================================================


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes in half-open before closing
    timeout: float = 30.0  # Seconds before trying half-open
    half_open_max_calls: int = 3  # Max concurrent calls in half-open
    excluded_exceptions: tuple = ()  # Exceptions that don't count as failures


class CircuitBreaker:
    """
    Production-ready circuit breaker.

    States:
    - CLOSED: Normal operation, tracking failures
    - OPEN: Failing fast, not making calls
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self.last_state_change = time.time()
        self.metrics = AdaptiveMetrics()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    async def _can_execute(self) -> bool:
        """Check if call can proceed."""
        async with self._lock:
            if self.is_closed:
                return True

            if self.is_open:
                # Check if timeout elapsed
                if (
                    self.last_failure_time
                    and time.time() - self.last_failure_time >= self.config.timeout
                ):
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._half_open_calls = 1
                    return True
                return False

            if self.is_half_open:
                # Allow limited concurrent calls
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()

        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitState.OPEN:
            self.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

        # Update Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            state_value = {"closed": 0, "open": 1, "half_open": 2}[new_state.value]
            circuit_state_gauge.labels(circuit_name=self.name).set(state_value)

        logger.info(
            f"Circuit {self.name}: {old_state.value} -> {new_state.value}",
            extra={
                "circuit": self.name,
                "old_state": old_state,
                "new_state": new_state,
            },
        )

    async def record_success(self, latency_ms: float) -> None:
        """Record a successful call."""
        async with self._lock:
            self.metrics.record_latency(latency_ms)

            if PROMETHEUS_AVAILABLE:
                circuit_success_total.labels(circuit_name=self.name).inc()
                circuit_latency_histogram.labels(circuit_name=self.name).observe(
                    latency_ms / 1000
                )

            if self.is_half_open:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    async def record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        # Check if exception is excluded
        if isinstance(error, self.config.excluded_exceptions):
            return

        async with self._lock:
            self.metrics.record_error()
            self.failure_count += 1
            self.last_failure_time = time.time()

            if PROMETHEUS_AVAILABLE:
                circuit_failures_total.labels(
                    circuit_name=self.name, error_type=type(error).__name__
                ).inc()

            if self.is_half_open:
                # Any failure in half-open goes back to open
                self._transition_to(CircuitState.OPEN)
            elif self.is_closed:
                # Check adaptive threshold
                threshold = self.metrics.get_adaptive_threshold(
                    self.config.failure_threshold
                )
                if self.failure_count >= threshold:
                    self._transition_to(CircuitState.OPEN)

    async def execute(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        fallback: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Arguments for func
            fallback: Optional fallback function if circuit is open
            **kwargs: Keyword arguments for func

        Returns:
            Result from func or fallback

        Raises:
            CircuitBreakerError: If circuit is open and no fallback
        """
        if not await self._can_execute():
            if fallback:
                logger.warning(
                    f"Circuit {self.name} is open, using fallback",
                    extra={"circuit": self.name},
                )
                return (
                    await fallback(*args, **kwargs)
                    if asyncio.iscoroutinefunction(fallback)
                    else fallback(*args, **kwargs)
                )
            raise CircuitBreakerError(self.name)

        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            await self.record_success(latency_ms)
            return result
        except Exception as e:
            await self.record_failure(e)
            raise

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_state_change": self.last_state_change,
            "error_rate": self.metrics.error_rate,
            "avg_latency_ms": self.metrics.avg_latency,
            "p95_latency_ms": self.metrics.p95_latency,
            "p99_latency_ms": self.metrics.p99_latency,
        }


# =============================================================================
# CIRCUIT BREAKER REGISTRY
# =============================================================================


class CircuitBreakerRegistry:
    """Singleton registry for all circuit breakers."""

    _instance: "CircuitBreakerRegistry | None" = None
    _circuits: dict[str, CircuitBreaker]

    def __new__(cls) -> "CircuitBreakerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._circuits = {}
        return cls._instance

    def get_or_create(
        self, name: str, config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker by name."""
        if name not in self._circuits:
            self._circuits[name] = CircuitBreaker(name, config)
        return self._circuits[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get a circuit breaker by name."""
        return self._circuits.get(name)

    def get_all_status(self) -> dict[str, Any]:
        """Get status of all circuit breakers."""
        return {name: cb.get_status() for name, cb in self._circuits.items()}

    def reset(self, name: str) -> bool:
        """Reset a circuit breaker to closed state."""
        if name in self._circuits:
            cb = self._circuits[name]
            cb._transition_to(CircuitState.CLOSED)
            return True
        return False

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for cb in self._circuits.values():
            cb._transition_to(CircuitState.CLOSED)


# Global registry instance
_registry = CircuitBreakerRegistry()


def get_circuit_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    return _registry


# =============================================================================
# RETRY LOGIC WITH TENACITY
# =============================================================================

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter: float = 1.0,
    retry_on: tuple = (RetryableError, TimeoutError, ConnectionError),
    operation_name: str | None = None,
) -> Callable:
    """
    Decorator for retry logic with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        jitter: Maximum jitter to add to wait time
        retry_on: Tuple of exception types to retry on
        operation_name: Name for metrics (defaults to function name)

    Returns:
        Decorated function with retry logic
    """
    if not TENACITY_AVAILABLE:
        # Fallback: simple decorator without retry
        def passthrough_decorator(func: Callable) -> Callable:
            return func

        return passthrough_decorator

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        name = operation_name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            async for attempt_state in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential_jitter(
                    initial=min_wait, max=max_wait, jitter=jitter
                ),
                retry=retry_if_exception_type(retry_on),
                reraise=True,
            ):
                with attempt_state:
                    attempt += 1
                    if attempt > 1:
                        logger.info(
                            f"Retry attempt {attempt}/{max_attempts} for {name}",
                            extra={"operation": name, "attempt": attempt},
                        )
                        if PROMETHEUS_AVAILABLE:
                            retry_attempts_total.labels(
                                operation_name=name, attempt=str(attempt)
                            ).inc()
                    return await func(*args, **kwargs)
            # This should never be reached
            raise RuntimeError("Retry loop ended unexpectedly")

        return wrapper

    return decorator


# =============================================================================
# DECORATORS
# =============================================================================


def circuit_breaker(
    circuit_name: str,
    config: CircuitBreakerConfig | None = None,
    fallback: Callable | None = None,
) -> Callable:
    """
    Decorator to wrap async function with circuit breaker.

    Args:
        circuit_name: Name of the circuit breaker
        config: Optional configuration
        fallback: Optional fallback function

    Usage:
        @circuit_breaker("bybit_api")
        async def fetch_from_bybit():
            ...
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        cb = _registry.get_or_create(circuit_name, config)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await cb.execute(func, *args, fallback=fallback, **kwargs)

        return wrapper

    return decorator


def resilient_call(
    circuit_name: str,
    max_retries: int = 3,
    circuit_config: CircuitBreakerConfig | None = None,
    fallback: Callable | None = None,
) -> Callable:
    """
    Combined decorator for circuit breaker + retry logic.

    This is the recommended decorator for all external API calls.

    Args:
        circuit_name: Name of the circuit breaker
        max_retries: Maximum retry attempts
        circuit_config: Optional circuit breaker configuration
        fallback: Optional fallback function

    Usage:
        @resilient_call("deepseek_api", max_retries=3)
        async def call_deepseek(prompt: str):
            ...
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        # Apply retry logic first (inner)
        if TENACITY_AVAILABLE:
            retried_func = with_retry(
                max_attempts=max_retries,
                operation_name=circuit_name,
            )(func)
        else:
            retried_func = func

        # Then apply circuit breaker (outer)
        cb = _registry.get_or_create(circuit_name, circuit_config)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await cb.execute(retried_func, *args, fallback=fallback, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "CircuitState",
    # Exceptions
    "CircuitBreakerError",
    "RetryableError",
    "RateLimitError",
    "TransientError",
    # Classes
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "AdaptiveMetrics",
    # Functions
    "get_circuit_registry",
    # Decorators
    "circuit_breaker",
    "with_retry",
    "resilient_call",
]
