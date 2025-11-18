"""
Circuit Breaker Manager for AI Agent System

Implements the Circuit Breaker pattern to prevent cascading failures and improve
system resilience. Each external dependency (DeepSeek API, Perplexity API, MCP Server)
gets its own circuit breaker that monitors failures and automatically stops requests
during outages.

Circuit States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failure threshold exceeded, requests immediately fail
- HALF_OPEN: Testing recovery, limited requests pass through

Phase 1 Implementation - Week 1
Part of autonomous multi-agent self-improvement initiative.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from loguru import logger
import pybreaker


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker"""
    name: str
    fail_max: int = 5  # Number of failures before opening
    timeout_duration: int = 60  # Seconds before trying half-open
    expected_exception: type = Exception
    
    # Metrics
    total_calls: int = 0
    failed_calls: int = 0
    successful_calls: int = 0
    total_trips: int = 0  # Number of times circuit opened
    last_trip_time: Optional[datetime] = None
    current_state: CircuitState = CircuitState.CLOSED


@dataclass
class CircuitBreakerMetrics:
    """Metrics for all circuit breakers"""
    breakers: Dict[str, CircuitBreakerConfig] = field(default_factory=dict)
    total_calls: int = 0
    total_failures: int = 0
    total_trips: int = 0
    
    def to_dict(self) -> dict:
        """Convert metrics to dictionary"""
        return {
            "breakers": {
                name: {
                    "state": config.current_state.value,
                    "total_calls": config.total_calls,
                    "failed_calls": config.failed_calls,
                    "successful_calls": config.successful_calls,
                    "total_trips": config.total_trips,
                    "last_trip_time": config.last_trip_time.isoformat() if config.last_trip_time else None
                }
                for name, config in self.breakers.items()
            },
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_trips": self.total_trips
        }


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreakerListener:
    """Listener for circuit breaker state changes"""
    
    def __init__(self, name: str, on_state_change_callback: Callable):
        self.name = name
        self.callback = on_state_change_callback
    
    def before_call(self, breaker, func, *args, **kwargs):
        """Called before function execution"""
        pass
    
    def success(self, breaker):
        """Called on successful execution"""
        pass
    
    def failure(self, breaker, exception):
        """Called on failed execution"""
        pass
    
    def state_change(self, breaker, old_state, new_state):
        """Called when state changes"""
        self.callback(breaker, old_state, new_state)


class AgentCircuitBreakerManager:
    """
    Manages circuit breakers for all AI agent external dependencies.
    
    Each agent type (DeepSeek, Perplexity) and MCP Server gets its own circuit breaker
    to isolate failures and prevent cascading issues.
    
    Usage:
        manager = get_circuit_manager()
        
        # Register a circuit breaker
        manager.register_breaker("deepseek_api", fail_max=5, timeout_duration=60)
        
        # Call with circuit breaker protection
        result = await manager.call_with_breaker(
            "deepseek_api",
            async_func,
            *args,
            **kwargs
        )
    """
    
    def __init__(self):
        self._breakers: Dict[str, pybreaker.CircuitBreaker] = {}
        self._configs: Dict[str, CircuitBreakerConfig] = {}
        self._lock = asyncio.Lock()
        logger.info("🛡️ Circuit Breaker Manager initialized")
    
    def register_breaker(
        self,
        name: str,
        fail_max: int = 5,
        timeout_duration: int = 60,
        expected_exception: type = Exception
    ) -> None:
        """
        Register a new circuit breaker for a component.
        
        Args:
            name: Unique name for the circuit breaker (e.g., "deepseek_api")
            fail_max: Number of consecutive failures before opening circuit
            timeout_duration: Seconds to wait before attempting recovery (half-open)
            expected_exception: Exception type to catch (default: Exception)
        """
        if name in self._breakers:
            logger.warning(f"Circuit breaker '{name}' already registered, skipping")
            return
        
        # Create configuration
        config = CircuitBreakerConfig(
            name=name,
            fail_max=fail_max,
            timeout_duration=timeout_duration,
            expected_exception=expected_exception
        )
        self._configs[name] = config
        
        # Create pybreaker instance
        breaker = pybreaker.CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=timeout_duration,  # pybreaker uses 'reset_timeout' parameter
            name=name
        )
        
        # Add state change listener
        listener = CircuitBreakerListener(name, self._on_state_change_callback(name))
        breaker.add_listener(listener)
        
        self._breakers[name] = breaker
        logger.info(
            f"✅ Circuit breaker '{name}' registered "
            f"(fail_max={fail_max}, timeout={timeout_duration}s)"
        )
    
    def _on_state_change_callback(self, name: str) -> Callable:
        """Create state change callback for a circuit breaker"""
        def callback(breaker: pybreaker.CircuitBreaker, old_state: pybreaker.CircuitBreakerState, new_state: pybreaker.CircuitBreakerState):
            config = self._configs.get(name)
            if not config:
                return
            
            # Map pybreaker states to our enum
            state_map = {
                pybreaker.STATE_CLOSED: CircuitState.CLOSED,
                pybreaker.STATE_OPEN: CircuitState.OPEN,
                pybreaker.STATE_HALF_OPEN: CircuitState.HALF_OPEN
            }
            
            config.current_state = state_map.get(new_state, CircuitState.CLOSED)
            
            # Track trips (transitions to OPEN)
            if new_state == pybreaker.STATE_OPEN:
                config.total_trips += 1
                config.last_trip_time = datetime.now(timezone.utc)
                logger.warning(
                    f"⚠️ Circuit breaker '{name}' OPENED "
                    f"(trip #{config.total_trips}, will retry in {config.timeout_duration}s)"
                )
            elif new_state == pybreaker.STATE_HALF_OPEN:
                logger.info(f"🔄 Circuit breaker '{name}' HALF-OPEN (testing recovery)")
            elif new_state == pybreaker.STATE_CLOSED:
                if old_state != pybreaker.STATE_CLOSED:
                    logger.info(f"✅ Circuit breaker '{name}' CLOSED (recovered)")
        
        return callback
    
    async def call_with_breaker(
        self,
        breaker_name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function protected by a circuit breaker.
        
        Args:
            breaker_name: Name of the registered circuit breaker
            func: Async function to execute
            *args, **kwargs: Arguments to pass to the function
        
        Returns:
            Result from the function
        
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from the function
        """
        if breaker_name not in self._breakers:
            logger.error(f"Circuit breaker '{breaker_name}' not registered")
            raise ValueError(f"Unknown circuit breaker: {breaker_name}")
        
        breaker = self._breakers[breaker_name]
        config = self._configs[breaker_name]
        
        # Check if circuit is open
        if breaker.current_state == pybreaker.STATE_OPEN:
            config.failed_calls += 1
            logger.warning(
                f"🚫 Circuit breaker '{breaker_name}' is OPEN, "
                f"rejecting request"
            )
            raise CircuitBreakerError(
                f"Circuit breaker '{breaker_name}' is open. "
                f"Service unavailable, will retry later."
            )
        
        # Execute with circuit breaker protection
        config.total_calls += 1
        
        try:
            # pybreaker requires decorating a function, so we create a wrapper
            @breaker
            def _sync_wrapper():
                # For async functions, we need to return the coroutine
                return func(*args, **kwargs)
            
            # Call the wrapped function and await if it's a coroutine
            result = _sync_wrapper()
            if asyncio.iscoroutine(result):
                result = await result
            
            config.successful_calls += 1
            return result
        
        except pybreaker.CircuitBreakerError as e:
            # Circuit opened during this call
            config.failed_calls += 1
            logger.error(f"❌ Circuit breaker '{breaker_name}' tripped during call: {e}")
            raise CircuitBreakerError(str(e)) from e
        
        except Exception as e:
            # Function failed, circuit breaker will track it
            config.failed_calls += 1
            logger.error(f"❌ Call failed through circuit breaker '{breaker_name}': {e}")
            raise
    
    def get_breaker_state(self, name: str) -> Optional[CircuitState]:
        """Get current state of a circuit breaker"""
        config = self._configs.get(name)
        return config.current_state if config else None
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get metrics for all circuit breakers"""
        metrics = CircuitBreakerMetrics(
            breakers=self._configs.copy(),
            total_calls=sum(c.total_calls for c in self._configs.values()),
            total_failures=sum(c.failed_calls for c in self._configs.values()),
            total_trips=sum(c.total_trips for c in self._configs.values())
        )
        return metrics
    
    def reset_breaker(self, name: str) -> bool:
        """
        Manually reset a circuit breaker (for testing/recovery).
        
        Args:
            name: Circuit breaker name
        
        Returns:
            True if reset successful
        """
        if name not in self._breakers:
            logger.error(f"Circuit breaker '{name}' not found")
            return False
        
        breaker = self._breakers[name]
        config = self._configs[name]
        
        # Reset pybreaker state
        breaker.call(lambda: None)  # Dummy successful call
        config.current_state = CircuitState.CLOSED
        
        logger.info(f"🔄 Circuit breaker '{name}' manually reset to CLOSED")
        return True
    
    def get_all_breakers(self) -> List[str]:
        """Get list of all registered circuit breaker names"""
        return list(self._breakers.keys())


# Global singleton instance
_circuit_manager: Optional[AgentCircuitBreakerManager] = None


def get_circuit_manager() -> AgentCircuitBreakerManager:
    """
    Get the global circuit breaker manager singleton.
    
    Returns:
        AgentCircuitBreakerManager instance
    """
    global _circuit_manager
    if _circuit_manager is None:
        _circuit_manager = AgentCircuitBreakerManager()
    return _circuit_manager
