"""
Test Market Regime Detection module.
"""

import numpy as np
import pytest

from backend.backtesting.market_regime import (
    AdaptiveStrategy,
    MarketRegimeDetector,
    RegimeConfig,
    RegimeState,
    RegimeType,
)


class TestMarketRegimeDetector:
    """Tests for Market Regime Detector."""

    @pytest.fixture
    def detector(self):
        """Create detector with default config."""
        return MarketRegimeDetector()

    @pytest.fixture
    def trending_up_data(self):
        """Generate strong uptrend data."""
        np.random.seed(42)
        n = 100
        # Strong uptrend: consistent higher highs and higher lows
        base = 100 + np.arange(n) * 0.8
        noise = np.random.randn(n) * 0.5
        close = base + noise
        high = close + np.abs(np.random.randn(n) * 0.3) + 0.2
        low = close - np.abs(np.random.randn(n) * 0.3) - 0.1
        return high, low, close

    @pytest.fixture
    def trending_down_data(self):
        """Generate strong downtrend data."""
        np.random.seed(42)
        n = 100
        # Strong downtrend
        base = 200 - np.arange(n) * 0.8
        noise = np.random.randn(n) * 0.5
        close = base + noise
        high = close + np.abs(np.random.randn(n) * 0.3) + 0.1
        low = close - np.abs(np.random.randn(n) * 0.3) - 0.2
        return high, low, close

    @pytest.fixture
    def ranging_data(self):
        """Generate ranging/sideways data."""
        np.random.seed(42)
        n = 100
        # Oscillating around 100 with small range
        close = 100 + np.sin(np.arange(n) * 0.3) * 2 + np.random.randn(n) * 0.3
        high = close + 0.3
        low = close - 0.3
        return high, low, close

    @pytest.fixture
    def volatile_data(self):
        """Generate high volatility data."""
        np.random.seed(42)
        n = 100
        # Large random moves
        close = 100 + np.cumsum(np.random.randn(n) * 5)
        high = close + np.abs(np.random.randn(n) * 3)
        low = close - np.abs(np.random.randn(n) * 3)
        return high, low, close

    def test_detector_initialization(self, detector):
        """Test detector initialization."""
        assert detector.config is not None
        assert detector.config.adx_trending_threshold == 25.0

    def test_custom_config(self):
        """Test detector with custom config."""
        config = RegimeConfig(
            adx_trending_threshold=30.0,
            volatility_high=0.03,
        )
        detector = MarketRegimeDetector(config=config)

        assert detector.config.adx_trending_threshold == 30.0
        assert detector.config.volatility_high == 0.03

    def test_detect_uptrend(self, detector, trending_up_data):
        """Test detection of uptrend."""
        high, low, close = trending_up_data
        detector.precompute_indicators(high, low, close)

        # Check last bars (after indicators warm up)
        regime = detector.detect(idx=-1)

        assert isinstance(regime, RegimeState)
        assert regime.regime in (RegimeType.TRENDING_UP, RegimeType.BREAKOUT_UP)
        assert regime.allow_long is True

    def test_detect_downtrend(self, detector, trending_down_data):
        """Test detection of downtrend."""
        high, low, close = trending_down_data
        detector.precompute_indicators(high, low, close)

        regime = detector.detect(idx=-1)

        assert regime.regime in (RegimeType.TRENDING_DOWN, RegimeType.BREAKOUT_DOWN)
        assert regime.allow_short is True

    def test_detect_ranging(self, detector, ranging_data):
        """Test detection of ranging market."""
        high, low, close = ranging_data
        detector.precompute_indicators(high, low, close)

        regime = detector.detect(idx=-1)

        # Ranging market should have low ADX
        assert regime.adx < 30 or regime.regime == RegimeType.RANGING

    def test_regime_state_fields(self, detector, trending_up_data):
        """Test that RegimeState has all required fields."""
        high, low, close = trending_up_data
        detector.precompute_indicators(high, low, close)

        regime = detector.detect(idx=-1)

        assert hasattr(regime, "regime")
        assert hasattr(regime, "confidence")
        assert hasattr(regime, "adx")
        assert hasattr(regime, "plus_di")
        assert hasattr(regime, "minus_di")
        assert hasattr(regime, "volatility")
        assert hasattr(regime, "bandwidth")
        assert hasattr(regime, "trend_strength")
        assert hasattr(regime, "allow_long")
        assert hasattr(regime, "allow_short")
        assert hasattr(regime, "recommended_position_size")
        assert hasattr(regime, "reason")

    def test_to_dict(self, detector, trending_up_data):
        """Test RegimeState serialization."""
        high, low, close = trending_up_data
        detector.precompute_indicators(high, low, close)

        regime = detector.detect(idx=-1)
        regime_dict = regime.to_dict()

        assert isinstance(regime_dict, dict)
        assert "regime" in regime_dict
        assert "confidence" in regime_dict
        assert isinstance(regime_dict["regime"], str)

    def test_detect_all(self, detector, trending_up_data):
        """Test detecting regimes for all bars."""
        high, low, close = trending_up_data
        regimes = detector.detect_all(high, low, close)

        assert len(regimes) == len(close)
        assert all(isinstance(r, RegimeState) for r in regimes)

    def test_regime_summary(self, detector, trending_up_data):
        """Test regime distribution summary."""
        high, low, close = trending_up_data
        regimes = detector.detect_all(high, low, close)

        summary = detector.get_regime_summary(regimes)

        assert isinstance(summary, dict)
        total_pct = sum(summary.values())
        assert abs(total_pct - 100.0) < 0.1  # Should sum to ~100%

    def test_position_size_adjustment(self, detector, trending_up_data):
        """Test position size recommendations."""
        high, low, close = trending_up_data
        detector.precompute_indicators(high, low, close)

        regime = detector.detect(idx=-1)

        # Position size should be a reasonable multiplier
        assert 0.3 <= regime.recommended_position_size <= 1.5

    def test_clear_cache(self, detector, trending_up_data):
        """Test cache clearing."""
        high, low, close = trending_up_data
        detector.precompute_indicators(high, low, close)

        assert len(detector._cache) > 0

        detector.clear_cache()

        assert len(detector._cache) == 0

    def test_no_data_handling(self, detector):
        """Test handling when no data is cached."""
        regime = detector.detect()

        assert regime.regime == RegimeType.UNKNOWN
        assert regime.confidence == 0.0


class TestAdaptiveStrategy:
    """Tests for AdaptiveStrategy."""

    @pytest.fixture
    def strategy(self):
        """Create adaptive strategy."""
        return AdaptiveStrategy()

    @pytest.fixture
    def sample_data(self):
        """Generate sample market data."""
        np.random.seed(42)
        n = 100
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        high = close + np.abs(np.random.randn(n) * 0.3)
        low = close - np.abs(np.random.randn(n) * 0.3)
        return high, low, close

    def test_filter_signals(self, strategy, sample_data):
        """Test signal filtering based on regime."""
        high, low, close = sample_data

        # Generate random signals
        signals = np.random.choice([-1, 0, 1], size=len(close))

        filtered = strategy.filter_signals(signals, high, low, close)

        assert len(filtered) == len(signals)
        # Some signals should be filtered out
        # (filtered zeros should be >= original zeros)
        assert np.sum(filtered == 0) >= np.sum(signals == 0)

    def test_adjust_position_sizes(self, strategy, sample_data):
        """Test position size adjustment."""
        high, low, close = sample_data

        # Generate position sizes
        sizes = np.where(np.random.random(len(close)) > 0.5, 1.0, 0.0)

        adjusted = strategy.adjust_position_sizes(sizes, high, low, close)

        assert len(adjusted) == len(sizes)
        # Non-zero sizes should remain non-zero (but may change value)
        non_zero_original = np.sum(sizes > 0)
        non_zero_adjusted = np.sum(adjusted > 0)
        assert non_zero_adjusted == non_zero_original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
