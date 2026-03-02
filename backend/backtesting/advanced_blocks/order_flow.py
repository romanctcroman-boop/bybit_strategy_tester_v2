"""
🧱 Order Flow Blocks

Order flow analysis blocks:
- Order Flow Imbalance
- Cumulative Delta
- Volume Imbalance
- Trade Flow
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OrderFlowResult:
    """Order flow result"""

    imbalance: float  # -1 to 1
    signal: int  # -1, 0, 1
    strength: float  # 0 to 1
    metadata: dict[str, Any] = field(default_factory=dict)


class OrderFlowImbalanceBlock:
    """
    Order Flow Imbalance block.

    Анализирует дисбаланс между покупками и продажами.

    Parameters:
        lookback: Количество баров для анализа
        threshold: Порог для сигнала

    Returns:
        imbalance: -1 (sell pressure) to 1 (buy pressure)
        signal: -1, 0, 1
        strength: Сила сигнала
    """

    def __init__(
        self,
        lookback: int = 20,
        threshold: float = 0.3,
    ):
        self.lookback = lookback
        self.threshold = threshold

    def calculate(self, data: pd.DataFrame) -> OrderFlowResult:
        """
        Рассчитать Order Flow Imbalance.

        Args:
            data: OHLCV данные

        Returns:
            OrderFlowResult
        """
        if len(data) < self.lookback:
            return OrderFlowResult(imbalance=0, signal=0, strength=0, metadata={"error": "Insufficient data"})

        # Calculate buy/sell pressure
        # Using high-low-close to estimate buying/selling pressure
        typical_price = (data["high"] + data["low"] + data["close"]) / 3
        price_change = typical_price.diff()

        # Volume-weighted pressure
        buy_volume = (data["volume"] * (price_change > 0)).fillna(0)
        sell_volume = (data["volume"] * (price_change < 0)).fillna(0)

        # Rolling sums
        buy_sum = buy_volume.rolling(self.lookback).sum()
        sell_sum = sell_volume.rolling(self.lookback).sum()

        # Imbalance
        total_volume = buy_sum + sell_sum
        imbalance = (buy_sum - sell_sum) / (total_volume + 1e-10)

        current_imbalance = imbalance.iloc[-1]

        # Signal
        if current_imbalance > self.threshold:
            signal = 1  # Buy pressure
        elif current_imbalance < -self.threshold:
            signal = -1  # Sell pressure
        else:
            signal = 0

        # Strength
        strength = min(abs(current_imbalance), 1.0)

        return OrderFlowResult(
            imbalance=current_imbalance,
            signal=signal,
            strength=strength,
            metadata={
                "buy_volume": buy_sum.iloc[-1],
                "sell_volume": sell_sum.iloc[-1],
                "lookback": self.lookback,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": "order_flow_imbalance",
            "lookback": self.lookback,
            "threshold": self.threshold,
        }


class CumulativeDeltaBlock:
    """
    Cumulative Delta block.

    Накопленная дельта между покупками и продажами.

    Parameters:
        window: Окно для сглаживания

    Returns:
        delta: Cumulative delta
        trend: Тренд дельты
        divergence: Дивергенция с ценой
    """

    def __init__(self, window: int = 10):
        self.window = window

    def calculate(self, data: pd.DataFrame) -> dict[str, Any]:
        """
        Рассчитать Cumulative Delta.

        Args:
            data: OHLCV данные

        Returns:
            Dict с delta, trend, divergence
        """
        # Calculate delta
        # Delta = buy volume - sell volume
        typical_price = (data["high"] + data["low"] + data["close"]) / 3
        price_change = typical_price.diff()

        buy_volume = (data["volume"] * (price_change > 0)).fillna(0)
        sell_volume = (data["volume"] * (price_change < 0)).fillna(0)

        delta = buy_volume - sell_volume

        # Cumulative delta
        cum_delta = delta.cumsum()

        # Smoothed delta
        smoothed_delta = cum_delta.rolling(self.window).mean()

        # Trend
        delta_trend = smoothed_delta.diff()
        current_trend = delta_trend.iloc[-1]

        # Divergence with price
        price_trend = data["close"].diff().iloc[-1]

        if current_trend > 0 and price_trend < 0:
            divergence = "bullish"  # Delta up, price down
        elif current_trend < 0 and price_trend > 0:
            divergence = "bearish"  # Delta down, price up
        else:
            divergence = "none"

        return {
            "cumulative_delta": cum_delta.iloc[-1],
            "smoothed_delta": smoothed_delta.iloc[-1],
            "delta_trend": current_trend,
            "divergence": divergence,
            "delta": delta.iloc[-1],
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": "cumulative_delta",
            "window": self.window,
        }
