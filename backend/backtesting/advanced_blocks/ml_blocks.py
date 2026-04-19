"""
🧱 Machine Learning Blocks

ML-based blocks for Strategy Builder:
- LSTM Prediction
- ML Signal (Random Forest, XGBoost)
- Feature Engineering
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MLBlockResult:
    """ML block result"""

    signal: float  # -1 to 1
    confidence: float  # 0 to 1
    prediction: float | None = None
    features: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class LSTMPredictorBlock:
    """
    LSTM-based price prediction block.

    Предсказывает направление цены на основе LSTM сети.

    Parameters:
        lookback: Количество баров для анализа (default: 60)
        prediction_horizon: Горизонт предсказания (default: 5)
        threshold: Порог для сигнала (default: 0.5)

    Returns:
        signal: -1 (sell), 0 (hold), 1 (buy)
        confidence: Уверенность модели
        prediction: Предсказанная цена
    """

    def __init__(
        self,
        lookback: int = 60,
        prediction_horizon: int = 5,
        threshold: float = 0.5,
    ):
        self.lookback = lookback
        self.prediction_horizon = prediction_horizon
        self.threshold = threshold

        # Model (lazy loading)
        self._model = None
        self._is_trained = False

    def _create_features(self, data: pd.DataFrame) -> np.ndarray:
        """Создать признаки для LSTM"""
        # Price features
        features = []

        # Returns
        returns = data["close"].pct_change().fillna(0)
        features.append(returns.values[-self.lookback :])

        # Volatility
        volatility = returns.rolling(window=10).std().fillna(0)
        features.append(volatility.values[-self.lookback :])

        # Volume
        if "volume" in data.columns:
            volume_change = data["volume"].pct_change().fillna(0)
            features.append(volume_change.values[-self.lookback :])

        # Stack features
        feature_array = np.stack(features, axis=1)

        # Reshape for LSTM [samples, timesteps, features]
        return feature_array.reshape(1, self.lookback, -1)

    def predict(self, data: pd.DataFrame) -> MLBlockResult:
        """
        Сделать предсказание.

        Args:
            data: OHLCV данные

        Returns:
            MLBlockResult
        """
        if len(data) < self.lookback:
            return MLBlockResult(signal=0, confidence=0, metadata={"error": "Insufficient data"})

        # Create features
        self._create_features(data)

        # Mock prediction (in production, load trained model)
        # prediction = self._model.predict(X)

        # Mock prediction based on recent trend
        recent_returns = data["close"].pct_change().values[-10:]
        trend = np.mean(recent_returns)

        # Generate signal
        if trend > 0.001:
            signal = 1
            confidence = min(abs(trend) * 100, 1.0)
        elif trend < -0.001:
            signal = -1
            confidence = min(abs(trend) * 100, 1.0)
        else:
            signal = 0
            confidence = 0.5

        # Prediction
        current_price = data["close"].iloc[-1]
        prediction = current_price * (1 + trend * self.prediction_horizon)

        return MLBlockResult(
            signal=signal,
            confidence=confidence,
            prediction=prediction,
            features={"trend": trend},
            metadata={
                "lookback": self.lookback,
                "prediction_horizon": self.prediction_horizon,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": "lstm_predictor",
            "lookback": self.lookback,
            "prediction_horizon": self.prediction_horizon,
            "threshold": self.threshold,
        }


class MLSignalBlock:
    """
    ML-based signal block (Random Forest / XGBoost).

    Генерирует сигналы на основе ML модели.

    Parameters:
        model_type: Тип модели ('rf', 'xgb', 'lightgbm')
        n_estimators: Количество деревьев
        max_depth: Максимальная глубина

    Returns:
        signal: -1, 0, 1
        confidence: 0 to 1
        feature_importance: Важность признаков
    """

    def __init__(
        self,
        model_type: str = "rf",
        n_estimators: int = 100,
        max_depth: int = 5,
    ):
        self.model_type = model_type
        self.n_estimators = n_estimators
        self.max_depth = max_depth

        self._model = None
        self._feature_names: list[str] = []

    def _create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Создать признаки"""
        features = pd.DataFrame(index=data.index)

        # Technical indicators
        features["rsi"] = self._calculate_rsi(data["close"])
        features["macd"] = self._calculate_macd(data["close"])
        features["bb_upper"], features["bb_lower"] = self._calculate_bollinger(data["close"])
        features["atr"] = self._calculate_atr(data)

        # Price features
        features["returns"] = data["close"].pct_change()
        features["high_low_range"] = (data["high"] - data["low"]) / data["close"]

        # Volume features
        if "volume" in data.columns:
            features["volume_change"] = data["volume"].pct_change()

        # Lag features
        for lag in [1, 2, 3, 5]:
            features[f"returns_lag_{lag}"] = features["returns"].shift(lag)

        return features.fillna(0)

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, prices: pd.Series) -> pd.Series:
        """Calculate MACD"""
        ema12 = prices.ewm(span=12, adjust=False).mean()
        ema26 = prices.ewm(span=26, adjust=False).mean()
        return ema12 - ema26

    def _calculate_bollinger(self, prices: pd.Series, period: int = 20) -> tuple[pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + 2 * std
        lower = middle - 2 * std
        return upper, lower

    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ATR"""
        high_low = data["high"] - data["low"]
        high_close = (data["high"] - data["close"].shift()).abs()
        low_close = (data["low"] - data["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def predict(self, data: pd.DataFrame) -> MLBlockResult:
        """
        Сделать предсказание.

        Args:
            data: OHLCV данные

        Returns:
            MLBlockResult
        """
        # Create features
        features = self._create_features(data)

        # Get latest features for prediction
        _latest_features = features.iloc[-1:].values

        # Mock prediction (in production, use trained model)
        # prediction = self._model.predict(X)[0]
        # proba = self._model.predict_proba(X)[0]

        # Mock signal based on RSI
        rsi = features["rsi"].iloc[-1]

        if rsi < 30:
            signal = 1  # Oversold - buy
            confidence = (30 - rsi) / 30
        elif rsi > 70:
            signal = -1  # Overbought - sell
            confidence = (rsi - 70) / 30
        else:
            signal = 0
            confidence = 0.5

        # Feature importance (mock)
        feature_importance = {
            "rsi": 0.3,
            "macd": 0.25,
            "returns": 0.2,
            "volume_change": 0.15,
            "atr": 0.1,
        }

        return MLBlockResult(
            signal=signal,
            confidence=confidence,
            features=features.iloc[-1].to_dict(),
            metadata={
                "model_type": self.model_type,
                "feature_importance": feature_importance,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": "ml_signal",
            "model_type": self.model_type,
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
        }


class FeatureEngineeringBlock:
    """
    Feature engineering block.

    Создает признаки для ML моделей.

    Parameters:
        features: Список признаков для создания

    Returns:
        features: DataFrame с признаками
    """

    def __init__(self, features: list[str] | None = None):
        self.features = features or [
            "returns",
            "volatility",
            "rsi",
            "macd",
            "bollinger",
            "volume_change",
        ]

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Создать признаки.

        Args:
            data: OHLCV данные

        Returns:
            DataFrame с признаками
        """
        features_df = pd.DataFrame(index=data.index)

        for feature in self.features:
            if feature == "returns":
                features_df["returns"] = data["close"].pct_change()

            elif feature == "volatility":
                returns = data["close"].pct_change()
                features_df["volatility"] = returns.rolling(10).std()

            elif feature == "rsi":
                features_df["rsi"] = self._rsi(data["close"])

            elif feature == "macd":
                features_df["macd"] = self._macd(data["close"])

            elif feature == "bollinger":
                upper, lower = self._bollinger(data["close"])
                features_df["bb_upper"] = upper
                features_df["bb_lower"] = lower
                features_df["bb_width"] = (upper - lower) / data["close"]

            elif feature == "volume_change":
                features_df["volume_change"] = data["volume"].pct_change()

        return features_df.fillna(0)

    def _rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def _macd(self, prices: pd.Series) -> pd.Series:
        ema12 = prices.ewm(span=12, adjust=False).mean()
        ema26 = prices.ewm(span=26, adjust=False).mean()
        return ema12 - ema26

    def _bollinger(self, prices: pd.Series, period: int = 20) -> tuple[pd.Series, pd.Series]:
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        return middle + 2 * std, middle - 2 * std

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": "feature_engineering",
            "features": self.features,
        }
