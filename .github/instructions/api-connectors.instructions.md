---
applyTo: "**/adapters/**/*.py"
---

# API Connector Rules (Bybit & External APIs)


## Error Handling - MANDATORY

EVERY API call wrapped in:

```python
from loguru import logger
from backend.utils.exceptions import NetworkError, RateLimitError, APIError

try:
    response = await client.request(...)
    if response.get('retCode') != 0:
        raise APIError(response.get('retMsg', 'Unknown API error'))
except (NetworkError, RateLimitError, TimeoutError) as e:
    logger.error(f"API call failed: {e}", exc_info=True)
    raise
```

## Rate Limiting (CRITICAL)

Bybit limits: **120 requests/minute**

Implement rate limiter:

```python
import asyncio
from collections import deque
from time import time

class RateLimiter:
    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()

    async def acquire(self):
        now = time()
        # Remove old requests
        while self.requests and self.requests[0] < now - self.window_seconds:
            self.requests.popleft()

        if len(self.requests) >= self.max_requests:
            wait_time = self.window_seconds - (now - self.requests[0])
            logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

        self.requests.append(now)
```

## Authentication

- Load from environment: `os.getenv('BYBIT_API_KEY')`
- NEVER commit: `.env` in `.gitignore`
- Validate at startup: check keys not empty
- Use `backend/config/settings.py` for secure loading

```python
from backend.config.settings import settings

# Correct
api_key = settings.BYBIT_API_KEY

# NEVER do this
api_key = "sk-xxxx..."  # SECURITY VIOLATION
```

## Logging Standards

```python
from loguru import logger

# Before API call
logger.info(f"API call: {endpoint} | symbol={symbol} | timeframe={timeframe}")

# After successful response
logger.debug(f"Response: status={response.status_code} | data_length={len(data)}")

# On error
logger.error(f"API error: {endpoint} | error={error}", exc_info=True)
```

## Retry Logic

```python
import asyncio
from functools import wraps

def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for API calls with exponential backoff"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except RateLimitError:
                    wait_time = base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt+1})")
                    await asyncio.sleep(wait_time)
                except (NetworkError, TimeoutError) as e:
                    last_error = e
                    if attempt == max_retries - 1:
                        raise
                    wait_time = base_delay * (2 ** attempt)
                    logger.error(f"Network error (attempt {attempt+1}/{max_retries}): {e}")
                    await asyncio.sleep(wait_time)
            raise last_error
        return wrapper
    return decorator
```

**Retry on:** 429 (rate limit), 5xx (server errors)
**Don't retry:** 4xx (client errors except 429)

## WebSocket Connections

```python
import websockets
from loguru import logger

class BybitWebSocket:
    def __init__(self, url: str):
        self.url = url
        self.should_run = True
        self.reconnect_delay = 5

    async def maintain_connection(self):
        """Keep WebSocket alive with reconnection logic"""
        while self.should_run:
            try:
                async with websockets.connect(self.url) as ws:
                    logger.info(f"WebSocket connected to {self.url}")
                    await self._handle_messages(ws)
            except websockets.ConnectionClosed as e:
                logger.warning(f"WS connection closed: {e.code}, reconnecting in {self.reconnect_delay}s")
                await asyncio.sleep(self.reconnect_delay)
            except Exception as e:
                logger.error(f"WS error: {e}, reconnecting in {self.reconnect_delay}s")
                await asyncio.sleep(self.reconnect_delay)
```

## Response Validation

```python
from pydantic import BaseModel, validator

class BybitKlineResponse(BaseModel):
    retCode: int
    retMsg: str
    result: dict

    @validator('retCode')
    def check_success(cls, v):
        if v != 0:
            raise ValueError(f"API error code: {v}")
        return v
```

## DO NOT

- Hardcode API keys or secrets
- Make API calls without rate limiting
- Ignore error responses
- Skip logging for API interactions
- Use synchronous requests (use aiohttp/httpx)
- Forget timeout on requests (default: 30s)
