"""
Cache Warmup Module

Handles SmartKline cache warmup on application startup.
Extracted from app.py lifespan for better modularity.
"""

import concurrent.futures
import logging
import time

logger = logging.getLogger(__name__)

# Core pairs for startup warmup
DEFAULT_WARMUP_PAIRS: list[tuple[str, str]] = [
    ("BTCUSDT", "15"),
    ("BTCUSDT", "60"),
    ("BTCUSDT", "D"),  # Daily for volatility/risk calculations
]


def warmup_cache(
    pairs: list[tuple[str, str]] = None,
    timeout_seconds: int = 10,
    limit: int = 500,
) -> bool:
    """
    Warm up SmartKline cache for specified symbol/interval pairs.

    Args:
        pairs: List of (symbol, interval) tuples to warm up
        timeout_seconds: Maximum time to wait for warmup (default 10s)
        limit: Number of candles to fetch per pair (default 500)

    Returns:
        True if warmup completed (or timed out gracefully), False on error
    """
    import os

    # Check if warmup is disabled
    if os.environ.get("SKIP_CACHE_WARMUP") == "1":
        logger.info("SmartKline cache warmup SKIPPED (SKIP_CACHE_WARMUP=1)")
        return True

    if pairs is None:
        pairs = DEFAULT_WARMUP_PAIRS

    try:
        from backend.services.smart_kline_service import SMART_KLINE_SERVICE

        def _warmup():
            start = time.time()
            for symbol, interval in pairs:
                try:
                    candles = SMART_KLINE_SERVICE.get_candles(symbol, interval, limit)
                    if candles:
                        logger.info(
                            "Warmed: %s:%s (%s candles)",
                            symbol,
                            interval,
                            len(candles),
                        )
                except Exception as e:
                    # Non-critical: warmup may fail on individual symbols
                    logger.info("Warmup skipped %s:%s: %s", symbol, interval, e)
            elapsed = time.time() - start
            logger.info("SmartKline cache warmup completed in %.1fs", elapsed)

        # Run warmup with timeout - don't block startup
        logger.info("SmartKline cache warmup starting...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_warmup)
            try:
                future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                logger.info(
                    f"SmartKline cache warmup timed out ({timeout_seconds}s), continuing..."
                )

        return True

    except Exception as e:
        logger.info(f"SmartKline cache warmup skipped: {e}")
        return False


__all__ = ["DEFAULT_WARMUP_PAIRS", "warmup_cache"]
