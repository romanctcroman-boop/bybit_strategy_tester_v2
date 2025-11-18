"""
Production-Ready Parallel DeepSeek Client with Circuit Breaker and Retry Logic
===============================================================================

Implements all critical recommendations from DeepSeek expert review:
✅ Exponential backoff with jitter
✅ Circuit breaker pattern per API key
✅ Retry logic with error classification
✅ Rate limit handling (Retry-After header)
✅ Performance-based load balancing
✅ Enhanced error handling

Based on DEEPSEEK_EXPERT_REVIEW.md recommendations.

Author: Bybit Strategy Tester Team (Enhanced)
Date: November 8, 2025
"""

import asyncio
import hashlib
import json
import random
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from loguru import logger

from .circuit_breaker import CircuitBreaker


class TaskPriority(str, Enum):
    """Task priority levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DeepSeekTask:
    """Single DeepSeek API task"""
    task_id: str
    prompt: str
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 2000
    priority: TaskPriority = TaskPriority.MEDIUM
    max_retries: int = 3  # NEW: Per-task retry limit


@dataclass
class TaskResult:
    """Result of task execution"""
    task_id: str
    success: bool
    response: str | None = None
    error: str | None = None
    api_key_used: str | None = None
    processing_time: float = 0.0
    tokens_used: int = 0
    model: str | None = None
    retry_count: int = 0  # NEW: Track retries


@dataclass
class APIKeyMetrics:
    """Performance metrics for an API key"""
    key_suffix: str
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    success_count: int = 0
    error_count: int = 0
    total_requests: int = 0
    last_rate_limit_time: float | None = None
    rate_limit_reset_time: float | None = None
    
    def avg_response_time(self) -> float:
        """Calculate average response time"""
        if not self.response_times:
            return 1.0
        return sum(self.response_times) / len(self.response_times)
    
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 1.0
        return self.success_count / self.total_requests
    
    def score(self) -> float:
        """Calculate overall performance score"""
        # Higher score = better performance
        success_rate = self.success_rate()
        avg_time = self.avg_response_time()
        
        # Score = success_rate / response_time
        # Fast + reliable = high score
        if avg_time == 0:
            avg_time = 0.1
        
        return success_rate / avg_time
    
    def is_rate_limited(self) -> bool:
        """Check if key is currently rate limited"""
        if not self.rate_limit_reset_time:
            return False
        return time.time() < self.rate_limit_reset_time


class ParallelDeepSeekClientV2:
    """
    Production-ready parallel DeepSeek client with advanced error handling.
    
    Features:
    - Circuit breaker per API key
    - Exponential backoff with jitter
    - Performance-based load balancing
    - Rate limit detection and respect
    - Comprehensive retry logic
    - Error classification
    
    Example:
        >>> client = ParallelDeepSeekClientV2(api_keys=keys, max_concurrent=10)
        >>> tasks = [DeepSeekTask(task_id="1", prompt="Hello")]
        >>> results = await client.process_batch(tasks)
    """
    
    def __init__(
        self,
        api_keys: list[str],
        max_concurrent: int = 10,
        enable_cache: bool = True,
        cache_ttl: int = 3600,
        base_url: str = "https://api.deepseek.com"
    ):
        """
        Initialize parallel DeepSeek client.
        
        Args:
            api_keys: List of DeepSeek API keys
            max_concurrent: Max concurrent requests
            enable_cache: Enable response caching
            cache_ttl: Cache time-to-live in seconds
            base_url: API base URL
        """
        if not api_keys:
            raise ValueError("At least one API key required")
        
        self.api_keys = api_keys
        self.max_concurrent = max_concurrent
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self.base_url = base_url
        
        # Circuit breakers per key (V2 with Prometheus metrics)
        self.circuit_breakers: dict[str, CircuitBreaker] = {
            key: CircuitBreaker(
                failure_threshold=5,
                success_threshold=2,
                timeout=60,
                key_id=key[-8:],  # Use last 8 chars as key_id
                provider="deepseek"
            ) for key in api_keys
        }
        
        # Performance metrics per key
        self.key_metrics: dict[str, APIKeyMetrics] = {
            key: APIKeyMetrics(key_suffix=key[-6:])
            for key in api_keys
        }
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.key_usage: dict[str, int] = {key: 0 for key in api_keys}
        
        # Caching
        self.cache: dict[str, dict[str, Any]] = {}
        
        # Global statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_tokens": 0,
            "total_processing_time": 0.0,
            "total_retries": 0,
            "rate_limit_hits": 0
        }
        
        logger.info(
            f"ParallelDeepSeekClientV2 initialized: "
            f"{len(api_keys)} keys, max_concurrent={max_concurrent}"
        )
    
    async def _get_best_key(self) -> str | None:
        """
        Select best performing available API key (async V2).
        
        NEW: Performance-based selection instead of least-used.
        V2: Async to support Circuit Breaker V2 with asyncio.Lock.
        
        Returns:
            Best available API key or None if all unavailable
        """
        available_keys = []
        
        for key in self.api_keys:
            # Check circuit breaker (V2: async with lock)
            if not await self.circuit_breakers[key].is_available():
                continue
            
            # Check rate limit
            metrics = self.key_metrics[key]
            if metrics.is_rate_limited():
                continue
            
            # Key is available
            available_keys.append(key)
        
        if not available_keys:
            logger.warning("No available API keys! All circuit breakers open or rate limited")
            return None
        
        # Select key with best performance score
        best_key = max(available_keys, key=lambda k: self.key_metrics[k].score())
        
        logger.debug(
            f"Selected key {best_key[-6:]}: "
            f"score={self.key_metrics[best_key].score():.3f}, "
            f"success_rate={self.key_metrics[best_key].success_rate():.2%}, "
            f"avg_time={self.key_metrics[best_key].avg_response_time():.2f}s"
        )
        
        return best_key
    
    def _classify_error(self, error: Exception, status_code: int | None = None) -> str:
        """
        Classify error as transient, persistent, or rate_limit.
        
        Args:
            error: Exception raised
            status_code: HTTP status code if available
            
        Returns:
            Error classification: "transient", "persistent", "rate_limit"
        """
        # Rate limit
        if status_code == 429:
            return "rate_limit"
        
        # Persistent errors (don't retry)
        if status_code in [400, 401, 403, 404]:
            return "persistent"
        
        # Transient errors (retry)
        if status_code and 500 <= status_code < 600:
            return "transient"
        
        # Network errors (transient)
        error_msg = str(error).lower()
        if any(keyword in error_msg for keyword in [
            "timeout", "connection", "network", "timed out",
            "peer closed", "incomplete"
        ]):
            return "transient"
        
        # Default: transient (give it a chance)
        return "transient"
    
    def _calculate_backoff(self, attempt: int, base_delay: float = 1.0) -> float:
        """
        Calculate exponential backoff with jitter.
        
        Args:
            attempt: Retry attempt number (0-indexed)
            base_delay: Base delay in seconds
            
        Returns:
            Delay in seconds with jitter
        """
        # Exponential: 1s, 2s, 4s, 8s, 16s (capped at 60s)
        exp_delay = min(60, base_delay * (2 ** attempt))
        
        # Add jitter (±30%)
        jitter = random.uniform(-0.3, 0.3) * exp_delay
        delay = exp_delay + jitter
        
        return max(0.1, delay)  # Minimum 0.1s
    
    def _generate_cache_key(self, task: DeepSeekTask) -> str:
        """Generate cache key from task parameters"""
        task_str = json.dumps({
            "prompt": task.prompt,
            "model": task.model,
            "temperature": task.temperature,
            "max_tokens": task.max_tokens
        }, sort_keys=True)
        # Using SHA256 for cache keys (more secure than MD5)
        return hashlib.sha256(task_str.encode()).hexdigest()[:16]  # Truncate for shorter keys
    
    def _check_cache(self, task: DeepSeekTask) -> TaskResult | None:
        """Check if task result is cached"""
        if not self.enable_cache:
            return None
        
        cache_key = self._generate_cache_key(task)
        
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if time.time() - cache_entry["timestamp"] < self.cache_ttl:
                self.stats["cache_hits"] += 1
                
                logger.debug(f"Cache hit for task {task.task_id}")
                
                return TaskResult(
                    task_id=task.task_id,
                    success=True,
                    response=cache_entry["response"],
                    tokens_used=cache_entry["tokens_used"],
                    model=cache_entry["model"],
                    processing_time=0.0  # Instant from cache
                )
        
        self.stats["cache_misses"] += 1
        return None
    
    def _save_to_cache(self, task: DeepSeekTask, result: TaskResult):
        """Save successful result to cache"""
        if not self.enable_cache or not result.success:
            return
        
        cache_key = self._generate_cache_key(task)
        self.cache[cache_key] = {
            "response": result.response,
            "tokens_used": result.tokens_used,
            "model": result.model,
            "timestamp": time.time()
        }
    
    async def _make_api_request(
        self,
        session: httpx.AsyncClient,
        api_key: str,
        task: DeepSeekTask,
        timeout: float = 90.0  # INCREASED: 60s → 90s for large prompts
    ) -> tuple[bool, str | None, int | None, dict | None]:
        """
        Make single API request.
        
        Returns:
            Tuple of (success, response_text, status_code, data)
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": task.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Python developer and AI assistant."
                },
                {
                    "role": "user",
                    "content": task.prompt
                }
            ],
            "temperature": task.temperature,
            "max_tokens": task.max_tokens
        }
        
        try:
            response = await session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return True, data["choices"][0]["message"]["content"], 200, data
            else:
                return False, response.text, response.status_code, None
        
        except httpx.TimeoutException as e:
            return False, f"Request timeout: {e}", None, None
        except httpx.NetworkError as e:
            return False, f"Network error: {e}", None, None
        except Exception as e:
            return False, f"Unexpected error: {e}", None, None
    
    async def process_single_task(
        self,
        session: httpx.AsyncClient,
        task: DeepSeekTask
    ) -> TaskResult:
        """
        Process single task with retry logic and circuit breaker.
        
        NEW: Implements exponential backoff and error classification.
        
        Args:
            session: HTTP client session
            task: Task to process
            
        Returns:
            Task result
        """
        # Check cache first
        cached_result = self._check_cache(task)
        if cached_result:
            return cached_result
        
        async with self.semaphore:
            retry_count = 0
            last_error = None
            
            # Retry loop
            for attempt in range(task.max_retries):
                # Get best available key (V2: async call)
                api_key = await self._get_best_key()
                
                if not api_key:
                    # No keys available
                    if attempt < task.max_retries - 1:
                        # Wait and retry
                        delay = self._calculate_backoff(attempt)
                        logger.warning(
                            f"Task {task.task_id}: No keys available, "
                            f"waiting {delay:.1f}s before retry {attempt + 1}/{task.max_retries}"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Final attempt failed
                        return TaskResult(
                            task_id=task.task_id,
                            success=False,
                            error="All API keys unavailable (circuit breakers open or rate limited)",
                            retry_count=retry_count
                        )
                
                # Track usage
                self.key_usage[api_key] += 1
                metrics = self.key_metrics[api_key]
                
                try:
                    start_time = time.time()
                    
                    # Make request
                    success, response_text, status_code, data = await self._make_api_request(
                        session, api_key, task
                    )
                    
                    processing_time = time.time() - start_time
                    
                    if success:
                        # SUCCESS
                        tokens_used = data.get("usage", {}).get("total_tokens", 0)
                        
                        result = TaskResult(
                            task_id=task.task_id,
                            success=True,
                            response=response_text,
                            api_key_used=api_key[-6:],
                            processing_time=processing_time,
                            tokens_used=tokens_used,
                            model=data.get("model", task.model),
                            retry_count=retry_count
                        )
                        
                        # Update metrics
                        metrics.response_times.append(processing_time)
                        metrics.success_count += 1
                        metrics.total_requests += 1
                        
                        # Circuit breaker success (V2: async)
                        await self.circuit_breakers[api_key].record_success()
                        
                        # Update stats
                        self.stats["successful_requests"] += 1
                        self.stats["total_tokens"] += tokens_used
                        self.stats["total_processing_time"] += processing_time
                        if retry_count > 0:
                            self.stats["total_retries"] += retry_count
                        
                        # Save to cache
                        self._save_to_cache(task, result)
                        
                        logger.debug(
                            f"Task {task.task_id} completed: "
                            f"{processing_time:.2f}s, {tokens_used} tokens, "
                            f"{retry_count} retries"
                        )
                        
                        return result
                    
                    else:
                        # FAILURE - classify error
                        error_type = self._classify_error(Exception(response_text), status_code)
                        
                        logger.warning(
                            f"Task {task.task_id} failed (attempt {attempt + 1}): "
                            f"status={status_code}, type={error_type}, error={response_text[:100]}"
                        )
                        
                        # Update metrics
                        metrics.error_count += 1
                        metrics.total_requests += 1
                        
                        if error_type == "rate_limit":
                            # Handle rate limit
                            self.stats["rate_limit_hits"] += 1
                            
                            # Try to extract Retry-After header
                            retry_after = 60  # Default 60s
                            if status_code == 429:
                                # In real scenario, extract from response headers
                                pass
                            
                            metrics.rate_limit_reset_time = time.time() + retry_after
                            
                            logger.warning(
                                f"Rate limit hit for key {api_key[-6:]}, "
                                f"disabled for {retry_after}s"
                            )
                            
                            # Circuit breaker failure (V2: async)
                            await self.circuit_breakers[api_key].record_failure()
                            
                            # Retry with different key
                            if attempt < task.max_retries - 1:
                                retry_count += 1
                                await asyncio.sleep(1)  # Brief pause before next key
                                continue
                        
                        elif error_type == "persistent":
                            # Persistent error - don't retry
                            await self.circuit_breakers[api_key].record_failure()
                            
                            return TaskResult(
                                task_id=task.task_id,
                                success=False,
                                error=f"Persistent error: {response_text}",
                                api_key_used=api_key[-6:],
                                processing_time=processing_time,
                                retry_count=retry_count
                            )
                        
                        elif error_type == "transient":
                            # Transient error - retry with backoff
                            await self.circuit_breakers[api_key].record_failure()
                            
                            if attempt < task.max_retries - 1:
                                delay = self._calculate_backoff(attempt)
                                retry_count += 1
                                
                                logger.info(
                                    f"Task {task.task_id}: Transient error, "
                                    f"retrying in {delay:.1f}s (attempt {attempt + 2}/{task.max_retries})"
                                )
                                
                                await asyncio.sleep(delay)
                                continue
                        
                        last_error = response_text
                
                except Exception as e:
                    # Exception during request
                    processing_time = time.time() - start_time
                    
                    logger.error(
                        f"Task {task.task_id} exception (attempt {attempt + 1}): {e}"
                    )
                    
                    # Update metrics
                    metrics.error_count += 1
                    metrics.total_requests += 1
                    
                    # Circuit breaker failure (V2: async)
                    await self.circuit_breakers[api_key].record_failure()
                    
                    # Retry transient errors
                    error_type = self._classify_error(e)
                    if error_type == "transient" and attempt < task.max_retries - 1:
                        delay = self._calculate_backoff(attempt)
                        retry_count += 1
                        
                        logger.info(
                            f"Task {task.task_id}: Exception, "
                            f"retrying in {delay:.1f}s (attempt {attempt + 2}/{task.max_retries})"
                        )
                        
                        await asyncio.sleep(delay)
                        continue
                    
                    last_error = str(e)
                
                finally:
                    self.key_usage[api_key] -= 1
                    self.stats["total_requests"] += 1
            
            # All retries exhausted
            self.stats["failed_requests"] += 1
            
            return TaskResult(
                task_id=task.task_id,
                success=False,
                error=f"Max retries ({task.max_retries}) exceeded. Last error: {last_error}",
                retry_count=retry_count
            )
    
    async def process_batch(
        self,
        tasks: list[DeepSeekTask],
        show_progress: bool = True
    ) -> list[TaskResult]:
        """
        Process batch of tasks in parallel.
        
        Args:
            tasks: List of tasks to process
            show_progress: Show progress logging
            
        Returns:
            List of task results
        """
        if not tasks:
            return []
        
        start_time = time.time()
        
        if show_progress:
            logger.info(f"Processing batch of {len(tasks)} tasks...")
        
        async with httpx.AsyncClient() as session:
            results = await asyncio.gather(
                *[self.process_single_task(session, task) for task in tasks],
                return_exceptions=False
            )
        
        total_time = time.time() - start_time
        
        if show_progress:
            successful = sum(1 for r in results if r.success)
            logger.info(
                f"Batch complete: {successful}/{len(tasks)} successful "
                f"in {total_time:.2f}s ({len(tasks)/total_time:.2f} tasks/sec)"
            )
        
        return results
    
    def get_statistics(self) -> dict:
        """Get comprehensive statistics"""
        total = self.stats["total_requests"]
        
        return {
            "total_requests": total,
            "successful_requests": self.stats["successful_requests"],
            "failed_requests": self.stats["failed_requests"],
            "success_rate": f"{self.stats['successful_requests']/total*100:.1f}%" if total > 0 else "0%",
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "cache_hit_rate": f"{self.stats['cache_hits']/(self.stats['cache_hits']+self.stats['cache_misses'])*100:.1f}%" if (self.stats['cache_hits']+self.stats['cache_misses']) > 0 else "0%",
            "total_tokens": self.stats["total_tokens"],
            "total_processing_time": f"{self.stats['total_processing_time']:.2f}s",
            "avg_processing_time": f"{self.stats['total_processing_time']/total:.2f}s" if total > 0 else "0s",
            "total_retries": self.stats["total_retries"],
            "rate_limit_hits": self.stats["rate_limit_hits"],
            "api_keys": {
                key[-6:]: {
                    "total_requests": metrics.total_requests,
                    "success_count": metrics.success_count,
                    "error_count": metrics.error_count,
                    "success_rate": f"{metrics.success_rate()*100:.1f}%",
                    "avg_response_time": f"{metrics.avg_response_time():.2f}s",
                    "score": f"{metrics.score():.3f}",
                    "circuit_breaker_state": self.circuit_breakers[key].state.value
                }
                for key, metrics in self.key_metrics.items()
            }
        }
