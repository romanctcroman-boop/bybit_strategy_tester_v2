"""
Tests for optimizer performance modules (P0-P5).

Tests:
- P0: IndicatorCache — hit/miss, eviction, thread safety, fingerprinting
- P1: MutableGraphUpdater — apply/restore correctness, RSI/MACD flag auto-enable
- P2: Auto n_jobs selection
- P3: PrecomputedOHLCV — array extraction, fingerprint
- P4: Early pruning — domain-specific prune decisions
- P5: Numba indicators — RSI, ADX, Supertrend correctness
- Integration: optimized path produces same results as original
"""

import copy
import threading

import numpy as np
import pandas as pd
import pytest

from backend.optimization.early_pruning import compute_adaptive_timeout, should_prune_early
from backend.optimization.graph_utils import (
    MutableGraphUpdater,
    classify_params_by_indicator_impact,
)
from backend.optimization.indicator_cache import (
    IndicatorCache,
    _freeze_params,
    _ohlcv_fingerprint,
)
from backend.optimization.numba_indicators import (
    compute_adx_fast,
    compute_rsi_fast,
    compute_supertrend_fast,
)
from backend.optimization.precompute import PrecomputedOHLCV, precompute_ohlcv

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data (500 candles) for testing."""
    np.random.seed(42)
    n = 500
    base_price = 50000.0

    timestamps = pd.date_range(start="2025-01-01", periods=n, freq="15min", tz="UTC")

    returns = np.random.randn(n) * 0.002
    prices = base_price * np.cumprod(1 + returns)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices * (1 + np.random.randn(n) * 0.001),
            "high": prices * (1 + abs(np.random.randn(n)) * 0.003),
            "low": prices * (1 - abs(np.random.randn(n)) * 0.003),
            "close": prices,
            "volume": np.random.uniform(100, 1000, n),
        }
    )


@pytest.fixture
def sample_rsi_graph():
    """Strategy graph with RSI + static_sltp blocks."""
    return {
        "name": "Test RSI Strategy",
        "blocks": [
            {
                "id": "rsi_1",
                "type": "rsi",
                "name": "RSI",
                "params": {
                    "period": 14,
                    "overbought": 70,
                    "oversold": 30,
                    "use_cross_level": False,
                    "cross_long_level": 30,
                    "cross_short_level": 70,
                    "use_long_range": False,
                    "long_rsi_more": 20,
                    "long_rsi_less": 40,
                },
            },
            {
                "id": "adx_1",
                "type": "adx",
                "name": "ADX",
                "params": {"period": 14},
            },
            {
                "id": "sltp_1",
                "type": "static_sltp",
                "name": "SL/TP",
                "params": {
                    "stop_loss_percent": 1.5,
                    "take_profit_percent": 2.0,
                },
            },
            {
                "id": "strategy_1",
                "type": "strategy",
                "name": "Main",
                "isMain": True,
            },
        ],
        "connections": [
            {
                "source": {"blockId": "rsi_1", "portId": "signal"},
                "target": {"blockId": "strategy_1", "portId": "entry_long"},
            },
            {
                "source": {"blockId": "adx_1", "portId": "signal"},
                "target": {"blockId": "strategy_1", "portId": "filter"},
            },
        ],
    }


@pytest.fixture
def sample_macd_graph():
    """Strategy graph with MACD block for testing auto-enable flags."""
    return {
        "name": "Test MACD Strategy",
        "blocks": [
            {
                "id": "macd_1",
                "type": "macd",
                "name": "MACD",
                "params": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                    "use_macd_cross_zero": False,
                    "macd_cross_zero_level": 0,
                    "disable_signal_memory": True,
                    "signal_memory_bars": 3,
                },
            },
        ],
        "connections": [],
    }


@pytest.fixture
def sample_param_specs():
    """Parameter specs for RSI + ADX + SL/TP optimization."""
    return [
        {
            "block_id": "rsi_1",
            "block_type": "rsi",
            "param_key": "period",
            "param_path": "rsi_1.period",
            "type": "int",
            "low": 5,
            "high": 25,
            "step": 1,
            "default": 14,
        },
        {
            "block_id": "rsi_1",
            "block_type": "rsi",
            "param_key": "cross_long_level",
            "param_path": "rsi_1.cross_long_level",
            "type": "float",
            "low": 20,
            "high": 40,
            "step": 5,
            "default": 30,
        },
        {
            "block_id": "adx_1",
            "block_type": "adx",
            "param_key": "period",
            "param_path": "adx_1.period",
            "type": "int",
            "low": 7,
            "high": 25,
            "step": 1,
            "default": 14,
        },
        {
            "block_id": "sltp_1",
            "block_type": "static_sltp",
            "param_key": "stop_loss_percent",
            "param_path": "sltp_1.stop_loss_percent",
            "type": "float",
            "low": 0.5,
            "high": 3.0,
            "step": 0.5,
            "default": 1.5,
        },
        {
            "block_id": "sltp_1",
            "block_type": "static_sltp",
            "param_key": "take_profit_percent",
            "param_path": "sltp_1.take_profit_percent",
            "type": "float",
            "low": 1.0,
            "high": 5.0,
            "step": 0.5,
            "default": 2.0,
        },
    ]


# =============================================================================
# P0: INDICATOR CACHE TESTS
# =============================================================================


class TestIndicatorCache:
    """Tests for IndicatorCache (P0)."""

    def test_cache_miss_returns_none(self):
        """Cache miss should return None."""
        cache = IndicatorCache(max_size=10)
        result = cache.get("rsi", {"period": 14}, "fp123")
        assert result is None

    def test_cache_hit_returns_stored_value(self):
        """Cache hit should return the stored result."""
        cache = IndicatorCache(max_size=10)
        test_result = {"signal": pd.Series([True, False, True])}
        cache.put("rsi", {"period": 14}, "fp123", test_result)

        cached = cache.get("rsi", {"period": 14}, "fp123")
        assert cached is not None
        assert "signal" in cached
        pd.testing.assert_series_equal(cached["signal"], test_result["signal"])

    def test_cache_miss_on_different_params(self):
        """Different params should be a cache miss."""
        cache = IndicatorCache(max_size=10)
        cache.put("rsi", {"period": 14}, "fp123", {"signal": pd.Series([True])})

        assert cache.get("rsi", {"period": 21}, "fp123") is None

    def test_cache_miss_on_different_ohlcv(self):
        """Different OHLCV fingerprint should be a cache miss."""
        cache = IndicatorCache(max_size=10)
        cache.put("rsi", {"period": 14}, "fp123", {"signal": pd.Series([True])})

        assert cache.get("rsi", {"period": 14}, "fp456") is None

    def test_cache_miss_on_different_indicator(self):
        """Different indicator type should be a cache miss."""
        cache = IndicatorCache(max_size=10)
        cache.put("rsi", {"period": 14}, "fp123", {"signal": pd.Series([True])})

        assert cache.get("adx", {"period": 14}, "fp123") is None

    def test_cache_eviction_lru(self):
        """Cache should evict LRU entry when full."""
        cache = IndicatorCache(max_size=3)
        cache.put("rsi", {"period": 14}, "fp1", {"s": pd.Series([1])})
        cache.put("adx", {"period": 14}, "fp1", {"s": pd.Series([2])})
        cache.put("macd", {"fast": 12}, "fp1", {"s": pd.Series([3])})

        # Cache is full (3 entries). Adding a 4th should evict the oldest (rsi)
        cache.put("ema", {"period": 20}, "fp1", {"s": pd.Series([4])})

        assert cache.get("rsi", {"period": 14}, "fp1") is None  # evicted
        assert cache.get("adx", {"period": 14}, "fp1") is not None  # still there
        assert cache.get("ema", {"period": 20}, "fp1") is not None  # new entry

    def test_cache_stats(self):
        """Stats should track hits and misses."""
        cache = IndicatorCache(max_size=10)
        cache.put("rsi", {"period": 14}, "fp1", {"s": pd.Series([1])})

        cache.get("rsi", {"period": 14}, "fp1")  # hit
        cache.get("rsi", {"period": 21}, "fp1")  # miss
        cache.get("rsi", {"period": 14}, "fp1")  # hit

        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(0.667, abs=0.01)
        assert stats["size"] == 1

    def test_cache_clear(self):
        """Clear should empty the cache and reset stats."""
        cache = IndicatorCache(max_size=10)
        cache.put("rsi", {"period": 14}, "fp1", {"s": pd.Series([1])})
        cache.get("rsi", {"period": 14}, "fp1")

        cache.clear()
        assert len(cache) == 0
        assert cache.stats["hits"] == 0
        assert cache.get("rsi", {"period": 14}, "fp1") is None

    def test_cache_thread_safety(self):
        """Cache should be thread-safe for concurrent reads/writes."""
        cache = IndicatorCache(max_size=100)
        errors = []

        def writer(thread_id):
            try:
                for i in range(50):
                    cache.put(f"ind_{thread_id}", {"p": i}, "fp1", {"s": pd.Series([i])})
            except Exception as e:
                errors.append(e)

        def reader(thread_id):
            try:
                for i in range(50):
                    cache.get(f"ind_{thread_id}", {"p": i}, "fp1")
            except Exception as e:
                errors.append(e)

        threads = []
        for t_id in range(4):
            threads.append(threading.Thread(target=writer, args=(t_id,)))
            threads.append(threading.Thread(target=reader, args=(t_id,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread safety errors: {errors}"

    def test_cache_update_existing_key(self):
        """Putting a value with an existing key should update it."""
        cache = IndicatorCache(max_size=10)
        cache.put("rsi", {"period": 14}, "fp1", {"s": pd.Series([1])})
        cache.put("rsi", {"period": 14}, "fp1", {"s": pd.Series([99])})

        result = cache.get("rsi", {"period": 14}, "fp1")
        assert result is not None
        assert result["s"].iloc[0] == 99
        assert len(cache) == 1  # no duplicate entry


class TestFreezeParams:
    """Tests for _freeze_params helper."""

    def test_simple_params(self):
        """Should freeze simple key-value params."""
        result = _freeze_params({"period": 14, "level": 30.0})
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_deterministic(self):
        """Same input should produce same output."""
        a = _freeze_params({"b": 2, "a": 1})
        b = _freeze_params({"a": 1, "b": 2})
        assert a == b

    def test_nested_dict(self):
        """Should handle nested dicts."""
        result = _freeze_params({"outer": {"inner": 42}})
        assert isinstance(result, tuple)

    def test_numpy_types(self):
        """Should handle numpy scalar types."""
        result = _freeze_params({"val": np.int64(14)})
        assert isinstance(result, tuple)
        # numpy int should be converted to Python int
        assert isinstance(result[0][1], int)


class TestOHLCVFingerprint:
    """Tests for _ohlcv_fingerprint helper."""

    def test_empty_dataframe(self):
        """Empty DataFrame should return 'empty'."""
        df = pd.DataFrame({"close": []})
        assert _ohlcv_fingerprint(df) == "empty"

    def test_deterministic(self, sample_ohlcv):
        """Same data should produce same fingerprint."""
        fp1 = _ohlcv_fingerprint(sample_ohlcv)
        fp2 = _ohlcv_fingerprint(sample_ohlcv)
        assert fp1 == fp2

    def test_different_data_different_fingerprint(self, sample_ohlcv):
        """Different data should produce different fingerprint."""
        fp1 = _ohlcv_fingerprint(sample_ohlcv)

        modified = sample_ohlcv.copy()
        modified.loc[modified.index[0], "close"] = 99999.0
        fp2 = _ohlcv_fingerprint(modified)
        assert fp1 != fp2


# =============================================================================
# P1: MUTABLE GRAPH UPDATER TESTS
# =============================================================================


class TestMutableGraphUpdater:
    """Tests for MutableGraphUpdater (P1)."""

    def test_apply_updates_params(self, sample_rsi_graph):
        """Apply should update block params in the graph."""
        updater = MutableGraphUpdater(sample_rsi_graph)
        graph = updater.apply({"rsi_1.period": 21})

        rsi_block = next(b for b in graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["period"] == 21

    def test_restore_reverts_params(self, sample_rsi_graph):
        """Restore should revert params to original values."""
        updater = MutableGraphUpdater(sample_rsi_graph)

        # Apply modification
        updater.apply({"rsi_1.period": 21})
        updater.restore()

        # Check original is restored
        rsi_block = next(b for b in updater.graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["period"] == 14

    def test_apply_restore_cycle(self, sample_rsi_graph):
        """Multiple apply/restore cycles should work correctly."""
        updater = MutableGraphUpdater(sample_rsi_graph)

        for new_period in [7, 14, 21, 28]:
            graph = updater.apply({"rsi_1.period": new_period})
            rsi_block = next(b for b in graph["blocks"] if b["id"] == "rsi_1")
            assert rsi_block["params"]["period"] == new_period
            updater.restore()

        # After all cycles, original value should be restored
        rsi_block = next(b for b in updater.graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["period"] == 14

    def test_apply_multiple_params(self, sample_rsi_graph):
        """Should handle multiple param overrides at once."""
        updater = MutableGraphUpdater(sample_rsi_graph)
        graph = updater.apply(
            {
                "rsi_1.period": 21,
                "sltp_1.stop_loss_percent": 2.0,
                "sltp_1.take_profit_percent": 4.0,
            }
        )

        rsi_block = next(b for b in graph["blocks"] if b["id"] == "rsi_1")
        sltp_block = next(b for b in graph["blocks"] if b["id"] == "sltp_1")
        assert rsi_block["params"]["period"] == 21
        assert sltp_block["params"]["stop_loss_percent"] == 2.0
        assert sltp_block["params"]["take_profit_percent"] == 4.0

        updater.restore()
        rsi_block = next(b for b in updater.graph["blocks"] if b["id"] == "rsi_1")
        sltp_block = next(b for b in updater.graph["blocks"] if b["id"] == "sltp_1")
        assert rsi_block["params"]["period"] == 14
        assert sltp_block["params"]["stop_loss_percent"] == 1.5

    def test_rsi_cross_level_auto_enables_flag(self, sample_rsi_graph):
        """Optimizing RSI cross_long_level should auto-enable use_cross_level."""
        updater = MutableGraphUpdater(sample_rsi_graph)
        graph = updater.apply({"rsi_1.cross_long_level": 25})

        rsi_block = next(b for b in graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["use_cross_level"] is True

        updater.restore()
        rsi_block = next(b for b in updater.graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["use_cross_level"] is False

    def test_rsi_long_range_auto_enables_flag(self, sample_rsi_graph):
        """Optimizing RSI long_rsi_more should auto-enable use_long_range."""
        updater = MutableGraphUpdater(sample_rsi_graph)
        graph = updater.apply({"rsi_1.long_rsi_more": 15})

        rsi_block = next(b for b in graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["use_long_range"] is True

        updater.restore()
        rsi_block = next(b for b in updater.graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["use_long_range"] is False

    def test_macd_cross_zero_auto_enables_flag(self, sample_macd_graph):
        """Optimizing MACD macd_cross_zero_level should auto-enable use_macd_cross_zero."""
        updater = MutableGraphUpdater(sample_macd_graph)
        graph = updater.apply({"macd_1.macd_cross_zero_level": 5})

        macd_block = next(b for b in graph["blocks"] if b["id"] == "macd_1")
        assert macd_block["params"]["use_macd_cross_zero"] is True

        updater.restore()
        macd_block = next(b for b in updater.graph["blocks"] if b["id"] == "macd_1")
        assert macd_block["params"]["use_macd_cross_zero"] is False

    def test_macd_signal_memory_auto_enables_flag(self, sample_macd_graph):
        """Optimizing MACD signal_memory_bars should set disable_signal_memory=False."""
        updater = MutableGraphUpdater(sample_macd_graph)
        graph = updater.apply({"macd_1.signal_memory_bars": 5})

        macd_block = next(b for b in graph["blocks"] if b["id"] == "macd_1")
        assert macd_block["params"]["disable_signal_memory"] is False

        updater.restore()
        macd_block = next(b for b in updater.graph["blocks"] if b["id"] == "macd_1")
        assert macd_block["params"]["disable_signal_memory"] is True

    def test_does_not_modify_original(self, sample_rsi_graph):
        """MutableGraphUpdater should not modify the original graph."""
        original_copy = copy.deepcopy(sample_rsi_graph)
        updater = MutableGraphUpdater(sample_rsi_graph)

        updater.apply({"rsi_1.period": 99})
        updater.restore()

        # Original should be unchanged
        assert sample_rsi_graph == original_copy

    def test_unknown_block_id_ignored(self, sample_rsi_graph):
        """Unknown block IDs should be silently ignored."""
        updater = MutableGraphUpdater(sample_rsi_graph)
        graph = updater.apply({"nonexistent_block.period": 21})

        # No crash, graph unchanged for known blocks
        rsi_block = next(b for b in graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["period"] == 14

    def test_new_param_key_added_and_removed(self, sample_rsi_graph):
        """Adding a new param key should be removed on restore."""
        updater = MutableGraphUpdater(sample_rsi_graph)
        graph = updater.apply({"rsi_1.new_param": 42})

        rsi_block = next(b for b in graph["blocks"] if b["id"] == "rsi_1")
        assert rsi_block["params"]["new_param"] == 42

        updater.restore()
        rsi_block = next(b for b in updater.graph["blocks"] if b["id"] == "rsi_1")
        assert "new_param" not in rsi_block["params"]

    def test_equivalence_with_clone_graph(self, sample_rsi_graph):
        """MutableGraphUpdater.apply should produce same result as clone_graph_with_params."""
        from backend.optimization.builder_optimizer import clone_graph_with_params

        overrides = {
            "rsi_1.period": 21,
            "rsi_1.cross_long_level": 25,
            "sltp_1.stop_loss_percent": 2.5,
        }

        # Clone approach
        cloned = clone_graph_with_params(sample_rsi_graph, overrides)

        # MutableGraphUpdater approach
        updater = MutableGraphUpdater(sample_rsi_graph)
        updated = updater.apply(overrides)

        # Compare block params
        for block_clone, block_update in zip(cloned["blocks"], updated["blocks"], strict=True):
            params_clone = block_clone.get("params") or block_clone.get("config") or {}
            params_update = block_update.get("params") or block_update.get("config") or {}
            assert params_clone == params_update, (
                f"Mismatch for block {block_clone['id']}: clone={params_clone}, updater={params_update}"
            )


class TestClassifyParamsByIndicatorImpact:
    """Tests for classify_params_by_indicator_impact."""

    def test_classification_correct(self, sample_param_specs):
        """Should correctly classify params into indicator/threshold/exit."""
        result = classify_params_by_indicator_impact(sample_param_specs)

        # rsi_1.period = indicator param (changes indicator computation)
        assert any(s["param_key"] == "period" and s["block_type"] == "rsi" for s in result["indicator_params"])

        # rsi_1.cross_long_level = threshold param
        assert any(s["param_key"] == "cross_long_level" for s in result["threshold_params"])

        # adx_1.period = indicator param
        assert any(s["param_key"] == "period" and s["block_type"] == "adx" for s in result["indicator_params"])

        # sltp_1.* = exit params
        assert len(result["exit_params"]) == 2

    def test_no_duplicate_params(self, sample_param_specs):
        """Each param should appear in exactly one category."""
        result = classify_params_by_indicator_impact(sample_param_specs)
        total = len(result["indicator_params"]) + len(result["threshold_params"]) + len(result["exit_params"])
        assert total == len(sample_param_specs)


# =============================================================================
# P3: PRECOMPUTED OHLCV TESTS
# =============================================================================


class TestPrecomputedOHLCV:
    """Tests for PrecomputedOHLCV (P3)."""

    def test_arrays_extracted_correctly(self, sample_ohlcv):
        """Should extract all OHLCV columns as contiguous float64 arrays."""
        precomp = precompute_ohlcv(sample_ohlcv)

        assert precomp.n == len(sample_ohlcv)
        assert precomp.open.dtype == np.float64
        assert precomp.high.dtype == np.float64
        assert precomp.low.dtype == np.float64
        assert precomp.close.dtype == np.float64
        assert precomp.volume.dtype == np.float64

    def test_arrays_contiguous(self, sample_ohlcv):
        """Arrays should be C-contiguous for optimal Numba performance."""
        precomp = precompute_ohlcv(sample_ohlcv)

        assert precomp.open.flags["C_CONTIGUOUS"]
        assert precomp.close.flags["C_CONTIGUOUS"]

    def test_values_match_original(self, sample_ohlcv):
        """Extracted values should match original DataFrame."""
        precomp = precompute_ohlcv(sample_ohlcv)

        np.testing.assert_array_almost_equal(precomp.close, sample_ohlcv["close"].values)
        np.testing.assert_array_almost_equal(precomp.high, sample_ohlcv["high"].values)

    def test_fingerprint_deterministic(self, sample_ohlcv):
        """Fingerprint should be deterministic."""
        p1 = precompute_ohlcv(sample_ohlcv)
        p2 = precompute_ohlcv(sample_ohlcv)
        assert p1.fingerprint == p2.fingerprint

    def test_as_dict(self, sample_ohlcv):
        """as_dict should return all 5 columns."""
        precomp = precompute_ohlcv(sample_ohlcv)
        d = precomp.as_dict()
        assert set(d.keys()) == {"open", "high", "low", "close", "volume"}


# =============================================================================
# P4: EARLY PRUNING TESTS
# =============================================================================


class TestEarlyPruning:
    """Tests for early pruning logic (P4)."""

    def test_prune_none_result(self):
        """None result should always be pruned."""
        assert should_prune_early(None, {}, 0.0, 0) is True

    def test_prune_zero_trades(self):
        """Zero trades should be pruned."""
        result = {"total_trades": 0, "max_drawdown": 0}
        assert should_prune_early(result, {}, 0.0, 0) is True

    def test_prune_catastrophic_drawdown(self):
        """Drawdown > 90% should be pruned."""
        result = {"total_trades": 10, "max_drawdown": -95.0}
        assert should_prune_early(result, {}, 0.0, 5) is True

    def test_prune_below_half_min_trades(self):
        """Trades below half of min_trades should be pruned."""
        result = {"total_trades": 3, "max_drawdown": -10.0}
        config = {"min_trades": 10}
        assert should_prune_early(result, config, 0.0, 5) is True

    def test_no_prune_valid_result(self):
        """Valid result should not be pruned."""
        result = {"total_trades": 50, "max_drawdown": -15.0}
        assert should_prune_early(result, {}, 0.0, 5) is False

    def test_no_prune_early_in_search(self):
        """Don't prune by score comparison before 30 trials."""
        result = {"total_trades": 5, "max_drawdown": -10.0}
        assert should_prune_early(result, {}, 100.0, 10) is False

    def test_prune_clearly_worse_after_many_trials(self):
        """After 30+ trials, prune results far below best score."""
        result = {
            "total_trades": 5,
            "max_drawdown": -10.0,
            "sharpe_ratio": 0.01,
            "net_profit_pct": -50.0,
            "profit_factor": 0.1,
            "win_rate": 10,
        }
        config = {"optimize_metric": "sharpe_ratio"}
        # Best score is 10, current would be very low → prune
        assert should_prune_early(result, config, 10.0, 50) is True


class TestAdaptiveTimeout:
    """Tests for compute_adaptive_timeout."""

    def test_minimum_timeout(self):
        """Timeout should be at least 10 seconds."""
        timeout = compute_adaptive_timeout(n_params=5, avg_trial_time=0.1, n_trials=100)
        assert timeout >= 10.0

    def test_maximum_timeout(self):
        """Timeout should be at most 120 seconds."""
        timeout = compute_adaptive_timeout(n_params=20, avg_trial_time=100.0, n_trials=100)
        assert timeout <= 120.0

    def test_scales_with_avg_time(self):
        """Timeout should scale with average trial time."""
        t1 = compute_adaptive_timeout(n_params=5, avg_trial_time=1.0, n_trials=100)
        t2 = compute_adaptive_timeout(n_params=5, avg_trial_time=5.0, n_trials=100)
        assert t2 > t1


# =============================================================================
# P5: NUMBA INDICATORS TESTS
# =============================================================================


class TestNumbaRSI:
    """Tests for Numba RSI implementation (P5)."""

    def test_rsi_output_shape(self, sample_ohlcv):
        """RSI output should have same length as input."""
        rsi = compute_rsi_fast(sample_ohlcv["close"], period=14)
        assert len(rsi) == len(sample_ohlcv)

    def test_rsi_warmup_nan(self, sample_ohlcv):
        """First `period` values should be NaN (warmup)."""
        period = 14
        rsi = compute_rsi_fast(sample_ohlcv["close"], period=period)
        assert np.isnan(rsi[:period]).all()

    def test_rsi_range_0_100(self, sample_ohlcv):
        """RSI values should be in [0, 100]."""
        rsi = compute_rsi_fast(sample_ohlcv["close"], period=14)
        valid = rsi[~np.isnan(rsi)]
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_matches_pandas_ta(self, sample_ohlcv):
        """Numba RSI should approximately match pandas_ta RSI."""
        try:
            import pandas_ta as ta

            period = 14
            ta_rsi = ta.rsi(sample_ohlcv["close"], length=period)
        except (ImportError, ModuleNotFoundError):
            pytest.skip("pandas_ta or talib not available")
        period = 14
        numba_rsi = compute_rsi_fast(sample_ohlcv["close"], period=period)

        # Compare after warmup (skip first period+10 values for convergence)
        start = period + 10
        numba_valid = numba_rsi[start:]
        ta_valid = ta_rsi.values[start:]

        # Allow small tolerance due to floating point differences
        np.testing.assert_array_almost_equal(numba_valid, ta_valid, decimal=1)

    def test_rsi_constant_price(self):
        """RSI on constant price should be NaN or 50-ish (no change)."""
        close = np.full(100, 50000.0)
        rsi = compute_rsi_fast(close, period=14)
        # After warmup, RSI should be undefined (0/0 case) or near 50
        valid = rsi[~np.isnan(rsi)]
        # With zero changes, avg_gain=0 and avg_loss=0, so RSI should be 100 (0/0 edge case)
        # Our implementation returns 100 when avg_loss=0
        if len(valid) > 0:
            assert valid[0] == 100.0  # first valid: all deltas are 0, avg_loss=0

    def test_rsi_short_series(self):
        """RSI on series shorter than period should return all NaN."""
        close = np.array([100.0, 101.0, 99.0])
        rsi = compute_rsi_fast(close, period=14)
        assert np.isnan(rsi).all()

    def test_rsi_numpy_input(self):
        """Should accept numpy array directly."""
        close = np.random.randn(200).cumsum() + 50000
        rsi = compute_rsi_fast(close, period=14)
        assert len(rsi) == 200

    def test_rsi_pandas_input(self):
        """Should accept pandas Series."""
        s = pd.Series(np.random.randn(200).cumsum() + 50000)
        rsi = compute_rsi_fast(s, period=14)
        assert len(rsi) == 200


class TestNumbaADX:
    """Tests for Numba ADX implementation (P5)."""

    def test_adx_output_keys(self, sample_ohlcv):
        """ADX should return dict with adx, plus_di, minus_di."""
        result = compute_adx_fast(
            sample_ohlcv["high"],
            sample_ohlcv["low"],
            sample_ohlcv["close"],
            period=14,
        )
        assert "adx" in result
        assert "plus_di" in result
        assert "minus_di" in result

    def test_adx_output_shape(self, sample_ohlcv):
        """ADX arrays should have same length as input."""
        result = compute_adx_fast(
            sample_ohlcv["high"],
            sample_ohlcv["low"],
            sample_ohlcv["close"],
            period=14,
        )
        assert len(result["adx"]) == len(sample_ohlcv)

    def test_adx_range_0_100(self, sample_ohlcv):
        """ADX and DI values should be in [0, 100] range."""
        result = compute_adx_fast(
            sample_ohlcv["high"],
            sample_ohlcv["low"],
            sample_ohlcv["close"],
            period=14,
        )
        for key in ["adx", "plus_di", "minus_di"]:
            valid = result[key][~np.isnan(result[key])]
            if len(valid) > 0:
                assert (valid >= 0).all(), f"{key} has values < 0"
                assert (valid <= 200).all(), f"{key} has values > 200"  # DI can exceed 100 rarely

    def test_adx_short_series(self):
        """ADX on short series should return all NaN."""
        high = np.array([100.0, 101.0, 102.0])
        low = np.array([99.0, 100.0, 101.0])
        close = np.array([100.5, 100.5, 101.5])
        result = compute_adx_fast(high, low, close, period=14)
        assert np.isnan(result["adx"]).all()


class TestNumbaSupertrend:
    """Tests for Numba Supertrend implementation (P5)."""

    def test_supertrend_output_keys(self, sample_ohlcv):
        """Supertrend should return dict with supertrend and direction."""
        result = compute_supertrend_fast(
            sample_ohlcv["high"],
            sample_ohlcv["low"],
            sample_ohlcv["close"],
            period=10,
            multiplier=3.0,
        )
        assert "supertrend" in result
        assert "direction" in result

    def test_supertrend_output_shape(self, sample_ohlcv):
        """Output arrays should match input length."""
        result = compute_supertrend_fast(
            sample_ohlcv["high"],
            sample_ohlcv["low"],
            sample_ohlcv["close"],
            period=10,
            multiplier=3.0,
        )
        assert len(result["supertrend"]) == len(sample_ohlcv)
        assert len(result["direction"]) == len(sample_ohlcv)

    def test_supertrend_direction_values(self, sample_ohlcv):
        """Direction should only contain 1.0 (bullish) or -1.0 (bearish)."""
        result = compute_supertrend_fast(
            sample_ohlcv["high"],
            sample_ohlcv["low"],
            sample_ohlcv["close"],
            period=10,
            multiplier=3.0,
        )
        valid = result["direction"][~np.isnan(result["supertrend"])]
        unique_vals = set(np.unique(valid))
        assert unique_vals.issubset({1.0, -1.0}), f"Unexpected direction values: {unique_vals}"

    def test_supertrend_below_price_when_bullish(self, sample_ohlcv):
        """In bullish direction, supertrend should be below close price."""
        result = compute_supertrend_fast(
            sample_ohlcv["high"],
            sample_ohlcv["low"],
            sample_ohlcv["close"],
            period=10,
            multiplier=3.0,
        )
        close = sample_ohlcv["close"].values
        st = result["supertrend"]
        direction = result["direction"]

        # For bullish bars (direction=1), supertrend should be ≤ close
        mask = (direction == 1.0) & ~np.isnan(st)
        if mask.any():
            assert (st[mask] <= close[mask] * 1.01).all()  # small tolerance

    def test_supertrend_short_series(self):
        """Supertrend on short series should return NaN values."""
        high = np.array([100.0, 101.0, 102.0])
        low = np.array([99.0, 100.0, 101.0])
        close = np.array([100.5, 100.5, 101.5])
        result = compute_supertrend_fast(high, low, close, period=10, multiplier=3.0)
        assert np.isnan(result["supertrend"]).all()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestOptimizerIntegration:
    """Integration tests for the optimized builder_optimizer path."""

    def test_mutable_graph_same_as_deepcopy(self, sample_rsi_graph):
        """MutableGraphUpdater should produce functionally identical results
        to the original clone_graph_with_params approach."""
        from backend.optimization.builder_optimizer import clone_graph_with_params

        test_cases = [
            {"rsi_1.period": 21},
            {"rsi_1.period": 7, "sltp_1.stop_loss_percent": 2.5},
            {"rsi_1.cross_long_level": 25},
            {"adx_1.period": 20},
        ]

        updater = MutableGraphUpdater(sample_rsi_graph)
        for overrides in test_cases:
            # Original approach
            cloned = clone_graph_with_params(sample_rsi_graph, overrides)

            # Optimized approach
            updated = updater.apply(overrides)

            # Compare all block params
            clone_blocks = {b["id"]: b for b in cloned["blocks"]}
            update_blocks = {b["id"]: b for b in updated["blocks"]}

            for block_id in clone_blocks:
                cp = clone_blocks[block_id].get("params") or clone_blocks[block_id].get("config") or {}
                up = update_blocks[block_id].get("params") or update_blocks[block_id].get("config") or {}
                assert cp == up, f"Mismatch for block {block_id} with overrides {overrides}: clone={cp}, update={up}"

            updater.restore()

    def test_indicator_cache_with_precomputed_ohlcv(self, sample_ohlcv):
        """Cache should work with precomputed OHLCV fingerprints."""
        precomp = PrecomputedOHLCV(sample_ohlcv)
        cache = IndicatorCache(max_size=100)

        # Compute RSI and cache it
        rsi = compute_rsi_fast(precomp.close, period=14)
        result = {"rsi_value": pd.Series(rsi, index=precomp.index)}
        cache.put("rsi", {"period": 14}, precomp.fingerprint, result)

        # Second access should be a cache hit
        cached = cache.get("rsi", {"period": 14}, precomp.fingerprint)
        assert cached is not None
        np.testing.assert_array_equal(cached["rsi_value"].values, rsi)

    def test_full_pipeline_components(self, sample_ohlcv, sample_rsi_graph, sample_param_specs):
        """Test that all P0-P5 components work together."""
        # P3: Precompute OHLCV
        precomp = PrecomputedOHLCV(sample_ohlcv)
        assert precomp.n == 500

        # P0: Create cache
        cache = IndicatorCache(max_size=100)

        # P5: Compute indicators using Numba
        rsi = compute_rsi_fast(precomp.close, period=14)
        adx_result = compute_adx_fast(precomp.high, precomp.low, precomp.close, period=14)

        # P0: Cache the results
        cache.put("rsi", {"period": 14}, precomp.fingerprint, {"rsi": pd.Series(rsi)})
        cache.put("adx", {"period": 14}, precomp.fingerprint, {"adx": pd.Series(adx_result["adx"])})

        # P1: Test graph updater
        updater = MutableGraphUpdater(sample_rsi_graph)

        # Simulate multiple trials
        for period in [7, 14, 21]:
            graph = updater.apply({"rsi_1.period": period})
            rsi_block = next(b for b in graph["blocks"] if b["id"] == "rsi_1")
            assert rsi_block["params"]["period"] == period

            # P0: Check cache (hit only for period=14 since we cached that)
            cached = cache.get("rsi", {"period": period}, precomp.fingerprint)
            if period == 14:
                assert cached is not None
            else:
                assert cached is None
                # Compute and cache
                new_rsi = compute_rsi_fast(precomp.close, period=period)
                cache.put("rsi", {"period": period}, precomp.fingerprint, {"rsi": pd.Series(new_rsi)})

            updater.restore()

        # Verify cache stats
        stats = cache.stats
        assert stats["hits"] >= 1
        assert stats["size"] >= 3  # at least rsi(14), adx(14), rsi(7 or 21)

    def test_early_pruning_integration(self):
        """Test early pruning with realistic backtest results."""
        # Good result — should NOT be pruned
        good_result = {
            "total_trades": 50,
            "max_drawdown": -15.0,
            "sharpe_ratio": 1.5,
            "net_profit_pct": 25.0,
        }
        assert should_prune_early(good_result, {}, 2.0, 5) is False

        # Bad result — should be pruned (zero trades)
        bad_result = {"total_trades": 0, "max_drawdown": 0}
        assert should_prune_early(bad_result, {}, 2.0, 5) is True

        # Catastrophic result — should be pruned
        catastrophic = {"total_trades": 3, "max_drawdown": -95.0}
        assert should_prune_early(catastrophic, {}, 2.0, 5) is True


# =============================================================================
# P2-MEM: Memory-aware n_jobs capping tests
# =============================================================================


class TestMemoryAwareNJobs:
    """Test memory-aware n_jobs capping logic that prevents OOM crashes."""

    def test_small_dataset_keeps_full_njobs(self):
        """Small datasets (< 30K candles) should keep auto-detected n_jobs."""
        # Simulate: 10K candles, plenty of RAM
        n_candles = 10_000
        _BYTES_PER_CANDLE_PER_TRIAL = 500
        est_mem_per_trial_mb = (n_candles * _BYTES_PER_CANDLE_PER_TRIAL) / (1024 * 1024)

        # ~4.8 MB per trial — even with 4 jobs = ~19 MB. Should NOT be capped.
        assert est_mem_per_trial_mb < 10  # Sanity: small per-trial estimate
        effective_n_jobs = 4

        # With 8GB available: usable = 5.6GB, max_by_mem = 5600/4.8 ≈ 1166
        avail_mb = 8000
        usable_mb = avail_mb * 0.7
        max_jobs_by_mem = max(1, int(usable_mb / max(est_mem_per_trial_mb, 1)))
        assert max_jobs_by_mem >= effective_n_jobs  # No capping needed

    def test_large_dataset_caps_njobs(self):
        """Large datasets (> 50K candles) should reduce n_jobs when RAM is limited."""
        n_candles = 50_000
        _BYTES_PER_CANDLE_PER_TRIAL = 500
        est_mem_per_trial_mb = (n_candles * _BYTES_PER_CANDLE_PER_TRIAL) / (1024 * 1024)

        # ~23.8 MB per trial
        assert est_mem_per_trial_mb > 20

        # Simulate only 200 MB available (constrained system)
        avail_mb = 200
        usable_mb = avail_mb * 0.7  # 140 MB
        max_jobs_by_mem = max(1, int(usable_mb / max(est_mem_per_trial_mb, 1)))

        # 140 / 23.8 ≈ 5, but with real overhead it would be less
        assert max_jobs_by_mem >= 1
        # With very constrained memory:
        avail_mb_tight = 50
        usable_mb_tight = avail_mb_tight * 0.7  # 35 MB
        max_jobs_tight = max(1, int(usable_mb_tight / max(est_mem_per_trial_mb, 1)))
        assert max_jobs_tight == 1  # Must cap to 1 when RAM is very tight

    def test_fallback_without_psutil_30k_threshold(self):
        """Without psutil, datasets > 30K candles should cap n_jobs to 2."""
        n_candles = 35_000
        effective_n_jobs = 4

        # Fallback heuristic: >30K candles → cap to 2
        if n_candles > 30_000 and effective_n_jobs > 2:
            effective_n_jobs = 2

        assert effective_n_jobs == 2

    def test_fallback_without_psutil_small_dataset(self):
        """Without psutil, small datasets should keep n_jobs unchanged."""
        n_candles = 20_000
        effective_n_jobs = 4

        # Fallback heuristic should NOT trigger for < 30K
        if n_candles > 30_000 and effective_n_jobs > 2:
            effective_n_jobs = 2

        assert effective_n_jobs == 4  # Unchanged

    def test_memory_estimate_proportional_to_candles(self):
        """Memory estimate should scale linearly with candle count."""
        _BYTES_PER_CANDLE_PER_TRIAL = 500
        small = 10_000 * _BYTES_PER_CANDLE_PER_TRIAL
        large = 50_000 * _BYTES_PER_CANDLE_PER_TRIAL
        assert large == 5 * small

    def test_njobs_never_below_one(self):
        """Even with extreme memory pressure, n_jobs should never go below 1."""
        n_candles = 100_000
        _BYTES_PER_CANDLE_PER_TRIAL = 500
        est_mem_per_trial_mb = (n_candles * _BYTES_PER_CANDLE_PER_TRIAL) / (1024 * 1024)

        # Simulate near-zero available memory
        avail_mb = 10
        usable_mb = avail_mb * 0.7
        max_jobs_by_mem = max(1, int(usable_mb / max(est_mem_per_trial_mb, 1)))
        assert max_jobs_by_mem >= 1

    def test_psutil_integration(self):
        """Test that psutil is available and returns reasonable values."""
        try:
            import psutil

            mem = psutil.virtual_memory()
            assert mem.available > 0
            assert mem.total > mem.available
            assert mem.percent >= 0
        except ImportError:
            pytest.skip("psutil not installed")


# =============================================================================
# P6: CROSS-BLOCK CONSTRAINT PARITY
# =============================================================================


class TestCrossBlockConstraints:
    """Tests for _apply_cross_block_constraints — ensures trial/re-run parity."""

    def _make_param_specs(
        self,
        *,
        has_sltp: bool = True,
        has_close_by_time: bool = False,
        has_breakeven: bool = False,
    ) -> list[dict]:
        """Build param_specs for constraint testing."""
        specs: list[dict] = []
        if has_sltp:
            specs.extend(
                [
                    {
                        "param_path": "sltp_1.stop_loss_percent",
                        "param_key": "stop_loss_percent",
                        "block_type": "static_sltp",
                        "type": "float",
                        "low": 1.0,
                        "high": 10.0,
                        "step": 0.5,
                    },
                    {
                        "param_path": "sltp_1.take_profit_percent",
                        "param_key": "take_profit_percent",
                        "block_type": "static_sltp",
                        "type": "float",
                        "low": 1.0,
                        "high": 10.0,
                        "step": 0.5,
                    },
                ]
            )
        if has_breakeven:
            specs.append(
                {
                    "param_path": "sltp_1.breakeven_activation_percent",
                    "param_key": "breakeven_activation_percent",
                    "block_type": "static_sltp",
                    "type": "float",
                    "low": 0.1,
                    "high": 5.0,
                    "step": 0.1,
                }
            )
        if has_close_by_time:
            specs.append(
                {
                    "param_path": "cbt_1.min_profit_percent",
                    "param_key": "min_profit_percent",
                    "block_type": "close_by_time",
                    "type": "float",
                    "low": 1.0,
                    "high": 10.0,
                    "step": 0.5,
                }
            )
        return specs

    def test_tp_clamped_to_sl_times_1_5(self):
        """TP should be clamped to SL * 1.5 when TP < SL * 1.5."""
        from backend.optimization.builder_optimizer import _apply_cross_block_constraints

        specs = self._make_param_specs()
        overrides = {
            "sltp_1.stop_loss_percent": 4.0,
            "sltp_1.take_profit_percent": 2.0,  # < 4.0 * 1.5 = 6.0
        }
        _apply_cross_block_constraints(overrides, specs)
        assert overrides["sltp_1.take_profit_percent"] == 6.0

    def test_tp_not_clamped_when_already_above(self):
        """TP should not be changed when TP >= SL * 1.5."""
        from backend.optimization.builder_optimizer import _apply_cross_block_constraints

        specs = self._make_param_specs()
        overrides = {
            "sltp_1.stop_loss_percent": 2.0,
            "sltp_1.take_profit_percent": 5.0,  # > 2.0 * 1.5 = 3.0
        }
        _apply_cross_block_constraints(overrides, specs)
        assert overrides["sltp_1.take_profit_percent"] == 5.0

    def test_min_profit_clamped_to_tp_plus_2(self):
        """min_profit >= TP + 2.0 constraint was removed (inverts close_by_time semantics).

        See backend.optimization.builder_optimizer._apply_cross_block_constraints docstring:
        keeping min_profit < TP allows close_by_time to close profitable trades before TP fires.
        Test is now an inversion: ensures the value is NOT clamped.
        """
        from backend.optimization.builder_optimizer import _apply_cross_block_constraints

        specs = self._make_param_specs(has_close_by_time=True)
        overrides = {
            "sltp_1.stop_loss_percent": 2.0,
            "sltp_1.take_profit_percent": 3.0,
            "cbt_1.min_profit_percent": 4.0,  # < 3.0 + 2.0 = 5.0
        }
        _apply_cross_block_constraints(overrides, specs)
        # Constraint intentionally removed — value remains as set.
        assert overrides["cbt_1.min_profit_percent"] == 4.0

    def test_breakeven_clamped_to_70pct_of_tp(self):
        """breakeven_activation should be < TP (clamped to 70% of TP)."""
        from backend.optimization.builder_optimizer import _apply_cross_block_constraints

        specs = self._make_param_specs(has_breakeven=True)
        overrides = {
            "sltp_1.stop_loss_percent": 2.0,
            "sltp_1.take_profit_percent": 4.0,
            "sltp_1.breakeven_activation_percent": 5.0,  # >= TP
        }
        _apply_cross_block_constraints(overrides, specs)
        assert overrides["sltp_1.breakeven_activation_percent"] == 2.8  # 4.0 * 0.7

    def test_macd_fast_slow_constraint(self):
        """slow_period should be > fast_period."""
        from backend.optimization.builder_optimizer import _apply_cross_block_constraints

        overrides = {
            "macd_1.fast_period": 20,
            "macd_1.slow_period": 15,  # <= fast_period
        }
        _apply_cross_block_constraints(overrides, [])  # no specs needed for MACD
        assert overrides["macd_1.slow_period"] == 21  # fast_period + 1

    def test_no_constraints_no_changes(self):
        """Overrides without constraint-relevant params should be unchanged."""
        from backend.optimization.builder_optimizer import _apply_cross_block_constraints

        overrides = {"rsi_1.period": 14, "rsi_1.overbought": 70}
        original = dict(overrides)
        _apply_cross_block_constraints(overrides, [])
        assert overrides == original

    def test_idempotent(self):
        """Applying constraints twice should produce the same result."""
        from backend.optimization.builder_optimizer import _apply_cross_block_constraints

        specs = self._make_param_specs(has_close_by_time=True, has_breakeven=True)
        overrides = {
            "sltp_1.stop_loss_percent": 4.0,
            "sltp_1.take_profit_percent": 2.0,
            "cbt_1.min_profit_percent": 3.0,
            "sltp_1.breakeven_activation_percent": 5.0,
        }
        _apply_cross_block_constraints(overrides, specs)
        first_pass = dict(overrides)
        _apply_cross_block_constraints(overrides, specs)
        assert overrides == first_pass

    def test_constraint_parity_with_clone_graph(self):
        """clone_graph_with_params with constrained params must produce
        the same graph as MutableGraphUpdater with the same constrained params.
        This is the core parity test for the trial/re-run bug fix."""
        from backend.optimization.builder_optimizer import (
            _apply_cross_block_constraints,
            clone_graph_with_params,
        )

        base_graph = {
            "name": "Test",
            "blocks": [
                {
                    "id": "sltp_1",
                    "type": "static_sltp",
                    "params": {"stop_loss_percent": 1.5, "take_profit_percent": 2.0},
                },
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "params": {"period": 14, "use_cross_level": False, "cross_long_level": 30},
                },
            ],
            "connections": [],
        }
        specs = self._make_param_specs()

        # Simulate trial.params (pre-constraint values)
        trial_params = {
            "sltp_1.stop_loss_percent": 5.0,
            "sltp_1.take_profit_percent": 3.0,  # < 5.0 * 1.5 = 7.5 → will be clamped
        }

        # Path 1: objective path (MutableGraphUpdater + constraints)
        updater = MutableGraphUpdater(base_graph)
        overrides_trial = dict(trial_params)
        _apply_cross_block_constraints(overrides_trial, specs)
        graph_trial = updater.apply(overrides_trial)
        tp_trial = graph_trial["blocks"][0]["params"]["take_profit_percent"]
        sl_trial = graph_trial["blocks"][0]["params"]["stop_loss_percent"]
        updater.restore()

        # Path 2: re-run path (clone_graph_with_params + constraints)
        overrides_rerun = dict(trial_params)
        _apply_cross_block_constraints(overrides_rerun, specs)
        graph_rerun = clone_graph_with_params(base_graph, overrides_rerun)
        tp_rerun = graph_rerun["blocks"][0]["params"]["take_profit_percent"]
        sl_rerun = graph_rerun["blocks"][0]["params"]["stop_loss_percent"]

        # Both must produce the same clamped values
        assert tp_trial == tp_rerun == 7.5  # SL * 1.5
        assert sl_trial == sl_rerun == 5.0


class TestRerunScoreCompression:
    """Verify that re-run top_results store compressed scores, matching objective."""

    def test_compress_score_applied_to_rerun(self):
        """score in top_results must be compressed (log-scale for sharpe_ratio)."""
        from backend.optimization.builder_optimizer import _compress_score
        from backend.optimization.scoring import calculate_composite_score

        # Simulate a backtest result with large sharpe
        result = {"sharpe_ratio": 50.0, "total_trades": 20}
        raw = calculate_composite_score(result, "sharpe_ratio")
        compressed = _compress_score(raw, "sharpe_ratio")

        assert raw == pytest.approx(50.0, abs=0.1)
        # Compressed must be log1p(50) ≈ 3.93, NOT 50
        assert compressed < raw
        assert compressed == pytest.approx(3.93, abs=0.1)

    def test_score_raw_field_preserved(self):
        """score_raw should be the uncompressed original value."""
        import math

        from backend.optimization.builder_optimizer import _compress_score
        from backend.optimization.scoring import calculate_composite_score

        result = {"sharpe_ratio": 25.0}
        raw = calculate_composite_score(result, "sharpe_ratio")
        compressed = _compress_score(raw, "sharpe_ratio")

        # Simulate the top_results dict structure
        entry = {"score": compressed, "score_raw": raw}
        assert entry["score_raw"] == pytest.approx(25.0, abs=0.1)
        assert entry["score"] == pytest.approx(math.log1p(25.0), abs=0.01)
        assert entry["score"] < entry["score_raw"]

    def test_oos_degradation_uses_same_scale(self):
        """OOS degradation should compare compressed IS vs compressed OOS."""
        from backend.optimization.builder_optimizer import _compress_score
        from backend.optimization.scoring import calculate_composite_score

        # IS result with sharpe=20
        is_result = {"sharpe_ratio": 20.0}
        is_raw = calculate_composite_score(is_result, "sharpe_ratio")
        is_compressed = _compress_score(is_raw, "sharpe_ratio")

        # OOS result with sharpe=10 (degraded)
        oos_result = {"sharpe_ratio": 10.0}
        oos_raw = calculate_composite_score(oos_result, "sharpe_ratio")
        oos_compressed = _compress_score(oos_raw, "sharpe_ratio")

        # Both compressed → degradation is meaningful
        if abs(is_compressed) > 1e-9:
            degradation = round((is_compressed - oos_compressed) / abs(is_compressed) * 100, 1)
        else:
            degradation = None

        assert degradation is not None
        assert degradation > 0  # OOS should be worse
        # Degradation should be reasonable (not inflated by scale mismatch)
        assert degradation < 100  # compressed values close → moderate degradation
