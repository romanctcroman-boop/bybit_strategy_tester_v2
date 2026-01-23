"""
Tests for CacheWarmingService

Tests the cache warming functionality that pre-loads high-frequency trading pairs
into cache for improved cache hit rates (>95% target).
"""

import pytest


class TestWarmingPriority:
    """Tests for WarmingPriority enum"""

    def test_priority_values(self):
        """Test WarmingPriority enum values are strings"""
        from backend.services.cache_warming import WarmingPriority

        assert WarmingPriority.CRITICAL.value == "critical"
        assert WarmingPriority.HIGH.value == "high"
        assert WarmingPriority.MEDIUM.value == "medium"
        assert WarmingPriority.LOW.value == "low"


class TestWarmingStatus:
    """Tests for WarmingStatus enum"""

    def test_status_values(self):
        """Test WarmingStatus enum values"""
        from backend.services.cache_warming import WarmingStatus

        assert WarmingStatus.PENDING.value == "pending"
        assert WarmingStatus.IN_PROGRESS.value == "in_progress"
        assert WarmingStatus.COMPLETED.value == "completed"
        assert WarmingStatus.FAILED.value == "failed"
        assert WarmingStatus.SKIPPED.value == "skipped"


class TestWarmingTarget:
    """Tests for WarmingTarget dataclass"""

    def test_warming_target_creation(self):
        """Test WarmingTarget can be created with valid data"""
        from backend.services.cache_warming import WarmingPriority, WarmingTarget

        target = WarmingTarget(
            symbol="BTCUSDT", interval="15", priority=WarmingPriority.CRITICAL
        )

        assert target.symbol == "BTCUSDT"
        assert target.interval == "15"
        assert target.priority == WarmingPriority.CRITICAL
        assert target.enabled is True
        assert target.last_warmed is None
        assert target.warm_count == 0
        assert target.failure_count == 0

    def test_warming_target_defaults(self):
        """Test WarmingTarget default values"""
        from backend.services.cache_warming import WarmingPriority, WarmingTarget

        target = WarmingTarget(symbol="ETHUSDT", interval="60")

        assert target.priority == WarmingPriority.MEDIUM
        assert target.enabled is True


class TestWarmingResult:
    """Tests for WarmingResult dataclass"""

    def test_warming_result_creation(self):
        """Test WarmingResult creation"""
        from backend.services.cache_warming import WarmingResult, WarmingStatus

        result = WarmingResult(
            symbol="BTCUSDT",
            interval="15",
            status=WarmingStatus.COMPLETED,
            candles_loaded=1000,
            duration_ms=150.5,
        )

        assert result.symbol == "BTCUSDT"
        assert result.interval == "15"
        assert result.status == WarmingStatus.COMPLETED
        assert result.candles_loaded == 1000
        assert result.duration_ms == 150.5

    def test_warming_result_failure(self):
        """Test WarmingResult for failed warming"""
        from backend.services.cache_warming import WarmingResult, WarmingStatus

        result = WarmingResult(
            symbol="BTCUSDT",
            interval="15",
            status=WarmingStatus.FAILED,
            candles_loaded=0,
            duration_ms=50.0,
            error_message="Connection timeout",
        )

        assert result.status == WarmingStatus.FAILED
        assert result.error_message == "Connection timeout"


class TestWarmingMetrics:
    """Tests for WarmingMetrics dataclass"""

    def test_warming_metrics_creation(self):
        """Test WarmingMetrics default values"""
        from backend.services.cache_warming import WarmingMetrics

        metrics = WarmingMetrics()

        assert metrics.total_warms == 0
        assert metrics.successful_warms == 0
        assert metrics.failed_warms == 0
        assert metrics.skipped_warms == 0
        assert metrics.total_candles_loaded == 0
        assert metrics.cache_hit_rate == 0.0


class TestCacheStats:
    """Tests for CacheStats dataclass"""

    def test_cache_stats_creation(self):
        """Test CacheStats default values"""
        from backend.services.cache_warming import CacheStats

        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0

    def test_cache_stats_hit_rate_no_requests(self):
        """Test hit rate with no requests"""
        from backend.services.cache_warming import CacheStats

        stats = CacheStats()

        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate_calculation(self):
        """Test hit rate calculation"""
        from backend.services.cache_warming import CacheStats

        stats = CacheStats(hits=80, misses=20)

        # 80 / 100 * 100 = 80%
        assert stats.hit_rate == 80.0


class TestDefaultHighFrequencyPairs:
    """Tests for default high-frequency trading pairs"""

    def test_default_pairs_exist(self):
        """Test that default pairs are defined"""
        from backend.services.cache_warming import DEFAULT_HIGH_FREQUENCY_PAIRS

        assert isinstance(DEFAULT_HIGH_FREQUENCY_PAIRS, list)
        assert len(DEFAULT_HIGH_FREQUENCY_PAIRS) > 0

    def test_btcusdt_in_defaults(self):
        """Test that BTCUSDT is in default pairs"""
        from backend.services.cache_warming import DEFAULT_HIGH_FREQUENCY_PAIRS

        symbols = [pair[0] for pair in DEFAULT_HIGH_FREQUENCY_PAIRS]
        assert "BTCUSDT" in symbols

    def test_ethusdt_in_defaults(self):
        """Test that ETHUSDT is in default pairs"""
        from backend.services.cache_warming import DEFAULT_HIGH_FREQUENCY_PAIRS

        symbols = [pair[0] for pair in DEFAULT_HIGH_FREQUENCY_PAIRS]
        assert "ETHUSDT" in symbols


class TestCacheWarmingServiceInit:
    """Tests for CacheWarmingService initialization"""

    def test_service_creation(self):
        """Test CacheWarmingService can be created"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()

        assert service is not None
        assert hasattr(service, "_targets")
        assert hasattr(service, "_running")
        assert hasattr(service, "metrics")

    def test_singleton_pattern(self):
        """Test singleton pattern via get_instance"""
        from backend.services.cache_warming import CacheWarmingService

        # Reset singleton
        CacheWarmingService._instance = None

        service1 = CacheWarmingService.get_instance()
        service2 = CacheWarmingService.get_instance()

        assert service1 is service2

    def test_default_targets_loaded(self):
        """Test default warming targets are loaded"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()

        # Should have default targets
        assert len(service._targets) > 0

    def test_initial_state(self):
        """Test initial service state"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()

        assert service._running is False


class TestCacheWarmingServiceTargets:
    """Tests for CacheWarmingService target management"""

    def test_add_target(self):
        """Test adding warming target"""
        from backend.services.cache_warming import CacheWarmingService, WarmingPriority

        service = CacheWarmingService()
        initial_count = len(service._targets)

        service.add_target("NEWCOIN", "5", WarmingPriority.HIGH)

        assert len(service._targets) == initial_count + 1
        assert "NEWCOIN:5" in service._targets

    def test_remove_target(self):
        """Test removing warming target"""
        from backend.services.cache_warming import CacheWarmingService, WarmingPriority

        service = CacheWarmingService()

        # Add a target first
        service.add_target("REMOVEME", "15", WarmingPriority.LOW)
        assert "REMOVEME:15" in service._targets

        # Remove it
        result = service.remove_target("REMOVEME", "15")

        assert result is True
        assert "REMOVEME:15" not in service._targets

    def test_remove_nonexistent_target(self):
        """Test removing non-existent target"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()

        result = service.remove_target("NONEXISTENT", "D")

        assert result is False

    def test_enable_disable_target(self):
        """Test enabling/disabling warming target"""
        from backend.services.cache_warming import CacheWarmingService, WarmingPriority

        service = CacheWarmingService()

        service.add_target("TOGGLEME", "60", WarmingPriority.MEDIUM)

        # Disable
        result = service.enable_target("TOGGLEME", "60", False)
        assert result is True
        assert service._targets["TOGGLEME:60"].enabled is False

        # Enable
        result = service.enable_target("TOGGLEME", "60", True)
        assert result is True
        assert service._targets["TOGGLEME:60"].enabled is True

    def test_get_targets(self):
        """Test getting targets"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()
        targets = service.get_targets()

        assert isinstance(targets, list)
        assert len(targets) > 0

    def test_get_targets_by_priority(self):
        """Test getting targets filtered by priority"""
        from backend.services.cache_warming import CacheWarmingService, WarmingPriority

        service = CacheWarmingService()
        targets = service.get_targets(priority=WarmingPriority.CRITICAL)

        for target in targets:
            assert target.priority == WarmingPriority.CRITICAL


class TestCacheWarmingServiceStats:
    """Tests for CacheWarmingService cache statistics"""

    def test_record_cache_hit(self):
        """Test recording cache hit"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()
        initial_hits = service._cache_stats.hits

        service.record_cache_hit()

        assert service._cache_stats.hits == initial_hits + 1

    def test_record_cache_miss(self):
        """Test recording cache miss"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()
        initial_misses = service._cache_stats.misses

        service.record_cache_miss()

        assert service._cache_stats.misses == initial_misses + 1

    def test_record_cache_eviction(self):
        """Test recording cache eviction"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()
        initial_evictions = service._cache_stats.evictions

        service.record_cache_eviction()

        assert service._cache_stats.evictions == initial_evictions + 1

    def test_get_cache_stats(self):
        """Test getting cache stats"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()
        stats = service.get_cache_stats()

        assert "hits" in stats
        assert "misses" in stats


class TestCacheWarmingServiceStatus:
    """Tests for CacheWarmingService status methods"""

    def test_get_status(self):
        """Test get_status method"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()
        status = service.get_status()

        assert isinstance(status, dict)
        assert "running" in status

    def test_get_metrics(self):
        """Test get_metrics method"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()
        metrics = service.get_metrics()

        # Should return WarmingMetrics
        assert hasattr(metrics, "total_warms")


class TestCacheWarmingServiceAsync:
    """Tests for async CacheWarmingService methods"""

    @pytest.mark.asyncio
    async def test_start_stop_service(self):
        """Test starting and stopping the service"""
        from backend.services.cache_warming import CacheWarmingService

        service = CacheWarmingService()

        # Start should not raise
        await service.start()
        assert service._running is True

        # Stop should not raise
        await service.stop()
        assert service._running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
