"""
📊 Market Analytics API Router
==============================
REST API endpoints for advanced market analysis:
- Open Interest
- Long/Short Ratio
- Funding Rate
- Full Market Analysis

Created: January 21, 2026
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.services.market_analytics import MarketAnalyticsService

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton service instance
_analytics_service = None


def get_analytics_service() -> MarketAnalyticsService:
    """Get or create Market Analytics service."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = MarketAnalyticsService()
    return _analytics_service


# =============================================================================
# OPEN INTEREST
# =============================================================================


@router.get("/open-interest/{symbol}")
async def get_open_interest(
    symbol: str,
    category: str = Query("linear", description="Market category: linear, inverse"),
    interval: str = Query("1h", description="Interval: 5min, 15min, 30min, 1h, 4h, 1d"),
    limit: int = Query(50, ge=1, le=200, description="Number of records"),
):
    """
    📊 Get Open Interest history for a symbol.

    Open Interest represents total outstanding contracts:
    - Rising OI = new money entering (trend confirmation)
    - Falling OI = money leaving (trend exhaustion)
    """
    try:
        service = get_analytics_service()
        data = service.get_open_interest(
            symbol=symbol, category=category, interval=interval, limit=limit
        )

        return {
            "success": True,
            "symbol": symbol.upper(),
            "category": category,
            "interval": interval,
            "count": len(data),
            "data": [
                {"timestamp": d.timestamp, "open_interest": d.open_interest}
                for d in data
            ],
        }
    except Exception as e:
        logger.error(f"Open Interest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/open-interest/{symbol}/analysis")
async def get_open_interest_analysis(
    symbol: str,
    category: str = Query("linear", description="Market category"),
    hours: int = Query(24, ge=1, le=168, description="Analysis period in hours"),
):
    """
    📊 Get Open Interest analysis with trend signal.

    Returns change % and trading signal based on OI movement.
    """
    try:
        service = get_analytics_service()
        result = service.get_open_interest_change(
            symbol=symbol, category=category, hours=hours
        )

        return {"success": True, **result}
    except Exception as e:
        logger.error(f"OI Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# LONG/SHORT RATIO
# =============================================================================


@router.get("/long-short/{symbol}")
async def get_long_short_ratio(
    symbol: str,
    category: str = Query("linear", description="Market category: linear, inverse"),
    period: str = Query("1h", description="Period: 5min, 15min, 30min, 1h, 4h, 1d"),
    limit: int = Query(50, ge=1, le=500, description="Number of records"),
):
    """
    📈 Get Long/Short Ratio history for a symbol.

    Shows percentage of accounts in longs vs shorts.
    Extreme readings often signal contrarian opportunities.
    """
    try:
        service = get_analytics_service()
        data = service.get_long_short_ratio(
            symbol=symbol, category=category, period=period, limit=limit
        )

        return {
            "success": True,
            "symbol": symbol.upper(),
            "category": category,
            "period": period,
            "count": len(data),
            "data": [
                {
                    "timestamp": d.timestamp,
                    "long_ratio": round(d.buy_ratio * 100, 2),
                    "short_ratio": round(d.sell_ratio * 100, 2),
                }
                for d in data
            ],
        }
    except Exception as e:
        logger.error(f"Long/Short Ratio error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/long-short/{symbol}/signal")
async def get_contrarian_signal(
    symbol: str, category: str = Query("linear", description="Market category")
):
    """
    📈 Get contrarian trading signal based on Long/Short ratio.

    When crowd is too bullish → consider shorting (and vice versa).
    """
    try:
        service = get_analytics_service()
        result = service.get_contrarian_signal(symbol=symbol, category=category)

        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Contrarian Signal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FUNDING RATE
# =============================================================================


@router.get("/funding/{symbol}")
async def get_funding_rate_history(
    symbol: str,
    category: str = Query("linear", description="Market category: linear, inverse"),
    limit: int = Query(100, ge=1, le=200, description="Number of records"),
):
    """
    💰 Get Funding Rate history for a symbol.

    Funding rate is paid every 8 hours between longs and shorts:
    - Positive = longs pay shorts (bullish sentiment)
    - Negative = shorts pay longs (bearish sentiment)
    """
    try:
        service = get_analytics_service()
        data = service.get_funding_rate_history(
            symbol=symbol, category=category, limit=limit
        )

        return {
            "success": True,
            "symbol": symbol.upper(),
            "category": category,
            "count": len(data),
            "data": [
                {
                    "timestamp": d.timestamp,
                    "funding_rate": round(d.funding_rate * 100, 4),  # As percentage
                }
                for d in data
            ],
        }
    except Exception as e:
        logger.error(f"Funding Rate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding/{symbol}/analysis")
async def get_funding_analysis(
    symbol: str,
    category: str = Query("linear", description="Market category"),
    days: int = Query(7, ge=1, le=30, description="Analysis period in days"),
):
    """
    💰 Get Funding Rate analysis with sentiment and arbitrage signals.

    Returns current rate, average, annualized APR, and trading implications.
    """
    try:
        service = get_analytics_service()
        result = service.get_funding_analysis(
            symbol=symbol, category=category, days=days
        )

        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Funding Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FULL MARKET ANALYSIS
# =============================================================================


@router.get("/analysis/{symbol}")
async def get_full_market_analysis(
    symbol: str,
    category: str = Query("linear", description="Market category: linear, inverse"),
):
    """
    🎯 Get comprehensive market analysis combining all indicators.

    Returns:
    - Overall sentiment (BULLISH/BEARISH/NEUTRAL)
    - Open Interest analysis
    - Long/Short ratio with contrarian signal
    - Funding rate analysis
    - Trading recommendations
    """
    try:
        service = get_analytics_service()
        result = service.get_full_market_analysis(symbol=symbol, category=category)

        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Full Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MULTI-SYMBOL ANALYSIS
# =============================================================================


@router.get("/analysis/batch")
async def get_batch_market_analysis(
    symbols: str = Query(
        ..., description="Comma-separated symbols (e.g., BTCUSDT,ETHUSDT)"
    ),
    category: str = Query("linear", description="Market category"),
):
    """
    🎯 Get market analysis for multiple symbols at once.
    """
    try:
        service = get_analytics_service()
        symbol_list = [s.strip().upper() for s in symbols.split(",")]

        results = {}
        for symbol in symbol_list[:10]:  # Limit to 10 symbols
            try:
                results[symbol] = service.get_full_market_analysis(
                    symbol=symbol, category=category
                )
            except Exception as e:
                results[symbol] = {"error": str(e)}

        return {"success": True, "count": len(results), "results": results}
    except Exception as e:
        logger.error(f"Batch Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
