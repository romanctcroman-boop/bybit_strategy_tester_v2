"""
Smart Recommendations Generator.

Analyzes optimization results and generates balanced/conservative/aggressive
recommendations.
"""

from __future__ import annotations


def generate_smart_recommendations(results: list[dict]) -> dict:
    """
    Generate smart recommendations based on optimization results.

    Analyzes all results and suggests best variants:
    - best_balanced: max Calmar Ratio (Return / Drawdown)
    - best_conservative: min drawdown among profitable
    - best_aggressive: max return

    Args:
        results: List of result dicts with metrics.

    Returns:
        Dict with best_balanced, best_conservative, best_aggressive,
        recommendation_text.
    """
    if not results:
        return {
            "best_balanced": None,
            "best_conservative": None,
            "best_aggressive": None,
            "recommendation_text": "Нет результатов для анализа",
        }

    # Filter profitable results
    profitable = [r for r in results if r.get("total_return", 0) > 0]

    recommendations = {
        "best_balanced": None,
        "best_conservative": None,
        "best_aggressive": None,
        "recommendation_text": "",
    }

    if not profitable:
        sorted_by_return = sorted(results, key=lambda x: x.get("total_return", -999), reverse=True)
        if sorted_by_return:
            recommendations["best_balanced"] = sorted_by_return[0]
            recommendations["recommendation_text"] = (
                "⚠️ Все комбинации убыточны. Рекомендуем изменить параметры стратегии или период тестирования."
            )
        return recommendations

    # 1. BALANCED — max Calmar Ratio (Return / Drawdown)
    for r in profitable:
        dd = abs(r.get("max_drawdown", 1)) or 1
        r["_calmar"] = r.get("total_return", 0) / dd

    sorted_by_calmar = sorted(profitable, key=lambda x: x.get("_calmar", 0), reverse=True)
    recommendations["best_balanced"] = sorted_by_calmar[0] if sorted_by_calmar else None

    # 2. CONSERVATIVE — min drawdown among profitable
    sorted_by_dd = sorted(profitable, key=lambda x: abs(x.get("max_drawdown", 999)))
    recommendations["best_conservative"] = sorted_by_dd[0] if sorted_by_dd else None

    # 3. AGGRESSIVE — max return
    sorted_by_return = sorted(profitable, key=lambda x: x.get("total_return", 0), reverse=True)
    recommendations["best_aggressive"] = sorted_by_return[0] if sorted_by_return else None

    # Generate recommendation text
    balanced = recommendations["best_balanced"]
    conservative = recommendations["best_conservative"]
    aggressive = recommendations["best_aggressive"]

    texts = []

    if balanced:
        texts.append(
            f"🎯 **Сбалансированный**: {_format_params(balanced)} - "
            f"Return {balanced.get('total_return', 0):.1f}%, DD {abs(balanced.get('max_drawdown', 0)):.1f}%"
        )

    if conservative and conservative != balanced:
        texts.append(
            f"🛡️ **Консервативный**: {_format_params(conservative)} - "
            f"Return {conservative.get('total_return', 0):.1f}%, DD {abs(conservative.get('max_drawdown', 0)):.1f}%"
        )

    if aggressive and aggressive != balanced:
        texts.append(
            f"🚀 **Агрессивный**: {_format_params(aggressive)} - "
            f"Return {aggressive.get('total_return', 0):.1f}%, DD {abs(aggressive.get('max_drawdown', 0)):.1f}%"
        )

    recommendations["recommendation_text"] = "\n".join(texts)

    # Cleanup temp fields
    for r in profitable:
        r.pop("_calmar", None)

    return recommendations


def _format_params(r: dict) -> str:
    """Format strategy parameters for display."""
    p = r.get("params", {})

    # Universal formatting — detect strategy type from params
    parts = []

    # RSI-style params
    if "rsi_period" in p:
        parts.append(f"RSI({p.get('rsi_period')}, {p.get('rsi_overbought')}, {p.get('rsi_oversold')})")
    # EMA-style params
    elif "fast_period" in p:
        parts.append(f"EMA({p.get('fast_period')}, {p.get('slow_period')})")
    # MACD-style params
    elif "macd_fast" in p:
        parts.append(f"MACD({p.get('macd_fast')}, {p.get('macd_slow')}, {p.get('macd_signal')})")
    # Bollinger-style params
    elif "bb_period" in p:
        parts.append(f"BB({p.get('bb_period')}, {p.get('bb_std')})")
    # Generic — list all numeric params
    else:
        for k, v in p.items():
            if k not in ("stop_loss_pct", "take_profit_pct") and isinstance(v, (int, float)):
                parts.append(f"{k}={v}")

    # Add SL/TP if present
    sl = p.get("stop_loss_pct")
    tp = p.get("take_profit_pct")
    if sl or tp:
        parts.append(f"SL={sl}%, TP={tp}%")

    return ", ".join(parts) if parts else str(p)
