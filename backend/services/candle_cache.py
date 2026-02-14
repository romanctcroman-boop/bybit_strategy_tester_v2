"""
Candle cache service for efficient market data management.

This module provides in-memory caching of candle data with automatic
loading from Bybit API and persistence to database.
"""

import logging
from datetime import UTC

logger = logging.getLogger(__name__)


class CandleCache:
    """
    In-memory cache for candle (OHLCV) data with lazy loading and persistence.

    Architecture:
    - Keeps last RAM_LIMIT candles in memory per symbol+interval
    - Loads up to LOAD_LIMIT candles from Bybit on first access
    - Persists loaded data to database for historical analysis
    - Working set: fast access to recent candles for real-time trading

    Usage:
        data = CANDLE_CACHE.get_working_set("BTCUSDT", "15")
        if not data:
            data = CANDLE_CACHE.load_initial("BTCUSDT", "15", persist=True)
    """

    # Configuration constants
    LOAD_LIMIT = 1000  # Maximum candles to load from API on init
    RAM_LIMIT = 500  # Maximum candles to keep in memory per symbol+interval

    def __init__(self):
        """Initialize empty cache store."""
        self._store: dict[str, list[dict]] = {}
        logger.info(
            "CandleCache initialized (LOAD_LIMIT=%d, RAM_LIMIT=%d)",
            self.LOAD_LIMIT,
            self.RAM_LIMIT,
        )

    def _key(self, symbol: str, interval: str) -> str:
        """Generate cache key from symbol and interval."""
        return f"{symbol}:{interval}"

    def get_working_set(
        self, symbol: str, interval: str, ensure_loaded: bool = True
    ) -> list[dict] | None:
        """
        Get working set of candles from cache.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Timeframe interval (e.g., "1", "15", "60", "D")
            ensure_loaded: If True and cache empty, triggers load_initial

        Returns:
            List of candle dicts [{ time, open, high, low, close, volume? }]
            or None if not cached and ensure_loaded=False
        """
        key = self._key(symbol, interval)
        data = self._store.get(key)

        if data is None and ensure_loaded:
            logger.info(
                "Cache miss for %s, loading initial data (ensure_loaded=True)", key
            )
            return self.load_initial(symbol, interval, persist=True)

        if data:
            logger.debug("Cache hit for %s: %d candles", key, len(data))
        else:
            logger.debug("Cache miss for %s (ensure_loaded=False)", key)

        return data

    def load_initial(
        self,
        symbol: str,
        interval: str,
        load_limit: int | None = None,
        persist: bool = False,
    ) -> list[dict]:
        """
        Load initial candle data from Bybit API.

        This method:
        1. Fetches up to load_limit candles from Bybit
        2. Optionally persists to database (if persist=True)
        3. Stores last RAM_LIMIT candles in memory
        4. Returns the working set

        Args:
            symbol: Trading pair symbol
            interval: Timeframe interval
            load_limit: Max candles to fetch (default: LOAD_LIMIT)
            persist: If True, save candles to database

        Returns:
            List of candle dicts (last RAM_LIMIT candles)
        """
        if load_limit is None:
            load_limit = self.LOAD_LIMIT

        key = self._key(symbol, interval)

        try:
            # Import here to avoid circular dependency
            from backend.services.adapters.bybit import BybitAdapter

            logger.info(
                "Loading initial data for %s (limit=%d, persist=%s)",
                key,
                load_limit,
                persist,
            )

            # Fetch from Bybit API
            client = BybitAdapter()
            candles = client.get_klines(
                symbol=symbol, interval=interval, limit=min(load_limit, self.LOAD_LIMIT)
            )

            if not candles:
                logger.warning("No candles returned from Bybit for %s", key)
                self._store[key] = []
                return []

            logger.info("Fetched %d candles from Bybit for %s", len(candles), key)

            # Persist to database if requested
            if persist:
                try:
                    self._persist_candles(symbol, interval, candles)
                except Exception as exc:
                    logger.error("Failed to persist candles for %s: %s", key, exc)
                    # Continue even if persistence fails

            # Keep only last RAM_LIMIT candles in memory
            working_set = (
                candles[-self.RAM_LIMIT :] if len(candles) > self.RAM_LIMIT else candles
            )
            self._store[key] = working_set

            logger.info(
                "Loaded %d candles into cache for %s (kept last %d)",
                len(candles),
                key,
                len(working_set),
            )

            return working_set

        except Exception as exc:
            logger.exception("Failed to load initial data for %s: %s", key, exc)
            # Store empty list to avoid repeated failures
            self._store[key] = []
            return []

    def reset(
        self, symbol: str, interval: str, reload: bool = False
    ) -> list[dict] | None:
        """
        Clear cache for symbol+interval.

        Args:
            symbol: Trading pair symbol
            interval: Timeframe interval
            reload: If True, immediately reload data after clearing

        Returns:
            Reloaded data if reload=True, else None
        """
        key = self._key(symbol, interval)

        if key in self._store:
            logger.info("Resetting cache for %s", key)
            del self._store[key]

        if reload:
            logger.info("Reloading cache for %s", key)
            return self.load_initial(symbol, interval, persist=True)

        return None

    def _persist_candles(self, symbol: str, interval: str, candles: list[dict]):
        """
        Persist candles to database.

        This is a simplified implementation. In production, you would:
        - Use proper database models (Candle model)
        - Implement upsert logic to handle duplicates
        - Batch insert for performance
        - Handle different timeframe formats

        Args:
            symbol: Trading pair symbol
            interval: Timeframe interval
            candles: List of candle dicts to persist
        """
        try:
            from datetime import datetime

            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit

            with SessionLocal() as session:
                inserted_count = 0
                for candle in candles:
                    # Extract timestamp (handle both 'time' and 'open_time' keys)
                    open_time = candle.get("open_time") or candle.get("time", 0)
                    if isinstance(open_time, float):
                        open_time = int(open_time * 1000)  # Convert seconds to ms
                    elif open_time < 1e12:
                        open_time = int(
                            open_time * 1000
                        )  # Likely seconds, convert to ms

                    # Check if already exists
                    exists = (
                        session.query(BybitKlineAudit)
                        .filter(
                            BybitKlineAudit.symbol == symbol,
                            BybitKlineAudit.open_time == open_time,
                        )
                        .first()
                    )

                    if exists:
                        continue  # Skip duplicates

                    # Create new record
                    record = BybitKlineAudit(
                        symbol=symbol,
                        open_time=open_time,
                        open_time_dt=datetime.fromtimestamp(
                            open_time / 1000, tz=UTC
                        ),
                        open_price=float(candle.get("open", 0)),
                        high_price=float(candle.get("high", 0)),
                        low_price=float(candle.get("low", 0)),
                        close_price=float(candle.get("close", 0)),
                        volume=float(candle.get("volume", 0)),
                        turnover=float(candle.get("turnover", 0)),
                    )
                    record.set_raw(candle)
                    session.add(record)
                    inserted_count += 1

                session.commit()
                logger.info(
                    "Persisted %d/%d candles for %s:%s",
                    inserted_count,
                    len(candles),
                    symbol,
                    interval,
                )
        except ImportError as e:
            logger.warning("Database modules not available: %s", e)
        except Exception as e:
            logger.error("Failed to persist candles for %s:%s: %s", symbol, interval, e)


# Global singleton instance
CANDLE_CACHE = CandleCache()
