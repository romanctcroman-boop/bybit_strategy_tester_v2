"""
Perplexity API Client
Simplified client for health checks

🚀 Quick Win 2: Оптимизированный health check
🚀 Priority 1: Unified Caching Client (Simplified approach)

Benefits:
    ✅ Uses same caching strategy as PerplexityProvider
    ✅ Reuses circuit breaker pattern concepts
    ✅ Minimal code (~120 lines vs ~440 lines before)
    ✅ Backward compatible API
"""

import os
import httpx
from typing import Optional
import time
import hashlib
import json
from collections import OrderedDict
from datetime import datetime, timedelta


class SimpleCache:
    """
    🚀 Priority 1: Shared caching implementation
    
    Same LRU + TTL strategy as PerplexityProvider
    """
    
    def __init__(self, max_size: int = 10, ttl_seconds: int = 60):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.stats = {"hits": 0, "misses": 0}
    
    def _compute_key(self, query: str, **kwargs) -> str:
        """Compute cache key using SHA256"""
        cache_dict = {"query": query.strip().lower(), **kwargs}
        cache_str = json.dumps(cache_dict, sort_keys=True)
        # Using SHA256 for cache keys (more secure than MD5)
        return hashlib.sha256(cache_str.encode()).hexdigest()[:16]  # Truncate for shorter keys
    
    def get(self, query: str, **kwargs) -> Optional[dict]:
        """Get from cache"""
        key = self._compute_key(query, **kwargs)
        
        if key in self.cache:
            entry = self.cache[key]
            
            # Check TTL
            if datetime.now() < entry["expires_at"]:
                self.cache.move_to_end(key)  # LRU update
                self.stats["hits"] += 1
                return entry["response"]
            else:
                del self.cache[key]  # Expired
        
        self.stats["misses"] += 1
        return None
    
    def set(self, query: str, response: dict, **kwargs):
        """Set to cache"""
        key = self._compute_key(query, **kwargs)
        
        # LRU eviction
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        
        self.cache[key] = {
            "response": response,
            "expires_at": datetime.now() + timedelta(seconds=self.ttl_seconds)
        }
        self.cache.move_to_end(key)
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": round(hit_rate, 1)
        }


class PerplexityClient:
    """
    Perplexity API client for health checks
    
    🚀 Priority 1: Simplified unified implementation
    - Shared caching strategy with PerplexityProvider
    - Circuit breaker ready (failure tracking)
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize client with unified caching"""
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY", "")
        self.base_url = "https://api.perplexity.ai"
        self.timeout = 5.0  # 🚀 Quick Win 2: Reduced timeout
        
        # 🚀 Priority 1: Shared cache implementation
        self.cache = SimpleCache(max_size=10, ttl_seconds=60)
        
        # Circuit breaker tracking
        self.failure_count = 0
        self.last_failure_time = 0
    
    async def test_connection(self) -> bool:
        """
        Test connection to Perplexity API
        
        🚀 Priority 1: Uses shared caching strategy
        """
        if not self.api_key:
            return False
        
        # Check cache first
        cached = self.cache.get("ping", model="sonar")
        if cached:
            return cached.get("success", False)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "sonar",
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                        "temperature": 0,
                        "stream": False
                    }
                )
                
                is_healthy = response.status_code in [200, 400, 401, 403]
                
                # Cache result
                self.cache.set("ping", {"success": is_healthy}, model="sonar")
                
                # Reset failure count on success
                if is_healthy:
                    self.failure_count = 0
                
                return is_healthy
                
        except (httpx.TimeoutException, Exception):
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            # Cache failure
            self.cache.set("ping", {"success": False}, model="sonar")
            return False
    
    async def check_health(self) -> dict:
        """
        Check API health status
        
        🚀 Priority 1: Returns unified stats
        """
        start_time = time.time()
        is_healthy = await self.test_connection()
        latency = (time.time() - start_time) * 1000
        
        # 🚀 Priority 1: Return cache stats + circuit breaker info
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "Perplexity API",
            "available": is_healthy,
            "latency_ms": round(latency, 2),
            "cache_stats": self.cache.get_stats(),  # 🚀 Priority 1
            "circuit_breaker": {  # 🚀 Priority 1: Circuit breaker info
                "failure_count": self.failure_count,
                "last_failure_time": self.last_failure_time,
                "state": "open" if self.failure_count >= 5 else "closed"
            }
        }
    
    def invalidate_health_cache(self):
        """
        🚀 Priority 1: Clear cache
        """
        self.cache.cache.clear()
        self.cache.stats = {"hits": 0, "misses": 0}

