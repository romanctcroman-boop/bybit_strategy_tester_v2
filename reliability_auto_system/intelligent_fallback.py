"""
Intelligent Fallback Router
Автоматическое переключение MCP → Direct API с circuit breaker pattern
Based on: Netflix Hystrix, AWS Route 53, Google Cloud Load Balancing best practices
"""

import httpx
import time
import asyncio
from enum import Enum
from typing import Dict, Any, List, Optional
import logging


class ConnectionMode(Enum):
    """Connection mode for AI requests"""
    MCP = "mcp"
    DIRECT_API = "direct_api"


class IntelligentFallbackRouter:
    """Smart routing between MCP and Direct API with automatic failover"""
    
    def __init__(self, mcp_url: str = "http://localhost:3000"):
        self.mcp_url = mcp_url
        self.current_mode = ConnectionMode.MCP
        
        # Circuit breaker configuration (Netflix Hystrix pattern)
        self.failure_count = 0
        self.max_failures = 3  # Open circuit after 3 failures
        self.circuit_open = False
        self.circuit_open_until = 0
        self.circuit_timeout = 300  # 5 minutes
        
        # API keys for fallback
        self.direct_api_keys = {
            "deepseek": [],
            "perplexity": []
        }
        
        # Key rotation index
        self.key_index = {
            "deepseek": 0,
            "perplexity": 0
        }
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        
        # Metrics
        self.metrics = {
            "mcp_requests": 0,
            "mcp_failures": 0,
            "direct_api_requests": 0,
            "direct_api_failures": 0,
            "circuit_opens": 0,
            "circuit_closes": 0
        }
    
    def add_api_key(self, service: str, api_key: str):
        """Add API key for direct API fallback"""
        if service in self.direct_api_keys:
            self.direct_api_keys[service].append(api_key)
            self.logger.info(f"✅ Added API key for {service} (total: {len(self.direct_api_keys[service])})")
    
    async def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request through MCP or Direct API with intelligent fallback"""
        
        # Check circuit breaker state
        if self.circuit_open:
            if time.time() < self.circuit_open_until:
                self.logger.warning("🚫 Circuit breaker is OPEN, using direct API")
                return await self._use_direct_api(request)
            else:
                # Circuit breaker timeout expired, try half-open state
                self.logger.info("🔄 Circuit breaker timeout expired, trying MCP (half-open)")
                self.circuit_open = False
                self.current_mode = ConnectionMode.MCP
                self.metrics["circuit_closes"] += 1
        
        # Try MCP first (primary mode)
        if self.current_mode == ConnectionMode.MCP:
            try:
                result = await self._use_mcp(request)
                self.failure_count = 0  # Reset on success
                self.metrics["mcp_requests"] += 1
                return result
            
            except Exception as e:
                self.failure_count += 1
                self.metrics["mcp_failures"] += 1
                self.logger.error(f"❌ MCP request failed ({self.failure_count}/{self.max_failures}): {e}")
                
                # Open circuit breaker if threshold exceeded
                if self.failure_count >= self.max_failures:
                    self._open_circuit_breaker()
                
                # Fallback to direct API for this request
                return await self._use_direct_api(request)
        
        else:
            # Already in direct API mode
            return await self._use_direct_api(request)
    
    def _open_circuit_breaker(self):
        """Open circuit breaker (Netflix Hystrix pattern)"""
        self.logger.warning(f"⚡ Opening circuit breaker (failures: {self.failure_count})")
        self.current_mode = ConnectionMode.DIRECT_API
        self.circuit_open = True
        self.circuit_open_until = time.time() + self.circuit_timeout
        self.metrics["circuit_opens"] += 1
    
    async def _use_mcp(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request through MCP server"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.mcp_url}/api/query",
                json=request
            )
            response.raise_for_status()
            
            data = response.json()
            data["source"] = "mcp"
            return data
    
    async def _use_direct_api(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request through Direct API with key rotation"""
        service = request.get("service", "deepseek")
        
        if service not in self.direct_api_keys or not self.direct_api_keys[service]:
            raise Exception(f"No API keys available for {service}")
        
        self.metrics["direct_api_requests"] += 1
        
        # Try each API key with rotation
        keys = self.direct_api_keys[service]
        start_index = self.key_index[service]
        
        for i in range(len(keys)):
            key_idx = (start_index + i) % len(keys)
            api_key = keys[key_idx]
            
            try:
                result = await self._call_direct_api(service, api_key, request)
                
                # Update rotation index for next request
                self.key_index[service] = (key_idx + 1) % len(keys)
                
                return result
            
            except Exception as e:
                self.logger.error(f"❌ Direct API call failed with key {key_idx + 1}: {e}")
                self.metrics["direct_api_failures"] += 1
                continue
        
        raise Exception(f"All direct API calls failed for {service}")
    
    async def _call_direct_api(self, service: str, api_key: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call Direct API with unified format conversion"""
        
        # API endpoints
        urls = {
            "deepseek": "https://api.deepseek.com/v1/chat/completions",
            "perplexity": "https://api.perplexity.ai/chat/completions"
        }
        
        # Convert MCP request format to Direct API format
        api_request = {
            "model": "deepseek-chat" if service == "deepseek" else "sonar",
            "messages": [{"role": "user", "content": request.get("query", "")}],
            "max_tokens": request.get("max_tokens", 2000),
            "temperature": request.get("temperature", 0.7)
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                urls[service],
                json=api_request,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Unify response format (convert Direct API → MCP format)
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": data.get("model", "unknown"),
                "usage": data.get("usage", {}),
                "source": "direct_api",
                "service": service
            }
    
    async def check_health_and_recover(self) -> bool:
        """Check MCP health and attempt recovery (Google SRE liveness probes)"""
        if self.current_mode == ConnectionMode.DIRECT_API:
            if not self.circuit_open or time.time() >= self.circuit_open_until:
                # Try to recover MCP connection
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(f"{self.mcp_url}/health")
                        
                        if response.status_code == 200:
                            self.logger.info("✅ MCP health check passed, switching back to MCP mode")
                            self.current_mode = ConnectionMode.MCP
                            self.circuit_open = False
                            self.failure_count = 0
                            self.metrics["circuit_closes"] += 1
                            return True
                
                except Exception as e:
                    self.logger.debug(f"MCP health check failed: {e}")
        
        return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get router metrics"""
        return {
            "current_mode": self.current_mode.value,
            "circuit_open": self.circuit_open,
            "failure_count": self.failure_count,
            "metrics": self.metrics.copy()
        }
    
    def force_mode(self, mode: ConnectionMode):
        """Force specific connection mode (for testing)"""
        self.logger.warning(f"🔧 Forcing mode to {mode.value}")
        self.current_mode = mode
        if mode == ConnectionMode.MCP:
            self.circuit_open = False
            self.failure_count = 0
