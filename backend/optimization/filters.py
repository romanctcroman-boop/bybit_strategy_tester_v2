"""
Optimization Filters.

Result filtering by static and dynamic constraints.
Extracted from optimizations.py for testability and reuse.
"""

from __future__ import annotations


def passes_filters(result: dict, request_params: dict) -> bool:
    """
    Check if a result passes all configured filters.

    Checks:
    1. min_trades — minimum number of trades
    2. max_drawdown_limit — max drawdown (fraction 0-1 from request, result in %)
    3. min_profit_factor — minimum profit factor
    4. min_win_rate — minimum win rate (fraction 0-1 from request, result in %)
    5. constraints — dynamic constraints from EvaluationCriteriaPanel

    Args:
        result: Dict with backtest metric values.
        request_params: Dict with filter thresholds.

    Returns:
        True if result passes all filters.
    """
    # Minimum trades
    min_trades = request_params.get("min_trades")
    if min_trades is not None and (result.get("total_trades", 0) or 0) < min_trades:
        return False

    # Max drawdown (limit as fraction 0-1, result as percentage)
    max_dd_limit = request_params.get("max_drawdown_limit")
    if max_dd_limit is not None:
        max_dd_pct = abs(result.get("max_drawdown", 0) or 0)
        max_dd_limit_pct = max_dd_limit * 100
        if max_dd_pct > max_dd_limit_pct:
            return False

    # Minimum Profit Factor
    min_pf = request_params.get("min_profit_factor")
    if min_pf is not None and (result.get("profit_factor", 0) or 0) < min_pf:
        return False

    # Minimum Win Rate (limit as fraction 0-1, result as percentage)
    min_wr = request_params.get("min_win_rate")
    if min_wr is not None:
        win_rate_pct = result.get("win_rate", 0) or 0
        win_rate_fraction = win_rate_pct / 100.0
        if win_rate_fraction < min_wr:
            return False

    # Dynamic constraints from frontend EvaluationCriteriaPanel
    constraints = request_params.get("constraints")
    return not (constraints and not passes_dynamic_constraints(result, constraints))


def passes_dynamic_constraints(result: dict, constraints: list[dict]) -> bool:
    """
    Check if result passes all dynamic constraints from frontend.

    Args:
        result: Dict with metric values.
        constraints: List of {"metric": str, "operator": str, "value": float}.
                     Operators: <=, >=, <, >, ==, !=

    Returns:
        True if all constraints pass.
    """
    for constraint in constraints:
        metric = constraint.get("metric")
        operator = constraint.get("operator")
        threshold = constraint.get("value")

        if not all([metric, operator, threshold is not None]):
            continue

        # Get metric value from result
        value = result.get(metric, 0) or 0

        # For negative drawdown values, use absolute
        if metric in ("max_drawdown", "avg_drawdown") and value < 0:
            value = abs(value)

        # Apply operator
        try:
            if (
                (operator == "<=" and value > threshold)
                or (operator == ">=" and value < threshold)
                or (operator == "<" and value >= threshold)
                or (operator == ">" and value <= threshold)
                or (operator == "==" and value != threshold)
                or (operator == "!=" and value == threshold)
            ):
                return False
        except (TypeError, ValueError):
            continue

    return True
