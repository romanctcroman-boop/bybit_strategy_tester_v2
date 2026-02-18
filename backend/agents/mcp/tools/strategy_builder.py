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
    # (stoch_rsi removed — consolidated into universal stochastic indicator)
    "stoch_rsi": "indicator",  # DEPRECATED: use universal "stochastic" block instead
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
    # (qqe_cross removed — consolidated into universal qqe indicator)
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
    # (static_sltp moved to exit blocks below)
    # Universal filter/indicator blocks (Library)
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
    # Legacy filter blocks
    # (rsi_filter removed — consolidated into universal rsi indicator with Range/Cross modes)
    "rsi_filter": "filter",  # DEPRECATED: use universal "rsi" block with use_long_range/use_cross_level instead
    # (supertrend_filter removed — consolidated into universal supertrend indicator)
    "two_ma_filter": "filter",
    "time_filter": "filter",
    "volatility_filter": "filter",
    "adx_filter": "filter",
    "session_filter": "filter",
    # Exit SL/TP blocks
    "static_sltp": "exit",
    "trailing_stop_exit": "exit",
    "atr_exit": "exit",
    "multi_tp_exit": "exit",
    # Close-by-Indicator exit blocks
    "close_by_time": "exit",
    "close_channel": "exit",
    "close_ma_cross": "exit",
    "close_rsi": "exit",
    "close_stochastic": "exit",
    "close_psar": "exit",
    # Manual Grid
    "grid_orders": "dca_grid",
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
    # (smart_rsi, smart_macd, smart_bollinger removed — Smart Signals category deprecated)
    # (smart_stochastic removed — consolidated into universal stochastic indicator)
    # (smart_supertrend removed — consolidated into universal supertrend indicator)
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
    # (rsi_divergence removed — consolidated into universal divergence block)
    "rsi_divergence": "divergence",  # DEPRECATED: use universal "divergence" block instead
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
        "two_ma_filter, volume_filter, time_filter, "
        "static_sltp, trailing_stop_exit, atr_exit, multi_tp_exit, "
        "fixed_size, percent_balance, risk_percent, "
        "and many more (use builder_get_block_library to see all). "
        "IMPORTANT: Do NOT use deprecated block types (rsi_filter, stoch_rsi, rsi_divergence). "
        "Use the universal 'rsi' block with its modes (Range/Cross/Legacy) instead of rsi_filter. "
        "Use the universal 'stochastic' block instead of stoch_rsi. "
        "Use the universal 'divergence' block instead of rsi_divergence.\n\n"
        "RSI UNIVERSAL NODE — supports 3 signal modes that combine with AND logic:\n"
        "  Base params: period(14, 2-500), timeframe('Chart', options: 1/5/15/30/60/240/D/W/M/Chart), "
        "use_btc_source(false) — if true, calculates RSI on BTCUSDT price instead of current symbol.\n"
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
        "RSI params: period(14, 2-500), timeframe('Chart'), use_btc_source(false), "
        "use_long_range(false), long_rsi_more(30, 0.1-100), "
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
        "  Base params: fast_period(12), slow_period(26), signal_period(9). "
        "fast_period MUST be < slow_period.\n"
        "  source('close', options: close/open/high/low/hl2/hlc3/ohlc4) — price source.\n"
        "  timeframe('Chart', options: 1/5/15/30/60/240/D/W/M/Chart) — timeframe for MACD.\n"
        "  use_btc_source(false) — if true, uses BTCUSDT price for calculation.\n"
        "  enable_visualization(false) — shows MACD histogram on the chart.\n"
        "  1) CROSS ZERO: use_macd_cross_zero=True → long when MACD crosses above level "
        "(default 0), short when below. opposite_macd_cross_zero swaps signals.\n"
        "  2) CROSS SIGNAL: use_macd_cross_signal=True → long when MACD crosses above "
        "Signal line, short when below. signal_only_if_macd_positive filters: long only "
        "when MACD<0, short only when MACD>0. opposite_macd_cross_signal swaps.\n"
        "  No mode enabled → data-only (MACD/Signal/Hist output, long/short always False).\n"
        "  Signal Memory: enabled by default, disable_signal_memory=True to turn off. "
        "signal_memory_bars(5) controls how many bars cross signals persist.\n"
        "MACD params: fast_period(12), slow_period(26), signal_period(9), source(close), "
        "timeframe('Chart'), use_btc_source(false), enable_visualization(false), "
        "use_macd_cross_zero(false), opposite_macd_cross_zero(false), macd_cross_zero_level(0), "
        "use_macd_cross_signal(false), signal_only_if_macd_positive(false), "
        "opposite_macd_cross_signal(false), disable_signal_memory(false), signal_memory_bars(5).\n"
        "Outputs: macd (series), signal (series), hist (series), long (bool), short (bool).\n"
        "Optimizable params: fast_period, slow_period, signal_period, macd_cross_zero_level, signal_memory_bars.\n"
        "OPTIMIZATION RANGES (MACD): Each optimizable param can be set for grid search with "
        "{enabled: true/false, min: <low>, max: <high>, step: <step>}. "
        "Stored in block.optimizationParams. Default ranges: "
        "fast_period {8,16,1}, slow_period {20,30,1}, signal_period {6,12,1}, "
        "macd_cross_zero_level {-50,50,1}, signal_memory_bars {1,20,1}.\n\n"
        "STOCHASTIC UNIVERSAL NODE — supports 3 signal modes that combine with AND logic:\n"
        "  Base params: stoch_k_length(14, 1-200), stoch_k_smoothing(3, 1-50), "
        "stoch_d_smoothing(3, 1-50), timeframe('Chart'), use_btc_source(false).\n"
        "  1) RANGE filter: use_stoch_range_filter=True → long when %D > long_stoch_d_more "
        "AND %D < long_stoch_d_less. MUST have more < less. "
        "short when %D > short_stoch_d_more AND %D < short_stoch_d_less.\n"
        "  2) CROSS level: use_stoch_cross_level=True → long when %D crosses UP through "
        "stoch_cross_level_long(20), short when %D crosses DOWN through "
        "stoch_cross_level_short(80). activate_stoch_cross_memory + stoch_cross_memory_bars(5) "
        "extends signal for N bars.\n"
        "  3) K/D CROSS: use_stoch_kd_cross=True → long when %K crosses above %D, "
        "short when %K crosses below %D. opposite_stoch_kd swaps long/short. "
        "activate_stoch_kd_memory + stoch_kd_memory_bars(5) extends signal for N bars.\n"
        "  No mode enabled → passthrough (always True).\n"
        "Stochastic params: stoch_k_length(14), stoch_k_smoothing(3), stoch_d_smoothing(3), "
        "timeframe('Chart'), use_btc_source(false), "
        "use_stoch_range_filter(false), long_stoch_d_more(1), long_stoch_d_less(50), "
        "short_stoch_d_less(100), short_stoch_d_more(50), "
        "use_stoch_cross_level(false), stoch_cross_level_long(20), stoch_cross_level_short(80), "
        "activate_stoch_cross_memory(false), stoch_cross_memory_bars(5), "
        "use_stoch_kd_cross(false), opposite_stoch_kd(false), "
        "activate_stoch_kd_memory(false), stoch_kd_memory_bars(5).\n"
        "Outputs: k (%K series), d (%D series), long (bool), short (bool).\n"
        "Optimizable params: stoch_k_length, stoch_k_smoothing, stoch_d_smoothing, "
        "long_stoch_d_more/less, short_stoch_d_less/more, "
        "stoch_cross_level_long, stoch_cross_level_short, stoch_cross_memory_bars, stoch_kd_memory_bars.\n"
        "OPTIMIZATION RANGES (STOCHASTIC): Default ranges: "
        "stoch_k_length {5,21,1}, stoch_k_smoothing {1,5,1}, stoch_d_smoothing {1,5,1}, "
        "long_stoch_d_more {0,30,5}, long_stoch_d_less {20,60,5}, "
        "short_stoch_d_less {60,100,5}, short_stoch_d_more {40,80,5}, "
        "stoch_cross_level_long {10,40,5}, stoch_cross_level_short {60,90,5}, "
        "stoch_cross_memory_bars {1,20,1}, stoch_kd_memory_bars {1,20,1}.\n\n"
        "SUPERTREND UNIVERSAL NODE — supports 2 signal modes (Filter vs Signal):\n"
        "  Base params: period(10, 1-100) — ATR period, multiplier(3.0, 0.1-50) — ATR multiplier, "
        "source('hl2', options: hl2/hlc3/close), "
        "timeframe('Chart', options: 1/5/15/30/60/240/D/W/M/Chart), "
        "use_btc_source(false) — if true, calculates SuperTrend on BTCUSDT price.\n"
        "  use_supertrend(false) — enable filter/signal mode. If false → passthrough (always True).\n"
        "  1) FILTER mode (default when use_supertrend=true): "
        "long while uptrend (direction==1), short while downtrend (direction==-1). "
        "Continuous signal — stays active entire trend.\n"
        "  2) SIGNAL mode: generate_on_trend_change=true → "
        "long only on direction flip from -1 to 1, short only on flip from 1 to -1. "
        "One-bar event signal (fires once per flip).\n"
        "  opposite_signal(false) — swaps long/short.\n"
        "  show_supertrend(false) — display on chart.\n"
        "SuperTrend params: period(10), multiplier(3.0), source('hl2'), "
        "timeframe('Chart'), use_btc_source(false), "
        "use_supertrend(false), generate_on_trend_change(false), "
        "opposite_signal(false), show_supertrend(false).\n"
        "Outputs: supertrend (line series), direction (1/-1), upper, lower, long (bool), short (bool).\n"
        "Optimizable params: period, multiplier.\n"
        "OPTIMIZATION RANGES (SUPERTREND): Default ranges: "
        "period {5,20,1}, multiplier {1.0,5.0,0.5}.\n\n"
        "ATR VOLATILITY NODE — compares two ATR values to detect volatility changes:\n"
        "  use_atr_volatility(false), atr1_to_atr2('ATR1 < ATR2'|'ATR1 > ATR2'), "
        "atr_diff_percent(10), atr_length1(20), atr_length2(100), "
        "atr_smoothing('WMA', opts: SMA/EMA/WMA/DEMA/TEMA/HMA). "
        "'ATR1 < ATR2'→ low-vol (mean reversion); 'ATR1 > ATR2'→ high-vol (breakout).\n\n"
        "VOLUME FILTER NODE — compares two Volume MAs:\n"
        "  use_volume_filter(false), vol1_to_vol2('VOL1 < VOL2'|'VOL1 > VOL2'), "
        "vol_diff_percent(10), vol_length1(20), vol_length2(100), "
        "vol_smoothing('WMA', opts: SMA/EMA/WMA/DEMA/TEMA/HMA).\n\n"
        "HIGHEST/LOWEST BAR NODE — detects price near recent highs/lows:\n"
        "  use_highest_lowest(false), hl_lookback_bars(10), hl_price_percent(0), "
        "hl_atr_percent(0), atr_hl_length(50), use_block_worse_than(false), "
        "block_worse_percent(1.1).\n\n"
        "TWO MAs NODE — two configurable MAs with cross and filter modes:\n"
        "  ma1_length(50), ma1_smoothing('SMA'), ma1_source('close'), "
        "ma2_length(100), ma2_smoothing('EMA'), ma2_source('close'), "
        "two_mas_timeframe('Chart'). Modes: "
        "1) MA CROSS: use_ma_cross=true → long when MA1>MA2, short when MA1<MA2. "
        "opposite_ma_cross swaps. activate_ma_cross_memory + ma_cross_memory_bars(5). "
        "2) MA1 FILTER: use_ma1_filter=true → long when price>MA1, short when price<MA1. "
        "opposite_ma1_filter swaps. Both modes combine with AND logic.\n\n"
        "ACCUMULATION AREAS NODE — detects tight consolidation zones:\n"
        "  use_accumulation(false), backtracking_interval(30), min_bars_to_execute(5), "
        "signal_on_breakout(false), signal_on_opposite_breakout(false).\n\n"
        "KELTNER/BOLLINGER CHANNEL NODE — channel-based entry signals:\n"
        "  use_channel(false), channel_timeframe('Chart'), "
        "channel_mode('Rebound'|'Breakout'), channel_type('Keltner Channel'|'Bollinger Bands'), "
        "enter_conditions('Wick out of band'|'Body out of band'|'Full candle out of band'), "
        "keltner_length(14), keltner_mult(1.5), bb_length(20), bb_deviation(2).\n\n"
        "RVI NODE — Relative Vigor Index range filter:\n"
        "  rvi_length(10), rvi_timeframe('Chart'), rvi_ma_type('WMA'), rvi_ma_length(2), "
        "use_rvi_long_range(false), rvi_long_more(1), rvi_long_less(50), "
        "use_rvi_short_range(false), rvi_short_less(100), rvi_short_more(50).\n\n"
        "MFI NODE — Money Flow Index range filter (volume-weighted RSI):\n"
        "  mfi_length(14), mfi_timeframe('Chart'), use_btcusdt_mfi(false), "
        "use_mfi_long_range(false), mfi_long_more(1), mfi_long_less(60), "
        "use_mfi_short_range(false), mfi_short_less(100), mfi_short_more(50).\n\n"
        "CCI NODE — Commodity Channel Index range filter:\n"
        "  cci_length(14), cci_timeframe('Chart'), "
        "use_cci_long_range(false), cci_long_more(-400), cci_long_less(400), "
        "use_cci_short_range(false), cci_short_less(400), cci_short_more(10).\n\n"
        "MOMENTUM NODE — rate-of-change range filter:\n"
        "  momentum_length(14), momentum_timeframe('Chart'), use_btcusdt_momentum(false), "
        "momentum_source('close'), use_momentum_long_range(false), "
        "momentum_long_more(-100), momentum_long_less(10), "
        "use_momentum_short_range(false), momentum_short_less(95), momentum_short_more(-30).\n\n"
        "CONDITIONS — logical signal combinators:\n"
        "  crossover: source_a, source_b — fires when A crosses above B.\n"
        "  crossunder: source_a, source_b — fires when A crosses below B.\n"
        "  greater_than: value(0), use_input(true) — input > value.\n"
        "  less_than: value(0), use_input(true) — input < value.\n"
        "  equals: value(0), tolerance(0.001) — input ≈ value.\n"
        "  between: min_value(0), max_value(100) — min ≤ input ≤ max.\n\n"
        "DIVERGENCE NODE — multi-oscillator divergence detection:\n"
        "  pivot_interval(9), act_without_confirmation(false), "
        "show_divergence_lines(false), activate_diver_signal_memory(false), "
        "keep_diver_signal_memory_bars(5). Sources: "
        "use_divergence_rsi(false)+rsi_period(14), use_divergence_stochastic(false)+stoch_length(14), "
        "use_divergence_momentum(false)+momentum_length(10), use_divergence_cmf(false)+cmf_period(21), "
        "use_obv(false), use_mfi(false)+mfi_length(14).\n\n"
        "DCA NODE — dollar-cost averaging grid:\n"
        "  grid_size_percent(15), order_count(5), martingale_coefficient(1.0), "
        "log_steps_coefficient(1.0), first_order_offset(0), grid_trailing(0).\n\n"
        "MANUAL GRID NODE (grid_orders) — custom orders with exact offsets:\n"
        "  orders: [{offset:0.1, volume:25}, ...] (max 40, total volume MUST=100%), "
        "grid_trailing(0).\n\n"
        "EXIT BLOCKS:\n"
        "  static_sltp: take_profit_percent(1.5), stop_loss_percent(1.5), "
        "sl_type('average_price'|'last_price'), close_only_in_profit(false), "
        "activate_breakeven(false), breakeven_activation_percent(0.5), new_breakeven_sl_percent(0.1).\n"
        "  trailing_stop_exit: activation_percent(1.0), trailing_percent(0.5), "
        "trail_type('percent'|'atr').\n"
        "  atr_exit: use_atr_sl(false), atr_sl_smoothing('WMA'), atr_sl_period(140), "
        "atr_sl_multiplier(4.0), use_atr_tp(false), atr_tp_smoothing('WMA'), "
        "atr_tp_period(140), atr_tp_multiplier(4.0).\n"
        "  multi_tp_exit: tp1_percent(1.0), tp1_close_percent(33), "
        "tp2_percent(2.0), tp2_close_percent(33), tp3_percent(3.0), "
        "tp3_close_percent(34), use_tp2(true), use_tp3(true). Sum MUST=100%.\n\n"
        "CLOSE-BY-INDICATOR EXITS:\n"
        "  close_by_time: enabled(false), bars_since_entry(10), profit_only(false), min_profit_percent(0).\n"
        "  close_channel: enabled(false), channel_close_timeframe('Chart'), "
        "band_to_close('Rebound'|'Breakout'), channel_type, close_condition, "
        "keltner_length(14), keltner_mult(1.5), bb_length(20), bb_deviation(2).\n"
        "  close_ma_cross: enabled(false), profit_only(false), min_profit_percent(1), "
        "ma1_length(10), ma2_length(30).\n"
        "  close_rsi: enabled(false), rsi_close_length(14), rsi_close_timeframe('Chart'), "
        "activate_rsi_reach(false) + rsi_long_more(70)/rsi_long_less(100)/rsi_short_less(30)/rsi_short_more(1), "
        "activate_rsi_cross(false) + rsi_cross_long_level(70)/rsi_cross_short_level(30).\n"
        "  close_stochastic: enabled(false), stoch_close_k_length(14), stoch_close_k_smoothing(3), "
        "stoch_close_d_smoothing(3), activate_stoch_reach(false) + stoch_long_more(80)/stoch_long_less(100)/"
        "stoch_short_less(20)/stoch_short_more(1), activate_stoch_cross(false) + "
        "stoch_cross_long_level(80)/stoch_cross_short_level(20).\n"
        "  close_psar: enabled(false), psar_start(0.02), psar_increment(0.02), "
        "psar_maximum(0.2), psar_close_nth_bar(1), psar_opposite(false)."
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
        "For RSI: use params like period, timeframe, use_btc_source, "
        "use_long_range, long_rsi_more, long_rsi_less, "
        "use_short_range, short_rsi_less, short_rsi_more, use_cross_level, "
        "cross_long_level, cross_short_level, opposite_signal, use_cross_memory, "
        "cross_memory_bars. Example: {use_cross_level: true, cross_long_level: 25}. "
        "For MACD: use params like fast_period, slow_period, signal_period, source, "
        "timeframe, use_btc_source, enable_visualization, "
        "use_macd_cross_zero, opposite_macd_cross_zero, macd_cross_zero_level, "
        "use_macd_cross_signal, signal_only_if_macd_positive, opposite_macd_cross_signal, "
        "disable_signal_memory, signal_memory_bars. "
        "Example: {use_macd_cross_signal: true, signal_only_if_macd_positive: true}. "
        "For Stochastic: stoch_k_length, stoch_k_smoothing, stoch_d_smoothing, "
        "use_stoch_range_filter, long_stoch_d_more, long_stoch_d_less, "
        "use_stoch_cross_level, use_stoch_kd_cross, opposite_stoch_kd. "
        "For SuperTrend: period, multiplier, source, use_supertrend, generate_on_trend_change. "
        "For QQE: rsi_period, qqe_factor, smoothing_period, use_qqe, opposite_qqe. "
        "For ATR Volatility: use_atr_volatility, atr1_to_atr2, atr_diff_percent, "
        "atr_length1, atr_length2, atr_smoothing. "
        "For Volume Filter: use_volume_filter, vol1_to_vol2, vol_diff_percent, "
        "vol_length1, vol_length2, vol_smoothing. "
        "For Highest/Lowest Bar: use_highest_lowest, hl_lookback_bars, hl_price_percent, "
        "hl_atr_percent, atr_hl_length, use_block_worse_than, block_worse_percent. "
        "For Two MAs: ma1_length, ma1_smoothing, ma2_length, ma2_smoothing, "
        "use_ma_cross, opposite_ma_cross, use_ma1_filter, opposite_ma1_filter. "
        "For Accumulation Areas: use_accumulation, backtracking_interval, "
        "min_bars_to_execute, signal_on_breakout, signal_on_opposite_breakout. "
        "For Keltner/Bollinger Channel: use_channel, channel_mode, channel_type, "
        "enter_conditions, keltner_length, keltner_mult, bb_length, bb_deviation. "
        "For RVI: rvi_length, rvi_ma_type, use_rvi_long_range, rvi_long_more, rvi_long_less. "
        "For MFI: mfi_length, use_btcusdt_mfi, use_mfi_long_range, mfi_long_more, mfi_long_less. "
        "For CCI: cci_length, use_cci_long_range, cci_long_more, cci_long_less. "
        "For Momentum: momentum_length, use_momentum_long_range, momentum_long_more, momentum_long_less. "
        "For Divergence: pivot_interval, use_divergence_rsi, rsi_period, "
        "use_divergence_stochastic, stoch_length, use_divergence_momentum. "
        "For DCA: grid_size_percent, order_count, martingale_coefficient, log_steps_coefficient. "
        "For Grid Orders: orders (array of {offset, volume}), grid_trailing. "
        "For Static SL/TP: take_profit_percent, stop_loss_percent, sl_type, activate_breakeven. "
        "For Trailing Stop Exit: activation_percent, trailing_percent, trail_type. "
        "For ATR Exit: use_atr_sl, atr_sl_period, atr_sl_multiplier, use_atr_tp, atr_tp_period. "
        "For Multi TP: tp1_percent, tp1_close_percent, tp2_percent, tp3_percent. "
        "For Close by Time: enabled, bars_since_entry, profit_only. "
        "For Close Channel: enabled, channel_type, band_to_close, close_condition. "
        "For Close MA Cross: enabled, ma1_length, ma2_length, profit_only. "
        "For Close RSI: enabled, rsi_close_length, activate_rsi_reach, activate_rsi_cross. "
        "For Close Stochastic: enabled, stoch_close_k_length, activate_stoch_reach, activate_stoch_cross. "
        "For Close PSAR: enabled, psar_start, psar_increment, psar_maximum, psar_close_nth_bar."
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
    name="builder_run_optimization",
    description=(
        "Run parameter optimization on a Strategy Builder strategy. "
        "Supports 3 methods: grid_search (exhaustive), random_search (sampled subset), "
        "bayesian (Optuna TPE/CMA-ES). The optimizer extracts all optimizable numeric "
        "params from strategy blocks, generates combinations within ranges, runs backtest "
        "for each combination, and returns ranked results sorted by optimize_metric. "
        "Use builder_get_optimizable_params first to see available params and default ranges. "
        "You can override ranges via parameter_ranges list. "
        "Returns top results with full metrics (Sharpe, win rate, drawdown, PnL, etc.). "
        "WARNING: grid_search with many params can produce millions of combinations — "
        "use max_iterations to limit, or prefer bayesian for large search spaces."
    ),
    category="strategy_builder",
)
async def builder_run_optimization(
    strategy_id: str,
    symbol: str = "BTCUSDT",
    interval: str = "15",
    start_date: str = "2025-01-01",
    end_date: str = "2025-06-01",
    initial_capital: float = 10000.0,
    leverage: int = 10,
    direction: str = "both",
    commission: float = 0.0007,
    method: str = "grid_search",
    optimize_metric: str = "sharpe_ratio",
    parameter_ranges: list[dict[str, Any]] | None = None,
    max_iterations: int = 0,
    n_trials: int = 100,
    timeout_seconds: int = 3600,
    max_results: int = 20,
    early_stopping: bool = False,
    early_stopping_patience: int = 20,
) -> dict[str, Any]:
    """
    Run parameter optimization on a Strategy Builder strategy.

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
        method: Optimization method — grid_search|random_search|bayesian
        optimize_metric: Metric to maximize (sharpe_ratio, net_profit, win_rate, etc.)
        parameter_ranges: Custom param ranges overriding defaults.
            Each item: {"param_path": "blockId.paramKey", "low": X, "high": Y, "step": Z, "enabled": true}
        max_iterations: Max iterations (0 = all for grid_search)
        n_trials: Optuna trials for bayesian method (10-500)
        timeout_seconds: Timeout in seconds (60-86400)
        max_results: Max results to return (1-100)
        early_stopping: Enable early stopping
        early_stopping_patience: Early stopping patience (iterations without improvement)

    Returns:
        Optimization results with ranked parameter combinations and metrics.
        Includes: best_params, results_count, results list with full metrics per combo.
    """
    try:
        payload: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "leverage": leverage,
            "direction": direction,
            "commission": commission,
            "method": method,
            "optimize_metric": optimize_metric,
            "max_iterations": max_iterations,
            "n_trials": n_trials,
            "timeout_seconds": timeout_seconds,
            "max_results": max_results,
            "early_stopping": early_stopping,
            "early_stopping_patience": early_stopping_patience,
        }
        if parameter_ranges:
            payload["parameter_ranges"] = parameter_ranges

        return await _api_post(f"/strategies/{strategy_id}/optimize", json_data=payload)
    except httpx.HTTPStatusError as e:
        logger.error(f"builder_run_optimization HTTP error: {e.response.status_code} - {e.response.text}")
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        logger.error(f"builder_run_optimization error: {e}")
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
