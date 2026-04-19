"""
🧱 Market Microstructure Blocks

Market microstructure analysis blocks.
"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class MicrostructureResult:
    """Microstructure result"""

    spread: float
    spread_pct: float
    liquidity_score: float
    market_quality: str  # 'high', 'medium', 'low'
    metadata: dict[str, Any] = field(default_factory=dict)


class SpreadAnalysisBlock:
    """
    Spread Analysis block.

    Анализирует спред и ликвидность.
    """

    def __init__(self):
        pass

    def calculate(self, data: pd.DataFrame) -> MicrostructureResult:
        """
        Calculate spread metrics.

        Args:
            data: OHLCV данные

        Returns:
            MicrostructureResult
        """
        # Calculate spread (high - low as proxy)
        spread = data["high"] - data["low"]
        avg_spread = spread.mean()
        current_spread = spread.iloc[-1]

        # Spread as percentage
        spread_pct = (current_spread / data["close"].iloc[-1]) * 100

        # Liquidity score (inverse of spread, normalized)
        max_spread = spread.max()
        min_spread = spread.min()

        if max_spread - min_spread > 0:
            liquidity_score = 1 - (current_spread - min_spread) / (max_spread - min_spread)
        else:
            liquidity_score = 1.0

        # Market quality
        if liquidity_score > 0.7:
            market_quality = "high"
        elif liquidity_score > 0.4:
            market_quality = "medium"
        else:
            market_quality = "low"

        return MicrostructureResult(
            spread=current_spread,
            spread_pct=spread_pct,
            liquidity_score=liquidity_score,
            market_quality=market_quality,
            metadata={
                "avg_spread": avg_spread,
                "max_spread": max_spread,
                "min_spread": min_spread,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "spread_analysis",
        }


class LiquidityBlock:
    """
    Liquidity analysis block.

    Анализирует ликвидность рынка.
    """

    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def calculate(self, data: pd.DataFrame) -> dict[str, Any]:
        """Calculate liquidity metrics"""
        # Volume-based liquidity
        avg_volume = data["volume"].rolling(self.lookback).mean().iloc[-1]
        current_volume = data["volume"].iloc[-1]

        # Volume liquidity score
        volume_liquidity = min(current_volume / (avg_volume + 1e-10), 2.0) / 2.0

        # Price-based liquidity (tightness)
        spread = (data["high"] - data["low"]).iloc[-1]
        avg_spread = (data["high"] - data["low"]).rolling(self.lookback).mean().iloc[-1]

        spread_liquidity = min(avg_spread / (spread + 1e-10), 2.0) / 2.0

        # Combined liquidity score
        liquidity_score = (volume_liquidity + spread_liquidity) / 2

        # Market depth (mock - would need orderbook data)
        market_depth = "medium"

        return {
            "liquidity_score": liquidity_score,
            "volume_liquidity": volume_liquidity,
            "spread_liquidity": spread_liquidity,
            "market_depth": market_depth,
            "avg_volume": avg_volume,
            "current_volume": current_volume,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "liquidity_analysis",
            "lookback": self.lookback,
        }
