"""
Indicator Library

Comprehensive collection of technical indicators that can be
used in the visual strategy builder.

Supports:
- Standard indicators (RSI, MACD, Bollinger, etc.)
- Custom indicators (user-defined)
- Indicator combination and transformation
"""

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class IndicatorType(Enum):
    """Types of indicators"""

    # Trend
    SMA = "sma"
    EMA = "ema"
    WMA = "wma"
    DEMA = "dema"
    TEMA = "tema"
    HULL_MA = "hull_ma"
    VWMA = "vwma"
    SUPERTREND = "supertrend"
    ICHIMOKU = "ichimoku"
    PARABOLIC_SAR = "parabolic_sar"

    # Momentum
    RSI = "rsi"
    STOCHASTIC = "stochastic"
    STOCH_RSI = "stoch_rsi"
    MACD = "macd"
    CCI = "cci"
    WILLIAMS_R = "williams_r"
    ROC = "roc"
    MFI = "mfi"
    CMO = "cmo"

    # Volatility
    ATR = "atr"
    BOLLINGER = "bollinger"
    KELTNER = "keltner"
    DONCHIAN = "donchian"
    STANDARD_DEV = "standard_dev"
    HISTORICAL_VOL = "historical_vol"

    # Volume
    OBV = "obv"
    VOLUME_SMA = "volume_sma"
    VOLUME_PROFILE = "volume_profile"
    VWAP = "vwap"
    PVT = "pvt"
    AD_LINE = "ad_line"
    CMF = "cmf"

    # Support/Resistance
    PIVOT_POINTS = "pivot_points"
    FIBONACCI = "fibonacci"
    SUPPORT_RESISTANCE = "support_resistance"

    # Pattern Recognition
    CANDLESTICK_PATTERN = "candlestick_pattern"
    CHART_PATTERN = "chart_pattern"

    # Custom
    CUSTOM = "custom"


@dataclass
class IndicatorParameter:
    """Parameter for an indicator"""

    name: str
    param_type: str  # "int", "float", "bool", "string", "choice"
    default: Any
    description: str = ""
    min_value: float | None = None
    max_value: float | None = None
    choices: list[Any] | None = None
    step: float | None = None

    def validate(self, value: Any) -> bool:
        """Validate parameter value"""
        if self.param_type == "int":
            if not isinstance(value, int):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        elif self.param_type == "float":
            if not isinstance(value, (int, float)):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        elif self.param_type == "bool":
            if not isinstance(value, bool):
                return False
        elif self.param_type == "choice":
            if self.choices and value not in self.choices:
                return False
        return True


@dataclass
class IndicatorOutput:
    """Output of an indicator"""

    name: str
    description: str = ""


@dataclass
class CustomIndicator:
    """
        User-defined custom indicator

        Example:
            indicator = CustomIndicator(
                name="My Custom RSI",
                indicator_type=IndicatorType.CUSTOM,
                code='''
    def calculate(close, period=14):
        delta = np.diff(close, prepend=close[0])
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)

        avg_gain = pd.Series(gains).rolling(period).mean().values
        avg_loss = pd.Series(losses).rolling(period).mean().values

        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return {"rsi": rsi}
                ''',
                parameters=[
                    IndicatorParameter("period", "int", 14, min_value=2, max_value=100)
                ],
                outputs=[IndicatorOutput("rsi")]
            )
    """

    id: str
    name: str
    indicator_type: IndicatorType
    code: str
    parameters: list[IndicatorParameter] = field(default_factory=list)
    outputs: list[IndicatorOutput] = field(default_factory=list)
    description: str = ""
    author: str = ""
    version: str = "1.0"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "indicator_type": self.indicator_type.value,
            "code": self.code,
            "parameters": [
                {
                    "name": p.name,
                    "param_type": p.param_type,
                    "default": p.default,
                    "description": p.description,
                    "min_value": p.min_value,
                    "max_value": p.max_value,
                    "choices": p.choices,
                    "step": p.step,
                }
                for p in self.parameters
            ],
            "outputs": [
                {"name": o.name, "description": o.description} for o in self.outputs
            ],
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "tags": self.tags,
        }


class IndicatorLibrary:
    """
    Library of built-in and custom indicators

    Provides calculation functions for all indicator types.
    """

    def __init__(self):
        self.custom_indicators: dict[str, CustomIndicator] = {}
        self._calculators: dict[IndicatorType, Callable] = {
            IndicatorType.SMA: self._calc_sma,
            IndicatorType.EMA: self._calc_ema,
            IndicatorType.WMA: self._calc_wma,
            IndicatorType.RSI: self._calc_rsi,
            IndicatorType.MACD: self._calc_macd,
            IndicatorType.BOLLINGER: self._calc_bollinger,
            IndicatorType.ATR: self._calc_atr,
            IndicatorType.STOCHASTIC: self._calc_stochastic,
            IndicatorType.CCI: self._calc_cci,
            IndicatorType.WILLIAMS_R: self._calc_williams_r,
            IndicatorType.ROC: self._calc_roc,
            IndicatorType.MFI: self._calc_mfi,
            IndicatorType.OBV: self._calc_obv,
            IndicatorType.VWAP: self._calc_vwap,
            IndicatorType.KELTNER: self._calc_keltner,
            IndicatorType.DONCHIAN: self._calc_donchian,
            IndicatorType.SUPERTREND: self._calc_supertrend,
            IndicatorType.HULL_MA: self._calc_hull_ma,
            IndicatorType.DEMA: self._calc_dema,
            IndicatorType.TEMA: self._calc_tema,
            IndicatorType.STOCH_RSI: self._calc_stoch_rsi,
            IndicatorType.CMO: self._calc_cmo,
            IndicatorType.PVT: self._calc_pvt,
            IndicatorType.AD_LINE: self._calc_ad_line,
            IndicatorType.CMF: self._calc_cmf,
            IndicatorType.STANDARD_DEV: self._calc_stddev,
        }

    def calculate(
        self,
        indicator_type: IndicatorType,
        data: dict[str, np.ndarray],
        parameters: dict[str, Any],
    ) -> dict[str, np.ndarray]:
        """
        Calculate indicator values

        Args:
            indicator_type: Type of indicator
            data: Input data (close, high, low, open, volume)
            parameters: Indicator parameters

        Returns:
            Dictionary of output arrays
        """
        if indicator_type == IndicatorType.CUSTOM:
            return self._calc_custom(data, parameters)

        calculator = self._calculators.get(indicator_type)
        if not calculator:
            raise ValueError(f"Unknown indicator type: {indicator_type}")

        return calculator(data, parameters)

    def get_indicator_info(self, indicator_type: IndicatorType) -> dict[str, Any]:
        """Get indicator information"""
        info = INDICATOR_DEFINITIONS.get(indicator_type, {})
        return {
            "type": indicator_type.value,
            "name": info.get("name", indicator_type.value),
            "description": info.get("description", ""),
            "category": info.get("category", "custom"),
            "parameters": info.get("parameters", []),
            "outputs": info.get("outputs", []),
            "inputs": info.get("inputs", ["close"]),
        }

    def get_all_indicators(self) -> list[dict[str, Any]]:
        """Get all available indicators"""
        result = []
        for ind_type in IndicatorType:
            if ind_type != IndicatorType.CUSTOM:
                result.append(self.get_indicator_info(ind_type))

        # Add custom indicators
        for custom in self.custom_indicators.values():
            result.append(
                {
                    "type": custom.id,
                    "name": custom.name,
                    "description": custom.description,
                    "category": "custom",
                    "parameters": [
                        {
                            "name": p.name,
                            "param_type": p.param_type,
                            "default": p.default,
                        }
                        for p in custom.parameters
                    ],
                    "outputs": [o.name for o in custom.outputs],
                    "is_custom": True,
                }
            )

        return result

    def add_custom_indicator(self, indicator: CustomIndicator) -> None:
        """Add a custom indicator"""
        self.custom_indicators[indicator.id] = indicator

    def remove_custom_indicator(self, indicator_id: str) -> bool:
        """Remove a custom indicator"""
        if indicator_id in self.custom_indicators:
            del self.custom_indicators[indicator_id]
            return True
        return False

    # === Indicator Calculations ===

    def _calc_sma(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Simple Moving Average"""
        source = data.get("close", data.get("source", np.array([])))
        period = params.get("period", 20)

        if len(source) < period:
            return {"sma": np.full_like(source, np.nan)}

        sma = np.convolve(source, np.ones(period) / period, mode="full")[: len(source)]
        sma[: period - 1] = np.nan

        return {"sma": sma}

    def _calc_ema(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Exponential Moving Average"""
        source = data.get("close", data.get("source", np.array([])))
        period = params.get("period", 20)

        if len(source) < period:
            return {"ema": np.full_like(source, np.nan)}

        alpha = 2 / (period + 1)
        ema = np.zeros_like(source, dtype=float)
        ema[0] = source[0]

        for i in range(1, len(source)):
            ema[i] = alpha * source[i] + (1 - alpha) * ema[i - 1]

        return {"ema": ema}

    def _calc_wma(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Weighted Moving Average"""
        source = data.get("close", data.get("source", np.array([])))
        period = params.get("period", 20)

        if len(source) < period:
            return {"wma": np.full_like(source, np.nan)}

        weights = np.arange(1, period + 1)
        wma = np.full_like(source, np.nan, dtype=float)

        for i in range(period - 1, len(source)):
            wma[i] = np.sum(weights * source[i - period + 1 : i + 1]) / np.sum(weights)

        return {"wma": wma}

    def _calc_dema(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Double Exponential Moving Average"""
        ema1 = self._calc_ema(data, params)["ema"]
        ema2 = self._calc_ema({"close": ema1}, params)["ema"]
        dema = 2 * ema1 - ema2
        return {"dema": dema}

    def _calc_tema(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Triple Exponential Moving Average"""
        ema1 = self._calc_ema(data, params)["ema"]
        ema2 = self._calc_ema({"close": ema1}, params)["ema"]
        ema3 = self._calc_ema({"close": ema2}, params)["ema"]
        tema = 3 * ema1 - 3 * ema2 + ema3
        return {"tema": tema}

    def _calc_hull_ma(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Hull Moving Average"""
        period = params.get("period", 20)
        half_period = max(1, period // 2)
        sqrt_period = max(1, int(math.sqrt(period)))

        wma_half = self._calc_wma(data, {"period": half_period})["wma"]
        wma_full = self._calc_wma(data, {"period": period})["wma"]

        raw_hma = 2 * wma_half - wma_full
        hma = self._calc_wma({"close": raw_hma}, {"period": sqrt_period})["wma"]

        return {"hull_ma": hma}

    def _calc_rsi(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Relative Strength Index"""
        source = data.get("close", data.get("source", np.array([])))
        period = params.get("period", 14)

        if len(source) < period + 1:
            return {"rsi": np.full_like(source, np.nan)}

        # Calculate price changes
        delta = np.diff(source, prepend=source[0])

        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)

        # EMA-based smoothing
        alpha = 1 / period
        avg_gain = np.zeros_like(source, dtype=float)
        avg_loss = np.zeros_like(source, dtype=float)

        avg_gain[period] = np.mean(gains[1 : period + 1])
        avg_loss[period] = np.mean(losses[1 : period + 1])

        for i in range(period + 1, len(source)):
            avg_gain[i] = alpha * gains[i] + (1 - alpha) * avg_gain[i - 1]
            avg_loss[i] = alpha * losses[i] + (1 - alpha) * avg_loss[i - 1]

        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi[:period] = np.nan

        return {"rsi": rsi}

    def _calc_stoch_rsi(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Stochastic RSI"""
        rsi_period = params.get("rsi_period", 14)
        stoch_period = params.get("stoch_period", 14)
        k_period = params.get("k_period", 3)
        d_period = params.get("d_period", 3)

        rsi = self._calc_rsi(data, {"period": rsi_period})["rsi"]

        stoch_rsi = np.full_like(rsi, np.nan)
        for i in range(stoch_period - 1, len(rsi)):
            window = rsi[i - stoch_period + 1 : i + 1]
            min_rsi = np.nanmin(window)
            max_rsi = np.nanmax(window)
            if max_rsi - min_rsi > 0:
                stoch_rsi[i] = (rsi[i] - min_rsi) / (max_rsi - min_rsi) * 100

        k = self._calc_sma({"close": stoch_rsi}, {"period": k_period})["sma"]
        d = self._calc_sma({"close": k}, {"period": d_period})["sma"]

        return {"stoch_rsi": stoch_rsi, "k": k, "d": d}

    def _calc_cmo(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Chande Momentum Oscillator"""
        source = data.get("close", np.array([]))
        period = params.get("period", 14)

        if len(source) < period + 1:
            return {"cmo": np.full_like(source, np.nan)}

        delta = np.diff(source, prepend=source[0])
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)

        sum_gains = np.convolve(gains, np.ones(period), mode="full")[: len(source)]
        sum_losses = np.convolve(losses, np.ones(period), mode="full")[: len(source)]

        cmo = 100 * (sum_gains - sum_losses) / (sum_gains + sum_losses + 1e-10)
        cmo[:period] = np.nan

        return {"cmo": cmo}

    def _calc_macd(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Moving Average Convergence Divergence"""
        fast_period = params.get("fast_period", 12)
        slow_period = params.get("slow_period", 26)
        signal_period = params.get("signal_period", 9)

        fast_ema = self._calc_ema(data, {"period": fast_period})["ema"]
        slow_ema = self._calc_ema(data, {"period": slow_period})["ema"]

        macd_line = fast_ema - slow_ema
        signal_line = self._calc_ema({"close": macd_line}, {"period": signal_period})[
            "ema"
        ]
        histogram = macd_line - signal_line

        return {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram,
        }

    def _calc_bollinger(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Bollinger Bands"""
        source = data.get("close", data.get("source", np.array([])))
        period = params.get("period", 20)
        std_dev = params.get("std_dev", 2.0)

        if len(source) < period:
            return {
                "upper": np.full_like(source, np.nan),
                "middle": np.full_like(source, np.nan),
                "lower": np.full_like(source, np.nan),
                "bandwidth": np.full_like(source, np.nan),
                "percent_b": np.full_like(source, np.nan),
            }

        middle = self._calc_sma(data, {"period": period})["sma"]

        # Calculate rolling std
        std = np.full_like(source, np.nan, dtype=float)
        for i in range(period - 1, len(source)):
            std[i] = np.std(source[i - period + 1 : i + 1])

        upper = middle + std_dev * std
        lower = middle - std_dev * std
        bandwidth = (upper - lower) / middle * 100
        percent_b = (source - lower) / (upper - lower + 1e-10) * 100

        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "bandwidth": bandwidth,
            "percent_b": percent_b,
        }

    def _calc_atr(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Average True Range"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        close = data.get("close", np.array([]))
        period = params.get("period", 14)

        if len(high) < 2:
            return {"atr": np.array([])}

        # True Range
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]

        tr = np.maximum(
            high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))
        )

        # ATR (EMA of TR)
        atr = self._calc_ema({"close": tr}, {"period": period})["ema"]

        return {"atr": atr, "tr": tr}

    def _calc_stochastic(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Stochastic Oscillator"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        close = data.get("close", np.array([]))
        k_period = params.get("k_period", 14)
        d_period = params.get("d_period", 3)

        if len(close) < k_period:
            return {
                "k": np.full_like(close, np.nan),
                "d": np.full_like(close, np.nan),
            }

        k = np.full_like(close, np.nan, dtype=float)

        for i in range(k_period - 1, len(close)):
            highest = np.max(high[i - k_period + 1 : i + 1])
            lowest = np.min(low[i - k_period + 1 : i + 1])
            if highest - lowest > 0:
                k[i] = (close[i] - lowest) / (highest - lowest) * 100

        d = self._calc_sma({"close": k}, {"period": d_period})["sma"]

        return {"k": k, "d": d}

    def _calc_cci(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Commodity Channel Index"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        close = data.get("close", np.array([]))
        period = params.get("period", 20)

        typical = (high + low + close) / 3
        sma = self._calc_sma({"close": typical}, {"period": period})["sma"]

        # Mean deviation
        mad = np.full_like(typical, np.nan, dtype=float)
        for i in range(period - 1, len(typical)):
            mad[i] = np.mean(np.abs(typical[i - period + 1 : i + 1] - sma[i]))

        cci = (typical - sma) / (0.015 * mad + 1e-10)

        return {"cci": cci}

    def _calc_williams_r(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Williams %R"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        close = data.get("close", np.array([]))
        period = params.get("period", 14)

        williams_r = np.full_like(close, np.nan, dtype=float)

        for i in range(period - 1, len(close)):
            highest = np.max(high[i - period + 1 : i + 1])
            lowest = np.min(low[i - period + 1 : i + 1])
            if highest - lowest > 0:
                williams_r[i] = (highest - close[i]) / (highest - lowest) * -100

        return {"williams_r": williams_r}

    def _calc_roc(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Rate of Change"""
        source = data.get("close", np.array([]))
        period = params.get("period", 12)

        roc = np.full_like(source, np.nan, dtype=float)

        for i in range(period, len(source)):
            if source[i - period] != 0:
                roc[i] = (source[i] - source[i - period]) / source[i - period] * 100

        return {"roc": roc}

    def _calc_mfi(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Money Flow Index"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        close = data.get("close", np.array([]))
        volume = data.get("volume", np.array([]))
        period = params.get("period", 14)

        typical = (high + low + close) / 3
        money_flow = typical * volume

        delta_typical = np.diff(typical, prepend=typical[0])
        positive_flow = np.where(delta_typical > 0, money_flow, 0)
        negative_flow = np.where(delta_typical < 0, money_flow, 0)

        sum_pos = np.convolve(positive_flow, np.ones(period), mode="full")[: len(close)]
        sum_neg = np.convolve(negative_flow, np.ones(period), mode="full")[: len(close)]

        mfi = 100 - (100 / (1 + sum_pos / (sum_neg + 1e-10)))
        mfi[:period] = np.nan

        return {"mfi": mfi}

    def _calc_obv(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """On Balance Volume"""
        close = data.get("close", np.array([]))
        volume = data.get("volume", np.array([]))

        obv = np.zeros_like(close, dtype=float)

        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv[i] = obv[i - 1] + volume[i]
            elif close[i] < close[i - 1]:
                obv[i] = obv[i - 1] - volume[i]
            else:
                obv[i] = obv[i - 1]

        return {"obv": obv}

    def _calc_pvt(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Price Volume Trend"""
        close = data.get("close", np.array([]))
        volume = data.get("volume", np.array([]))

        pvt = np.zeros_like(close, dtype=float)

        for i in range(1, len(close)):
            if close[i - 1] != 0:
                pvt[i] = (
                    pvt[i - 1] + volume[i] * (close[i] - close[i - 1]) / close[i - 1]
                )

        return {"pvt": pvt}

    def _calc_ad_line(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Accumulation/Distribution Line"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        close = data.get("close", np.array([]))
        volume = data.get("volume", np.array([]))

        clv = ((close - low) - (high - close)) / (high - low + 1e-10)
        ad = np.cumsum(clv * volume)

        return {"ad_line": ad}

    def _calc_cmf(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Chaikin Money Flow"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        close = data.get("close", np.array([]))
        volume = data.get("volume", np.array([]))
        period = params.get("period", 20)

        clv = ((close - low) - (high - close)) / (high - low + 1e-10)
        money_flow_vol = clv * volume

        cmf = np.full_like(close, np.nan, dtype=float)

        for i in range(period - 1, len(close)):
            sum_mfv = np.sum(money_flow_vol[i - period + 1 : i + 1])
            sum_vol = np.sum(volume[i - period + 1 : i + 1])
            if sum_vol > 0:
                cmf[i] = sum_mfv / sum_vol

        return {"cmf": cmf}

    def _calc_vwap(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Volume Weighted Average Price"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        close = data.get("close", np.array([]))
        volume = data.get("volume", np.array([]))

        typical = (high + low + close) / 3
        cum_tp_vol = np.cumsum(typical * volume)
        cum_vol = np.cumsum(volume)

        vwap = cum_tp_vol / (cum_vol + 1e-10)

        return {"vwap": vwap}

    def _calc_keltner(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Keltner Channels"""
        period = params.get("period", 20)
        multiplier = params.get("multiplier", 2.0)

        ema = self._calc_ema(data, {"period": period})["ema"]
        atr = self._calc_atr(data, {"period": period})["atr"]

        upper = ema + multiplier * atr
        lower = ema - multiplier * atr

        return {
            "upper": upper,
            "middle": ema,
            "lower": lower,
        }

    def _calc_donchian(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Donchian Channels"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        period = params.get("period", 20)

        upper = np.full_like(high, np.nan, dtype=float)
        lower = np.full_like(low, np.nan, dtype=float)

        for i in range(period - 1, len(high)):
            upper[i] = np.max(high[i - period + 1 : i + 1])
            lower[i] = np.min(low[i - period + 1 : i + 1])

        middle = (upper + lower) / 2

        return {"upper": upper, "middle": middle, "lower": lower}

    def _calc_supertrend(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Supertrend Indicator"""
        high = data.get("high", np.array([]))
        low = data.get("low", np.array([]))
        close = data.get("close", np.array([]))
        period = params.get("period", 10)
        multiplier = params.get("multiplier", 3.0)

        atr = self._calc_atr(data, {"period": period})["atr"]
        hl2 = (high + low) / 2

        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr

        supertrend = np.zeros_like(close, dtype=float)
        direction = np.ones_like(close, dtype=int)  # 1 = up, -1 = down

        for i in range(1, len(close)):
            # Adjust bands
            if np.isnan(upper_band[i - 1]):
                final_upper = upper_band[i]
            else:
                final_upper = (
                    min(upper_band[i], upper_band[i - 1])
                    if close[i - 1] > upper_band[i - 1]
                    else upper_band[i]
                )

            if np.isnan(lower_band[i - 1]):
                final_lower = lower_band[i]
            else:
                final_lower = (
                    max(lower_band[i], lower_band[i - 1])
                    if close[i - 1] < lower_band[i - 1]
                    else lower_band[i]
                )

            upper_band[i] = final_upper
            lower_band[i] = final_lower

            # Determine trend
            if direction[i - 1] == 1:
                if close[i] < lower_band[i]:
                    direction[i] = -1
                    supertrend[i] = upper_band[i]
                else:
                    direction[i] = 1
                    supertrend[i] = lower_band[i]
            else:
                if close[i] > upper_band[i]:
                    direction[i] = 1
                    supertrend[i] = lower_band[i]
                else:
                    direction[i] = -1
                    supertrend[i] = upper_band[i]

        return {"supertrend": supertrend, "direction": direction.astype(float)}

    def _calc_stddev(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Standard Deviation"""
        source = data.get("close", np.array([]))
        period = params.get("period", 20)

        std = np.full_like(source, np.nan, dtype=float)

        for i in range(period - 1, len(source)):
            std[i] = np.std(source[i - period + 1 : i + 1])

        return {"stddev": std}

    def _calc_custom(
        self, data: dict[str, np.ndarray], params: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Calculate custom indicator"""
        indicator_id = params.get("indicator_id")
        if not indicator_id or indicator_id not in self.custom_indicators:
            raise ValueError(f"Custom indicator not found: {indicator_id}")

        indicator = self.custom_indicators[indicator_id]

        # Prepare namespace for code execution
        namespace = {
            "np": np,
            "data": data,
            "params": params,
        }

        # Execute custom code
        try:
            exec(indicator.code, namespace)
            if "calculate" in namespace:
                result = namespace["calculate"](data, **params)
                return result
            else:
                raise ValueError("Custom indicator must define 'calculate' function")
        except Exception as e:
            logger.error(f"Error executing custom indicator: {e}")
            raise


# Indicator definitions for UI
INDICATOR_DEFINITIONS: dict[IndicatorType, dict[str, Any]] = {
    IndicatorType.SMA: {
        "name": "Simple Moving Average",
        "description": "Average of closing prices over a period",
        "category": "trend",
        "inputs": ["close"],
        "outputs": ["sma"],
        "parameters": [
            {
                "name": "period",
                "param_type": "int",
                "default": 20,
                "min_value": 2,
                "max_value": 500,
            },
        ],
    },
    IndicatorType.EMA: {
        "name": "Exponential Moving Average",
        "description": "Weighted average giving more weight to recent prices",
        "category": "trend",
        "inputs": ["close"],
        "outputs": ["ema"],
        "parameters": [
            {
                "name": "period",
                "param_type": "int",
                "default": 20,
                "min_value": 2,
                "max_value": 500,
            },
        ],
    },
    IndicatorType.RSI: {
        "name": "Relative Strength Index",
        "description": "Momentum oscillator measuring speed and magnitude of price changes",
        "category": "momentum",
        "inputs": ["close"],
        "outputs": ["rsi"],
        "parameters": [
            {
                "name": "period",
                "param_type": "int",
                "default": 14,
                "min_value": 2,
                "max_value": 100,
            },
        ],
    },
    IndicatorType.MACD: {
        "name": "MACD",
        "description": "Trend-following momentum indicator",
        "category": "momentum",
        "inputs": ["close"],
        "outputs": ["macd_line", "signal_line", "histogram"],
        "parameters": [
            {"name": "fast_period", "param_type": "int", "default": 12},
            {"name": "slow_period", "param_type": "int", "default": 26},
            {"name": "signal_period", "param_type": "int", "default": 9},
        ],
    },
    IndicatorType.BOLLINGER: {
        "name": "Bollinger Bands",
        "description": "Volatility bands placed above and below a moving average",
        "category": "volatility",
        "inputs": ["close"],
        "outputs": ["upper", "middle", "lower", "bandwidth", "percent_b"],
        "parameters": [
            {"name": "period", "param_type": "int", "default": 20},
            {"name": "std_dev", "param_type": "float", "default": 2.0},
        ],
    },
    IndicatorType.ATR: {
        "name": "Average True Range",
        "description": "Volatility indicator based on true range",
        "category": "volatility",
        "inputs": ["high", "low", "close"],
        "outputs": ["atr", "tr"],
        "parameters": [
            {"name": "period", "param_type": "int", "default": 14},
        ],
    },
    IndicatorType.STOCHASTIC: {
        "name": "Stochastic Oscillator",
        "description": "Momentum indicator comparing closing price to price range",
        "category": "momentum",
        "inputs": ["high", "low", "close"],
        "outputs": ["k", "d"],
        "parameters": [
            {"name": "k_period", "param_type": "int", "default": 14},
            {"name": "d_period", "param_type": "int", "default": 3},
        ],
    },
    IndicatorType.CCI: {
        "name": "Commodity Channel Index",
        "description": "Momentum oscillator used to identify cyclical trends",
        "category": "momentum",
        "inputs": ["high", "low", "close"],
        "outputs": ["cci"],
        "parameters": [
            {"name": "period", "param_type": "int", "default": 20},
        ],
    },
    IndicatorType.OBV: {
        "name": "On Balance Volume",
        "description": "Momentum indicator using volume flow",
        "category": "volume",
        "inputs": ["close", "volume"],
        "outputs": ["obv"],
        "parameters": [],
    },
    IndicatorType.VWAP: {
        "name": "Volume Weighted Average Price",
        "description": "Trading benchmark showing average price weighted by volume",
        "category": "volume",
        "inputs": ["high", "low", "close", "volume"],
        "outputs": ["vwap"],
        "parameters": [],
    },
    IndicatorType.SUPERTREND: {
        "name": "Supertrend",
        "description": "Trend-following indicator using ATR",
        "category": "trend",
        "inputs": ["high", "low", "close"],
        "outputs": ["supertrend", "direction"],
        "parameters": [
            {"name": "period", "param_type": "int", "default": 10},
            {"name": "multiplier", "param_type": "float", "default": 3.0},
        ],
    },
}
