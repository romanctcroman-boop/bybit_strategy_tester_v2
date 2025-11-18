"""
Request Deduplication System

Prevents duplicate in-flight requests by:
- Tracking active requests by unique key
- Coalescing identical concurrent requests
- Returning shared result to all waiters
- Handling request failures and retries
- TTL-based cleanup of stale entries

Architecture:
- Request Key: Hash of (endpoint, method, params)
- Shared Futures: Multiple callers wait on same Future
- Result Broadcasting: One fetch, many receivers
- Error Handling: Failure propagated to all waiters
- Memory Management: Auto-cleanup after completion

Usage:
    deduplicator = RequestDeduplicator()
    
    # Multiple concurrent identical requests
    results = await asyncio.gather(
        deduplicator.deduplicate("api_call", fetch_func),
        deduplicator.deduplicate("api_call", fetch_func),
        deduplicator.deduplicate("api_call", fetch_func)
    )
    # Only 1 actual fetch executed, result shared with all 3
    
    # With custom key generation
    key = deduplicator.generate_key(
        endpoint="/api/users",
        method="GET",
        params={"id": 123}
    )
    result = await deduplicator.deduplicate(key, fetch_func)

Phase 3, Day 19-20
Target: 25+ tests, >90% coverage
"""

import asyncio
import hashlib
import json
import time
import logging
from typing import Any, Callable, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RequestStatus(Enum):
    """Request lifecycle status"""
    PENDING = "pending"       # Request in flight
    COMPLETED = "completed"   # Successfully completed
    FAILED = "failed"         # Failed with error
    CANCELLED = "cancelled"   # Cancelled by client


@dataclass
class RequestState:
    """State of a deduplicated request
    
    Attributes:
        key: Unique request identifier
        future: Shared future for result
        waiter_count: Number of callers waiting
        status: Current request status
        created_at: Timestamp when created
        completed_at: Timestamp when completed (if finished)
        result: Cached result (if successful)
        error: Error object (if failed)
    """
    key: str
    future: asyncio.Future
    waiter_count: int = 0
    status: RequestStatus = RequestStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[Exception] = None


@dataclass
class DeduplicationConfig:
    """Configuration for request deduplication
    
    Attributes:
        max_pending_requests: Max concurrent deduplicated requests (0 = unlimited)
        request_ttl: Max time request can be pending before timeout (seconds)
        cleanup_interval: Interval for cleaning up completed requests (seconds)
        enable_metrics: Enable metrics collection
        hash_algorithm: Algorithm for key hashing (md5, sha256)
    """
    max_pending_requests: int = 1000
    request_ttl: int = 30
    cleanup_interval: int = 60
    enable_metrics: bool = True
    hash_algorithm: str = "md5"


@dataclass
class DeduplicationStats:
    """Deduplication statistics
    
    Attributes:
        total_requests: Total requests received
        deduplicated_requests: Requests that were deduplicated
        unique_requests: Unique requests executed
        active_requests: Currently pending requests
        completed_requests: Successfully completed
        failed_requests: Failed requests
        cancelled_requests: Cancelled requests
        timeouts: Requests that timed out
    """
    total_requests: int = 0
    deduplicated_requests: int = 0
    unique_requests: int = 0
    active_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    cancelled_requests: int = 0
    timeouts: int = 0
    
    @property
    def deduplication_rate(self) -> float:
        """Calculate deduplication rate (% of requests deduplicated)"""
        if self.total_requests == 0:
            return 0.0
        return self.deduplicated_requests / self.total_requests


class RequestDeduplicator:
    """Request deduplication system
    
    Prevents duplicate concurrent requests by tracking in-flight
    requests and coalescing identical calls.
    
    Features:
    - Automatic request coalescing
    - Shared result broadcasting
    - Error propagation to all waiters
    - TTL-based timeout
    - Automatic cleanup
    - Metrics tracking
    """
    
    def __init__(
        self,
        config: Optional[DeduplicationConfig] = None,
        enable_metrics: bool = True
    ):
        """Initialize request deduplicator
        
        Args:
            config: Deduplication configuration
            enable_metrics: Enable metrics collection
        """
        self.config = config or DeduplicationConfig()
        self.enable_metrics = enable_metrics
        
        # Active requests: key -> RequestState
        self._requests: Dict[str, RequestState] = {}
        
        # Lock for thread-safe access
        self._lock = asyncio.Lock()
        
        # Stats
        self.stats = DeduplicationStats()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(
            f"Request deduplicator initialized: "
            f"max_pending={self.config.max_pending_requests}, "
            f"ttl={self.config.request_ttl}s, "
            f"cleanup_interval={self.config.cleanup_interval}s"
        )
    
    def generate_key(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate unique request key
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            params: Query parameters
            body: Request body
            
        Returns:
            Unique request key (hash)
        """
        # Normalize params and body
        params_str = json.dumps(params or {}, sort_keys=True)
        body_str = json.dumps(body or {}, sort_keys=True)
        
        # Create key string
        key_data = f"{method}:{endpoint}:{params_str}:{body_str}"
        
        # Hash key
        if self.config.hash_algorithm == "sha256":
            hash_obj = hashlib.sha256(key_data.encode())
        else:
            hash_obj = hashlib.md5(key_data.encode())
        
        return hash_obj.hexdigest()
    
    async def deduplicate(
        self,
        key: str,
        fetch_func: Callable[[], Any],
        timeout: Optional[float] = None
    ) -> Any:
        """Deduplicate request by key
        
        If request with same key is already in flight, wait for its result.
        Otherwise, execute fetch_func and share result with concurrent callers.
        
        Args:
            key: Unique request key
            fetch_func: Function to fetch data (sync or async)
            timeout: Request timeout in seconds (uses config.request_ttl if None)
            
        Returns:
            Request result
            
        Raises:
            asyncio.TimeoutError: If request times out
            Exception: Any exception from fetch_func
        """
        timeout = timeout or self.config.request_ttl
        
        # Update stats
        if self.enable_metrics:
            self.stats.total_requests += 1
        
        # Check if request already exists
        async with self._lock:
            if key in self._requests:
                # Request already in flight - deduplicate!
                request_state = self._requests[key]
                request_state.waiter_count += 1
                
                if self.enable_metrics:
                    self.stats.deduplicated_requests += 1
                
                logger.debug(
                    f"Deduplicating request: key={key[:8]}..., "
                    f"waiters={request_state.waiter_count}"
                )
            else:
                # New unique request
                future = asyncio.Future()
                request_state = RequestState(
                    key=key,
                    future=future,
                    waiter_count=1
                )
                self._requests[key] = request_state
                
                if self.enable_metrics:
                    self.stats.unique_requests += 1
                    self.stats.active_requests += 1
                
                logger.debug(f"New unique request: key={key[:8]}...")
                
                # Execute fetch in background
                asyncio.create_task(self._execute_request(key, fetch_func))
        
        # Wait for result with timeout
        try:
            result = await asyncio.wait_for(
                request_state.future,
                timeout=timeout
            )
            return result
        
        except asyncio.TimeoutError:
            if self.enable_metrics:
                self.stats.timeouts += 1
            
            logger.warning(f"Request timeout: key={key[:8]}..., timeout={timeout}s")
            
            # Clean up timed out request
            async with self._lock:
                if key in self._requests:
                    self._requests[key].status = RequestStatus.FAILED
                    del self._requests[key]
            
            raise
        
        except Exception as e:
            # Error already logged in _execute_request
            raise
    
    async def _execute_request(
        self,
        key: str,
        fetch_func: Callable[[], Any]
    ):
        """Execute request and broadcast result to all waiters
        
        Args:
            key: Request key
            fetch_func: Function to fetch data
        """
        request_state = self._requests.get(key)
        if not request_state:
            return
        
        try:
            # Execute fetch function
            if asyncio.iscoroutinefunction(fetch_func):
                result = await fetch_func()
            else:
                result = fetch_func()
            
            # Mark as completed
            request_state.status = RequestStatus.COMPLETED
            request_state.completed_at = time.time()
            request_state.result = result
            
            # Set result on future (broadcasts to all waiters)
            if not request_state.future.done():
                request_state.future.set_result(result)
            
            if self.enable_metrics:
                self.stats.completed_requests += 1
                self.stats.active_requests -= 1
            
            duration = request_state.completed_at - request_state.created_at
            logger.debug(
                f"Request completed: key={key[:8]}..., "
                f"duration={duration:.3f}s, "
                f"waiters={request_state.waiter_count}"
            )
        
        except Exception as e:
            # Mark as failed
            request_state.status = RequestStatus.FAILED
            request_state.completed_at = time.time()
            request_state.error = e
            
            # Set exception on future (broadcasts to all waiters)
            if not request_state.future.done():
                request_state.future.set_exception(e)
            
            if self.enable_metrics:
                self.stats.failed_requests += 1
                self.stats.active_requests -= 1
            
            logger.error(
                f"Request failed: key={key[:8]}..., "
                f"error={type(e).__name__}: {e}"
            )
        
        finally:
            # Schedule cleanup
            asyncio.create_task(self._cleanup_request(key, delay=1.0))
    
    async def _cleanup_request(self, key: str, delay: float = 0.0):
        """Clean up completed request after delay
        
        Args:
            key: Request key to clean up
            delay: Delay before cleanup (seconds)
        """
        if delay > 0:
            await asyncio.sleep(delay)
        
        async with self._lock:
            if key in self._requests:
                request_state = self._requests[key]
                
                # Only cleanup if completed/failed and no active waiters
                if request_state.status in (RequestStatus.COMPLETED, RequestStatus.FAILED):
                    del self._requests[key]
                    
                    logger.debug(f"Cleaned up request: key={key[:8]}...")
    
    async def cancel_request(self, key: str) -> bool:
        """Cancel pending request
        
        Args:
            key: Request key to cancel
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        async with self._lock:
            if key not in self._requests:
                return False
            
            request_state = self._requests[key]
            
            if request_state.status != RequestStatus.PENDING:
                return False
            
            # Cancel future
            if not request_state.future.done():
                request_state.future.cancel()
            
            request_state.status = RequestStatus.CANCELLED
            
            if self.enable_metrics:
                self.stats.cancelled_requests += 1
                self.stats.active_requests -= 1
            
            # Clean up
            del self._requests[key]
            
            logger.debug(f"Cancelled request: key={key[:8]}...")
            
            return True
    
    async def cleanup_stale_requests(self):
        """Clean up stale/timed-out requests"""
        current_time = time.time()
        stale_keys = []
        
        async with self._lock:
            for key, request_state in self._requests.items():
                # Check if request is stale (exceeded TTL)
                if current_time - request_state.created_at > self.config.request_ttl:
                    stale_keys.append(key)
        
        # Clean up stale requests
        for key in stale_keys:
            await self.cancel_request(key)
            
            if self.enable_metrics:
                self.stats.timeouts += 1
        
        if stale_keys:
            logger.info(f"Cleaned up {len(stale_keys)} stale requests")
    
    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self._cleanup_task is not None:
            logger.warning("Cleanup task already running")
            return
        
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.cleanup_interval)
                    await self.cleanup_stale_requests()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Cleanup task error: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Cleanup task started")
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self._cleanup_task is None:
            return
        
        self._cleanup_task.cancel()
        
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass
        
        self._cleanup_task = None
        logger.info("Cleanup task stopped")
    
    def get_active_requests(self) -> Dict[str, RequestState]:
        """Get all active requests
        
        Returns:
            Dictionary of key -> RequestState
        """
        return self._requests.copy()
    
    def get_stats(self) -> DeduplicationStats:
        """Get deduplication statistics
        
        Returns:
            DeduplicationStats object
        """
        if not self.enable_metrics:
            return DeduplicationStats()
        
        # Update active count
        self.stats.active_requests = len(self._requests)
        
        return self.stats
    
    async def clear(self):
        """Clear all pending requests"""
        async with self._lock:
            # Cancel all pending futures
            for request_state in self._requests.values():
                if not request_state.future.done():
                    request_state.future.cancel()
            
            self._requests.clear()
        
        logger.info("All requests cleared")


class DeduplicationMiddleware:
    """Middleware for automatic request deduplication
    
    Wraps API client methods to automatically deduplicate requests.
    """
    
    def __init__(
        self,
        deduplicator: RequestDeduplicator,
        key_generator: Optional[Callable] = None
    ):
        """Initialize middleware
        
        Args:
            deduplicator: RequestDeduplicator instance
            key_generator: Custom key generation function (optional)
        """
        self.deduplicator = deduplicator
        self.key_generator = key_generator or deduplicator.generate_key
    
    async def __call__(
        self,
        endpoint: str,
        method: str,
        fetch_func: Callable,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Any:
        """Execute request with deduplication
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            fetch_func: Function to fetch data
            params: Query parameters
            body: Request body
            timeout: Request timeout
            
        Returns:
            Request result
        """
        # Generate key
        key = self.key_generator(
            endpoint=endpoint,
            method=method,
            params=params,
            body=body
        )
        
        # Deduplicate
        return await self.deduplicator.deduplicate(
            key=key,
            fetch_func=fetch_func,
            timeout=timeout
        )
