"""
P3.1 Tests — TagNormalizer

Tests for synonym resolution, case normalization, deduplication,
and runtime synonym registration.
"""

from __future__ import annotations

import pytest

from backend.agents.memory.tag_normalizer import TagNormalizer, get_tag_normalizer

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def normalizer() -> TagNormalizer:
    """Fresh TagNormalizer instance (not the global singleton)."""
    return TagNormalizer()


# ============================================================================
# Synonym resolution
# ============================================================================


class TestSynonymResolution:
    """TZ: test_synonym_resolution — known aliases resolve to canonical."""

    def test_rsi_indicator_to_rsi(self, normalizer: TagNormalizer):
        assert normalizer.normalize("RSI_indicator") == "rsi"

    def test_relative_strength_index(self, normalizer: TagNormalizer):
        assert normalizer.normalize("relative-strength-index") == "rsi"

    def test_rsi_canonical(self, normalizer: TagNormalizer):
        assert normalizer.normalize("RSI") == "rsi"

    def test_macd_indicator(self, normalizer: TagNormalizer):
        assert normalizer.normalize("MACD_indicator") == "macd"

    def test_bollinger_bands(self, normalizer: TagNormalizer):
        assert normalizer.normalize("bollinger_bands") == "bollinger"

    def test_bb_to_bollinger(self, normalizer: TagNormalizer):
        assert normalizer.normalize("BB") == "bollinger"

    def test_ema_alias(self, normalizer: TagNormalizer):
        assert normalizer.normalize("exponential_moving_average") == "ema"

    def test_atr_alias(self, normalizer: TagNormalizer):
        assert normalizer.normalize("average-true-range") == "atr"

    def test_trading_alias(self, normalizer: TagNormalizer):
        assert normalizer.normalize("trade") == "trading"

    def test_backtest_alias(self, normalizer: TagNormalizer):
        assert normalizer.normalize("backtesting") == "backtest"

    def test_strategy_alias(self, normalizer: TagNormalizer):
        assert normalizer.normalize("strategies") == "strategy"

    def test_optimization_alias(self, normalizer: TagNormalizer):
        assert normalizer.normalize("optimize") == "optimization"

    def test_risk_alias(self, normalizer: TagNormalizer):
        assert normalizer.normalize("risk_management") == "risk"

    def test_support_alias(self, normalizer: TagNormalizer):
        assert normalizer.normalize("support_level") == "support"

    def test_buy_long(self, normalizer: TagNormalizer):
        assert normalizer.normalize("long") == "buy"

    def test_sell_short(self, normalizer: TagNormalizer):
        assert normalizer.normalize("short") == "sell"

    def test_unknown_tag_lowered(self, normalizer: TagNormalizer):
        """Unknown tags are just lowercased, not dropped."""
        assert normalizer.normalize("MyCustomTag") == "mycustomtag"

    def test_empty_string(self, normalizer: TagNormalizer):
        assert normalizer.normalize("") == ""


# ============================================================================
# Case insensitivity
# ============================================================================


class TestCaseInsensitive:
    """TZ: test_case_insensitive — "Trading" == "trading"."""

    def test_upper(self, normalizer: TagNormalizer):
        assert normalizer.normalize("TRADING") == "trading"

    def test_title(self, normalizer: TagNormalizer):
        assert normalizer.normalize("Trading") == "trading"

    def test_mixed(self, normalizer: TagNormalizer):
        assert normalizer.normalize("tRaDiNg") == "trading"

    def test_rsi_mixed_case(self, normalizer: TagNormalizer):
        assert normalizer.normalize("Rsi") == "rsi"


# ============================================================================
# Deduplication
# ============================================================================


class TestDeduplication:
    """TZ: test_deduplication — ["rsi", "RSI", "rsi_indicator"] → ["rsi"]."""

    def test_basic_dedup(self, normalizer: TagNormalizer):
        result = normalizer.normalize_list(["rsi", "RSI", "rsi_indicator"])
        assert result == ["rsi"]

    def test_mixed_dedup(self, normalizer: TagNormalizer):
        result = normalizer.normalize_list(["trade", "Trading", "TRADING"])
        assert result == ["trading"]

    def test_no_dedup_needed(self, normalizer: TagNormalizer):
        result = normalizer.normalize_list(["rsi", "macd", "atr"])
        assert result == ["rsi", "macd", "atr"]

    def test_empty_list(self, normalizer: TagNormalizer):
        assert normalizer.normalize_list([]) == []

    def test_preserves_order(self, normalizer: TagNormalizer):
        result = normalizer.normalize_list(["macd", "rsi", "atr"])
        assert result == ["macd", "rsi", "atr"]


# ============================================================================
# Runtime synonym registration
# ============================================================================


class TestRuntimeSynonyms:
    """Test add_synonym and add_synonym_group at runtime."""

    def test_add_single_synonym(self, normalizer: TagNormalizer):
        normalizer.add_synonym("profit", "take_profit")
        assert normalizer.normalize("take_profit") == "profit"

    def test_add_synonym_group(self, normalizer: TagNormalizer):
        normalizer.add_synonym_group("volume", ["vol_indicator", "volume_analysis"])
        assert normalizer.normalize("vol_indicator") == "volume"
        assert normalizer.normalize("volume_analysis") == "volume"

    def test_is_known(self, normalizer: TagNormalizer):
        assert normalizer.is_known("RSI")
        assert normalizer.is_known("rsi_indicator")
        assert not normalizer.is_known("xyzzy_unknown_12345")

    def test_get_all_canonicals(self, normalizer: TagNormalizer):
        canonicals = normalizer.get_all_canonicals()
        assert "rsi" in canonicals
        assert "macd" in canonicals
        assert "trading" in canonicals
        # Should be sorted
        assert canonicals == sorted(canonicals)


# ============================================================================
# Extra synonyms at construction
# ============================================================================


class TestExtraSynonyms:
    """Test extra_synonyms passed at construction time."""

    def test_extra_synonyms_work(self):
        n = TagNormalizer(extra_synonyms={"leverage": ["lev", "leverage_ratio"]})
        assert n.normalize("lev") == "leverage"
        assert n.normalize("leverage_ratio") == "leverage"


# ============================================================================
# get_canonical & Singleton
# ============================================================================


class TestGetCanonical:
    def test_get_canonical_same_as_normalize(self, normalizer: TagNormalizer):
        assert normalizer.get_canonical("RSI_indicator") == normalizer.normalize("RSI_indicator")


class TestSingleton:
    def test_singleton_returns_same_instance(self):
        a = get_tag_normalizer()
        b = get_tag_normalizer()
        assert a is b

    def test_singleton_is_tag_normalizer(self):
        assert isinstance(get_tag_normalizer(), TagNormalizer)
