"""
Trading-Specific MCP Tools

Pre-registered tools for trading analysis and strategy development.
Auto-registered on module import.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger

from backend.agents.mcp.tool_registry import get_tool_registry


# Get the global registry
registry = get_tool_registry()


# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================


@registry.register(
    name="calculate_rsi",
    description="Calculate Relative Strength Index (RSI)",
    category="indicators",
)
async def calculate_rsi(
    prices: List[float],
    period: int = 14,
) -> Dict[str, Any]:
    """
    Calculate RSI indicator.

    Args:
        prices: List of closing prices
        period: RSI period (default: 14)

    Returns:
        RSI value and interpretation
    """
    if len(prices) < period + 1:
        return {"error": f"Need at least {period + 1} prices", "rsi": None}

    prices_arr = np.array(prices)
    deltas = np.diff(prices_arr)

    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    # Interpretation
    if rsi > 70:
        interpretation = "overbought"
    elif rsi < 30:
        interpretation = "oversold"
    else:
        interpretation = "neutral"

    return {
        "rsi": round(rsi, 2),
        "period": period,
        "interpretation": interpretation,
    }


@registry.register(
    name="calculate_macd",
    description="Calculate MACD indicator with signal line",
    category="indicators",
)
async def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Dict[str, Any]:
    """
    Calculate MACD indicator.

    Args:
        prices: List of closing prices
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal line period

    Returns:
        MACD line, signal line, histogram, and interpretation
    """
    if len(prices) < slow_period + signal_period:
        return {"error": "Not enough data for MACD calculation"}

    prices_arr = np.array(prices)

    # Calculate EMAs
    def ema(data, period):
        alpha = 2 / (period + 1)
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    fast_ema = ema(prices_arr, fast_period)
    slow_ema = ema(prices_arr, slow_period)

    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line

    # Current values
    current_macd = macd_line[-1]
    current_signal = signal_line[-1]
    current_histogram = histogram[-1]

    # Interpretation
    if current_macd > current_signal and current_histogram > 0:
        interpretation = "bullish"
    elif current_macd < current_signal and current_histogram < 0:
        interpretation = "bearish"
    else:
        interpretation = "neutral"

    # Crossover detection
    if len(macd_line) >= 2:
        prev_macd = macd_line[-2]
        prev_signal = signal_line[-2]

        if prev_macd < prev_signal and current_macd > current_signal:
            crossover = "bullish_crossover"
        elif prev_macd > prev_signal and current_macd < current_signal:
            crossover = "bearish_crossover"
        else:
            crossover = None
    else:
        crossover = None

    return {
        "macd": round(current_macd, 4),
        "signal": round(current_signal, 4),
        "histogram": round(current_histogram, 4),
        "interpretation": interpretation,
        "crossover": crossover,
    }


@registry.register(
    name="calculate_bollinger_bands",
    description="Calculate Bollinger Bands",
    category="indicators",
)
async def calculate_bollinger_bands(
    prices: List[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> Dict[str, Any]:
    """
    Calculate Bollinger Bands.

    Args:
        prices: List of closing prices
        period: SMA period
        std_dev: Standard deviation multiplier

    Returns:
        Upper band, middle band, lower band, and band width
    """
    if len(prices) < period:
        return {"error": f"Need at least {period} prices"}

    prices_arr = np.array(prices[-period:])

    middle = np.mean(prices_arr)
    std = np.std(prices_arr)

    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)

    current_price = prices[-1]

    # Position within bands (0 = lower, 1 = upper)
    band_width = upper - lower
    position = (current_price - lower) / band_width if band_width > 0 else 0.5

    return {
        "upper": round(upper, 2),
        "middle": round(middle, 2),
        "lower": round(lower, 2),
        "band_width": round(band_width, 2),
        "band_width_percent": round((band_width / middle) * 100, 2),
        "position": round(position, 2),
        "current_price": current_price,
    }


@registry.register(
    name="calculate_atr",
    description="Calculate Average True Range (ATR)",
    category="indicators",
)
async def calculate_atr(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 14,
) -> Dict[str, Any]:
    """
    Calculate ATR for volatility measurement.

    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        period: ATR period

    Returns:
        ATR value and volatility interpretation
    """
    if len(high) < period + 1:
        return {"error": f"Need at least {period + 1} candles"}

    high_arr = np.array(high)
    low_arr = np.array(low)
    close_arr = np.array(close)

    # Calculate True Range
    tr = np.maximum(
        high_arr[1:] - low_arr[1:],
        np.maximum(
            np.abs(high_arr[1:] - close_arr[:-1]), np.abs(low_arr[1:] - close_arr[:-1])
        ),
    )

    # ATR (Simple moving average of TR)
    atr = np.mean(tr[-period:])

    # ATR as percentage of price
    current_price = close[-1]
    atr_percent = (atr / current_price) * 100

    # Volatility interpretation
    if atr_percent > 5:
        volatility = "high"
    elif atr_percent > 2:
        volatility = "medium"
    else:
        volatility = "low"

    return {
        "atr": round(atr, 4),
        "atr_percent": round(atr_percent, 2),
        "volatility": volatility,
        "current_price": current_price,
    }


# ============================================================================
# MARKET ANALYSIS
# ============================================================================


@registry.register(
    name="analyze_trend",
    description="Analyze market trend using multiple indicators",
    category="analysis",
)
async def analyze_trend(
    prices: List[float],
    high: Optional[List[float]] = None,
    low: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Comprehensive trend analysis.

    Args:
        prices: List of closing prices
        high: Optional list of high prices
        low: Optional list of low prices

    Returns:
        Trend direction, strength, and supporting evidence
    """
    if len(prices) < 50:
        return {"error": "Need at least 50 candles for analysis"}

    prices_arr = np.array(prices)

    # Calculate moving averages
    sma_20 = np.mean(prices_arr[-20:])
    sma_50 = np.mean(prices_arr[-50:])

    current_price = prices[-1]

    # Price position relative to MAs
    above_sma_20 = current_price > sma_20
    above_sma_50 = current_price > sma_50
    sma_20_above_50 = sma_20 > sma_50

    # Calculate trend strength
    price_change_20 = ((current_price - prices[-20]) / prices[-20]) * 100
    price_change_50 = ((current_price - prices[-50]) / prices[-50]) * 100

    # Determine trend
    if above_sma_20 and above_sma_50 and sma_20_above_50:
        trend = "uptrend"
        strength = min(abs(price_change_20) / 10, 1.0)
    elif not above_sma_20 and not above_sma_50 and not sma_20_above_50:
        trend = "downtrend"
        strength = min(abs(price_change_20) / 10, 1.0)
    else:
        trend = "sideways"
        strength = 0.3

    # Higher highs / Lower lows analysis
    if high and low and len(high) >= 20:
        recent_highs = high[-20:]
        recent_lows = low[-20:]

        higher_highs = sum(
            1 for i in range(5, 20) if max(recent_highs[i - 5 : i]) < recent_highs[i]
        )
        lower_lows = sum(
            1 for i in range(5, 20) if min(recent_lows[i - 5 : i]) > recent_lows[i]
        )

        structure = {
            "higher_highs": higher_highs,
            "lower_lows": lower_lows,
        }
    else:
        structure = None

    return {
        "trend": trend,
        "strength": round(strength, 2),
        "current_price": current_price,
        "sma_20": round(sma_20, 2),
        "sma_50": round(sma_50, 2),
        "price_change_20d": round(price_change_20, 2),
        "price_change_50d": round(price_change_50, 2),
        "price_above_sma_20": above_sma_20,
        "price_above_sma_50": above_sma_50,
        "structure": structure,
    }


@registry.register(
    name="find_support_resistance",
    description="Identify support and resistance levels",
    category="analysis",
)
async def find_support_resistance(
    high: List[float],
    low: List[float],
    close: List[float],
    num_levels: int = 3,
) -> Dict[str, Any]:
    """
    Find key support and resistance levels.

    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        num_levels: Number of levels to find

    Returns:
        Support and resistance levels with strength
    """
    if len(high) < 20:
        return {"error": "Need at least 20 candles"}

    # Find local maxima (resistance) and minima (support)
    window = 5

    resistances = []
    supports = []

    for i in range(window, len(high) - window):
        # Local maximum
        if high[i] == max(high[i - window : i + window + 1]):
            resistances.append(high[i])

        # Local minimum
        if low[i] == min(low[i - window : i + window + 1]):
            supports.append(low[i])

    # Cluster nearby levels
    def cluster_levels(levels, threshold_pct=0.5):
        if not levels:
            return []

        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]

        for level in levels[1:]:
            if (level - current_cluster[-1]) / current_cluster[
                -1
            ] * 100 < threshold_pct:
                current_cluster.append(level)
            else:
                clusters.append(
                    {
                        "level": np.mean(current_cluster),
                        "touches": len(current_cluster),
                    }
                )
                current_cluster = [level]

        clusters.append(
            {
                "level": np.mean(current_cluster),
                "touches": len(current_cluster),
            }
        )

        return sorted(clusters, key=lambda x: x["touches"], reverse=True)[:num_levels]

    current_price = close[-1]

    support_levels = cluster_levels(supports)
    resistance_levels = cluster_levels(resistances)

    # Find nearest levels
    nearest_support = None
    nearest_resistance = None

    for s in support_levels:
        if s["level"] < current_price:
            if nearest_support is None or s["level"] > nearest_support["level"]:
                nearest_support = s

    for r in resistance_levels:
        if r["level"] > current_price:
            if nearest_resistance is None or r["level"] < nearest_resistance["level"]:
                nearest_resistance = r

    return {
        "current_price": current_price,
        "support_levels": [
            {"level": round(s["level"], 2), "strength": s["touches"]}
            for s in support_levels
        ],
        "resistance_levels": [
            {"level": round(r["level"], 2), "strength": r["touches"]}
            for r in resistance_levels
        ],
        "nearest_support": {
            "level": round(nearest_support["level"], 2),
            "distance_percent": round(
                (current_price - nearest_support["level"]) / current_price * 100, 2
            ),
        }
        if nearest_support
        else None,
        "nearest_resistance": {
            "level": round(nearest_resistance["level"], 2),
            "distance_percent": round(
                (nearest_resistance["level"] - current_price) / current_price * 100, 2
            ),
        }
        if nearest_resistance
        else None,
    }


# ============================================================================
# RISK MANAGEMENT
# ============================================================================


@registry.register(
    name="calculate_position_size",
    description="Calculate optimal position size based on risk parameters",
    category="risk",
)
async def calculate_position_size(
    account_balance: float,
    risk_percent: float,
    entry_price: float,
    stop_loss_price: float,
    leverage: float = 1.0,
) -> Dict[str, Any]:
    """
    Calculate position size based on risk management rules.

    Args:
        account_balance: Total account balance
        risk_percent: Risk percentage per trade (e.g., 1.0 = 1%)
        entry_price: Entry price
        stop_loss_price: Stop loss price
        leverage: Leverage multiplier

    Returns:
        Position size, risk amount, and R:R metrics
    """
    # Validate inputs
    if risk_percent <= 0 or risk_percent > 10:
        return {"error": "Risk percent should be between 0 and 10"}

    if entry_price <= 0 or stop_loss_price <= 0:
        return {"error": "Prices must be positive"}

    # Calculate risk per unit
    risk_per_unit = abs(entry_price - stop_loss_price)
    risk_percent_trade = (risk_per_unit / entry_price) * 100

    # Risk amount in account currency
    risk_amount = account_balance * (risk_percent / 100)

    # Position size calculation
    position_size = risk_amount / risk_per_unit

    # With leverage
    position_value = position_size * entry_price
    margin_required = position_value / leverage

    # Check if margin is available
    if margin_required > account_balance:
        max_position = (account_balance * leverage) / entry_price
        position_size = min(position_size, max_position)
        margin_required = (position_size * entry_price) / leverage

    return {
        "position_size": round(position_size, 6),
        "position_value": round(position_size * entry_price, 2),
        "risk_amount": round(risk_amount, 2),
        "risk_percent": risk_percent,
        "margin_required": round(margin_required, 2),
        "leverage": leverage,
        "stop_loss_distance_percent": round(risk_percent_trade, 2),
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
    }


@registry.register(
    name="calculate_risk_reward",
    description="Calculate risk-reward ratio for a trade setup",
    category="risk",
)
async def calculate_risk_reward(
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
) -> Dict[str, Any]:
    """
    Calculate risk-reward ratio.

    Args:
        entry_price: Entry price
        stop_loss_price: Stop loss price
        take_profit_price: Take profit price

    Returns:
        Risk-reward ratio and trade setup analysis
    """
    # Determine trade direction
    is_long = take_profit_price > entry_price

    # Calculate distances
    risk = abs(entry_price - stop_loss_price)
    reward = abs(take_profit_price - entry_price)

    # Validate setup
    if is_long and stop_loss_price >= entry_price:
        return {"error": "For long: stop loss should be below entry"}
    if not is_long and stop_loss_price <= entry_price:
        return {"error": "For short: stop loss should be above entry"}

    if risk == 0:
        return {"error": "Risk cannot be zero"}

    rr_ratio = reward / risk

    # Calculate breakeven win rate
    breakeven_winrate = 1 / (1 + rr_ratio) * 100

    # Trade quality assessment
    if rr_ratio >= 3:
        quality = "excellent"
    elif rr_ratio >= 2:
        quality = "good"
    elif rr_ratio >= 1:
        quality = "acceptable"
    else:
        quality = "poor"

    return {
        "direction": "long" if is_long else "short",
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "risk": round(risk, 4),
        "reward": round(reward, 4),
        "risk_reward_ratio": round(rr_ratio, 2),
        "risk_percent": round((risk / entry_price) * 100, 2),
        "reward_percent": round((reward / entry_price) * 100, 2),
        "breakeven_winrate": round(breakeven_winrate, 1),
        "quality": quality,
    }


logger.info(
    f"📊 Trading MCP Tools registered: {len(registry.list_tools(category='indicators'))} indicators, "
    f"{len(registry.list_tools(category='analysis'))} analysis, "
    f"{len(registry.list_tools(category='risk'))} risk tools"
)
