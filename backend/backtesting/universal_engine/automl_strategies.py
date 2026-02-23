"""
AutoML Strategies Module for Universal Math Engine v2.4.

This module provides automatic strategy discovery and optimization:
1. FeatureEngineering - Auto feature generation from OHLCV
2. ModelSelector - Auto model selection and hyperparameter tuning
3. StrategyEvolver - Genetic algorithm for strategy evolution
4. SignalCombiner - Ensemble signal combination
5. WalkForwardValidator - Robust strategy validation

Author: Universal Math Engine Team
Version: 2.4.0
"""

import copy
import random
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from numpy.typing import NDArray

# ============================================================================
# ENUMS AND DATA STRUCTURES
# ============================================================================


class FeatureType(Enum):
    """Types of auto-generated features."""

    MOMENTUM = "momentum"
    TREND = "trend"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    PATTERN = "pattern"
    STATISTICAL = "statistical"
    CUSTOM = "custom"


class ModelType(Enum):
    """Types of ML models for AutoML."""

    LINEAR = "linear"
    TREE = "tree"
    ENSEMBLE = "ensemble"
    NEURAL = "neural"
    SVM = "svm"
    GENETIC = "genetic"


class CrossoverType(Enum):
    """Genetic algorithm crossover types."""

    SINGLE_POINT = "single_point"
    TWO_POINT = "two_point"
    UNIFORM = "uniform"
    ARITHMETIC = "arithmetic"


class SelectionType(Enum):
    """Genetic algorithm selection types."""

    TOURNAMENT = "tournament"
    ROULETTE = "roulette"
    RANK = "rank"
    ELITIST = "elitist"


@dataclass
class Feature:
    """Generated feature definition."""

    name: str
    feature_type: FeatureType
    params: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.0
    correlation_with_target: float = 0.0


@dataclass
class FeatureSet:
    """Set of features for a strategy."""

    features: list[Feature]
    feature_matrix: NDArray | None = None
    target: NDArray | None = None
    feature_importance: dict[str, float] = field(default_factory=dict)


@dataclass
class StrategyGenome:
    """Genome representation of a trading strategy."""

    # Entry conditions
    entry_features: list[str]
    entry_thresholds: dict[str, tuple[float, float]]  # (min, max)
    entry_logic: str  # "and" or "or"

    # Exit conditions
    exit_features: list[str]
    exit_thresholds: dict[str, tuple[float, float]]
    exit_logic: str

    # Position sizing
    position_size_factor: float = 1.0

    # Risk management
    stop_loss: float = 0.02
    take_profit: float = 0.04

    # Metadata
    fitness: float = 0.0
    generation: int = 0
    strategy_id: str = ""


@dataclass
class AutoMLConfig:
    """Configuration for AutoML optimization."""

    # Feature engineering
    max_features: int = 50
    feature_types: list[FeatureType] = field(default_factory=lambda: list(FeatureType))

    # Model selection
    model_types: list[ModelType] = field(default_factory=lambda: [ModelType.ENSEMBLE])
    max_models: int = 10

    # Genetic algorithm
    population_size: int = 100
    generations: int = 50
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    elitism_ratio: float = 0.1
    tournament_size: int = 5

    # Validation
    train_ratio: float = 0.6
    val_ratio: float = 0.2
    test_ratio: float = 0.2
    walk_forward_windows: int = 5

    # Fitness
    fitness_metric: str = "sharpe"  # sharpe, sortino, calmar, profit_factor


@dataclass
class ValidationResult:
    """Walk-forward validation result."""

    train_sharpe: float
    val_sharpe: float
    test_sharpe: float
    train_return: float
    val_return: float
    test_return: float
    max_drawdown: float
    profit_factor: float
    win_rate: float
    total_trades: int
    is_overfit: bool = False
    robustness_score: float = 0.0


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================


class FeatureEngineering:
    """
    Automatic feature generation from OHLCV data.

    Generates hundreds of technical indicators automatically.
    """

    def __init__(self, config: AutoMLConfig | None = None):
        self.config = config or AutoMLConfig()
        self._feature_generators: dict[FeatureType, list[Callable]] = {}
        self._register_generators()

    def _register_generators(self) -> None:
        """Register feature generator functions."""
        self._feature_generators = {
            FeatureType.MOMENTUM: [
                self._generate_rsi,
                self._generate_roc,
                self._generate_momentum,
                self._generate_tsi,
            ],
            FeatureType.TREND: [
                self._generate_sma_crossovers,
                self._generate_ema_crossovers,
                self._generate_adx,
                self._generate_aroon,
            ],
            FeatureType.VOLATILITY: [
                self._generate_atr,
                self._generate_bollinger,
                self._generate_keltner,
                self._generate_std,
            ],
            FeatureType.VOLUME: [
                self._generate_obv,
                self._generate_vwap,
                self._generate_mfi,
                self._generate_volume_ratio,
            ],
            FeatureType.PATTERN: [
                self._generate_candlestick_patterns,
                self._generate_pivot_points,
                self._generate_support_resistance,
            ],
            FeatureType.STATISTICAL: [
                self._generate_zscore,
                self._generate_percentile,
                self._generate_skew_kurt,
                self._generate_hurst,
            ],
        }

    def generate_features(
        self,
        open_prices: NDArray,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        volume: NDArray,
        target: NDArray | None = None,
    ) -> FeatureSet:
        """
        Generate comprehensive feature set.

        Args:
            open_prices: Open prices
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume
            target: Optional target for feature importance

        Returns:
            FeatureSet with all generated features
        """
        features: list[Feature] = []
        feature_arrays: list[NDArray] = []

        for feature_type in self.config.feature_types:
            if feature_type in self._feature_generators:
                for generator in self._feature_generators[feature_type]:
                    try:
                        generated = generator(open_prices, high, low, close, volume)
                        for name, array in generated.items():
                            features.append(
                                Feature(name=name, feature_type=feature_type)
                            )
                            feature_arrays.append(array)
                    except Exception:
                        continue

        # Stack feature arrays
        if feature_arrays:
            feature_matrix = np.column_stack(feature_arrays)

            # Calculate feature importance if target provided
            importance = {}
            if target is not None:
                importance = self._calculate_importance(
                    feature_matrix, target, features
                )
                for feat in features:
                    feat.importance = importance.get(feat.name, 0.0)

            # Select top features
            if len(features) > self.config.max_features:
                sorted_features = sorted(
                    features, key=lambda f: f.importance, reverse=True
                )
                features = sorted_features[: self.config.max_features]
                indices = [i for i, f in enumerate(sorted_features) if f in features]
                feature_matrix = feature_matrix[:, indices]

            return FeatureSet(
                features=features,
                feature_matrix=feature_matrix,
                target=target,
                feature_importance=importance,
            )

        return FeatureSet(features=[], feature_matrix=None)

    def _calculate_importance(
        self, features: NDArray, target: NDArray, feature_list: list[Feature]
    ) -> dict[str, float]:
        """Calculate feature importance using correlation and mutual info."""
        importance = {}
        n_features = features.shape[1]

        for i in range(n_features):
            feat = features[:, i]
            # Remove NaN
            mask = ~np.isnan(feat) & ~np.isnan(target)
            if mask.sum() < 10:
                importance[feature_list[i].name] = 0.0
                continue

            # Correlation
            corr = np.abs(np.corrcoef(feat[mask], target[mask])[0, 1])
            if np.isnan(corr):
                corr = 0.0

            importance[feature_list[i].name] = corr

        return importance

    # -------------------------------------------------------------------------
    # MOMENTUM FEATURES
    # -------------------------------------------------------------------------

    def _generate_rsi(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate RSI features with multiple periods."""
        features = {}
        for period in [7, 14, 21, 28]:
            delta = np.diff(close)
            gains = np.where(delta > 0, delta, 0)
            losses = np.where(delta < 0, -delta, 0)

            avg_gain = self._ewma(gains, period)
            avg_loss = self._ewma(losses, period)

            rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
            rsi = 100 - (100 / (1 + rs))

            # Pad to match original length
            rsi = np.insert(rsi, 0, np.nan)
            features[f"rsi_{period}"] = rsi

        return features

    def _generate_roc(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate Rate of Change features."""
        features = {}
        for period in [5, 10, 20, 50]:
            roc = np.full(len(close), np.nan)
            roc[period:] = (close[period:] - close[:-period]) / close[:-period] * 100
            features[f"roc_{period}"] = roc
        return features

    def _generate_momentum(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate momentum features."""
        features = {}
        for period in [10, 20, 50]:
            mom = np.full(len(close), np.nan)
            mom[period:] = close[period:] - close[:-period]
            features[f"momentum_{period}"] = mom
        return features

    def _generate_tsi(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate True Strength Index."""
        price_change = np.diff(close)
        double_smooth_pc = self._ewma(self._ewma(price_change, 25), 13)
        double_smooth_abs_pc = self._ewma(self._ewma(np.abs(price_change), 25), 13)

        tsi = np.where(
            double_smooth_abs_pc != 0, 100 * double_smooth_pc / double_smooth_abs_pc, 0
        )
        tsi = np.insert(tsi, 0, np.nan)

        return {"tsi": tsi}

    # -------------------------------------------------------------------------
    # TREND FEATURES
    # -------------------------------------------------------------------------

    def _generate_sma_crossovers(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate SMA crossover features."""
        features = {}

        sma_periods = [5, 10, 20, 50, 100, 200]
        smas = {}
        for period in sma_periods:
            smas[period] = self._sma(close, period)

        # Crossover signals and distances
        pairs = [(5, 20), (10, 50), (20, 100), (50, 200)]
        for fast, slow in pairs:
            if fast in smas and slow in smas:
                features[f"sma_{fast}_{slow}_diff"] = smas[fast] - smas[slow]
                features[f"sma_{fast}_{slow}_ratio"] = np.where(
                    smas[slow] != 0, smas[fast] / smas[slow], 1
                )
                # Crossover signal
                cross = np.zeros(len(close))
                diff = smas[fast] - smas[slow]
                cross[1:] = np.where(
                    (diff[1:] > 0) & (diff[:-1] <= 0),
                    1,
                    np.where((diff[1:] < 0) & (diff[:-1] >= 0), -1, 0),
                )
                features[f"sma_{fast}_{slow}_cross"] = cross

        return features

    def _generate_ema_crossovers(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate EMA crossover features."""
        features = {}

        ema_periods = [9, 12, 21, 26, 50]
        emas = {}
        for period in ema_periods:
            emas[period] = self._ema(close, period)

        # MACD-style features
        if 12 in emas and 26 in emas:
            macd = emas[12] - emas[26]
            signal = self._ema(macd, 9)
            features["macd"] = macd
            features["macd_signal"] = signal
            features["macd_histogram"] = macd - signal

        # EMA distance from price
        for period in ema_periods:
            features[f"ema_{period}_dist"] = (close - emas[period]) / close * 100

        return features

    def _generate_adx(
        self, _open: NDArray, high: NDArray, low: NDArray, close: NDArray, _vol: NDArray
    ) -> dict[str, NDArray]:
        """Generate ADX and DI features."""
        period = 14
        n = len(close)

        # True Range
        tr = np.zeros(n)
        tr[1:] = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])),
        )

        # +DM and -DM
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)

        up = high[1:] - high[:-1]
        down = low[:-1] - low[1:]

        plus_dm[1:] = np.where((up > down) & (up > 0), up, 0)
        minus_dm[1:] = np.where((down > up) & (down > 0), down, 0)

        # Smoothed averages
        atr = self._ewma(tr[1:], period)
        smooth_plus_dm = self._ewma(plus_dm[1:], period)
        smooth_minus_dm = self._ewma(minus_dm[1:], period)

        # +DI and -DI
        plus_di = 100 * smooth_plus_dm / np.where(atr != 0, atr, 1)
        minus_di = 100 * smooth_minus_dm / np.where(atr != 0, atr, 1)

        # DX and ADX
        di_sum = plus_di + minus_di
        dx = 100 * np.abs(plus_di - minus_di) / np.where(di_sum != 0, di_sum, 1)
        adx = self._ewma(dx, period)

        # Pad
        plus_di = np.insert(plus_di, 0, np.nan)
        minus_di = np.insert(minus_di, 0, np.nan)
        adx = np.insert(adx, 0, np.nan)

        return {
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di,
            "di_diff": plus_di - minus_di,
        }

    def _generate_aroon(
        self,
        _open: NDArray,
        high: NDArray,
        low: NDArray,
        _close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate Aroon indicator."""
        period = 25
        n = len(high)

        aroon_up = np.full(n, np.nan)
        aroon_down = np.full(n, np.nan)

        for i in range(period, n):
            window_high = high[i - period : i + 1]
            window_low = low[i - period : i + 1]

            high_idx = np.argmax(window_high)
            low_idx = np.argmin(window_low)

            aroon_up[i] = ((period - (period - high_idx)) / period) * 100
            aroon_down[i] = ((period - (period - low_idx)) / period) * 100

        return {
            "aroon_up": aroon_up,
            "aroon_down": aroon_down,
            "aroon_osc": aroon_up - aroon_down,
        }

    # -------------------------------------------------------------------------
    # VOLATILITY FEATURES
    # -------------------------------------------------------------------------

    def _generate_atr(
        self, _open: NDArray, high: NDArray, low: NDArray, close: NDArray, _vol: NDArray
    ) -> dict[str, NDArray]:
        """Generate ATR features."""
        features = {}

        for period in [7, 14, 21]:
            tr = np.zeros(len(close))
            tr[1:] = np.maximum(
                high[1:] - low[1:],
                np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])),
            )
            atr = self._ewma(tr[1:], period)
            atr = np.insert(atr, 0, np.nan)

            features[f"atr_{period}"] = atr
            features[f"atr_{period}_pct"] = atr / close * 100

        return features

    def _generate_bollinger(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate Bollinger Band features."""
        features = {}

        for period in [10, 20, 50]:
            sma = self._sma(close, period)
            std = self._rolling_std(close, period)

            upper = sma + 2 * std
            lower = sma - 2 * std

            features[f"bb_{period}_width"] = (upper - lower) / sma
            features[f"bb_{period}_pos"] = (close - lower) / (upper - lower)

        return features

    def _generate_keltner(
        self, _open: NDArray, high: NDArray, low: NDArray, close: NDArray, _vol: NDArray
    ) -> dict[str, NDArray]:
        """Generate Keltner Channel features."""
        period = 20
        atr_mult = 2

        ema = self._ema(close, period)

        tr = np.zeros(len(close))
        tr[1:] = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])),
        )
        atr = self._ewma(tr[1:], period)
        atr = np.insert(atr, 0, np.nan)

        upper = ema + atr_mult * atr
        lower = ema - atr_mult * atr

        return {
            "keltner_pos": (close - lower) / (upper - lower),
            "keltner_width": (upper - lower) / ema,
        }

    def _generate_std(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate standard deviation features."""
        features = {}

        for period in [10, 20, 50]:
            std = self._rolling_std(close, period)
            features[f"std_{period}"] = std
            features[f"std_{period}_pct"] = std / close * 100

        # Historical volatility
        returns = np.diff(np.log(close))
        returns = np.insert(returns, 0, 0)

        for period in [10, 20, 50]:
            hv = self._rolling_std(returns, period) * np.sqrt(252) * 100
            features[f"hv_{period}"] = hv

        return features

    # -------------------------------------------------------------------------
    # VOLUME FEATURES
    # -------------------------------------------------------------------------

    def _generate_obv(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        volume: NDArray,
    ) -> dict[str, NDArray]:
        """Generate On-Balance Volume features."""
        obv = np.zeros(len(close))
        obv[0] = volume[0]

        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv[i] = obv[i - 1] + volume[i]
            elif close[i] < close[i - 1]:
                obv[i] = obv[i - 1] - volume[i]
            else:
                obv[i] = obv[i - 1]

        obv_sma = self._sma(obv, 20)

        return {"obv": obv, "obv_sma_20": obv_sma, "obv_diff": obv - obv_sma}

    def _generate_vwap(
        self,
        _open: NDArray,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        volume: NDArray,
    ) -> dict[str, NDArray]:
        """Generate VWAP features."""
        typical_price = (high + low + close) / 3
        cum_tp_vol = np.cumsum(typical_price * volume)
        cum_vol = np.cumsum(volume)

        vwap = cum_tp_vol / np.where(cum_vol != 0, cum_vol, 1)

        return {"vwap": vwap, "vwap_dist": (close - vwap) / vwap * 100}

    def _generate_mfi(
        self,
        _open: NDArray,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        volume: NDArray,
    ) -> dict[str, NDArray]:
        """Generate Money Flow Index."""
        period = 14
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume

        positive_flow = np.zeros(len(close))
        negative_flow = np.zeros(len(close))

        for i in range(1, len(close)):
            if typical_price[i] > typical_price[i - 1]:
                positive_flow[i] = money_flow[i]
            else:
                negative_flow[i] = money_flow[i]

        positive_sum = self._rolling_sum(positive_flow, period)
        negative_sum = self._rolling_sum(negative_flow, period)

        money_ratio = positive_sum / np.where(negative_sum != 0, negative_sum, 1)
        mfi = 100 - (100 / (1 + money_ratio))

        return {"mfi": mfi}

    def _generate_volume_ratio(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        volume: NDArray,
    ) -> dict[str, NDArray]:
        """Generate volume ratio features."""
        features = {}

        for period in [10, 20, 50]:
            vol_sma = self._sma(volume, period)
            features[f"vol_ratio_{period}"] = volume / np.where(
                vol_sma != 0, vol_sma, 1
            )

        # Volume trend
        vol_change = np.diff(volume)
        vol_change = np.insert(vol_change, 0, 0)
        features["vol_change"] = vol_change
        features["vol_change_pct"] = vol_change / np.where(volume != 0, volume, 1) * 100

        return features

    # -------------------------------------------------------------------------
    # PATTERN FEATURES
    # -------------------------------------------------------------------------

    def _generate_candlestick_patterns(
        self,
        open_p: NDArray,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate candlestick pattern features."""
        n = len(close)

        # Body and wick sizes
        body = close - open_p
        upper_wick = high - np.maximum(open_p, close)
        lower_wick = np.minimum(open_p, close) - low
        total_range = high - low

        features = {
            "body_size": np.abs(body),
            "body_ratio": np.abs(body) / np.where(total_range != 0, total_range, 1),
            "upper_wick_ratio": upper_wick / np.where(total_range != 0, total_range, 1),
            "lower_wick_ratio": lower_wick / np.where(total_range != 0, total_range, 1),
        }

        # Doji detection
        features["is_doji"] = (
            np.abs(body) / np.where(total_range != 0, total_range, 1) < 0.1
        ).astype(float)

        # Hammer/shooting star
        features["is_hammer"] = (
            (lower_wick > 2 * np.abs(body)) & (upper_wick < 0.5 * np.abs(body))
        ).astype(float)

        features["is_shooting_star"] = (
            (upper_wick > 2 * np.abs(body)) & (lower_wick < 0.5 * np.abs(body))
        ).astype(float)

        # Engulfing
        engulfing = np.zeros(n)
        for i in range(1, n):
            if body[i] > 0 and body[i - 1] < 0:  # Bullish engulfing
                if open_p[i] < close[i - 1] and close[i] > open_p[i - 1]:
                    engulfing[i] = 1
            elif body[i] < 0 and body[i - 1] > 0:  # Bearish engulfing
                if open_p[i] > close[i - 1] and close[i] < open_p[i - 1]:
                    engulfing[i] = -1

        features["engulfing"] = engulfing

        return features

    def _generate_pivot_points(
        self, _open: NDArray, high: NDArray, low: NDArray, close: NDArray, _vol: NDArray
    ) -> dict[str, NDArray]:
        """Generate pivot point features."""
        # Standard pivot points (using previous day)
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)

        # Shift by 1 for actual trading use
        pivot = np.roll(pivot, 1)
        r1 = np.roll(r1, 1)
        s1 = np.roll(s1, 1)
        r2 = np.roll(r2, 1)
        s2 = np.roll(s2, 1)

        pivot[0] = r1[0] = s1[0] = r2[0] = s2[0] = np.nan

        return {
            "pivot": pivot,
            "pivot_dist": (close - pivot) / pivot * 100,
            "r1_dist": (close - r1) / r1 * 100,
            "s1_dist": (close - s1) / s1 * 100,
        }

    def _generate_support_resistance(
        self, _open: NDArray, high: NDArray, low: NDArray, close: NDArray, _vol: NDArray
    ) -> dict[str, NDArray]:
        """Generate support/resistance features."""
        window = 20
        n = len(close)

        features = {
            "highest_high": np.full(n, np.nan),
            "lowest_low": np.full(n, np.nan),
            "range_position": np.full(n, np.nan),
        }

        for i in range(window, n):
            hh = np.max(high[i - window : i])
            ll = np.min(low[i - window : i])
            features["highest_high"][i] = hh
            features["lowest_low"][i] = ll

            rng = hh - ll
            if rng > 0:
                features["range_position"][i] = (close[i] - ll) / rng

        return features

    # -------------------------------------------------------------------------
    # STATISTICAL FEATURES
    # -------------------------------------------------------------------------

    def _generate_zscore(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate Z-score features."""
        features = {}

        for period in [20, 50, 100]:
            mean = self._sma(close, period)
            std = self._rolling_std(close, period)
            zscore = (close - mean) / np.where(std != 0, std, 1)
            features[f"zscore_{period}"] = zscore

        return features

    def _generate_percentile(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate percentile rank features."""
        features = {}

        for period in [20, 50, 100]:
            pct_rank = np.full(len(close), np.nan)
            for i in range(period, len(close)):
                window = close[i - period : i + 1]
                pct_rank[i] = (np.sum(window < close[i]) / period) * 100
            features[f"pct_rank_{period}"] = pct_rank

        return features

    def _generate_skew_kurt(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate skewness and kurtosis features."""
        returns = np.diff(np.log(close))
        returns = np.insert(returns, 0, 0)

        period = 50
        n = len(close)

        skew = np.full(n, np.nan)
        kurt = np.full(n, np.nan)

        for i in range(period, n):
            window = returns[i - period : i]
            mean = np.mean(window)
            std = np.std(window)
            if std > 0:
                skew[i] = np.mean(((window - mean) / std) ** 3)
                kurt[i] = np.mean(((window - mean) / std) ** 4) - 3

        return {"skewness": skew, "kurtosis": kurt}

    def _generate_hurst(
        self,
        _open: NDArray,
        _high: NDArray,
        _low: NDArray,
        close: NDArray,
        _vol: NDArray,
    ) -> dict[str, NDArray]:
        """Generate Hurst exponent feature."""
        period = 100
        n = len(close)
        hurst = np.full(n, np.nan)

        for i in range(period, n):
            window = close[i - period : i]

            # R/S analysis
            mean = np.mean(window)
            std = np.std(window)

            if std > 0:
                cumdev = np.cumsum(window - mean)
                rs = (np.max(cumdev) - np.min(cumdev)) / std

                # Simplified Hurst estimate
                if rs > 0:
                    hurst[i] = np.log(rs) / np.log(period)

        return {"hurst": hurst}

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    def _sma(self, data: NDArray, period: int) -> NDArray:
        """Simple moving average."""
        result = np.full(len(data), np.nan)
        for i in range(period - 1, len(data)):
            result[i] = np.mean(data[i - period + 1 : i + 1])
        return result

    def _ema(self, data: NDArray, period: int) -> NDArray:
        """Exponential moving average."""
        alpha = 2 / (period + 1)
        result = np.zeros(len(data))
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    def _ewma(self, data: NDArray, period: int) -> NDArray:
        """Exponential weighted moving average."""
        alpha = 2 / (period + 1)
        result = np.zeros(len(data))
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    def _rolling_std(self, data: NDArray, period: int) -> NDArray:
        """Rolling standard deviation."""
        result = np.full(len(data), np.nan)
        for i in range(period - 1, len(data)):
            result[i] = np.std(data[i - period + 1 : i + 1])
        return result

    def _rolling_sum(self, data: NDArray, period: int) -> NDArray:
        """Rolling sum."""
        result = np.full(len(data), np.nan)
        for i in range(period - 1, len(data)):
            result[i] = np.sum(data[i - period + 1 : i + 1])
        return result


# ============================================================================
# MODEL SELECTOR
# ============================================================================


class BaseModel(ABC):
    """Base class for ML models."""

    @abstractmethod
    def fit(self, X: NDArray, y: NDArray) -> "BaseModel":
        """Train the model."""
        pass

    @abstractmethod
    def predict(self, X: NDArray) -> NDArray:
        """Make predictions."""
        pass

    @abstractmethod
    def get_params(self) -> dict[str, Any]:
        """Get model parameters."""
        pass


class LinearModel(BaseModel):
    """Simple linear regression model."""

    def __init__(self, regularization: float = 0.01):
        self.regularization = regularization
        self._weights: NDArray | None = None
        self._bias: float = 0.0

    def fit(self, X: NDArray, y: NDArray) -> "LinearModel":
        """Fit using closed-form solution with regularization."""
        _n_samples, n_features = X.shape

        # Add regularization
        XtX = X.T @ X + self.regularization * np.eye(n_features)
        Xty = X.T @ y

        self._weights = np.linalg.solve(XtX, Xty)
        self._bias = np.mean(y - X @ self._weights)

        return self

    def predict(self, X: NDArray) -> NDArray:
        """Make predictions."""
        if self._weights is None:
            raise ValueError("Model not fitted")
        return X @ self._weights + self._bias

    def get_params(self) -> dict[str, Any]:
        return {"regularization": self.regularization}


class DecisionTreeModel(BaseModel):
    """Simple decision tree model."""

    def __init__(self, max_depth: int = 5, min_samples_split: int = 10):
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self._tree: dict | None = None

    def fit(self, X: NDArray, y: NDArray) -> "DecisionTreeModel":
        """Build decision tree."""
        self._tree = self._build_tree(X, y, depth=0)
        return self

    def _build_tree(self, X: NDArray, y: NDArray, depth: int) -> dict:
        """Recursively build tree."""
        n_samples = len(y)

        # Stopping conditions
        if depth >= self.max_depth or n_samples < self.min_samples_split:
            return {"leaf": True, "value": np.mean(y)}

        # Find best split
        best_feature = 0
        best_threshold = 0.0
        best_gain = -np.inf

        for feature in range(X.shape[1]):
            thresholds = np.percentile(X[:, feature], [25, 50, 75])
            for threshold in thresholds:
                left_mask = X[:, feature] <= threshold
                right_mask = ~left_mask

                if left_mask.sum() < 2 or right_mask.sum() < 2:
                    continue

                # Variance reduction
                var_before = np.var(y)
                var_left = np.var(y[left_mask])
                var_right = np.var(y[right_mask])
                var_after = (
                    left_mask.sum() * var_left + right_mask.sum() * var_right
                ) / n_samples

                gain = var_before - var_after

                if gain > best_gain:
                    best_gain = gain
                    best_feature = feature
                    best_threshold = threshold

        # No good split found
        if best_gain <= 0:
            return {"leaf": True, "value": np.mean(y)}

        # Split data
        left_mask = X[:, best_feature] <= best_threshold
        right_mask = ~left_mask

        return {
            "leaf": False,
            "feature": best_feature,
            "threshold": best_threshold,
            "left": self._build_tree(X[left_mask], y[left_mask], depth + 1),
            "right": self._build_tree(X[right_mask], y[right_mask], depth + 1),
        }

    def _predict_one(self, x: NDArray, tree: dict) -> float:
        """Predict single sample."""
        if tree["leaf"]:
            return tree["value"]

        if x[tree["feature"]] <= tree["threshold"]:
            return self._predict_one(x, tree["left"])
        return self._predict_one(x, tree["right"])

    def predict(self, X: NDArray) -> NDArray:
        """Make predictions."""
        if self._tree is None:
            raise ValueError("Model not fitted")
        return np.array([self._predict_one(x, self._tree) for x in X])

    def get_params(self) -> dict[str, Any]:
        return {
            "max_depth": self.max_depth,
            "min_samples_split": self.min_samples_split,
        }


class EnsembleModel(BaseModel):
    """Ensemble of multiple models."""

    def __init__(self, n_estimators: int = 10, base_model: str = "tree"):
        self.n_estimators = n_estimators
        self.base_model = base_model
        self._models: list[BaseModel] = []

    def fit(self, X: NDArray, y: NDArray) -> "EnsembleModel":
        """Fit ensemble with bagging."""
        self._models = []
        n_samples = len(y)

        for _ in range(self.n_estimators):
            # Bootstrap sample
            indices = np.random.choice(n_samples, n_samples, replace=True)
            X_boot = X[indices]
            y_boot = y[indices]

            # Create and fit model
            model = DecisionTreeModel(max_depth=3) if self.base_model == "tree" else LinearModel()

            model.fit(X_boot, y_boot)
            self._models.append(model)

        return self

    def predict(self, X: NDArray) -> NDArray:
        """Average predictions from all models."""
        predictions = np.array([m.predict(X) for m in self._models])
        return np.mean(predictions, axis=0)

    def get_params(self) -> dict[str, Any]:
        return {"n_estimators": self.n_estimators, "base_model": self.base_model}


class ModelSelector:
    """Auto model selection and hyperparameter tuning."""

    def __init__(self, config: AutoMLConfig | None = None):
        self.config = config or AutoMLConfig()
        self._best_model: BaseModel | None = None
        self._best_score: float = -np.inf

    def select_model(
        self, X_train: NDArray, y_train: NDArray, X_val: NDArray, y_val: NDArray
    ) -> BaseModel:
        """
        Select best model from candidates.

        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features
            y_val: Validation target

        Returns:
            Best performing model
        """
        candidates = self._generate_candidates()

        for model in candidates:
            try:
                model.fit(X_train, y_train)
                y_pred = model.predict(X_val)

                # Calculate score (negative MSE)
                mse = np.mean((y_pred - y_val) ** 2)
                score = -mse

                if score > self._best_score:
                    self._best_score = score
                    self._best_model = model
            except Exception:
                continue

        if self._best_model is None:
            # Fallback to simple model
            self._best_model = LinearModel()
            self._best_model.fit(X_train, y_train)

        return self._best_model

    def _generate_candidates(self) -> list[BaseModel]:
        """Generate model candidates with different hyperparameters."""
        candidates = []

        if ModelType.LINEAR in self.config.model_types:
            for reg in [0.001, 0.01, 0.1, 1.0]:
                candidates.append(LinearModel(regularization=reg))

        if ModelType.TREE in self.config.model_types:
            for depth in [3, 5, 7]:
                for min_samples in [5, 10, 20]:
                    candidates.append(
                        DecisionTreeModel(
                            max_depth=depth, min_samples_split=min_samples
                        )
                    )

        if ModelType.ENSEMBLE in self.config.model_types:
            for n_est in [5, 10, 20]:
                candidates.append(EnsembleModel(n_estimators=n_est, base_model="tree"))

        return candidates[: self.config.max_models]


# ============================================================================
# STRATEGY EVOLVER (GENETIC ALGORITHM)
# ============================================================================


class StrategyEvolver:
    """
    Genetic algorithm for evolving trading strategies.

    Uses evolutionary computation to discover profitable strategies.
    """

    def __init__(
        self,
        config: AutoMLConfig | None = None,
        feature_names: list[str] | None = None,
    ):
        self.config = config or AutoMLConfig()
        self.feature_names = feature_names or []
        self._population: list[StrategyGenome] = []
        self._best_genome: StrategyGenome | None = None
        self._generation: int = 0

    def initialize_population(self) -> None:
        """Create initial random population."""
        self._population = []

        for _ in range(self.config.population_size):
            genome = self._create_random_genome()
            self._population.append(genome)

    def _create_random_genome(self) -> StrategyGenome:
        """Create a random strategy genome."""
        n_entry_features = random.randint(1, min(5, len(self.feature_names)))
        n_exit_features = random.randint(1, min(3, len(self.feature_names)))

        entry_features = random.sample(self.feature_names, n_entry_features)
        exit_features = random.sample(self.feature_names, n_exit_features)

        entry_thresholds = {
            f: (random.uniform(-2, 0), random.uniform(0, 2)) for f in entry_features
        }
        exit_thresholds = {
            f: (random.uniform(-2, 0), random.uniform(0, 2)) for f in exit_features
        }

        return StrategyGenome(
            entry_features=entry_features,
            entry_thresholds=entry_thresholds,
            entry_logic=random.choice(["and", "or"]),
            exit_features=exit_features,
            exit_thresholds=exit_thresholds,
            exit_logic=random.choice(["and", "or"]),
            position_size_factor=random.uniform(0.5, 2.0),
            stop_loss=random.uniform(0.01, 0.05),
            take_profit=random.uniform(0.02, 0.10),
            strategy_id=f"gen0_{random.randint(1000, 9999)}",
        )

    def evolve(
        self, features: NDArray, prices: NDArray, n_generations: int | None = None
    ) -> StrategyGenome:
        """
        Run genetic algorithm evolution.

        Args:
            features: Feature matrix (T x N)
            prices: Price series
            n_generations: Number of generations

        Returns:
            Best evolved strategy
        """
        if n_generations is None:
            n_generations = self.config.generations

        if not self._population:
            self.initialize_population()

        for gen in range(n_generations):
            self._generation = gen

            # Evaluate fitness
            self._evaluate_population(features, prices)

            # Sort by fitness
            self._population.sort(key=lambda g: g.fitness, reverse=True)

            # Update best
            if (
                self._best_genome is None
                or self._population[0].fitness > self._best_genome.fitness
            ):
                self._best_genome = copy.deepcopy(self._population[0])

            # Selection and reproduction
            new_population = []

            # Elitism
            n_elite = int(self.config.elitism_ratio * self.config.population_size)
            new_population.extend(
                [copy.deepcopy(g) for g in self._population[:n_elite]]
            )

            # Crossover and mutation
            while len(new_population) < self.config.population_size:
                parent1 = self._select_parent()
                parent2 = self._select_parent()

                if random.random() < self.config.crossover_rate:
                    child = self._crossover(parent1, parent2)
                else:
                    child = copy.deepcopy(parent1)

                if random.random() < self.config.mutation_rate:
                    child = self._mutate(child)

                child.generation = gen + 1
                child.strategy_id = f"gen{gen + 1}_{random.randint(1000, 9999)}"
                new_population.append(child)

            self._population = new_population

        return self._best_genome if self._best_genome else self._population[0]

    def _evaluate_population(self, features: NDArray, prices: NDArray) -> None:
        """Evaluate fitness of all genomes."""
        for genome in self._population:
            genome.fitness = self._calculate_fitness(genome, features, prices)

    def _calculate_fitness(
        self, genome: StrategyGenome, features: NDArray, prices: NDArray
    ) -> float:
        """Calculate fitness score for a genome."""
        try:
            # Generate signals
            signals = self._generate_signals(genome, features)

            # Simulate trading
            returns = self._simulate_trading(genome, signals, prices)

            if len(returns) == 0:
                return -np.inf

            # Calculate fitness metric
            if self.config.fitness_metric == "sharpe":
                mean_ret = np.mean(returns) * 252
                std_ret = np.std(returns) * np.sqrt(252)
                return mean_ret / std_ret if std_ret > 0 else 0

            elif self.config.fitness_metric == "sortino":
                mean_ret = np.mean(returns) * 252
                neg_returns = returns[returns < 0]
                downside_std = (
                    np.std(neg_returns) * np.sqrt(252) if len(neg_returns) > 0 else 0.01
                )
                return mean_ret / downside_std

            elif self.config.fitness_metric == "profit_factor":
                gross_profit = np.sum(returns[returns > 0])
                gross_loss = np.abs(np.sum(returns[returns < 0]))
                return gross_profit / gross_loss if gross_loss > 0 else 0

            else:  # Total return
                return float(np.sum(returns))

        except Exception:
            return -np.inf

    def _generate_signals(self, genome: StrategyGenome, features: NDArray) -> NDArray:
        """Generate trading signals from genome."""
        n = features.shape[0]
        signals = np.zeros(n)

        # Get feature indices
        entry_indices = [
            self.feature_names.index(f)
            for f in genome.entry_features
            if f in self.feature_names
        ]
        exit_indices = [
            self.feature_names.index(f)
            for f in genome.exit_features
            if f in self.feature_names
        ]

        for i in range(n):
            # Entry conditions
            entry_signals = []
            for idx, fname in zip(entry_indices, genome.entry_features, strict=False):
                val = features[i, idx]
                thresh = genome.entry_thresholds.get(fname, (-1, 1))
                entry_signals.append(thresh[0] <= val <= thresh[1])

            # Exit conditions
            exit_signals = []
            for idx, fname in zip(exit_indices, genome.exit_features, strict=False):
                val = features[i, idx]
                thresh = genome.exit_thresholds.get(fname, (-1, 1))
                exit_signals.append(thresh[0] <= val <= thresh[1])

            # Combine signals
            if genome.entry_logic == "and":
                entry = all(entry_signals) if entry_signals else False
            else:
                entry = any(entry_signals) if entry_signals else False

            if genome.exit_logic == "and":
                exit_sig = all(exit_signals) if exit_signals else False
            else:
                exit_sig = any(exit_signals) if exit_signals else False

            if entry:
                signals[i] = 1
            elif exit_sig:
                signals[i] = -1

        return signals

    def _simulate_trading(
        self, genome: StrategyGenome, signals: NDArray, prices: NDArray
    ) -> NDArray:
        """Simple trading simulation."""
        returns = []
        position = 0
        entry_price = 0.0

        for i in range(1, len(prices)):
            if position == 0 and signals[i] == 1:
                # Enter long
                position = 1
                entry_price = prices[i]

            elif position == 1:
                # Check exit
                pnl_pct = (prices[i] - entry_price) / entry_price

                if (
                    signals[i] == -1
                    or pnl_pct <= -genome.stop_loss
                    or pnl_pct >= genome.take_profit
                ):
                    returns.append(pnl_pct * genome.position_size_factor)
                    position = 0

        return np.array(returns)

    def _select_parent(self) -> StrategyGenome:
        """Tournament selection."""
        tournament = random.sample(self._population, self.config.tournament_size)
        return max(tournament, key=lambda g: g.fitness)

    def _crossover(
        self, parent1: StrategyGenome, parent2: StrategyGenome
    ) -> StrategyGenome:
        """Uniform crossover."""
        child = copy.deepcopy(parent1)

        # Mix entry features
        all_entry = list(set(parent1.entry_features) | set(parent2.entry_features))
        child.entry_features = random.sample(
            all_entry, min(len(all_entry), random.randint(1, 5))
        )

        # Mix thresholds
        child.entry_thresholds = {}
        for f in child.entry_features:
            if f in parent1.entry_thresholds and f in parent2.entry_thresholds:
                t1 = parent1.entry_thresholds[f]
                t2 = parent2.entry_thresholds[f]
                child.entry_thresholds[f] = ((t1[0] + t2[0]) / 2, (t1[1] + t2[1]) / 2)
            elif f in parent1.entry_thresholds:
                child.entry_thresholds[f] = parent1.entry_thresholds[f]
            elif f in parent2.entry_thresholds:
                child.entry_thresholds[f] = parent2.entry_thresholds[f]
            else:
                child.entry_thresholds[f] = (-1, 1)

        # Mix parameters
        if random.random() < 0.5:
            child.stop_loss = parent2.stop_loss
        if random.random() < 0.5:
            child.take_profit = parent2.take_profit
        if random.random() < 0.5:
            child.position_size_factor = parent2.position_size_factor

        return child

    def _mutate(self, genome: StrategyGenome) -> StrategyGenome:
        """Mutate a genome."""
        genome = copy.deepcopy(genome)

        # Mutate thresholds
        for f in genome.entry_thresholds:
            if random.random() < 0.3:
                old = genome.entry_thresholds[f]
                genome.entry_thresholds[f] = (
                    old[0] + random.gauss(0, 0.2),
                    old[1] + random.gauss(0, 0.2),
                )

        # Mutate parameters
        if random.random() < 0.2:
            genome.stop_loss *= random.uniform(0.8, 1.2)
            genome.stop_loss = max(0.005, min(0.1, genome.stop_loss))

        if random.random() < 0.2:
            genome.take_profit *= random.uniform(0.8, 1.2)
            genome.take_profit = max(0.01, min(0.2, genome.take_profit))

        if random.random() < 0.2:
            genome.position_size_factor *= random.uniform(0.9, 1.1)
            genome.position_size_factor = max(
                0.5, min(2.0, genome.position_size_factor)
            )

        # Mutate logic
        if random.random() < 0.1:
            genome.entry_logic = "or" if genome.entry_logic == "and" else "and"

        return genome


# ============================================================================
# SIGNAL COMBINER
# ============================================================================


class SignalCombiner:
    """
    Combine multiple signal sources into unified trading signals.
    """

    def __init__(self, combination_method: str = "weighted_average"):
        self.combination_method = combination_method
        self._signal_sources: dict[
            str, tuple[NDArray, float]
        ] = {}  # name -> (signals, weight)

    def add_signal_source(
        self, name: str, signals: NDArray, weight: float = 1.0
    ) -> None:
        """Add a signal source."""
        self._signal_sources[name] = (signals, weight)

    def combine(self) -> NDArray:
        """Combine all signal sources."""
        if not self._signal_sources:
            return np.array([])

        # Get signal length
        first_signals = next(iter(self._signal_sources.values()))[0]
        n = len(first_signals)

        if self.combination_method == "weighted_average":
            combined = np.zeros(n)
            total_weight = 0.0

            for signals, weight in self._signal_sources.values():
                combined += signals[:n] * weight
                total_weight += weight

            return combined / total_weight if total_weight > 0 else combined

        elif self.combination_method == "voting":
            # Majority voting
            votes = np.zeros(n)
            for signals, _ in self._signal_sources.values():
                votes += np.sign(signals[:n])
            return np.sign(votes)

        elif self.combination_method == "unanimous":
            # All must agree
            combined = np.ones(n)
            for signals, _ in self._signal_sources.values():
                combined *= np.sign(signals[:n])
            return combined

        return np.zeros(n)


# ============================================================================
# WALK-FORWARD VALIDATOR
# ============================================================================


class WalkForwardValidator:
    """
    Walk-forward analysis for strategy validation.

    Prevents overfitting by testing on unseen data.
    """

    def __init__(self, config: AutoMLConfig | None = None):
        self.config = config or AutoMLConfig()

    def validate(
        self,
        strategy_func: Callable[[NDArray, NDArray], NDArray],
        features: NDArray,
        prices: NDArray,
    ) -> list[ValidationResult]:
        """
        Run walk-forward validation.

        Args:
            strategy_func: Function that takes (features, prices) and returns signals
            features: Feature matrix
            prices: Price series

        Returns:
            List of validation results for each window
        """
        n = len(prices)
        window_size = n // self.config.walk_forward_windows
        results = []

        for i in range(self.config.walk_forward_windows):
            start = i * window_size
            end = min((i + 1) * window_size, n)

            # Split into train/val/test
            train_end = start + int(window_size * self.config.train_ratio)
            val_end = train_end + int(window_size * self.config.val_ratio)

            train_features = features[start:train_end]
            train_prices = prices[start:train_end]

            val_features = features[train_end:val_end]
            val_prices = prices[train_end:val_end]

            test_features = features[val_end:end]
            test_prices = prices[val_end:end]

            # Generate signals for each period
            try:
                train_signals = strategy_func(train_features, train_prices)
                val_signals = strategy_func(val_features, val_prices)
                test_signals = strategy_func(test_features, test_prices)

                # Calculate metrics
                train_metrics = self._calculate_metrics(train_signals, train_prices)
                val_metrics = self._calculate_metrics(val_signals, val_prices)
                test_metrics = self._calculate_metrics(test_signals, test_prices)

                # Check for overfitting
                is_overfit = (
                    train_metrics["sharpe"] > val_metrics["sharpe"] * 1.5
                    or train_metrics["sharpe"] > test_metrics["sharpe"] * 1.5
                )

                # Robustness score
                robustness = min(
                    val_metrics["sharpe"] / max(train_metrics["sharpe"], 0.01),
                    test_metrics["sharpe"] / max(val_metrics["sharpe"], 0.01),
                )

                results.append(
                    ValidationResult(
                        train_sharpe=train_metrics["sharpe"],
                        val_sharpe=val_metrics["sharpe"],
                        test_sharpe=test_metrics["sharpe"],
                        train_return=train_metrics["total_return"],
                        val_return=val_metrics["total_return"],
                        test_return=test_metrics["total_return"],
                        max_drawdown=test_metrics["max_drawdown"],
                        profit_factor=test_metrics["profit_factor"],
                        win_rate=test_metrics["win_rate"],
                        total_trades=test_metrics["total_trades"],
                        is_overfit=is_overfit,
                        robustness_score=robustness,
                    )
                )

            except Exception:
                continue

        return results

    def _calculate_metrics(self, signals: NDArray, prices: NDArray) -> dict[str, float]:
        """Calculate trading metrics from signals."""
        # Simple position tracking
        returns = []
        position = 0
        entry_price = 0.0
        winning_trades = 0
        total_trades = 0

        for i in range(1, len(prices)):
            if position == 0 and signals[i] > 0:
                position = 1
                entry_price = prices[i]

            elif position == 1 and signals[i] < 0:
                pnl = (prices[i] - entry_price) / entry_price
                returns.append(pnl)
                total_trades += 1
                if pnl > 0:
                    winning_trades += 1
                position = 0

        if not returns:
            return {
                "sharpe": 0,
                "total_return": 0,
                "max_drawdown": 0,
                "profit_factor": 0,
                "win_rate": 0,
                "total_trades": 0,
            }

        returns_arr = np.array(returns)

        # Sharpe ratio
        sharpe = (
            (np.mean(returns_arr) * 252) / (np.std(returns_arr) * np.sqrt(252))
            if np.std(returns_arr) > 0
            else 0
        )

        # Total return
        total_return = float(np.sum(returns_arr))

        # Max drawdown
        cum_returns = np.cumprod(1 + returns_arr)
        peak = np.maximum.accumulate(cum_returns)
        drawdowns = (peak - cum_returns) / peak
        max_dd = float(np.max(drawdowns))

        # Profit factor
        gross_profit = float(np.sum(returns_arr[returns_arr > 0]))
        gross_loss = float(np.abs(np.sum(returns_arr[returns_arr < 0])))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Win rate
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        return {
            "sharpe": sharpe,
            "total_return": total_return,
            "max_drawdown": max_dd,
            "profit_factor": profit_factor,
            "win_rate": win_rate,
            "total_trades": total_trades,
        }


# ============================================================================
# AUTOML PIPELINE
# ============================================================================


class AutoMLPipeline:
    """
    Complete AutoML pipeline for strategy development.

    Combines feature engineering, model selection, and strategy evolution.
    """

    def __init__(self, config: AutoMLConfig | None = None):
        self.config = config or AutoMLConfig()
        self.feature_engineer = FeatureEngineering(config)
        self.model_selector = ModelSelector(config)
        self.validator = WalkForwardValidator(config)

        self._feature_set: FeatureSet | None = None
        self._best_model: BaseModel | None = None
        self._best_strategy: StrategyGenome | None = None

    def fit(
        self,
        open_prices: NDArray,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        volume: NDArray,
        target: NDArray | None = None,
    ) -> "AutoMLPipeline":
        """
        Fit the AutoML pipeline.

        Args:
            open_prices, high, low, close, volume: OHLCV data
            target: Optional target for supervised learning
        """
        # Generate features
        if target is None:
            # Use future returns as target
            target = np.zeros(len(close))
            target[:-1] = (close[1:] - close[:-1]) / close[:-1]

        self._feature_set = self.feature_engineer.generate_features(
            open_prices, high, low, close, volume, target
        )

        if self._feature_set.feature_matrix is None:
            raise ValueError("No features generated")

        # Remove NaN rows
        mask = ~np.any(np.isnan(self._feature_set.feature_matrix), axis=1)
        features = self._feature_set.feature_matrix[mask]
        target_clean = target[mask]

        # Split data
        n = len(features)
        train_end = int(n * self.config.train_ratio)
        val_end = int(n * (self.config.train_ratio + self.config.val_ratio))

        X_train = features[:train_end]
        y_train = target_clean[:train_end]
        X_val = features[train_end:val_end]
        y_val = target_clean[train_end:val_end]

        # Select model
        self._best_model = self.model_selector.select_model(
            X_train, y_train, X_val, y_val
        )

        # Evolve strategy
        feature_names = [f.name for f in self._feature_set.features]
        evolver = StrategyEvolver(self.config, feature_names)
        self._best_strategy = evolver.evolve(features, close[mask])

        return self

    def predict(self, features: NDArray) -> NDArray:
        """Generate trading signals."""
        if self._best_model is None:
            raise ValueError("Pipeline not fitted")

        # Model predictions
        raw_predictions = self._best_model.predict(features)

        # Convert to signals (-1, 0, 1)
        signals = np.sign(raw_predictions)

        return signals

    def get_best_strategy(self) -> StrategyGenome | None:
        """Get the best evolved strategy."""
        return self._best_strategy

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance scores."""
        if self._feature_set:
            return self._feature_set.feature_importance
        return {}


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "AutoMLConfig",
    # Pipeline
    "AutoMLPipeline",
    # Model selection
    "BaseModel",
    "CrossoverType",
    "DecisionTreeModel",
    "EnsembleModel",
    # Data structures
    "Feature",
    # Feature engineering
    "FeatureEngineering",
    "FeatureSet",
    # Enums
    "FeatureType",
    "LinearModel",
    "ModelSelector",
    "ModelType",
    "SelectionType",
    # Signal combination
    "SignalCombiner",
    # Genetic algorithm
    "StrategyEvolver",
    "StrategyGenome",
    "ValidationResult",
    # Validation
    "WalkForwardValidator",
]
