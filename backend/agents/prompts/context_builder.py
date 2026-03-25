"""
Market Context Builder for LLM prompts.

Analyzes OHLCV data to build structured market context:
- Market regime detection (trending/ranging/volatile)
- Support/resistance levels
- Volatility metrics (ATR, historical volatility)
- Volume profile analysis
- Technical indicator summary

This context enriches LLM prompts for more relevant strategy generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class MarketContext:
    """Structured market context for LLM prompts."""

    symbol: str
    timeframe: str
    current_price: float
    period_high: float
    period_low: float
    price_change_pct: float
    data_points: int

    # Market regime
    market_regime: str  # "trending_up", "trending_down", "ranging", "volatile"
    trend_direction: str  # "bullish", "bearish", "neutral"
    trend_strength: str  # "strong", "moderate", "weak"

    # Volatility
    atr_value: float
    atr_pct: float  # ATR as % of price
    historical_volatility: float

    # Volume
    volume_profile: str  # "increasing", "decreasing", "stable"
    avg_volume: float

    # Key levels
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)

    # Indicator summary
    indicators_summary: str = ""

    def to_prompt_vars(self) -> dict[str, Any]:
        """Convert to dict for prompt template formatting."""
        return {
            "symbol": self.symbol,
            "timeframe_display": self._timeframe_display(),
            "current_price": self.current_price,
            "period_high": self.period_high,
            "period_low": self.period_low,
            "price_change_pct": self.price_change_pct,
            "data_points": self.data_points,
            "market_regime": self.market_regime,
            "trend_direction": self.trend_direction,
            "atr_value": f"{self.atr_pct:.2f}%",
            "volume_profile": self.volume_profile,
            "support_levels": ", ".join(f"${s:,.2f}" for s in self.support_levels[:3]),
            "resistance_levels": ", ".join(f"${r:,.2f}" for r in self.resistance_levels[:3]),
            "indicators_summary": self.indicators_summary,
            "volume_summary": f"Avg volume: {self.avg_volume:,.0f}, Profile: {self.volume_profile}",
        }

    def _timeframe_display(self) -> str:
        """Convert internal timeframe to display format."""
        mapping = {
            "1": "1 min",
            "5": "5 min",
            "15": "15 min",
            "30": "30 min",
            "60": "1 hour",
            "240": "4 hours",
            "D": "Daily",
            "W": "Weekly",
            "M": "Monthly",
        }
        return mapping.get(self.timeframe, self.timeframe)


class MarketContextBuilder:
    """
    Builds structured market context from OHLCV data.

    Analyzes raw candle data and produces a MarketContext
    object that can be used to enrich LLM prompts.

    Example:
        builder = MarketContextBuilder()
        context = builder.build_context(
            symbol="BTCUSDT",
            timeframe="15",
            df=candles_df,
        )
        prompt_vars = context.to_prompt_vars()
    """

    # ATR period for volatility calculation
    ATR_PERIOD = 14

    # EMA periods for trend detection
    TREND_FAST_EMA = 20
    TREND_SLOW_EMA = 50

    # Lookback for S/R detection
    SR_LOOKBACK = 50
    SR_NUM_LEVELS = 3

    def build_context(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
    ) -> MarketContext:
        """
        Build complete market context from OHLCV DataFrame.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            timeframe: Timeframe string (e.g., "15", "60", "D")
            df: OHLCV DataFrame with columns: open, high, low, close, volume

        Returns:
            MarketContext with all fields populated
        """
        if df is None or df.empty or len(df) < self.TREND_SLOW_EMA:
            logger.warning(f"Insufficient data for context: {len(df) if df is not None else 0} rows")
            return self._empty_context(symbol, timeframe)

        # Ensure required columns
        required_cols = {"open", "high", "low", "close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in DataFrame: {missing}")

        current_price = float(df["close"].iloc[-1])
        period_high = float(df["high"].max())
        period_low = float(df["low"].min())
        first_close = float(df["close"].iloc[0])
        price_change_pct = ((current_price - first_close) / first_close * 100) if first_close > 0 else 0

        # Calculate all components
        atr_value, atr_pct, hist_vol = self._calculate_volatility(df, current_price)
        market_regime, trend_dir, trend_str = self._detect_market_regime(df)
        volume_profile, avg_volume = self._analyze_volume(df)
        support, resistance = self._find_support_resistance(df, current_price)
        indicators_summary = self._summarize_indicators(df)

        return MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            current_price=current_price,
            period_high=period_high,
            period_low=period_low,
            price_change_pct=price_change_pct,
            data_points=len(df),
            market_regime=market_regime,
            trend_direction=trend_dir,
            trend_strength=trend_str,
            atr_value=atr_value,
            atr_pct=atr_pct,
            historical_volatility=hist_vol,
            volume_profile=volume_profile,
            avg_volume=avg_volume,
            support_levels=support,
            resistance_levels=resistance,
            indicators_summary=indicators_summary,
        )

    def _calculate_volatility(self, df: pd.DataFrame, current_price: float) -> tuple[float, float, float]:
        """Calculate ATR and historical volatility."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # True Range
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = float(true_range.rolling(window=self.ATR_PERIOD).mean().iloc[-1])
        atr_pct = (atr / current_price * 100) if current_price > 0 else 0

        # Historical volatility (annualized)
        returns = close.pct_change().dropna()
        hist_vol = float(returns.std() * np.sqrt(252) * 100) if len(returns) > 1 else 0

        return atr, atr_pct, hist_vol

    def _detect_market_regime(self, df: pd.DataFrame) -> tuple[str, str, str]:
        """
        Detect market regime using EMA crossover and ADX-like logic.

        Returns:
            (regime, trend_direction, trend_strength)
        """
        close = df["close"]

        # EMAs for trend
        ema_fast = close.ewm(span=self.TREND_FAST_EMA, adjust=False).mean()
        ema_slow = close.ewm(span=self.TREND_SLOW_EMA, adjust=False).mean()

        current_fast = float(ema_fast.iloc[-1])
        current_slow = float(ema_slow.iloc[-1])
        current_close = float(close.iloc[-1])

        # Trend direction
        if current_fast > current_slow and current_close > current_fast:
            trend_direction = "bullish"
        elif current_fast < current_slow and current_close < current_fast:
            trend_direction = "bearish"
        else:
            trend_direction = "neutral"

        # Trend strength: distance between EMAs as % of price
        ema_spread = abs(current_fast - current_slow) / current_slow * 100 if current_slow > 0 else 0

        if ema_spread > 3.0:
            trend_strength = "strong"
        elif ema_spread > 1.0:
            trend_strength = "moderate"
        else:
            trend_strength = "weak"

        # Market regime
        # Check volatility (range of recent candles)
        recent = df.tail(20)
        recent_range = (float(recent["high"].max()) - float(recent["low"].min())) / current_close * 100

        if trend_direction != "neutral" and trend_strength in ("strong", "moderate"):
            market_regime = "trending_up" if trend_direction == "bullish" else "trending_down"
        elif recent_range > 10:
            market_regime = "volatile"
        else:
            market_regime = "ranging"

        return market_regime, trend_direction, trend_strength

    def _analyze_volume(self, df: pd.DataFrame) -> tuple[str, float]:
        """Analyze volume profile."""
        volume = df["volume"]
        avg_volume = float(volume.mean())

        if avg_volume == 0:
            return "stable", 0.0

        # Compare recent volume to historical
        recent_avg = float(volume.tail(20).mean())
        historical_avg = float(volume.mean())

        ratio = recent_avg / historical_avg if historical_avg > 0 else 1.0

        if ratio > 1.3:
            profile = "increasing"
        elif ratio < 0.7:
            profile = "decreasing"
        else:
            profile = "stable"

        return profile, avg_volume

    def _find_support_resistance(self, df: pd.DataFrame, current_price: float) -> tuple[list[float], list[float]]:
        """
        Find support and resistance levels using pivot points.

        Uses local minima/maxima detection.
        """
        lookback = min(len(df), self.SR_LOOKBACK * 3)
        recent = df.tail(lookback)

        highs = recent["high"].values
        lows = recent["low"].values

        # Find local maxima (resistance) and minima (support)
        resistance_candidates: list[float] = []
        support_candidates: list[float] = []

        window = 5
        for i in range(window, len(highs) - window):
            # Local max
            if highs[i] == max(highs[i - window : i + window + 1]):
                resistance_candidates.append(float(highs[i]))
            # Local min
            if lows[i] == min(lows[i - window : i + window + 1]):
                support_candidates.append(float(lows[i]))

        # Cluster nearby levels (within 0.5%)
        support_levels = self._cluster_levels(
            [s for s in support_candidates if s < current_price],
            current_price,
        )
        resistance_levels = self._cluster_levels(
            [r for r in resistance_candidates if r > current_price],
            current_price,
        )

        # Sort: support descending (closest first), resistance ascending (closest first)
        support_levels.sort(reverse=True)
        resistance_levels.sort()

        return support_levels[: self.SR_NUM_LEVELS], resistance_levels[: self.SR_NUM_LEVELS]

    def _cluster_levels(self, levels: list[float], reference_price: float, threshold_pct: float = 0.5) -> list[float]:
        """Cluster nearby price levels within threshold_pct of each other."""
        if not levels:
            return []

        sorted_levels = sorted(levels)
        clusters: list[list[float]] = [[sorted_levels[0]]]

        for level in sorted_levels[1:]:
            cluster_avg = sum(clusters[-1]) / len(clusters[-1])
            if abs(level - cluster_avg) / cluster_avg * 100 < threshold_pct:
                clusters[-1].append(level)
            else:
                clusters.append([level])

        # Return average of each cluster
        return [round(sum(c) / len(c), 2) for c in clusters]

    def _summarize_indicators(self, df: pd.DataFrame) -> str:
        """Generate text summary of key technical indicators."""
        close = df["close"]
        lines = []

        try:
            # RSI
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            rsi_val = float(rsi.iloc[-1])
            rsi_zone = "oversold" if rsi_val < 30 else "overbought" if rsi_val > 70 else "neutral"
            lines.append(f"RSI(14): {rsi_val:.1f} ({rsi_zone})")
        except Exception:
            pass

        try:
            # MACD
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line
            macd_signal = "bullish" if float(histogram.iloc[-1]) > 0 else "bearish"
            lines.append(f"MACD(12,26,9): {macd_signal}, histogram={float(histogram.iloc[-1]):.2f}")
        except Exception:
            pass

        try:
            # EMAs
            ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
            ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
            current = float(close.iloc[-1])
            pos = "above" if current > ema20 else "below"
            lines.append(f"EMA(20): {ema20:.2f} (price {pos})")
            lines.append(f"EMA(50): {ema50:.2f}")
        except Exception:
            pass

        try:
            # Bollinger Bands
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            upper = float((sma20 + 2 * std20).iloc[-1])
            lower = float((sma20 - 2 * std20).iloc[-1])
            current = float(close.iloc[-1])
            bb_pct = (current - lower) / (upper - lower) * 100 if (upper - lower) > 0 else 50
            lines.append(f"Bollinger(20,2): upper={upper:.2f}, lower={lower:.2f}, %B={bb_pct:.0f}%")
        except Exception:
            pass

        return "\n".join(lines) if lines else "No indicators available"

    def _empty_context(self, symbol: str, timeframe: str) -> MarketContext:
        """Return empty context for insufficient data."""
        return MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            current_price=0.0,
            period_high=0.0,
            period_low=0.0,
            price_change_pct=0.0,
            data_points=0,
            market_regime="unknown",
            trend_direction="neutral",
            trend_strength="weak",
            atr_value=0.0,
            atr_pct=0.0,
            historical_volatility=0.0,
            volume_profile="stable",
            avg_volume=0.0,
            indicators_summary="Insufficient data",
        )
