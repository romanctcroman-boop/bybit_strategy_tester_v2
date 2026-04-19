# Code Patterns

## Strategy Template

```python
from backend.backtesting.strategies.base import BaseStrategy
from typing import Dict, Optional
import pandas as pd
import pandas_ta as ta

class NewStrategy(BaseStrategy):
    """Strategy description"""

    def __init__(self, params: Dict[str, float]):
        super().__init__(params)
        self.required_params = ['param1', 'param2']
        self._validate_params()

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate entry/exit signals"""
        signals = data.copy()
        # Implementation
        return signals
```

## FastAPI Endpoint

```python
from fastapi import APIRouter, Depends, HTTPException
from backend.api.schemas import RequestModel, ResponseModel
from loguru import logger

router = APIRouter(prefix="/api/v1", tags=["feature"])

@router.post("/endpoint", response_model=ResponseModel)
async def endpoint(request: RequestModel):
    """Endpoint description"""
    try:
        # Implementation
        return ResponseModel(...)
    except Exception as e:
        logger.error(f"Endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## Error Handling

```python
from loguru import logger
import asyncio

def robust_operation(func):
    """Decorator for operations with retry logic"""
    async def wrapper(*args, **kwargs):
        retries = 3
        for attempt in range(retries):
            try:
                return await func(*args, **kwargs)
            except RateLimitError:
                wait_time = 2 ** attempt
                logger.warning(f"Rate limited, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
            except NetworkError as e:
                if attempt == retries - 1:
                    raise
                logger.error(f"Network error (attempt {attempt+1}/{retries}): {e}")
        return None
    return wrapper
```

## Bybit API Pattern

```python
# ALWAYS use this pattern:
try:
    response = await bybit_client.fetch_data(symbol, timeframe)
    if response.get('retCode') != 0:
        raise APIError(response.get('retMsg'))
except (NetworkError, RateLimitError, Timeout) as e:
    logger.error(f"Bybit API error: {e}")
    # implement retry logic with exponential backoff
```

- Rate limit: 120 requests/min
- NEVER hardcode keys (use environment variables)
- Log ALL API calls (timestamp, endpoint, response code)
