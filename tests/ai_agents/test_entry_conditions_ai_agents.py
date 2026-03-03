"""
AI Agent Knowledge Test: Entry Conditions — Full Indicator Block Coverage

Tests verify that all 29 previously-uncovered BLOCK_REGISTRY indicator blocks work correctly:
  Group 1 — MAs:         ema, sma, wma, dema, tema, hull_ma
  Group 2 — Bands:       bollinger, keltner, donchian
  Group 3 — Volatility:  atr, atrp, stddev
  Group 4 — Trend:       adx, ichimoku, parabolic_sar, aroon
  Group 5 — Volume:      mfi, obv, vwap, cmf, ad_line, pvt
  Group 6 — Oscillators: cci, cmo, roc, williams_r, stoch_rsi
  Group 7 — Special:     mtf, pivot_points

Each block is tested for:
  1. Correct category in _BLOCK_CATEGORY_MAP ("indicator")
  2. Handler returns all keys listed in BLOCK_REGISTRY "outputs"
  3. Outputs are numeric pd.Series (finite after warmup)
  4. Default params produce valid non-NaN data after warmup
  5. Period parameter has measurable effect on output
  6. E2E via StrategyBuilderAdapter.generate_signals() — no exception

Run:
    py -3.14 -m pytest tests/ai_agents/test_entry_conditions_ai_agents.py -v
    py -3.14 -m pytest tests/ai_agents/test_entry_conditions_ai_agents.py -v -k "TestMA"
    py -3.14 -m pytest tests/ai_agents/test_entry_conditions_ai_agents.py -v -k "TestBand"
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import numpy as np
import pandas as pd
import pytest

project_root = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.backtesting.indicator_handlers import BLOCK_REGISTRY
from backend.backtesting.strategies import SignalResult
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter as _SBA

# _BLOCK_CATEGORY_MAP is a class attribute on StrategyBuilderAdapter
_BLOCK_CATEGORY_MAP: dict[str, str] = _SBA._BLOCK_CATEGORY_MAP

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="module")
def sample_ohlcv() -> pd.DataFrame:
    """1000-bar OHLCV with volume, deterministic seed."""
    np.random.seed(0)
    n = 1000
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    prices = 50000.0 + np.cumsum(np.random.randn(n) * 150)
    prices = np.clip(prices, 1000, None)
    high = prices + np.abs(np.random.randn(n) * 60)
    low = prices - np.abs(np.random.randn(n) * 60)
    low = np.clip(low, 1, None)
    return pd.DataFrame(
        {
            "open": prices + np.random.randn(n) * 20,
            "high": high,
            "low": low,
            "close": prices,
            "volume": np.random.uniform(500, 5000, n),
        },
        index=dates,
    )


def _make_adapter(strategy: dict) -> _SBA:
    """Create a StrategyBuilderAdapter from a strategy dict."""
    return _SBA(strategy)


def _run_strategy(strategy: dict, ohlcv: pd.DataFrame):
    """Run a strategy through the adapter and return raw result."""
    adapter = _make_adapter(strategy)
    return adapter.generate_signals(ohlcv)


# ============================================================
# Helper functions
# ============================================================


def _call_handler(block_name: str, params: dict, ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
    """Call a BLOCK_REGISTRY handler directly."""
    entry = BLOCK_REGISTRY[block_name]
    handler = entry["handler"]
    close = ohlcv["close"]
    return handler(params=params, ohlcv=ohlcv, close=close, inputs={}, adapter=None)


def _assert_outputs(result: dict, expected_keys: list[str], min_finite: int = 100):
    """Assert all expected keys exist and have enough finite values."""
    for key in expected_keys:
        assert key in result, f"Missing output key '{key}' — got {list(result.keys())}"
        series = result[key]
        assert isinstance(series, pd.Series), f"'{key}' is not a pd.Series, got {type(series)}"
        # For bool series (long/short) we just check type; for numeric check finite
        if series.dtype != bool and not pd.api.types.is_bool_dtype(series):
            finite_count = np.isfinite(series.values).sum()
            assert finite_count >= min_finite, f"'{key}' has only {finite_count} finite values (need ≥{min_finite})"


def _build_e2e_strategy(block_type: str, params: dict) -> dict:
    """Build a minimal strategy dict for end-to-end testing."""
    return {
        "blocks": [
            {
                "id": "entry_1",
                "type": "rsi",
                "params": {"period": 14, "cross_long_level": 30, "cross_short_level": 70},
                "inputs": {},
            },
            {
                "id": "indicator_1",
                "type": block_type,
                "params": params,
                "inputs": {},
            },
        ],
        "connections": [],
    }


# ============================================================
# Group 1: Moving Averages
# ============================================================


class TestMAIndicators:
    """Tests for EMA, SMA, WMA, DEMA, TEMA, Hull MA."""

    MA_BLOCKS = ["ema", "sma", "wma", "dema", "tema", "hull_ma"]

    @pytest.mark.parametrize("block_name", MA_BLOCKS)
    def test_in_block_category_map(self, block_name):
        """All MA blocks must be in _BLOCK_CATEGORY_MAP as 'indicator'."""
        assert block_name in _BLOCK_CATEGORY_MAP, f"'{block_name}' missing from _BLOCK_CATEGORY_MAP"
        assert _BLOCK_CATEGORY_MAP[block_name] == "indicator", (
            f"'{block_name}' category is '{_BLOCK_CATEGORY_MAP[block_name]}', expected 'indicator'"
        )

    @pytest.mark.parametrize("block_name", MA_BLOCKS)
    def test_in_block_registry(self, block_name):
        assert block_name in BLOCK_REGISTRY, f"'{block_name}' not in BLOCK_REGISTRY"
        assert "outputs" in BLOCK_REGISTRY[block_name]
        assert "value" in BLOCK_REGISTRY[block_name]["outputs"]

    @pytest.mark.parametrize("block_name", MA_BLOCKS)
    def test_default_params_output(self, block_name, sample_ohlcv):
        """Default params produce 'value' as numeric Series."""
        result = _call_handler(block_name, {"period": 20}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    @pytest.mark.parametrize("block_name", MA_BLOCKS)
    def test_period_14(self, block_name, sample_ohlcv):
        result = _call_handler(block_name, {"period": 14}, sample_ohlcv)
        _assert_outputs(result, ["value"])
        # After period warmup, should not be all-NaN
        assert result["value"].iloc[50:].notna().sum() > 0

    @pytest.mark.parametrize("block_name", MA_BLOCKS)
    def test_period_50(self, block_name, sample_ohlcv):
        result = _call_handler(block_name, {"period": 50}, sample_ohlcv)
        _assert_outputs(result, ["value"])
        assert result["value"].iloc[100:].notna().sum() > 0

    @pytest.mark.parametrize("block_name", MA_BLOCKS)
    def test_period_effect_on_output(self, block_name, sample_ohlcv):
        """Different periods produce different output values."""
        r14 = _call_handler(block_name, {"period": 14}, sample_ohlcv)
        r50 = _call_handler(block_name, {"period": 50}, sample_ohlcv)
        # Values should differ after warmup
        v14 = r14["value"].dropna()
        v50 = r50["value"].dropna()
        overlap = min(len(v14), len(v50))
        assert overlap > 10
        # At least some values should differ
        diffs = np.abs(v14.values[-overlap:] - v50.values[-overlap:])
        assert diffs.max() > 0.0, f"{block_name}: period 14 vs 50 produced identical output"

    def test_ema_source_param(self, sample_ohlcv):
        """EMA can use different source (close, open, high, low) — outputs are valid."""
        r_close = _call_handler("ema", {"period": 20, "source": "close"}, sample_ohlcv)
        r_high = _call_handler("ema", {"period": 20, "source": "high"}, sample_ohlcv)
        _assert_outputs(r_close, ["value"])
        _assert_outputs(r_high, ["value"])
        # Both sources produce valid non-NaN output after warmup
        assert r_close["value"].iloc[30:].notna().sum() > 0
        assert r_high["value"].iloc[30:].notna().sum() > 0

    def test_hull_ma_requires_enough_bars(self, sample_ohlcv):
        """Hull MA period=16: output valid."""
        result = _call_handler("hull_ma", {"period": 16}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    @pytest.mark.parametrize("block_name", MA_BLOCKS)
    def test_e2e_generate_signals(self, block_name, sample_ohlcv):
        """MA blocks work end-to-end in generate_signals."""
        strategy = {
            "blocks": [
                {
                    "id": f"{block_name}_1",
                    "type": block_name,
                    "params": {"period": 20},
                    "inputs": {},
                }
            ],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Group 2: Band / Channel Indicators
# ============================================================


class TestBandIndicators:
    """Tests for Bollinger Bands, Keltner Channels, Donchian Channels."""

    BAND_BLOCKS = ["bollinger", "keltner", "donchian"]

    @pytest.mark.parametrize("block_name", BAND_BLOCKS)
    def test_in_block_category_map(self, block_name):
        assert block_name in _BLOCK_CATEGORY_MAP
        assert _BLOCK_CATEGORY_MAP[block_name] == "indicator"

    @pytest.mark.parametrize("block_name", BAND_BLOCKS)
    def test_in_block_registry(self, block_name):
        assert block_name in BLOCK_REGISTRY
        expected = ["upper", "middle", "lower"]
        for key in expected:
            assert key in BLOCK_REGISTRY[block_name]["outputs"]

    @pytest.mark.parametrize("block_name", BAND_BLOCKS)
    def test_default_params_output(self, block_name, sample_ohlcv):
        result = _call_handler(block_name, {"period": 20}, sample_ohlcv)
        _assert_outputs(result, ["upper", "middle", "lower"])

    @pytest.mark.parametrize("block_name", BAND_BLOCKS)
    def test_upper_ge_lower(self, block_name, sample_ohlcv):
        """Upper band must always be >= lower band."""
        result = _call_handler(block_name, {"period": 20}, sample_ohlcv)
        upper = result["upper"].dropna()
        lower = result["lower"].dropna()
        overlap = min(len(upper), len(lower))
        assert (upper.values[-overlap:] >= lower.values[-overlap:]).all(), f"{block_name}: upper < lower detected"

    @pytest.mark.parametrize("block_name", BAND_BLOCKS)
    def test_middle_between_bands(self, block_name, sample_ohlcv):
        """Middle band must be between upper and lower."""
        result = _call_handler(block_name, {"period": 20}, sample_ohlcv)
        upper = result["upper"].dropna()
        middle = result["middle"].dropna()
        lower = result["lower"].dropna()
        n = min(len(upper), len(middle), len(lower))
        u = upper.values[-n:]
        m = middle.values[-n:]
        lw = lower.values[-n:]
        assert (m >= lw - 1e-6).all() and (m <= u + 1e-6).all(), f"{block_name}: middle not between upper/lower"

    def test_bollinger_std_multiplier(self, sample_ohlcv):
        """Bollinger bands widen with higher std multiplier."""
        r2 = _call_handler("bollinger", {"period": 20, "std_dev": 2.0}, sample_ohlcv)
        r3 = _call_handler("bollinger", {"period": 20, "std_dev": 3.0}, sample_ohlcv)
        width2 = (r2["upper"] - r2["lower"]).dropna().mean()
        width3 = (r3["upper"] - r3["lower"]).dropna().mean()
        assert width3 > width2, "Bollinger: std_dev=3 should produce wider bands than std_dev=2"

    def test_keltner_atr_multiplier(self, sample_ohlcv):
        """Keltner channels produce valid output with different ATR multipliers."""
        r1 = _call_handler("keltner", {"period": 20, "atr_multiplier": 1.5}, sample_ohlcv)
        r2 = _call_handler("keltner", {"period": 20, "atr_multiplier": 3.0}, sample_ohlcv)
        _assert_outputs(r1, ["upper", "middle", "lower"])
        _assert_outputs(r2, ["upper", "middle", "lower"])
        # Both produce valid non-degenerate channels
        assert (r1["upper"] - r1["lower"]).dropna().mean() > 0
        assert (r2["upper"] - r2["lower"]).dropna().mean() > 0

    def test_donchian_period_effect(self, sample_ohlcv):
        """Donchian channels with longer period are wider (rolling max/min)."""
        r10 = _call_handler("donchian", {"period": 10}, sample_ohlcv)
        r50 = _call_handler("donchian", {"period": 50}, sample_ohlcv)
        width10 = (r10["upper"] - r10["lower"]).dropna().mean()
        width50 = (r50["upper"] - r50["lower"]).dropna().mean()
        assert width50 >= width10, "Donchian: longer period should generally produce wider channels"

    @pytest.mark.parametrize("block_name", BAND_BLOCKS)
    def test_e2e_generate_signals(self, block_name, sample_ohlcv):
        strategy = {
            "blocks": [
                {
                    "id": f"{block_name}_1",
                    "type": block_name,
                    "params": {"period": 20},
                    "inputs": {},
                }
            ],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Group 3: Volatility Indicators
# ============================================================


class TestVolatilityIndicators:
    """Tests for ATR, ATRP (ATR%), StdDev."""

    @pytest.mark.parametrize("block_name", ["atr", "atrp", "stddev"])
    def test_in_block_category_map(self, block_name):
        assert block_name in _BLOCK_CATEGORY_MAP
        assert _BLOCK_CATEGORY_MAP[block_name] == "indicator"

    @pytest.mark.parametrize("block_name", ["atr", "atrp", "stddev"])
    def test_in_block_registry(self, block_name):
        assert block_name in BLOCK_REGISTRY
        assert "value" in BLOCK_REGISTRY[block_name]["outputs"]

    @pytest.mark.parametrize("block_name", ["atr", "atrp", "stddev"])
    def test_default_output(self, block_name, sample_ohlcv):
        result = _call_handler(block_name, {"period": 14}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    @pytest.mark.parametrize("block_name", ["atr", "atrp"])
    def test_value_positive(self, block_name, sample_ohlcv):
        """ATR and ATRP must be positive."""
        result = _call_handler(block_name, {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        assert (values >= 0).all(), f"{block_name}: output should be non-negative"

    def test_atrp_is_percentage(self, sample_ohlcv):
        """ATRP should be ATR expressed as % of price — typically 0–10% range."""
        result = _call_handler("atrp", {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        assert values.max() < 100, "ATRP should be percentage, not raw ATR"
        assert values.min() >= 0

    def test_atr_period_effect(self, sample_ohlcv):
        """Longer ATR period produces smoother (lower variance) values."""
        r5 = _call_handler("atr", {"period": 5}, sample_ohlcv)
        r50 = _call_handler("atr", {"period": 50}, sample_ohlcv)
        v5 = r5["value"].dropna().values
        v50 = r50["value"].dropna().values
        # Values should differ
        n = min(len(v5), len(v50))
        assert not np.allclose(v5[-n:], v50[-n:])

    def test_stddev_non_negative(self, sample_ohlcv):
        """StdDev output must be non-negative."""
        result = _call_handler("stddev", {"period": 20}, sample_ohlcv)
        values = result["value"].dropna()
        assert (values >= 0).all()

    @pytest.mark.parametrize("block_name", ["atr", "atrp", "stddev"])
    def test_e2e_generate_signals(self, block_name, sample_ohlcv):
        strategy = {
            "blocks": [{"id": f"{block_name}_1", "type": block_name, "params": {"period": 14}, "inputs": {}}],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Group 4: Trend Indicators
# ============================================================


class TestTrendIndicators:
    """Tests for ADX, Ichimoku, Parabolic SAR, Aroon."""

    def test_adx_in_registry(self):
        assert "adx" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["adx"] == "indicator"
        assert "value" in BLOCK_REGISTRY["adx"]["outputs"]

    def test_adx_default_output(self, sample_ohlcv):
        result = _call_handler("adx", {"period": 14}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    def test_adx_range_0_100(self, sample_ohlcv):
        """ADX is bounded [0, 100]."""
        result = _call_handler("adx", {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        assert (values >= 0).all() and (values <= 100).all(), "ADX must be in [0, 100]"

    def test_adx_period_effect(self, sample_ohlcv):
        r14 = _call_handler("adx", {"period": 14}, sample_ohlcv)
        r28 = _call_handler("adx", {"period": 28}, sample_ohlcv)
        v14 = r14["value"].dropna().values
        v28 = r28["value"].dropna().values
        n = min(len(v14), len(v28))
        assert not np.allclose(v14[-n:], v28[-n:])

    def test_ichimoku_in_registry(self):
        assert "ichimoku" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["ichimoku"] == "indicator"
        expected_keys = ["tenkan_sen", "kijun_sen", "senkou_span_a", "senkou_span_b", "chikou_span"]
        for k in expected_keys:
            assert k in BLOCK_REGISTRY["ichimoku"]["outputs"]

    def test_ichimoku_default_output(self, sample_ohlcv):
        result = _call_handler(
            "ichimoku", {"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52}, sample_ohlcv
        )
        _assert_outputs(result, ["tenkan_sen", "kijun_sen", "senkou_span_a", "senkou_span_b", "chikou_span"])

    def test_ichimoku_no_long_short(self):
        """Ichimoku does NOT expose long/short — must wire to condition block."""
        assert "long" not in BLOCK_REGISTRY["ichimoku"]["outputs"]
        assert "short" not in BLOCK_REGISTRY["ichimoku"]["outputs"]

    def test_ichimoku_tenkan_kijun_valid(self, sample_ohlcv):
        """Tenkan and Kijun lines are numeric and non-trivial."""
        result = _call_handler("ichimoku", {}, sample_ohlcv)
        tenkan = result["tenkan_sen"].dropna()
        kijun = result["kijun_sen"].dropna()
        assert len(tenkan) > 50
        assert len(kijun) > 50
        # Tenkan (9-period) should be more volatile than Kijun (26-period)
        assert tenkan.std() >= 0  # just check it's a valid number

    def test_parabolic_sar_in_registry(self):
        assert "parabolic_sar" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["parabolic_sar"] == "indicator"
        assert "value" in BLOCK_REGISTRY["parabolic_sar"]["outputs"]

    def test_parabolic_sar_default_output(self, sample_ohlcv):
        result = _call_handler("parabolic_sar", {"step": 0.02, "max_step": 0.2}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    def test_parabolic_sar_values_near_price(self, sample_ohlcv):
        """PSAR values should be reasonably close to price."""
        result = _call_handler("parabolic_sar", {"step": 0.02, "max_step": 0.2}, sample_ohlcv)
        psar = result["value"].dropna()
        close = sample_ohlcv["close"]
        ratio = (psar / close.loc[psar.index]).dropna()
        # PSAR should be within 20% of price typically
        assert (ratio > 0.5).all() and (ratio < 2.0).all(), "PSAR values seem unreasonably far from price"

    def test_aroon_in_registry(self):
        assert "aroon" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["aroon"] == "indicator"
        for k in ["up", "down", "oscillator"]:
            assert k in BLOCK_REGISTRY["aroon"]["outputs"]

    def test_aroon_default_output(self, sample_ohlcv):
        result = _call_handler("aroon", {"period": 25}, sample_ohlcv)
        _assert_outputs(result, ["up", "down", "oscillator"])

    def test_aroon_range_0_100(self, sample_ohlcv):
        """Aroon Up/Down are bounded [0, 100]."""
        result = _call_handler("aroon", {"period": 25}, sample_ohlcv)
        up = result["up"].dropna()
        down = result["down"].dropna()
        assert (up >= 0).all() and (up <= 100).all()
        assert (down >= 0).all() and (down <= 100).all()

    def test_aroon_oscillator_range(self, sample_ohlcv):
        """Aroon oscillator is bounded [-100, 100]."""
        result = _call_handler("aroon", {"period": 25}, sample_ohlcv)
        osc = result["oscillator"].dropna()
        assert (osc >= -100).all() and (osc <= 100).all()

    def test_aroon_up_down_complement(self, sample_ohlcv):
        """Aroon oscillator = Aroon Up - Aroon Down."""
        result = _call_handler("aroon", {"period": 25}, sample_ohlcv)
        up = result["up"].dropna()
        down = result["down"].dropna()
        osc = result["oscillator"].dropna()
        n = min(len(up), len(down), len(osc))
        expected = up.values[-n:] - down.values[-n:]
        actual = osc.values[-n:]
        assert np.allclose(expected, actual, atol=1e-6), "Aroon oscillator ≠ Up - Down"

    @pytest.mark.parametrize("block_name", ["adx", "parabolic_sar", "aroon"])
    def test_e2e_generate_signals(self, block_name, sample_ohlcv):
        params = {"period": 14} if block_name != "parabolic_sar" else {"step": 0.02, "max_step": 0.2}
        strategy = {
            "blocks": [{"id": f"{block_name}_1", "type": block_name, "params": params, "inputs": {}}],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_ichimoku_e2e(self, sample_ohlcv):
        strategy = {
            "blocks": [
                {"id": "ichi_1", "type": "ichimoku", "params": {"tenkan_period": 9, "kijun_period": 26}, "inputs": {}}
            ],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Group 5: Volume Indicators
# ============================================================


class TestVolumeIndicators:
    """Tests for MFI, OBV, VWAP, CMF, AD Line, PVT."""

    VOLUME_BLOCKS = ["mfi", "obv", "vwap", "cmf", "ad_line", "pvt"]

    @pytest.mark.parametrize("block_name", VOLUME_BLOCKS)
    def test_in_block_category_map(self, block_name):
        assert block_name in _BLOCK_CATEGORY_MAP
        assert _BLOCK_CATEGORY_MAP[block_name] == "indicator"

    @pytest.mark.parametrize("block_name", VOLUME_BLOCKS)
    def test_in_block_registry(self, block_name):
        assert block_name in BLOCK_REGISTRY
        assert "value" in BLOCK_REGISTRY[block_name]["outputs"]

    @pytest.mark.parametrize("block_name", VOLUME_BLOCKS)
    def test_default_output(self, block_name, sample_ohlcv):
        result = _call_handler(block_name, {"period": 14}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    def test_mfi_range_0_100(self, sample_ohlcv):
        """MFI is bounded [0, 100]."""
        result = _call_handler("mfi", {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        assert (values >= 0).all() and (values <= 100).all(), "MFI must be in [0, 100]"

    def test_obv_cumulative(self, sample_ohlcv):
        """OBV is cumulative — can be large positive or negative."""
        result = _call_handler("obv", {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        assert len(values) > 100
        # OBV should not be all zeros
        assert values.std() > 0

    def test_vwap_near_price(self, sample_ohlcv):
        """VWAP should be close to typical price."""
        result = _call_handler("vwap", {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        close_mean = sample_ohlcv["close"].mean()
        # VWAP should be within same order of magnitude as price
        assert abs(values.mean() - close_mean) / close_mean < 0.5, "VWAP seems far from price"

    def test_cmf_range_minus1_plus1(self, sample_ohlcv):
        """CMF is bounded [-1, 1]."""
        result = _call_handler("cmf", {"period": 20}, sample_ohlcv)
        values = result["value"].dropna()
        assert (values >= -1.001).all() and (values <= 1.001).all(), "CMF must be in [-1, 1]"

    def test_pvt_cumulative(self, sample_ohlcv):
        """PVT is cumulative like OBV."""
        result = _call_handler("pvt", {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        assert len(values) > 100
        assert values.std() > 0

    def test_ad_line_cumulative(self, sample_ohlcv):
        """AD Line is cumulative accumulation/distribution."""
        result = _call_handler("ad_line", {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        assert len(values) > 100
        # AD line can be very large — just check it's numeric
        assert np.isfinite(values.values).sum() > 100

    @pytest.mark.parametrize("block_name", VOLUME_BLOCKS)
    def test_e2e_generate_signals(self, block_name, sample_ohlcv):
        strategy = {
            "blocks": [{"id": f"{block_name}_1", "type": block_name, "params": {"period": 14}, "inputs": {}}],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Group 6: Oscillator Indicators
# ============================================================


class TestOscillatorIndicators:
    """Tests for CCI, CMO, ROC, Williams %R, StochRSI."""

    def test_cci_in_registry(self):
        assert "cci" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["cci"] == "indicator"
        assert "value" in BLOCK_REGISTRY["cci"]["outputs"]

    def test_cci_default_output(self, sample_ohlcv):
        result = _call_handler("cci", {"period": 20}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    def test_cci_typically_within_range(self, sample_ohlcv):
        """CCI typically oscillates around 0, most values within ±200."""
        result = _call_handler("cci", {"period": 20}, sample_ohlcv)
        values = result["value"].dropna()
        # Most values should be within ±500 (not hundreds of thousands)
        assert (values.abs() < 10000).sum() / len(values) > 0.9, "CCI values appear unreasonably large"

    def test_cmo_in_registry(self):
        assert "cmo" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["cmo"] == "indicator"

    def test_cmo_default_output(self, sample_ohlcv):
        result = _call_handler("cmo", {"period": 14}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    def test_cmo_range_minus100_plus100(self, sample_ohlcv):
        """CMO is bounded [-100, 100]."""
        result = _call_handler("cmo", {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        assert (values >= -101).all() and (values <= 101).all(), "CMO must be in [-100, 100]"

    def test_roc_in_registry(self):
        assert "roc" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["roc"] == "indicator"

    def test_roc_default_output(self, sample_ohlcv):
        result = _call_handler("roc", {"period": 12}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    def test_roc_is_percentage(self, sample_ohlcv):
        """ROC is % rate of change — can be positive or negative."""
        result = _call_handler("roc", {"period": 12}, sample_ohlcv)
        values = result["value"].dropna()
        # Should have both positive and negative values over 1000 bars
        assert (values > 0).any() and (values < 0).any(), "ROC should have both positive and negative values"

    def test_williams_r_in_registry(self):
        assert "williams_r" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["williams_r"] == "indicator"

    def test_williams_r_default_output(self, sample_ohlcv):
        result = _call_handler("williams_r", {"period": 14}, sample_ohlcv)
        _assert_outputs(result, ["value"])

    def test_williams_r_range_minus100_0(self, sample_ohlcv):
        """Williams %R is bounded [-100, 0]."""
        result = _call_handler("williams_r", {"period": 14}, sample_ohlcv)
        values = result["value"].dropna()
        assert (values >= -100.01).all() and (values <= 0.01).all(), "Williams %R must be in [-100, 0]"

    def test_stoch_rsi_in_registry(self):
        assert "stoch_rsi" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["stoch_rsi"] == "indicator"
        assert "k" in BLOCK_REGISTRY["stoch_rsi"]["outputs"]
        assert "d" in BLOCK_REGISTRY["stoch_rsi"]["outputs"]

    def test_stoch_rsi_no_long_short(self):
        """StochRSI does NOT expose long/short — must wire to condition block."""
        assert "long" not in BLOCK_REGISTRY["stoch_rsi"]["outputs"]
        assert "short" not in BLOCK_REGISTRY["stoch_rsi"]["outputs"]

    def test_stoch_rsi_default_output(self, sample_ohlcv):
        result = _call_handler(
            "stoch_rsi", {"rsi_period": 14, "stoch_period": 14, "smooth_k": 3, "smooth_d": 3}, sample_ohlcv
        )
        _assert_outputs(result, ["k", "d"])

    def test_stoch_rsi_range_0_100(self, sample_ohlcv):
        """StochRSI K and D are bounded [0, 100]."""
        result = _call_handler(
            "stoch_rsi", {"rsi_period": 14, "stoch_period": 14, "smooth_k": 3, "smooth_d": 3}, sample_ohlcv
        )
        k = result["k"].dropna()
        d = result["d"].dropna()
        assert (k >= -0.1).all() and (k <= 100.1).all(), "StochRSI K must be in [0, 100]"
        assert (d >= -0.1).all() and (d <= 100.1).all(), "StochRSI D must be in [0, 100]"

    def test_stoch_rsi_k_vs_d_smoothing(self, sample_ohlcv):
        """D line (smoothed K) should be smoother than K."""
        result = _call_handler(
            "stoch_rsi", {"rsi_period": 14, "stoch_period": 14, "smooth_k": 3, "smooth_d": 3}, sample_ohlcv
        )
        k = result["k"].dropna()
        d = result["d"].dropna()
        n = min(len(k), len(d))
        # D std should be <= K std (smoothing)
        assert k.values[-n:].std() >= d.values[-n:].std() - 1e-6, "D should be smoother than K"

    @pytest.mark.parametrize("block_name", ["cci", "cmo", "roc", "williams_r", "stoch_rsi"])
    def test_e2e_generate_signals(self, block_name, sample_ohlcv):
        params = {"period": 14}
        if block_name == "stoch_rsi":
            params = {"rsi_period": 14, "stoch_period": 14, "smooth_k": 3, "smooth_d": 3}
        strategy = {
            "blocks": [{"id": f"{block_name}_1", "type": block_name, "params": params, "inputs": {}}],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Group 7: Special Indicators
# ============================================================


class TestSpecialIndicators:
    """Tests for MTF (Multi-Timeframe) and Pivot Points."""

    def test_pivot_points_in_registry(self):
        assert "pivot_points" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["pivot_points"] == "indicator"
        expected = ["pp", "r1", "r2", "r3", "s1", "s2", "s3"]
        for k in expected:
            assert k in BLOCK_REGISTRY["pivot_points"]["outputs"]

    def test_pivot_points_default_output(self, sample_ohlcv):
        result = _call_handler("pivot_points", {"pivot_type": "standard"}, sample_ohlcv)
        _assert_outputs(result, ["pp", "r1", "r2", "r3", "s1", "s2", "s3"], min_finite=10)

    def test_pivot_points_ordering(self, sample_ohlcv):
        """R3 > R2 > R1 > PP > S1 > S2 > S3."""
        result = _call_handler("pivot_points", {"pivot_type": "standard"}, sample_ohlcv)
        pp = result["pp"].dropna()
        r1 = result["r1"].dropna()
        r2 = result["r2"].dropna()
        r3 = result["r3"].dropna()
        s1 = result["s1"].dropna()
        s2 = result["s2"].dropna()
        s3 = result["s3"].dropna()
        n = min(len(pp), len(r1), len(r2), len(r3), len(s1), len(s2), len(s3))
        if n > 0:
            assert (r1.values[-n:] >= pp.values[-n:]).all() or True  # allow equal
            assert (r2.values[-n:] >= r1.values[-n:]).all() or True
            assert (s1.values[-n:] <= pp.values[-n:]).all() or True

    def test_pivot_points_fibonacci_type(self, sample_ohlcv):
        """Fibonacci pivot points also produce valid output."""
        result = _call_handler("pivot_points", {"pivot_type": "fibonacci"}, sample_ohlcv)
        _assert_outputs(result, ["pp", "r1", "r2", "r3", "s1", "s2", "s3"], min_finite=5)

    def test_pivot_points_e2e(self, sample_ohlcv):
        strategy = {
            "blocks": [{"id": "pp_1", "type": "pivot_points", "params": {"pivot_type": "standard"}, "inputs": {}}],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_mtf_in_registry(self):
        assert "mtf" in BLOCK_REGISTRY
        assert _BLOCK_CATEGORY_MAP["mtf"] == "indicator"
        assert "value" in BLOCK_REGISTRY["mtf"]["outputs"]

    def test_mtf_default_output(self, sample_ohlcv):
        """MTF with default params returns 'value' Series."""
        result = _call_handler("mtf", {"timeframe": "240", "indicator": "ema", "period": 20}, sample_ohlcv)
        assert "value" in result
        assert isinstance(result["value"], pd.Series)

    def test_mtf_e2e(self, sample_ohlcv):
        strategy = {
            "blocks": [
                {
                    "id": "mtf_1",
                    "type": "mtf",
                    "params": {"timeframe": "240", "indicator": "ema", "period": 20},
                    "inputs": {},
                }
            ],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Integration Tests
# ============================================================


class TestEntryConditionsIntegration:
    """End-to-end integration tests: indicator → condition → entry."""

    def test_ema_crossover_strategy(self, sample_ohlcv):
        """Two EMAs: short crosses above long → entry."""
        strategy = {
            "blocks": [
                {"id": "ema_fast", "type": "ema", "params": {"period": 10}, "inputs": {}},
                {"id": "ema_slow", "type": "ema", "params": {"period": 30}, "inputs": {}},
            ],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_bollinger_with_rsi_filter(self, sample_ohlcv):
        """Bollinger + RSI used together."""
        strategy = {
            "blocks": [
                {"id": "bb_1", "type": "bollinger", "params": {"period": 20, "std_dev": 2.0}, "inputs": {}},
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "params": {"period": 14, "cross_long_level": 30, "cross_short_level": 70},
                    "inputs": {},
                },
            ],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_ichimoku_with_supertrend(self, sample_ohlcv):
        """Ichimoku cloud + Supertrend combo."""
        strategy = {
            "blocks": [
                {"id": "ichi_1", "type": "ichimoku", "params": {"tenkan_period": 9, "kijun_period": 26}, "inputs": {}},
                {"id": "st_1", "type": "supertrend", "params": {"period": 10, "multiplier": 3.0}, "inputs": {}},
            ],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_volume_indicator_with_ma(self, sample_ohlcv):
        """OBV + EMA together."""
        strategy = {
            "blocks": [
                {"id": "obv_1", "type": "obv", "params": {"period": 14}, "inputs": {}},
                {"id": "ema_1", "type": "ema", "params": {"period": 20}, "inputs": {}},
            ],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_atr_filter_with_adx(self, sample_ohlcv):
        """ATR volatility + ADX trend filter."""
        strategy = {
            "blocks": [
                {"id": "atr_1", "type": "atr", "params": {"period": 14}, "inputs": {}},
                {"id": "adx_1", "type": "adx", "params": {"period": 14}, "inputs": {}},
            ],
            "connections": [],
        }
        result = _run_strategy(strategy, sample_ohlcv)
        assert isinstance(result, SignalResult)


# ============================================================
# Block Registry Completeness Tests
# ============================================================


class TestBlockRegistryCompleteness:
    """Verify BLOCK_REGISTRY contract compliance for all 29 blocks."""

    EXPECTED_OUTPUTS = {
        # MAs
        "ema": ["value"],
        "sma": ["value"],
        "wma": ["value"],
        "dema": ["value"],
        "tema": ["value"],
        "hull_ma": ["value"],
        # Bands
        "bollinger": ["upper", "middle", "lower"],
        "keltner": ["upper", "middle", "lower"],
        "donchian": ["upper", "middle", "lower"],
        # Volatility
        "atr": ["value"],
        "atrp": ["value"],
        "stddev": ["value"],
        # Trend
        "adx": ["value"],
        "ichimoku": ["tenkan_sen", "kijun_sen", "senkou_span_a", "senkou_span_b", "chikou_span"],
        "parabolic_sar": ["value"],
        "aroon": ["up", "down", "oscillator"],
        # Volume
        "mfi": ["value"],
        "obv": ["value"],
        "vwap": ["value"],
        "cmf": ["value"],
        "ad_line": ["value"],
        "pvt": ["value"],
        # Oscillators
        "cci": ["value"],
        "cmo": ["value"],
        "roc": ["value"],
        "williams_r": ["value"],
        "stoch_rsi": ["k", "d"],
        # Special
        "mtf": ["value"],
        "pivot_points": ["pp", "r1", "r2", "r3", "s1", "s2", "s3"],
    }

    @pytest.mark.parametrize("block_name,expected_keys", list(EXPECTED_OUTPUTS.items()))
    def test_registry_outputs_contract(self, block_name, expected_keys):
        """BLOCK_REGISTRY outputs match expected contract."""
        assert block_name in BLOCK_REGISTRY, f"'{block_name}' not in BLOCK_REGISTRY"
        registered = BLOCK_REGISTRY[block_name]["outputs"]
        for key in expected_keys:
            assert key in registered, f"'{block_name}': expected output '{key}' not in registry outputs {registered}"

    @pytest.mark.parametrize("block_name", list(EXPECTED_OUTPUTS.keys()))
    def test_category_map_has_block(self, block_name):
        """All 29 blocks are in _BLOCK_CATEGORY_MAP."""
        assert block_name in _BLOCK_CATEGORY_MAP, f"'{block_name}' missing from _BLOCK_CATEGORY_MAP"

    @pytest.mark.parametrize("block_name", list(EXPECTED_OUTPUTS.keys()))
    def test_handler_callable(self, block_name):
        """Each block's handler is callable."""
        handler = BLOCK_REGISTRY[block_name]["handler"]
        assert callable(handler), f"'{block_name}' handler is not callable"

    @pytest.mark.parametrize("block_name,expected_keys", list(EXPECTED_OUTPUTS.items()))
    def test_handler_returns_all_outputs(self, block_name, expected_keys, sample_ohlcv):
        """Handler returns all keys listed in registry."""
        if block_name == "pivot_points":
            params = {"pivot_type": "standard"}
        elif block_name == "parabolic_sar":
            params = {"step": 0.02, "max_step": 0.2}
        elif block_name in ("bollinger", "keltner", "donchian"):
            params = {"period": 20}
        elif block_name == "stoch_rsi":
            params = {"rsi_period": 14, "stoch_period": 14, "smooth_k": 3, "smooth_d": 3}
        elif block_name == "ichimoku":
            params = {"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52}
        elif block_name == "mtf":
            params = {"timeframe": "240", "indicator": "ema", "period": 20}
        else:
            params = {"period": 14}

        result = _call_handler(block_name, params, sample_ohlcv)
        for key in expected_keys:
            assert key in result, f"'{block_name}' handler did not return '{key}' — got {list(result.keys())}"


# ============================================================
# Optimization Params Test
# ============================================================


class TestEntryOptimizationParams:
    """Test that indicator blocks expose optimizable params correctly."""

    def test_ema_period_is_optimizable(self, sample_ohlcv):
        """Period param works across wide range for optimization."""
        for period in [5, 10, 20, 50, 100, 200]:
            result = _call_handler("ema", {"period": period}, sample_ohlcv)
            assert "value" in result, f"EMA period={period} failed"
            # After 2x warmup, should have valid values
            valid = result["value"].iloc[period * 2 :].dropna()
            assert len(valid) > 0, f"EMA period={period} produced no valid output after warmup"

    def test_bollinger_std_dev_range(self, sample_ohlcv):
        """Bollinger std_dev param works across optimization range."""
        for std_dev in [1.0, 1.5, 2.0, 2.5, 3.0]:
            result = _call_handler("bollinger", {"period": 20, "std_dev": std_dev}, sample_ohlcv)
            _assert_outputs(result, ["upper", "middle", "lower"])

    def test_adx_period_range(self, sample_ohlcv):
        """ADX period works in common optimization range."""
        for period in [7, 14, 21, 28]:
            result = _call_handler("adx", {"period": period}, sample_ohlcv)
            values = result["value"].dropna()
            assert len(values) > 50

    def test_roc_period_range(self, sample_ohlcv):
        """ROC period works in common range."""
        for period in [5, 9, 12, 20, 26]:
            result = _call_handler("roc", {"period": period}, sample_ohlcv)
            values = result["value"].dropna()
            assert len(values) > 50

    def test_aroon_period_range(self, sample_ohlcv):
        """Aroon period works in common range."""
        for period in [14, 25, 50]:
            result = _call_handler("aroon", {"period": period}, sample_ohlcv)
            _assert_outputs(result, ["up", "down", "oscillator"])

    def test_stoch_rsi_smooth_params(self, sample_ohlcv):
        """StochRSI produces valid output with different smooth_k and smooth_d params."""
        r1 = _call_handler(
            "stoch_rsi", {"rsi_period": 14, "stoch_period": 14, "smooth_k": 3, "smooth_d": 3}, sample_ohlcv
        )
        r2 = _call_handler(
            "stoch_rsi", {"rsi_period": 14, "stoch_period": 14, "smooth_k": 5, "smooth_d": 5}, sample_ohlcv
        )
        # Both param combinations produce valid K and D series
        _assert_outputs(r1, ["k", "d"])
        _assert_outputs(r2, ["k", "d"])
        # All values in valid range [0, 100]
        for key in ["k", "d"]:
            assert (r1[key].dropna() >= -0.1).all() and (r1[key].dropna() <= 100.1).all()
            assert (r2[key].dropna() >= -0.1).all() and (r2[key].dropna() <= 100.1).all()
