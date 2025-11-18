"""
Rate Limiter - Token bucket rate limiting for API endpoints
Prevents abuse and ensures fair usage
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger('security.rate_limiter')


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10  # Allow short bursts


class TokenBucket:
    """
    Token bucket algorithm implementation.
    
    Allows:
    - Steady rate with burst capacity
    - Configurable refill rate
    - Per-user/per-endpoint limits
    """
    
    def __init__(self, rate: float, capacity: int):
        """
        Initialize token bucket.
        
        Args:
            rate: Tokens per second refill rate
            capacity: Maximum bucket capacity (burst size)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Get time to wait until tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Wait time in seconds (0 if tokens available)
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        needed = tokens - self.tokens
        return needed / self.rate


class RateLimiter:
    """
    Multi-tier rate limiter with per-user and per-endpoint limits.
    
    Features:
    - Per-minute, per-hour, per-day limits
    - User-specific limits
    - Endpoint-specific limits
    - Token bucket algorithm (smooth rate limiting)
    - Automatic cleanup of old buckets
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        
        # Per-user buckets (user_id -> bucket)
        self._user_minute_buckets: Dict[str, TokenBucket] = {}
        self._user_hour_buckets: Dict[str, TokenBucket] = {}
        self._user_day_buckets: Dict[str, TokenBucket] = {}
        
        # Per-endpoint buckets (endpoint -> user_id -> bucket)
        self._endpoint_buckets: Dict[str, Dict[str, TokenBucket]] = defaultdict(dict)
        
        # Statistics
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._blocked_counts: Dict[str, int] = defaultdict(int)
    
    def _get_or_create_user_buckets(self, user_id: str) -> tuple:
        """Get or create token buckets for user"""
        if user_id not in self._user_minute_buckets:
            self._user_minute_buckets[user_id] = TokenBucket(
                rate=self.config.requests_per_minute / 60.0,  # per second
                capacity=self.config.burst_size
            )
        
        if user_id not in self._user_hour_buckets:
            self._user_hour_buckets[user_id] = TokenBucket(
                rate=self.config.requests_per_hour / 3600.0,
                capacity=self.config.burst_size * 5
            )
        
        if user_id not in self._user_day_buckets:
            self._user_day_buckets[user_id] = TokenBucket(
                rate=self.config.requests_per_day / 86400.0,
                capacity=self.config.burst_size * 10
            )
        
        return (
            self._user_minute_buckets[user_id],
            self._user_hour_buckets[user_id],
            self._user_day_buckets[user_id]
        )
    
    def check_rate_limit(
        self,
        user_id: str,
        endpoint: Optional[str] = None,
        cost: int = 1
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request is allowed under rate limits.
        
        Args:
            user_id: User identifier
            endpoint: Optional endpoint identifier for endpoint-specific limits
            cost: Request cost in tokens (default 1, expensive operations can cost more)
            
        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
        """
        self._request_counts[user_id] += 1
        
        # Get user buckets
        minute_bucket, hour_bucket, day_bucket = self._get_or_create_user_buckets(user_id)
        
        # Check minute limit
        if not minute_bucket.consume(cost):
            self._blocked_counts[user_id] += 1
            wait_time = minute_bucket.get_wait_time(cost)
            logger.warning(f"Rate limit exceeded for user {user_id}: minute limit, wait {wait_time:.1f}s")
            return False, f"Rate limit: {self.config.requests_per_minute} requests/minute. Wait {wait_time:.1f}s"
        
        # Check hour limit
        if not hour_bucket.consume(cost):
            self._blocked_counts[user_id] += 1
            wait_time = hour_bucket.get_wait_time(cost)
            logger.warning(f"Rate limit exceeded for user {user_id}: hour limit, wait {wait_time:.1f}s")
            return False, f"Rate limit: {self.config.requests_per_hour} requests/hour. Wait {wait_time:.1f}s"
        
        # Check day limit
        if not day_bucket.consume(cost):
            self._blocked_counts[user_id] += 1
            wait_time = day_bucket.get_wait_time(cost)
            logger.warning(f"Rate limit exceeded for user {user_id}: day limit, wait {wait_time:.1f}s")
            return False, f"Rate limit: {self.config.requests_per_day} requests/day. Wait {wait_time:.1f}s"
        
        # Check endpoint-specific limit if provided
        if endpoint:
            if user_id not in self._endpoint_buckets[endpoint]:
                # Endpoint-specific limits (stricter than global)
                self._endpoint_buckets[endpoint][user_id] = TokenBucket(
                    rate=self.config.requests_per_minute / 120.0,  # Half of global rate
                    capacity=self.config.burst_size // 2
                )
            
            endpoint_bucket = self._endpoint_buckets[endpoint][user_id]
            if not endpoint_bucket.consume(cost):
                self._blocked_counts[user_id] += 1
                wait_time = endpoint_bucket.get_wait_time(cost)
                logger.warning(f"Endpoint rate limit exceeded for user {user_id} on {endpoint}")
                return False, f"Endpoint rate limit for {endpoint}. Wait {wait_time:.1f}s"
        
        logger.debug(f"Rate limit check passed for user {user_id}")
        return True, None
    
    def get_user_stats(self, user_id: str) -> Dict:
        """
        Get rate limit statistics for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with statistics
        """
        minute_bucket, hour_bucket, day_bucket = self._get_or_create_user_buckets(user_id)
        
        return {
            "user_id": user_id,
            "total_requests": self._request_counts.get(user_id, 0),
            "blocked_requests": self._blocked_counts.get(user_id, 0),
            "limits": {
                "per_minute": self.config.requests_per_minute,
                "per_hour": self.config.requests_per_hour,
                "per_day": self.config.requests_per_day
            },
            "current_tokens": {
                "minute": int(minute_bucket.tokens),
                "hour": int(hour_bucket.tokens),
                "day": int(day_bucket.tokens)
            },
            "bucket_capacity": {
                "minute": minute_bucket.capacity,
                "hour": hour_bucket.capacity,
                "day": day_bucket.capacity
            }
        }
    
    def reset_user_limits(self, user_id: str) -> None:
        """
        Reset rate limits for user (admin function).
        
        Args:
            user_id: User identifier
        """
        self._user_minute_buckets.pop(user_id, None)
        self._user_hour_buckets.pop(user_id, None)
        self._user_day_buckets.pop(user_id, None)
        
        # Clear endpoint buckets
        for endpoint_buckets in self._endpoint_buckets.values():
            endpoint_buckets.pop(user_id, None)
        
        logger.info(f"Reset rate limits for user {user_id}")
    
    def get_global_stats(self) -> Dict:
        """
        Get global rate limiter statistics.
        
        Returns:
            Dict with global statistics
        """
        total_requests = sum(self._request_counts.values())
        total_blocked = sum(self._blocked_counts.values())
        
        return {
            "total_users": len(self._user_minute_buckets),
            "total_requests": total_requests,
            "total_blocked": total_blocked,
            "block_rate": (total_blocked / total_requests * 100) if total_requests > 0 else 0.0,
            "active_buckets": {
                "minute": len(self._user_minute_buckets),
                "hour": len(self._user_hour_buckets),
                "day": len(self._user_day_buckets),
                "endpoints": len(self._endpoint_buckets)
            }
        }
    
    def cleanup_old_buckets(self, inactive_seconds: int = 3600) -> int:
        """
        Clean up inactive buckets to free memory.
        
        Args:
            inactive_seconds: Remove buckets inactive for this many seconds
            
        Returns:
            Number of buckets removed
        """
        now = time.time()
        removed = 0
        
        # Clean minute buckets
        for user_id in list(self._user_minute_buckets.keys()):
            bucket = self._user_minute_buckets[user_id]
            if now - bucket.last_refill > inactive_seconds:
                del self._user_minute_buckets[user_id]
                removed += 1
        
        # Clean hour buckets
        for user_id in list(self._user_hour_buckets.keys()):
            bucket = self._user_hour_buckets[user_id]
            if now - bucket.last_refill > inactive_seconds:
                del self._user_hour_buckets[user_id]
                removed += 1
        
        # Clean day buckets
        for user_id in list(self._user_day_buckets.keys()):
            bucket = self._user_day_buckets[user_id]
            if now - bucket.last_refill > inactive_seconds:
                del self._user_day_buckets[user_id]
                removed += 1
        
        logger.info(f"Cleaned up {removed} inactive buckets")
        return removed
