"""
Risk Management Tools

Position sizing and risk-reward calculation.
Auto-registered with the global MCP tool registry on import.
"""

from __future__ import annotations

from typing import Any

from backend.agents.mcp.tool_registry import get_tool_registry

registry = get_tool_registry()


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
) -> dict[str, Any]:
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
    if risk_percent <= 0 or risk_percent > 10:
        return {"error": "Risk percent should be between 0 and 10"}

    if entry_price <= 0 or stop_loss_price <= 0:
        return {"error": "Prices must be positive"}

    risk_per_unit = abs(entry_price - stop_loss_price)
    risk_percent_trade = (risk_per_unit / entry_price) * 100

    risk_amount = account_balance * (risk_percent / 100)
    position_size = risk_amount / risk_per_unit

    position_value = position_size * entry_price
    margin_required = position_value / leverage

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
) -> dict[str, Any]:
    """
    Calculate risk-reward ratio.

    Args:
        entry_price: Entry price
        stop_loss_price: Stop loss price
        take_profit_price: Take profit price

    Returns:
        Risk-reward ratio and trade setup analysis
    """
    is_long = take_profit_price > entry_price

    risk = abs(entry_price - stop_loss_price)
    reward = abs(take_profit_price - entry_price)

    if is_long and stop_loss_price >= entry_price:
        return {"error": "For long: stop loss should be below entry"}
    if not is_long and stop_loss_price <= entry_price:
        return {"error": "For short: stop loss should be above entry"}

    if risk == 0:
        return {"error": "Risk cannot be zero"}

    rr_ratio = reward / risk
    breakeven_winrate = 1 / (1 + rr_ratio) * 100

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
