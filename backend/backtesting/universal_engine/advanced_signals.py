"""
Advanced Signals Module for Universal Math Engine v2.3.

This module provides ML-based signal generation:
1. FeatureEngine - Advanced feature engineering
2. SignalClassifier - ML-based signal classification
3. EnsemblePredictor - Multi-model ensemble predictions
4. RegimeDetector - Market regime detection
5. AdaptiveSignalGenerator - Self-tuning signal generation

Author: Universal Math Engine Team
Version: 2.3.0
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 1. FEATURE ENGINEERING
# =============================================================================


class FeatureCategory(Enum):
    """Categories of features."""

    PRICE = "price"
    VOLUME = "volume"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    TREND = "trend"
    PATTERN = "pattern"
    MICROSTRUCTURE = "microstructure"
    SENTIMENT = "sentiment"


@dataclass
class FeatureConfig:
    """Configuration for feature generation."""

    # Lookback periods
    short_period: int = 5
    medium_period: int = 20
    long_period: int = 50

    # Feature categories to include
    categories: list[FeatureCategory] = field(
        default_factory=lambda: list(FeatureCategory)
    )

    # Normalization
    normalize: bool = True
    normalization_window: int = 100

    # Missing value handling
    fill_method: str = "ffill"  # ffill, bfill, mean, zero


class FeatureEngine:
    """
    Advanced feature engineering for ML signal generation.

    Features:
    - Price-based features (returns, log returns, normalized prices)
    - Volume features (relative volume, OBV, VWAP)
    - Momentum features (RSI, MACD, ROC, Stochastic)
    - Volatility features (ATR, Bollinger bands, Parkinson)
    - Trend features (ADX, Aroon, Linear regression)
    - Pattern features (candlestick patterns, support/resistance)
    """

    def __init__(self, config: FeatureConfig | None = None):
        """Initialize feature engine."""
        self.config = config or FeatureConfig()

    def generate_features(
        self,
        ohlcv: dict[str, NDArray[np.float64]],
    ) -> dict[str, NDArray[np.float64]]:
        """
        Generate all features from OHLCV data.

        Args:
            ohlcv: Dictionary with 'open', 'high', 'low', 'close', 'volume'

        Returns:
            Dictionary of feature arrays
        """
        features = {}

        open_arr = ohlcv["open"]
        high = ohlcv["high"]
        low = ohlcv["low"]
        close = ohlcv["close"]
        volume = ohlcv["volume"]

        # Price features
        if FeatureCategory.PRICE in self.config.categories:
            features.update(self._price_features(open_arr, high, low, close))

        # Volume features
        if FeatureCategory.VOLUME in self.config.categories:
            features.update(self._volume_features(close, volume))

        # Momentum features
        if FeatureCategory.MOMENTUM in self.config.categories:
            features.update(self._momentum_features(high, low, close))

        # Volatility features
        if FeatureCategory.VOLATILITY in self.config.categories:
            features.update(self._volatility_features(high, low, close))

        # Trend features
        if FeatureCategory.TREND in self.config.categories:
            features.update(self._trend_features(high, low, close))

        # Pattern features
        if FeatureCategory.PATTERN in self.config.categories:
            features.update(self._pattern_features(open_arr, high, low, close))

        # Normalize if configured
        if self.config.normalize:
            features = self._normalize_features(features)

        return features

    def _price_features(
        self,
        open_arr: NDArray,
        high: NDArray,
        low: NDArray,
        close: NDArray,
    ) -> dict[str, NDArray]:
        """Generate price-based features."""
        n = len(close)
        features = {}

        # Returns
        features["return_1"] = np.concatenate([[0], np.diff(close) / close[:-1]])
        features["return_5"] = np.concatenate(
            [np.zeros(5), (close[5:] - close[:-5]) / close[:-5]]
        )
        features["return_20"] = np.concatenate(
            [np.zeros(20), (close[20:] - close[:-20]) / close[:-20]]
        )

        # Log returns
        features["log_return"] = np.concatenate([[0], np.diff(np.log(close + 1e-10))])

        # Price position in range
        range_hl = high - low
        range_hl = np.where(range_hl == 0, 1, range_hl)
        features["price_position"] = (close - low) / range_hl

        # Gap
        features["gap"] = np.concatenate(
            [[0], (open_arr[1:] - close[:-1]) / close[:-1]]
        )

        # Body ratio
        body = np.abs(close - open_arr)
        features["body_ratio"] = body / range_hl

        # Upper/lower shadow
        features["upper_shadow"] = (high - np.maximum(close, open_arr)) / range_hl
        features["lower_shadow"] = (np.minimum(close, open_arr) - low) / range_hl

        return features

    def _volume_features(
        self,
        close: NDArray,
        volume: NDArray,
    ) -> dict[str, NDArray]:
        """Generate volume-based features."""
        features = {}

        # Relative volume
        vol_sma = self._sma(volume, self.config.medium_period)
        vol_sma = np.where(vol_sma == 0, 1, vol_sma)
        features["relative_volume"] = volume / vol_sma

        # Volume change
        features["volume_change"] = np.concatenate(
            [[0], np.diff(volume) / (volume[:-1] + 1e-10)]
        )

        # On-balance volume
        obv = np.zeros(len(close))
        price_change = np.concatenate([[0], np.diff(close)])
        for i in range(1, len(close)):
            if price_change[i] > 0:
                obv[i] = obv[i - 1] + volume[i]
            elif price_change[i] < 0:
                obv[i] = obv[i - 1] - volume[i]
            else:
                obv[i] = obv[i - 1]
        features["obv_normalized"] = obv / (np.abs(obv).max() + 1e-10)

        # VWAP ratio
        vwap = np.cumsum(close * volume) / (np.cumsum(volume) + 1e-10)
        features["vwap_ratio"] = close / (vwap + 1e-10)

        # Volume-price trend
        features["vpt"] = np.cumsum(
            volume * np.concatenate([[0], np.diff(close) / (close[:-1] + 1e-10)])
        )

        return features

    def _momentum_features(
        self,
        high: NDArray,
        low: NDArray,
        close: NDArray,
    ) -> dict[str, NDArray]:
        """Generate momentum-based features."""
        features = {}

        # RSI
        features["rsi_14"] = self._rsi(close, 14)
        features["rsi_7"] = self._rsi(close, 7)
        features["rsi_21"] = self._rsi(close, 21)

        # Stochastic
        stoch_k, stoch_d = self._stochastic(high, low, close, 14, 3)
        features["stoch_k"] = stoch_k
        features["stoch_d"] = stoch_d

        # MACD
        macd, signal, hist = self._macd(close)
        features["macd"] = macd / (close + 1e-10)  # Normalized
        features["macd_signal"] = signal / (close + 1e-10)
        features["macd_hist"] = hist / (close + 1e-10)

        # Rate of change
        features["roc_5"] = self._roc(close, 5)
        features["roc_10"] = self._roc(close, 10)
        features["roc_20"] = self._roc(close, 20)

        # Williams %R
        features["williams_r"] = self._williams_r(high, low, close, 14)

        # CCI
        features["cci"] = self._cci(high, low, close, 20)

        return features

    def _volatility_features(
        self,
        high: NDArray,
        low: NDArray,
        close: NDArray,
    ) -> dict[str, NDArray]:
        """Generate volatility-based features."""
        features = {}

        # ATR
        atr = self._atr(high, low, close, 14)
        features["atr_14"] = atr / (close + 1e-10)

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self._bollinger_bands(close, 20, 2)
        bb_width = (bb_upper - bb_lower) / (bb_middle + 1e-10)
        features["bb_width"] = bb_width
        features["bb_position"] = (close - bb_lower) / (bb_upper - bb_lower + 1e-10)

        # Historical volatility
        returns = np.concatenate([[0], np.diff(np.log(close + 1e-10))])
        features["hvol_10"] = self._rolling_std(returns, 10)
        features["hvol_20"] = self._rolling_std(returns, 20)

        # Parkinson volatility
        features["parkinson_vol"] = self._parkinson_volatility(high, low, 20)

        # Range volatility
        range_pct = (high - low) / (close + 1e-10)
        features["range_vol"] = self._sma(range_pct, 14)

        return features

    def _trend_features(
        self,
        high: NDArray,
        low: NDArray,
        close: NDArray,
    ) -> dict[str, NDArray]:
        """Generate trend-based features."""
        features = {}

        # Moving averages
        sma_5 = self._sma(close, 5)
        sma_20 = self._sma(close, 20)
        sma_50 = self._sma(close, 50)

        features["sma_5_ratio"] = close / (sma_5 + 1e-10)
        features["sma_20_ratio"] = close / (sma_20 + 1e-10)
        features["sma_50_ratio"] = close / (sma_50 + 1e-10)

        # MA crossovers
        features["ma_cross_5_20"] = (sma_5 - sma_20) / (sma_20 + 1e-10)
        features["ma_cross_20_50"] = (sma_20 - sma_50) / (sma_50 + 1e-10)

        # ADX
        features["adx"] = self._adx(high, low, close, 14)

        # Aroon
        aroon_up, aroon_down = self._aroon(high, low, 25)
        features["aroon_up"] = aroon_up
        features["aroon_down"] = aroon_down
        features["aroon_osc"] = aroon_up - aroon_down

        # Linear regression slope
        features["lr_slope_20"] = self._linear_regression_slope(close, 20)

        return features

    def _pattern_features(
        self,
        open_arr: NDArray,
        high: NDArray,
        low: NDArray,
        close: NDArray,
    ) -> dict[str, NDArray]:
        """Generate pattern-based features."""
        n = len(close)
        features = {}

        # Doji
        body = np.abs(close - open_arr)
        range_hl = high - low
        features["is_doji"] = (body < 0.1 * range_hl).astype(float)

        # Hammer/Shooting star
        lower_shadow = np.minimum(open_arr, close) - low
        upper_shadow = high - np.maximum(open_arr, close)

        features["is_hammer"] = (
            (lower_shadow > 2 * body) & (upper_shadow < body)
        ).astype(float)
        features["is_shooting_star"] = (
            (upper_shadow > 2 * body) & (lower_shadow < body)
        ).astype(float)

        # Engulfing
        is_bullish_engulf = np.zeros(n)
        is_bearish_engulf = np.zeros(n)
        for i in range(1, n):
            # Bullish engulfing
            if (
                close[i - 1] < open_arr[i - 1]  # Previous bearish
                and close[i] > open_arr[i]  # Current bullish
                and open_arr[i] < close[i - 1]
                and close[i] > open_arr[i - 1]
            ):
                is_bullish_engulf[i] = 1.0
            # Bearish engulfing
            if (
                close[i - 1] > open_arr[i - 1]  # Previous bullish
                and close[i] < open_arr[i]  # Current bearish
                and open_arr[i] > close[i - 1]
                and close[i] < open_arr[i - 1]
            ):
                is_bearish_engulf[i] = 1.0

        features["is_bullish_engulf"] = is_bullish_engulf
        features["is_bearish_engulf"] = is_bearish_engulf

        # Higher high / Lower low
        features["higher_high"] = (high > np.roll(high, 1)).astype(float)
        features["lower_low"] = (low < np.roll(low, 1)).astype(float)

        return features

    def _normalize_features(
        self,
        features: dict[str, NDArray],
    ) -> dict[str, NDArray]:
        """Normalize features using rolling z-score."""
        window = self.config.normalization_window
        normalized = {}

        for name, values in features.items():
            if name.startswith("is_"):
                # Don't normalize binary features
                normalized[name] = values
            else:
                mean = self._sma(values, window)
                std = self._rolling_std(values, window)
                std = np.where(std == 0, 1, std)
                normalized[name] = (values - mean) / std
                # Clip to prevent extreme values
                normalized[name] = np.clip(normalized[name], -5, 5)

        return normalized

    # Helper methods for indicators
    def _sma(self, data: NDArray, period: int) -> NDArray:
        """Simple moving average."""
        return np.convolve(data, np.ones(period) / period, mode="same")

    def _ema(self, data: NDArray, period: int) -> NDArray:
        """Exponential moving average."""
        alpha = 2 / (period + 1)
        result = np.zeros(len(data))
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    def _rolling_std(self, data: NDArray, period: int) -> NDArray:
        """Rolling standard deviation."""
        result = np.zeros(len(data))
        for i in range(period - 1, len(data)):
            result[i] = np.std(data[i - period + 1 : i + 1])
        return result

    def _rsi(self, close: NDArray, period: int) -> NDArray:
        """Relative Strength Index."""
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)

        avg_gain = self._ema(np.concatenate([[0], gain]), period)
        avg_loss = self._ema(np.concatenate([[0], loss]), period)

        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def _stochastic(
        self,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        k_period: int,
        d_period: int,
    ) -> tuple[NDArray, NDArray]:
        """Stochastic oscillator."""
        n = len(close)
        stoch_k = np.zeros(n)

        for i in range(k_period - 1, n):
            h_high = high[i - k_period + 1 : i + 1].max()
            l_low = low[i - k_period + 1 : i + 1].min()
            denom = h_high - l_low
            if denom > 0:
                stoch_k[i] = 100 * (close[i] - l_low) / denom

        stoch_d = self._sma(stoch_k, d_period)
        return stoch_k, stoch_d

    def _macd(
        self,
        close: NDArray,
        fast: int = 12,
        slow: int = 26,
        signal_period: int = 9,
    ) -> tuple[NDArray, NDArray, NDArray]:
        """MACD indicator."""
        fast_ema = self._ema(close, fast)
        slow_ema = self._ema(close, slow)
        macd_line = fast_ema - slow_ema
        signal_line = self._ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def _roc(self, close: NDArray, period: int) -> NDArray:
        """Rate of Change."""
        result = np.zeros(len(close))
        for i in range(period, len(close)):
            if close[i - period] != 0:
                result[i] = (close[i] - close[i - period]) / close[i - period]
        return result

    def _williams_r(
        self,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        period: int,
    ) -> NDArray:
        """Williams %R."""
        n = len(close)
        result = np.zeros(n)

        for i in range(period - 1, n):
            h_high = high[i - period + 1 : i + 1].max()
            l_low = low[i - period + 1 : i + 1].min()
            denom = h_high - l_low
            if denom > 0:
                result[i] = -100 * (h_high - close[i]) / denom

        return result

    def _cci(
        self,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        period: int,
    ) -> NDArray:
        """Commodity Channel Index."""
        tp = (high + low + close) / 3
        sma_tp = self._sma(tp, period)
        mad = np.zeros(len(close))

        for i in range(period - 1, len(close)):
            mad[i] = np.mean(np.abs(tp[i - period + 1 : i + 1] - sma_tp[i]))

        mad = np.where(mad == 0, 1, mad)
        return (tp - sma_tp) / (0.015 * mad)

    def _atr(
        self,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        period: int,
    ) -> NDArray:
        """Average True Range."""
        tr = np.zeros(len(close))
        tr[0] = high[0] - low[0]

        for i in range(1, len(close)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )

        return self._ema(tr, period)

    def _bollinger_bands(
        self,
        close: NDArray,
        period: int,
        std_dev: float,
    ) -> tuple[NDArray, NDArray, NDArray]:
        """Bollinger Bands."""
        middle = self._sma(close, period)
        std = self._rolling_std(close, period)
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        return upper, middle, lower

    def _parkinson_volatility(
        self,
        high: NDArray,
        low: NDArray,
        period: int,
    ) -> NDArray:
        """Parkinson volatility estimator."""
        log_hl = np.log(high / (low + 1e-10))
        factor = 1 / (4 * np.log(2))
        result = np.zeros(len(high))

        for i in range(period - 1, len(high)):
            result[i] = np.sqrt(factor * np.mean(log_hl[i - period + 1 : i + 1] ** 2))

        return result

    def _adx(
        self,
        high: NDArray,
        low: NDArray,
        close: NDArray,
        period: int,
    ) -> NDArray:
        """Average Directional Index."""
        n = len(close)
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)

        for i in range(1, n):
            up = high[i] - high[i - 1]
            down = low[i - 1] - low[i]

            if up > down and up > 0:
                plus_dm[i] = up
            if down > up and down > 0:
                minus_dm[i] = down

        atr = self._atr(high, low, close, period)
        atr = np.where(atr == 0, 1, atr)

        plus_di = 100 * self._ema(plus_dm, period) / atr
        minus_di = 100 * self._ema(minus_dm, period) / atr

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = self._ema(dx, period)

        return adx

    def _aroon(
        self,
        high: NDArray,
        low: NDArray,
        period: int,
    ) -> tuple[NDArray, NDArray]:
        """Aroon indicator."""
        n = len(high)
        aroon_up = np.zeros(n)
        aroon_down = np.zeros(n)

        for i in range(period - 1, n):
            window_high = high[i - period + 1 : i + 1]
            window_low = low[i - period + 1 : i + 1]

            high_idx = np.argmax(window_high)
            low_idx = np.argmin(window_low)

            aroon_up[i] = 100 * (period - (period - 1 - high_idx)) / period
            aroon_down[i] = 100 * (period - (period - 1 - low_idx)) / period

        return aroon_up, aroon_down

    def _linear_regression_slope(
        self,
        close: NDArray,
        period: int,
    ) -> NDArray:
        """Linear regression slope."""
        result = np.zeros(len(close))
        x = np.arange(period)

        for i in range(period - 1, len(close)):
            y = close[i - period + 1 : i + 1]
            slope = np.polyfit(x, y, 1)[0]
            result[i] = slope / (close[i] + 1e-10)

        return result


# =============================================================================
# 2. SIGNAL CLASSIFIER
# =============================================================================


class SignalType(Enum):
    """Types of trading signals."""

    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class SignalPrediction:
    """ML signal prediction."""

    timestamp: int
    signal: SignalType
    confidence: float  # 0-1
    probabilities: dict[SignalType, float]
    features_used: list[str]


@dataclass
class ClassifierConfig:
    """Configuration for signal classifier."""

    # Model parameters
    hidden_layers: list[int] = field(default_factory=lambda: [64, 32])
    dropout_rate: float = 0.3
    learning_rate: float = 0.001

    # Training parameters
    batch_size: int = 32
    epochs: int = 100
    validation_split: float = 0.2

    # Classification thresholds
    buy_threshold: float = 0.6
    sell_threshold: float = 0.4
    strong_threshold: float = 0.8


class SignalClassifier(ABC):
    """
    Abstract base class for signal classifiers.

    Features:
    - Multi-class signal classification
    - Confidence scoring
    - Feature importance
    """

    def __init__(self, config: ClassifierConfig | None = None):
        """Initialize classifier."""
        self.config = config or ClassifierConfig()
        self._is_trained = False
        self._feature_names: list[str] = []

    @abstractmethod
    def train(
        self,
        features: NDArray[np.float64],
        labels: NDArray[np.int32],
    ) -> dict[str, float]:
        """Train the classifier."""
        pass

    @abstractmethod
    def predict(
        self,
        features: NDArray[np.float64],
    ) -> list[SignalPrediction]:
        """Generate predictions."""
        pass

    @abstractmethod
    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance scores."""
        pass


class SimpleMLPClassifier(SignalClassifier):
    """
    Simple MLP-based signal classifier.

    Uses NumPy-only implementation for portability.
    """

    def __init__(self, config: ClassifierConfig | None = None):
        """Initialize MLP classifier."""
        super().__init__(config)
        self._weights: list[NDArray] = []
        self._biases: list[NDArray] = []
        self._feature_importance: dict[str, float] = {}

    def _init_weights(self, input_size: int, output_size: int = 5) -> None:
        """Initialize network weights."""
        layers = [input_size] + self.config.hidden_layers + [output_size]

        self._weights = []
        self._biases = []

        for i in range(len(layers) - 1):
            # Xavier initialization
            scale = np.sqrt(2.0 / (layers[i] + layers[i + 1]))
            w = np.random.randn(layers[i], layers[i + 1]) * scale
            b = np.zeros(layers[i + 1])

            self._weights.append(w)
            self._biases.append(b)

    def _forward(
        self,
        x: NDArray,
        training: bool = False,
    ) -> NDArray:
        """Forward pass through the network."""
        current = x

        for i, (w, b) in enumerate(zip(self._weights, self._biases)):
            current = current @ w + b

            if i < len(self._weights) - 1:
                # ReLU activation for hidden layers
                current = np.maximum(0, current)

                if training and self.config.dropout_rate > 0:
                    mask = np.random.rand(*current.shape) > self.config.dropout_rate
                    current *= mask / (1 - self.config.dropout_rate)

        # Softmax for output
        exp_x = np.exp(current - current.max(axis=-1, keepdims=True))
        return exp_x / exp_x.sum(axis=-1, keepdims=True)

    def train(
        self,
        features: NDArray[np.float64],
        labels: NDArray[np.int32],
    ) -> dict[str, float]:
        """Train the classifier using mini-batch gradient descent."""
        n_samples = features.shape[0]
        n_features = features.shape[1]

        # Initialize weights
        self._init_weights(n_features)

        # Convert labels to one-hot
        n_classes = 5
        one_hot = np.zeros((n_samples, n_classes))
        one_hot[np.arange(n_samples), labels + 2] = 1  # Shift labels to 0-4

        # Training loop
        best_loss = float("inf")
        patience_counter = 0
        patience = 10

        for epoch in range(self.config.epochs):
            # Shuffle data
            indices = np.random.permutation(n_samples)
            features_shuffled = features[indices]
            labels_shuffled = one_hot[indices]

            epoch_loss = 0

            # Mini-batch training
            for i in range(0, n_samples, self.config.batch_size):
                batch_x = features_shuffled[i : i + self.config.batch_size]
                batch_y = labels_shuffled[i : i + self.config.batch_size]

                # Forward pass
                output = self._forward(batch_x, training=True)

                # Cross-entropy loss
                loss = -np.mean(np.sum(batch_y * np.log(output + 1e-10), axis=1))
                epoch_loss += loss

                # Backward pass (simplified gradient descent)
                error = output - batch_y

                for layer in range(len(self._weights) - 1, -1, -1):
                    if layer == len(self._weights) - 1:
                        grad_w = (
                            batch_x.T @ error
                            if layer == 0
                            else self._forward(batch_x, False).T @ error
                        )
                    else:
                        grad_w = batch_x.T @ error

                    grad_w /= len(batch_x)

                    self._weights[layer] -= self.config.learning_rate * grad_w
                    self._biases[layer] -= self.config.learning_rate * error.mean(
                        axis=0
                    )

            epoch_loss /= n_samples // self.config.batch_size

            # Early stopping
            if epoch_loss < best_loss:
                best_loss = epoch_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    break

        self._is_trained = True

        # Calculate feature importance using weight magnitudes
        if self._weights:
            importance = np.abs(self._weights[0]).sum(axis=1)
            importance /= importance.sum()
            self._feature_importance = {
                self._feature_names[i] if i < len(self._feature_names) else f"f_{i}": v
                for i, v in enumerate(importance)
            }

        return {"final_loss": best_loss, "epochs": epoch + 1}

    def predict(
        self,
        features: NDArray[np.float64],
    ) -> list[SignalPrediction]:
        """Generate predictions."""
        if not self._is_trained:
            raise RuntimeError("Classifier not trained")

        probs = self._forward(features)
        predictions = []

        signal_map = {
            0: SignalType.STRONG_SELL,
            1: SignalType.SELL,
            2: SignalType.NEUTRAL,
            3: SignalType.BUY,
            4: SignalType.STRONG_BUY,
        }

        for i, prob_row in enumerate(probs):
            class_idx = np.argmax(prob_row)
            confidence = prob_row[class_idx]

            predictions.append(
                SignalPrediction(
                    timestamp=i,
                    signal=signal_map[class_idx],
                    confidence=float(confidence),
                    probabilities={
                        signal_map[j]: float(p) for j, p in enumerate(prob_row)
                    },
                    features_used=self._feature_names,
                )
            )

        return predictions

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance scores."""
        return self._feature_importance


# =============================================================================
# 3. ENSEMBLE PREDICTOR
# =============================================================================


@dataclass
class EnsembleConfig:
    """Configuration for ensemble predictor."""

    # Ensemble settings
    n_models: int = 5
    bagging_fraction: float = 0.8
    feature_fraction: float = 0.8

    # Aggregation method
    aggregation: str = "weighted_average"  # weighted_average, voting, stacking


class EnsemblePredictor:
    """
    Multi-model ensemble for robust signal prediction.

    Features:
    - Bagging (bootstrap aggregation)
    - Feature subsampling
    - Weighted averaging based on model confidence
    """

    def __init__(
        self,
        base_classifier: type = SimpleMLPClassifier,
        config: EnsembleConfig | None = None,
    ):
        """Initialize ensemble predictor."""
        self.base_classifier = base_classifier
        self.config = config or EnsembleConfig()
        self._models: list[SignalClassifier] = []
        self._model_weights: list[float] = []
        self._feature_subsets: list[list[int]] = []

    def train(
        self,
        features: NDArray[np.float64],
        labels: NDArray[np.int32],
    ) -> dict[str, Any]:
        """Train ensemble models."""
        n_samples, n_features = features.shape
        n_subsample = int(n_samples * self.config.bagging_fraction)
        n_feat_subsample = int(n_features * self.config.feature_fraction)

        training_results = []

        for i in range(self.config.n_models):
            # Bootstrap sample
            sample_indices = np.random.choice(n_samples, n_subsample, replace=True)

            # Feature subsampling
            feature_indices = np.random.choice(
                n_features, n_feat_subsample, replace=False
            )
            feature_indices = sorted(feature_indices)

            # Train model
            model = self.base_classifier()
            subset_features = features[np.ix_(sample_indices, feature_indices)]
            subset_labels = labels[sample_indices]

            result = model.train(subset_features, subset_labels)
            training_results.append(result)

            self._models.append(model)
            self._feature_subsets.append(feature_indices)

        # Initialize equal weights
        self._model_weights = [1.0 / self.config.n_models] * self.config.n_models

        return {
            "n_models": self.config.n_models,
            "avg_loss": np.mean([r["final_loss"] for r in training_results]),
        }

    def predict(
        self,
        features: NDArray[np.float64],
    ) -> list[SignalPrediction]:
        """Generate ensemble predictions."""
        all_predictions: list[list[SignalPrediction]] = []

        # Get predictions from each model
        for model, feat_indices in zip(self._models, self._feature_subsets):
            subset_features = features[:, feat_indices]
            preds = model.predict(subset_features)
            all_predictions.append(preds)

        # Aggregate predictions
        ensemble_predictions = []

        for i in range(len(features)):
            # Collect predictions for this sample
            sample_preds = [preds[i] for preds in all_predictions]

            # Weighted average of probabilities
            avg_probs = {}
            for signal_type in SignalType:
                weighted_prob = sum(
                    p.probabilities.get(signal_type, 0) * w
                    for p, w in zip(sample_preds, self._model_weights)
                )
                avg_probs[signal_type] = weighted_prob

            # Get final signal
            best_signal = max(avg_probs, key=lambda k: avg_probs[k])
            confidence = avg_probs[best_signal]

            ensemble_predictions.append(
                SignalPrediction(
                    timestamp=i,
                    signal=best_signal,
                    confidence=confidence,
                    probabilities=avg_probs,
                    features_used=[],
                )
            )

        return ensemble_predictions


# =============================================================================
# 4. ADAPTIVE SIGNAL GENERATOR
# =============================================================================


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive signal generator."""

    # Adaptation settings
    retrain_interval: int = 1000  # Retrain every N bars
    min_training_samples: int = 500
    lookback_window: int = 5000

    # Performance tracking
    performance_window: int = 100
    min_accuracy: float = 0.55


class AdaptiveSignalGenerator:
    """
    Self-tuning signal generator that adapts to market conditions.

    Features:
    - Automatic retraining
    - Feature selection
    - Performance monitoring
    """

    def __init__(
        self,
        feature_engine: FeatureEngine,
        classifier: SignalClassifier,
        config: AdaptiveConfig | None = None,
    ):
        """Initialize adaptive signal generator."""
        self.feature_engine = feature_engine
        self.classifier = classifier
        self.config = config or AdaptiveConfig()

        self._sample_count = 0
        self._last_retrain = 0
        self._performance_history: list[bool] = []

    def generate_signal(
        self,
        ohlcv: dict[str, NDArray[np.float64]],
    ) -> SignalPrediction | None:
        """
        Generate signal for the latest bar.

        Args:
            ohlcv: OHLCV data dictionary

        Returns:
            Signal prediction or None if insufficient data
        """
        # Generate features
        features = self.feature_engine.generate_features(ohlcv)

        # Stack features into array
        feature_names = list(features.keys())
        feature_array = np.stack([features[name] for name in feature_names], axis=1)

        # Get latest features
        latest_features = feature_array[-1:].copy()

        # Check if we need to handle NaN
        if np.any(np.isnan(latest_features)):
            return None

        # Generate prediction
        predictions = self.classifier.predict(latest_features)

        if predictions:
            return predictions[0]

        return None

    def train_on_history(
        self,
        ohlcv: dict[str, NDArray[np.float64]],
        forward_returns: NDArray[np.float64],
    ) -> dict[str, Any]:
        """
        Train classifier on historical data.

        Args:
            ohlcv: OHLCV data
            forward_returns: Future returns for labeling

        Returns:
            Training results
        """
        # Generate features
        features = self.feature_engine.generate_features(ohlcv)
        feature_names = list(features.keys())
        feature_array = np.stack([features[name] for name in feature_names], axis=1)

        # Generate labels from forward returns
        labels = self._generate_labels(forward_returns)

        # Remove NaN rows
        valid_mask = ~np.any(np.isnan(feature_array), axis=1)
        valid_features = feature_array[valid_mask]
        valid_labels = labels[valid_mask]

        if len(valid_features) < self.config.min_training_samples:
            return {"error": "Insufficient training data"}

        # Store feature names in classifier
        self.classifier._feature_names = feature_names

        # Train
        result = self.classifier.train(valid_features, valid_labels)
        self._last_retrain = self._sample_count

        return result

    def _generate_labels(
        self,
        forward_returns: NDArray[np.float64],
    ) -> NDArray[np.int32]:
        """Generate labels from forward returns."""
        labels = np.zeros(len(forward_returns), dtype=np.int32)

        # Strong sell: < -1%
        labels[forward_returns < -0.01] = -2
        # Sell: -1% to -0.3%
        labels[(forward_returns >= -0.01) & (forward_returns < -0.003)] = -1
        # Neutral: -0.3% to 0.3%
        labels[(forward_returns >= -0.003) & (forward_returns <= 0.003)] = 0
        # Buy: 0.3% to 1%
        labels[(forward_returns > 0.003) & (forward_returns <= 0.01)] = 1
        # Strong buy: > 1%
        labels[forward_returns > 0.01] = 2

        return labels

    def update_performance(self, was_correct: bool) -> None:
        """Update performance tracking."""
        self._performance_history.append(was_correct)

        # Keep only recent history
        if len(self._performance_history) > self.config.performance_window:
            self._performance_history.pop(0)

    def get_accuracy(self) -> float:
        """Get recent prediction accuracy."""
        if not self._performance_history:
            return 0.5

        return sum(self._performance_history) / len(self._performance_history)

    def needs_retrain(self) -> bool:
        """Check if model needs retraining."""
        # Check interval
        if (self._sample_count - self._last_retrain) >= self.config.retrain_interval:
            return True

        # Check performance
        if (
            len(self._performance_history) >= self.config.performance_window
            and self.get_accuracy() < self.config.min_accuracy
        ):
            return True

        return False


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Feature Engineering
    "FeatureCategory",
    "FeatureConfig",
    "FeatureEngine",
    # Signal Classifier
    "SignalType",
    "SignalPrediction",
    "ClassifierConfig",
    "SignalClassifier",
    "SimpleMLPClassifier",
    # Ensemble
    "EnsembleConfig",
    "EnsemblePredictor",
    # Adaptive
    "AdaptiveConfig",
    "AdaptiveSignalGenerator",
]
