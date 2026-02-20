"""
Optimization Scoring Functions.

Composite score calculation and multi-criteria ranking.
Extracted from optimizations.py for testability and reuse.
"""

from __future__ import annotations


def calculate_composite_score(result: dict, metric: str, weights: dict | None = None) -> float:
    """
    Calculate composite score for a backtest result.

    Supports all 20 metrics from EvaluationCriteriaPanel:
    - Performance: total_return, cagr, sharpe_ratio, sortino_ratio, calmar_ratio
    - Risk: max_drawdown, avg_drawdown, volatility, var_95, risk_adjusted_return
    - Trade quality: win_rate, profit_factor, avg_win, avg_loss, expectancy, payoff_ratio
    - Activity: total_trades, trades_per_month, avg_trade_duration, avg_bars_in_trade

    Args:
        result: Dict with backtest metric values.
        metric: Name of the metric to optimize.
        weights: Optional dict of metric weights for composite scoring.

    Returns:
        Score value (higher = better for all metrics).

    Note:
        max_drawdown comes in PERCENT (17.29 = 17.29%).
    """
    total_return = result.get("total_return", 0) or 0
    sharpe_ratio = result.get("sharpe_ratio", 0) or 0
    net_profit = result.get("net_profit", 0) or 0
    max_drawdown_pct = abs(result.get("max_drawdown", 0) or 0)
    max_drawdown = max_drawdown_pct / 100.0
    win_rate_pct = result.get("win_rate", 0) or 0
    profit_factor = result.get("profit_factor", 0) or 0  # 0 for losers, not 1

    # Simple metrics (higher = better)
    if metric == "net_profit":
        return net_profit
    elif metric == "sharpe_ratio":
        return sharpe_ratio
    elif metric == "sortino_ratio":
        return result.get("sortino_ratio", 0) or 0
    elif metric == "total_return":
        return total_return
    elif metric == "cagr":
        return result.get("cagr", 0) or 0
    elif metric == "win_rate":
        return win_rate_pct
    elif metric == "profit_factor":
        return profit_factor
    elif metric == "expectancy":
        return result.get("expectancy", 0) or 0
    elif metric == "recovery_factor":
        return result.get("recovery_factor", 0) or 0
    elif metric == "avg_win":
        return result.get("avg_win", 0) or 0
    elif metric == "payoff_ratio":
        return result.get("payoff_ratio", 0) or 0
    elif metric == "total_trades":
        return result.get("total_trades", 0) or 0
    elif metric == "trades_per_month":
        return result.get("trades_per_month", 0) or 0

    # Inverted metrics (lower = better, return negative for sorting)
    elif metric == "max_drawdown":
        return -max_drawdown_pct
    elif metric == "avg_drawdown":
        return -(abs(result.get("avg_drawdown", 0) or 0))
    elif metric == "avg_loss":
        return -(abs(result.get("avg_loss", 0) or 0))
    elif metric == "volatility":
        return -(abs(result.get("volatility", 0) or 0))
    elif metric == "var_95":
        return -(abs(result.get("var_95", 0) or 0))

    # Activity metrics (neutral - return raw value)
    elif metric == "avg_trade_duration":
        return result.get("avg_trade_duration", 0) or result.get("avg_bars_in_trade", 0) or 0
    elif metric == "avg_bars_in_trade":
        return result.get("avg_bars_in_trade", 0) or 0

    # Computed composite metrics
    elif metric == "calmar_ratio":
        if max_drawdown_pct > 0.01:
            return total_return / max_drawdown_pct
        return total_return * 10 if total_return > 0 else total_return
    elif metric == "risk_adjusted_return":
        drawdown_factor = 1 + max_drawdown
        return total_return / drawdown_factor

    # Default — net_profit
    return net_profit


def rank_by_multi_criteria(results: list[dict], selection_criteria: list[str]) -> list[dict]:
    """
    Rank results by multiple criteria using average rank method.

    For each criterion, assigns ranks (1=best). The overall score
    is the average rank across all criteria. Lower = better.

    Args:
        results: List of result dicts with metric values.
        selection_criteria: List of metric names to rank by.

    Returns:
        Sorted list (best first) with '_avg_rank' field added.
    """
    if not results or not selection_criteria:
        return results

    # Direction: True = higher is better, False = lower is better
    criteria_direction = {
        # Performance (higher = better)
        "net_profit": True,
        "total_return": True,
        "cagr": True,
        "sharpe_ratio": True,
        "sortino_ratio": True,
        "calmar_ratio": True,
        "risk_adjusted_return": True,
        # Risk (lower = better)
        "max_drawdown": False,
        "avg_drawdown": False,
        "volatility": False,
        "var_95": False,
        # Trade quality
        "win_rate": True,
        "profit_factor": True,
        "avg_win": True,
        "avg_loss": False,
        "expectancy": True,
        "payoff_ratio": True,
        "recovery_factor": True,
        # Activity
        "total_trades": True,
        "trades_per_month": True,
        "avg_trade_duration": True,
        "avg_bars_in_trade": True,
    }

    n = len(results)

    # Calculate ranks for each criterion
    for criterion in selection_criteria:
        if criterion not in criteria_direction:
            continue

        higher_is_better = criteria_direction[criterion]

        # For max_drawdown, use absolute value for ranking
        def get_value(r, crit=criterion):
            if crit == "max_drawdown":
                return abs(r.get(crit, 0) or 0)
            return r.get(crit, 0) or 0

        # Sort indices by criterion value
        sorted_indices = sorted(
            range(n),
            key=lambda i, gv=get_value: gv(results[i]),
            reverse=higher_is_better,
        )

        # Assign ranks (1-based)
        for rank, idx in enumerate(sorted_indices, 1):
            if "_ranks" not in results[idx]:
                results[idx]["_ranks"] = {}
            results[idx]["_ranks"][criterion] = rank

    # Calculate average rank
    for r in results:
        ranks = r.get("_ranks", {})
        if ranks:
            r["_avg_rank"] = sum(ranks.values()) / len(ranks)
        else:
            r["_avg_rank"] = float("inf")

    # Sort by average rank (lower = better)
    results.sort(key=lambda x: x.get("_avg_rank", float("inf")))

    # Set score as negative average rank (for compatibility with existing sort)
    for r in results:
        r["score"] = -r.get("_avg_rank", float("inf"))

    # Cleanup temp fields
    for r in results:
        r.pop("_ranks", None)
        r.pop("_avg_rank", None)

    return results


def apply_custom_sort_order(results: list[dict], sort_order: list[dict]) -> list[dict]:
    """
    Apply custom multi-level sort from frontend EvaluationCriteriaPanel.

    Args:
        results: List of result dicts.
        sort_order: List of {"metric": str, "direction": "asc"|"desc"}.

    Returns:
        Sorted list of results.
    """
    if not results or not sort_order:
        return results

    # Build composite sort key
    def sort_key(item):
        keys = []
        for so in sort_order:
            metric = so.get("metric", "")
            direction = so.get("direction", "desc")
            value = item.get(metric, 0) or 0
            # Negate for descending so sorted() works correctly
            keys.append(-value if direction == "desc" else value)
        return tuple(keys)

    return sorted(results, key=sort_key)
