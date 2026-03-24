"""
Topology utilities for the Strategy Builder graph.

Provides:
- BLOCK_CATEGORY_MAP  — block_type → category lookup
- infer_category()    — fallback category inference
- build_execution_order() — topological sort (Kahn's algorithm)

All functions are pure (no side-effects, no class dependencies).
"""

from __future__ import annotations

from collections import deque

from loguru import logger

# ---------------------------------------------------------------------------
# Block type → category mapping
# ---------------------------------------------------------------------------

BLOCK_CATEGORY_MAP: dict[str, str] = {
    # Input blocks
    "price": "input",
    "volume": "input",
    "constant": "input",
    "candle_data": "input",
    # Indicator blocks
    "rsi": "indicator",
    "ema": "indicator",
    "sma": "indicator",
    "wma": "indicator",
    "dema": "indicator",
    "tema": "indicator",
    "hull_ma": "indicator",
    "macd": "indicator",
    "bollinger": "indicator",
    "atr": "indicator",
    "stochastic": "indicator",
    "stoch_rsi": "indicator",
    "adx": "indicator",
    "cci": "indicator",
    "mfi": "indicator",
    "obv": "indicator",
    "williams_r": "indicator",
    "roc": "indicator",
    "supertrend": "indicator",
    "ichimoku": "indicator",
    "keltner": "indicator",
    "donchian": "indicator",
    "vwap": "indicator",
    "parabolic_sar": "indicator",
    "pivot_points": "indicator",
    "cmf": "indicator",
    "cmo": "indicator",
    "pvt": "indicator",
    "ad_line": "indicator",
    "aroon": "indicator",
    "stddev": "indicator",
    "atrp": "indicator",
    "qqe": "indicator",
    "mtf": "indicator",
    "momentum": "indicator",
    # Condition blocks
    "crossover": "condition",
    "crossunder": "condition",
    "greater_than": "condition",
    "less_than": "condition",
    "between": "condition",
    "equals": "condition",
    "threshold": "condition",
    "compare": "condition",
    "cross": "condition",
    # Logic blocks
    "and": "logic",
    "or": "logic",
    "not": "logic",
    "delay": "logic",
    "filter": "logic",
    "comparison": "logic",
    # Action blocks
    "buy": "action",
    "buy_market": "action",
    "buy_limit": "action",
    "sell": "action",
    "sell_market": "action",
    "sell_limit": "action",
    "close_long": "action",
    "close_short": "action",
    "close_all": "action",
    "stop_loss": "action",
    "take_profit": "action",
    "trailing_stop": "action",
    "break_even": "action",
    "profit_lock": "action",
    "scale_out": "action",
    "multi_tp": "action",
    "atr_stop": "action",
    "chandelier_stop": "action",
    "static_sltp": "exit",
    # Filter blocks
    "rsi_filter": "filter",
    "two_ma_filter": "filter",
    "time_filter": "filter",
    "volatility_filter": "filter",
    "adx_filter": "filter",
    "session_filter": "filter",
    # Exit blocks
    "trailing_stop_exit": "exit",
    "atr_exit": "exit",
    "multi_tp_exit": "multiple_tp",
    # Position sizing
    "fixed_size": "sizing",
    "percent_balance": "sizing",
    "risk_percent": "sizing",
    # Signal blocks
    "long_entry": "signal",
    "short_entry": "signal",
    "long_exit": "signal",
    "short_exit": "signal",
    "buy_signal": "signal",
    "sell_signal": "signal",
    # Strategy aggregator
    "strategy": "strategy",
    # DCA/Grid
    "dca_grid": "dca_grid",
    "dca": "dca_grid",
    # Price action
    "engulfing": "price_action",
    "hammer": "price_action",
    "doji": "price_action",
    "pinbar": "price_action",
    # Divergence
    "divergence": "divergence",
    # Close condition blocks
    "close_by_time": "close_conditions",
    "close_channel": "close_conditions",
    "close_ma_cross": "close_conditions",
    "close_rsi": "close_conditions",
    "close_stochastic": "close_conditions",
    "close_psar": "close_conditions",
    # Universal filters / indicators
    "atr_volatility": "indicator",
    "volume_filter": "indicator",
    "highest_lowest_bar": "indicator",
    "two_mas": "indicator",
    "accumulation_areas": "indicator",
    "keltner_bollinger": "indicator",
    "rvi_filter": "indicator",
    "mfi_filter": "indicator",
    "cci_filter": "indicator",
    "momentum_filter": "indicator",
}


def infer_category(block_type: str) -> str:
    """Infer block category from block type when category field is missing.

    Args:
        block_type: The block's ``type`` field value (e.g. ``"rsi"``, ``"crossover"``).

    Returns:
        Category string (e.g. ``"indicator"``, ``"condition"``, ``"action"``).
        Falls back to ``"indicator"`` when the type is completely unknown.
    """
    if block_type in BLOCK_CATEGORY_MAP:
        return BLOCK_CATEGORY_MAP[block_type]
    # Heuristic fallback for prefixed types
    for prefix, cat in [
        ("indicator_", "indicator"),
        ("condition_", "condition"),
        ("action_", "action"),
        ("filter_", "filter"),
    ]:
        if block_type.startswith(prefix):
            return cat
    logger.warning(f"Cannot infer category for block type '{block_type}', defaulting to 'indicator'")
    return "indicator"


def build_execution_order(
    blocks: dict[str, dict],
    connections: list[dict[str, str]],
) -> list[str]:
    """Build a topological sort of blocks based on their connections.

    Uses Kahn's algorithm.  Disconnected blocks are appended after
    connected ones.  Cycles are detected and logged as warnings — the
    cyclic blocks are still included so the strategy can produce partial
    results instead of aborting.

    Args:
        blocks: Mapping of block_id → block dict.
        connections: Normalized connection list (each item has
            ``source_id`` and ``target_id`` string keys).

    Returns:
        List of block IDs in a valid execution order.
    """
    # Build dependency graph: each block → list of blocks it depends on
    dependencies: dict[str, list[str]] = {block_id: [] for block_id in blocks}

    for conn in connections:
        source_id = conn["source_id"]
        target_id = conn["target_id"]
        if target_id in dependencies and source_id:
            dependencies[target_id].append(source_id)

    # Kahn's algorithm
    in_degree = {block_id: len(deps) for block_id, deps in dependencies.items()}
    queue = deque(block_id for block_id, degree in in_degree.items() if degree == 0)
    result: list[str] = []

    while queue:
        block_id = queue.popleft()
        result.append(block_id)

        for conn in connections:
            if conn["source_id"] == block_id:
                target_id = conn["target_id"]
                if target_id in in_degree:
                    in_degree[target_id] -= 1
                    if in_degree[target_id] == 0:
                        queue.append(target_id)

    # Append remaining blocks — distinguish disconnected from cyclic
    remaining = [bid for bid in blocks if bid not in result]
    if remaining:
        connected_block_ids = {c["source_id"] for c in connections} | {c["target_id"] for c in connections}
        cyclic = [bid for bid in remaining if bid in connected_block_ids and in_degree.get(bid, 0) > 0]
        if cyclic:
            logger.warning(
                "Cycle detected in strategy graph -- blocks {} have "
                "unsatisfied dependencies and may produce incorrect signals. "
                "Break the cycle by removing a connection.",
                cyclic,
            )
        result.extend(remaining)

    return result
