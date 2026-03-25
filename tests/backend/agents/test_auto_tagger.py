"""
P3.2 Tests -- AutoTagger

Tests for pattern extraction, keyword extraction, metadata mapping,
and integration with TagNormalizer.
"""

from __future__ import annotations

import pytest

from backend.agents.memory.auto_tagger import AutoTagger, get_auto_tagger

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def tagger() -> AutoTagger:
    """Fresh AutoTagger instance."""
    return AutoTagger()


# ============================================================================
# Symbol extraction
# ============================================================================


class TestAutoTagSymbols:
    """TZ: test_auto_tag_symbols -- "BTCUSDT price analysis" -> ["btcusdt"]."""

    def test_btcusdt(self, tagger: AutoTagger):
        tags = tagger.generate_tags("BTCUSDT price analysis")
        assert "btcusdt" in tags

    def test_ethusdt(self, tagger: AutoTagger):
        tags = tagger.generate_tags("ETHUSDT showing bullish pattern")
        assert "ethusdt" in tags

    def test_multiple_symbols(self, tagger: AutoTagger):
        tags = tagger.generate_tags("Compare BTCUSDT vs ETHUSDT volume")
        assert "btcusdt" in tags
        assert "ethusdt" in tags

    def test_no_symbol(self, tagger: AutoTagger):
        tags = tagger.generate_tags("Generic trading analysis")
        # Should not contain random uppercase abbreviations
        assert not any("usdt" in t for t in tags)


# ============================================================================
# Indicator extraction
# ============================================================================


class TestAutoTagIndicators:
    """TZ: test_auto_tag_indicators -- "RSI crossed above 70" -> ["rsi"]."""

    def test_rsi(self, tagger: AutoTagger):
        tags = tagger.generate_tags("RSI crossed above 70")
        assert "rsi" in tags

    def test_macd(self, tagger: AutoTagger):
        tags = tagger.generate_tags("MACD histogram turning positive")
        assert "macd" in tags

    def test_bollinger(self, tagger: AutoTagger):
        tags = tagger.generate_tags("Price touched Bollinger upper band")
        assert "bollinger" in tags

    def test_ema(self, tagger: AutoTagger):
        tags = tagger.generate_tags("EMA 20 crossed above EMA 50")
        assert "ema" in tags

    def test_atr(self, tagger: AutoTagger):
        tags = tagger.generate_tags("ATR suggests high volatility")
        assert "atr" in tags

    def test_case_insensitive_indicator(self, tagger: AutoTagger):
        tags = tagger.generate_tags("The rsi indicator shows overbought")
        assert "rsi" in tags


# ============================================================================
# Timeframe extraction
# ============================================================================


class TestAutoTagTimeframes:
    def test_15m(self, tagger: AutoTagger):
        tags = tagger.generate_tags("Analysis on 15m timeframe")
        assert "15m" in tags

    def test_4h(self, tagger: AutoTagger):
        tags = tagger.generate_tags("4h chart shows a triangle pattern")
        assert "4h" in tags

    def test_1d(self, tagger: AutoTagger):
        tags = tagger.generate_tags("Daily (1d) candle closed bullish")
        assert "1d" in tags


# ============================================================================
# Price action patterns
# ============================================================================


class TestAutoTagPriceAction:
    def test_support(self, tagger: AutoTagger):
        tags = tagger.generate_tags("Price bounced off support level at 60000")
        assert "support" in tags

    def test_resistance(self, tagger: AutoTagger):
        tags = tagger.generate_tags("Approaching resistance zone")
        assert "resistance" in tags

    def test_breakout(self, tagger: AutoTagger):
        tags = tagger.generate_tags("Breakout confirmed above 65000")
        assert "breakout" in tags

    def test_divergence(self, tagger: AutoTagger):
        tags = tagger.generate_tags("Bearish divergence on RSI")
        assert "divergence" in tags
        assert "rsi" in tags  # Also picks up RSI


# ============================================================================
# Keyword extraction
# ============================================================================


class TestKeywordExtraction:
    def test_extracts_top_keywords(self, tagger: AutoTagger):
        content = "bitcoin price bitcoin analysis bitcoin strategy trading"
        keywords = tagger.extract_keywords(content, top_k=3)
        assert "bitcoin" in keywords

    def test_filters_stop_words(self, tagger: AutoTagger):
        content = "the price is above the moving average"
        keywords = tagger.extract_keywords(content)
        assert "the" not in keywords
        assert "is" not in keywords

    def test_empty_content(self, tagger: AutoTagger):
        assert tagger.extract_keywords("") == []

    def test_only_stop_words(self, tagger: AutoTagger):
        assert tagger.extract_keywords("the a an is are") == []


# ============================================================================
# Metadata mapping
# ============================================================================


class TestMetadataMapping:
    def test_source_tag(self, tagger: AutoTagger):
        tags = tagger.generate_tags("result", source="backtest_engine")
        assert "source:backtest_engine" in tags

    def test_agent_namespace_tag(self, tagger: AutoTagger):
        tags = tagger.generate_tags("result", agent_namespace="deepseek")
        assert "agent:deepseek" in tags

    def test_shared_namespace_no_tag(self, tagger: AutoTagger):
        """Shared namespace should NOT produce an agent: tag."""
        tags = tagger.generate_tags("result", agent_namespace="shared")
        assert not any(t.startswith("agent:") for t in tags)

    def test_metadata_symbol(self, tagger: AutoTagger):
        tags = tagger.generate_tags("analysis", metadata={"symbol": "BTCUSDT"})
        assert "btcusdt" in tags

    def test_metadata_timeframe(self, tagger: AutoTagger):
        tags = tagger.generate_tags("analysis", metadata={"timeframe": "15m"})
        assert "15m" in tags

    def test_metadata_strategy_name(self, tagger: AutoTagger):
        tags = tagger.generate_tags("result", metadata={"strategy_name": "RSI_Crossover"})
        assert "rsi_crossover" in tags


# ============================================================================
# Existing tags preserved
# ============================================================================


class TestExistingTags:
    def test_existing_tags_included(self, tagger: AutoTagger):
        tags = tagger.generate_tags("price data", existing_tags=["custom_tag"])
        assert "custom_tag" in tags

    def test_existing_tags_normalized(self, tagger: AutoTagger):
        tags = tagger.generate_tags("price data", existing_tags=["RSI_indicator"])
        assert "rsi" in tags
        # Should not have the un-normalized form
        assert "rsi_indicator" not in tags


# ============================================================================
# Integration with TagNormalizer
# ============================================================================


class TestNormalizationIntegration:
    """Confirm auto-generated tags go through TagNormalizer."""

    def test_indicator_normalized(self, tagger: AutoTagger):
        """RSI pattern match -> normalized via TagNormalizer."""
        tags = tagger.generate_tags("RSI_indicator crossed 70")
        # "rsi_indicator" from keyword, "rsi" from pattern
        # Both should normalize to "rsi"
        assert "rsi" in tags
        assert tags.count("rsi") == 1  # Deduplicated

    def test_no_duplicates(self, tagger: AutoTagger):
        tags = tagger.generate_tags(
            "RSI analysis",
            existing_tags=["rsi", "RSI"],
        )
        assert tags.count("rsi") == 1


# ============================================================================
# Singleton
# ============================================================================


class TestAutoTaggerSingleton:
    def test_singleton_returns_same(self):
        a = get_auto_tagger()
        b = get_auto_tagger()
        assert a is b

    def test_singleton_is_auto_tagger(self):
        assert isinstance(get_auto_tagger(), AutoTagger)
