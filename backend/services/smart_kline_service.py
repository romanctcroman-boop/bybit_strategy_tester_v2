"""
Smart Kline Service - Intelligent Historical Data Management

System Requirements:
1. First pair selection loads 12 months of history on selected timeframe
2. Automatically loads adjacent timeframes (e.g., 30m → also 15m and 1h)
3. Keep 500 candles in memory per symbol+interval for fast access
4. Database stores all historical data
5. Auto-update mechanism to keep data fresh
6. Minimize API calls by using cached/DB data when available

Architecture:
- On first load: Check DB → if missing, fetch 12 months from Bybit
- Adjacent timeframes loaded in background
- RAM keeps only working set (500 candles)
- Background task updates data periodically
"""

import asyncio
import contextlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

from backend.config.database_policy import (
    DATA_START_TIMESTAMP_MS,
    MAX_RETENTION_DAYS,
    RETENTION_CHECK_DAYS,
    RETENTION_YEARS,
)

logger = logging.getLogger(__name__)

# Strong references to background tasks — prevents GC before completion (RUF006)
_background_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coroutine) -> asyncio.Task:
    task = asyncio.create_task(coroutine)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


# Timeframe relationships for adjacent loading
TIMEFRAME_ADJACENCY = {
    "1": ["1", "3", "5"],  # 1m → 1m, 3m, 5m
    "3": ["1", "3", "5"],  # 3m → 1m, 3m, 5m
    "5": ["3", "5", "15"],  # 5m → 3m, 5m, 15m
    "15": ["5", "15", "30"],  # 15m → 5m, 15m, 30m
    "30": ["15", "30", "60"],  # 30m → 15m, 30m, 1h
    "60": ["30", "60", "120"],  # 1h → 30m, 1h, 2h
    "120": ["60", "120", "240"],  # 2h → 1h, 2h, 4h
    "240": ["120", "240", "D"],  # 4h → 2h, 4h, D
    "D": ["240", "D", "W"],  # D → 4h, D, W
    "W": ["D", "W"],  # W → D, W
}

# Timeframes always loaded when creating/editing a strategy
# These are needed for multi-timeframe analysis and validation
STRATEGY_REQUIRED_INTERVALS = ["1", "60"]  # 1m and 1h

# Market types for parallel data loading
# SPOT = TradingView data source (for signal generation parity)
# LINEAR = Perpetual futures (for actual trading execution)
MARKET_TYPES = ["spot", "linear"]

# How many candles are in 12 months for each timeframe
CANDLES_PER_12_MONTHS = {
    "1": 525600,  # 365 * 24 * 60 (too many, limit to 50000)
    "3": 175200,  # (too many, limit to 50000)
    "5": 105120,  # (too many, limit to 50000)
    "15": 35040,  # Reasonable
    "30": 17520,  # Good
    "60": 8760,  # Good
    "120": 4380,  # Good
    "240": 2190,  # Good
    "D": 365,  # Good
    "W": 52,  # Good
}

# Maximum candles to load per timeframe (API and storage limits)
MAX_CANDLES_TO_LOAD = {
    "1": 10000,  # ~7 days
    "3": 10000,  # ~21 days
    "5": 10000,  # ~35 days
    "15": 35040,  # 12 months
    "30": 17520,  # 12 months
    "60": 8760,  # 12 months
    "120": 4380,  # 12 months
    "240": 2190,  # 12 months
    "D": 365,  # 12 months
    "W": 104,  # 2 years
}


@dataclass
class LoadingProgress:
    """Progress of a loading operation."""

    symbol: str
    interval: str
    status: str = "pending"  # pending, loading, completed, failed
    total_candles: int = 0
    loaded_candles: int = 0
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None

    @property
    def progress_percent(self) -> float:
        if self.total_candles == 0:
            return 0.0
        return (self.loaded_candles / self.total_candles) * 100


@dataclass
class SymbolState:
    """State of a loaded symbol."""

    symbol: str
    loaded_intervals: set[str] = field(default_factory=set)
    db_coverage: dict[str, tuple] = field(default_factory=dict)  # interval -> (oldest, newest)
    last_update: datetime | None = None
    is_primary: bool = False  # If this is the main selected symbol


class SmartKlineService:
    """
    Smart Kline Service for efficient market data management.

    Features:
    - Loads 12 months of history on first access
    - Pre-loads adjacent timeframes
    - Keeps 500 candles in RAM per symbol+interval
    - Uses database as persistent cache
    - Background updates to keep data fresh

    Note: Data retention policy constants are imported from
    backend.config.database_policy for consistency across all services.
    """

    _instance: Optional["SmartKlineService"] = None
    RAM_LIMIT = 500  # Candles to keep in memory
    REPAIR_INTERVAL_HOURS = 6  # How often to check for gaps
    # Retention constants now imported from backend.config.database_policy

    def __init__(self):
        self._ram_cache: dict[str, list[dict]] = {}  # key -> candles
        self._symbol_states: dict[str, SymbolState] = {}
        self._loading_progress: dict[str, LoadingProgress] = {}
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._update_task: asyncio.Task | None = None
        self._repair_task: asyncio.Task | None = None
        self._running = False
        self._adapter = None
        self._db_service = None
        self._quality_service = None  # DataQualityService for anomaly detection
        self._last_repair_check: datetime | None = None
        self._last_retention_check: datetime | None = None
        logger.info("SmartKlineService initialized")

    @classmethod
    def get_instance(cls) -> "SmartKlineService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_db_service(self):
        """Get or create KlineDBService instance."""
        if self._db_service is None:
            try:
                from backend.services.kline_db_service import KlineDBService

                self._db_service = KlineDBService.get_instance()
                if not self._db_service._running.is_set():
                    self._db_service.start()
                logger.info("KlineDBService connected")
            except Exception as e:
                logger.warning(f"KlineDBService not available: {e}")
                self._db_service = None
        return self._db_service

    def _get_adapter(self):
        """Get or create BybitAdapter."""
        if self._adapter is None:
            from backend.services.adapters.bybit import BybitAdapter

            api_key = os.environ.get("BYBIT_API_KEY")
            api_secret = os.environ.get("BYBIT_API_SECRET")
            self._adapter = BybitAdapter(api_key=api_key, api_secret=api_secret)
        return self._adapter

    def _get_repository_adapter(self):
        """
        Get or create RepositoryAdapter for optimized database access.

        Uses new Repository pattern for better performance and consistency.
        Falls back to direct SQLAlchemy if not available.
        """
        if not hasattr(self, "_repository_adapter"):
            self._repository_adapter = None
        if self._repository_adapter is None:
            try:
                from backend.services.kline_repository_adapter import (
                    get_repository_adapter,
                )

                db_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "data.sqlite3",
                )
                self._repository_adapter = get_repository_adapter(f"sqlite:///{db_path}")
                logger.debug("RepositoryAdapter connected")
            except Exception as e:
                logger.debug(f"RepositoryAdapter not available: {e}")
                self._repository_adapter = None
        return self._repository_adapter

    def _get_quality_service(self):
        """Get or create DataQualityService for anomaly detection."""
        if self._quality_service is None:
            try:
                from backend.services.data_quality_service import DATA_QUALITY_SERVICE

                self._quality_service = DATA_QUALITY_SERVICE
                logger.info("DataQualityService connected")
            except Exception as e:
                logger.debug(f"DataQualityService not available: {e}")
                self._quality_service = None
        return self._quality_service

    def _normalize_interval(self, interval: str) -> str:
        """Normalize interval aliases to standard format.

        Converts:
        - '1h' -> '60'
        - '4h' -> '240'
        - '1m' -> '1'
        - etc.
        """
        interval_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "2h": "120",
            "4h": "240",
            "6h": "360",
            "12h": "720",
            "1d": "D",
            "1w": "W",
        }
        return interval_map.get(interval.lower(), interval)

    def _cache_key(self, symbol: str, interval: str) -> str:
        """Generate cache key."""
        interval = self._normalize_interval(interval)
        return f"{symbol}:{interval}"

    def _interval_to_ms(self, interval: str) -> int:
        """Convert interval string to milliseconds.

        Examples: '1' -> 60000, '15' -> 900000, '60' -> 3600000, 'D' -> 86400000
        """
        interval_str = str(interval).upper()

        # Daily/Weekly/Monthly
        if interval_str == "D":
            return 24 * 60 * 60 * 1000  # 1 day
        elif interval_str == "W":
            return 7 * 24 * 60 * 60 * 1000  # 1 week
        elif interval_str == "M":
            return 30 * 24 * 60 * 60 * 1000  # ~1 month

        # Minutes
        try:
            minutes = int(interval_str)
            return minutes * 60 * 1000
        except ValueError:
            # Fallback: assume 1 hour
            return 60 * 60 * 1000

    # =========================================================================
    # Core API Methods
    # =========================================================================

    def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        from_db: bool = False,
        force_fresh: bool = False,
    ) -> list[dict]:
        """
        Get candles for display. Returns last `limit` candles.

        First checks RAM cache, then DB, then fetches from API.
        Always validates freshness - last candle must be within 1x timeframe of current time.

        Args:
            force_fresh: If True, always fetch from API to ensure latest data
        """
        # Normalize interval (e.g., '1h' -> '60')
        interval = self._normalize_interval(interval)
        key = self._cache_key(symbol, interval)

        # If force_fresh, skip cache and fetch from API
        if force_fresh:
            logger.info(f"Force fresh requested: {key}, fetching from API")
            candles = self._fetch_from_api(symbol, interval, limit)
            if candles:
                self._ram_cache[key] = candles[-self.RAM_LIMIT :]
                self._persist_to_db(symbol, interval, candles)
            return candles

        # Calculate freshness threshold (1x interval - strict to avoid price gaps)
        # This ensures chart data stays current
        interval_ms = self._interval_to_ms(interval)
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        freshness_threshold = now_ms - interval_ms  # 1x interval tolerance

        def is_fresh(candles: list[dict]) -> bool:
            """Check if last candle is fresh enough."""
            if not candles:
                return False
            last_candle = candles[-1]
            last_time = last_candle.get("open_time", 0)
            return last_time >= freshness_threshold

        # Check RAM cache first
        if key in self._ram_cache and not from_db:
            candles = self._ram_cache[key]
            if len(candles) >= limit and is_fresh(candles):
                logger.info(f"RAM cache hit: {key} ({len(candles)} candles, fresh)")
                return candles[-limit:]
            elif len(candles) >= limit:
                logger.info(f"RAM cache stale: {key}, last candle too old")
            else:
                logger.info(f"RAM cache partial: {key} ({len(candles)}/{limit} candles)")

        # Check DB
        try:
            db_candles = self._load_from_db(symbol, interval, limit)
            if db_candles and len(db_candles) >= limit and is_fresh(db_candles):
                # Update RAM cache
                self._ram_cache[key] = db_candles[-self.RAM_LIMIT :]
                logger.info(f"DB cache hit: {key} ({len(db_candles)} candles, fresh)")
                return db_candles[-limit:]
            elif db_candles and len(db_candles) >= limit:
                logger.info(f"DB cache stale: {key}, fetching fresh data from API")
        except Exception as e:
            logger.warning(f"DB load failed for {key}: {e}")

        # Fetch from API (always fresh)
        logger.info(f"Cache miss/stale: {key}, fetching from API")
        candles = self._fetch_from_api(symbol, interval, limit)
        if candles:
            self._ram_cache[key] = candles[-self.RAM_LIMIT :]
            self._persist_to_db(symbol, interval, candles)
        return candles

    def get_historical_candles(self, symbol: str, interval: str, end_time: int, limit: int = 200) -> list[dict]:
        """
        Get historical candles before a specific time.
        Used for infinite scroll.

        IMPORTANT: Requests with overlap to prevent gaps when merging with existing data.
        The overlap ensures that even if there's a slight time discrepancy,
        the frontend will filter duplicates and have continuous data.
        """
        # Normalize interval (e.g., '1h' -> '60')
        interval = self._normalize_interval(interval)

        # Calculate overlap: 10 candles worth of time to ensure seamless merging
        interval_ms = self._interval_to_ms(interval)
        overlap_candles = 10
        overlap_time = overlap_candles * interval_ms

        # Extend end_time to include overlap (request candles slightly newer than requested)
        effective_end_time = end_time + overlap_time

        # First check DB with overlap
        try:
            db_candles = self._load_from_db_before(symbol, interval, effective_end_time, limit + overlap_candles)
            if db_candles and len(db_candles) >= limit // 2:
                logger.info(f"DB historical hit: {symbol}:{interval} before {end_time} (with overlap)")
                return db_candles
        except Exception as e:
            logger.warning(f"DB historical load failed: {e}")

        # Fetch from API with overlap
        adapter = self._get_adapter()
        try:
            candles = adapter.get_klines_before(
                symbol=symbol,
                interval=interval,
                end_time=effective_end_time,
                limit=limit + overlap_candles,
            )
            if candles:
                self._persist_to_db(symbol, interval, candles)
            return candles
        except Exception as e:
            logger.error(f"API historical fetch failed: {e}")
            return []

    async def initialize_symbol(
        self,
        symbol: str,
        primary_interval: str,
        load_history: bool = True,
        load_adjacent: bool = True,
    ) -> dict[str, Any]:
        """
        Initialize a symbol for trading.

        This is called when user first selects a trading pair.
        Loads 12 months of history and adjacent timeframes.

        Returns:
            Status dict with loading information
        """
        logger.info(f"🚀 Initializing symbol: {symbol}, interval: {primary_interval}")

        # Create symbol state
        if symbol not in self._symbol_states:
            self._symbol_states[symbol] = SymbolState(symbol=symbol)

        state = self._symbol_states[symbol]
        state.is_primary = True

        result: dict[str, Any] = {
            "symbol": symbol,
            "primary_interval": primary_interval,
            "status": "initialized",
            "intervals_loaded": [],
            "intervals_loading": [],
            "db_coverage": {},
        }

        # Determine intervals to load
        intervals_to_load = [primary_interval]
        if load_adjacent and primary_interval in TIMEFRAME_ADJACENCY:
            intervals_to_load = TIMEFRAME_ADJACENCY[primary_interval]

        # ALWAYS include daily (D) timeframe for volatility/risk calculations
        # This is required for accurate leverage risk assessment
        if "D" not in intervals_to_load:
            intervals_to_load.append("D")
            logger.info(f"[VOLATILITY] Adding daily (D) timeframe for {symbol} risk calculations")

        # ALWAYS include 1m and 1h for strategy creation/validation
        # These are required for multi-timeframe analysis
        for required_interval in STRATEGY_REQUIRED_INTERVALS:
            if required_interval not in intervals_to_load:
                intervals_to_load.append(required_interval)
                logger.info(f"[STRATEGY] Adding {required_interval}m timeframe for {symbol} strategy support")

        # Add market_types to result
        result["market_types"] = MARKET_TYPES
        result["load_both_markets"] = True  # Flag for frontend

        # Check what we already have in DB
        for interval in intervals_to_load:
            coverage = self._get_db_coverage(symbol, interval)
            if coverage is not None:
                state.db_coverage[interval] = coverage
            result["db_coverage"][interval] = (
                {"oldest": coverage[0], "newest": coverage[1], "count": coverage[2]} if coverage else None
            )

        # Load data
        if load_history:
            # Start background loading for intervals without enough data
            for interval in intervals_to_load:
                coverage = state.db_coverage.get(interval)
                target_candles = MAX_CANDLES_TO_LOAD.get(interval, 5000)

                if coverage and coverage[2] >= target_candles * 0.9:
                    # We have enough data
                    state.loaded_intervals.add(interval)
                    result["intervals_loaded"].append(interval)
                    logger.info(f"[OK] {symbol}:{interval} already has {coverage[2]} candles in DB")
                else:
                    # Need to load more
                    result["intervals_loading"].append(interval)
                    # Start background task
                    _fire_and_forget(self._load_historical_background(symbol, interval, target_candles))

        # Load initial data into RAM for primary interval
        candles = self.get_candles(symbol, primary_interval, self.RAM_LIMIT)
        result["initial_candles"] = len(candles)

        # Start data quality monitoring for this symbol/interval
        quality_service = self._get_quality_service()
        if quality_service:
            quality_service.start_monitoring(symbol, primary_interval)
            # Start background monitoring if not already running
            _fire_and_forget(quality_service.start_background_monitoring())
            logger.info(f"Started quality monitoring for {symbol}:{primary_interval}")

        return result

    async def _load_historical_background(self, symbol: str, interval: str, target_candles: int):
        """Load historical data in background."""
        key = self._cache_key(symbol, interval)

        progress = LoadingProgress(
            symbol=symbol,
            interval=interval,
            total_candles=target_candles,
            start_time=datetime.now(UTC),
            status="loading",
        )
        self._loading_progress[key] = progress

        try:
            logger.info(f"[LOADING] Background loading: {key}, target: {target_candles}")

            # Get current newest time in DB to start from there
            coverage = self._get_db_coverage(symbol, interval)
            end_time = None
            if coverage and coverage[0]:
                end_time = coverage[0]  # oldest timestamp, we go backwards

            # Use historical fetch method
            adapter = self._get_adapter()
            loop = asyncio.get_event_loop()

            candles = await loop.run_in_executor(
                self._executor,
                lambda: adapter.get_klines_historical(
                    symbol=symbol,
                    interval=interval,
                    total_candles=target_candles,
                    end_time=end_time,
                ),
            )

            if candles:
                # Persist to DB
                self._persist_to_db(symbol, interval, candles)
                progress.loaded_candles = len(candles)
                progress.status = "completed"

                # Update state
                if symbol in self._symbol_states:
                    self._symbol_states[symbol].loaded_intervals.add(interval)

                logger.info(f"[OK] Background loading complete: {key}, loaded: {len(candles)}")

                # Auto-repair gaps after loading
                _fire_and_forget(self._auto_repair_gaps(symbol, interval))
            else:
                progress.status = "failed"
                progress.error = "No candles returned"

        except Exception as e:
            logger.error(f"[ERROR] Background loading failed: {key}: {e}")
            progress.status = "failed"
            progress.error = str(e)
        finally:
            progress.end_time = datetime.now(UTC)

    async def _auto_repair_gaps(self, symbol: str, interval: str, max_gaps: int = 20) -> None:
        """
        Automatically detect and repair data gaps after loading.

        This runs in background after initial data load to ensure
        data continuity.
        """
        try:
            from backend.services.data_gap_repair import DataGapRepairService

            logger.info(f"[REPAIR] Auto-repair starting for {symbol}:{interval}")

            repair_service = DataGapRepairService()

            # Get summary first
            summary = repair_service.get_repair_summary(symbol, interval)

            if not summary.get("needs_repair"):
                logger.info(f"[OK] No gaps to repair for {symbol}:{interval}")
                return

            data_gaps = summary.get("data_gaps", 0)
            logger.info(f"[REPAIR] Found {data_gaps} gaps in {symbol}:{interval}, repairing...")

            # Run repair (limit to max_gaps to avoid long operations)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                lambda: repair_service.repair_all_gaps(
                    symbol=symbol,
                    interval=interval,
                    skip_weekends=True,
                    max_gaps=max_gaps,
                ),
            )

            if result.get("status") == "completed":
                logger.info(
                    f"[OK] Auto-repair complete for {symbol}:{interval}: "
                    f"repaired {result.get('gaps_repaired', 0)} gaps, "
                    f"inserted {result.get('total_candles_inserted', 0)} candles"
                )
            else:
                logger.warning(f"[WARN] Auto-repair for {symbol}:{interval}: {result.get('status')}")

        except ImportError:
            logger.debug("DataGapRepairService not available, skipping auto-repair")
        except Exception as e:
            logger.error(f"[ERROR] Auto-repair failed for {symbol}:{interval}: {e}")

    async def _check_and_repair_gaps_periodically(self) -> None:
        """
        Periodically check and repair gaps for all active symbols.

        Runs every REPAIR_INTERVAL_HOURS hours.
        """
        now = datetime.now(UTC)

        # Check if it's time to run repair
        if self._last_repair_check is not None:
            hours_since_last = (now - self._last_repair_check).total_seconds() / 3600
            if hours_since_last < self.REPAIR_INTERVAL_HOURS:
                return  # Not time yet

        logger.info("[REPAIR] Starting periodic gap repair check...")
        self._last_repair_check = now

        try:
            from backend.services.data_gap_repair import DataGapRepairService

            repair_service = DataGapRepairService()

            # Check all active symbols and intervals
            for symbol, state in self._symbol_states.items():
                for interval in state.loaded_intervals:
                    try:
                        summary = repair_service.get_repair_summary(symbol, interval)

                        if summary.get("needs_repair"):
                            data_gaps = summary.get("data_gaps", 0)
                            logger.info(f"[REPAIR] Found {data_gaps} gaps in {symbol}:{interval}")

                            # Run repair in background
                            _fire_and_forget(self._auto_repair_gaps(symbol, interval, max_gaps=10))
                    except Exception as e:
                        logger.warning(f"Gap check failed for {symbol}:{interval}: {e}")

            logger.info("[OK] Periodic gap repair check complete")

        except ImportError:
            logger.debug("DataGapRepairService not available")
        except Exception as e:
            logger.error(f"Periodic gap repair failed: {e}")

    async def _enforce_retention_policy(self) -> None:
        """
        Enforce sliding window retention policy per symbol/interval.

        Rules:
        1. Minimum start date: DATA_START_DATE (2025-01-01)
        2. Maximum period per symbol/interval: RETENTION_YEARS (2 years)
        3. When data exceeds 2 years, delete oldest month to make room

        Runs monthly (every RETENTION_CHECK_DAYS).
        """
        now = datetime.now(UTC)

        # Check if it's time to run retention cleanup
        if self._last_retention_check is not None:
            days_since_last = (now - self._last_retention_check).total_seconds() / 86400
            if days_since_last < RETENTION_CHECK_DAYS:
                return  # Not time yet

        logger.info(f"🧹 Starting retention policy check (max {RETENTION_YEARS} years per pair)...")
        self._last_retention_check = now

        try:
            from dateutil.relativedelta import relativedelta
            from sqlalchemy import func

            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit

            # Minimum allowed timestamp (from centralized config)
            min_allowed_ts = DATA_START_TIMESTAMP_MS
            # Maximum period in days
            max_period_days = MAX_RETENTION_DAYS

            with SessionLocal() as session:
                # Step 1: Delete anything before DATA_START_DATE (2025-01-01)
                old_count = (
                    session.query(func.count(BybitKlineAudit.id))
                    .filter(BybitKlineAudit.open_time < min_allowed_ts)
                    .scalar()
                )
                if old_count and old_count > 0:
                    session.query(BybitKlineAudit).filter(BybitKlineAudit.open_time < min_allowed_ts).delete(
                        synchronize_session=False
                    )
                    session.commit()
                    logger.info(f"🗑️ Deleted {old_count:,} candles before 2025-01-01")

                # Step 2: Get all unique symbol/interval pairs
                pairs = session.query(BybitKlineAudit.symbol, BybitKlineAudit.interval).distinct().all()

                total_deleted = 0
                for symbol, interval in pairs:
                    # Get date range for this pair
                    result = (
                        session.query(
                            func.min(BybitKlineAudit.open_time),
                            func.max(BybitKlineAudit.open_time),
                        )
                        .filter(
                            BybitKlineAudit.symbol == symbol,
                            BybitKlineAudit.interval == interval,
                        )
                        .first()
                    )

                    if not result or not result[0] or not result[1]:
                        continue

                    min_ts, max_ts = result
                    min_date = datetime.utcfromtimestamp(min_ts / 1000).replace(tzinfo=UTC)
                    max_date = datetime.utcfromtimestamp(max_ts / 1000).replace(tzinfo=UTC)
                    period_days = (max_date - min_date).days

                    # If period exceeds 2 years, trim oldest month
                    if period_days > max_period_days:
                        # Calculate cutoff: delete first month of data
                        cutoff_date = min_date + relativedelta(months=1)
                        cutoff_ts = int(cutoff_date.timestamp() * 1000)

                        deleted = (
                            session.query(BybitKlineAudit)
                            .filter(
                                BybitKlineAudit.symbol == symbol,
                                BybitKlineAudit.interval == interval,
                                BybitKlineAudit.open_time < cutoff_ts,
                            )
                            .delete(synchronize_session=False)
                        )
                        session.commit()

                        if deleted:
                            total_deleted += deleted
                            logger.info(
                                f"[CLEANUP] {symbol}/{interval}: trimmed {deleted:,} candles "
                                f"(period was {period_days} days, removed {min_date.strftime('%Y-%m')})"
                            )

                if total_deleted > 0:
                    logger.info(f"[OK] Retention cleanup complete: deleted {total_deleted:,} old candles")
                else:
                    logger.info("[OK] All pairs within 2-year limit, no cleanup needed")

        except ImportError as e:
            logger.warning(f"dateutil not available, skipping retention: {e}")
        except Exception as e:
            logger.error(f"Retention policy enforcement failed: {e}")

    async def _ensure_data_freshness(self, symbol: str, interval: str) -> None:
        """
        Ensure data is up-to-date by loading any missing recent candles.

        Checks the newest candle in DB and loads everything from there to now.
        """
        try:
            from sqlalchemy import func

            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit

            # Get newest candle timestamp in DB
            with SessionLocal() as session:
                result = (
                    session.query(func.max(BybitKlineAudit.open_time))
                    .filter(
                        BybitKlineAudit.symbol == symbol,
                        BybitKlineAudit.interval == interval,
                    )
                    .scalar()
                )

            if not result:
                logger.warning(f"No data in DB for {symbol}:{interval}")
                return

            newest_in_db = result
            now_ms = int(datetime.now(UTC).timestamp() * 1000)

            # Get interval in ms
            interval_ms_map = {
                "1": 60_000,
                "3": 180_000,
                "5": 300_000,
                "15": 900_000,
                "30": 1_800_000,
                "60": 3_600_000,
                "120": 7_200_000,
                "240": 14_400_000,
                "D": 86_400_000,
                "W": 604_800_000,
            }
            interval_ms = interval_ms_map.get(interval, 60_000)

            # Calculate how many candles are missing
            gap_ms = now_ms - newest_in_db
            missing_candles = int(gap_ms / interval_ms)

            if missing_candles <= 1:
                return  # Data is fresh

            logger.info(f"📥 {symbol}:{interval} needs {missing_candles} recent candles")

            # Fetch missing candles
            adapter = self._get_adapter()
            candles = adapter.get_klines(
                symbol=symbol,
                interval=interval,
                limit=min(missing_candles + 10, 1000),
            )

            if candles:
                # Filter to only new candles
                new_candles = [c for c in candles if c["open_time"] > newest_in_db]
                if new_candles:
                    self._persist_to_db(symbol, interval, new_candles)
                    logger.info(f"[OK] Loaded {len(new_candles)} new candles for {symbol}:{interval}")

        except Exception as e:
            logger.error(f"Freshness check failed for {symbol}:{interval}: {e}")

    def get_loading_status(self) -> dict[str, Any]:
        """Get status of all loading operations."""
        return {
            key: {
                "symbol": p.symbol,
                "interval": p.interval,
                "status": p.status,
                "progress": p.progress_percent,
                "loaded": p.loaded_candles,
                "total": p.total_candles,
                "error": p.error,
            }
            for key, p in self._loading_progress.items()
        }

    # =========================================================================
    # Database Operations (Using Repository Pattern)
    # =========================================================================

    def _load_from_db(self, symbol: str, interval: str, limit: int = 500) -> list[dict]:
        """
        Load candles from database using Repository pattern.

        Falls back to legacy SQLAlchemy if RepositoryAdapter unavailable.
        """
        # Try RepositoryAdapter first (faster, uses proper indexes)
        repo_adapter = self._get_repository_adapter()
        if repo_adapter:
            try:
                return repo_adapter.get_klines(symbol, interval, limit=limit)
            except Exception as e:
                logger.debug(f"RepositoryAdapter failed, using fallback: {e}")

        # Fallback to direct SQLAlchemy
        try:
            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit

            with SessionLocal() as session:
                rows = (
                    session.query(BybitKlineAudit)
                    .filter(
                        BybitKlineAudit.symbol == symbol,
                        BybitKlineAudit.interval == interval,
                    )
                    .order_by(BybitKlineAudit.open_time.desc())
                    .limit(limit)
                    .all()
                )

                # Convert to dicts and reverse (oldest first)
                candles = []
                for r in reversed(rows):
                    candles.append(
                        {
                            "open_time": r.open_time,
                            "open": float(r.open_price),
                            "high": float(r.high_price),
                            "low": float(r.low_price),
                            "close": float(r.close_price),
                            "volume": float(r.volume) if r.volume else 0,
                            "turnover": float(r.turnover) if r.turnover else 0,
                        }
                    )
                return candles
        except Exception as e:
            logger.error(f"DB load error: {e}")
            return []

    def _load_from_db_before(self, symbol: str, interval: str, end_time: int, limit: int = 200) -> list[dict]:
        """
        Load historical candles from database before a specific time.

        Uses Repository pattern with fallback to legacy SQLAlchemy.
        """
        # Try RepositoryAdapter first (faster, uses proper indexes)
        repo_adapter = self._get_repository_adapter()
        if repo_adapter:
            try:
                return repo_adapter.get_klines(symbol, interval, limit=limit, end_time=end_time)
            except Exception as e:
                logger.debug(f"RepositoryAdapter failed, using fallback: {e}")

        # Fallback to direct SQLAlchemy
        try:
            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit

            with SessionLocal() as session:
                rows = (
                    session.query(BybitKlineAudit)
                    .filter(
                        BybitKlineAudit.symbol == symbol,
                        BybitKlineAudit.interval == interval,
                        BybitKlineAudit.open_time < end_time,
                    )
                    .order_by(BybitKlineAudit.open_time.desc())
                    .limit(limit)
                    .all()
                )

                candles = []
                for r in reversed(rows):
                    candles.append(
                        {
                            "open_time": r.open_time,
                            "open": float(r.open_price),
                            "high": float(r.high_price),
                            "low": float(r.low_price),
                            "close": float(r.close_price),
                            "volume": float(r.volume) if r.volume else 0,
                            "turnover": float(r.turnover) if r.turnover else 0,
                        }
                    )
                return candles
        except Exception as e:
            logger.error(f"DB load before error: {e}")
            return []

    def _get_db_coverage(self, symbol: str, interval: str) -> tuple | None:
        """
        Get DB coverage info: (oldest_time, newest_time, count).

        Uses Repository pattern with fallback to legacy SQLAlchemy.
        """
        # Try RepositoryAdapter first (faster, uses proper indexes)
        repo_adapter = self._get_repository_adapter()
        if repo_adapter:
            try:
                return repo_adapter.get_coverage(symbol, interval)
            except Exception as e:
                logger.debug(f"RepositoryAdapter failed, using fallback: {e}")

        # Fallback to direct SQLAlchemy
        try:
            from sqlalchemy import func

            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit

            with SessionLocal() as session:
                result = (
                    session.query(
                        func.min(BybitKlineAudit.open_time),
                        func.max(BybitKlineAudit.open_time),
                        func.count(BybitKlineAudit.id),
                    )
                    .filter(
                        BybitKlineAudit.symbol == symbol,
                        BybitKlineAudit.interval == interval,
                    )
                    .first()
                )

                if result and result[2] > 0:
                    return (result[0], result[1], result[2])
                return None
        except Exception as e:
            logger.error(f"DB coverage check error: {e}")
            return None

    def _persist_to_db(self, symbol: str, interval: str, candles: list[dict]):
        """Persist candles to database using KlineDBService queue."""
        if not candles:
            return

        # Try to use KlineDBService first (faster, queue-based)
        db_service = self._get_db_service()
        if db_service:
            try:
                queued = db_service.queue_klines(symbol, interval, candles)
                logger.info(f"Queued {queued} candles for {symbol}:{interval}")
                return
            except Exception as e:
                logger.warning(f"KlineDBService queue failed, falling back to direct: {e}")

        # Fallback to direct database insert
        try:
            from datetime import datetime

            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit

            with SessionLocal() as session:
                inserted = 0
                for candle in candles:
                    open_time = candle.get("open_time", 0)
                    if open_time < 1e12:
                        open_time = int(open_time * 1000)

                    # Check if exists - if yes, update it (candle data may have changed)
                    exists = (
                        session.query(BybitKlineAudit)
                        .filter(
                            BybitKlineAudit.symbol == symbol,
                            BybitKlineAudit.interval == interval,
                            BybitKlineAudit.open_time == open_time,
                        )
                        .first()
                    )

                    # Serialize raw data for NOT NULL constraint
                    # Use custom serializer for datetime objects
                    def json_serializer(obj):
                        if hasattr(obj, "isoformat"):
                            return obj.isoformat()
                        return str(obj)

                    raw_json = json.dumps(candle, default=json_serializer) if candle else "{}"

                    if exists:
                        # Update existing candle with fresh data
                        exists.open_price = float(candle.get("open", exists.open_price))  # type: ignore[assignment]
                        exists.high_price = float(candle.get("high", exists.high_price))  # type: ignore[assignment]
                        exists.low_price = float(candle.get("low", exists.low_price))  # type: ignore[assignment]
                        exists.close_price = float(candle.get("close", exists.close_price))  # type: ignore[assignment]
                        exists.volume = float(candle.get("volume", exists.volume))  # type: ignore[assignment]
                        exists.turnover = float(candle.get("turnover", exists.turnover))  # type: ignore[assignment]
                        exists.raw = raw_json  # type: ignore[assignment]
                        inserted += 1
                        continue

                    record = BybitKlineAudit(
                        symbol=symbol,
                        interval=interval,
                        open_time=open_time,
                        open_time_dt=datetime.fromtimestamp(open_time / 1000, tz=UTC),
                        open_price=float(candle.get("open", 0)),
                        high_price=float(candle.get("high", 0)),
                        low_price=float(candle.get("low", 0)),
                        close_price=float(candle.get("close", 0)),
                        volume=float(candle.get("volume", 0)),
                        turnover=float(candle.get("turnover", 0)),
                        raw=raw_json,
                    )
                    session.add(record)
                    inserted += 1

                session.commit()
                if inserted > 0:
                    logger.info(f"Persisted {inserted} candles for {symbol}:{interval}")
        except Exception as e:
            logger.error(f"DB persist error: {e}")

    def _fetch_from_api(self, symbol: str, interval: str, limit: int = 500) -> list[dict]:
        """Fetch candles from Bybit API."""
        try:
            adapter = self._get_adapter()
            return adapter.get_klines(symbol=symbol, interval=interval, limit=limit)
        except Exception as e:
            logger.error(f"API fetch error: {e}")
            return []

    def _fetch_from_api_both_markets(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        persist: bool = True,
    ) -> dict[str, list[dict]]:
        """
        Fetch candles from BOTH SPOT and LINEAR markets in parallel.

        This enables TradingView parity (SPOT) while also having LINEAR data
        for perpetual trading execution.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            interval: Timeframe
            limit: Number of candles
            persist: Whether to persist to DB

        Returns:
            Dict with 'spot' and 'linear' keys
        """
        try:
            adapter = self._get_adapter()

            # Use new parallel fetch method
            results = adapter.get_klines_both_markets(symbol=symbol, interval=interval, limit=limit)

            # Persist to DB with market_type
            if persist:
                for market_type in ["spot", "linear"]:
                    candles = results.get(market_type, [])
                    if candles:
                        try:
                            inserted = adapter.persist_klines_with_market_type(
                                symbol=symbol,
                                market_type=market_type,
                                normalized_rows=candles,
                            )
                            logger.debug(f"Persisted {inserted} {market_type.upper()} candles for {symbol}/{interval}")
                        except Exception as e:
                            logger.warning(f"Failed to persist {market_type} klines: {e}")

            return results

        except Exception as e:
            logger.error(f"API fetch error (both markets): {e}")
            return {"spot": [], "linear": []}

    # =========================================================================
    # Background Update Service
    # =========================================================================

    async def start_update_service(self, update_interval_seconds: int = 60):
        """Start background update service."""
        if self._running:
            return

        self._running = True
        self._update_task = asyncio.create_task(self._update_loop(update_interval_seconds))
        logger.info(f"Started background update service (interval: {update_interval_seconds}s)")

    async def stop_update_service(self):
        """Stop background update service."""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._update_task
        logger.info("Stopped background update service")

    async def _update_loop(self, interval_seconds: int):
        """Background loop to update data for active symbols."""
        while self._running:
            try:
                await self._update_active_symbols()

                # Periodic gap repair check
                await self._check_and_repair_gaps_periodically()

                # Periodic retention policy enforcement (delete old data)
                await self._enforce_retention_policy()
            except Exception as e:
                logger.error(f"Update loop error: {e}")

            await asyncio.sleep(interval_seconds)

    async def _update_active_symbols(self):
        """Update data for all active symbols."""
        for symbol, state in self._symbol_states.items():
            if not state.is_primary:
                continue

            for interval in state.loaded_intervals:
                try:
                    # First ensure data is fresh (fill any gaps to current time)
                    await self._ensure_data_freshness(symbol, interval)

                    # Fetch latest candles
                    candles = self._fetch_from_api(symbol, interval, 10)
                    if candles:
                        self._persist_to_db(symbol, interval, candles)

                        # Update RAM cache if exists
                        key = self._cache_key(symbol, interval)
                        if key in self._ram_cache:
                            existing = self._ram_cache[key]
                            existing_times = {c.get("open_time") for c in existing}
                            for c in candles:
                                if c.get("open_time") not in existing_times:
                                    existing.append(c)
                            # Sort and trim
                            existing.sort(key=lambda x: x.get("open_time", 0))
                            self._ram_cache[key] = existing[-self.RAM_LIMIT :]

                        state.last_update = datetime.now(UTC)
                except Exception as e:
                    logger.warning(f"Update failed for {symbol}:{interval}: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get service status."""
        return {
            "running": self._running,
            "symbols_loaded": len(self._symbol_states),
            "ram_cache_keys": list(self._ram_cache.keys()),
            "ram_cache_total_candles": sum(len(v) for v in self._ram_cache.values()),
            "loading_progress": self.get_loading_status(),
            "symbol_states": {
                symbol: {
                    "intervals": list(state.loaded_intervals),
                    "last_update": state.last_update.isoformat() if state.last_update else None,
                    "is_primary": state.is_primary,
                }
                for symbol, state in self._symbol_states.items()
            },
        }


# Singleton instance
SMART_KLINE_SERVICE = SmartKlineService.get_instance()
