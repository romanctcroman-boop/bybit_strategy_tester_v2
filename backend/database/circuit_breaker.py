"""
Circuit Breaker Pattern for Database Operations

Prevents cascade failures by temporarily stopping requests to a failing service.
When failure threshold is reached, the circuit "opens" and fails fast
for a recovery period before attempting again.

States:
    CLOSED: Normal operation, requests pass through
    OPEN: Failure threshold reached, requests fail immediately
    HALF_OPEN: Recovery period passed, allowing one test request

Usage:
    from backend.database.circuit_breaker import circuit_breaker

    @circuit_breaker
    def risky_db_operation():
        # Database operation that might fail
        pass

    # Or use the instance directly:
    from backend.database.circuit_breaker import db_circuit_breaker

    with db_circuit_breaker:
        # Protected operation
        pass
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5
    """Number of consecutive failures before opening circuit."""

    recovery_timeout: float = 60.0
    """Seconds to wait before attempting recovery (HALF_OPEN)."""

    success_threshold: int = 2
    """Number of successes in HALF_OPEN before closing circuit."""

    excluded_exceptions: tuple = ()
    """Exception types that should not count as failures."""

    name: str = "database"
    """Name for logging and metrics."""


@dataclass
class CircuitBreakerStats:
    """Runtime statistics for circuit breaker."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: List[Dict[str, Any]] = field(default_factory=list)
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreakerOpenError(Exception):
    """Raised when circuit is open and request is rejected."""

    def __init__(self, circuit_name: str, recovery_in: float):
        self.circuit_name = circuit_name
        self.recovery_in = recovery_in
        super().__init__(
            f"Circuit '{circuit_name}' is OPEN. Recovery in {recovery_in:.1f}s"
        )


class CircuitBreaker:
    """
    Circuit Breaker implementation for database operations.

    Thread-safe implementation that can be used as:
    - Decorator for functions
    - Context manager for code blocks
    - Direct call with execute() method

    Example:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))

        # As decorator
        @cb
        def db_operation():
            pass

        # As context manager
        with cb:
            cursor.execute("SELECT ...")

        # Direct call
        result = cb.execute(lambda: cursor.execute("SELECT ..."))
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats()
        self._lock = threading.Lock()
        self._last_state_change = time.time()

        logger.info(
            f"CircuitBreaker '{self.config.name}' initialized: "
            f"threshold={self.config.failure_threshold}, "
            f"recovery={self.config.recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """Current circuit state with automatic transitions."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                time_since_open = time.time() - self._last_state_change
                if time_since_open >= self.config.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get current statistics."""
        return self._stats

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state with logging."""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._last_state_change = time.time()

        # Record state change
        self._stats.state_changes.append(
            {
                "from": old_state.value,
                "to": new_state.value,
                "timestamp": self._last_state_change,
            }
        )

        # Keep only last 100 state changes
        if len(self._stats.state_changes) > 100:
            self._stats.state_changes = self._stats.state_changes[-100:]

        logger.warning(
            f"CircuitBreaker '{self.config.name}': {old_state.value} -> {new_state.value}"
        )

    def _record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.last_success_time = time.time()
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes += 1

            # In HALF_OPEN, check if we can close the circuit
            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def _record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        # Check if this exception should be excluded
        if isinstance(error, self.config.excluded_exceptions):
            return

        with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.last_failure_time = time.time()
            self._stats.consecutive_successes = 0
            self._stats.consecutive_failures += 1

            # Check if we should open the circuit
            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

            # In HALF_OPEN, any failure opens the circuit again
            elif self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)

    def _check_state(self) -> None:
        """Check if request should be allowed."""
        state = self.state  # This triggers automatic transitions

        if state == CircuitState.OPEN:
            time_since_open = time.time() - self._last_state_change
            recovery_in = self.config.recovery_timeout - time_since_open

            self._stats.rejected_calls += 1
            raise CircuitBreakerOpenError(self.config.name, recovery_in)

    def execute(self, func: Callable[[], Any]) -> Any:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Zero-argument callable to execute

        Returns:
            Result of the function

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If function raises and circuit trips
        """
        self._check_state()

        try:
            result = func()
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise

    def __call__(self, func: Callable) -> Callable:
        """Use as decorator."""

        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.execute(lambda: func(*args, **kwargs))

        return wrapper

    def __enter__(self):
        """Use as context manager."""
        self._check_state()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record result on context exit."""
        if exc_type is None:
            self._record_success()
        else:
            self._record_failure(exc_val)
        return False  # Don't suppress exceptions

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes = 0
            logger.info(f"CircuitBreaker '{self.config.name}' manually reset")

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics for monitoring."""
        with self._lock:
            return {
                "name": self.config.name,
                "state": self._state.value,
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "rejected_calls": self._stats.rejected_calls,
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes,
                "last_failure_time": self._stats.last_failure_time,
                "last_success_time": self._stats.last_success_time,
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            }

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        metrics = self.get_metrics()
        name = self.config.name

        lines = [
            "# HELP circuit_breaker_state Circuit breaker state (0=closed, 1=half_open, 2=open)",
            "# TYPE circuit_breaker_state gauge",
            f'circuit_breaker_state{{name="{name}"}} {["closed", "half_open", "open"].index(metrics["state"])}',
            "",
            "# HELP circuit_breaker_calls_total Total calls by result",
            "# TYPE circuit_breaker_calls_total counter",
            f'circuit_breaker_calls_total{{name="{name}",result="success"}} {metrics["successful_calls"]}',
            f'circuit_breaker_calls_total{{name="{name}",result="failure"}} {metrics["failed_calls"]}',
            f'circuit_breaker_calls_total{{name="{name}",result="rejected"}} {metrics["rejected_calls"]}',
            "",
            "# HELP circuit_breaker_consecutive_failures Current consecutive failures",
            "# TYPE circuit_breaker_consecutive_failures gauge",
            f'circuit_breaker_consecutive_failures{{name="{name}"}} {metrics["consecutive_failures"]}',
        ]

        return "\n".join(lines)


# ============================================================================
# Global Instance
# ============================================================================

# Default circuit breaker for database operations
db_circuit_breaker = CircuitBreaker(
    CircuitBreakerConfig(
        name="database",
        failure_threshold=5,
        recovery_timeout=60.0,
        success_threshold=2,
    )
)


def circuit_breaker(func: Callable) -> Callable:
    """
    Decorator that applies the default database circuit breaker.

    Usage:
        @circuit_breaker
        def my_db_function():
            # Database operation
            pass
    """
    return db_circuit_breaker(func)


def get_circuit_breaker_metrics() -> Dict[str, Any]:
    """Get metrics from the default circuit breaker."""
    return db_circuit_breaker.get_metrics()


def reset_circuit_breaker() -> None:
    """Reset the default circuit breaker."""
    db_circuit_breaker.reset()
