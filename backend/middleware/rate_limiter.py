"""
Rate Limiter для FastAPI
Защита от DDoS и злоупотреблений API
"""

import os
import time
import logging
from typing import Optional, Callable
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram
import asyncio

logger = logging.getLogger(__name__)

# Prometheus метрики
RATE_LIMIT_HITS = Counter(
    'rate_limit_hits_total',
    'Total rate limit hits',
    ['endpoint', 'client']
)

RATE_LIMIT_BLOCKS = Counter(
    'rate_limit_blocks_total',
    'Total blocked requests due to rate limiting',
    ['endpoint', 'client']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint', 'status']
)


class RateLimitExceeded(HTTPException):
    """Exception для превышения rate limit"""
    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )


class TokenBucket:
    """
    Token Bucket algorithm для rate limiting
    
    Более гибкий чем sliding window - позволяет короткие всплески
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Максимальное количество токенов
            refill_rate: Скорость пополнения токенов в секунду
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        """
        Попытка использовать токены
        
        Args:
            tokens: Количество токенов для использования
        
        Returns:
            True если токены доступны, False если лимит превышен
        """
        async with self.lock:
            # Пополняем токены
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate
            )
            self.last_refill = now
            
            # Проверяем доступность
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def get_retry_after(self) -> int:
        """Сколько секунд ждать до следующего запроса"""
        tokens_needed = 1 - self.tokens
        if tokens_needed <= 0:
            return 0
        return int(tokens_needed / self.refill_rate) + 1


class RateLimiter:
    """
    Advanced Rate Limiter с различными стратегиями
    
    Features:
    - Per-IP limiting
    - Per-user limiting
    - Per-endpoint limiting
    - Token bucket algorithm
    - Whitelist/Blacklist
    - Automatic cleanup
    """
    
    def __init__(self):
        # IP -> endpoint -> TokenBucket
        self.ip_buckets: dict = defaultdict(dict)
        
        # User -> endpoint -> TokenBucket
        self.user_buckets: dict = defaultdict(dict)
        
        # Whitelist IP addresses (no limits)
        # Conditional: E2E_TEST_MODE='rate_limit' disables whitelist for rate limit testing
        # В продакшене удалить 127.0.0.1 и добавить доверенные IP: monitoring, health checks, etc.
        if os.getenv("E2E_TEST_MODE") == "rate_limit":
            self.whitelist: set = set()  # Empty for rate limit E2E tests
            logger.info("⚠️ Rate limiter: E2E_TEST_MODE=rate_limit, whitelist disabled")
        else:
            self.whitelist: set = {"127.0.0.1", "::1"}  # localhost для обычных E2E тестов
            logger.info("✅ Rate limiter: localhost in whitelist for E2E tests")
        
        # Blacklist IP addresses (block all)
        self.blacklist: set = set()
        
        # Default limits per endpoint (настроено для демонстрации и E2E тестов)
        self.endpoint_limits = {
            "/auth/login": {"capacity": 25, "refill_rate": 1.0},  # 25 login attempts, faster refill for 16+ E2E tests
            "/run_task": {"capacity": 5, "refill_rate": 0.2},   # 5 requests, refill 1 per 5 sec
            "/status": {"capacity": 20, "refill_rate": 0.5},    # 20 requests, refill 0.5/sec (30/min)
            "/logs": {"capacity": 15, "refill_rate": 0.5},      # 15 requests, refill 0.5/sec
            "/sandbox/execute": {"capacity": 3, "refill_rate": 0.1},  # 3 requests, very slow refill
            "default": {"capacity": 10, "refill_rate": 0.3}     # 10 requests, refill 0.3/sec (18/min)
        }
        
        # Cleanup task
        self.cleanup_task = None
        self._cleanup_started = False
    
    def start_cleanup_task(self):
        """Запустить фоновую очистку старых buckets"""
        if self._cleanup_started:
            return
        
        self._cleanup_started = True
        
        async def cleanup():
            while True:
                await asyncio.sleep(300)  # Every 5 minutes
                await self._cleanup_old_buckets()
        
        try:
            self.cleanup_task = asyncio.create_task(cleanup())
        except RuntimeError:
            # Event loop not running yet, will be started later
            self._cleanup_started = False
    
    async def _cleanup_old_buckets(self):
        """Удалить неактивные buckets"""
        now = time.time()
        timeout = 600  # 10 minutes
        
        # Cleanup IP buckets
        for ip in list(self.ip_buckets.keys()):
            for endpoint in list(self.ip_buckets[ip].keys()):
                bucket = self.ip_buckets[ip][endpoint]
                if now - bucket.last_refill > timeout:
                    del self.ip_buckets[ip][endpoint]
            
            if not self.ip_buckets[ip]:
                del self.ip_buckets[ip]
        
        logger.info(f"Cleaned up old rate limit buckets")
    
    def get_bucket(self, 
                   identifier: str,
                   endpoint: str,
                   bucket_type: str = "ip") -> TokenBucket:
        """
        Получить или создать bucket
        
        Args:
            identifier: IP address или user_id
            endpoint: API endpoint
            bucket_type: "ip" или "user"
        
        Returns:
            TokenBucket instance
        """
        buckets = self.ip_buckets if bucket_type == "ip" else self.user_buckets
        
        if endpoint not in buckets[identifier]:
            # Получаем лимиты для endpoint
            limits = self.endpoint_limits.get(
                endpoint,
                self.endpoint_limits["default"]
            )
            
            buckets[identifier][endpoint] = TokenBucket(
                capacity=limits["capacity"],
                refill_rate=limits["refill_rate"]
            )
        
        return buckets[identifier][endpoint]
    
    async def check_rate_limit(self,
                              request: Request,
                              endpoint: Optional[str] = None,
                              user_id: Optional[str] = None) -> None:
        """
        Проверить rate limit
        
        Args:
            request: FastAPI Request
            endpoint: API endpoint (если None, берётся из request.url.path)
            user_id: User ID для per-user limiting
        
        Raises:
            RateLimitExceeded: Если лимит превышен
        """
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Whitelist check
        if client_ip in self.whitelist:
            return
        
        # Blacklist check
        if client_ip in self.blacklist:
            RATE_LIMIT_BLOCKS.labels(endpoint=endpoint or "blacklist", client=client_ip).inc()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP address is blacklisted"
            )
        
        # Get endpoint
        if endpoint is None:
            endpoint = request.url.path
        
        # Check IP-based limit
        ip_bucket = self.get_bucket(client_ip, endpoint, "ip")
        if not await ip_bucket.consume():
            retry_after = ip_bucket.get_retry_after()
            RATE_LIMIT_BLOCKS.labels(endpoint=endpoint, client=client_ip).inc()
            logger.warning(f"Rate limit exceeded for IP {client_ip} on {endpoint}")
            raise RateLimitExceeded(retry_after=retry_after)
        
        # Check user-based limit (if user_id provided)
        if user_id:
            user_bucket = self.get_bucket(user_id, endpoint, "user")
            if not await user_bucket.consume():
                retry_after = user_bucket.get_retry_after()
                RATE_LIMIT_BLOCKS.labels(endpoint=endpoint, client=user_id).inc()
                logger.warning(f"Rate limit exceeded for user {user_id} on {endpoint}")
                raise RateLimitExceeded(retry_after=retry_after)
        
        RATE_LIMIT_HITS.labels(endpoint=endpoint, client=client_ip).inc()
    
    def _get_client_ip(self, request: Request) -> str:
        """Получить IP клиента (учитывая proxy)"""
        # Check X-Forwarded-For header (за proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection IP
        return request.client.host if request.client else "unknown"
    
    def add_to_whitelist(self, ip: str):
        """Добавить IP в whitelist"""
        self.whitelist.add(ip)
        logger.info(f"Added {ip} to whitelist")
    
    def add_to_blacklist(self, ip: str):
        """Добавить IP в blacklist"""
        self.blacklist.add(ip)
        logger.warning(f"Added {ip} to blacklist")
    
    def remove_from_whitelist(self, ip: str):
        """Убрать IP из whitelist"""
        self.whitelist.discard(ip)
        logger.info(f"Removed {ip} from whitelist")
    
    def remove_from_blacklist(self, ip: str):
        """Убрать IP из blacklist"""
        self.blacklist.discard(ip)
        logger.info(f"Removed {ip} from blacklist")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI Middleware для автоматического rate limiting
    
    Usage:
        app.add_middleware(RateLimitMiddleware)
    """
    
    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self.limiter = limiter
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""
        # Start cleanup task on first request
        if not self.limiter._cleanup_started:
            self.limiter.start_cleanup_task()
        
        start_time = time.time()
        
        try:
            # Check rate limit
            await self.limiter.check_rate_limit(request)
            
            # Process request
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).observe(duration)
            
            return response
            
        except RateLimitExceeded as e:
            # Return 429 Too Many Requests
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers
            )
        
        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
            # Let other error handlers deal with it
            raise


# Singleton instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Получить singleton instance rate limiter"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
        # Cleanup task will be started by middleware on first request
    return _rate_limiter


# Dependency для использования в routes
async def rate_limit_dependency(request: Request):
    """
    FastAPI dependency для rate limiting
    
    Usage:
        @app.post("/run_task", dependencies=[Depends(rate_limit_dependency)])
        async def run_task():
            ...
    """
    limiter = get_rate_limiter()
    await limiter.check_rate_limit(request)
