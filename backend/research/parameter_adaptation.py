"""
🔄 Real-Time Parameter Adaptation

Adaptive strategy parameters based on market regime.

@version: 1.0.0
@date: 2026-02-26
"""

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    """Market regime classification"""

    regime: str  # 'trending', 'ranging', 'volatile', 'calm'
    confidence: float
    parameters: dict[str, Any]


class ParameterAdapter:
    """
    Real-time strategy parameter adaptation.

    Adapts strategy parameters based on current market regime.
    """

    def __init__(self, lookback: int = 100):
        """
        Args:
            lookback: Lookback period for regime detection
        """
        self.lookback = lookback

        # Default parameters for each regime
        self.regime_parameters = {
            "trending": {
                "rsi_period": 21,
                "take_profit": 0.03,
                "stop_loss": 0.01,
                "position_size": 0.1,
            },
            "ranging": {
                "rsi_period": 14,
                "take_profit": 0.02,
                "stop_loss": 0.015,
                "position_size": 0.05,
            },
            "volatile": {
                "rsi_period": 10,
                "take_profit": 0.05,
                "stop_loss": 0.02,
                "position_size": 0.03,
            },
            "calm": {
                "rsi_period": 14,
                "take_profit": 0.02,
                "stop_loss": 0.01,
                "position_size": 0.08,
            },
        }

    def detect_regime(self, data: pd.DataFrame) -> MarketRegime:
        """
        Detect current market regime.

        Args:
            data: OHLCV data

        Returns:
            MarketRegime
        """
        if len(data) < self.lookback:
            return MarketRegime(regime="unknown", confidence=0.0, parameters={})

        # Calculate indicators
        returns = data["close"].pct_change().dropna()

        # Trend strength (ADX proxy)
        ma_short = data["close"].rolling(10).mean()
        ma_long = data["close"].rolling(50).mean()
        trend_strength = abs(ma_short.iloc[-1] - ma_long.iloc[-1]) / ma_long.iloc[-1]

        # Volatility
        volatility = returns.std()

        # Range-bound (autocorrelation)
        autocorr = returns.autocorr(lag=1) if len(returns) > 20 else 0.0

        # Classify regime
        if trend_strength > 0.05:
            regime = "trending"
            confidence = min(trend_strength / 0.1, 1.0)
        elif volatility > 0.03:
            regime = "volatile"
            confidence = min(volatility / 0.05, 1.0)
        elif abs(autocorr) > 0.3:
            regime = "ranging"
            confidence = abs(autocorr)
        else:
            regime = "calm"
            confidence = 1.0 - abs(autocorr)

        return MarketRegime(regime=regime, confidence=confidence, parameters=self.regime_parameters.get(regime, {}))

    def get_adaptive_parameters(self, data: pd.DataFrame, base_parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Get adaptive parameters.

        Args:
            data: OHLCV data
            base_parameters: Base strategy parameters

        Returns:
            Adapted parameters
        """
        regime = self.detect_regime(data)

        # Get regime-specific parameters
        regime_params = self.regime_parameters.get(regime.regime, {})

        # Blend with base parameters
        adapted = {**base_parameters}

        for key, value in regime_params.items():
            if key in adapted:
                # Weight by regime confidence
                adapted[key] = adapted[key] * (1 - regime.confidence) + value * regime.confidence

        adapted["market_regime"] = regime.regime
        adapted["regime_confidence"] = regime.confidence

        return adapted

    def adapt_on_fly(
        self, parameters: dict[str, Any], current_pnl: float, drawdown: float, win_rate: float
    ) -> dict[str, Any]:
        """
        Adapt parameters on-the-fly based on performance.

        Args:
            parameters: Current parameters
            current_pnl: Current PnL
            drawdown: Current drawdown
            win_rate: Win rate

        Returns:
            Adapted parameters
        """
        adapted = {**parameters}

        # Reduce position size during drawdown
        if drawdown > 0.1:
            adapted["position_size"] *= 0.5

        # Increase position size during good performance
        if win_rate > 0.6 and current_pnl > 0:
            adapted["position_size"] *= 1.2

        # Adjust take profit based on win rate
        if win_rate < 0.4:
            adapted["take_profit"] *= 0.8

        return adapted
