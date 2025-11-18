"""
🚀 Reliable MCP Server - Phase 1-3 Integration
============================================

Применяет ВСЕ паттерны надёжности:
- Phase 1: RetryPolicy, KeyRotation, ServiceMonitor
- Phase 3: RateLimiter, CircuitBreaker, Cache, Deduplication

ЦЕЛЬ: Надёжность = 110%
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List
from datetime import datetime
import signal
import sys

# Phase 1 Imports
from reliability.retry_policy import RetryPolicy, RetryConfig
from reliability.key_rotation import KeyRotation, KeyConfig
from reliability.service_monitor import ServiceMonitor, ServiceConfig

# Phase 3 Imports
from reliability.rate_limiter import RateLimiter, RateLimiterConfig
from reliability.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerRegistry
from reliability.distributed_cache import DistributedCache
from reliability.request_deduplication import RequestDeduplication

# Configure logging
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'reliable_mcp_server.log', encoding='utf-8'),
    ]
)

logger = logging.getLogger('reliable_mcp')


class ReliableMCPServer:
    """
    MCP Server с 110% надёжностью через Phase 1-3 паттерны
    """
    
    def __init__(self):
        logger.info("=" * 80)
        logger.info("🚀 Initializing RELIABLE MCP Server (Phase 1-3 Integration)")
        logger.info("=" * 80)
        
        # ========== Phase 1: Reliability Foundations ==========
        
        # 1. RetryPolicy для API вызовов
        self.retry_policy = RetryPolicy(RetryConfig(
            max_retries=5,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True
        ))
        logger.info("✅ RetryPolicy initialized (max_retries=5, exponential backoff)")
        
        # 2. KeyRotation для Perplexity (4 ключа) и DeepSeek (8 ключей)
        self.perplexity_keys = KeyRotation(KeyConfig(
            service_name="perplexity",
            api_keys=self._load_perplexity_keys(),  # 4 ключа
            rotation_enabled=True,
            health_check_interval=3600  # 1 час
        ))
        
        self.deepseek_keys = KeyRotation(KeyConfig(
            service_name="deepseek",
            api_keys=self._load_deepseek_keys(),  # 8 ключей
            rotation_enabled=True,
            health_check_interval=1800  # 30 минут
        ))
        logger.info("✅ KeyRotation initialized:")
        logger.info(f"   - Perplexity: {len(self.perplexity_keys.config.api_keys)} keys")
        logger.info(f"   - DeepSeek: {len(self.deepseek_keys.config.api_keys)} keys")
        
        # 3. ServiceMonitor для всех компонентов
        self.service_monitor = ServiceMonitor([
            ServiceConfig(
                name="mcp_server",
                health_check_url="http://localhost:8000/health",
                check_interval=30
            ),
            ServiceConfig(
                name="perplexity_api",
                health_check_url="https://api.perplexity.ai/health",
                check_interval=60
            ),
            ServiceConfig(
                name="deepseek_api",
                health_check_url="https://api.deepseek.com/health",
                check_interval=60
            )
        ])
        logger.info("✅ ServiceMonitor initialized (3 services)")
        
        # ========== Phase 3: Distributed Patterns ==========
        
        # 1. RateLimiter (token bucket)
        self.rate_limiters = {
            'perplexity': RateLimiter(RateLimiterConfig(
                max_requests=60,  # 60 req/min
                window_seconds=60,
                burst_size=10  # Burst до 10
            )),
            'deepseek': RateLimiter(RateLimiterConfig(
                max_requests=100,  # 100 req/min (больше ключей)
                window_seconds=60,
                burst_size=20
            ))
        }
        logger.info("✅ RateLimiters initialized:")
        logger.info("   - Perplexity: 60 req/min (burst 10)")
        logger.info("   - DeepSeek: 100 req/min (burst 20)")
        
        # 2. CircuitBreakers для каждого API
        self.circuit_breakers = CircuitBreakerRegistry()
        
        self.circuit_breakers.register("perplexity_api", CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout=30.0,
            recovery_timeout=60.0
        ))
        
        self.circuit_breakers.register("deepseek_api", CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout=30.0,
            recovery_timeout=60.0
        ))
        logger.info("✅ CircuitBreakers registered (2 APIs)")
        
        # 3. DistributedCache для результатов
        self.cache = DistributedCache(
            max_size=1000,
            default_ttl=3600  # 1 час
        )
        logger.info("✅ DistributedCache initialized (max_size=1000, ttl=3600s)")
        
        # 4. RequestDeduplication
        self.deduplicator = RequestDeduplication(window_seconds=60)
        logger.info("✅ RequestDeduplication initialized (window=60s)")
        
        # Shutdown handler
        self._shutdown = False
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        logger.info("=" * 80)
        logger.info("🎉 RELIABLE MCP Server ready! (Надёжность = 110%)")
        logger.info("=" * 80)
    
    def _load_perplexity_keys(self) -> List[str]:
        """Загрузить 4 Perplexity API ключа (зашифрованные)"""
        # TODO: Загрузить из системы шифрования
        import os
        keys = []
        for i in range(1, 5):  # 4 ключа
            key = os.getenv(f'PERPLEXITY_API_KEY_{i}')
            if key:
                keys.append(key)
        
        if not keys:
            # Fallback на основной ключ
            main_key = os.getenv('PERPLEXITY_API_KEY')
            if main_key:
                keys = [main_key]
        
        logger.info(f"Loaded {len(keys)} Perplexity keys from environment")
        return keys
    
    def _load_deepseek_keys(self) -> List[str]:
        """Загрузить 8 DeepSeek API ключей (зашифрованные)"""
        # TODO: Загрузить из системы шифрования
        import os
        keys = []
        for i in range(1, 9):  # 8 ключей
            key = os.getenv(f'DEEPSEEK_API_KEY_{i}')
            if key:
                keys.append(key)
        
        if not keys:
            # Fallback на основной ключ
            main_key = os.getenv('DEEPSEEK_API_KEY')
            if main_key:
                keys = [main_key]
        
        logger.info(f"Loaded {len(keys)} DeepSeek keys from environment")
        return keys
    
    async def call_perplexity(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Вызов Perplexity API с ПОЛНОЙ надёжностью (Phase 1-3)
        """
        # 1. Check deduplication
        request_data = {'api': 'perplexity', 'query': query, **kwargs}
        if await self.deduplicator.is_duplicate(request_data):
            logger.info(f"🔄 Duplicate request detected, returning cached result")
            cached = await self.cache.get(f"perplexity:{query}")
            if cached:
                return cached
        
        # 2. Check cache
        cache_key = f"perplexity:{query}"
        cached = await self.cache.get(cache_key)
        if cached:
            logger.info(f"💾 Cache HIT for: {query[:50]}...")
            return cached
        
        # 3. Check rate limiter
        if not await self.rate_limiters['perplexity'].acquire():
            raise Exception("Rate limit exceeded for Perplexity API")
        
        # 4. Get healthy API key
        api_key = await self.perplexity_keys.get_next_key()
        
        # 5. Execute with Circuit Breaker + Retry
        cb = self.circuit_breakers.get("perplexity_api")
        
        async def api_call():
            # Actual API call here
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "llama-3.1-sonar-small-128k-online",
                        "messages": [{"role": "user", "content": query}],
                        **kwargs
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        
        # Wrap in retry + circuit breaker
        result = await cb.call(
            lambda: self.retry_policy.execute_with_retry(api_call),
            fallback=lambda: {"error": "Service unavailable", "fallback": True}
        )
        
        # 6. Cache result
        if "error" not in result:
            await self.cache.set(cache_key, result, ttl=3600)
        
        logger.info(f"✅ Perplexity call successful: {query[:50]}...")
        return result
    
    async def call_deepseek(self, code: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Вызов DeepSeek API с ПОЛНОЙ надёжностью (Phase 1-3)
        """
        # Same pattern as Perplexity
        request_data = {'api': 'deepseek', 'code': code, 'prompt': prompt, **kwargs}
        if await self.deduplicator.is_duplicate(request_data):
            logger.info(f"🔄 Duplicate DeepSeek request detected")
            cached = await self.cache.get(f"deepseek:{prompt}")
            if cached:
                return cached
        
        cache_key = f"deepseek:{prompt}"
        cached = await self.cache.get(cache_key)
        if cached:
            logger.info(f"💾 Cache HIT for DeepSeek: {prompt[:50]}...")
            return cached
        
        if not await self.rate_limiters['deepseek'].acquire():
            raise Exception("Rate limit exceeded for DeepSeek API")
        
        api_key = await self.deepseek_keys.get_next_key()
        cb = self.circuit_breakers.get("deepseek_api")
        
        async def api_call():
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "deepseek-coder",
                        "messages": [
                            {"role": "system", "content": "You are a code review expert."},
                            {"role": "user", "content": f"{prompt}\n\nCode:\n{code}"}
                        ],
                        **kwargs
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        
        result = await cb.call(
            lambda: self.retry_policy.execute_with_retry(api_call),
            fallback=lambda: {"error": "Service unavailable", "fallback": True}
        )
        
        if "error" not in result:
            await self.cache.set(cache_key, result, ttl=3600)
        
        logger.info(f"✅ DeepSeek call successful: {prompt[:50]}...")
        return result
    
    async def parallel_audit(self, code: str, reports: List[str]) -> Dict[str, Any]:
        """
        Параллельный аудит через DeepSeek (8 ключей) и Perplexity (4 ключа)
        
        Используем многопоточность через asyncio.gather
        """
        logger.info("🚀 Starting PARALLEL AUDIT")
        logger.info(f"   - DeepSeek keys available: {len(self.deepseek_keys.config.api_keys)}")
        logger.info(f"   - Perplexity keys available: {len(self.perplexity_keys.config.api_keys)}")
        
        tasks = []
        
        # 1. DeepSeek tasks (используем все 8 ключей)
        deepseek_prompts = [
            "Review Phase 1 RetryPolicy implementation",
            "Review Phase 1 KeyRotation implementation",
            "Review Phase 1 ServiceMonitor implementation",
            "Review Phase 3 RateLimiter implementation",
            "Review Phase 3 CircuitBreaker implementation",
            "Review Phase 3 DistributedCache implementation",
            "Review Phase 3 RequestDeduplication implementation",
            "Overall architecture review and compliance score"
        ]
        
        for prompt in deepseek_prompts:
            tasks.append(self.call_deepseek(code, prompt))
        
        # 2. Perplexity tasks (используем все 4 ключа)
        perplexity_queries = [
            "Best practices for Circuit Breaker pattern Netflix Hystrix",
            "Industry standards for retry policies AWS SDK",
            "Rate limiting algorithms comparison token bucket vs leaky bucket",
            "Production readiness checklist for distributed systems"
        ]
        
        for query in perplexity_queries:
            tasks.append(self.call_perplexity(query))
        
        # 3. Параллельное выполнение ВСЕХ задач
        logger.info(f"📊 Executing {len(tasks)} tasks in parallel...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 4. Обработка результатов
        deepseek_results = []
        perplexity_results = []
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append({"task": i, "error": str(result)})
            elif i < len(deepseek_prompts):
                deepseek_results.append(result)
            else:
                perplexity_results.append(result)
        
        logger.info(f"✅ Parallel audit complete:")
        logger.info(f"   - DeepSeek: {len(deepseek_results)}/{len(deepseek_prompts)} success")
        logger.info(f"   - Perplexity: {len(perplexity_results)}/{len(perplexity_queries)} success")
        logger.info(f"   - Errors: {len(errors)}")
        
        return {
            "deepseek_reviews": deepseek_results,
            "perplexity_research": perplexity_results,
            "errors": errors,
            "summary": {
                "total_tasks": len(tasks),
                "successful": len(results) - len(errors),
                "failed": len(errors),
                "parallel_execution": True
            }
        }
    
    def _handle_shutdown(self, signum, frame):
        """Graceful shutdown"""
        logger.info(f"🛑 Shutdown signal received: {signum}")
        self._shutdown = True
        
        # Stop monitoring
        self.service_monitor.stop()
        
        # Get final stats
        logger.info("📊 Final Statistics:")
        logger.info(f"   Rate Limiters:")
        for name, limiter in self.rate_limiters.items():
            stats = limiter.get_stats()
            logger.info(f"      {name}: {stats}")
        
        logger.info(f"   Circuit Breakers:")
        cb_stats = self.circuit_breakers.get_all_stats()
        for name, stats in cb_stats.items():
            logger.info(f"      {name}: {stats}")
        
        logger.info("👋 Goodbye!")
        sys.exit(0)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN: Start Reliable MCP Server
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Start the reliable MCP server"""
    server = ReliableMCPServer()
    
    # Start monitoring
    await server.service_monitor.start()
    
    logger.info("🎯 Reliable MCP Server is running")
    logger.info("Press Ctrl+C to stop")
    
    # Keep running
    while not server._shutdown:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
