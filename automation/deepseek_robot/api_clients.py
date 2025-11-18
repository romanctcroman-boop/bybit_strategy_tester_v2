"""
🌐 Real API Clients for DeepSeek and Perplexity

Production-ready implementation with:
- Real HTTP calls via httpx
- Error handling & retry logic
- Rate limiting
- Timeout management
- Detailed logging
"""

import asyncio
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DeepSeekAPIError(Exception):
    """DeepSeek API specific error"""
    pass


class PerplexityAPIError(Exception):
    """Perplexity API specific error"""
    pass


class DeepSeekClient:
    """
    Real DeepSeek API Client
    
    Features:
    - Async HTTP calls via httpx
    - Automatic retry with exponential backoff
    - Error handling
    - Token usage tracking
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        timeout: float = 60.0,  # 🚀 ОПТИМИЗАЦИЯ: 30→60s для больших запросов
        max_retries: int = 3
    ):
        """
        Args:
            api_key: DeepSeek API key
            base_url: API base URL
            timeout: Request timeout in seconds (increased to 60s)
            max_retries: Maximum retry attempts
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_tokens_used = 0
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-coder",
        temperature: float = 0.1,
        max_tokens: int = 4000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request to DeepSeek API
        
        Args:
            messages: Chat messages [{"role": "user", "content": "..."}]
            model: Model name (deepseek-coder, deepseek-chat)
            temperature: 0-2, lower is more deterministic
            max_tokens: Maximum tokens in response
            **kwargs: Additional API parameters
        
        Returns:
            {
                "success": True,
                "response": "AI response text",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                "model": "deepseek-coder",
                "finish_reason": "stop"
            }
        
        Raises:
            DeepSeekAPIError: If API request fails after retries
        """
        url = f"{self.base_url}/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                self.total_requests += 1
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    
                    # Check status code
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Extract response
                        choice = data.get("choices", [{}])[0]
                        usage = data.get("usage", {})
                        
                        self.successful_requests += 1
                        self.total_tokens_used += usage.get("total_tokens", 0)
                        
                        result = {
                            "success": True,
                            "response": choice.get("message", {}).get("content", ""),
                            "usage": usage,
                            "model": data.get("model", model),
                            "finish_reason": choice.get("finish_reason", "unknown"),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        logger.info(
                            f"✅ DeepSeek API success: {usage.get('total_tokens', 0)} tokens"
                        )
                        
                        return result
                    
                    elif response.status_code == 429:
                        # Rate limit exceeded
                        retry_after = int(response.headers.get("Retry-After", 5))
                        logger.warning(f"⚠️  Rate limit hit, retry after {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    elif response.status_code >= 500:
                        # Server error, retry
                        logger.warning(f"⚠️  Server error {response.status_code}, retrying...")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    
                    else:
                        # Client error (400, 401, 403, etc.)
                        error_data = response.json() if response.text else {}
                        error_msg = error_data.get("error", {}).get("message", response.text)
                        
                        self.failed_requests += 1
                        
                        raise DeepSeekAPIError(
                            f"API error {response.status_code}: {error_msg}"
                        )
            
            except httpx.TimeoutException:
                logger.warning(f"⚠️  Request timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.failed_requests += 1
                    raise DeepSeekAPIError("Request timeout after retries")
            
            except httpx.NetworkError as e:
                logger.warning(f"⚠️  Network error: {e} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.failed_requests += 1
                    raise DeepSeekAPIError(f"Network error after retries: {e}")
            
            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}")
                self.failed_requests += 1
                raise DeepSeekAPIError(f"Unexpected error: {e}")
        
        # Should not reach here
        self.failed_requests += 1
        raise DeepSeekAPIError("Max retries exceeded")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        success_rate = (
            self.successful_requests / self.total_requests
            if self.total_requests > 0
            else 0
        )
        
        return {
            "total_requests": self.total_requests,
            "successful": self.successful_requests,
            "failed": self.failed_requests,
            "success_rate": f"{success_rate:.1%}",
            "total_tokens": self.total_tokens_used,
            "avg_tokens_per_request": (
                self.total_tokens_used / self.successful_requests
                if self.successful_requests > 0
                else 0
            )
        }


class PerplexityClient:
    """
    Real Perplexity API Client (Sonar Pro)
    
    Features:
    - Real-time web search integration
    - Source citations
    - Async HTTP calls
    - Error handling
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.perplexity.ai",
        timeout: float = 60.0,  # 🚀 ОПТИМИЗАЦИЯ: 30→60s для web search
        max_retries: int = 3
    ):
        """
        Args:
            api_key: Perplexity API key
            base_url: API base URL
            timeout: Request timeout in seconds (increased to 60s)
            max_retries: Maximum retry attempts
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
    
    async def search(
        self,
        query: str,
        model: str = "sonar-pro",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Search via Perplexity API
        
        Args:
            query: Search query
            model: Model name (sonar, sonar-pro)
            **kwargs: Additional parameters
        
        Returns:
            {
                "success": True,
                "response": "AI response with web search",
                "sources": ["https://...", "https://..."],
                "citations": [...],
                "model": "sonar-pro"
            }
        
        Raises:
            PerplexityAPIError: If API request fails after retries
        """
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": query
                }
            ],
            **kwargs
        }
        
        # Retry logic
        for attempt in range(self.max_retries):
            try:
                self.total_requests += 1
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        choice = data.get("choices", [{}])[0]
                        
                        self.successful_requests += 1
                        
                        result = {
                            "success": True,
                            "response": choice.get("message", {}).get("content", ""),
                            "sources": data.get("sources", []),
                            "citations": data.get("citations", []),
                            "model": data.get("model", model),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        logger.info(
                            f"✅ Perplexity API success: {len(result['sources'])} sources"
                        )
                        
                        return result
                    
                    elif response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 5))
                        logger.warning(f"⚠️  Rate limit hit, retry after {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    elif response.status_code >= 500:
                        logger.warning(f"⚠️  Server error {response.status_code}, retrying...")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    
                    else:
                        error_data = response.json() if response.text else {}
                        error_msg = error_data.get("error", {}).get("message", response.text)
                        
                        self.failed_requests += 1
                        
                        raise PerplexityAPIError(
                            f"API error {response.status_code}: {error_msg}"
                        )
            
            except httpx.TimeoutException:
                logger.warning(f"⚠️  Request timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.failed_requests += 1
                    raise PerplexityAPIError("Request timeout after retries")
            
            except httpx.NetworkError as e:
                logger.warning(f"⚠️  Network error: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.failed_requests += 1
                    raise PerplexityAPIError(f"Network error after retries: {e}")
            
            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}")
                self.failed_requests += 1
                raise PerplexityAPIError(f"Unexpected error: {e}")
        
        self.failed_requests += 1
        raise PerplexityAPIError("Max retries exceeded")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        success_rate = (
            self.successful_requests / self.total_requests
            if self.total_requests > 0
            else 0
        )
        
        return {
            "total_requests": self.total_requests,
            "successful": self.successful_requests,
            "failed": self.failed_requests,
            "success_rate": f"{success_rate:.1%}"
        }
