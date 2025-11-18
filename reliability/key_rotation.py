"""
API Key Rotation Strategy with Intelligent Health Tracking

Implements smart API key rotation based on:
- DeepSeek Agent: Weighted Priority Queue, exponential backoff (2^failures min)
- Perplexity Agent: Health tracking, rate limit detection, automatic failover

Features:
- Weighted Priority Queue: Healthy keys prioritized
- Health Tracking: Per-key success rate, failure count, last error
- Exponential Cooldown: 2^failures minutes (1m → 2m → 4m → 8m, max 64min)
- Rate Limit Handling: 5-minute cooldown for 429 errors
- Alerting: Warn when >50% keys are cooling down
- Fair Distribution: Gini coefficient < 0.2 target

Usage:
    from reliability.key_rotation import KeyRotation, KeyConfig
    
    # Initialize with API keys
    keys = [
        KeyConfig(id="key1", api_key="xxx", secret="yyy", weight=1.0),
        KeyConfig(id="key2", api_key="zzz", secret="www", weight=1.0),
    ]
    rotation = KeyRotation(keys)
    
    # Get next healthy key
    key = await rotation.get_next_key()
    
    # Report success/failure
    await rotation.report_success(key.id)
    await rotation.report_failure(key.id, error_type="rate_limit")
"""

import asyncio
import logging
import time
import heapq
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class KeyStatus(Enum):
    """API key health status"""
    HEALTHY = "healthy"           # Ready to use
    COOLING = "cooling"           # In cooldown after failure
    RATE_LIMITED = "rate_limited" # Hit rate limit (429)
    DEAD = "dead"                 # Permanently failed (too many errors)


@dataclass
class KeyConfig:
    """API key configuration
    
    Attributes:
        id: Unique identifier for this key
        api_key: API key string
        secret: API secret string
        weight: Priority weight (higher = preferred), default 1.0
        max_failures: Max failures before marking DEAD (default: 10)
    """
    id: str
    api_key: str
    secret: str
    weight: float = 1.0
    max_failures: int = 10


@dataclass
class KeyHealth:
    """Health tracking for an API key
    
    Tracks:
    - Success/failure counts
    - Last error details
    - Cooldown state
    - Usage statistics
    """
    key_id: str
    status: KeyStatus = KeyStatus.HEALTHY
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    last_used: Optional[float] = None
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None
    cooldown_until: Optional[float] = None
    rate_limit_until: Optional[float] = None
    
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 1.0
        return self.total_successes / self.total_requests
    
    def is_available(self) -> bool:
        """Check if key is available for use"""
        now = time.time()
        
        if self.status == KeyStatus.DEAD:
            return False
        
        if self.cooldown_until and now < self.cooldown_until:
            return False
        
        if self.rate_limit_until and now < self.rate_limit_until:
            return False
        
        return True
    
    def time_until_available(self) -> float:
        """Get seconds until key is available"""
        if self.status == KeyStatus.DEAD:
            return float('inf')
        
        now = time.time()
        wait_times = []
        
        if self.cooldown_until:
            wait_times.append(max(0, self.cooldown_until - now))
        
        if self.rate_limit_until:
            wait_times.append(max(0, self.rate_limit_until - now))
        
        return max(wait_times) if wait_times else 0.0


class KeyRotation:
    """Intelligent API key rotation with health tracking
    
    Uses weighted priority queue where priority = weight * success_rate * availability
    
    Features:
    - Automatic failover to healthy keys
    - Exponential backoff for failing keys (2^failures minutes)
    - Special handling for rate limits (5-minute cooldown)
    - Dead key detection (>10 consecutive failures)
    - Fair distribution tracking (Gini coefficient)
    
    Example:
        rotation = KeyRotation(keys)
        
        # Get next key
        key = await rotation.get_next_key()
        
        # Use key...
        try:
            result = await api_call(key.api_key)
            await rotation.report_success(key.id)
        except RateLimitError:
            await rotation.report_failure(key.id, error_type="rate_limit")
        except Exception as e:
            await rotation.report_failure(key.id, error_type="error")
    """
    
    def __init__(self, keys: List[KeyConfig]):
        """Initialize key rotation
        
        Args:
            keys: List of API key configurations
        """
        if not keys:
            raise ValueError("At least one API key required")
        
        self.keys = {k.id: k for k in keys}
        self.health = {k.id: KeyHealth(key_id=k.id) for k in keys}
        self._lock = asyncio.Lock()
        
        logger.info(f"Key rotation initialized with {len(keys)} keys")
    
    async def get_next_key(self, timeout: float = 30.0) -> KeyConfig:
        """Get next available healthy key
        
        Uses weighted priority queue:
        - Priority = weight * success_rate * (1 if available else 0)
        - Highest priority key selected
        
        Args:
            timeout: Max seconds to wait for available key
        
        Returns:
            Next available key
        
        Raises:
            RuntimeError: If no keys available within timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            async with self._lock:
                # Find best available key
                best_key = None
                best_priority = -1.0
                
                for key_id, key_config in self.keys.items():
                    health = self.health[key_id]
                    
                    if not health.is_available():
                        continue
                    
                    # Calculate priority
                    priority = (
                        key_config.weight *
                        health.success_rate() *
                        1.0  # Available bonus
                    )
                    
                    if priority > best_priority:
                        best_priority = priority
                        best_key = key_config
                
                if best_key:
                    # Mark as used
                    self.health[best_key.id].last_used = time.time()
                    logger.debug(
                        f"Selected key '{best_key.id}' with priority {best_priority:.3f}"
                    )
                    return best_key
            
            # No keys available, wait and retry
            await asyncio.sleep(0.5)
        
        # Timeout - check if ANY keys will become available
        min_wait = float('inf')
        for health in self.health.values():
            wait = health.time_until_available()
            if wait < min_wait:
                min_wait = wait
        
        if min_wait == float('inf'):
            raise RuntimeError("All API keys are DEAD - no recovery possible")
        
        raise RuntimeError(
            f"No API keys available within {timeout}s. "
            f"Next key available in {min_wait:.1f}s"
        )
    
    async def report_success(self, key_id: str):
        """Report successful API call
        
        Args:
            key_id: ID of key that succeeded
        """
        async with self._lock:
            health = self.health[key_id]
            health.total_requests += 1
            health.total_successes += 1
            health.consecutive_failures = 0  # Reset failure counter
            
            # Clear cooldowns on success
            if health.status == KeyStatus.COOLING:
                health.status = KeyStatus.HEALTHY
                health.cooldown_until = None
                logger.info(f"Key '{key_id}' recovered: now HEALTHY")
            
            logger.debug(
                f"Key '{key_id}' success: {health.total_successes}/{health.total_requests} "
                f"({health.success_rate():.1%})"
            )
    
    async def report_failure(
        self,
        key_id: str,
        error_type: str = "error",
        error_message: Optional[str] = None
    ):
        """Report failed API call
        
        Args:
            key_id: ID of key that failed
            error_type: Type of error ("rate_limit", "auth", "error")
            error_message: Optional error details
        """
        async with self._lock:
            health = self.health[key_id]
            health.total_requests += 1
            health.total_failures += 1
            health.consecutive_failures += 1
            health.last_error = error_message or error_type
            health.last_error_time = time.time()
            
            # Handle rate limit (429) - special 5-minute cooldown
            if error_type == "rate_limit":
                health.status = KeyStatus.RATE_LIMITED
                health.rate_limit_until = time.time() + 300  # 5 minutes
                logger.warning(
                    f"Key '{key_id}' rate limited: cooling for 5 minutes"
                )
            
            # Handle authentication errors - mark as DEAD
            elif error_type == "auth":
                health.status = KeyStatus.DEAD
                logger.error(f"Key '{key_id}' authentication failed: marked DEAD")
            
            # Handle other errors - exponential backoff
            else:
                # Check if key should be marked DEAD
                if health.consecutive_failures >= self.keys[key_id].max_failures:
                    health.status = KeyStatus.DEAD
                    logger.error(
                        f"Key '{key_id}' exceeded max failures "
                        f"({health.consecutive_failures}): marked DEAD"
                    )
                else:
                    # Apply exponential cooldown: 2^failures minutes
                    cooldown_minutes = 2 ** health.consecutive_failures
                    cooldown_minutes = min(cooldown_minutes, 64)  # Cap at 64 minutes
                    
                    health.status = KeyStatus.COOLING
                    health.cooldown_until = time.time() + (cooldown_minutes * 60)
                    
                    logger.warning(
                        f"Key '{key_id}' failed ({health.consecutive_failures} consecutive): "
                        f"cooling for {cooldown_minutes} minutes"
                    )
            
            # Check if >50% keys are cooling/dead - ALERT!
            self._check_key_health_alert()
    
    def _check_key_health_alert(self):
        """Check if too many keys are unhealthy and log alert"""
        total_keys = len(self.keys)
        unhealthy_keys = sum(
            1 for h in self.health.values()
            if h.status in (KeyStatus.COOLING, KeyStatus.RATE_LIMITED, KeyStatus.DEAD)
        )
        
        unhealthy_percentage = unhealthy_keys / total_keys
        
        if unhealthy_percentage > 0.5:
            available_keys = total_keys - unhealthy_keys
            logger.error(
                f"⚠️  ALERT: {unhealthy_percentage:.0%} of API keys are unhealthy! "
                f"Only {available_keys}/{total_keys} keys available"
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get key rotation metrics
        
        Returns:
            Dictionary with metrics:
            - total_keys: Total number of keys
            - healthy_keys: Number of HEALTHY keys
            - cooling_keys: Number of COOLING keys
            - rate_limited_keys: Number of RATE_LIMITED keys
            - dead_keys: Number of DEAD keys
            - avg_success_rate: Average success rate across all keys
            - gini_coefficient: Distribution fairness (0 = perfect, 1 = unfair)
        """
        total_keys = len(self.keys)
        healthy = sum(1 for h in self.health.values() if h.status == KeyStatus.HEALTHY)
        cooling = sum(1 for h in self.health.values() if h.status == KeyStatus.COOLING)
        rate_limited = sum(1 for h in self.health.values() if h.status == KeyStatus.RATE_LIMITED)
        dead = sum(1 for h in self.health.values() if h.status == KeyStatus.DEAD)
        
        # Calculate average success rate
        success_rates = [h.success_rate() for h in self.health.values()]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0
        
        # Calculate Gini coefficient (distribution fairness)
        gini = self._calculate_gini_coefficient()
        
        return {
            "total_keys": total_keys,
            "healthy_keys": healthy,
            "cooling_keys": cooling,
            "rate_limited_keys": rate_limited,
            "dead_keys": dead,
            "avg_success_rate": avg_success_rate,
            "gini_coefficient": gini,
            "per_key_stats": {
                key_id: {
                    "status": health.status.value,
                    "requests": health.total_requests,
                    "success_rate": health.success_rate(),
                    "consecutive_failures": health.consecutive_failures,
                    "time_until_available": health.time_until_available()
                }
                for key_id, health in self.health.items()
            }
        }
    
    def _calculate_gini_coefficient(self) -> float:
        """Calculate Gini coefficient for request distribution
        
        Returns:
            Gini coefficient (0 = perfect equality, 1 = perfect inequality)
            Target: < 0.2 (good distribution)
        """
        usage_counts = [h.total_requests for h in self.health.values()]
        
        if not usage_counts or sum(usage_counts) == 0:
            return 0.0
        
        # Sort usage counts
        sorted_usage = sorted(usage_counts)
        n = len(sorted_usage)
        
        # Calculate Gini coefficient
        cumsum = 0
        for i, count in enumerate(sorted_usage):
            cumsum += (i + 1) * count
        
        total_usage = sum(sorted_usage)
        gini = (2 * cumsum) / (n * total_usage) - (n + 1) / n
        
        return gini
    
    def reset_key(self, key_id: str):
        """Manually reset a key to HEALTHY state
        
        Args:
            key_id: ID of key to reset
        
        Raises:
            KeyError: If key_id not found
        """
        if key_id not in self.keys:
            raise KeyError(f"Key '{key_id}' not found")
        
        health = self.health[key_id]
        health.status = KeyStatus.HEALTHY
        health.consecutive_failures = 0
        health.cooldown_until = None
        health.rate_limit_until = None
        
        logger.info(f"Key '{key_id}' manually reset to HEALTHY")
    
    def __repr__(self) -> str:
        healthy = sum(1 for h in self.health.values() if h.status == KeyStatus.HEALTHY)
        return f"KeyRotation(keys={len(self.keys)}, healthy={healthy})"
