"""
DeepSeek API Client
Simplified client for health checks
"""

import os

import httpx


class DeepSeekClient:
    """DeepSeek API client for health checks"""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = "https://api.deepseek.com/v1"
        self.timeout = 10.0
    
    async def test_connection(self) -> bool:
        """Test connection to DeepSeek API"""
        if not self.api_key:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception:
            return False
    
    async def check_health(self) -> dict:
        """Check API health status"""
        is_healthy = await self.test_connection()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "DeepSeek API",
            "available": is_healthy
        }
