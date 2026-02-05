"""
📊 Market Regime Detection API Router

Provides endpoints for:
- Real-time market regime detection
- Historical regime analysis
- Regime-based trading signals

Usage:
    from backend.api.routers.market_regime import router
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.backtesting.market_regime import (
    MarketRegimeDetector,
    RegimeConfig,
    RegimeType,
)
from backend.services.adapters.bybit import BybitAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market-regime", tags=["market-regime"])


# ============== Request/Response Models ==============


class RegimeDetectionRequest(BaseModel):
    """Request for regime detection."""

    symbol: str = Field(default="BTCUSDT", description="Trading pair symbol")
    interval: str = Field(default="1h", description="Candlestick interval")
    lookback_bars: int = Field(
        default=200, ge=50, le=1000, description="Number of bars to analyze"
    )

    # Optional custom thresholds
    adx_trending_threshold: float | None = Field(
        default=None, ge=10, le=50, description="ADX threshold for trending"
    )
    adx_weak_threshold: float | None = Field(
        default=None, ge=5, le=25, description="ADX threshold for ranging"
    )
    bandwidth_squeeze: float | None = Field(
        default=None, ge=1, le=10, description="BB bandwidth squeeze threshold"
    )


class RegimeIndicators(BaseModel):
    """Regime indicator values."""

    adx: float = Field(..., description="Average Directional Index")
    plus_di: float = Field(..., description="Positive Directional Indicator")
    minus_di: float = Field(..., description="Negative Directional Indicator")
    volatility: float = Field(..., description="ATR as percentage of price")
    bandwidth: float = Field(..., description="Bollinger Bandwidth")
    trend_strength: float = Field(..., description="Normalized trend strength 0-1")


class RegimeDetectionResponse(BaseModel):
    """Response from regime detection."""

    symbol: str
    interval: str
    timestamp: str
    regime: str = Field(..., description="Detected regime type")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence")
    indicators: RegimeIndicators
    trading_signals: dict = Field(..., description="Trading recommendations")
    reason: str = Field(..., description="Detection reason")


class RegimeHistoryItem(BaseModel):
    """Single item in regime history."""

    timestamp: str
    regime: str
    confidence: float
    adx: float


class RegimeHistoryResponse(BaseModel):
    """Response for historical regime analysis."""

    symbol: str
    interval: str
    start_date: str
    end_date: str
    total_bars: int
    regime_distribution: dict = Field(..., description="Percentage of each regime")
    history: list[RegimeHistoryItem] = Field(..., description="Regime history")
    transitions: int = Field(..., description="Number of regime changes")


class RegimeStatsResponse(BaseModel):
    """Statistical analysis of regimes."""

    symbol: str
    interval: str
    analysis_period_days: int
    regime_stats: dict = Field(..., description="Statistics per regime")
    current_regime: str
    avg_regime_duration_bars: float
    dominant_regime: str


# ============== API Endpoints ==============


@router.post("/detect", response_model=RegimeDetectionResponse)
async def detect_market_regime(
    request: RegimeDetectionRequest,
) -> RegimeDetectionResponse:
    """
    Detect current market regime for a symbol.

    Returns regime type, confidence, and trading recommendations.
    """
    try:
        # Build config from request
        config = RegimeConfig()
        if request.adx_trending_threshold:
            config.adx_trending_threshold = request.adx_trending_threshold
        if request.adx_weak_threshold:
            config.adx_weak_threshold = request.adx_weak_threshold
        if request.bandwidth_squeeze:
            config.bandwidth_squeeze = request.bandwidth_squeeze

        # Fetch market data
        adapter = BybitAdapter()

        klines = adapter.get_klines(
            symbol=request.symbol,
            interval=request.interval,
            limit=request.lookback_bars,
        )

        if not klines or len(klines) < 50:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for {request.symbol}: got {len(klines) if klines else 0} bars",
            )

        # Convert to numpy arrays
        high = np.array([k["high"] for k in klines])
        low = np.array([k["low"] for k in klines])
        close = np.array([k["close"] for k in klines])

        # Detect regime
        detector = MarketRegimeDetector(config)
        detector.precompute_indicators(high, low, close)
        regime_state = detector.detect(idx=-1)

        # Build response
        return RegimeDetectionResponse(
            symbol=request.symbol,
            interval=request.interval,
            timestamp=datetime.now().isoformat(),
            regime=regime_state.regime.value,
            confidence=regime_state.confidence,
            indicators=RegimeIndicators(
                adx=regime_state.adx,
                plus_di=regime_state.plus_di,
                minus_di=regime_state.minus_di,
                volatility=regime_state.volatility,
                bandwidth=regime_state.bandwidth,
                trend_strength=regime_state.trend_strength,
            ),
            trading_signals={
                "allow_long": regime_state.allow_long,
                "allow_short": regime_state.allow_short,
                "recommended_position_size": regime_state.recommended_position_size,
                "regime_description": _get_regime_description(regime_state.regime),
            },
            reason=regime_state.reason,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regime detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{symbol}", response_model=RegimeHistoryResponse)
async def get_regime_history(
    symbol: str,
    interval: str = Query(default="1h", description="Candlestick interval"),
    days: int = Query(default=30, ge=1, le=365, description="Days of history"),
) -> RegimeHistoryResponse:
    """
    Get historical regime analysis for a symbol.

    Returns regime distribution and transitions over time.
    """
    try:
        # Fetch market data
        adapter = BybitAdapter()
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        # Calculate approximate number of bars needed
        limit = min(days * 24, 1000)  # Approximate bars for hourly data

        klines = adapter.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        if not klines or len(klines) < 50:
            raise HTTPException(status_code=400, detail="Insufficient data")

        # Convert to numpy arrays
        high = np.array([k["high"] for k in klines])
        low = np.array([k["low"] for k in klines])
        close = np.array([k["close"] for k in klines])
        timestamps = [k.get("timestamp", k.get("open_time", "")) for k in klines]

        # Detect regimes for all bars
        detector = MarketRegimeDetector()
        detector.precompute_indicators(high, low, close)

        history = []
        regime_counts: dict[str, int] = {}
        prev_regime = None
        transitions = 0

        for i in range(50, len(close)):  # Skip warmup period
            state = detector.detect(idx=i)
            regime_name = state.regime.value

            # Count regimes
            regime_counts[regime_name] = regime_counts.get(regime_name, 0) + 1

            # Count transitions
            if prev_regime and prev_regime != regime_name:
                transitions += 1
            prev_regime = regime_name

            # Sample history (every 10 bars to reduce response size)
            if i % 10 == 0:
                ts = timestamps[i] if i < len(timestamps) else ""
                history.append(
                    RegimeHistoryItem(
                        timestamp=str(ts),
                        regime=regime_name,
                        confidence=round(state.confidence, 3),
                        adx=round(state.adx, 2),
                    )
                )

        # Calculate distribution
        total = sum(regime_counts.values())
        distribution = {k: round(v / total * 100, 2) for k, v in regime_counts.items()}

        return RegimeHistoryResponse(
            symbol=symbol,
            interval=interval,
            start_date=start_time.isoformat(),
            end_date=end_time.isoformat(),
            total_bars=len(close),
            regime_distribution=distribution,
            history=history,
            transitions=transitions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regime history failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{symbol}", response_model=RegimeStatsResponse)
async def get_regime_stats(
    symbol: str,
    interval: str = Query(default="1h"),
    days: int = Query(default=30, ge=7, le=365),
) -> RegimeStatsResponse:
    """
    Get statistical analysis of market regimes.

    Returns average duration, dominant regime, and performance metrics.
    """
    try:
        # Fetch data
        adapter = BybitAdapter()

        # Calculate approximate number of bars
        limit = min(days * 24, 1000)

        klines = adapter.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        if not klines or len(klines) < 50:
            raise HTTPException(status_code=400, detail="Insufficient data")

        high = np.array([k["high"] for k in klines])
        low = np.array([k["low"] for k in klines])
        close = np.array([k["close"] for k in klines])

        detector = MarketRegimeDetector()
        detector.precompute_indicators(high, low, close)

        # Analyze regimes
        regime_stats: dict[str, dict[str, Any]] = {}
        current_regime = None
        current_duration = 0
        durations: list[int] = []

        for i in range(50, len(close)):
            state = detector.detect(idx=i)
            regime_name = state.regime.value

            if regime_name not in regime_stats:
                regime_stats[regime_name] = {
                    "count": 0,
                    "total_bars": 0,
                    "avg_adx": 0.0,
                    "avg_confidence": 0.0,
                    "adx_values": [],
                    "confidence_values": [],
                }

            regime_stats[regime_name]["count"] += 1
            regime_stats[regime_name]["total_bars"] += 1
            regime_stats[regime_name]["adx_values"].append(state.adx)
            regime_stats[regime_name]["confidence_values"].append(state.confidence)

            if current_regime == regime_name:
                current_duration += 1
            else:
                if current_duration > 0:
                    durations.append(current_duration)
                current_regime = regime_name
                current_duration = 1

        # Finalize stats
        for regime_name, stats in regime_stats.items():
            if stats["adx_values"]:
                stats["avg_adx"] = round(np.mean(stats["adx_values"]), 2)
                stats["avg_confidence"] = round(np.mean(stats["confidence_values"]), 3)
            del stats["adx_values"]
            del stats["confidence_values"]

        # Find dominant regime
        dominant = max(regime_stats.items(), key=lambda x: x[1]["total_bars"])
        avg_duration = np.mean(durations) if durations else 0

        # Get current regime
        current_state = detector.detect(idx=-1)

        return RegimeStatsResponse(
            symbol=symbol,
            interval=interval,
            analysis_period_days=days,
            regime_stats=regime_stats,
            current_regime=current_state.regime.value,
            avg_regime_duration_bars=round(avg_duration, 2),
            dominant_regime=dominant[0],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regime stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
async def list_regime_types() -> dict[str, Any]:
    """
    List all available regime types with descriptions.
    """
    return {
        "regime_types": [
            {
                "type": RegimeType.TRENDING_UP.value,
                "name": "Trending Up",
                "description": "Strong upward trend with ADX > 25 and +DI > -DI",
                "trading_bias": "LONG",
                "color": "#26a69a",
            },
            {
                "type": RegimeType.TRENDING_DOWN.value,
                "name": "Trending Down",
                "description": "Strong downward trend with ADX > 25 and -DI > +DI",
                "trading_bias": "SHORT",
                "color": "#ef5350",
            },
            {
                "type": RegimeType.RANGING.value,
                "name": "Ranging",
                "description": "Low volatility sideways market with ADX < 15",
                "trading_bias": "NEUTRAL",
                "color": "#78909c",
            },
            {
                "type": RegimeType.VOLATILE.value,
                "name": "Volatile",
                "description": "High volatility with no clear direction",
                "trading_bias": "CAUTION",
                "color": "#ffa726",
            },
            {
                "type": RegimeType.BREAKOUT_UP.value,
                "name": "Breakout Up",
                "description": "Transitioning from squeeze to uptrend",
                "trading_bias": "LONG",
                "color": "#66bb6a",
            },
            {
                "type": RegimeType.BREAKOUT_DOWN.value,
                "name": "Breakout Down",
                "description": "Transitioning from squeeze to downtrend",
                "trading_bias": "SHORT",
                "color": "#f44336",
            },
            {
                "type": RegimeType.UNKNOWN.value,
                "name": "Unknown",
                "description": "Insufficient data for detection",
                "trading_bias": "NONE",
                "color": "#9e9e9e",
            },
        ]
    }


def _get_regime_description(regime: RegimeType) -> str:
    """Get human-readable description for regime."""
    descriptions = {
        RegimeType.TRENDING_UP: "Market is in a strong uptrend. Favor LONG positions.",
        RegimeType.TRENDING_DOWN: "Market is in a strong downtrend. Favor SHORT positions.",
        RegimeType.RANGING: "Market is ranging sideways. Consider mean-reversion strategies.",
        RegimeType.VOLATILE: "High volatility detected. Reduce position sizes.",
        RegimeType.BREAKOUT_UP: "Potential bullish breakout forming. Watch for confirmation.",
        RegimeType.BREAKOUT_DOWN: "Potential bearish breakout forming. Watch for confirmation.",
        RegimeType.UNKNOWN: "Unable to determine market regime.",
    }
    return descriptions.get(regime, "Unknown regime")
