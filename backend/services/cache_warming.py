"""
Cache Warming Service.

AI Agent Recommendation Implementation:
- Pre-load high-frequency trading pairs into cache
- Target: >95% cache hit rate (current: 85%)
- Automatic warm-up on startup
- Scheduled refresh for active pairs
- Priority-based warming queue

Features:
- Pre-defined list of high-frequency pairs
- Configurable warm-up intervals
- Background warming tasks
- Warm-up status monitoring
- Cache hit rate tracking
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WarmingPriority(str, Enum):
    """Priority levels for cache warming."""

    CRITICAL = "critical"  # Always warm first (BTC, ETH)
    HIGH = "high"  # Major pairs
    MEDIUM = "medium"  # Popular alts
    LOW = "low"  # Other pairs


class WarmingStatus(str, Enum):
    """Status of a warming task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WarmingTarget:
    """Target for cache warming."""

    symbol: str
    interval: str
    priority: WarmingPriority = WarmingPriority.MEDIUM
    last_warmed: Optional[datetime] = None
    warm_count: int = 0
    failure_count: int = 0
    avg_warm_time_ms: float = 0.0
    enabled: bool = True


@dataclass
class WarmingResult:
    """Result of a warming operation."""

    symbol: str
    interval: str
    status: WarmingStatus
    candles_loaded: int = 0
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class WarmingMetrics:
    """Metrics for cache warming."""

    total_warms: int = 0
    successful_warms: int = 0
    failed_warms: int = 0
    skipped_warms: int = 0
    total_candles_loaded: int = 0
    total_warm_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    last_full_warm: Optional[datetime] = None
    warm_queue_size: int = 0
    active_warming: bool = False


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


# Default high-frequency trading pairs
DEFAULT_HIGH_FREQUENCY_PAIRS = [
    # Critical (BTC/ETH)
    ("BTCUSDT", "1", WarmingPriority.CRITICAL),
    ("BTCUSDT", "5", WarmingPriority.CRITICAL),
    ("BTCUSDT", "15", WarmingPriority.CRITICAL),
    ("BTCUSDT", "60", WarmingPriority.CRITICAL),
    ("BTCUSDT", "240", WarmingPriority.CRITICAL),
    ("BTCUSDT", "D", WarmingPriority.CRITICAL),
    ("ETHUSDT", "1", WarmingPriority.CRITICAL),
    ("ETHUSDT", "5", WarmingPriority.CRITICAL),
    ("ETHUSDT", "15", WarmingPriority.CRITICAL),
    ("ETHUSDT", "60", WarmingPriority.CRITICAL),
    ("ETHUSDT", "240", WarmingPriority.CRITICAL),
    ("ETHUSDT", "D", WarmingPriority.CRITICAL),
    # High (Major Alts)
    ("SOLUSDT", "15", WarmingPriority.HIGH),
    ("SOLUSDT", "60", WarmingPriority.HIGH),
    ("XRPUSDT", "15", WarmingPriority.HIGH),
    ("XRPUSDT", "60", WarmingPriority.HIGH),
    ("BNBUSDT", "15", WarmingPriority.HIGH),
    ("BNBUSDT", "60", WarmingPriority.HIGH),
    ("ADAUSDT", "15", WarmingPriority.HIGH),
    ("ADAUSDT", "60", WarmingPriority.HIGH),
    ("DOGEUSDT", "15", WarmingPriority.HIGH),
    ("DOGEUSDT", "60", WarmingPriority.HIGH),
    # Medium (Popular)
    ("AVAXUSDT", "15", WarmingPriority.MEDIUM),
    ("AVAXUSDT", "60", WarmingPriority.MEDIUM),
    ("DOTUSDT", "15", WarmingPriority.MEDIUM),
    ("DOTUSDT", "60", WarmingPriority.MEDIUM),
    ("MATICUSDT", "15", WarmingPriority.MEDIUM),
    ("MATICUSDT", "60", WarmingPriority.MEDIUM),
    ("LINKUSDT", "15", WarmingPriority.MEDIUM),
    ("LINKUSDT", "60", WarmingPriority.MEDIUM),
]


class CacheWarmingService:
    """
    Cache Warming Service.

    Pre-loads high-frequency trading pairs into cache to achieve
    >95% cache hit rate. Runs as background task with configurable
    refresh intervals.
    """

    _instance: Optional["CacheWarmingService"] = None

    def __init__(
        self,
        refresh_interval_minutes: int = 5,
        stale_threshold_minutes: int = 15,
        max_concurrent_warms: int = 5,
    ):
        """Initialize cache warming service."""
        self.refresh_interval = timedelta(minutes=refresh_interval_minutes)
        self.stale_threshold = timedelta(minutes=stale_threshold_minutes)
        self.max_concurrent = max_concurrent_warms

        # Warming targets
        self._targets: Dict[str, WarmingTarget] = {}

        # Results history
        self._results: List[WarmingResult] = []
        self._max_results = 1000

        # Metrics
        self.metrics = WarmingMetrics()
        self._cache_stats = CacheStats()

        # Background task
        self._warming_task: Optional[asyncio.Task] = None
        self._running = False
        self._semaphore: Optional[asyncio.Semaphore] = None

        # Callbacks
        self._warm_callback: Optional[Callable] = None

        # Initialize default targets
        self._init_default_targets()

        logger.info(
            "CacheWarmingService initialized (refresh=%dm, stale=%dm, concurrent=%d)",
            refresh_interval_minutes,
            stale_threshold_minutes,
            max_concurrent_warms,
        )

    @classmethod
    def get_instance(cls) -> "CacheWarmingService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_default_targets(self):
        """Initialize default warming targets."""
        for symbol, interval, priority in DEFAULT_HIGH_FREQUENCY_PAIRS:
            key = f"{symbol}:{interval}"
            self._targets[key] = WarmingTarget(
                symbol=symbol,
                interval=interval,
                priority=priority,
            )
        logger.info(f"Initialized {len(self._targets)} default warming targets")

    def set_warm_callback(self, callback: Callable):
        """
        Set callback function for warming a symbol/interval.

        Callback signature: async def callback(symbol: str, interval: str) -> int
        Returns number of candles loaded.
        """
        self._warm_callback = callback

    # ========================================================================
    # Target Management
    # ========================================================================

    def add_target(
        self,
        symbol: str,
        interval: str,
        priority: WarmingPriority = WarmingPriority.MEDIUM,
    ) -> WarmingTarget:
        """Add a warming target."""
        key = f"{symbol}:{interval}"
        if key not in self._targets:
            self._targets[key] = WarmingTarget(
                symbol=symbol,
                interval=interval,
                priority=priority,
            )
            logger.info(f"Added warming target: {key} (priority={priority.value})")
        return self._targets[key]

    def remove_target(self, symbol: str, interval: str) -> bool:
        """Remove a warming target."""
        key = f"{symbol}:{interval}"
        if key in self._targets:
            del self._targets[key]
            logger.info(f"Removed warming target: {key}")
            return True
        return False

    def get_targets(
        self,
        priority: Optional[WarmingPriority] = None,
        enabled_only: bool = True,
    ) -> List[WarmingTarget]:
        """Get warming targets."""
        targets = list(self._targets.values())
        if priority:
            targets = [t for t in targets if t.priority == priority]
        if enabled_only:
            targets = [t for t in targets if t.enabled]
        return sorted(targets, key=lambda t: (t.priority.value, t.symbol))

    def enable_target(self, symbol: str, interval: str, enabled: bool = True) -> bool:
        """Enable or disable a warming target."""
        key = f"{symbol}:{interval}"
        if key in self._targets:
            self._targets[key].enabled = enabled
            return True
        return False

    # ========================================================================
    # Cache Statistics
    # ========================================================================

    def record_cache_hit(self):
        """Record a cache hit."""
        self._cache_stats.hits += 1
        self._update_hit_rate()

    def record_cache_miss(self):
        """Record a cache miss."""
        self._cache_stats.misses += 1
        self._update_hit_rate()

    def record_cache_eviction(self):
        """Record a cache eviction."""
        self._cache_stats.evictions += 1

    def _update_hit_rate(self):
        """Update cache hit rate in metrics."""
        self.metrics.cache_hit_rate = self._cache_stats.hit_rate

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "hits": self._cache_stats.hits,
            "misses": self._cache_stats.misses,
            "evictions": self._cache_stats.evictions,
            "hit_rate": self._cache_stats.hit_rate,
            "target_hit_rate": 95.0,
            "hit_rate_gap": 95.0 - self._cache_stats.hit_rate,
        }

    # ========================================================================
    # Warming Operations
    # ========================================================================

    async def warm_target(self, symbol: str, interval: str) -> WarmingResult:
        """Warm a single target."""
        key = f"{symbol}:{interval}"
        start_time = time.time()

        target = self._targets.get(key)
        if not target:
            return WarmingResult(
                symbol=symbol,
                interval=interval,
                status=WarmingStatus.SKIPPED,
                error_message="Target not registered",
            )

        if not target.enabled:
            return WarmingResult(
                symbol=symbol,
                interval=interval,
                status=WarmingStatus.SKIPPED,
                error_message="Target disabled",
            )

        try:
            candles_loaded = 0

            if self._warm_callback:
                # Use registered callback
                if asyncio.iscoroutinefunction(self._warm_callback):
                    candles_loaded = await self._warm_callback(symbol, interval)
                else:
                    candles_loaded = self._warm_callback(symbol, interval)
            else:
                # Default: try to use CandleCache
                try:
                    from backend.services.candle_cache import CANDLE_CACHE

                    data = CANDLE_CACHE.load_initial(symbol, interval, persist=False)
                    candles_loaded = len(data) if data else 0
                except ImportError:
                    logger.warning("CandleCache not available for warming")
                    candles_loaded = 0

            duration_ms = (time.time() - start_time) * 1000

            # Update target stats
            target.last_warmed = datetime.now(timezone.utc)
            target.warm_count += 1
            target.avg_warm_time_ms = (
                target.avg_warm_time_ms * (target.warm_count - 1) + duration_ms
            ) / target.warm_count

            # Update metrics
            self.metrics.total_warms += 1
            self.metrics.successful_warms += 1
            self.metrics.total_candles_loaded += candles_loaded
            self.metrics.total_warm_time_ms += duration_ms

            result = WarmingResult(
                symbol=symbol,
                interval=interval,
                status=WarmingStatus.COMPLETED,
                candles_loaded=candles_loaded,
                duration_ms=duration_ms,
            )

            logger.debug(
                f"Warmed {key}: {candles_loaded} candles in {duration_ms:.1f}ms"
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            target.failure_count += 1
            self.metrics.total_warms += 1
            self.metrics.failed_warms += 1

            result = WarmingResult(
                symbol=symbol,
                interval=interval,
                status=WarmingStatus.FAILED,
                duration_ms=duration_ms,
                error_message=str(e),
            )

            logger.error(f"Failed to warm {key}: {e}")

        # Store result
        self._results.append(result)
        if len(self._results) > self._max_results:
            self._results = self._results[-self._max_results :]

        return result

    async def warm_all(
        self,
        priority: Optional[WarmingPriority] = None,
        force: bool = False,
    ) -> List[WarmingResult]:
        """
        Warm all targets.

        Args:
            priority: Only warm targets of this priority
            force: Warm even if recently warmed
        """
        targets = self.get_targets(priority=priority, enabled_only=True)
        now = datetime.now(timezone.utc)
        results = []

        # Filter stale targets unless force
        if not force:
            targets = [
                t
                for t in targets
                if t.last_warmed is None or (now - t.last_warmed) > self.stale_threshold
            ]

        if not targets:
            logger.info("No stale targets to warm")
            return results

        logger.info(f"Warming {len(targets)} targets...")
        self.metrics.active_warming = True

        # Use semaphore for concurrency control
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)

        async def warm_with_semaphore(target: WarmingTarget) -> WarmingResult:
            async with self._semaphore:
                return await self.warm_target(target.symbol, target.interval)

        # Warm in priority order
        for prio in [
            WarmingPriority.CRITICAL,
            WarmingPriority.HIGH,
            WarmingPriority.MEDIUM,
            WarmingPriority.LOW,
        ]:
            prio_targets = [t for t in targets if t.priority == prio]
            if prio_targets:
                prio_results = await asyncio.gather(
                    *[warm_with_semaphore(t) for t in prio_targets],
                    return_exceptions=True,
                )
                for r in prio_results:
                    if isinstance(r, WarmingResult):
                        results.append(r)

        self.metrics.active_warming = False
        self.metrics.last_full_warm = datetime.now(timezone.utc)

        success_count = sum(1 for r in results if r.status == WarmingStatus.COMPLETED)
        logger.info(f"Warming complete: {success_count}/{len(results)} successful")

        return results

    async def warm_critical(self) -> List[WarmingResult]:
        """Warm only critical targets."""
        return await self.warm_all(priority=WarmingPriority.CRITICAL)

    # ========================================================================
    # Background Task
    # ========================================================================

    async def start(self):
        """Start background warming task."""
        if self._running:
            return

        self._running = True
        self._warming_task = asyncio.create_task(self._warming_loop())
        logger.info("Cache warming service started")

    async def stop(self):
        """Stop background warming task."""
        self._running = False
        if self._warming_task:
            self._warming_task.cancel()
            try:
                await self._warming_task
            except asyncio.CancelledError:
                pass
        logger.info("Cache warming service stopped")

    async def _warming_loop(self):
        """Background warming loop."""
        # Initial warm on startup
        await self.warm_all(force=True)

        while self._running:
            try:
                await asyncio.sleep(self.refresh_interval.total_seconds())
                if self._running:
                    await self.warm_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Warming loop error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    # ========================================================================
    # Status and Metrics
    # ========================================================================

    def get_metrics(self) -> WarmingMetrics:
        """Get warming metrics."""
        self.metrics.warm_queue_size = len(
            [
                t
                for t in self._targets.values()
                if t.enabled
                and (
                    t.last_warmed is None
                    or (datetime.now(timezone.utc) - t.last_warmed)
                    > self.stale_threshold
                )
            ]
        )
        return self.metrics

    def get_results(self, limit: int = 100) -> List[WarmingResult]:
        """Get recent warming results."""
        return self._results[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        metrics = self.get_metrics()
        return {
            "running": self._running,
            "total_targets": len(self._targets),
            "enabled_targets": len([t for t in self._targets.values() if t.enabled]),
            "stale_targets": metrics.warm_queue_size,
            "metrics": {
                "total_warms": metrics.total_warms,
                "successful_warms": metrics.successful_warms,
                "failed_warms": metrics.failed_warms,
                "total_candles_loaded": metrics.total_candles_loaded,
                "avg_warm_time_ms": (
                    metrics.total_warm_time_ms / metrics.total_warms
                    if metrics.total_warms > 0
                    else 0
                ),
                "cache_hit_rate": metrics.cache_hit_rate,
                "target_hit_rate": 95.0,
                "last_full_warm": metrics.last_full_warm.isoformat()
                if metrics.last_full_warm
                else None,
            },
            "cache_stats": self.get_cache_stats(),
        }

    def get_health(self) -> Dict[str, Any]:
        """Get service health."""
        metrics = self.get_metrics()
        hit_rate_ok = metrics.cache_hit_rate >= 85.0
        failures_ok = metrics.failed_warms < metrics.successful_warms * 0.1

        return {
            "status": "healthy"
            if (hit_rate_ok and failures_ok and self._running)
            else "degraded",
            "running": self._running,
            "cache_hit_rate": metrics.cache_hit_rate,
            "target_hit_rate": 95.0,
            "hit_rate_ok": hit_rate_ok,
            "failures_ok": failures_ok,
            "checks": {
                "service_running": self._running,
                "hit_rate_above_85": hit_rate_ok,
                "failure_rate_below_10pct": failures_ok,
            },
        }


# ============================================================================
# Module-level accessor
# ============================================================================


def get_cache_warming_service() -> CacheWarmingService:
    """Get singleton cache warming service."""
    return CacheWarmingService.get_instance()
