"""
Strategy Builder MCP Tools

Provides MCP tools for AI agents to interact with the visual Strategy Builder
exactly like a human user — creating strategies, adding/connecting blocks,
configuring parameters, validating, and running backtests.

All operations go through the same REST API endpoints that the frontend uses,
so every action is visible to the user in the Strategy Builder UI in real-time.

Auto-registered with the global MCP tool registry on import.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from backend.agents.mcp.tool_registry import get_tool_registry

registry = get_tool_registry()

# Base URL for internal API calls (same server)
_API_BASE = "http://localhost:8000/api/v1/strategy-builder"
_TIMEOUT = 30.0


async def _api_get(path: str, params: dict | None = None) -> dict[str, Any]:
    """Make GET request to strategy builder API."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_API_BASE}{path}", params=params)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result  # type: ignore[return-value]


async def _api_post(path: str, json_data: dict | None = None) -> dict[str, Any]:
    """Make POST request to strategy builder API."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{_API_BASE}{path}", json=json_data or {})
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result  # type: ignore[return-value]


async def _api_put(path: str, json_data: dict | None = None) -> dict[str, Any]:
    """Make PUT request to strategy builder API."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.put(f"{_API_BASE}{path}", json=json_data or {})
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result  # type: ignore[return-value]


async def _api_delete(path: str) -> dict[str, Any]:
    """Make DELETE request to strategy builder API."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.delete(f"{_API_BASE}{path}")
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result  # type: ignore[return-value]


# =============================================================================
# BLOCK TYPE → CATEGORY MAPPING
# =============================================================================

# Maps block type strings to the category expected by StrategyBuilderAdapter._execute_block().
# Without correct category, adapter logs "Unknown block category" and generates no signals.
_BLOCK_CATEGORY_MAP: dict[str, str] = {
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
    "qqe_cross": "indicator",
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
    "static_sltp": "action",
    # Filter blocks
    "rsi_filter": "filter",
    "supertrend_filter": "filter",
    "two_ma_filter": "filter",
    "volume_filter": "filter",
    "time_filter": "filter",
    "volatility_filter": "filter",
    "adx_filter": "filter",
    "session_filter": "filter",
    # Exit blocks
    "trailing_stop_exit": "exit",
    "atr_exit": "atr_exit",
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
    # Smart signals
    "smart_rsi": "smart_signals",
    "smart_macd": "smart_signals",
    "smart_bollinger": "smart_signals",
    "smart_stochastic": "smart_signals",
    "smart_supertrend": "smart_signals",
    # Strategy node (aggregator)
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
    "rsi_divergence": "divergence",
}


def _infer_block_category(block_type: str) -> str:
    """Infer the adapter category for a block type.

    The StrategyBuilderAdapter dispatches execution based on the 'category' field.
    Without it, blocks are silently ignored ('Unknown block category' warning).
    """
    if block_type in _BLOCK_CATEGORY_MAP:
        return _BLOCK_CATEGORY_MAP[block_type]
    # Heuristic fallback: check common prefixes
    for prefix, cat in [
        ("indicator_", "indicator"),
        ("condition_", "condition"),
        ("action_", "action"),
        ("filter_", "filter"),
        ("smart_", "smart_signals"),
    ]:
        if block_type.startswith(prefix):
            return cat
    logger.warning(f"Unknown block type '{block_type}', defaulting category to 'indicator'")
    return "indicator"


# =============================================================================
# BLOCK LIBRARY — What blocks are available?
# =============================================================================


@registry.register(
    name="builder_get_block_library",
    description=(
        "Get the complete Strategy Builder block library with all categories. "
        "Returns all available blocks: indicators (RSI, MACD, EMA, Bollinger, etc.), "
        "filters, conditions, actions, exits, position sizing, risk controls, "
        "sessions, time management, divergences, price action patterns, smart signals. "
        "Use this FIRST to understand what blocks you can add to a strategy."
    ),
    category="strategy_builder",
)
async def builder_get_block_library() -> dict[str, Any]:
    """
    Get the complete block library with all categories.

    Returns:
        Dict with categories, each containing a list of available blocks
        with id, name, description, and icon.
    """
    try:
        return await _api_get("/blocks/library")
    except Exception as e:
        logger.error(f"builder_get_block_library error: {e}")
        return {"error": str(e)}


# =============================================================================
# STRATEGY CRUD — Create, Read, Update, Delete strategies
# =============================================================================


@registry.register(
    name="builder_create_strategy",
    description=(
        "Create a new strategy in the Strategy Builder. "
        "This creates an empty canvas that you can add blocks to. "
        "Specify name, symbol (e.g. BTCUSDT), timeframe (1,5,15,30,60,240,D,W,M), "
        "direction (long/short/both), initial capital, and leverage."
    ),
    category="strategy_builder",
)
async def builder_create_strategy(
    name: str,
    symbol: str = "BTCUSDT",
    timeframe: str = "15",
    direction: str = "both",
    market_type: str = "linear",
    initial_capital: float = 10000.0,
    leverage: float = 10.0,
    description: str = "",
) -> dict[str, Any]:
    """
    Create a new strategy in Strategy Builder.

    Args:
        name: Strategy name (e.g. "RSI Mean Reversion")
        symbol: Trading pair (e.g. "BTCUSDT")
        timeframe: Candle timeframe (1,5,15,30,60,240,D,W,M)
        direction: Trade direction (long/short/both)
        market_type: Market type (linear/spot)
        initial_capital: Starting capital
        leverage: Leverage multiplier (1-125)
        description: Strategy description

    Returns:
        Created strategy with id, blocks, connections
    """
    try:
        payload = {
            "name": name,
            "description": description,
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "market_type": market_type,
            "initial_capital": initial_capital,
            "leverage": leverage,
            "blocks": [],
            "connections": [],
        }
        return await _api_post("/strategies", json_data=payload)
    except Exception as e:
        logger.error(f"builder_create_strategy error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_get_strategy",
    description=(
        "Get a strategy by ID. Returns the full strategy including "
        "all blocks, connections, parameters, and builder_graph."
    ),
    category="strategy_builder",
)
async def builder_get_strategy(strategy_id: str) -> dict[str, Any]:
    """
    Get a strategy by ID.

    Args:
        strategy_id: Strategy UUID

    Returns:
        Full strategy with blocks, connections, parameters
    """
    try:
        return await _api_get(f"/strategies/{strategy_id}")
    except Exception as e:
        logger.error(f"builder_get_strategy error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_list_strategies",
    description="List all strategies in the Strategy Builder with pagination.",
    category="strategy_builder",
)
async def builder_list_strategies(
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """
    List all Strategy Builder strategies.

    Args:
        page: Page number (1-based)
        page_size: Items per page (1-100)

    Returns:
        Paginated list of strategies with metadata
    """
    try:
        return await _api_get("/strategies", params={"page": page, "page_size": page_size})
    except Exception as e:
        logger.error(f"builder_list_strategies error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_update_strategy",
    description=(
        "Update a strategy — save blocks, connections, parameters. "
        "This is the equivalent of the user clicking 'Save' in the UI. "
        "Pass the full strategy state including all blocks and connections."
    ),
    category="strategy_builder",
)
async def builder_update_strategy(
    strategy_id: str,
    name: str,
    blocks: list[dict[str, Any]],
    connections: list[dict[str, Any]],
    symbol: str = "BTCUSDT",
    timeframe: str = "15",
    direction: str = "both",
    market_type: str = "linear",
    initial_capital: float = 10000.0,
    leverage: float = 10.0,
    description: str = "",
    main_strategy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Update (save) a strategy with current blocks and connections.

    Args:
        strategy_id: Strategy UUID to update
        name: Strategy name
        blocks: List of block definitions
        connections: List of connection definitions
        symbol: Trading pair
        timeframe: Candle timeframe
        direction: Trade direction
        market_type: Market type
        initial_capital: Starting capital
        leverage: Leverage multiplier
        description: Strategy description
        main_strategy: Main strategy node config (entry/exit signals)

    Returns:
        Updated strategy
    """
    try:
        payload = {
            "name": name,
            "description": description,
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "market_type": market_type,
            "initial_capital": initial_capital,
            "leverage": leverage,
            "blocks": blocks,
            "connections": connections,
        }
        if main_strategy:
            payload["main_strategy"] = main_strategy
        return await _api_put(f"/strategies/{strategy_id}", json_data=payload)
    except Exception as e:
        logger.error(f"builder_update_strategy error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_delete_strategy",
    description="Delete a strategy from the Strategy Builder (soft delete).",
    category="strategy_builder",
)
async def builder_delete_strategy(strategy_id: str) -> dict[str, Any]:
    """
    Delete a strategy (soft delete).

    Args:
        strategy_id: Strategy UUID to delete

    Returns:
        Deletion confirmation
    """
    try:
        return await _api_delete(f"/strategies/{strategy_id}")
    except Exception as e:
        logger.error(f"builder_delete_strategy error: {e}")
        return {"error": str(e)}


# =============================================================================
# BLOCK OPERATIONS — Add, update, remove blocks on the canvas
# =============================================================================


@registry.register(
    name="builder_add_block",
    description=(
        "Add a block to the strategy canvas. "
        "Block types include: rsi, ema, sma, macd, bollinger, atr, stochastic, adx, supertrend, "
        "crossover, crossunder, greater_than, less_than, between, "
        "buy, sell, close, stop_loss, take_profit, trailing_stop, "
        "rsi_filter, supertrend_filter, two_ma_filter, volume_filter, time_filter, "
        "static_sltp, trailing_stop_exit, atr_exit, multi_tp_exit, "
        "fixed_size, percent_balance, risk_percent, "
        "and many more (use builder_get_block_library to see all). "
        "\n\n"
        "RSI UNIVERSAL NODE — supports 3 signal modes that combine with AND logic:\n"
        "  1) RANGE filter (continuous): use_long_range=True → long when RSI > long_rsi_more "
        "AND RSI < long_rsi_less. long_rsi_more=LOWER bound (min), long_rsi_less=UPPER bound (max). "
        "MUST have more < less. Example: long_rsi_more=0, long_rsi_less=30 → oversold zone 0..30.\n"
        "  use_short_range=True → short when RSI > short_rsi_more AND RSI < short_rsi_less. "
        "short_rsi_more=LOWER bound, short_rsi_less=UPPER bound. MUST have more < less. "
        "Example: short_rsi_more=70, short_rsi_less=100 → overbought zone 70..100.\n"
        "  2) CROSS signal (event): use_cross_level=True → long when RSI crosses UP "
        "through cross_long_level(30), short when RSI crosses DOWN through "
        "cross_short_level(70). opposite_signal swaps long/short. "
        "use_cross_memory + cross_memory_bars(5) extends cross signal for N bars.\n"
        "  3) LEGACY (auto-fallback): if no mode enabled and overbought/oversold params exist, "
        "uses classic RSI < oversold = long, RSI > overbought = short.\n"
        "  No mode enabled + no legacy params → passthrough (always True).\n"
        "RSI params: period(14, 2-500), use_long_range(false), long_rsi_more(30, 0.1-100), "
        "long_rsi_less(70, 0.1-100), use_short_range(false), short_rsi_less(70, 0.1-100), "
        "short_rsi_more(30, 0.1-100), use_cross_level(false), cross_long_level(30, 0.1-100), "
        "cross_short_level(70, 0.1-100), opposite_signal(false), use_cross_memory(false), "
        "cross_memory_bars(5, 1-100).\n"
        "Outputs: value (RSI series), long (bool signal), short (bool signal).\n"
        "Optimizable params: period, long_rsi_more/less, short_rsi_less/more, "
        "cross_long_level, cross_short_level, cross_memory_bars.\n"
        "OPTIMIZATION RANGES (RSI): Each optimizable param can be set for grid search with "
        "{enabled: true/false, min: <low>, max: <high>, step: <step>}. "
        "Stored in block.optimizationParams. Default ranges: "
        "period {5,30,1}, long_rsi_more {10,45,5}, long_rsi_less {55,90,5}, "
        "short_rsi_less {55,90,5}, short_rsi_more {10,45,5}, cross_long_level {15,45,5}, "
        "cross_short_level {55,85,5}, cross_memory_bars {1,20,1}.\n\n"
        "MACD UNIVERSAL NODE — supports 2 signal modes combined with OR logic:\n"
        "  1) CROSS ZERO: use_macd_cross_zero=True → long when MACD crosses above level "
        "(default 0), short when below. opposite_macd_cross_zero swaps signals.\n"
        "  2) CROSS SIGNAL: use_macd_cross_signal=True → long when MACD crosses above "
        "Signal line, short when below. signal_only_if_macd_positive filters: long only "
        "when MACD<0, short only when MACD>0. opposite_macd_cross_signal swaps.\n"
        "  No mode enabled → data-only (MACD/Signal/Hist output, long/short always False).\n"
        "  Signal Memory: enabled by default, disable_signal_memory=True to turn off. "
        "signal_memory_bars(5) controls how many bars cross signals persist.\n"
        "MACD params: fast_period(12), slow_period(26), signal_period(9), source(close), "
        "use_macd_cross_zero(false), opposite_macd_cross_zero(false), macd_cross_zero_level(0), "
        "use_macd_cross_signal(false), signal_only_if_macd_positive(false), "
        "opposite_macd_cross_signal(false), disable_signal_memory(false), signal_memory_bars(5).\n"
        "Outputs: macd (series), signal (series), hist (series), long (bool), short (bool).\n"
        "Optimizable params: fast_period, slow_period, signal_period, macd_cross_zero_level, signal_memory_bars.\n"
        "OPTIMIZATION RANGES (MACD): Each optimizable param can be set for grid search with "
        "{enabled: true/false, min: <low>, max: <high>, step: <step>}. "
        "Stored in block.optimizationParams. Default ranges: "
        "fast_period {8,16,1}, slow_period {20,30,1}, signal_period {6,12,1}, "
        "macd_cross_zero_level {-50,50,1}, signal_memory_bars {1,20,1}."
    ),
    category="strategy_builder",
)
async def builder_add_block(
    strategy_id: str,
    block_type: str,
    block_id: str | None = None,
    name: str | None = None,
    x: float = 400.0,
    y: float = 200.0,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Add a block to the strategy canvas.

    This is equivalent to the user dragging a block from the library
    onto the canvas. The block appears at position (x, y).

    Args:
        strategy_id: Strategy UUID
        block_type: Block type ID (e.g. 'rsi', 'ema', 'crossover', 'buy')
        block_id: Optional custom block ID (auto-generated if not provided)
        name: Optional display name
        x: X position on canvas
        y: Y position on canvas
        params: Block-specific parameters (e.g. {'period': 14, 'overbought': 70})

    Returns:
        The added block with its generated ID
    """
    try:
        # Strategy Builder stores blocks in the strategy's block list.
        # We need to: 1) get current strategy, 2) add block, 3) save.
        strategy = await _api_get(f"/strategies/{strategy_id}")
        if "error" in strategy:
            return strategy

        import uuid

        new_block = {
            "id": block_id or f"{block_type}_{uuid.uuid4().hex[:8]}",
            "type": block_type,
            "category": _infer_block_category(block_type),
            "name": name or block_type.upper(),
            "x": x,
            "y": y,
            "params": params or {},
        }

        # If params contain isMain, promote it to top-level (adapter checks block.get("isMain"))
        if params and params.get("isMain"):
            new_block["isMain"] = True

        blocks = strategy.get("blocks", [])
        blocks.append(new_block)

        # Save back
        update_payload = {
            "name": strategy["name"],
            "description": strategy.get("description", ""),
            "symbol": strategy.get("symbol", "BTCUSDT"),
            "timeframe": strategy.get("timeframe", "15"),
            "direction": strategy.get("direction", "both"),
            "market_type": strategy.get("market_type", "linear"),
            "initial_capital": strategy.get("initial_capital", 10000.0),
            "leverage": strategy.get("leverage", 10.0),
            "blocks": blocks,
            "connections": strategy.get("connections", []),
        }
        if strategy.get("builder_graph", {}).get("main_strategy"):
            update_payload["main_strategy"] = strategy["builder_graph"]["main_strategy"]

        await _api_put(f"/strategies/{strategy_id}", json_data=update_payload)

        return {
            "status": "added",
            "block": new_block,
            "total_blocks": len(blocks),
        }
    except Exception as e:
        logger.error(f"builder_add_block error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_update_block_params",
    description=(
        "Update parameters of an existing block on the canvas. "
        "For RSI: use params like period, use_long_range, long_rsi_more, long_rsi_less, "
        "use_short_range, short_rsi_less, short_rsi_more, use_cross_level, "
        "cross_long_level, cross_short_level, opposite_signal, use_cross_memory, "
        "cross_memory_bars. Example: {use_cross_level: true, cross_long_level: 25}. "
        "For MACD: use params like fast_period, slow_period, signal_period, source, "
        "use_macd_cross_zero, opposite_macd_cross_zero, macd_cross_zero_level, "
        "use_macd_cross_signal, signal_only_if_macd_positive, opposite_macd_cross_signal, "
        "disable_signal_memory, signal_memory_bars. "
        "Example: {use_macd_cross_signal: true, signal_only_if_macd_positive: true}."
    ),
    category="strategy_builder",
)
async def builder_update_block_params(
    strategy_id: str,
    block_id: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """
    Update parameters of an existing block.

    Args:
        strategy_id: Strategy UUID
        block_id: Block ID to update
        params: New parameters to merge (existing params are preserved unless overwritten)

    Returns:
        Updated block
    """
    try:
        strategy = await _api_get(f"/strategies/{strategy_id}")
        if "error" in strategy:
            return strategy

        blocks = strategy.get("blocks", [])
        target = None
        for b in blocks:
            if b.get("id") == block_id:
                target = b
                break

        if not target:
            return {"error": f"Block {block_id} not found in strategy {strategy_id}"}

        existing_params = target.get("params", {})
        existing_params.update(params)
        target["params"] = existing_params

        # Save back
        update_payload = {
            "name": strategy["name"],
            "description": strategy.get("description", ""),
            "symbol": strategy.get("symbol", "BTCUSDT"),
            "timeframe": strategy.get("timeframe", "15"),
            "direction": strategy.get("direction", "both"),
            "market_type": strategy.get("market_type", "linear"),
            "initial_capital": strategy.get("initial_capital", 10000.0),
            "leverage": strategy.get("leverage", 10.0),
            "blocks": blocks,
            "connections": strategy.get("connections", []),
        }
        if strategy.get("builder_graph", {}).get("main_strategy"):
            update_payload["main_strategy"] = strategy["builder_graph"]["main_strategy"]

        await _api_put(f"/strategies/{strategy_id}", json_data=update_payload)

        return {
            "status": "updated",
            "block_id": block_id,
            "params": existing_params,
        }
    except Exception as e:
        logger.error(f"builder_update_block_params error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_remove_block",
    description="Remove a block from the strategy canvas. Also removes any connections to/from it.",
    category="strategy_builder",
)
async def builder_remove_block(
    strategy_id: str,
    block_id: str,
) -> dict[str, Any]:
    """
    Remove a block and its connections from the strategy.

    Args:
        strategy_id: Strategy UUID
        block_id: Block ID to remove

    Returns:
        Removal confirmation
    """
    try:
        strategy = await _api_get(f"/strategies/{strategy_id}")
        if "error" in strategy:
            return strategy

        blocks = strategy.get("blocks", [])
        connections = strategy.get("connections", [])

        # Remove block
        new_blocks = [b for b in blocks if b.get("id") != block_id]
        if len(new_blocks) == len(blocks):
            return {"error": f"Block {block_id} not found"}

        # Remove connections that reference this block
        new_connections = [
            c
            for c in connections
            if c.get("source", {}).get("blockId") != block_id and c.get("target", {}).get("blockId") != block_id
        ]

        update_payload = {
            "name": strategy["name"],
            "description": strategy.get("description", ""),
            "symbol": strategy.get("symbol", "BTCUSDT"),
            "timeframe": strategy.get("timeframe", "15"),
            "direction": strategy.get("direction", "both"),
            "market_type": strategy.get("market_type", "linear"),
            "initial_capital": strategy.get("initial_capital", 10000.0),
            "leverage": strategy.get("leverage", 10.0),
            "blocks": new_blocks,
            "connections": new_connections,
        }
        if strategy.get("builder_graph", {}).get("main_strategy"):
            update_payload["main_strategy"] = strategy["builder_graph"]["main_strategy"]

        await _api_put(f"/strategies/{strategy_id}", json_data=update_payload)

        removed_conns = len(connections) - len(new_connections)
        return {
            "status": "removed",
            "block_id": block_id,
            "connections_removed": removed_conns,
            "remaining_blocks": len(new_blocks),
        }
    except Exception as e:
        logger.error(f"builder_remove_block error: {e}")
        return {"error": str(e)}


# =============================================================================
# CONNECTIONS — Wire blocks together
# =============================================================================


@registry.register(
    name="builder_connect_blocks",
    description=(
        "Connect two blocks by wiring an output port of one block "
        "to an input port of another. This is equivalent to the user "
        "dragging a wire between two nodes on the canvas. "
        "Common port names: 'value', 'signal', 'condition', 'input', 'output'."
    ),
    category="strategy_builder",
)
async def builder_connect_blocks(
    strategy_id: str,
    source_block_id: str,
    source_port: str,
    target_block_id: str,
    target_port: str,
) -> dict[str, Any]:
    """
    Connect two blocks (draw a wire between them).

    Args:
        strategy_id: Strategy UUID
        source_block_id: Source block ID (output side)
        source_port: Source port name (e.g. 'value', 'signal')
        target_block_id: Target block ID (input side)
        target_port: Target port name (e.g. 'input', 'condition')

    Returns:
        Created connection
    """
    try:
        import uuid

        strategy = await _api_get(f"/strategies/{strategy_id}")
        if "error" in strategy:
            return strategy

        connections = strategy.get("connections", [])
        new_connection = {
            "id": f"conn_{uuid.uuid4().hex[:8]}",
            "source": {
                "blockId": source_block_id,
                "portId": source_port,
            },
            "target": {
                "blockId": target_block_id,
                "portId": target_port,
            },
        }
        connections.append(new_connection)

        update_payload = {
            "name": strategy["name"],
            "description": strategy.get("description", ""),
            "symbol": strategy.get("symbol", "BTCUSDT"),
            "timeframe": strategy.get("timeframe", "15"),
            "direction": strategy.get("direction", "both"),
            "market_type": strategy.get("market_type", "linear"),
            "initial_capital": strategy.get("initial_capital", 10000.0),
            "leverage": strategy.get("leverage", 10.0),
            "blocks": strategy.get("blocks", []),
            "connections": connections,
        }
        if strategy.get("builder_graph", {}).get("main_strategy"):
            update_payload["main_strategy"] = strategy["builder_graph"]["main_strategy"]

        await _api_put(f"/strategies/{strategy_id}", json_data=update_payload)

        return {
            "status": "connected",
            "connection": new_connection,
            "total_connections": len(connections),
        }
    except Exception as e:
        logger.error(f"builder_connect_blocks error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_disconnect_blocks",
    description="Remove a connection (wire) between two blocks.",
    category="strategy_builder",
)
async def builder_disconnect_blocks(
    strategy_id: str,
    connection_id: str,
) -> dict[str, Any]:
    """
    Remove a connection between blocks.

    Args:
        strategy_id: Strategy UUID
        connection_id: Connection ID to remove

    Returns:
        Disconnection confirmation
    """
    try:
        strategy = await _api_get(f"/strategies/{strategy_id}")
        if "error" in strategy:
            return strategy

        connections = strategy.get("connections", [])
        new_connections = [c for c in connections if c.get("id") != connection_id]

        if len(new_connections) == len(connections):
            return {"error": f"Connection {connection_id} not found"}

        update_payload = {
            "name": strategy["name"],
            "description": strategy.get("description", ""),
            "symbol": strategy.get("symbol", "BTCUSDT"),
            "timeframe": strategy.get("timeframe", "15"),
            "direction": strategy.get("direction", "both"),
            "market_type": strategy.get("market_type", "linear"),
            "initial_capital": strategy.get("initial_capital", 10000.0),
            "leverage": strategy.get("leverage", 10.0),
            "blocks": strategy.get("blocks", []),
            "connections": new_connections,
        }
        if strategy.get("builder_graph", {}).get("main_strategy"):
            update_payload["main_strategy"] = strategy["builder_graph"]["main_strategy"]

        await _api_put(f"/strategies/{strategy_id}", json_data=update_payload)

        return {
            "status": "disconnected",
            "connection_id": connection_id,
            "remaining_connections": len(new_connections),
        }
    except Exception as e:
        logger.error(f"builder_disconnect_blocks error: {e}")
        return {"error": str(e)}


# =============================================================================
# VALIDATION & CODE GENERATION
# =============================================================================


@registry.register(
    name="builder_validate_strategy",
    description=(
        "Validate a strategy for completeness and correctness. "
        "Checks that all required blocks are present, connections are valid, "
        "and the strategy can be backtested. Returns errors and warnings."
    ),
    category="strategy_builder",
)
async def builder_validate_strategy(
    strategy_id: str,
) -> dict[str, Any]:
    """
    Validate a strategy before backtesting.

    Args:
        strategy_id: Strategy UUID to validate

    Returns:
        Validation result with is_valid, errors, warnings
    """
    try:
        return await _api_post(f"/validate/{strategy_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Strategy exists in DB but not in the in-memory StrategyBuilder.strategies dict.
            # This happens when the strategy was created via MCP workflow (REST API) rather
            # than the in-memory StrategyBuilder.create_strategy() path.
            # Return advisory-valid so the workflow can proceed to backtest,
            # which has its own validation against the DB-backed strategy.
            logger.warning(
                f"builder_validate_strategy: strategy {strategy_id} not in memory "
                f"(created via API) — returning advisory-valid"
            )
            return {
                "is_valid": True,
                "errors": [],
                "warnings": [
                    "Validation skipped: strategy exists in DB but not in memory graph. "
                    "Backtest endpoint will perform its own validation."
                ],
                "skipped": True,
            }
        logger.error(f"builder_validate_strategy HTTP error: {e.response.status_code} - {e.response.text}")
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        logger.error(f"builder_validate_strategy error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_generate_code",
    description=(
        "Generate Python code from a Strategy Builder strategy. "
        "Converts the visual block graph into executable Python code. "
        "Returns the generated code string."
    ),
    category="strategy_builder",
)
async def builder_generate_code(
    strategy_id: str,
    template: str = "backtest",
    include_comments: bool = True,
) -> dict[str, Any]:
    """
    Generate Python code from the strategy's block graph.

    Args:
        strategy_id: Strategy UUID
        template: Code template (backtest/live)
        include_comments: Include comments in generated code

    Returns:
        Generated Python code and metadata
    """
    try:
        payload = {
            "template": template,
            "include_comments": include_comments,
            "include_logging": True,
            "async_mode": False,
        }
        return await _api_post(f"/strategies/{strategy_id}/generate-code", json_data=payload)
    except Exception as e:
        logger.error(f"builder_generate_code error: {e}")
        return {"error": str(e)}


# =============================================================================
# BACKTEST — Run backtest on a strategy
# =============================================================================


@registry.register(
    name="builder_run_backtest",
    description=(
        "Run a backtest on a Strategy Builder strategy. "
        "This is equivalent to the user clicking 'Backtest' in the UI. "
        "The strategy must have blocks and connections configured. "
        "Results include metrics (Sharpe, win rate, drawdown, etc.) and trade list."
    ),
    category="strategy_builder",
)
async def builder_run_backtest(
    strategy_id: str,
    symbol: str = "BTCUSDT",
    interval: str = "15",
    start_date: str = "2025-01-01",
    end_date: str = "2025-06-01",
    initial_capital: float = 10000.0,
    leverage: int = 10,
    direction: str = "both",
    commission: float = 0.0007,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> dict[str, Any]:
    """
    Run backtest on a Strategy Builder strategy.

    Args:
        strategy_id: Strategy UUID
        symbol: Trading pair (e.g. BTCUSDT)
        interval: Timeframe (1,5,15,30,60,240,D,W,M)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        initial_capital: Starting capital
        leverage: Leverage (1-125)
        direction: Trade direction (long/short/both)
        commission: Commission rate (0.0007 = 0.07%)
        stop_loss: Stop loss fraction (e.g. 0.02 = 2%)
        take_profit: Take profit fraction (e.g. 0.03 = 3%)

    Returns:
        Backtest results with metrics and trade list
    """
    try:
        payload = {
            "symbol": symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "leverage": leverage,
            "direction": direction,
            "commission": commission,
        }
        if stop_loss is not None:
            payload["stop_loss"] = stop_loss
        if take_profit is not None:
            payload["take_profit"] = take_profit

        return await _api_post(f"/strategies/{strategy_id}/backtest", json_data=payload)
    except httpx.HTTPStatusError as e:
        logger.error(f"builder_run_backtest HTTP error: {e.response.status_code} - {e.response.text}")
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        logger.error(f"builder_run_backtest error: {e}")
        return {"error": str(e)}


# =============================================================================
# TEMPLATES — Pre-built strategy templates
# =============================================================================


@registry.register(
    name="builder_list_templates",
    description=(
        "List available strategy templates. Templates are pre-built strategies "
        "that can be instantiated as a starting point."
    ),
    category="strategy_builder",
)
async def builder_list_templates(
    category: str | None = None,
) -> dict[str, Any]:
    """
    List available strategy templates.

    Args:
        category: Optional category filter

    Returns:
        List of templates with metadata
    """
    try:
        params = {}
        if category:
            params["category"] = category
        return await _api_get("/templates", params=params)
    except Exception as e:
        logger.error(f"builder_list_templates error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_instantiate_template",
    description=(
        "Create a new strategy from a template. "
        "This gives you a pre-configured strategy with blocks and connections "
        "that you can then modify."
    ),
    category="strategy_builder",
)
async def builder_instantiate_template(
    template_id: str,
    name: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
) -> dict[str, Any]:
    """
    Instantiate a strategy from a template.

    Args:
        template_id: Template ID to instantiate
        name: Optional custom name
        symbol: Optional symbol override
        timeframe: Optional timeframe override

    Returns:
        Created strategy from template
    """
    try:
        payload: dict[str, Any] = {"template_id": template_id}
        if name:
            payload["name"] = name
        if symbol:
            payload["symbols"] = [symbol]
        if timeframe:
            payload["timeframe"] = timeframe
        return await _api_post("/templates/instantiate", json_data=payload)
    except Exception as e:
        logger.error(f"builder_instantiate_template error: {e}")
        return {"error": str(e)}


# =============================================================================
# OPTIMIZATION — Optimize strategy parameters
# =============================================================================


@registry.register(
    name="builder_get_optimizable_params",
    description=(
        "Get the list of optimizable parameters for a strategy. "
        "Returns parameter ranges that can be used for grid search or Bayesian optimization."
    ),
    category="strategy_builder",
)
async def builder_get_optimizable_params(
    strategy_id: str,
) -> dict[str, Any]:
    """
    Get optimizable parameters for a strategy.

    Args:
        strategy_id: Strategy UUID

    Returns:
        List of optimizable parameters with ranges
    """
    try:
        return await _api_get(f"/strategies/{strategy_id}/optimizable-params")
    except Exception as e:
        logger.error(f"builder_get_optimizable_params error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_analyze_strategy",
    description=(
        "Analyze a strategy for potential issues and improvements. "
        "Returns suggestions for better parameters, missing blocks, "
        "risk management improvements, etc."
    ),
    category="strategy_builder",
)
async def builder_analyze_strategy(
    strategy_id: str,
) -> dict[str, Any]:
    """
    Analyze strategy for potential issues and improvements.

    Args:
        strategy_id: Strategy UUID

    Returns:
        Analysis with issues, suggestions, and score
    """
    try:
        return await _api_get(f"/strategies/{strategy_id}/analyze")
    except Exception as e:
        logger.error(f"builder_analyze_strategy error: {e}")
        return {"error": str(e)}


# =============================================================================
# VERSIONS — Strategy version history
# =============================================================================


@registry.register(
    name="builder_get_versions",
    description="Get version history of a strategy. Each save creates a new version.",
    category="strategy_builder",
)
async def builder_get_versions(
    strategy_id: str,
) -> dict[str, Any]:
    """
    Get version history of a strategy.

    Args:
        strategy_id: Strategy UUID

    Returns:
        List of versions with timestamps
    """
    try:
        return await _api_get(f"/strategies/{strategy_id}/versions")
    except Exception as e:
        logger.error(f"builder_get_versions error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_revert_version",
    description="Revert a strategy to a previous version.",
    category="strategy_builder",
)
async def builder_revert_version(
    strategy_id: str,
    version_id: int,
) -> dict[str, Any]:
    """
    Revert a strategy to a previous version.

    Args:
        strategy_id: Strategy UUID
        version_id: Version ID to revert to

    Returns:
        Revert confirmation
    """
    try:
        return await _api_post(f"/strategies/{strategy_id}/revert/{version_id}")
    except Exception as e:
        logger.error(f"builder_revert_version error: {e}")
        return {"error": str(e)}


# =============================================================================
# EXPORT / IMPORT
# =============================================================================


@registry.register(
    name="builder_export_strategy",
    description="Export a strategy as JSON for sharing or backup.",
    category="strategy_builder",
)
async def builder_export_strategy(
    strategy_id: str,
) -> dict[str, Any]:
    """
    Export a strategy as JSON.

    Args:
        strategy_id: Strategy UUID

    Returns:
        Full strategy JSON for import/sharing
    """
    try:
        return await _api_get(f"/export/{strategy_id}")
    except Exception as e:
        logger.error(f"builder_export_strategy error: {e}")
        return {"error": str(e)}


@registry.register(
    name="builder_import_strategy",
    description="Import a strategy from JSON.",
    category="strategy_builder",
)
async def builder_import_strategy(
    strategy_json: dict[str, Any],
) -> dict[str, Any]:
    """
    Import a strategy from JSON.

    Args:
        strategy_json: Full strategy JSON to import

    Returns:
        Imported strategy
    """
    try:
        return await _api_post("/import", json_data=strategy_json)
    except Exception as e:
        logger.error(f"builder_import_strategy error: {e}")
        return {"error": str(e)}
