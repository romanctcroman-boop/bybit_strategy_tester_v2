"""Tests for P3-5: Real-time parameter adaptation."""

import numpy as np
import pandas as pd
import pytest

from backend.research import MarketRegime, ParameterAdapter


@pytest.fixture
def ohlcv_data():
    """Generate synthetic OHLCV data with 200 rows."""
    n = 200
    np.random.seed(42)
    close = 50000.0 * np.cumprod(1 + np.random.randn(n) * 0.01)
    df = pd.DataFrame(
        {
            "open": close * (1 + np.random.randn(n) * 0.002),
            "high": close * (1 + np.abs(np.random.randn(n)) * 0.005),
            "low": close * (1 - np.abs(np.random.randn(n)) * 0.005),
            "close": close,
            "volume": np.random.uniform(1e6, 1e7, n),
        }
    )
    return df


@pytest.fixture
def short_data():
    """Short DataFrame — fewer rows than lookback."""
    n = 30
    close = 50000.0 * np.cumprod(1 + np.random.randn(n) * 0.01)
    return pd.DataFrame({"close": close})


class TestMarketRegime:
    def test_is_dataclass(self):
        r = MarketRegime(regime="trending", confidence=0.8, parameters={"rsi_period": 21})
        assert r.regime == "trending"
        assert r.confidence == 0.8
        assert r.parameters["rsi_period"] == 21


class TestParameterAdapter:
    def test_init(self):
        adapter = ParameterAdapter(lookback=100)
        assert adapter.lookback == 100
        assert "trending" in adapter.regime_parameters
        assert "ranging" in adapter.regime_parameters
        assert "volatile" in adapter.regime_parameters
        assert "calm" in adapter.regime_parameters

    def test_detect_regime_returns_market_regime(self, ohlcv_data):
        adapter = ParameterAdapter(lookback=100)
        regime = adapter.detect_regime(ohlcv_data)
        assert isinstance(regime, MarketRegime)
        assert regime.regime in ("trending", "ranging", "volatile", "calm")
        assert 0.0 <= regime.confidence <= 1.0

    def test_detect_regime_short_data_returns_unknown(self, short_data):
        adapter = ParameterAdapter(lookback=100)
        regime = adapter.detect_regime(short_data)
        assert regime.regime == "unknown"
        assert regime.confidence == 0.0

    def test_regime_parameters_have_required_keys(self):
        adapter = ParameterAdapter()
        for regime_name, params in adapter.regime_parameters.items():
            assert "rsi_period" in params, f"Missing rsi_period in {regime_name}"
            assert "take_profit" in params, f"Missing take_profit in {regime_name}"
            assert "stop_loss" in params, f"Missing stop_loss in {regime_name}"
            assert "position_size" in params, f"Missing position_size in {regime_name}"

    def test_get_adaptive_parameters_includes_base(self, ohlcv_data):
        adapter = ParameterAdapter(lookback=100)
        base = {"rsi_period": 14, "take_profit": 0.02, "stop_loss": 0.01, "position_size": 0.05, "custom": "value"}
        result = adapter.get_adaptive_parameters(ohlcv_data, base)
        assert isinstance(result, dict)
        assert "market_regime" in result
        assert "regime_confidence" in result
        assert result["market_regime"] in ("trending", "ranging", "volatile", "calm")
        # Custom key not in regime_params should be preserved unchanged
        assert result["custom"] == "value"

    def test_get_adaptive_parameters_blends_values(self, ohlcv_data):
        adapter = ParameterAdapter(lookback=100)
        base = {"rsi_period": 14, "take_profit": 0.02, "stop_loss": 0.01, "position_size": 0.05}
        result = adapter.get_adaptive_parameters(ohlcv_data, base)
        # All numeric params should be positive
        for k in ("rsi_period", "take_profit", "stop_loss", "position_size"):
            assert result[k] > 0

    def test_adapt_on_fly_reduces_position_on_drawdown(self):
        adapter = ParameterAdapter()
        params = {"position_size": 0.1, "take_profit": 0.02}
        adapted = adapter.adapt_on_fly(params, current_pnl=-100, drawdown=0.15, win_rate=0.5)
        assert adapted["position_size"] < params["position_size"]

    def test_adapt_on_fly_increases_position_on_good_performance(self):
        adapter = ParameterAdapter()
        params = {"position_size": 0.1, "take_profit": 0.02}
        adapted = adapter.adapt_on_fly(params, current_pnl=500, drawdown=0.0, win_rate=0.65)
        assert adapted["position_size"] > params["position_size"]

    def test_adapt_on_fly_reduces_take_profit_on_low_win_rate(self):
        adapter = ParameterAdapter()
        params = {"position_size": 0.1, "take_profit": 0.02}
        adapted = adapter.adapt_on_fly(params, current_pnl=-50, drawdown=0.0, win_rate=0.3)
        assert adapted["take_profit"] < params["take_profit"]

    def test_adapt_on_fly_no_change_on_normal(self):
        adapter = ParameterAdapter()
        params = {"position_size": 0.1, "take_profit": 0.02}
        adapted = adapter.adapt_on_fly(params, current_pnl=0, drawdown=0.0, win_rate=0.5)
        # Neither condition triggered
        assert adapted["position_size"] == pytest.approx(0.1)
        assert adapted["take_profit"] == pytest.approx(0.02)
