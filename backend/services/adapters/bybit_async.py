"""
Async Bybit API adapter for parallel data fetching.

Provides asynchronous methods for:
- Parallel symbol loading
- Batch kline fetching
- Concurrent historical data retrieval

Features:
- aiohttp for async HTTP
- Concurrent request limiting
- Redis cache integration
- Prometheus metrics
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import time

from backend.core.config import get_config
from backend.core.logging_config import get_logger
from backend.core.exceptions import (
    BybitAPIError,
    BybitRateLimitError,
    BybitConnectionError,
    BybitTimeoutError,
    handle_bybit_error
)
from backend.core.metrics import (
    record_api_fetch,
    record_cache_hit,
    record_cache_miss,
    record_historical_fetch,
    bybit_api_requests_total,
    bybit_api_duration_seconds
)
from backend.core.cache import get_cache, make_cache_key

config = get_config()
logger = get_logger(__name__)


class AsyncBybitAdapter:
    """
    Asynchronous Bybit API adapter.
    
    Provides high-performance parallel data fetching with:
    - Concurrent request limiting
    - Automatic rate limiting
    - Redis caching
    - Error handling & retries
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: int = 10,
        max_concurrent: int = 5,
        rate_limit_delay: float = 0.2
    ):
        """
        Initialize async adapter.
        
        Args:
            api_key: Bybit API key (optional)
            api_secret: Bybit API secret (optional)
            timeout: Request timeout in seconds
            max_concurrent: Max concurrent requests
            rate_limit_delay: Delay between requests in seconds
        """
        self.api_key = api_key or config.API_KEY
        self.api_secret = api_secret or config.API_SECRET
        self.timeout = timeout or config.API_TIMEOUT
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay or config.RATE_LIMIT_DELAY
        
        # Semaphore for concurrent request limiting
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        # Redis cache
        self.redis_cache = None
        if config.REDIS_ENABLED:
            try:
                self.redis_cache = get_cache()
            except Exception as e:
                logger.warning(f"Redis cache init failed: {e}")
        
        # Session (created per fetch)
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(
            "AsyncBybitAdapter initialized",
            extra={
                'max_concurrent': max_concurrent,
                'timeout': timeout,
                'rate_limit_delay': rate_limit_delay
            }
        )
    
    async def _ensure_session(self):
        """Create aiohttp session if not exists."""
        if self._session is None or self._session.closed:
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout_config,
                headers={
                    'User-Agent': 'BybitStrategyTester/2.0-Async',
                    'Accept': 'application/json'
                }
            )
    
    async def close(self):
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def __aenter__(self):
        """Context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
    
    def _normalize_kline_row(self, row: Any) -> Dict[str, Any]:
        """
        Normalize kline row to standard format.
        
        Args:
            row: Raw kline data from API
            
        Returns:
            Normalized dict with keys: open_time, open, high, low, close, volume
        """
        if isinstance(row, dict):
            return {
                "open_time": row.get("timestamp") or row.get("open_time") or row.get("start_time"),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
            }
        
        # Array format [timestamp, open, high, low, close, volume, ...]
        if isinstance(row, (list, tuple)) and len(row) >= 6:
            return {
                "open_time": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
        
        logger.warning(f"Unknown kline format: {row}")
        return {}
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1",
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Fetch klines for single symbol asynchronously.
        
        Args:
            symbol: Trading symbol
            interval: Time interval (1, 15, 60, D, etc.)
            limit: Number of candles
            
        Returns:
            List of normalized kline dicts
        """
        # Check cache first
        if self.redis_cache:
            cache_key = make_cache_key(symbol, interval, limit)
            cached = self.redis_cache.get(cache_key, symbol, interval)
            if cached:
                logger.debug(f"Cache hit: {symbol} {interval}")
                return cached
        
        await self._ensure_session()
        
        # Rate limiting
        async with self._semaphore:
            start_time = time.time()
            
            try:
                url = "https://api.bybit.com/v5/market/kline"
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "interval": interval,
                    "limit": limit
                }
                
                async with self._session.get(url, params=params) as response:
                    duration = time.time() - start_time
                    
                    # Record metrics
                    bybit_api_requests_total.labels(
                        symbol=symbol,
                        interval=interval,
                        endpoint='kline',
                        status='success' if response.status == 200 else 'error'
                    ).inc()
                    
                    bybit_api_duration_seconds.labels(
                        symbol=symbol,
                        interval=interval,
                        endpoint='kline'
                    ).observe(duration)
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API error for {symbol}: {response.status} - {error_text}")
                        raise BybitAPIError(
                            f"HTTP {response.status}",
                            ret_code=response.status,
                            ret_msg=error_text
                        )
                    
                    data = await response.json()
                    result = data.get("result", {})
                    klines = result.get("list", [])
                    
                    if not klines:
                        logger.warning(f"No klines returned for {symbol} {interval}")
                        return []
                    
                    normalized = [self._normalize_kline_row(k) for k in klines]
                    
                    # Record metrics
                    record_api_fetch(symbol, interval, len(normalized))
                    
                    # Cache result
                    if self.redis_cache:
                        cache_key = make_cache_key(symbol, interval, limit)
                        self.redis_cache.set(cache_key, normalized, symbol=symbol, interval=interval)
                    
                    logger.info(f"Fetched {len(normalized)} klines for {symbol} {interval}")
                    
                    # Rate limiting delay
                    await asyncio.sleep(self.rate_limit_delay)
                    
                    return normalized
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching {symbol} {interval}")
                raise BybitTimeoutError(f"Timeout for {symbol}")
            
            except aiohttp.ClientError as e:
                logger.error(f"Connection error for {symbol}: {e}")
                raise BybitConnectionError(str(e))
    
    async def get_klines_batch(
        self,
        symbols: List[str],
        interval: str = "1",
        limit: int = 200
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch klines for multiple symbols in parallel.
        
        Args:
            symbols: List of trading symbols
            interval: Time interval
            limit: Number of candles per symbol
            
        Returns:
            Dict mapping symbol -> klines list
        """
        tasks = [
            self.get_klines(symbol, interval, limit)
            for symbol in symbols
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dict
        output = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {symbol}: {result}")
                output[symbol] = []
            else:
                output[symbol] = result
        
        return output
    
    async def get_historical_klines(
        self,
        symbol: str,
        interval: str = "1",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_requests: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical klines with pagination.
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            start_time: Start datetime (default: 30 days ago)
            end_time: End datetime (default: now)
            max_requests: Max API requests
            
        Returns:
            Combined list of klines
        """
        if start_time is None:
            start_time = datetime.now() - timedelta(days=30)
        if end_time is None:
            end_time = datetime.now()
        
        all_klines = []
        api_requests = 0
        fetch_start = time.time()
        
        current_end = end_time
        limit = 1000  # Max per request
        
        while api_requests < max_requests:
            klines = await self.get_klines(symbol, interval, limit)
            
            if not klines:
                break
            
            all_klines.extend(klines)
            api_requests += 1
            
            # Check if we reached start_time
            oldest_time = min(k.get('open_time', float('inf')) for k in klines)
            if oldest_time <= int(start_time.timestamp() * 1000):
                break
            
            # Update current_end for next iteration
            current_end = datetime.fromtimestamp(oldest_time / 1000)
            
            logger.debug(f"Fetched batch {api_requests}: {len(klines)} klines")
        
        # Record metrics
        duration = time.time() - fetch_start
        record_historical_fetch(
            symbol,
            interval,
            duration,
            api_requests,
            len(all_klines)
        )
        
        logger.info(
            f"Historical fetch complete: {symbol} {interval}",
            extra={
                'candles': len(all_klines),
                'api_requests': api_requests,
                'duration': round(duration, 2)
            }
        )
        
        return all_klines


# Convenience function
async def fetch_multiple_symbols(
    symbols: List[str],
    interval: str = "1",
    limit: int = 200
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch klines for multiple symbols using async adapter.
    
    Args:
        symbols: List of symbols to fetch
        interval: Time interval
        limit: Candles per symbol
        
    Returns:
        Dict mapping symbol -> klines
    
    Example:
        >>> result = await fetch_multiple_symbols(['BTCUSDT', 'ETHUSDT'], '15', 1000)
        >>> btc_candles = result['BTCUSDT']
    """
    async with AsyncBybitAdapter() as adapter:
        return await adapter.get_klines_batch(symbols, interval, limit)
