"""
🚀 Simplified Reliable MCP Server
==================================

Минимальная интеграция Phase 1-3 паттернов для демонстрации 110% надёжности
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List
import os
import sys

# Add automation path for KeyManager
sys.path.insert(0, str(Path(__file__).parent))

# Import encrypted key manager
from automation.task2_key_manager.key_manager import KeyManager

# Configure logging
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'reliable_mcp_simple.log', encoding='utf-8'),
    ]
)

logger = logging.getLogger('reliable_mcp')


class SimplifiedReliableMCP:
    """
    Упрощённая версия для демонстрации концепции 110% надёжности
    """
    
    def __init__(self):
        logger.info("=" * 80)
        logger.info("🚀 Simplified Reliable MCP Server (with Encryption)")
        logger.info("=" * 80)
        
        # Initialize KeyManager with encryption
        self.key_manager = KeyManager()
        
        # Load encryption key from .env
        from dotenv import load_dotenv
        load_dotenv()
        
        encryption_key = os.getenv('ENCRYPTION_KEY')
        if not encryption_key:
            logger.error("❌ ENCRYPTION_KEY not found in .env!")
            raise Exception("ENCRYPTION_KEY required in .env")
        
        # Initialize encryption
        if not self.key_manager.initialize_encryption(encryption_key):
            logger.error("❌ Failed to initialize encryption!")
            raise Exception("Encryption initialization failed")
        
        # Load encrypted keys
        if not self.key_manager.load_keys("encrypted_secrets.json"):
            logger.error("❌ Failed to load encrypted keys!")
            raise Exception("Failed to load encrypted_secrets.json")
        
        # Load API keys using get_all_keys()
        self.perplexity_keys = self.key_manager.get_all_keys('PERPLEXITY_API_KEY')
        self.deepseek_keys = self.key_manager.get_all_keys('DEEPSEEK_API_KEY')
        
        logger.info(f"✅ Loaded {len(self.perplexity_keys)} Perplexity keys (encrypted)")
        logger.info(f"✅ Loaded {len(self.deepseek_keys)} DeepSeek keys (encrypted)")
        
        if len(self.perplexity_keys) != 4:
            logger.warning(f"⚠️ Expected 4 Perplexity keys, got {len(self.perplexity_keys)}")
        
        if len(self.deepseek_keys) != 8:
            logger.warning(f"⚠️ Expected 8 DeepSeek keys, got {len(self.deepseek_keys)}")
        
        # Simple round-robin counters
        self._perplexity_index = 0
        self._deepseek_index = 0
        
        # Simple in-memory cache
        self._cache = {}
        
        logger.info("🎉 Simplified server ready with encrypted keys!")
        logger.info("=" * 80)
    
    def _load_keys(self, base_env_var: str, count: int) -> List[str]:
        """DEPRECATED - now using KeyManager.get_all_keys()"""
        logger.warning("_load_keys() is deprecated, using KeyManager instead")
        return []
    
    def get_perplexity_key(self) -> str:
        """Round-robin key selection for Perplexity"""
        if not self.perplexity_keys:
            raise Exception("No Perplexity API keys configured!")
        
        key = self.perplexity_keys[self._perplexity_index]
        self._perplexity_index = (self._perplexity_index + 1) % len(self.perplexity_keys)
        return key
    
    def get_deepseek_key(self) -> str:
        """Round-robin key selection for DeepSeek"""
        if not self.deepseek_keys:
            raise Exception("No DeepSeek API keys configured!")
        
        key = self.deepseek_keys[self._deepseek_index]
        self._deepseek_index = (self._deepseek_index + 1) % len(self.deepseek_keys)
        return key
    
    async def send_to_deepseek(self, audit_request: str) -> Dict[str, Any]:
        """Send audit request to DeepSeek with retry and key rotation"""
        logger.info(f"📤 Sending to DeepSeek: {audit_request[:50]}...")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Get next key (rotation)
                api_key = self.get_deepseek_key()
                logger.info(f"   Using key #{self._deepseek_index} (attempt {attempt + 1})")
                
                # Simulate API call
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.deepseek.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": "deepseek-coder",
                            "messages": [
                                {"role": "system", "content": "Code review expert"},
                                {"role": "user", "content": audit_request}
                            ],
                            "stream": False  # ✅ FIX: Disable streaming
                        },
                        timeout=60.0  # ✅ FIX: Increase timeout for large responses
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    logger.info(f"✅ DeepSeek response received")
                    return result
                    
            except Exception as e:
                logger.error(f"❌ DeepSeek attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return {"error": str(e), "fallback": True}
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return {"error": "All retries exhausted"}
    
    async def send_to_perplexity(self, query: str) -> Dict[str, Any]:
        """Send query to Perplexity with retry and key rotation"""
        logger.info(f"📤 Sending to Perplexity: {query[:50]}...")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                api_key = self.get_perplexity_key()
                logger.info(f"   Using key #{self._perplexity_index} (attempt {attempt + 1})")
                
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.perplexity.ai/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"  # ✅ FIX: Explicit content type
                        },
                        json={
                            "model": "sonar",  # ✅ FIX: Updated model name
                            "messages": [{"role": "user", "content": query}],
                            "stream": False,
                            "max_tokens": 4096  # ✅ FIX: Limit response size
                        },
                        timeout=60.0
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    logger.info(f"✅ Perplexity response received")
                    return result
                    
            except Exception as e:
                logger.error(f"❌ Perplexity attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return {"error": str(e), "fallback": True}
                await asyncio.sleep(2 ** attempt)
        
        return {"error": "All retries exhausted"}
    
    async def parallel_audit(self) -> Dict[str, Any]:
        """
        Параллельный аудит: DeepSeek (8 ключей) + Perplexity (4 ключа)
        """
        logger.info("🚀 Starting PARALLEL AUDIT")
        logger.info(f"   - DeepSeek: {len(self.deepseek_keys)} keys available")
        logger.info(f"   - Perplexity: {len(self.perplexity_keys)} keys available")
        
        tasks = []
        
        # DeepSeek tasks (8 параллельных запросов)
        deepseek_requests = [
            "Review Phase 1: RetryPolicy implementation",
            "Review Phase 1: KeyRotation implementation",
            "Review Phase 1: ServiceMonitor implementation",
            "Review Phase 3: RateLimiter implementation",
            "Review Phase 3: CircuitBreaker state machine",
            "Review Phase 3: DistributedCache LRU policy",
            "Review Phase 3: RequestDeduplication hashing",
            "Overall Phase 1-3 compliance score"
        ]
        
        for req in deepseek_requests:
            tasks.append(self.send_to_deepseek(req))
        
        # Perplexity tasks (4 параллельных запроса)
        perplexity_queries = [
            "Netflix Hystrix Circuit Breaker best practices",
            "AWS SDK retry policy patterns",
            "Token bucket vs leaky bucket rate limiting",
            "Production readiness checklist distributed systems"
        ]
        
        for query in perplexity_queries:
            tasks.append(self.send_to_perplexity(query))
        
        # Execute all in parallel
        logger.info(f"📊 Executing {len(tasks)} tasks in parallel...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        deepseek_results = results[:len(deepseek_requests)]
        perplexity_results = results[len(deepseek_requests):]
        
        errors = [r for r in results if isinstance(r, Exception)]
        
        logger.info(f"✅ Parallel audit complete:")
        logger.info(f"   - DeepSeek: {len([r for r in deepseek_results if not isinstance(r, Exception)])} success")
        logger.info(f"   - Perplexity: {len([r for r in perplexity_results if not isinstance(r, Exception)])} success")
        logger.info(f"   - Errors: {len(errors)}")
        
        return {
            "deepseek_reviews": deepseek_results,
            "perplexity_research": perplexity_results,
            "errors": [str(e) for e in errors],
            "summary": {
                "total_tasks": len(tasks),
                "deepseek_keys_used": len(self.deepseek_keys),
                "perplexity_keys_used": len(self.perplexity_keys),
                "parallel_execution": True
            }
        }


async def main():
    """Test the simplified server"""
    server = SimplifiedReliableMCP()
    
    logger.info("\n" + "=" * 80)
    logger.info("🧪 Testing Key Rotation")
    logger.info("=" * 80)
    
    # Test key rotation
    for i in range(6):
        perp_key = server.get_perplexity_key()
        deep_key = server.get_deepseek_key()
        logger.info(f"Round {i+1}:")
        logger.info(f"   Perplexity key: {perp_key[:10]}...")
        logger.info(f"   DeepSeek key: {deep_key[:10]}...")
    
    logger.info("\n" + "=" * 80)
    logger.info("🚀 Ready for parallel audit!")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
