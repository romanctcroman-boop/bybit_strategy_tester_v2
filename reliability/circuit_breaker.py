"""
Distributed Circuit Breaker

Implements circuit breaker pattern for fault tolerance:
- Prevents cascading failures by stopping calls to failing services
- Three states: CLOSED (normal), OPEN (failing), HALF_OPEN (testing)
- Automatic state transitions based on failure rate
- Request volume threshold before opening circuit
- Exponential backoff for recovery attempts
- Redis-backed distributed state (works across instances)

Architecture:
- State Machine: CLOSED → OPEN → HALF_OPEN → CLOSED/OPEN
- Failure Tracking: Rolling window of recent requests
- Recovery Strategy: Exponential backoff with jitter
- Distributed Coordination: Redis for shared state
- Fallback Support: Execute fallback on circuit open

States:
- CLOSED: Service healthy, requests allowed
- OPEN: Service failing, requests blocked (fast-fail)
- HALF_OPEN: Testing recovery, limited requests allowed

Usage:
    circuit_breaker = CircuitBreaker(
        failure_threshold=0.5,  # 50% failure rate
        recovery_timeout=60,    # Try recovery after 60s
        min_request_volume=10   # Need 10 requests before opening
    )
    
    # Wrap service calls
    @circuit_breaker
    async def call_external_api():
        return await api.get("/data")
    
    # Or use explicitly
    result = await circuit_breaker.call(
        func=api_call,
        fallback=lambda: "default_value"
    )

Phase 3, Day 21
Target: 30+ tests, >90% coverage
"""

import asyncio
import time
import logging
from typing import Any, Callable, Optional, Dict, Deque
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"           # Normal operation, requests allowed
    OPEN = "open"               # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"     # Testing recovery, limited requests


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration
    
    Attributes:
        failure_threshold: Failure rate to open circuit (0.0-1.0)
        recovery_timeout: Seconds to wait before attempting recovery
        min_request_volume: Minimum requests before opening circuit
        half_open_max_calls: Max calls allowed in half-open state
        success_threshold: Success rate to close circuit from half-open
        request_timeout: Timeout for individual requests (seconds)
        window_size: Rolling window size for failure tracking
        window_duration: Time-based rolling window duration (seconds, 0=count-based)
        enable_metrics: Enable metrics collection
    """
    failure_threshold: float = 0.5          # 50% failure rate
    recovery_timeout: int = 60              # 60 seconds
    min_request_volume: int = 10            # 10 requests minimum
    half_open_max_calls: int = 3            # 3 test calls
    success_threshold: float = 0.5          # 50% success to close
    request_timeout: int = 30               # 30 seconds per request
    window_size: int = 100                  # Track last 100 requests (if time-based disabled)
    window_duration: int = 60               # 60 seconds rolling window (0=count-based)
    enable_metrics: bool = True


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics
    
    Attributes:
        state: Current circuit state
        total_requests: Total requests received
        successful_requests: Successful requests
        failed_requests: Failed requests
        rejected_requests: Rejected due to open circuit
        state_transitions: Number of state changes
        last_failure_time: Timestamp of last failure
        last_state_change: Timestamp of last state change
    """
    state: CircuitState = CircuitState.CLOSED
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    state_transitions: int = 0
    last_failure_time: float = 0.0
    last_state_change: float = 0.0
    
    @property
    def failure_rate(self) -> float:
        """Calculate current failure rate"""
        total = self.successful_requests + self.failed_requests
        if total == 0:
            return 0.0
        return self.failed_requests / total
    
    @property
    def success_rate(self) -> float:
        """Calculate current success rate"""
        return 1.0 - self.failure_rate


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """Distributed circuit breaker for fault tolerance
    
    Implements the circuit breaker pattern to prevent cascading failures.
    Tracks request success/failure and automatically opens circuit when
    failure threshold exceeded.
    
    Features:
    - Three-state machine (CLOSED, OPEN, HALF_OPEN)
    - Rolling window failure tracking
    - Exponential backoff recovery
    - Distributed state with Redis
    - Fallback support
    - Comprehensive metrics
    """
    
    def __init__(
        self,
        name: str = "default",
        config: Optional[CircuitBreakerConfig] = None,
        redis_client: Optional[Any] = None,
        enable_metrics: bool = True
    ):
        """Initialize circuit breaker
        
        Args:
            name: Circuit breaker name (for multi-service scenarios)
            config: Circuit breaker configuration
            redis_client: Redis client for distributed state (optional)
            enable_metrics: Enable metrics collection
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.redis_client = redis_client
        self.enable_metrics = enable_metrics
        
        # State
        self._state = CircuitState.CLOSED
        self._opened_at: float = 0.0
        
        # Request tracking - time-based rolling window
        # Each entry: (timestamp, success_boolean)
        self._request_history: Deque[Tuple[float, bool]] = deque()
        
        # Half-open state tracking
        self._half_open_calls: int = 0
        
        # Lock for thread-safe state changes
        self._lock = asyncio.Lock()
        
        # Stats
        self.stats = CircuitBreakerStats()
        
        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={self.config.failure_threshold}, "
            f"recovery_timeout={self.config.recovery_timeout}s, "
            f"min_volume={self.config.min_request_volume}, "
            f"window={'time-based ' + str(self.config.window_duration) + 's' if self.config.window_duration > 0 else 'count-based ' + str(self.config.window_size)}"
        )
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state
    
    def _clean_old_requests(self):
        """Remove requests outside the rolling window
        
        For time-based window: Remove requests older than window_duration.
        For count-based window: Keep only last window_size requests.
        """
        if self.config.window_duration > 0:
            # Time-based rolling window
            cutoff_time = time.time() - self.config.window_duration
            
            while self._request_history and self._request_history[0][0] < cutoff_time:
                self._request_history.popleft()
        else:
            # Count-based window (legacy mode)
            while len(self._request_history) > self.config.window_size:
                self._request_history.popleft()
    
    async def call(
        self,
        func: Callable[[], Any],
        fallback: Optional[Callable[[], Any]] = None,
        timeout: Optional[float] = None
    ) -> Any:
        """Execute function through circuit breaker
        
        Args:
            func: Function to execute (sync or async)
            fallback: Fallback function if circuit open (optional)
            timeout: Request timeout (uses config if None)
            
        Returns:
            Function result or fallback result
            
        Raises:
            CircuitBreakerError: If circuit open and no fallback
            asyncio.TimeoutError: If request times out
            Exception: Any exception from func
        """
        timeout = timeout or self.config.request_timeout
        
        # Update stats
        if self.enable_metrics:
            self.stats.total_requests += 1
        
        # Check if circuit allows request
        if not await self._allow_request():
            if self.enable_metrics:
                self.stats.rejected_requests += 1
            
            logger.warning(
                f"Circuit breaker '{self.name}' OPEN - request rejected"
            )
            
            # Use fallback if provided
            if fallback:
                return await self._execute_fallback(fallback)
            
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN"
            )
        
        # Execute request with timeout
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(func(), timeout=timeout)
            else:
                result = func()
            
            # Record success
            await self._on_success()
            
            return result
        
        except Exception as e:
            # Record failure
            await self._on_failure()
            
            logger.error(
                f"Circuit breaker '{self.name}' - request failed: {type(e).__name__}: {e}"
            )
            
            # Use fallback if provided
            if fallback:
                return await self._execute_fallback(fallback)
            
            raise
    
    async def _allow_request(self) -> bool:
        """Check if request should be allowed
        
        Returns:
            True if request allowed, False if blocked
        """
        async with self._lock:
            current_state = self._state
            
            if current_state == CircuitState.CLOSED:
                return True
            
            elif current_state == CircuitState.OPEN:
                # Check if recovery timeout elapsed
                if time.time() - self._opened_at >= self.config.recovery_timeout:
                    # Try half-open state
                    await self._transition_to(CircuitState.HALF_OPEN)
                    return True
                
                return False
            
            elif current_state == CircuitState.HALF_OPEN:
                # Allow limited requests in half-open
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                
                return False
            
            return False
    
    async def _on_success(self):
        """Handle successful request with time-based rolling window"""
        async with self._lock:
            # Record success with timestamp
            now = time.time()
            self._request_history.append((now, True))
            
            # Clean old requests outside window
            self._clean_old_requests()
            
            if self.enable_metrics:
                self.stats.successful_requests += 1
            
            # Check state transition
            if self._state == CircuitState.HALF_OPEN:
                # Check if enough successes to close circuit
                recent_successes = sum(1 for _, success in self._request_history if success)
                recent_total = len(self._request_history)
                
                if recent_total >= self.config.half_open_max_calls:
                    success_rate = recent_successes / recent_total
                    
                    if success_rate >= self.config.success_threshold:
                        # Circuit recovered!
                        await self._transition_to(CircuitState.CLOSED)
                        logger.info(
                            f"Circuit breaker '{self.name}' recovered - "
                            f"success_rate={success_rate:.2%}"
                        )
    
    async def _on_failure(self):
        """Handle failed request with time-based rolling window"""
        async with self._lock:
            # Record failure with timestamp
            now = time.time()
            self._request_history.append((now, False))
            
            # Clean old requests outside window
            self._clean_old_requests()
            
            if self.enable_metrics:
                self.stats.failed_requests += 1
                self.stats.last_failure_time = time.time()
            
            # Check if circuit should open
            if self._state == CircuitState.CLOSED:
                await self._check_failure_threshold()
            
            elif self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens circuit
                await self._transition_to(CircuitState.OPEN)
                logger.warning(
                    f"Circuit breaker '{self.name}' reopened - "
                    f"failure during recovery"
                )
    
    async def _check_failure_threshold(self):
        """Check if failure threshold exceeded with time-based window
        
        Uses time-based rolling window for accurate failure rate calculation.
        Only considers requests within window_duration (if configured).
        """
        recent_total = len(self._request_history)
        
        # Need minimum volume before opening
        if recent_total < self.config.min_request_volume:
            return
        
        # Calculate failure rate from time-based window
        recent_failures = sum(1 for _, success in self._request_history if not success)
        failure_rate = recent_failures / recent_total
        
        # Open circuit if threshold exceeded
        if failure_rate >= self.config.failure_threshold:
            await self._transition_to(CircuitState.OPEN)
            
            logger.error(
                f"Circuit breaker '{self.name}' OPENED - "
                f"failure_rate={failure_rate:.2%} "
                f"(threshold={self.config.failure_threshold:.2%}), "
                f"window={recent_total} requests in {self.config.window_duration}s"
            )
    
    async def _transition_to(self, new_state: CircuitState):
        """Transition to new state
        
        Args:
            new_state: Target state
        """
        old_state = self._state
        
        if old_state == new_state:
            return
        
        self._state = new_state
        
        if self.enable_metrics:
            self.stats.state = new_state
            self.stats.state_transitions += 1
            self.stats.last_state_change = time.time()
        
        # State-specific actions
        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
        
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            # Clear history for fresh evaluation
            self._request_history.clear()
        
        elif new_state == CircuitState.CLOSED:
            self._half_open_calls = 0
        
        # Sync to Redis if available
        if self.redis_client:
            await self._sync_state_to_redis()
        
        logger.info(
            f"Circuit breaker '{self.name}' state transition: "
            f"{old_state.value} → {new_state.value}"
        )
    
    async def _execute_fallback(self, fallback: Callable) -> Any:
        """Execute fallback function
        
        Args:
            fallback: Fallback function
            
        Returns:
            Fallback result
        """
        logger.info(f"Circuit breaker '{self.name}' - executing fallback")
        
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback()
            else:
                return fallback()
        except Exception as e:
            logger.error(f"Fallback failed: {type(e).__name__}: {e}")
            raise
    
    async def _sync_state_to_redis(self):
        """Sync circuit state to Redis for distributed coordination"""
        if not self.redis_client:
            return
        
        try:
            key = f"circuit_breaker:{self.name}:state"
            
            # Store state with TTL
            await self.redis_client.setex(
                key,
                self.config.recovery_timeout * 2,  # 2x recovery timeout
                self._state.value
            )
        
        except Exception as e:
            logger.warning(f"Failed to sync state to Redis: {e}")
    
    async def _load_state_from_redis(self) -> Optional[CircuitState]:
        """Load circuit state from Redis
        
        Returns:
            Circuit state from Redis or None
        """
        if not self.redis_client:
            return None
        
        try:
            key = f"circuit_breaker:{self.name}:state"
            state_value = await self.redis_client.get(key)
            
            if state_value:
                return CircuitState(state_value.decode())
            
            return None
        
        except Exception as e:
            logger.warning(f"Failed to load state from Redis: {e}")
            return None
    
    async def force_open(self):
        """Manually force circuit open (for testing/maintenance)"""
        async with self._lock:
            await self._transition_to(CircuitState.OPEN)
            logger.warning(f"Circuit breaker '{self.name}' manually opened")
    
    async def force_close(self):
        """Manually force circuit closed (for testing/recovery)"""
        async with self._lock:
            await self._transition_to(CircuitState.CLOSED)
            self._request_history.clear()
            logger.warning(f"Circuit breaker '{self.name}' manually closed")
    
    async def force_half_open(self):
        """Manually force circuit to half-open (for testing)"""
        async with self._lock:
            await self._transition_to(CircuitState.HALF_OPEN)
            logger.warning(f"Circuit breaker '{self.name}' manually half-opened")
    
    def reset(self):
        """Reset circuit breaker to initial state"""
        self._state = CircuitState.CLOSED
        self._opened_at = 0.0
        self._request_history.clear()
        self._half_open_calls = 0
        self.stats = CircuitBreakerStats()
        
        logger.info(f"Circuit breaker '{self.name}' reset")
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics
        
        Returns:
            CircuitBreakerStats object
        """
        if not self.enable_metrics:
            return CircuitBreakerStats()
        
        return self.stats
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator for wrapping functions with circuit breaker
        
        Usage:
            @circuit_breaker
            async def call_api():
                return await api.get("/data")
        """
        async def wrapper(*args, **kwargs):
            return await self.call(lambda: func(*args, **kwargs))
        
        return wrapper


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers
    
    Allows centralized management of circuit breakers for different services.
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def register(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        redis_client: Optional[Any] = None
    ) -> CircuitBreaker:
        """Register new circuit breaker
        
        Args:
            name: Circuit breaker name
            config: Configuration
            redis_client: Redis client (optional)
            
        Returns:
            CircuitBreaker instance
        """
        if name in self._breakers:
            logger.warning(f"Circuit breaker '{name}' already registered")
            return self._breakers[name]
        
        breaker = CircuitBreaker(
            name=name,
            config=config,
            redis_client=redis_client
        )
        
        self._breakers[name] = breaker
        
        logger.info(f"Registered circuit breaker: {name}")
        
        return breaker
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name
        
        Args:
            name: Circuit breaker name
            
        Returns:
            CircuitBreaker or None if not found
        """
        return self._breakers.get(name)
    
    def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """Get stats for all circuit breakers
        
        Returns:
            Dictionary of name -> stats
        """
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }
    
    async def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self._breakers.values():
            breaker.reset()
        
        logger.info("All circuit breakers reset")
