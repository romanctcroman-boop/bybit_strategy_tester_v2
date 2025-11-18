"""
Retry Policy with Exponential Backoff and Jitter

Implements intelligent retry logic for transient failures based on:
- DeepSeek Agent: Exponential backoff 2^n, max 30s, jitter prevents thundering herd
- Perplexity Agent: Retry only 5xx errors, NOT 4xx (client errors unrecoverable)

Features:
- Exponential backoff: 1s → 2s → 4s → 8s → 16s (max 30s)
- Jitter: Randomize 0.5x to 1.5x to prevent synchronized retries
- Exception filtering: Retry transient errors only (network, 5xx)
- Max retries: Configurable (default 3)
- Integration ready: Works with Circuit Breaker

Usage:
    from reliability.retry_policy import RetryPolicy, RetryConfig
    
    # Create retry policy
    config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2,
        jitter=True
    )
    policy = RetryPolicy(config)
    
    # Wrap function calls
    async def api_call():
        response = await httpx.get("https://api.example.com/data")
        return response.json()
    
    result = await policy.retry(api_call)
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any, Optional, Type, Tuple

logger = logging.getLogger(__name__)


class RetryableException(Exception):
    """Base class for exceptions that should be retried"""
    pass


class NonRetryableException(Exception):
    """Base class for exceptions that should NOT be retried"""
    pass


@dataclass
class RetryConfig:
    """Configuration for retry policy
    
    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 30.0)
        exponential_base: Base for exponential backoff (default: 2)
        jitter: Add randomization to delays (default: True)
        jitter_percentage: Percentage of jitter to apply (0.0-1.0, default: 1.0 = 100% full jitter)
                          - 0.0 = No jitter (deterministic)
                          - 0.5 = Half jitter: uniform(0.5 * delay, delay)
                          - 1.0 = Full jitter: uniform(0, delay) [AWS SDK standard]
        jitter_min: DEPRECATED - use jitter_percentage instead (kept for backward compatibility)
        jitter_max: DEPRECATED - use jitter_percentage instead (kept for backward compatibility)
    """
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: int = 2
    jitter: bool = True
    jitter_percentage: float = 1.0  # 100% full jitter by default (AWS SDK standard)
    jitter_min: float = 0.0  # DEPRECATED: Legacy field for backward compatibility
    jitter_max: float = 1.0  # DEPRECATED: Legacy field for backward compatibility


@dataclass
class RetryAttempt:
    """Record of a single retry attempt"""
    attempt_number: int
    timestamp: float
    success: bool
    error: Optional[str] = None
    delay_before: Optional[float] = None


class RetryPolicy:
    """Retry policy with exponential backoff and jitter
    
    Features:
    - Exponential backoff: delay = base_delay * (exponential_base ^ attempt)
    - Jitter: Randomize delay to prevent thundering herd
    - Exception filtering: Only retry specific exception types
    - Attempt tracking: Record all retry attempts for metrics
    
    Example:
        policy = RetryPolicy()
        
        async def flaky_api():
            response = await httpx.get("https://api.example.com")
            return response.json()
        
        try:
            result = await policy.retry(flaky_api)
            print(f"Success: {result}")
        except Exception as e:
            print(f"Failed after {policy.total_attempts} attempts: {e}")
    """
    
    def __init__(self, config: Optional[RetryConfig] = None, circuit_breaker: Optional[Any] = None):
        """Initialize retry policy
        
        Args:
            config: Optional retry configuration (uses defaults if None)
            circuit_breaker: Optional circuit breaker instance for integration
        """
        self.config = config or RetryConfig()
        self.circuit_breaker = circuit_breaker
        self.total_attempts = 0
        self.total_successes = 0
        self.total_failures = 0
        self.retry_history: list[RetryAttempt] = []
        
        logger.info(
            f"Retry policy initialized: max_retries={self.config.max_retries}, "
            f"base_delay={self.config.base_delay}s, max_delay={self.config.max_delay}s, "
            f"circuit_breaker={'enabled' if circuit_breaker else 'disabled'}"
        )
    
    async def retry(
        self,
        func: Callable,
        *args,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        **kwargs
    ) -> Any:
        """Execute function with retry logic and circuit breaker integration
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            retryable_exceptions: Tuple of exception types to retry (default: all)
            **kwargs: Keyword arguments for func
        
        Returns:
            Result from successful func execution
        
        Raises:
            Exception: Last exception if all retries exhausted or circuit open
        """
        if retryable_exceptions is None:
            # Default: retry all exceptions except NonRetryableException
            retryable_exceptions = (Exception,)
        
        # ✅ FIX: Check circuit breaker before retrying
        if self.circuit_breaker:
            # Import here to avoid circular dependency
            from reliability.circuit_breaker import CircuitState
            
            # Get circuit state
            state = getattr(self.circuit_breaker, 'state', CircuitState.CLOSED)
            
            # Compare enum values (strings) for compatibility with mocks
            state_value = state.value if hasattr(state, 'value') else state
            
            if state_value == CircuitState.OPEN.value or state == CircuitState.OPEN:
                # Circuit is open, fail fast without retry
                logger.warning("Circuit breaker is OPEN, skipping retry attempts")
                raise NonRetryableException(
                    "Circuit breaker is OPEN - service unavailable, retry aborted"
                )
        
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):  # +1 for initial attempt
            self.total_attempts += 1
            attempt_start = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Success!
                self.total_successes += 1
                self._record_attempt(
                    attempt_number=attempt,
                    timestamp=attempt_start,
                    success=True
                )
                
                if attempt > 0:
                    logger.info(
                        f"Retry succeeded on attempt {attempt + 1}/{self.config.max_retries + 1}"
                    )
                
                return result
            
            except NonRetryableException as e:
                # Non-retryable error, fail immediately
                self.total_failures += 1
                self._record_attempt(
                    attempt_number=attempt,
                    timestamp=attempt_start,
                    success=False,
                    error=str(e)
                )
                logger.error(f"Non-retryable exception: {type(e).__name__}: {e}")
                raise
            
            except retryable_exceptions as e:
                last_exception = e
                self.total_failures += 1
                
                # Check if we have retries left
                if attempt >= self.config.max_retries:
                    # No more retries
                    self._record_attempt(
                        attempt_number=attempt,
                        timestamp=attempt_start,
                        success=False,
                        error=str(e)
                    )
                    logger.error(
                        f"All retries exhausted after {attempt + 1} attempts: "
                        f"{type(e).__name__}: {e}"
                    )
                    raise
                
                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt)
                
                self._record_attempt(
                    attempt_number=attempt,
                    timestamp=attempt_start,
                    success=False,
                    error=str(e),
                    delay_before=delay
                )
                
                logger.warning(
                    f"Retry attempt {attempt + 1}/{self.config.max_retries + 1} failed: "
                    f"{type(e).__name__}: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                # Wait before retry
                await asyncio.sleep(delay)
        
        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay before next retry
        
        Implements configurable jitter following AWS SDK best practices:
        - 0% jitter: Deterministic exponential backoff
        - 50% jitter: uniform(0.5 * delay, delay)
        - 100% jitter (default): uniform(0, delay) [AWS SDK full jitter]
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in seconds with exponential backoff and optional jitter
        """
        # Exponential backoff: base_delay * (exponential_base ^ attempt)
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.config.max_delay)
        
        # Apply jitter if enabled
        if self.config.jitter:
            # Check if using new jitter_percentage or legacy jitter_min/max
            if hasattr(self.config, 'jitter_percentage'):
                # New method: Configurable jitter percentage (0.0 to 1.0)
                # jitter_percentage = 1.0 → full jitter: uniform(0, delay)
                # jitter_percentage = 0.5 → half jitter: uniform(0.5 * delay, delay)
                # jitter_percentage = 0.0 → no jitter: delay unchanged
                min_jitter = (1.0 - self.config.jitter_percentage) * delay
                max_jitter = delay
                delay = random.uniform(min_jitter, max_jitter)
            else:
                # Legacy method: jitter_min/max multipliers (backward compatibility)
                jitter_multiplier = random.uniform(
                    self.config.jitter_min,
                    self.config.jitter_max
                )
                delay *= jitter_multiplier
        
        return delay
    
    def _record_attempt(
        self,
        attempt_number: int,
        timestamp: float,
        success: bool,
        error: Optional[str] = None,
        delay_before: Optional[float] = None
    ):
        """Record retry attempt for metrics
        
        Args:
            attempt_number: Attempt number (0-indexed)
            timestamp: Timestamp of attempt
            success: Whether attempt succeeded
            error: Error message if failed
            delay_before: Delay before this attempt (None for first attempt)
        """
        self.retry_history.append(RetryAttempt(
            attempt_number=attempt_number,
            timestamp=timestamp,
            success=success,
            error=error,
            delay_before=delay_before
        ))
    
    def get_metrics(self) -> dict[str, Any]:
        """Get retry policy metrics
        
        Returns:
            Dictionary with metrics:
            - total_attempts: Total number of attempts
            - total_successes: Total successful attempts
            - total_failures: Total failed attempts
            - success_rate: Overall success rate
            - retry_rate: Percentage of calls that needed retries
            - avg_attempts_per_call: Average attempts per call
        """
        total_calls = self.total_successes
        retried_calls = len([
            h for h in self.retry_history
            if h.success and h.attempt_number > 0
        ])
        
        return {
            "total_attempts": self.total_attempts,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "success_rate": self.total_successes / self.total_attempts if self.total_attempts > 0 else 0.0,
            "retry_rate": retried_calls / total_calls if total_calls > 0 else 0.0,
            "avg_attempts_per_call": self.total_attempts / total_calls if total_calls > 0 else 0.0,
            "config": {
                "max_retries": self.config.max_retries,
                "base_delay": self.config.base_delay,
                "max_delay": self.config.max_delay,
                "jitter": self.config.jitter
            }
        }
    
    def reset(self):
        """Reset all metrics and history"""
        self.total_attempts = 0
        self.total_successes = 0
        self.total_failures = 0
        self.retry_history.clear()
        logger.info("Retry policy metrics reset")
    
    def __repr__(self) -> str:
        return (
            f"RetryPolicy(max_retries={self.config.max_retries}, "
            f"attempts={self.total_attempts}, successes={self.total_successes})"
        )


# Helper function to determine if HTTP exception is retryable
def is_http_error_retryable(status_code: int) -> bool:
    """Determine if HTTP status code should be retried
    
    Based on Perplexity Agent recommendation:
    - 5xx errors: Server errors, usually transient → RETRY
    - 429: Rate limit, temporary → RETRY (with exponential backoff)
    - 408: Request timeout → RETRY
    - 4xx errors (except 429, 408): Client errors, permanent → DON'T RETRY
    
    Args:
        status_code: HTTP status code
    
    Returns:
        True if error should be retried, False otherwise
    """
    if 500 <= status_code < 600:
        # Server errors (5xx) - usually transient
        return True
    
    if status_code in (408, 429, 503, 504):
        # Specific retryable 4xx/5xx codes
        # 408: Request Timeout
        # 429: Too Many Requests (rate limit)
        # 503: Service Unavailable
        # 504: Gateway Timeout
        return True
    
    # All other errors (mostly 4xx) - client errors, don't retry
    return False
