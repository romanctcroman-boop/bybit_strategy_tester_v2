"""
📊 Market Analytics Service
============================
Advanced market data endpoints from Bybit V5 API:
- Open Interest (OI) - для оценки силы тренда
- Long/Short Ratio - контраргументный сигнал
- Funding Rate History - для фьючерсных стратегий
- Mark Price / Index Price Klines

Created: January 21, 2026
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import requests

logger = logging.getLogger(__name__)


class IntervalTime(Enum):
    """Intervals for Open Interest"""

    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"


class MarketCategory(Enum):
    """Market categories"""

    SPOT = "spot"
    LINEAR = "linear"
    INVERSE = "inverse"


@dataclass
class OpenInterestData:
    """Open Interest data point"""

    timestamp: int
    open_interest: float  # Total OI in contracts/coins
    symbol: str


@dataclass
class LongShortRatioData:
    """Long/Short ratio data point"""

    timestamp: int
    buy_ratio: float  # Long ratio (0-1)
    sell_ratio: float  # Short ratio (0-1)
    symbol: str


@dataclass
class FundingRateData:
    """Funding rate data point"""

    timestamp: int
    funding_rate: float  # Funding rate (e.g., 0.0001 = 0.01%)
    symbol: str


class MarketAnalyticsService:
    """
    Service for advanced market analytics from Bybit V5 API.

    Features:
    - Open Interest tracking
    - Long/Short Ratio analysis
    - Funding Rate history
    - Mark/Index price data
    """

    BASE_URL = "https://api.bybit.com"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # =========================================================================
    # OPEN INTEREST
    # =========================================================================

    def get_open_interest(
        self,
        symbol: str,
        category: str = "linear",
        interval: str = "1h",
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 50,
    ) -> list[OpenInterestData]:
        """
        📊 Get Open Interest history.

        Open Interest shows the total number of outstanding contracts.
        Rising OI = new money entering the market (trend confirmation)
        Falling OI = money leaving (trend exhaustion)

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            category: "linear" or "inverse"
            interval: "5min", "15min", "30min", "1h", "4h", "1d"
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            limit: Number of records (max 200)

        Returns:
            List of OpenInterestData
        """
        endpoint = f"{self.BASE_URL}/v5/market/open-interest"

        params = {
            "symbol": symbol.upper(),
            "category": category,
            "intervalTime": interval,
            "limit": min(limit, 200),
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            data = response.json()

            if data.get("retCode") != 0:
                logger.error(f"Open Interest error: {data.get('retMsg')}")
                return []

            result = []
            for item in data.get("result", {}).get("list", []):
                result.append(
                    OpenInterestData(
                        timestamp=int(item.get("timestamp", 0)),
                        open_interest=float(item.get("openInterest", 0)),
                        symbol=symbol.upper(),
                    )
                )

            # API returns newest first, reverse for chronological order
            return result[::-1]

        except Exception as e:
            logger.error(f"Failed to get Open Interest: {e}")
            return []

    def get_open_interest_change(
        self, symbol: str, category: str = "linear", hours: int = 24
    ) -> dict[str, Any]:
        """
        📊 Calculate Open Interest change over period.

        Returns:
            Dict with current OI, change %, and trend signal
        """
        now = int(datetime.now().timestamp() * 1000)
        start = now - (hours * 60 * 60 * 1000)

        data = self.get_open_interest(
            symbol=symbol,
            category=category,
            interval="1h",
            start_time=start,
            end_time=now,
            limit=200,
        )

        if len(data) < 2:
            return {"error": "Insufficient data"}

        first_oi = data[0].open_interest
        last_oi = data[-1].open_interest
        change_pct = ((last_oi - first_oi) / first_oi * 100) if first_oi > 0 else 0

        # Determine trend signal
        if change_pct > 5:
            signal = "BULLISH_STRONG"
        elif change_pct > 0:
            signal = "BULLISH"
        elif change_pct > -5:
            signal = "BEARISH"
        else:
            signal = "BEARISH_STRONG"

        return {
            "symbol": symbol,
            "current_oi": last_oi,
            "start_oi": first_oi,
            "change_pct": round(change_pct, 2),
            "hours": hours,
            "signal": signal,
            "interpretation": self._interpret_oi_signal(signal),
        }

    def _interpret_oi_signal(self, signal: str) -> str:
        """Interpret OI signal for trading"""
        interpretations = {
            "BULLISH_STRONG": "Strong money inflow - trend likely to continue",
            "BULLISH": "Money entering market - supports current trend",
            "BEARISH": "Money leaving market - trend may be weakening",
            "BEARISH_STRONG": "Strong money outflow - potential reversal",
        }
        return interpretations.get(signal, "Unknown")

    # =========================================================================
    # LONG/SHORT RATIO
    # =========================================================================

    def get_long_short_ratio(
        self, symbol: str, category: str = "linear", period: str = "1h", limit: int = 50
    ) -> list[LongShortRatioData]:
        """
        📈 Get Long/Short Ratio history.

        Shows percentage of accounts holding longs vs shorts.
        Extreme readings (>0.7 or <0.3) often signal contrarian opportunities.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            category: "linear" or "inverse"
            period: "5min", "15min", "30min", "1h", "4h", "1d"
            limit: Number of records (max 500)

        Returns:
            List of LongShortRatioData
        """
        endpoint = f"{self.BASE_URL}/v5/market/account-ratio"

        params = {
            "symbol": symbol.upper(),
            "category": category,
            "period": period,
            "limit": min(limit, 500),
        }

        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            data = response.json()

            if data.get("retCode") != 0:
                logger.error(f"Long/Short Ratio error: {data.get('retMsg')}")
                return []

            result = []
            for item in data.get("result", {}).get("list", []):
                result.append(
                    LongShortRatioData(
                        timestamp=int(item.get("timestamp", 0)),
                        buy_ratio=float(item.get("buyRatio", 0)),
                        sell_ratio=float(item.get("sellRatio", 0)),
                        symbol=symbol.upper(),
                    )
                )

            # Reverse for chronological order
            return result[::-1]

        except Exception as e:
            logger.error(f"Failed to get Long/Short Ratio: {e}")
            return []

    def get_contrarian_signal(
        self, symbol: str, category: str = "linear"
    ) -> dict[str, Any]:
        """
        📈 Get contrarian trading signal based on Long/Short ratio.

        When too many traders are long → consider shorting (and vice versa).

        Returns:
            Dict with current ratio and contrarian signal
        """
        data = self.get_long_short_ratio(
            symbol=symbol, category=category, period="1h", limit=1
        )

        if not data:
            return {"error": "No data available"}

        latest = data[-1]
        long_ratio = latest.buy_ratio

        # Generate contrarian signal
        if long_ratio >= 0.70:
            signal = "CONTRARIAN_SHORT"
            strength = "STRONG"
            reason = f"Extreme long bias ({long_ratio * 100:.1f}%) - crowd may be wrong"
        elif long_ratio >= 0.60:
            signal = "CONTRARIAN_SHORT"
            strength = "MODERATE"
            reason = f"High long bias ({long_ratio * 100:.1f}%) - caution for longs"
        elif long_ratio <= 0.30:
            signal = "CONTRARIAN_LONG"
            strength = "STRONG"
            reason = (
                f"Extreme short bias ({long_ratio * 100:.1f}%) - crowd may be wrong"
            )
        elif long_ratio <= 0.40:
            signal = "CONTRARIAN_LONG"
            strength = "MODERATE"
            reason = f"High short bias ({long_ratio * 100:.1f}%) - caution for shorts"
        else:
            signal = "NEUTRAL"
            strength = "NONE"
            reason = f"Balanced market ({long_ratio * 100:.1f}% long)"

        return {
            "symbol": symbol,
            "long_ratio": round(long_ratio * 100, 2),
            "short_ratio": round(latest.sell_ratio * 100, 2),
            "signal": signal,
            "strength": strength,
            "reason": reason,
            "timestamp": latest.timestamp,
        }

    # =========================================================================
    # FUNDING RATE
    # =========================================================================

    def get_funding_rate_history(
        self,
        symbol: str,
        category: str = "linear",
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 200,
    ) -> list[FundingRateData]:
        """
        💰 Get Funding Rate history.

        Funding rate is paid between longs and shorts every 8 hours.
        - Positive rate = longs pay shorts (bullish sentiment)
        - Negative rate = shorts pay longs (bearish sentiment)

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            category: "linear" or "inverse"
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            limit: Number of records (max 200)

        Returns:
            List of FundingRateData
        """
        endpoint = f"{self.BASE_URL}/v5/market/funding/history"

        params = {
            "symbol": symbol.upper(),
            "category": category,
            "limit": min(limit, 200),
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            data = response.json()

            if data.get("retCode") != 0:
                logger.error(f"Funding Rate error: {data.get('retMsg')}")
                return []

            result = []
            for item in data.get("result", {}).get("list", []):
                result.append(
                    FundingRateData(
                        timestamp=int(item.get("fundingRateTimestamp", 0)),
                        funding_rate=float(item.get("fundingRate", 0)),
                        symbol=symbol.upper(),
                    )
                )

            # Reverse for chronological order
            return result[::-1]

        except Exception as e:
            logger.error(f"Failed to get Funding Rate: {e}")
            return []

    def get_funding_analysis(
        self, symbol: str, category: str = "linear", days: int = 7
    ) -> dict[str, Any]:
        """
        💰 Analyze funding rates for trading signals.

        Returns:
            Dict with funding stats and arbitrage opportunity
        """
        now = int(datetime.now().timestamp() * 1000)
        start = now - (days * 24 * 60 * 60 * 1000)

        data = self.get_funding_rate_history(
            symbol=symbol, category=category, start_time=start, end_time=now, limit=200
        )

        if not data:
            return {"error": "No funding data available"}

        rates = [d.funding_rate for d in data]
        avg_rate = sum(rates) / len(rates)
        latest_rate = rates[-1]

        # Annualized APR (3 funding periods per day * 365 days)
        daily_rate = avg_rate * 3
        annualized_apr = daily_rate * 365 * 100

        # Determine sentiment
        if latest_rate > 0.0005:  # > 0.05%
            sentiment = "VERY_BULLISH"
        elif latest_rate > 0.0001:  # > 0.01%
            sentiment = "BULLISH"
        elif latest_rate < -0.0005:  # < -0.05%
            sentiment = "VERY_BEARISH"
        elif latest_rate < -0.0001:  # < -0.01%
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"

        # Arbitrage opportunity
        if abs(annualized_apr) > 20:
            arb_signal = "HIGH_OPPORTUNITY"
        elif abs(annualized_apr) > 10:
            arb_signal = "MODERATE_OPPORTUNITY"
        else:
            arb_signal = "LOW_OPPORTUNITY"

        return {
            "symbol": symbol,
            "current_rate": round(latest_rate * 100, 4),  # As percentage
            "avg_rate_7d": round(avg_rate * 100, 4),
            "annualized_apr": round(annualized_apr, 2),
            "sentiment": sentiment,
            "arbitrage_signal": arb_signal,
            "data_points": len(data),
            "period_days": days,
            "interpretation": self._interpret_funding(sentiment, annualized_apr),
        }

    def _interpret_funding(self, sentiment: str, apr: float) -> str:
        """Interpret funding for trading"""
        if sentiment in ["VERY_BULLISH", "BULLISH"]:
            return f"Longs paying {abs(apr):.1f}% APR to shorts - crowded long position"
        elif sentiment in ["VERY_BEARISH", "BEARISH"]:
            return (
                f"Shorts paying {abs(apr):.1f}% APR to longs - crowded short position"
            )
        else:
            return "Balanced funding - no strong directional bias"

    # =========================================================================
    # COMPOSITE MARKET ANALYSIS
    # =========================================================================

    def get_full_market_analysis(
        self, symbol: str, category: str = "linear"
    ) -> dict[str, Any]:
        """
        🎯 Get comprehensive market analysis combining all indicators.

        Returns:
            Complete market analysis with all signals
        """
        oi_analysis = self.get_open_interest_change(symbol, category, hours=24)
        ls_signal = self.get_contrarian_signal(symbol, category)
        funding = self.get_funding_analysis(symbol, category, days=7)

        # Combine signals for overall sentiment
        signals = []

        if "signal" in oi_analysis:
            signals.append(("OI", oi_analysis.get("signal", "NEUTRAL")))
        if "signal" in ls_signal:
            signals.append(("LS", ls_signal.get("signal", "NEUTRAL")))
        if "sentiment" in funding:
            signals.append(("FR", funding.get("sentiment", "NEUTRAL")))

        # Calculate overall sentiment
        bullish_count = sum(1 for _, s in signals if "BULL" in s or "LONG" in s)
        bearish_count = sum(1 for _, s in signals if "BEAR" in s or "SHORT" in s)

        if bullish_count > bearish_count:
            overall = "BULLISH"
        elif bearish_count > bullish_count:
            overall = "BEARISH"
        else:
            overall = "NEUTRAL"

        return {
            "symbol": symbol,
            "timestamp": int(datetime.now().timestamp() * 1000),
            "overall_sentiment": overall,
            "confidence": abs(bullish_count - bearish_count) / max(len(signals), 1),
            "open_interest": oi_analysis,
            "long_short_ratio": ls_signal,
            "funding_rate": funding,
            "recommendations": self._generate_recommendations(
                oi_analysis, ls_signal, funding
            ),
        }

    def _generate_recommendations(self, oi: dict, ls: dict, fr: dict) -> list[str]:
        """Generate trading recommendations"""
        recommendations = []

        # OI-based
        if oi.get("signal") == "BULLISH_STRONG":
            recommendations.append("📈 Strong OI inflow supports current trend")
        elif oi.get("signal") == "BEARISH_STRONG":
            recommendations.append("⚠️ Money leaving - watch for trend reversal")

        # L/S ratio based
        if ls.get("signal") == "CONTRARIAN_SHORT" and ls.get("strength") == "STRONG":
            recommendations.append("🔴 Extreme long bias - consider contrarian short")
        elif ls.get("signal") == "CONTRARIAN_LONG" and ls.get("strength") == "STRONG":
            recommendations.append("🟢 Extreme short bias - consider contrarian long")

        # Funding based
        if fr.get("sentiment") == "VERY_BULLISH":
            recommendations.append("💰 High funding - longs paying premium (crowded)")
        elif fr.get("sentiment") == "VERY_BEARISH":
            recommendations.append("💰 Negative funding - shorts paying premium")

        if fr.get("arbitrage_signal") == "HIGH_OPPORTUNITY":
            apr = fr.get("annualized_apr", 0)
            recommendations.append(f"🎯 Funding arbitrage opportunity: {apr:.1f}% APR")

        if not recommendations:
            recommendations.append("📊 Market in equilibrium - no strong signals")

        return recommendations


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    # Quick test
    service = MarketAnalyticsService()

    print("=" * 70)
    print("🎯 MARKET ANALYTICS TEST: BTCUSDT")
    print("=" * 70)

    # Full analysis
    analysis = service.get_full_market_analysis("BTCUSDT", "linear")

    print(f"\n📊 Overall Sentiment: {analysis['overall_sentiment']}")
    print(f"   Confidence: {analysis['confidence'] * 100:.0f}%")

    print("\n📈 Open Interest:")
    oi = analysis.get("open_interest", {})
    print(f"   Change (24h): {oi.get('change_pct', 'N/A')}%")
    print(f"   Signal: {oi.get('signal', 'N/A')}")

    print("\n🔄 Long/Short Ratio:")
    ls = analysis.get("long_short_ratio", {})
    print(f"   Long: {ls.get('long_ratio', 'N/A')}%")
    print(f"   Short: {ls.get('short_ratio', 'N/A')}%")
    print(f"   Signal: {ls.get('signal', 'N/A')}")

    print("\n💰 Funding Rate:")
    fr = analysis.get("funding_rate", {})
    print(f"   Current: {fr.get('current_rate', 'N/A')}%")
    print(f"   7d Avg: {fr.get('avg_rate_7d', 'N/A')}%")
    print(f"   APR: {fr.get('annualized_apr', 'N/A')}%")

    print("\n📋 Recommendations:")
    for rec in analysis.get("recommendations", []):
        print(f"   {rec}")

    print("\n" + "=" * 70)
