"""
Strategy Builder Adapter

Converts Strategy Builder visual graphs (blocks + connections) into executable
BaseStrategy instances that can be used with backtesting engines.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.strategies import BaseStrategy, SignalResult

# Import our custom indicators for extended coverage
from backend.core.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_atr_smoothed,
    calculate_bollinger,
    calculate_cci,
    calculate_cmf,
    calculate_ema,
    calculate_keltner,
    calculate_macd,
    calculate_mfi,
    calculate_obv,
    calculate_parabolic_sar,
    calculate_roc,
    calculate_rsi,
    calculate_sma,
    calculate_stochastic,
)


def _param(params: dict, default: Any, *keys: str) -> Any:
    """Get param value trying keys in order (supports snake_case and camelCase from frontend)."""
    for k in keys:
        v = params.get(k)
        if v is not None:
            return v
    return default


def _clamp_period(val: Any, min_val: int = 1, max_val: int = 500) -> int:
    """Convert indicator period to a safe integer, clamped to [min_val, max_val].

    Protects against user-supplied values like 0, -5, or 999999 which would cause
    vectorbt/NumPy errors. Logs a warning when clamping is applied.

    Args:
        val: Raw parameter value (int, float, str, or None).
        min_val: Minimum allowed period (default 1).
        max_val: Maximum allowed period (default 500).

    Returns:
        Clamped integer period.
    """
    try:
        raw = int(val)
    except (TypeError, ValueError):
        logger.warning("_clamp_period: could not convert {!r} to int, using min_val={}", val, min_val)
        return min_val
    clamped = max(min_val, min(max_val, raw))
    if clamped != raw:
        logger.warning(
            "_clamp_period: period={} out of range [{}, {}], clamped to {}",
            raw,
            min_val,
            max_val,
            clamped,
        )
    return clamped


class StrategyBuilderAdapter(BaseStrategy):
    """
    Adapter for Strategy Builder generated strategies.

    Converts a visual block-based strategy graph into executable Python code
    that generates trading signals compatible with backtesting engines.

    Example:
        graph = {
            "blocks": [...],
            "connections": [...],
            "name": "My RSI Strategy"
        }
        adapter = StrategyBuilderAdapter(graph)
        signals = adapter.generate_signals(ohlcv)
    """

    # Port alias maps — class-level constants (avoid re-creation on every call)
    _PORT_ALIASES: dict[str, list[str]] = {
        "output": ["value", "close"],
        "value": ["output", "close"],
        "result": ["signal", "output"],
        "signal": ["result", "output"],
        "input": ["value", "close"],
    }

    _SIGNAL_PORT_ALIASES: dict[str, list[str]] = {
        "long": ["bullish", "entry_long", "signal"],
        "short": ["bearish", "entry_short", "signal"],
        "bullish": ["long", "entry_long", "signal"],
        "bearish": ["short", "entry_short", "signal"],
        "output": ["value", "result", "signal"],
        "value": ["output", "result", "signal"],
        "result": ["signal", "output", "value"],
        "signal": ["result", "output", "value"],
        # Close-condition blocks expose "config" as their single output port on the frontend.
        # Resolve it to the actual signal keys present in the cached output.
        "config": ["exit_long", "exit_short", "exit", "signal"],
    }

    def __init__(self, strategy_graph: dict[str, Any], btcusdt_ohlcv: pd.DataFrame | None = None):
        """
        Initialize adapter from strategy graph.

        Args:
            strategy_graph: Dictionary containing:
                - blocks: List of block objects
                - connections: List of connection objects
                - name: Strategy name
                - description: Strategy description (optional)
                - main_strategy: (optional) The main strategy node with isMain: True
                - interval: (optional) Main chart timeframe from Properties panel
                  Used to resolve "Chart" timeframe in block params.
            btcusdt_ohlcv: Pre-loaded BTCUSDT OHLCV DataFrame for mfi_filter
                use_btcusdt_mfi=True. Must be loaded by the caller (e.g. async
                router) before constructing the adapter — do NOT use asyncio.run()
                inside generate_signals. Pass None to disable the feature.
        """
        self.graph = strategy_graph
        self.name = strategy_graph.get("name", "Builder Strategy")
        self.description = strategy_graph.get("description", "")
        # Main chart interval from Properties panel (e.g. "15", "60", "D")
        # When a block's timeframe is "Chart", it resolves to this value.
        self.main_interval = strategy_graph.get("interval", "")
        self.blocks = {block["id"]: block for block in strategy_graph.get("blocks", [])}

        # Normalize connections into canonical format once
        # so the rest of the code can do simple dict access instead of
        # probing 5 possible key names on every call.
        self.connections = self._normalize_connections(strategy_graph.get("connections", []))

        # Handle main_strategy node if present
        # This is the "strategy" node that collects all entry/exit signals
        main_strategy = strategy_graph.get("main_strategy")
        if main_strategy and isinstance(main_strategy, dict):
            main_id = main_strategy.get("id")
            if main_id:
                # Ensure isMain is set
                main_strategy["isMain"] = True
                # Add to blocks if not already there
                if main_id not in self.blocks:
                    self.blocks[main_id] = main_strategy
                else:
                    # Update existing block with isMain flag
                    self.blocks[main_id]["isMain"] = True

        # Resolve "Chart" timeframe in block params в†' main_interval from Properties panel
        if self.main_interval:
            self._resolve_chart_timeframes()

        self.params = self._extract_params()

        # Build execution order (topological sort)
        self.execution_order = self._build_execution_order()

        # Cache for computed values
        self._value_cache: dict[str, pd.Series] = {}

        # BTCUSDT OHLCV for use_btcusdt_mfi feature (Фича 3)
        # Pre-loaded by the router; None means feature is disabled / data unavailable.
        self._btcusdt_ohlcv: pd.DataFrame | None = btcusdt_ohlcv

        # Validate
        self._validate_params()

    # в"Ђв"Ђ Connection normalization в"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђ
    # The frontend, AI Builder, and tests send connections in 5+ different
    # key schemas.  _normalize_connections() runs once in __init__ and
    # converts every connection to a flat canonical dict:
    #   {"source_id": str, "target_id": str, "source_port": str, "target_port": str}
    # After that the rest of the codebase does simple key lookups.

    @staticmethod
    def _parse_source_id(conn: dict[str, Any]) -> str:
        """Extract source block ID from any known connection format."""
        if "source" in conn and isinstance(conn["source"], dict):
            return str(conn["source"].get("blockId", ""))
        if "source" in conn and isinstance(conn["source"], str):
            return conn["source"]
        if "source_id" in conn:
            return str(conn["source_id"])
        if "source_block" in conn:
            return str(conn["source_block"])
        return str(conn.get("from", ""))

    @staticmethod
    def _parse_target_id(conn: dict[str, Any]) -> str:
        """Extract target block ID from any known connection format."""
        if "target" in conn and isinstance(conn["target"], dict):
            return str(conn["target"].get("blockId", ""))
        if "target" in conn and isinstance(conn["target"], str):
            return conn["target"]
        if "target_id" in conn:
            return str(conn["target_id"])
        if "target_block" in conn:
            return str(conn["target_block"])
        return str(conn.get("to", ""))

    @staticmethod
    def _parse_source_port(conn: dict[str, Any]) -> str:
        """Extract source port from any known connection format."""
        if "source" in conn and isinstance(conn["source"], dict):
            # Bug #6 fix: use "" not "value" so missing portId doesn't silently
            # match a real port named "value" and lose the signal.
            return str(conn["source"].get("portId", ""))
        if "source_port" in conn:
            return str(conn["source_port"])
        if "source_output" in conn:
            return str(conn["source_output"])
        if "sourcePort" in conn:
            return str(conn["sourcePort"])
        return str(conn.get("fromPort", ""))

    @staticmethod
    def _parse_target_port(conn: dict[str, Any]) -> str:
        """Extract target port from any known connection format."""
        if "target" in conn and isinstance(conn["target"], dict):
            # Bug #6 fix: use "" not "value" so missing portId doesn't silently
            # match a real port named "value" and lose the signal.
            return str(conn["target"].get("portId", ""))
        if "target_port" in conn:
            return str(conn["target_port"])
        if "target_input" in conn:
            return str(conn["target_input"])
        if "targetPort" in conn:
            return str(conn["targetPort"])
        return str(conn.get("toPort", ""))

    @classmethod
    def _normalize_connections(cls, raw_connections: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Normalize connections to canonical format once at init time.

        Supports 5+ connection schemas (old nested, AI Build, frontend camelCase,
        etc.) and converts each to a flat dict with 4 string keys:
        ``source_id``, ``target_id``, ``source_port``, ``target_port``.

        Args:
            raw_connections: List of connection dicts in any supported format.

        Returns:
            List of normalized connection dicts.
        """
        normalized: list[dict[str, str]] = []
        for conn in raw_connections:
            normalized.append(
                {
                    "source_id": cls._parse_source_id(conn),
                    "target_id": cls._parse_target_id(conn),
                    "source_port": cls._parse_source_port(conn),
                    "target_port": cls._parse_target_port(conn),
                }
            )
        return normalized

    def _validate_params(self) -> None:
        """Validate strategy graph structure"""
        if not self.blocks:
            raise ValueError("Strategy graph must contain at least one block")

        # Check for main strategy node
        main_node = None
        for block in self.blocks.values():
            if block.get("type") == "strategy" or block.get("isMain"):
                main_node = block
                break

        if not main_node:
            logger.warning("No main strategy node found. Entry/exit signals may not be connected.")

    def _requires_btcusdt_data(self) -> bool:
        """Return True if any mfi_filter block has use_btcusdt_mfi=True.

        Called by the router BEFORE constructing the adapter so it can pre-load
        BTCUSDT OHLCV and pass it as the btcusdt_ohlcv kwarg.  Can also be
        called as a static helper by passing a raw strategy_graph dict:

            needs_btc = StrategyBuilderAdapter(graph)._requires_btcusdt_data()
        """
        for block in self.blocks.values():
            if block.get("type") == "mfi_filter" and block.get("params", {}).get("use_btcusdt_mfi", False):
                return True
        return False

    # в"Ђв"Ђ "Chart" timeframe resolution в"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђ
    # All param keys ending in "timeframe" that hold "Chart"/"chart"
    # are replaced with the main chart interval from the Properties panel.
    _TIMEFRAME_PARAM_KEYS = frozenset(
        {
            "timeframe",
            "two_mas_timeframe",
            "channel_timeframe",
            "rvi_timeframe",
            "mfi_timeframe",
            "cci_timeframe",
            "momentum_timeframe",
            "channel_close_timeframe",
            "rsi_close_timeframe",
            "stoch_close_timeframe",
        }
    )

    def _resolve_chart_timeframes(self) -> None:
        """Replace "Chart" timeframe values in all block params with main_interval.

        When a user selects "Chart" in a node's timeframe dropdown, it means
        "use the timeframe from the Properties panel" (the main chart TF).
        This method walks all blocks and substitutes "Chart"/"chart" with
        the actual main interval (e.g. "15", "60", "D").
        """
        resolved_count = 0
        for _block_id, block in self.blocks.items():
            params = block.get("params") or block.get("config")
            if not params or not isinstance(params, dict):
                continue
            for key in self._TIMEFRAME_PARAM_KEYS:
                if key in params and isinstance(params[key], str) and params[key].lower() == "chart":
                    params[key] = self.main_interval
                    resolved_count += 1
        if resolved_count:
            logger.debug(
                "[ChartTF] Resolved {} 'Chart' timeframe param(s) в†' '{}' (main interval)",
                resolved_count,
                self.main_interval,
            )

    def _extract_params(self) -> dict[str, Any]:
        """Extract parameters from blocks (supports both 'params' and 'config' keys)"""
        params = {}
        for block_id, block in self.blocks.items():
            block_params = block.get("params") or block.get("config")
            if block_params:
                params[block_id] = block_params
        return params

    def _build_execution_order(self) -> list[str]:
        """
        Build topological sort of blocks based on connections.

        Returns:
            List of block IDs in execution order
        """
        # Build dependency graph
        dependencies: dict[str, list[str]] = {block_id: [] for block_id in self.blocks}

        for conn in self.connections:
            source_id = conn["source_id"]
            target_id = conn["target_id"]
            if target_id in dependencies and source_id:
                dependencies[target_id].append(source_id)

        # Topological sort (Kahn's algorithm)
        in_degree = {block_id: len(deps) for block_id, deps in dependencies.items()}
        queue = deque(block_id for block_id, degree in in_degree.items() if degree == 0)
        result = []

        while queue:
            block_id = queue.popleft()
            result.append(block_id)

            # Find blocks that depend on this one
            for conn in self.connections:
                if conn["source_id"] == block_id:
                    target_id = conn["target_id"]
                    # Only decrement for actual blocks, not special targets like 'main_strategy'
                    if target_id in in_degree:
                        in_degree[target_id] -= 1
                        if in_degree[target_id] == 0:
                            queue.append(target_id)

        # Add any remaining blocks — distinguish disconnected from cyclic
        remaining = [bid for bid in self.blocks if bid not in result]
        if remaining:
            # Blocks with in_degree > 0 after Kahn's are part of a cycle
            connected_block_ids = {c["source_id"] for c in self.connections} | {
                c["target_id"] for c in self.connections
            }
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

    # Block type в†' category mapping for auto-inference when blocks lack 'category'
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
        # (qqe_cross removed — consolidated into universal QQE indicator block)
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
        "static_sltp": "exit",  # was "action": _execute_exit has the handler; _execute_action did not
        # Filter blocks
        "rsi_filter": "filter",
        # (supertrend_filter removed — consolidated into universal supertrend indicator)
        "two_ma_filter": "filter",
        "time_filter": "filter",
        "volatility_filter": "filter",
        "adx_filter": "filter",
        "session_filter": "filter",
        # Exit blocks
        "trailing_stop_exit": "exit",
        "atr_exit": "exit",  # Fix: route to _execute_exit, not empty stub
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
        # (smart_rsi, smart_macd, smart_bollinger removed — Smart Signals category deprecated)
        # (smart_stochastic removed — consolidated into universal stochastic indicator)
        # (smart_supertrend removed — consolidated into universal supertrend indicator)
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
        # Divergence — unified multi-indicator divergence signal block
        "divergence": "divergence",
        # Close condition blocks (Bug fix: were missing from map; _infer_category
        # fell back to "indicator" so _execute_close_condition was never called)
        "close_by_time": "close_conditions",
        "close_channel": "close_conditions",
        "close_ma_cross": "close_conditions",
        "close_rsi": "close_conditions",
        "close_stochastic": "close_conditions",
        "close_psar": "close_conditions",
        # Universal filters (new instruments in РўРµС…РЅРёС‡РµСЃРєРёРµ РРЅРґРёРєР°С,РѕСЂС<)
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

    @classmethod
    def _infer_category(cls, block_type: str) -> str:
        """Infer block category from block type when category field is missing."""
        if block_type in cls._BLOCK_CATEGORY_MAP:
            return cls._BLOCK_CATEGORY_MAP[block_type]
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

    def _execute_block(self, block_id: str, ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """
        Execute a single block and return its outputs.

        Args:
            block_id: Block ID to execute
            ohlcv: OHLCV DataFrame

        Returns:
            Dictionary mapping output port IDs to pd.Series values
        """
        block = self.blocks[block_id]
        block_type = block["type"]
        category = block.get("category", "")
        # Auto-infer category if missing (blocks saved via API may lack it)
        if not category:
            category = self._infer_category(block_type)
            block["category"] = category  # Cache for next use
        # Support both "params" and "config" keys (frontend sends "config", some tests send "params")
        params = block.get("params") or block.get("config") or {}

        # Get input values from cache
        inputs = self._get_block_inputs(block_id)

        # Execute based on block type
        if category == "indicator":
            return self._execute_indicator(block_type, params, ohlcv, inputs)
        elif category == "condition":
            return self._execute_condition(block_type, params, inputs)
        elif category == "input":
            return self._execute_input(block_type, params, ohlcv)
        elif category == "logic":
            return self._execute_logic(block_type, params, inputs)
        elif category == "filter":
            return self._execute_filter(block_type, params, ohlcv, inputs)
        elif category == "action":
            # Action blocks (buy, sell, close, etc.) - return action type for engine
            return self._execute_action(block_type, params, inputs)
        elif category in ("exit", "exits"):
            # Exit condition blocks - return exit signals
            return self._execute_exit(block_type, params, ohlcv, inputs)
        elif category in ("sizing", "position_sizing"):
            # Position sizing blocks - config-only, processed by engine
            return self._execute_position_sizing(block_type, params)
        elif category in ("entry", "entry_refinement", "entry_mgmt"):
            # Entry refinement blocks (DCA, grid, martingale, etc.) - config-only
            return {}
        elif category in ("risk", "risk_controls"):
            # Risk control blocks - config-only
            return {}
        elif category in ("session", "session_mgmt"):
            # Session management blocks - config-only
            return {}
        elif category in ("time", "time_mgmt"):
            # Time management blocks - return time filter
            return self._execute_time_filter(block_type, params, ohlcv)
        elif category == "dca_grid":
            # DCA blocks are config-only, no signal output
            return self._execute_dca_block(block_type, params)
        elif category == "multiple_tp":
            # Multi-TP blocks are config-only
            return {}
        elif category == "signal_memory":
            # Signal memory blocks are config-only
            return {}
        elif category == "price_action":
            # Price action pattern blocks
            return self._execute_price_action(block_type, params, ohlcv)
        elif category == "divergence":
            # Divergence detection blocks
            return self._execute_divergence(block_type, params, ohlcv)
        elif category == "close_conditions":
            # Close condition blocks - return exit signals
            return self._execute_close_condition(block_type, params, ohlcv, inputs)
        elif category == "correlation":
            # Correlation blocks - config-only for multi-symbol
            return {}
        elif category == "alerts":
            # Alert blocks - config-only, processed by alerting system
            return {}
        elif category == "visualization":
            # Visualization blocks - config-only, no signals
            return {}
        # (smart_signals category removed — entire Smart Signals category deprecated)
        elif category == "signal":
            # Signal blocks (long_entry, short_entry, long_exit, short_exit)
            # These pass through condition input to output
            return self._execute_signal_block(block_type, params, inputs)
        else:
            logger.warning(f"Unknown block category: {category} for block {block_id}")
            return {}

    def _get_block_inputs(self, block_id: str) -> dict[str, pd.Series]:
        """Get input values for a block from connections.

        Supports port name aliases: "output" в†" "value", "result" в†" "signal".
        This allows connections to use either canonical or alias port names.
        """
        inputs = {}
        for conn in self.connections:
            target_id = conn["target_id"]
            if target_id == block_id:
                source_id = conn["source_id"]
                source_port = conn["source_port"]
                target_port = conn["target_port"]

                # Get value from cache
                if source_id in self._value_cache:
                    source_outputs = self._value_cache[source_id]
                    if source_port in source_outputs:
                        inputs[target_port] = source_outputs[source_port]
                    else:
                        # Try port aliases (e.g. "output" в†' "value")
                        resolved = False
                        for alias in self._PORT_ALIASES.get(source_port, []):
                            if alias in source_outputs:
                                inputs[target_port] = source_outputs[alias]
                                resolved = True
                                logger.warning(
                                    f"[PortResolver] Port alias fallback: '{source_port}' в†' '{alias}' "
                                    f"for block {source_id} в†' {block_id}. "
                                    f"Available outputs: {list(source_outputs.keys())}"
                                )
                                break
                        if not resolved and len(source_outputs) == 1:
                            # Last resort: if block has only one output, use it
                            only_key = next(iter(source_outputs.keys()))
                            inputs[target_port] = source_outputs[only_key]
                            logger.warning(
                                f"[PortResolver] Single-output fallback: port '{source_port}' not found "
                                f"in block '{source_id}' (outputs: {list(source_outputs.keys())}), "
                                f"using only output '{only_key}' в†' target '{target_port}' on block '{block_id}'"
                            )
                        elif not resolved:
                            logger.warning(
                                f"[PortResolver] Port '{source_port}' not found in block '{source_id}' "
                                f"outputs {list(source_outputs.keys())} and no fallback available. "
                                f"Input '{target_port}' on block '{block_id}' will be missing!"
                            )
        return inputs

    @staticmethod
    def _apply_signal_memory(signal: pd.Series, bars: int) -> pd.Series:
        """Keep a boolean signal active for N bars after it fires.

        Args:
            signal: Boolean Series where True = signal fired.
            bars: Number of bars to keep the signal active.

        Returns:
            Boolean Series with extended signal memory.
        """
        if bars <= 0:
            return signal
        result = signal.copy()
        for i in range(1, bars + 1):
            result = result | signal.shift(i).fillna(False).astype(bool)
        return result

    def _execute_indicator(
        self, indicator_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Execute an indicator block via the unified BLOCK_REGISTRY.

        Steps:
          1. Look up the registry entry for ``indicator_type``.
          2. Apply ``param_aliases`` — translate any old frontend param names to
             the canonical backend names expected by the handler. This lets saved
             strategies that used old param names continue to work without
             touching the handler itself.
          3. Call the handler.
          4. Validate that every key listed in ``outputs`` is present in the
             returned dict. Missing keys mean the handler changed its contract
             without updating the registry — surface this immediately as a
             warning instead of a silent downstream bug (e.g. a port resolving
             to None because the expected key disappeared).
        """
        from backend.backtesting.indicator_handlers import BLOCK_REGISTRY, _require_vbt

        _require_vbt()

        entry = BLOCK_REGISTRY.get(indicator_type)
        if entry is None:
            logger.warning(
                "Unknown indicator type '{}' — not found in BLOCK_REGISTRY. "
                "Register the handler and its output schema there.",
                indicator_type,
            )
            return {}

        # ── Step 2: apply param aliases ─────────────────────────────────────
        aliases: dict[str, str] = entry.get("param_aliases") or {}
        if aliases:
            normalised: dict[str, Any] = {}
            for key, val in params.items():
                canonical = aliases.get(key, key)
                if canonical != key and canonical not in params:
                    # Only rename if the canonical key is not already present
                    # (the user might supply both old and new names)
                    normalised[canonical] = val
                    logger.debug("[ParamAlias] {}: '{}' -> '{}'", indicator_type, key, canonical)
                else:
                    normalised[key] = val
            params = normalised

        # ── Step 3: call handler ─────────────────────────────────────────────
        result: dict[str, Any] = entry["handler"](params, ohlcv, ohlcv["close"], inputs, self)

        # ── Step 4: validate output keys ─────────────────────────────────────
        expected: list[str] = entry.get("outputs") or []
        missing = [k for k in expected if k not in result]
        if missing:
            logger.warning(
                "[RegistryMismatch] Handler for '{}' is missing expected output "
                "key(s): {}. Update BLOCK_REGISTRY outputs or fix the handler.",
                indicator_type,
                missing,
            )

        return result

    def _execute_condition(
        self, condition_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Execute a condition block.

        Supports port name variants from different frontend versions:
        - 'a'/'b' (legacy)
        - 'left'/'right' (current frontend port IDs for greater_than/less_than)
        """
        # Infer series length from inputs (avoids hardcoded sizes)
        ref = next(iter(inputs.values()), None) if inputs else None

        def _empty_bool() -> pd.Series:
            if ref is not None:
                return pd.Series([False] * len(ref), index=ref.index)
            return pd.Series([False], dtype=bool)

        def _empty_numeric() -> pd.Series:
            if ref is not None:
                return pd.Series([0.0] * len(ref), index=ref.index)
            return pd.Series([0.0])

        if condition_type == "crossover":
            a = inputs.get("a", inputs.get("left", _empty_bool()))
            b = inputs.get("b", inputs.get("right", _empty_bool()))
            result = (a > b) & (a.shift(1) <= b.shift(1))
            return {"result": result}

        elif condition_type == "crossunder":
            a = inputs.get("a", inputs.get("left", _empty_bool()))
            b = inputs.get("b", inputs.get("right", _empty_bool()))
            result = (a < b) & (a.shift(1) >= b.shift(1))
            return {"result": result}

        elif condition_type == "greater_than":
            a = inputs.get("a", inputs.get("left", _empty_numeric()))
            b = inputs.get("b", inputs.get("right", _empty_numeric()))
            result = a > b
            return {"result": result}

        elif condition_type == "less_than":
            a = inputs.get("a", inputs.get("left", _empty_numeric()))
            b = inputs.get("b", inputs.get("right", _empty_numeric()))
            result = a < b
            return {"result": result}

        elif condition_type == "equals":
            a = inputs.get("a", inputs.get("left", _empty_numeric()))
            b = inputs.get("b", inputs.get("right", _empty_numeric()))
            tolerance = float(params.get("tolerance", 0.0001))
            result = (a - b).abs() <= tolerance
            return {"result": result}

        elif condition_type == "between":
            value = inputs.get("value", _empty_numeric())
            min_val = inputs.get("min", _empty_numeric())
            max_val = inputs.get("max", _empty_numeric())
            result = (value >= min_val) & (value <= max_val)
            return {"result": result}

        else:
            logger.warning(f"Unknown condition type: {condition_type}")
            return {"result": _empty_bool()}

    def _execute_input(self, input_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """Execute an input block"""
        if input_type == "price":
            return {
                "open": ohlcv["open"],
                "high": ohlcv["high"],
                "low": ohlcv["low"],
                "close": ohlcv["close"],
                "value": ohlcv["close"],  # Alias for compatibility with connections
            }
        elif input_type == "volume":
            return {"value": ohlcv["volume"]}
        elif input_type == "constant":
            value = params.get("value", 0)
            n = len(ohlcv)
            return {"value": pd.Series([value] * n, index=ohlcv.index)}
        else:
            logger.warning(f"Unknown input type: {input_type}")
            return {}

    def _execute_logic(
        self, logic_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Execute a logic block"""

        # Infer series length from inputs (avoids hardcoded sizes)
        def _default_bool(n: int, fill: bool = False) -> pd.Series:
            ref = next(iter(inputs.values()), None) if inputs else None
            if ref is not None:
                return pd.Series([fill] * len(ref), index=ref.index)
            return pd.Series([fill] * n)

        def _default_numeric(n: int, fill: float = 0.0) -> pd.Series:
            ref = next(iter(inputs.values()), None) if inputs else None
            if ref is not None:
                return pd.Series([fill] * len(ref), index=ref.index)
            return pd.Series([fill] * n)

        if logic_type == "and":
            a = inputs.get("a", _default_bool(0))
            b = inputs.get("b", _default_bool(0))
            result = a & b
            # Support optional 3rd input (C port)
            if "c" in inputs:
                result = result & inputs["c"]
            return {"result": result}

        elif logic_type == "or":
            a = inputs.get("a", _default_bool(0))
            b = inputs.get("b", _default_bool(0))
            result = a | b
            # Support optional 3rd input (C port)
            if "c" in inputs:
                result = result | inputs["c"]
            return {"result": result}

        elif logic_type == "not":
            input_val = inputs.get("input", _default_bool(0))
            return {"result": ~input_val}

        elif logic_type == "delay":
            bars = params.get("bars", 1)
            input_val = inputs.get("input", _default_bool(0))
            return {"result": input_val.shift(bars).fillna(False).astype(bool)}

        elif logic_type == "filter":
            signal = inputs.get("signal", _default_bool(0))
            filter_val = inputs.get("filter", _default_bool(0, fill=True))
            return {"result": signal & filter_val}

        elif logic_type == "comparison":
            # Comparison block - compare two values with an operator
            # Inputs: value_a, value_b (numeric series)
            # Params: operator (>, <, >=, <=, ==, !=, crosses_above, crosses_below)
            # Output: result (boolean series)
            a = inputs.get("value_a", inputs.get("a", _default_numeric(0)))
            b = inputs.get("value_b", inputs.get("b", _default_numeric(0)))
            op = params.get("operator", "==")

            # Ensure series are aligned
            if len(a) != len(b):
                # Try to broadcast if one is scalar
                if len(a) == 1:
                    a = pd.Series([float(a.iloc[0])] * len(b), index=b.index)
                elif len(b) == 1:
                    b = pd.Series([float(b.iloc[0])] * len(a), index=a.index)

            if op == ">":
                result = a > b
            elif op == "<":
                result = a < b
            elif op == ">=":
                result = a >= b
            elif op == "<=":
                result = a <= b
            elif op == "==":
                result = a == b
            elif op == "!=":
                result = a != b
            elif op == "crosses_above":
                # a crosses above b: a[i] > b[i] and a[i-1] <= b[i-1]
                above_now = a > b
                below_before = a.shift(1) <= b.shift(1)
                result = above_now & below_before
                result = result.fillna(False)
            elif op == "crosses_below":
                # a crosses below b: a[i] < b[i] and a[i-1] >= b[i-1]
                below_now = a < b
                above_before = a.shift(1) >= b.shift(1)
                result = below_now & above_before
                result = result.fillna(False)
            else:
                logger.warning(f"Unknown comparison operator: {op}")
                result = pd.Series([False] * len(a), index=a.index)

            return {"result": result}

        else:
            logger.warning(f"Unknown logic type: {logic_type}")
            return {"result": _default_bool(0)}

    def _execute_filter(
        self, filter_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """
        Execute a filter block - generates buy/sell signals based on indicator conditions.

        Filters are self-contained signal generators that compute indicators internally
        and return buy/sell boolean series.
        """
        n = len(ohlcv)
        close = ohlcv["close"].values
        high = ohlcv["high"].values
        low = ohlcv["low"].values
        volume = ohlcv["volume"].values

        # Helper for crossover detection (using shift to avoid np.roll wraparound)
        def crossover(a, b):
            a_prev = pd.Series(a).shift(1).fillna(a[0] if len(a) > 0 else 0).values
            b_prev = pd.Series(b).shift(1).fillna(b[0] if len(b) > 0 else 0).values
            return (a > b) & (a_prev <= b_prev)

        def crossunder(a, b):
            a_prev = pd.Series(a).shift(1).fillna(a[0] if len(a) > 0 else 0).values
            b_prev = pd.Series(b).shift(1).fillna(b[0] if len(b) > 0 else 0).values
            return (a < b) & (a_prev >= b_prev)

        def apply_signal_memory(
            buy_events: np.ndarray,
            sell_events: np.ndarray,
            memory_bars: int,
        ) -> tuple[np.ndarray, np.ndarray]:
            """
            Extend buy/sell signals for N bars after each event; opposite signal cancels.

            If a buy occurs at bar i, buy is True for bars i..i+N unless a sell occurs
            in that window (then buy memory stops at that bar). Same for sell.
            """
            n = len(buy_events)
            buy_out = np.zeros(n, dtype=bool)
            sell_out = np.zeros(n, dtype=bool)
            active_buy_until = -1
            active_sell_until = -1
            for i in range(n):
                if sell_events[i]:
                    active_buy_until = -1
                if buy_events[i]:
                    active_buy_until = i + memory_bars
                buy_out[i] = active_buy_until >= i
                if buy_events[i]:
                    active_sell_until = -1
                if sell_events[i]:
                    active_sell_until = i + memory_bars
                sell_out[i] = active_sell_until >= i
            return buy_out, sell_out

        # ========== RSI Filter ==========
        if filter_type == "rsi_filter":
            period = params.get("period", 14)
            oversold = params.get("oversold", 30)
            overbought = params.get("overbought", 70)
            mode = params.get("mode", "range")  # range, cross

            rsi = calculate_rsi(close, period)

            if mode == "range":
                buy = rsi < oversold
                sell = rsi > overbought
            else:  # cross
                buy = crossunder(rsi, np.full(n, oversold))
                sell = crossover(rsi, np.full(n, overbought))

            mem_bars = int(params.get("signal_memory_bars", 0))
            if mem_bars > 0 and (params.get("signal_memory_enable", False) or params.get("use_signal_memory", False)):
                buy, sell = apply_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "value": pd.Series(rsi, index=ohlcv.index),
            }

        # (QQE Filter removed — consolidated into universal QQE indicator block)

        # (SuperTrend Filter removed — consolidated into universal SuperTrend indicator block)

        # ========== Two MA Filter ==========
        elif filter_type == "two_ma_filter":
            fast_period = _param(params, 9, "fast_period", "fastPeriod")
            slow_period = _param(params, 21, "slow_period", "slowPeriod")
            ma_type = _param(params, "ema", "ma_type", "maType")

            if ma_type == "ema":
                fast = calculate_ema(close, fast_period)
                slow = calculate_ema(close, slow_period)
            else:
                fast = calculate_sma(close, fast_period)
                slow = calculate_sma(close, slow_period)

            buy = crossover(fast, slow)
            sell = crossunder(fast, slow)

            mem_bars = int(params.get("ma_cross_memory_bars", 0))
            if mem_bars > 0:
                buy, sell = apply_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "fast": pd.Series(fast, index=ohlcv.index),
                "slow": pd.Series(slow, index=ohlcv.index),
            }

        # (Stochastic Filter removed — consolidated into universal Stochastic indicator block)

        # ========== MACD Filter ==========
        elif filter_type == "macd_filter":
            macd_fast_p: int = int(_param(params, 12, "fast_period", "fast"))
            macd_slow_p: int = int(_param(params, 26, "slow_period", "slow"))
            signal_period: int = int(_param(params, 9, "signal_period", "signal"))
            mode = params.get("mode", "signal_cross")  # signal_cross, zero_cross, histogram

            macd_line, signal_line, histogram = calculate_macd(close, macd_fast_p, macd_slow_p, signal_period)

            if mode == "zero_cross":
                buy = crossover(macd_line, np.zeros(n))
                sell = crossunder(macd_line, np.zeros(n))
            elif mode == "histogram":
                hist_prev = pd.Series(histogram).shift(1).fillna(0).values
                buy = (histogram > 0) & (hist_prev <= 0)
                sell = (histogram < 0) & (hist_prev >= 0)
            else:  # signal_cross
                buy = crossover(macd_line, signal_line)
                sell = crossunder(macd_line, signal_line)

            mem_bars = int(params.get("macd_signal_memory_bars", 0))
            if mem_bars > 0 and not params.get("disable_macd_signal_memory", True):
                buy, sell = apply_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "macd": pd.Series(macd_line, index=ohlcv.index),
                "signal": pd.Series(signal_line, index=ohlcv.index),
                "histogram": pd.Series(histogram, index=ohlcv.index),
            }

        # ========== CCI Filter ==========
        elif filter_type == "cci_filter":
            period = params.get("period", 20)
            oversold = params.get("oversold", -100)
            overbought = params.get("overbought", 100)

            cci = calculate_cci(high, low, close, period)

            buy = crossunder(cci, np.full(n, oversold))
            sell = crossover(cci, np.full(n, overbought))

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "value": pd.Series(cci, index=ohlcv.index),
            }

        # ========== DMI/ADX Filter ==========
        elif filter_type == "dmi_filter":
            period = params.get("period", 14)
            adx_threshold = _param(params, 25, "threshold", "adxThreshold")

            adx_result = calculate_adx(high, low, close, period)
            adx = adx_result.adx
            plus_di = adx_result.plus_di
            minus_di = adx_result.minus_di

            # Buy when +DI crosses above -DI and ADX > threshold
            buy = crossover(plus_di, minus_di) & (adx > adx_threshold)
            sell = crossunder(plus_di, minus_di) & (adx > adx_threshold)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "adx": pd.Series(adx, index=ohlcv.index),
                "plus_di": pd.Series(plus_di, index=ohlcv.index),
                "minus_di": pd.Series(minus_di, index=ohlcv.index),
            }

        # ========== ATR Filter ==========
        elif filter_type == "atr_filter":
            period = params.get("period", 14)
            threshold = params.get("threshold", 1.5)  # ATR multiplier

            atr = calculate_atr(high, low, close, period)
            atr_ma = pd.Series(atr).rolling(period).mean().values

            # High volatility when ATR > threshold * average ATR
            high_volatility = atr > (threshold * atr_ma)

            return {
                "pass": pd.Series(high_volatility, index=ohlcv.index),
                "value": pd.Series(atr, index=ohlcv.index),
            }

        # ========== Volume Filter ==========
        elif filter_type == "volume_filter":
            period = params.get("period", 20)
            multiplier = params.get("multiplier", 1.5)

            volume_ma = pd.Series(volume).rolling(period).mean().values
            high_volume = volume > (multiplier * volume_ma)

            return {
                "pass": pd.Series(high_volume, index=ohlcv.index),
                "value": pd.Series(volume, index=ohlcv.index),
                "ma": pd.Series(volume_ma, index=ohlcv.index),
            }

        # ========== Volume Compare Filter ==========
        elif filter_type == "volume_compare_filter":
            period = params.get("period", 20)
            multiplier = params.get("multiplier", 2.0)

            volume_ma = pd.Series(volume).rolling(period).mean().values
            above_avg = volume > (multiplier * volume_ma)

            return {
                "pass": pd.Series(above_avg, index=ohlcv.index),
                "ratio": pd.Series(volume / np.maximum(volume_ma, 1), index=ohlcv.index),
            }

        # ========== CMF Filter ==========
        elif filter_type == "cmf_filter":
            period = params.get("period", 20)
            threshold = params.get("threshold", 0.05)

            cmf = calculate_cmf(high, low, close, volume, period)

            buy = cmf > threshold
            sell = cmf < -threshold

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "value": pd.Series(cmf, index=ohlcv.index),
            }

        # ========== Trend Filter ==========
        elif filter_type == "trend_filter":
            ema_period = params.get("emaPeriod", 50)
            adx_period = params.get("adxPeriod", 14)
            adx_threshold = _param(params, 25, "threshold", "adxThreshold")

            ema = calculate_ema(close, ema_period)
            adx_result = calculate_adx(high, low, close, adx_period)

            uptrend = (close > ema) & (adx_result.adx > adx_threshold)
            downtrend = (close < ema) & (adx_result.adx > adx_threshold)

            return {
                "uptrend": pd.Series(uptrend, index=ohlcv.index),
                "downtrend": pd.Series(downtrend, index=ohlcv.index),
                "ema": pd.Series(ema, index=ohlcv.index),
                "adx": pd.Series(adx_result.adx, index=ohlcv.index),
            }

        # ========== Price Filter ==========
        elif filter_type == "price_filter":
            level = params.get("level", 0)
            mode = params.get("mode", "above")  # above, below
            result = close > level if mode == "above" else close < level

            return {"pass": pd.Series(result, index=ohlcv.index)}

        # ========== Volatility Filter ==========
        elif filter_type == "volatility_filter":
            period = params.get("period", 20)
            mode = params.get("mode", "atr")  # atr, bb_width
            threshold = params.get("threshold", 1.0)

            if mode == "bb_width":
                bb_mid, bb_upper, bb_lower = calculate_bollinger(close, period, 2.0)
                bb_width = (bb_upper - bb_lower) / np.where(bb_mid != 0, bb_mid, 1.0)
                bb_width_ma = pd.Series(bb_width).rolling(period).mean().values
                high_vol = bb_width > (threshold * bb_width_ma)
                return {"pass": pd.Series(high_vol, index=ohlcv.index), "value": pd.Series(bb_width, index=ohlcv.index)}
            else:
                atr = calculate_atr(high, low, close, period)
                atr_ma = pd.Series(atr).rolling(period).mean().values
                high_vol = atr > (threshold * atr_ma)
                return {"pass": pd.Series(high_vol, index=ohlcv.index), "value": pd.Series(atr, index=ohlcv.index)}

        # ========== Highest/Lowest Filter ==========
        elif filter_type == "highest_lowest_filter":
            period = params.get("period", 20)

            highest = pd.Series(high).rolling(period).max().values
            lowest = pd.Series(low).rolling(period).min().values

            breakout_up = close >= highest
            breakout_down = close <= lowest

            return {
                "buy": pd.Series(breakout_up, index=ohlcv.index),
                "sell": pd.Series(breakout_down, index=ohlcv.index),
                "highest": pd.Series(highest, index=ohlcv.index),
                "lowest": pd.Series(lowest, index=ohlcv.index),
            }

        # ========== Momentum Filter ==========
        elif filter_type == "momentum_filter":
            period = params.get("period", 10)
            threshold = params.get("threshold", 0)

            momentum = close - pd.Series(close).shift(period).fillna(0).values

            buy = momentum > threshold
            sell = momentum < -threshold

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "value": pd.Series(momentum, index=ohlcv.index),
            }

        # ========== Time Filter ==========
        elif filter_type == "time_filter":
            start_hour = params.get("startHour", 9)
            end_hour = params.get("endHour", 17)

            hours = ohlcv.index.hour if hasattr(ohlcv.index, "hour") else np.zeros(n)
            in_session = (hours >= start_hour) & (hours < end_hour)

            return {"pass": pd.Series(in_session, index=ohlcv.index)}

        # ========== Accumulation Filter ==========
        elif filter_type == "accumulation_filter":
            # Detect volume accumulation zones
            period = params.get("period", 20)
            volume_mult = params.get("volume_multiplier", 1.5)
            range_threshold = params.get("range_threshold", 0.5)  # ATR multiplier

            volume = ohlcv["volume"]
            avg_volume = volume.rolling(period).mean()
            high_volume = volume > avg_volume * volume_mult

            # Price range compression (consolidation)
            atr = pd.Series(
                calculate_atr(ohlcv["high"].values, ohlcv["low"].values, ohlcv["close"].values, period),
                index=ohlcv.index,
            )
            price_range = ohlcv["high"] - ohlcv["low"]
            avg_range = price_range.rolling(period).mean()
            tight_range = price_range < avg_range * range_threshold

            # Accumulation: high volume + tight range
            accumulation = high_volume & tight_range

            # Distribution: high volume + wide range
            distribution = high_volume & ~tight_range

            return {
                "accumulation": accumulation.fillna(False),
                "distribution": distribution.fillna(False),
                "buy": accumulation.fillna(False),
                "sell": distribution.fillna(False),
            }

        # ========== Linear Regression Filter ==========
        elif filter_type == "linreg_filter":
            # Linear regression channel filter
            period = params.get("period", 20)
            dev_mult = params.get("deviation", 2.0)
            mode = params.get("mode", "trend")  # trend, channel_break, slope

            close = ohlcv["close"]

            # Calculate linear regression
            def linreg(series, length):
                """Calculate linear regression value."""
                x = np.arange(length)
                result = np.full(len(series), np.nan)
                for i in range(length - 1, len(series)):
                    y = series.iloc[i - length + 1 : i + 1].values
                    if len(y) == length:
                        slope, intercept = np.polyfit(x, y, 1)
                        result[i] = intercept + slope * (length - 1)
                return result

            def linreg_slope(series, length):
                """Calculate linear regression slope."""
                x = np.arange(length)
                result = np.full(len(series), np.nan)
                for i in range(length - 1, len(series)):
                    y = series.iloc[i - length + 1 : i + 1].values
                    if len(y) == length:
                        slope, _ = np.polyfit(x, y, 1)
                        result[i] = slope
                return result

            linreg_val = pd.Series(linreg(close, period), index=ohlcv.index)
            slope = pd.Series(linreg_slope(close, period), index=ohlcv.index)

            # Standard deviation for channel
            residuals = close - linreg_val
            std = residuals.rolling(period).std()
            upper = linreg_val + dev_mult * std
            lower = linreg_val - dev_mult * std

            if mode == "trend":
                # Uptrend: positive slope, price above linreg
                buy = (slope > 0) & (close > linreg_val)
                sell = (slope < 0) & (close < linreg_val)
            elif mode == "channel_break":
                # Buy on upper break, sell on lower break
                buy = close > upper
                sell = close < lower
            else:  # slope
                # Buy on positive slope, sell on negative
                buy = slope > 0
                sell = slope < 0

            return {
                "buy": buy.fillna(False),
                "sell": sell.fillna(False),
                "linreg": linreg_val,
                "slope": slope,
                "upper": upper,
                "lower": lower,
            }

        # (divergence_filter removed — old divergence blocks cleared)

        # ========== Balance of Power Filter ==========
        elif filter_type == "bop_filter":
            # Balance of Power indicator filter
            period = params.get("period", 14)
            threshold = params.get("threshold", 0.0)
            mode = params.get("mode", "level")  # level, cross, trend

            # BOP = (Close - Open) / (High - Low)
            high = ohlcv["high"]
            low = ohlcv["low"]
            open_price = ohlcv["open"]
            close = ohlcv["close"]

            bop = (close - open_price) / (high - low + 1e-10)
            bop_smooth = bop.rolling(period).mean()

            if mode == "level":
                # Buy when BOP above threshold, sell when below
                buy = bop_smooth > threshold
                sell = bop_smooth < -threshold
            elif mode == "cross":
                # Buy on cross above zero, sell on cross below
                buy = (bop_smooth > 0) & (bop_smooth.shift(1) <= 0)
                sell = (bop_smooth < 0) & (bop_smooth.shift(1) >= 0)
            else:  # trend
                # Buy on rising BOP, sell on falling
                buy = bop_smooth > bop_smooth.shift(1)
                sell = bop_smooth < bop_smooth.shift(1)

            return {
                "buy": buy.fillna(False),
                "sell": sell.fillna(False),
                "value": bop_smooth,
            }

        # ========== Levels Break Filter ==========
        elif filter_type == "levels_filter":
            # Pivot/Support/Resistance break filter
            period = params.get("period", 20)
            level_type = params.get("level_type", "pivot")  # pivot, swing, fixed

            high = ohlcv["high"]
            low = ohlcv["low"]
            close = ohlcv["close"]

            if level_type == "pivot":
                # Use pivot points
                pp = (high.shift(1) + low.shift(1) + close.shift(1)) / 3
                r1 = 2 * pp - low.shift(1)
                s1 = 2 * pp - high.shift(1)

                buy = close > r1  # Break above R1
                sell = close < s1  # Break below S1

                return {
                    "buy": buy.fillna(False),
                    "sell": sell.fillna(False),
                    "pivot": pp,
                    "r1": r1,
                    "s1": s1,
                }
            else:  # swing
                # Swing high/low breaks
                swing_high = high.rolling(period).max()
                swing_low = low.rolling(period).min()

                buy = close > swing_high.shift(1)  # Break above swing high
                sell = close < swing_low.shift(1)  # Break below swing low

                return {
                    "buy": buy.fillna(False),
                    "sell": sell.fillna(False),
                    "swing_high": swing_high,
                    "swing_low": swing_low,
                }

        # ========== Price Action Filter ==========
        elif filter_type == "price_action_filter":
            # Candlestick pattern filter
            pattern = params.get("pattern", "engulfing")

            o = ohlcv["open"]
            h = ohlcv["high"]
            low = ohlcv["low"]
            c = ohlcv["close"]
            body = abs(c - o)

            if pattern == "engulfing":
                # Bullish engulfing
                prev_red = o.shift(1) > c.shift(1)
                curr_green = c > o
                engulfs = (c > o.shift(1)) & (o < c.shift(1))
                bullish = prev_red & curr_green & engulfs

                # Bearish engulfing
                prev_green = c.shift(1) > o.shift(1)
                curr_red = o > c
                engulfs_bear = (o > c.shift(1)) & (c < o.shift(1))
                bearish = prev_green & curr_red & engulfs_bear

            elif pattern == "doji":
                # Doji: small body
                avg_body = body.rolling(20).mean()
                doji = body < avg_body * 0.1
                bullish = doji & (c > o)
                bearish = doji & (c < o)

            elif pattern == "hammer":
                # Hammer: long lower wick
                lower_wick = pd.concat([o, c], axis=1).min(axis=1) - low
                upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
                bullish = (lower_wick > body * 2) & (upper_wick < body * 0.5)
                bearish = (upper_wick > body * 2) & (lower_wick < body * 0.5)

            else:
                bullish = pd.Series([False] * n, index=ohlcv.index)
                bearish = pd.Series([False] * n, index=ohlcv.index)

            return {
                "buy": bullish.fillna(False),
                "sell": bearish.fillna(False),
            }

        # ========== Default: Unknown filter ==========
        else:
            logger.warning(f"Unknown filter type: {filter_type}")
            return {
                "buy": pd.Series([False] * n, index=ohlcv.index),
                "sell": pd.Series([False] * n, index=ohlcv.index),
            }

    def _execute_signal_block(
        self, signal_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """
        Execute signal blocks (long_entry, short_entry, long_exit, short_exit, signal).

        Signal blocks receive a boolean condition and output it as the appropriate
        signal type. They act as the terminal nodes that define entry/exit signals.

        Supported signal types:
            - long_entry: Generate long entry signal
            - short_entry: Generate short entry signal
            - long_exit: Generate long exit signal
            - short_exit: Generate short exit signal
            - signal: Universal signal block that receives signals on multiple ports
                      (entry_long, exit_long, entry_short, exit_short)

        Args:
            signal_type: Type of signal block
            params: Block parameters
            inputs: Input values from connected blocks

        Returns:
            Dictionary with signal output
        """
        result: dict[str, pd.Series] = {}

        # Handle universal "signal" block type that receives multiple signal inputs
        if signal_type == "signal":
            # Universal signal block - each input port maps directly to output
            n = len(next(iter(inputs.values()))) if inputs else 100

            # Check for entry_long input
            if "entry_long" in inputs:
                sig = inputs["entry_long"]
                if sig.dtype != bool:
                    sig = sig.astype(bool)
                result["entry_long"] = sig

            # Check for exit_long input
            if "exit_long" in inputs:
                sig = inputs["exit_long"]
                if sig.dtype != bool:
                    sig = sig.astype(bool)
                result["exit_long"] = sig

            # Check for entry_short input
            if "entry_short" in inputs:
                sig = inputs["entry_short"]
                if sig.dtype != bool:
                    sig = sig.astype(bool)
                result["entry_short"] = sig

            # Check for exit_short input
            if "exit_short" in inputs:
                sig = inputs["exit_short"]
                if sig.dtype != bool:
                    sig = sig.astype(bool)
                result["exit_short"] = sig

            # Also support generic "signal" or "condition" input for backwards compat
            for key in ["signal", "condition", "result", "input", "output"]:
                if key in inputs and key not in ["entry_long", "exit_long", "entry_short", "exit_short"]:
                    sig = inputs[key]
                    if sig.dtype != bool:
                        sig = sig.astype(bool)
                    result["signal"] = sig
                    break

            # If no outputs generated, return empty signals
            if not result:
                empty = pd.Series([False] * n)
                result = {"signal": empty}

            return result

        # Handle specific signal types (long_entry, short_entry, etc.)
        # Get input signal (from condition, result, or signal port)
        input_signal = None
        for key in ["condition", "result", "signal", "input", "output"]:
            if key in inputs:
                input_signal = inputs[key]
                break

        if input_signal is None:
            # No input - return empty signal
            n = len(next(iter(inputs.values()))) if inputs else 100
            return {"signal": pd.Series([False] * n)}

        # Ensure it's a boolean series
        if input_signal.dtype != bool:
            input_signal = input_signal.astype(bool)

        result = {"signal": input_signal}

        if signal_type in ["long_entry", "entry_long", "buy_signal"]:
            result["entry_long"] = input_signal
        elif signal_type in ["short_entry", "entry_short", "sell_signal"]:
            result["entry_short"] = input_signal
        elif signal_type in ["long_exit", "exit_long", "close_long"]:
            result["exit_long"] = input_signal
        elif signal_type in ["short_exit", "exit_short", "close_short"]:
            result["exit_short"] = input_signal
        else:
            logger.warning(f"Unknown signal type: {signal_type}")

        return result

    # (Smart Signals section removed — entire category deprecated in favor of universal indicator blocks)

    def _execute_action(
        self, action_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """
        Execute action blocks (buy, sell, close, etc.).

        Action blocks generate entry/exit signals based on input conditions.

        Supported action types:
            - buy, buy_market, buy_limit: Long entry
            - sell, sell_market, sell_limit: Short entry
            - close_long, close_short, close_all: Exit signals
            - stop_loss, take_profit: Exit with price levels
            - trailing_stop: Exit with trailing
        """
        # Get input signal (from condition or filter block)
        input_signal = None
        for key in ["signal", "condition", "output"]:
            if key in inputs:
                input_signal = inputs[key]
                break

        if input_signal is None:
            # No input - action doesn't trigger
            n = len(next(iter(inputs.values()))) if inputs else 0
            empty_signal = pd.Series([False] * n)
            return {"signal": empty_signal}

        # Pass through signal based on action type
        result: dict[str, pd.Series] = {}

        if action_type in ["buy", "buy_market", "buy_limit"]:
            result["entry_long"] = input_signal
            result["signal"] = input_signal

        elif action_type in ["sell", "sell_market", "sell_limit"]:
            result["entry_short"] = input_signal
            result["signal"] = input_signal

        elif action_type == "close_long":
            result["exit_long"] = input_signal
            result["signal"] = input_signal

        elif action_type == "close_short":
            result["exit_short"] = input_signal
            result["signal"] = input_signal

        elif action_type == "close_all":
            result["exit_long"] = input_signal
            result["exit_short"] = input_signal
            result["signal"] = input_signal

        elif action_type == "stop_loss":
            # Stop loss configuration
            percent = params.get("percent", 2.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["stop_loss_percent"] = percent

        elif action_type == "take_profit":
            # Take profit configuration
            percent = params.get("percent", 3.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["take_profit_percent"] = percent

        elif action_type == "trailing_stop":
            # Trailing stop configuration
            percent = params.get("percent", 1.5)
            activation = params.get("activation", 1.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["trailing_percent"] = percent
            result["trailing_activation"] = activation

        elif action_type == "atr_stop":
            # ATR-based stop loss
            period = params.get("period", 14)
            multiplier = params.get("multiplier", 2.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["atr_period"] = period
            result["atr_multiplier"] = multiplier

        elif action_type == "chandelier_stop":
            # Chandelier stop (from highest high - ATR)
            period = params.get("period", 22)
            multiplier = params.get("multiplier", 3.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["chandelier_period"] = period
            result["chandelier_multiplier"] = multiplier

        elif action_type == "break_even":
            # Move stop to entry price after X% profit
            trigger = params.get("trigger_percent", 1.0)
            offset = params.get("offset", 0.0)  # Small offset above/below entry
            result["signal"] = input_signal
            result["breakeven_trigger"] = trigger
            result["breakeven_offset"] = offset

        elif action_type == "profit_lock":
            # Lock minimum profit after threshold
            trigger = params.get("trigger_percent", 2.0)
            lock = params.get("lock_percent", 1.0)
            result["signal"] = input_signal
            result["profit_lock_trigger"] = trigger
            result["profit_lock_amount"] = lock

        elif action_type == "scale_out":
            # Partial position close
            percent = params.get("close_percent", 50.0)
            at_profit = params.get("at_profit", 1.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["scale_out_percent"] = percent
            result["scale_out_at_profit"] = at_profit

        elif action_type == "multi_tp":
            # Multi take profit levels
            tp1 = params.get("tp1_percent", 1.0)
            tp1_close = params.get("tp1_close", 30.0)
            tp2 = params.get("tp2_percent", 2.0)
            tp2_close = params.get("tp2_close", 30.0)
            tp3 = params.get("tp3_percent", 3.0)
            tp3_close = params.get("tp3_close", 40.0)
            result["signal"] = input_signal
            result["multi_tp_levels"] = [
                {"percent": tp1, "close": tp1_close},
                {"percent": tp2, "close": tp2_close},
                {"percent": tp3, "close": tp3_close},
            ]

        elif action_type == "limit_entry":
            # Limit order entry at specific price
            price = params.get("price", 0)
            offset = params.get("offset_percent", 0)
            result["entry_long"] = input_signal
            result["signal"] = input_signal
            result["limit_price"] = price
            result["limit_offset"] = offset
            result["order_type"] = "limit"

        elif action_type == "stop_entry":
            # Stop order entry on breakout
            price = params.get("price", 0)
            offset = params.get("offset_percent", 0)
            result["entry_long"] = input_signal
            result["signal"] = input_signal
            result["stop_price"] = price
            result["stop_offset"] = offset
            result["order_type"] = "stop"

        elif action_type == "close":
            # Close current position (any direction)
            result["exit_long"] = input_signal
            result["exit_short"] = input_signal
            result["signal"] = input_signal

        else:
            result["signal"] = input_signal

        return result

    def _execute_exit(
        self, exit_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """
        Execute exit condition blocks.

        Exit blocks generate exit signals based on price conditions or indicators.

        Supported exit types:
            - static_sltp: Unified fixed % SL/TP with breakeven
            - tp_percent, sl_percent: Legacy fixed % take profit / stop loss
            - trailing_stop_exit: Trailing stop
            - atr_stop, atr_tp: ATR-based exits
            - time_exit: Exit after N bars
            - breakeven_exit: Move stop to breakeven
            - chandelier_exit: Chandelier exit
        """
        n = len(ohlcv)
        result: dict[str, pd.Series] = {}

        if exit_type == "static_sltp":
            # Unified static SL/TP — config-only block, engine handles execution
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            # Pass SL/TP values for engine config extraction
            result["stop_loss_percent"] = params.get("stop_loss_percent", 1.5)
            result["take_profit_percent"] = params.get("take_profit_percent", 1.5)
            result["close_only_in_profit"] = params.get("close_only_in_profit", False)
            result["activate_breakeven"] = params.get("activate_breakeven", False)
            result["breakeven_activation_percent"] = params.get("breakeven_activation_percent", 0.5)
            result["new_breakeven_sl_percent"] = params.get("new_breakeven_sl_percent", 0.1)

        elif exit_type in ("tp_percent", "sl_percent"):
            # Legacy blocks — kept for backward compatibility
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)

        elif exit_type == "trailing_stop_exit":
            # Trailing stop is config-only — engine handles bar-by-bar execution.
            # Pass params so generate_signals can relay them via extra_data.
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["trailing_activation_percent"] = params.get("activation_percent", 1.0)
            result["trailing_percent"] = params.get("trailing_percent", 0.5)
            result["trail_type"] = params.get("trail_type", "percent")

        elif exit_type == "atr_stop":
            # ATR-based stop loss
            period = params.get("period", 14)
            multiplier = params.get("multiplier", 2.0)
            atr = pd.Series(
                calculate_atr(ohlcv["high"].values, ohlcv["low"].values, ohlcv["close"].values, period),
                index=ohlcv.index,
            )
            # Exit signal: price breaks below entry - ATR*multiplier
            # This needs position tracking, return empty for now
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["atr"] = atr

        elif exit_type == "time_exit":
            # Exit after N bars - needs position tracking
            bars = params.get("bars", 10)
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["max_bars"] = pd.Series([bars] * n, index=ohlcv.index)

        elif exit_type in ("breakeven_exit", "break_even_exit"):
            # Move to breakeven after X% profit
            trigger_pct = params.get("trigger_percent", 1.0)
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["breakeven_trigger"] = trigger_pct

        elif exit_type == "chandelier_exit":
            # Chandelier exit - ATR-based trailing
            period = params.get("period", 22)
            multiplier = params.get("multiplier", 3.0)
            atr = pd.Series(
                calculate_atr(ohlcv["high"].values, ohlcv["low"].values, ohlcv["close"].values, period),
                index=ohlcv.index,
            )
            high_n = ohlcv["high"].rolling(period).max()
            low_n = ohlcv["low"].rolling(period).min()

            # Long exit: close below highest high - ATR*mult
            long_exit_level = high_n - atr * multiplier
            # Short exit: close above lowest low + ATR*mult
            short_exit_level = low_n + atr * multiplier

            result["exit_long"] = ohlcv["close"] < long_exit_level
            result["exit_short"] = ohlcv["close"] > short_exit_level
            result["exit"] = result["exit_long"] | result["exit_short"]

        elif exit_type == "atr_exit":
            # ATR-based TP/SL exit with separate smoothing methods and periods

            use_atr_sl = params.get("use_atr_sl", False)
            use_atr_tp = params.get("use_atr_tp", False)

            high_arr = ohlcv["high"].values
            low_arr = ohlcv["low"].values
            close_arr = ohlcv["close"].values

            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["use_atr_sl"] = use_atr_sl
            result["use_atr_tp"] = use_atr_tp

            if use_atr_sl:
                sl_period = max(1, min(150, int(params.get("atr_sl_period", 150))))
                sl_smoothing = params.get("atr_sl_smoothing", "WMA")
                if sl_smoothing not in ("WMA", "RMA", "SMA", "EMA"):
                    sl_smoothing = "RMA"
                sl_mult = max(0.1, min(4.0, float(params.get("atr_sl_multiplier", 4.0))))
                sl_on_wicks = params.get("atr_sl_on_wicks", False)
                atr_sl = pd.Series(
                    calculate_atr_smoothed(high_arr, low_arr, close_arr, period=sl_period, method=sl_smoothing),
                    index=ohlcv.index,
                )
                result["atr_sl"] = atr_sl
                result["atr_sl_mult"] = sl_mult
                result["atr_sl_on_wicks"] = sl_on_wicks

            if use_atr_tp:
                tp_period = max(1, min(150, int(params.get("atr_tp_period", 150))))
                tp_smoothing = params.get("atr_tp_smoothing", "WMA")
                if tp_smoothing not in ("WMA", "RMA", "SMA", "EMA"):
                    tp_smoothing = "RMA"
                tp_mult = max(0.1, min(4.0, float(params.get("atr_tp_multiplier", 4.0))))
                tp_on_wicks = params.get("atr_tp_on_wicks", False)
                atr_tp = pd.Series(
                    calculate_atr_smoothed(high_arr, low_arr, close_arr, period=tp_period, method=tp_smoothing),
                    index=ohlcv.index,
                )
                result["atr_tp"] = atr_tp
                result["atr_tp_mult"] = tp_mult
                result["atr_tp_on_wicks"] = tp_on_wicks

        elif exit_type == "session_exit":
            # Exit at session end (specific hour)
            exit_hour = params.get("exit_hour", 21)
            idx = ohlcv.index
            hours = idx.hour if hasattr(idx, "hour") else pd.to_datetime(idx).hour
            at_session_end = hours == exit_hour
            result["exit"] = pd.Series(at_session_end, index=ohlcv.index)

        elif exit_type == "signal_exit":
            # Exit on opposite signal (reverse of entry)
            # This is handled by engine logic, return empty
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["signal_exit_mode"] = True

        elif exit_type == "indicator_exit":
            # Exit on indicator condition - generic
            indicator = params.get("indicator", "rsi")
            threshold = params.get("threshold", 50)
            mode = params.get("mode", "above")  # above, below, cross_above, cross_below

            if indicator == "rsi":
                ind_val = pd.Series(calculate_rsi(ohlcv["close"].values, 14), index=ohlcv.index)
            else:
                ind_val = pd.Series(calculate_rsi(ohlcv["close"].values, 14), index=ohlcv.index)

            if mode == "above":
                exit_signal = ind_val > threshold
            elif mode == "below":
                exit_signal = ind_val < threshold
            elif mode == "cross_above":
                exit_signal = (ind_val > threshold) & (ind_val.shift(1) <= threshold)
            else:  # cross_below
                exit_signal = (ind_val < threshold) & (ind_val.shift(1) >= threshold)

            result["exit"] = exit_signal.fillna(False)

        elif exit_type == "partial_close":
            # Partial close at targets
            targets = params.get("targets", [{"profit": 1.0, "close_pct": 50}])
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["partial_targets"] = targets

        elif exit_type == "multi_tp_exit":
            # Multi TP levels with % allocation
            tp1 = params.get("tp1_percent", 1.0)
            tp1_alloc = params.get("tp1_allocation", 30)
            tp2 = params.get("tp2_percent", 2.0)
            tp2_alloc = params.get("tp2_allocation", 30)
            tp3 = params.get("tp3_percent", 3.0)
            tp3_alloc = params.get("tp3_allocation", 40)

            # Validate allocations sum to ~100%
            total_alloc = tp1_alloc + tp2_alloc + tp3_alloc
            if not (99.0 <= total_alloc <= 101.0):
                logger.warning("Multi-TP allocations sum to {}%, expected 100%", total_alloc)

            # Warn if TP levels are not in ascending order
            if tp1 >= tp2 or tp2 >= tp3:
                logger.warning(
                    "Multi-TP levels not ascending: TP1={}% TP2={}% TP3={}% — execution order may be incorrect",
                    tp1,
                    tp2,
                    tp3,
                )

            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["multi_tp_config"] = [
                {"percent": tp1, "allocation": tp1_alloc},
                {"percent": tp2, "allocation": tp2_alloc},
                {"percent": tp3, "allocation": tp3_alloc},
            ]

        else:
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)

        return result

    def _execute_position_sizing(self, sizing_type: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute position sizing blocks.

        Sizing blocks are config-only and return sizing parameters.

        Supported sizing types:
            - fixed_size: Fixed position size
            - percent_equity: % of equity
            - risk_based: Risk % per trade
            - kelly_criterion: Kelly formula
            - volatility_sized: ATR-based sizing
        """
        result: dict[str, Any] = {}

        if sizing_type == "fixed_size":
            result["size"] = params.get("size", 1.0)
            result["sizing_mode"] = "fixed"

        elif sizing_type == "percent_equity":
            result["equity_percent"] = params.get("percent", 10.0)
            result["sizing_mode"] = "percent"

        elif sizing_type == "risk_based":
            result["risk_percent"] = params.get("risk_percent", 1.0)
            result["sizing_mode"] = "risk"

        elif sizing_type == "kelly_criterion":
            result["kelly_fraction"] = params.get("fraction", 0.5)
            result["sizing_mode"] = "kelly"

        elif sizing_type == "volatility_sized":
            result["atr_period"] = params.get("period", 14)
            result["target_risk"] = params.get("target_risk", 1.0)
            result["sizing_mode"] = "volatility"

        return result

    def _execute_time_filter(self, time_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """
        Execute time-based filter blocks.

        Time filters return boolean series based on time conditions.

        Supported time filter types:
            - trading_hours: Filter by time of day
            - trading_days: Filter by day of week
            - session_filter: Trading sessions (Asia, London, NY)
            - date_range: Filter by date range
            - exclude_news: Avoid news times
        """
        n = len(ohlcv)
        idx = ohlcv.index
        result: dict[str, pd.Series] = {}

        if time_type == "trading_hours":
            start_hour = params.get("start_hour", 9)
            end_hour = params.get("end_hour", 17)
            hours = idx.hour if hasattr(idx, "hour") else pd.to_datetime(idx).hour

            result["allow"] = pd.Series((hours >= start_hour) & (hours < end_hour), index=idx)

        elif time_type == "trading_days":
            allowed_days = params.get("days", [0, 1, 2, 3, 4])  # Mon-Fri
            dow = idx.dayofweek if hasattr(idx, "dayofweek") else pd.to_datetime(idx).dayofweek

            result["allow"] = pd.Series([d in allowed_days for d in dow], index=idx)

        elif time_type == "session_filter":
            session = params.get("session", "all")
            hours = idx.hour if hasattr(idx, "hour") else pd.to_datetime(idx).hour

            if session == "asia":
                # Asia session: 00:00 - 09:00 UTC
                result["allow"] = pd.Series((hours >= 0) & (hours < 9), index=idx)
            elif session == "london":
                # London session: 08:00 - 17:00 UTC
                result["allow"] = pd.Series((hours >= 8) & (hours < 17), index=idx)
            elif session == "ny":
                # NY session: 13:00 - 22:00 UTC
                result["allow"] = pd.Series((hours >= 13) & (hours < 22), index=idx)
            else:
                result["allow"] = pd.Series([True] * n, index=idx)

        elif time_type == "date_range":
            start_date = params.get("start_date")
            end_date = params.get("end_date")

            dates = pd.to_datetime(idx)
            allow = pd.Series([True] * n, index=idx)

            if start_date:
                allow = allow & (dates >= pd.to_datetime(start_date))
            if end_date:
                allow = allow & (dates <= pd.to_datetime(end_date))

            result["allow"] = allow

        else:
            result["allow"] = pd.Series([True] * n, index=idx)

        return result

    def _execute_price_action(
        self, pattern_type: str, params: dict[str, Any], ohlcv: pd.DataFrame
    ) -> dict[str, pd.Series]:
        """
        Execute price action pattern detection blocks.

        Returns signals when specific candlestick patterns are detected.

        Supported pattern types:
            - engulfing: Bullish/bearish engulfing
            - hammer: Hammer/hanging man
            - doji: Doji patterns
            - pin_bar: Pin bar / rejection
            - inside_bar: Inside bar
            - outside_bar: Outside bar
            - three_white_soldiers: 3 white soldiers / black crows
            - morning_star: Morning/evening star
        """
        n = len(ohlcv)
        idx = ohlcv.index
        result: dict[str, pd.Series] = {}

        o = ohlcv["open"]
        h = ohlcv["high"]
        low = ohlcv["low"]
        c = ohlcv["close"]
        body = abs(c - o)
        upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
        lower_wick = pd.concat([o, c], axis=1).min(axis=1) - low

        if pattern_type == "engulfing":
            # Bullish engulfing: prev red, current green, current body > prev body
            prev_red = o.shift(1) > c.shift(1)
            curr_green = c > o
            engulfs = (c > o.shift(1)) & (o < c.shift(1))
            bullish = prev_red & curr_green & engulfs

            prev_green = c.shift(1) > o.shift(1)
            curr_red = o > c
            engulfs_bear = (o > c.shift(1)) & (c < o.shift(1))
            bearish = prev_green & curr_red & engulfs_bear

            result["bullish"] = bullish.fillna(False)
            result["bearish"] = bearish.fillna(False)
            result["signal"] = bullish.fillna(False)

        elif pattern_type == "hammer":
            min_wick_ratio = params.get("min_wick_ratio", 2.0)
            max_upper_ratio = params.get("max_upper_ratio", 0.3)

            hammer = (lower_wick > body * min_wick_ratio) & (upper_wick < body * max_upper_ratio)
            hanging = (upper_wick > body * min_wick_ratio) & (lower_wick < body * max_upper_ratio)

            result["hammer"] = hammer.fillna(False)
            result["hanging_man"] = hanging.fillna(False)
            result["signal"] = hammer.fillna(False)

        elif pattern_type == "doji":
            threshold = params.get("body_threshold", 0.1)
            avg_range = (h - low).rolling(20).mean()

            doji = body < avg_range * threshold
            result["doji"] = doji.fillna(False)
            result["signal"] = doji.fillna(False)

        elif pattern_type == "pin_bar":
            min_wick = params.get("min_wick_ratio", 2.0)

            # Bullish pin: long lower wick
            bull_pin = (lower_wick > body * min_wick) & (lower_wick > upper_wick * 2)
            # Bearish pin: long upper wick
            bear_pin = (upper_wick > body * min_wick) & (upper_wick > lower_wick * 2)

            result["bullish"] = bull_pin.fillna(False)
            result["bearish"] = bear_pin.fillna(False)
            result["signal"] = bull_pin.fillna(False)

        elif pattern_type == "inside_bar":
            # Current bar inside previous bar
            inside = (h <= h.shift(1)) & (low >= low.shift(1))
            result["inside"] = inside.fillna(False)
            result["signal"] = inside.fillna(False)

        elif pattern_type == "outside_bar":
            # Current bar engulfs previous bar
            outside = (h > h.shift(1)) & (low < low.shift(1))
            result["outside"] = outside.fillna(False)
            result["signal"] = outside.fillna(False)

        elif pattern_type == "three_white_soldiers":
            # 3 consecutive bullish bars with higher closes
            green = c > o
            three_green = green & green.shift(1) & green.shift(2)
            higher_close = (c > c.shift(1)) & (c.shift(1) > c.shift(2))

            soldiers = three_green & higher_close

            # 3 black crows
            red = o > c
            three_red = red & red.shift(1) & red.shift(2)
            lower_close = (c < c.shift(1)) & (c.shift(1) < c.shift(2))
            crows = three_red & lower_close

            result["soldiers"] = soldiers.fillna(False)
            result["crows"] = crows.fillna(False)
            result["signal"] = soldiers.fillna(False)

        elif pattern_type == "hammer_hangman":
            # Hammer (bullish) and Hanging Man (bearish) patterns
            min_wick_ratio = params.get("min_wick_ratio", 2.0)
            max_upper_ratio = params.get("max_upper_ratio", 0.3)

            hammer = (lower_wick > body * min_wick_ratio) & (upper_wick < body * max_upper_ratio)
            hanging = (upper_wick > body * min_wick_ratio) & (lower_wick < body * max_upper_ratio)

            result["bullish"] = hammer.fillna(False)
            result["bearish"] = hanging.fillna(False)
            result["signal"] = hammer.fillna(False)

        elif pattern_type == "doji_patterns":
            # Multiple doji types: standard, dragonfly, gravestone
            threshold = params.get("body_threshold", 0.1)
            avg_range = (h - low).rolling(20).mean()

            small_body = body < avg_range * threshold
            # Dragonfly doji: small body at top, long lower wick
            dragonfly = small_body & (lower_wick > body * 3) & (upper_wick < body)
            # Gravestone doji: small body at bottom, long upper wick
            gravestone = small_body & (upper_wick > body * 3) & (lower_wick < body)
            # Standard doji
            standard_doji = small_body & ~dragonfly & ~gravestone

            result["doji"] = small_body.fillna(False)
            result["standard_doji"] = standard_doji.fillna(False)
            result["dragonfly"] = dragonfly.fillna(False)
            result["gravestone"] = gravestone.fillna(False)
            result["bullish"] = dragonfly.fillna(False)  # Dragonfly is bullish
            result["bearish"] = gravestone.fillna(False)  # Gravestone is bearish
            result["signal"] = small_body.fillna(False)

        elif pattern_type == "shooting_star":
            # Shooting star: small body at bottom, long upper wick (bearish)
            min_wick_ratio = params.get("min_wick_ratio", 2.0)
            max_lower_ratio = params.get("max_lower_ratio", 0.3)

            shooting = (upper_wick > body * min_wick_ratio) & (lower_wick < body * max_lower_ratio)
            # Only valid if after uptrend
            uptrend = c.shift(1) > c.shift(3)
            valid_shooting = shooting & uptrend

            result["bearish"] = valid_shooting.fillna(False)
            result["bullish"] = pd.Series([False] * n, index=idx)
            result["signal"] = valid_shooting.fillna(False)

        elif pattern_type == "marubozu":
            # Marubozu: strong momentum candle with no/tiny wicks
            max_wick_ratio = params.get("max_wick_ratio", 0.1)

            tiny_wicks = (upper_wick < body * max_wick_ratio) & (lower_wick < body * max_wick_ratio)
            bullish_marubozu = tiny_wicks & (c > o)
            bearish_marubozu = tiny_wicks & (o > c)

            result["bullish"] = bullish_marubozu.fillna(False)
            result["bearish"] = bearish_marubozu.fillna(False)
            result["signal"] = bullish_marubozu.fillna(False)

        elif pattern_type == "tweezer":
            # Tweezer top/bottom: two candles with same high/low
            tolerance = params.get("tolerance", 0.001)

            # Tweezer bottom: same lows, first red then green
            same_low = abs(low - low.shift(1)) < (low * tolerance)
            first_red = o.shift(1) > c.shift(1)
            second_green = c > o
            tweezer_bottom = same_low & first_red & second_green

            # Tweezer top: same highs, first green then red
            same_high = abs(h - h.shift(1)) < (h * tolerance)
            first_green = c.shift(1) > o.shift(1)
            second_red = o > c
            tweezer_top = same_high & first_green & second_red

            result["bullish"] = tweezer_bottom.fillna(False)
            result["bearish"] = tweezer_top.fillna(False)
            result["signal"] = tweezer_bottom.fillna(False)

        elif pattern_type == "three_methods":
            # Rising/Falling three methods (continuation patterns)
            green = c > o
            red = o > c

            # Rising three methods: big green, 3 small reds inside, big green
            big_green_1 = green.shift(4) & (body.shift(4) > body.shift(4).rolling(10).mean())
            small_reds = red.shift(3) & red.shift(2) & red.shift(1)
            contained = (low.shift(1) > low.shift(4)) & (h.shift(1) < h.shift(4))
            big_green_2 = green & (c > h.shift(4))
            rising_three = big_green_1 & small_reds & contained & big_green_2

            # Falling three methods: opposite
            big_red_1 = red.shift(4) & (body.shift(4) > body.shift(4).rolling(10).mean())
            small_greens = green.shift(3) & green.shift(2) & green.shift(1)
            contained_fall = (h.shift(1) < h.shift(4)) & (low.shift(1) > low.shift(4))
            big_red_2 = red & (c < low.shift(4))
            falling_three = big_red_1 & small_greens & contained_fall & big_red_2

            result["bullish"] = rising_three.fillna(False)
            result["bearish"] = falling_three.fillna(False)
            result["signal"] = rising_three.fillna(False)

        elif pattern_type == "piercing_darkcloud":
            # Piercing line (bullish) and Dark cloud cover (bearish)

            # Piercing line: red candle, then green opens below prev low, closes above midpoint
            prev_red = o.shift(1) > c.shift(1)
            curr_green = c > o
            opens_below = o < low.shift(1)
            closes_above_mid = c > (o.shift(1) + c.shift(1)) / 2
            piercing = prev_red & curr_green & opens_below & closes_above_mid

            # Dark cloud: green candle, then red opens above prev high, closes below midpoint
            prev_green = c.shift(1) > o.shift(1)
            curr_red = o > c
            opens_above = o > h.shift(1)
            closes_below_mid = c < (o.shift(1) + c.shift(1)) / 2
            dark_cloud = prev_green & curr_red & opens_above & closes_below_mid

            result["bullish"] = piercing.fillna(False)
            result["bearish"] = dark_cloud.fillna(False)
            result["signal"] = piercing.fillna(False)

        elif pattern_type == "harami":
            # Harami (inside bar reversal)

            # Bullish harami: big red, then small green inside
            big_red = (o.shift(1) > c.shift(1)) & (body.shift(1) > body.shift(1).rolling(10).mean())
            small_green = (c > o) & (body < body.shift(1) * 0.5)
            inside_prev = (o > c.shift(1)) & (c < o.shift(1))
            bullish_harami = big_red & small_green & inside_prev

            # Bearish harami: big green, then small red inside
            big_green = (c.shift(1) > o.shift(1)) & (body.shift(1) > body.shift(1).rolling(10).mean())
            small_red = (o > c) & (body < body.shift(1) * 0.5)
            inside_prev_bear = (o < c.shift(1)) & (c > o.shift(1))
            bearish_harami = big_green & small_red & inside_prev_bear

            result["bullish"] = bullish_harami.fillna(False)
            result["bearish"] = bearish_harami.fillna(False)
            result["signal"] = bullish_harami.fillna(False)

        else:
            result["signal"] = pd.Series([False] * n, index=idx)

        return result

    def _execute_divergence(self, div_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """
        Execute unified divergence detection block.

        Detects divergences between price and one or more indicators.
        Supports RSI, Stochastic, Momentum (ROC), CMF, OBV, MFI.

        Divergence logic:
            - Bullish divergence: price makes lower low, indicator makes higher low
            - Bearish divergence: price makes higher high, indicator makes lower high

        Pivot detection uses pivot_interval to find swing highs/lows.

        Note: The first and last `pivot_interval` bars of the data are excluded from
        pivot detection (boundary effect). For default pivot_interval=9, this means
        the first 9 and last 9 bars will never generate divergence signals. This is
        inherent to the pivot algorithm (needs N bars on each side to confirm a swing).

        Parameters:
            pivot_interval (int): Number of bars to left/right for pivot detection (1-9, default 9)
            act_without_confirmation (bool): If True, fire signal immediately; if False, wait for
                price confirmation (next bar closes in divergence direction)
            activate_diver_signal_memory (bool): If True, divergence signals persist for N bars
            keep_diver_signal_memory_bars (int): How many bars to keep signal in memory (1-100)
            use_divergence_rsi (bool): Enable RSI divergence
            rsi_period (int): RSI period
            use_divergence_stochastic (bool): Enable Stochastic divergence
            stoch_length (int): Stochastic %K period
            use_divergence_momentum (bool): Enable Momentum (ROC) divergence
            momentum_length (int): Momentum/ROC period
            use_divergence_cmf (bool): Enable CMF divergence
            cmf_period (int): CMF period
            use_obv (bool): Enable OBV divergence
            use_mfi (bool): Enable MFI divergence
            mfi_length (int): MFI period
        """
        n = len(ohlcv)
        idx = ohlcv.index

        close = ohlcv["close"].values.astype(float)
        high = ohlcv["high"].values.astype(float)
        low = ohlcv["low"].values.astype(float)
        volume = ohlcv["volume"].values.astype(float)

        pivot_interval = int(_param(params, 9, "pivot_interval"))
        act_without_confirmation = bool(_param(params, False, "act_without_confirmation"))
        activate_memory = bool(_param(params, False, "activate_diver_signal_memory"))
        memory_bars = int(_param(params, 5, "keep_diver_signal_memory_bars"))

        # Collect all enabled indicator series
        indicator_series: list[np.ndarray] = []

        if _param(params, False, "use_divergence_rsi"):
            rsi_period = int(_param(params, 14, "rsi_period"))
            indicator_series.append(calculate_rsi(close, rsi_period))

        if _param(params, False, "use_divergence_stochastic"):
            stoch_length = int(_param(params, 14, "stoch_length"))
            stoch_k, _ = calculate_stochastic(high, low, close, k_period=stoch_length)
            indicator_series.append(stoch_k)

        if _param(params, False, "use_divergence_momentum"):
            momentum_length = int(_param(params, 10, "momentum_length"))
            indicator_series.append(calculate_roc(close, momentum_length))

        if _param(params, False, "use_divergence_cmf"):
            cmf_period = int(_param(params, 21, "cmf_period"))
            indicator_series.append(calculate_cmf(high, low, close, volume, cmf_period))

        if _param(params, False, "use_obv"):
            indicator_series.append(calculate_obv(close, volume))

        if _param(params, False, "use_mfi"):
            mfi_length = int(_param(params, 14, "mfi_length"))
            indicator_series.append(calculate_mfi(high, low, close, volume, mfi_length))

        # If no indicator enabled — return empty signals
        if not indicator_series:
            return {
                "signal": pd.Series([False] * n, index=idx),
                "bullish": pd.Series([False] * n, index=idx),
                "bearish": pd.Series([False] * n, index=idx),
            }

        # Detect pivot highs and lows using pivot_interval
        pivot_highs = np.full(n, np.nan)
        pivot_lows = np.full(n, np.nan)
        for i in range(pivot_interval, n - pivot_interval):
            # Pivot high: high[i] is the highest in the window
            window_high = high[i - pivot_interval : i + pivot_interval + 1]
            if high[i] >= np.max(window_high):
                pivot_highs[i] = high[i]
            # Pivot low: low[i] is the lowest in the window
            window_low = low[i - pivot_interval : i + pivot_interval + 1]
            if low[i] <= np.min(window_low):
                pivot_lows[i] = low[i]

        # For each indicator, detect divergence
        bullish_raw = np.zeros(n, dtype=bool)
        bearish_raw = np.zeros(n, dtype=bool)

        for ind_values in indicator_series:
            # Compute indicator pivot highs/lows at the same pivot bar locations
            ind_pivot_highs = np.full(n, np.nan)
            ind_pivot_lows = np.full(n, np.nan)
            for i in range(pivot_interval, n - pivot_interval):
                if not np.isnan(pivot_highs[i]) and not np.isnan(ind_values[i]):
                    ind_pivot_highs[i] = ind_values[i]
                if not np.isnan(pivot_lows[i]) and not np.isnan(ind_values[i]):
                    ind_pivot_lows[i] = ind_values[i]

            # Compare consecutive pivots to detect divergence
            # Track the most recent valid pivot for comparison
            last_pivot_high_idx = -1
            last_pivot_low_idx = -1

            for i in range(pivot_interval, n):
                # Check bearish divergence at pivot highs
                if not np.isnan(pivot_highs[i]) and not np.isnan(ind_pivot_highs[i]):
                    if (
                        last_pivot_high_idx >= 0
                        and pivot_highs[i] > pivot_highs[last_pivot_high_idx]
                        and ind_pivot_highs[i] < ind_pivot_highs[last_pivot_high_idx]
                    ):
                        # Price makes higher high, indicator makes lower high в†' bearish
                        signal_bar = min(i + pivot_interval, n - 1)
                        bearish_raw[signal_bar] = True
                    last_pivot_high_idx = i

                # Check bullish divergence at pivot lows
                if not np.isnan(pivot_lows[i]) and not np.isnan(ind_pivot_lows[i]):
                    if (
                        last_pivot_low_idx >= 0
                        and pivot_lows[i] < pivot_lows[last_pivot_low_idx]
                        and ind_pivot_lows[i] > ind_pivot_lows[last_pivot_low_idx]
                    ):
                        # Price makes lower low, indicator makes higher low в†' bullish
                        signal_bar = min(i + pivot_interval, n - 1)
                        bullish_raw[signal_bar] = True
                    last_pivot_low_idx = i

        # Apply confirmation filter if act_without_confirmation is False
        if not act_without_confirmation:
            bullish_confirmed = np.zeros(n, dtype=bool)
            bearish_confirmed = np.zeros(n, dtype=bool)
            for i in range(1, n):
                # Bullish confirmation: current close > previous close
                if bullish_raw[i] and close[i] > close[i - 1]:
                    bullish_confirmed[i] = True
                # Bearish confirmation: current close < previous close
                if bearish_raw[i] and close[i] < close[i - 1]:
                    bearish_confirmed[i] = True
            bullish = bullish_confirmed
            bearish = bearish_confirmed
        else:
            bullish = bullish_raw
            bearish = bearish_raw

        # Apply signal memory: if enabled, signals persist for N bars (vectorized)
        if activate_memory and memory_bars > 1:
            bullish_s = pd.Series(bullish, index=idx)
            bearish_s = pd.Series(bearish, index=idx)
            # Rolling max over window=memory_bars propagates True forward
            bullish = bullish_s.rolling(window=memory_bars, min_periods=1).max().fillna(0).astype(bool).values
            bearish = bearish_s.rolling(window=memory_bars, min_periods=1).max().fillna(0).astype(bool).values

        signal = bullish | bearish

        # Return with port IDs matching frontend: "long" (bullish) and "short" (bearish)
        return {
            "signal": pd.Series(signal, index=idx),
            "long": pd.Series(bullish, index=idx),
            "short": pd.Series(bearish, index=idx),
            # Keep aliases for backward compatibility with tests/API consumers
            "bullish": pd.Series(bullish, index=idx),
            "bearish": pd.Series(bearish, index=idx),
        }

    def _execute_close_condition(
        self, close_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """
        Execute close condition blocks from frontend close_conditions category.

        These blocks define when to close positions based on indicators or time.

        Supported close types:
            - close_by_time: Close after N bars
            - close_channel: Close on Keltner/Bollinger band touch
            - close_ma_cross: Close on MA1/MA2 cross
            - close_rsi: Close on RSI reach/cross level
            - close_stochastic: Close on Stochastic reach/cross level
            - close_psar: Close on Parabolic SAR signal reversal
        """
        n = len(ohlcv)
        idx = ohlcv.index
        close = ohlcv["close"]
        result: dict[str, pd.Series] = {}

        if close_type == "close_by_time":
            # Close after N bars since entry - needs position tracking
            # Bug fix: frontend stores key as "bars_since_entry", not "bars"
            bars = int(params.get("bars_since_entry", params.get("bars", 10)))
            # Return config, actual implementation in engine
            result["exit"] = pd.Series([False] * n, index=idx)
            result["max_bars"] = pd.Series([bars] * n, index=idx)

        elif close_type == "close_channel":
            # Close on Keltner Channel or Bollinger Bands band touch
            channel_type = params.get("channel_type", "Keltner Channel")
            band_to_close = params.get("band_to_close", "Rebound")
            close_condition = params.get("close_condition", "Wick out of band")
            keltner_length = int(params.get("keltner_length", 14))
            keltner_mult = float(params.get("keltner_mult", 1.5))
            bb_length = int(params.get("bb_length", 20))
            bb_deviation = float(params.get("bb_deviation", 2.0))

            high = ohlcv["high"]
            low = ohlcv["low"]

            if channel_type == "Keltner Channel":
                _kc_mid, kc_upper, kc_lower = calculate_keltner(
                    high.values,
                    low.values,
                    close.values,
                    keltner_length,
                    keltner_length,
                    keltner_mult,
                )
                upper = pd.Series(kc_upper, index=idx)
                lower = pd.Series(kc_lower, index=idx)
            else:
                # Bollinger Bands
                middle = close.rolling(bb_length).mean()
                std = close.rolling(bb_length).std()
                upper = middle + bb_deviation * std
                lower = middle - bb_deviation * std

            # Build exit signals based on band_to_close mode and close_condition
            if close_condition == "Out-of-band closure":
                # Bar closes outside the band
                if band_to_close == "Rebound":
                    exit_long = close >= upper
                    exit_short = close <= lower
                else:  # Breakout
                    exit_long = close <= lower
                    exit_short = close >= upper
            elif close_condition == "Wick out of band":
                # Wick (high/low) touches band
                if band_to_close == "Rebound":
                    exit_long = high >= upper
                    exit_short = low <= lower
                else:
                    exit_long = low <= lower
                    exit_short = high >= upper
            elif close_condition == "Wick out of the band then close in":
                # Previous wick outside, current close inside
                if band_to_close == "Rebound":
                    exit_long = (high.shift(1) >= upper.shift(1)) & (close < upper)
                    exit_short = (low.shift(1) <= lower.shift(1)) & (close > lower)
                else:
                    exit_long = (low.shift(1) <= lower.shift(1)) & (close > lower)
                    exit_short = (high.shift(1) >= upper.shift(1)) & (close < upper)
            else:
                # "Close out of the band then close in"
                if band_to_close == "Rebound":
                    exit_long = (close.shift(1) >= upper.shift(1)) & (close < upper)
                    exit_short = (close.shift(1) <= lower.shift(1)) & (close > lower)
                else:
                    exit_long = (close.shift(1) <= lower.shift(1)) & (close > lower)
                    exit_short = (close.shift(1) >= upper.shift(1)) & (close < upper)

            result["exit_long"] = exit_long.fillna(False)
            result["exit_short"] = exit_short.fillna(False)
            result["exit"] = (exit_long | exit_short).fillna(False)
            result["signal"] = result["exit"]

        elif close_type == "close_ma_cross":
            # Close on MA1/MA2 cross
            ma1_length = int(params.get("ma1_length", 10))
            ma2_length = int(params.get("ma2_length", 30))
            profit_only = params.get("profit_only", False)
            min_profit = float(params.get("min_profit_percent", 1.0))

            fast_ma = close.ewm(span=ma1_length, adjust=False).mean()
            slow_ma = close.ewm(span=ma2_length, adjust=False).mean()

            # Long exit: fast MA crosses below slow MA (bearish cross)
            exit_long = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
            # Short exit: fast MA crosses above slow MA (bullish cross)
            exit_short = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))

            result["exit_long"] = exit_long.fillna(False)
            result["exit_short"] = exit_short.fillna(False)
            result["exit"] = (exit_long | exit_short).fillna(False)
            result["signal"] = result["exit"]
            # Pass profit_only config for engine-level filtering
            if profit_only:
                result["profit_only"] = pd.Series([True] * n, index=idx)
                result["min_profit"] = pd.Series([min_profit] * n, index=idx)

        elif close_type == "close_rsi":
            # Close by RSI: reach or cross level modes
            rsi_length = int(params.get("rsi_close_length", 14))
            rsi_profit_only = params.get("rsi_close_profit_only", False)
            rsi_min_profit = float(params.get("rsi_close_min_profit", 1.0))
            activate_reach = params.get("activate_rsi_reach", False)
            activate_cross = params.get("activate_rsi_cross", False)

            rsi_values = pd.Series(calculate_rsi(close.values, rsi_length), index=idx)

            exit_long = pd.Series([False] * n, index=idx)
            exit_short = pd.Series([False] * n, index=idx)

            if activate_reach:
                # Reach mode: RSI in zone в†' exit
                long_more = float(params.get("rsi_long_more", 70))
                long_less = float(params.get("rsi_long_less", 100))
                if long_more > long_less:
                    logger.warning(
                        "Close RSI range inversion: long_more={} > long_less={} — swapping to prevent always-False exit",
                        long_more,
                        long_less,
                    )
                    long_more, long_less = long_less, long_more
                short_less = float(params.get("rsi_short_less", 30))
                short_more = float(params.get("rsi_short_more", 1))
                if short_more > short_less:
                    logger.warning(
                        "Close RSI range inversion: short_more={} > short_less={} — swapping to prevent always-False exit",
                        short_more,
                        short_less,
                    )
                    short_more, short_less = short_less, short_more
                exit_long = exit_long | ((rsi_values >= long_more) & (rsi_values <= long_less))
                exit_short = exit_short | ((rsi_values <= short_less) & (rsi_values >= short_more))

            if activate_cross:
                # Cross mode: RSI crosses level
                # Long exit: RSI crosses down through level (from above to below)
                cross_long_level = float(params.get("rsi_cross_long_level", 70))
                cross_short_level = float(params.get("rsi_cross_short_level", 30))
                exit_long = exit_long | ((rsi_values < cross_long_level) & (rsi_values.shift(1) >= cross_long_level))
                # Short exit: RSI crosses up through level (from below to above)
                exit_short = exit_short | (
                    (rsi_values > cross_short_level) & (rsi_values.shift(1) <= cross_short_level)
                )

            result["exit_long"] = exit_long.fillna(False)
            result["exit_short"] = exit_short.fillna(False)
            result["exit"] = (exit_long | exit_short).fillna(False)
            result["signal"] = result["exit"]
            if rsi_profit_only:
                result["profit_only"] = pd.Series([True] * n, index=idx)
                result["min_profit"] = pd.Series([rsi_min_profit] * n, index=idx)

        elif close_type == "close_stochastic":
            # Close by Stochastic: reach or cross level modes
            k_length = int(params.get("stoch_close_k_length", 14))
            k_smooth = int(params.get("stoch_close_k_smoothing", 3))
            d_smooth = int(params.get("stoch_close_d_smoothing", 3))
            stoch_profit_only = params.get("stoch_close_profit_only", False)
            stoch_min_profit = float(params.get("stoch_close_min_profit", 1.0))
            activate_reach = params.get("activate_stoch_reach", False)
            activate_cross = params.get("activate_stoch_cross", False)

            high = ohlcv["high"]
            low = ohlcv["low"]
            stoch_k, _stoch_d = calculate_stochastic(
                high.values, low.values, close.values, k_length, k_smooth, d_smooth
            )
            stoch_values = pd.Series(stoch_k, index=idx)

            exit_long = pd.Series([False] * n, index=idx)
            exit_short = pd.Series([False] * n, index=idx)

            if activate_reach:
                # Reach mode: Stoch %K in zone в†' exit
                long_more = float(params.get("stoch_long_more", 80))
                long_less = float(params.get("stoch_long_less", 100))
                if long_more > long_less:
                    logger.warning(
                        "Close Stochastic range inversion: long_more={} > long_less={} — swapping to prevent always-False exit",
                        long_more,
                        long_less,
                    )
                    long_more, long_less = long_less, long_more
                short_less = float(params.get("stoch_short_less", 20))
                short_more = float(params.get("stoch_short_more", 1))
                if short_more > short_less:
                    logger.warning(
                        "Close Stochastic range inversion: short_more={} > short_less={} — swapping to prevent always-False exit",
                        short_more,
                        short_less,
                    )
                    short_more, short_less = short_less, short_more
                exit_long = exit_long | ((stoch_values >= long_more) & (stoch_values <= long_less))
                exit_short = exit_short | ((stoch_values <= short_less) & (stoch_values >= short_more))

            if activate_cross:
                # Cross mode: Stoch %K crosses level
                cross_long = float(params.get("stoch_cross_long_level", 80))
                cross_short = float(params.get("stoch_cross_short_level", 20))
                exit_long = exit_long | ((stoch_values < cross_long) & (stoch_values.shift(1) >= cross_long))
                exit_short = exit_short | ((stoch_values > cross_short) & (stoch_values.shift(1) <= cross_short))

            result["exit_long"] = exit_long.fillna(False)
            result["exit_short"] = exit_short.fillna(False)
            result["exit"] = (exit_long | exit_short).fillna(False)
            result["signal"] = result["exit"]
            if stoch_profit_only:
                result["profit_only"] = pd.Series([True] * n, index=idx)
                result["min_profit"] = pd.Series([stoch_min_profit] * n, index=idx)

        elif close_type == "close_psar":
            # Close by Parabolic SAR signal
            psar_start = float(params.get("psar_start", 0.02))
            psar_increment = float(params.get("psar_increment", 0.02))
            psar_maximum = float(params.get("psar_maximum", 0.2))
            psar_opposite = params.get("psar_opposite", False)
            psar_profit_only = params.get("psar_close_profit_only", False)
            psar_min_profit = float(params.get("psar_close_min_profit", 1.0))
            nth_bar = int(params.get("psar_close_nth_bar", 1))

            high = ohlcv["high"]
            low = ohlcv["low"]
            psar_arr, psar_trend = calculate_parabolic_sar(
                high.values, low.values, psar_start, psar_increment, psar_maximum
            )
            _psar_values = pd.Series(psar_arr, index=idx)  # kept for future overlay

            # Detect trend change using trend direction from PSAR
            trend_series = pd.Series(psar_trend, index=idx)
            trend_change_bull = (trend_series == 1) & (trend_series.shift(1) == -1)  # bearishв†'bullish
            trend_change_bear = (trend_series == -1) & (trend_series.shift(1) == 1)  # bullishв†'bearish

            if nth_bar <= 1:
                # Close on the bar of trend change
                if psar_opposite:
                    exit_long = trend_change_bull  # Close long on bullish signal (opposite)
                    exit_short = trend_change_bear
                else:
                    exit_long = trend_change_bear  # Close long on bearish signal (normal)
                    exit_short = trend_change_bull
            else:
                # Close on Nth bar of new trend
                if psar_opposite:
                    bull_counter = trend_change_bull.cumsum()
                    bars_since_bull = bull_counter.groupby(bull_counter).cumcount() + 1
                    bear_counter = trend_change_bear.cumsum()
                    bars_since_bear = bear_counter.groupby(bear_counter).cumcount() + 1
                    exit_long = bars_since_bull == nth_bar
                    exit_short = bars_since_bear == nth_bar
                else:
                    bear_counter = trend_change_bear.cumsum()
                    bars_since_bear = bear_counter.groupby(bear_counter).cumcount() + 1
                    bull_counter = trend_change_bull.cumsum()
                    bars_since_bull = bull_counter.groupby(bull_counter).cumcount() + 1
                    exit_long = bars_since_bear == nth_bar
                    exit_short = bars_since_bull == nth_bar

            result["exit_long"] = exit_long.fillna(False)
            result["exit_short"] = exit_short.fillna(False)
            result["exit"] = (exit_long | exit_short).fillna(False)
            result["signal"] = result["exit"]
            if psar_profit_only:
                result["profit_only"] = pd.Series([True] * n, index=idx)
                result["min_profit"] = pd.Series([psar_min_profit] * n, index=idx)

        else:
            result["exit"] = pd.Series([False] * n, index=idx)
            result["signal"] = pd.Series([False] * n, index=idx)

        return result

    def _execute_dca_block(self, block_type: str, params: dict[str, Any]) -> dict[str, pd.Series]:
        """
        Process DCA/Grid configuration blocks.

        DCA blocks are configuration-only and don't produce signal outputs.
        Their parameters are collected by extract_dca_config() for BacktestConfig.

        Supported block types:
            - dca_grid_enable: Master enable switch
            - dca_grid_settings: Grid order count and size
            - dca_martingale_config: Martingale coefficient settings
            - dca_log_steps: Logarithmic step distribution
            - dca_dynamic_tp: Multi-level take profit
            - dca_safety_close: Safety close on drawdown
        """
        # DCA blocks are config-only, no signal outputs
        # They're processed via extract_dca_config()
        return {}

    def extract_dca_config(self) -> dict[str, Any]:
        """
        Extract DCA Grid configuration from strategy blocks.

        Scans all blocks with category="dca_grid" or "multiple_tp" and
        assembles a configuration dictionary compatible with BacktestConfig.

        Returns:
            Dictionary with DCA configuration fields:
                - dca_enabled: bool
                - dca_direction: str
                - dca_order_count: int
                - dca_grid_size_percent: float
                - dca_martingale_coef: float
                - dca_martingale_mode: str
                - dca_log_step_enabled: bool
                - dca_log_step_coef: float
                - dca_drawdown_threshold: float
                - dca_safety_close_enabled: bool
                - dca_multi_tp_enabled: bool
                - dca_tp{1-4}_percent: float
                - dca_tp{1-4}_close_percent: float
        """
        dca_config: dict[str, Any] = {
            "dca_enabled": False,
            "dca_direction": "both",
            "dca_order_count": 5,
            "dca_grid_size_percent": 1.0,
            "dca_martingale_coef": 1.5,
            "dca_martingale_mode": "multiply_each",
            "dca_log_step_enabled": False,
            "dca_log_step_coef": 1.2,
            "dca_drawdown_threshold": 30.0,
            "dca_safety_close_enabled": True,
            "dca_multi_tp_enabled": False,
            "dca_tp1_percent": 0.5,
            "dca_tp1_close_percent": 25.0,
            "dca_tp2_percent": 1.0,
            "dca_tp2_close_percent": 25.0,
            "dca_tp3_percent": 2.0,
            "dca_tp3_close_percent": 25.0,
            "dca_tp4_percent": 3.0,
            "dca_tp4_close_percent": 25.0,
            # Manual Grid (custom orders)
            "custom_orders": None,
            "grid_trailing_percent": 0.0,
        }

        for _block_id, block in self.blocks.items():
            category = block.get("category", "")
            block_type = block.get("type", "")
            params = block.get("params") or block.get("config") or {}

            # Support for Manual Grid (grid_orders) block from entry_mgmt/entry_refinement category
            if category in ("entry_refinement", "entry_mgmt") and block_type == "grid_orders":
                custom_orders = params.get("orders", [])
                if custom_orders and len(custom_orders) > 0:
                    dca_config["dca_enabled"] = True
                    dca_config["custom_orders"] = custom_orders
                    dca_config["dca_order_count"] = len(custom_orders)
                    # Calculate grid step size as median of inter-order gaps (not total range)
                    sorted_offsets = sorted(o for o in (order.get("offset", 0) for order in custom_orders) if o > 0)
                    if len(sorted_offsets) >= 2:
                        steps = [sorted_offsets[i + 1] - sorted_offsets[i] for i in range(len(sorted_offsets) - 1)]
                        grid_step = float(sorted(steps)[len(steps) // 2])  # median step
                    elif sorted_offsets:
                        grid_step = float(sorted_offsets[0])
                    else:
                        grid_step = 1.0
                    dca_config["dca_grid_size_percent"] = grid_step
                # Grid trailing
                grid_trailing = params.get("grid_trailing", 0)
                if grid_trailing > 0:
                    dca_config["grid_trailing_percent"] = grid_trailing
                    dca_config["grid_trailing"] = grid_trailing

            # Support for unified 'dca' block from entry_mgmt/entry_refinement category (new format)
            elif category in ("entry_refinement", "entry_mgmt") and block_type == "dca":
                dca_config["dca_enabled"] = True
                dca_config["dca_grid_size_percent"] = params.get("grid_size_percent", 15.0)
                dca_config["dca_order_count"] = params.get("order_count", 5)
                dca_config["dca_martingale_coef"] = params.get("martingale_coefficient", 1.0)
                # Map log_steps_coefficient to dca_log_step_coef
                log_coef = params.get("log_steps_coefficient", 1.0)
                if log_coef != 1.0:
                    dca_config["dca_log_step_enabled"] = True
                    dca_config["dca_log_step_coef"] = log_coef
                # Map first_order_offset to indent_order config
                first_offset = params.get("first_order_offset", 0)
                if first_offset > 0:
                    dca_config["indent_order"] = {
                        "enabled": True,
                        "indent_percent": first_offset,
                        "cancel_after_bars": 10,
                    }
                # grid_trailing - store for future use (not yet implemented in backend)
                grid_trailing = params.get("grid_trailing", 0)
                if grid_trailing > 0:
                    dca_config["grid_trailing"] = grid_trailing

            elif category == "dca_grid":
                if block_type == "dca_grid_enable":
                    dca_config["dca_enabled"] = params.get("enabled", True)
                    dca_config["dca_direction"] = params.get("direction", "both")

                elif block_type == "dca_grid_settings":
                    dca_config["dca_order_count"] = params.get("order_count", 5)
                    dca_config["dca_grid_size_percent"] = params.get("grid_size_percent", 1.0)

                elif block_type == "dca_martingale_config":
                    dca_config["dca_martingale_coef"] = params.get("martingale_coef", 1.5)
                    dca_config["dca_martingale_mode"] = params.get("martingale_mode", "multiply_each")

                elif block_type == "dca_log_steps":
                    dca_config["dca_log_step_enabled"] = params.get("enabled", False)
                    dca_config["dca_log_step_coef"] = params.get("log_step_coef", 1.2)

                elif block_type == "dca_safety_close":
                    dca_config["dca_safety_close_enabled"] = params.get("enabled", True)
                    dca_config["dca_drawdown_threshold"] = params.get("drawdown_threshold", 30.0)

                elif block_type == "dca_dynamic_tp":
                    dca_config["dca_multi_tp_enabled"] = params.get("enabled", False)

            elif category == "multiple_tp":
                if block_type == "multi_tp_levels":
                    dca_config["dca_multi_tp_enabled"] = True
                    levels = params.get("levels", [])
                    for i, level in enumerate(levels[:4], start=1):
                        dca_config[f"dca_tp{i}_percent"] = level.get("percent", i * 0.5)
                        dca_config[f"dca_tp{i}_close_percent"] = level.get("close_percent", 25.0)

        # Close Conditions (Session 5.5): extract from exit blocks
        close_conditions: dict[str, Any] = {}
        for _block_id, block in self.blocks.items():
            block_type = block.get("type", "")
            params = block.get("params") or block.get("config") or {}
            if block_type in ("rsi_close", "stoch_close", "psar_close"):
                pass  # Legacy block types — removed
            elif block_type == "channel_close":
                pass  # Legacy block type — use close_channel instead
            elif block_type == "ma_close":
                pass  # Legacy block type — use close_ma_cross instead
            elif block_type == "close_channel":
                close_conditions["channel_close_enable"] = True
                close_conditions["channel_close_timeframe"] = params.get("channel_close_timeframe", "Chart")
                close_conditions["channel_close_band_to_close"] = params.get("band_to_close", "Rebound")
                close_conditions["channel_close_type"] = params.get("channel_type", "Keltner Channel")
                close_conditions["channel_close_condition"] = params.get("close_condition", "Wick out of band")
                close_conditions["channel_close_keltner_length"] = params.get("keltner_length", 14)
                close_conditions["channel_close_keltner_mult"] = params.get("keltner_mult", 1.5)
                close_conditions["channel_close_bb_length"] = params.get("bb_length", 20)
                close_conditions["channel_close_bb_deviation"] = params.get("bb_deviation", 2.0)
            elif block_type == "close_ma_cross":
                close_conditions["ma_cross_close_enable"] = True
                close_conditions["ma_cross_close_profit_only"] = params.get("profit_only", False)
                close_conditions["ma_cross_close_min_profit"] = params.get("min_profit_percent", 1.0)
                close_conditions["ma_cross_close_ma1_length"] = params.get("ma1_length", 10)
                close_conditions["ma_cross_close_ma2_length"] = params.get("ma2_length", 30)
            elif block_type == "close_rsi":
                close_conditions["rsi_close_enable"] = True
                close_conditions["rsi_close_length"] = params.get("rsi_close_length", 14)
                close_conditions["rsi_close_timeframe"] = params.get("rsi_close_timeframe", "Chart")
                close_conditions["rsi_close_profit_only"] = params.get("rsi_close_profit_only", False)
                close_conditions["rsi_close_min_profit"] = params.get("rsi_close_min_profit", 1.0)
                close_conditions["rsi_close_activate_reach"] = params.get("activate_rsi_reach", False)
                close_conditions["rsi_close_long_more"] = params.get("rsi_long_more", 70)
                close_conditions["rsi_close_long_less"] = params.get("rsi_long_less", 100)
                close_conditions["rsi_close_short_less"] = params.get("rsi_short_less", 30)
                close_conditions["rsi_close_short_more"] = params.get("rsi_short_more", 1)
                close_conditions["rsi_close_activate_cross"] = params.get("activate_rsi_cross", False)
                close_conditions["rsi_close_cross_long_level"] = params.get("rsi_cross_long_level", 70)
                close_conditions["rsi_close_cross_short_level"] = params.get("rsi_cross_short_level", 30)
            elif block_type == "close_stochastic":
                close_conditions["stoch_close_enable"] = True
                close_conditions["stoch_close_k_length"] = params.get("stoch_close_k_length", 14)
                close_conditions["stoch_close_k_smoothing"] = params.get("stoch_close_k_smoothing", 3)
                close_conditions["stoch_close_d_smoothing"] = params.get("stoch_close_d_smoothing", 3)
                close_conditions["stoch_close_timeframe"] = params.get("stoch_close_timeframe", "Chart")
                close_conditions["stoch_close_profit_only"] = params.get("stoch_close_profit_only", False)
                close_conditions["stoch_close_min_profit"] = params.get("stoch_close_min_profit", 1.0)
                close_conditions["stoch_close_activate_reach"] = params.get("activate_stoch_reach", False)
                close_conditions["stoch_close_long_more"] = params.get("stoch_long_more", 80)
                close_conditions["stoch_close_long_less"] = params.get("stoch_long_less", 100)
                close_conditions["stoch_close_short_less"] = params.get("stoch_short_less", 20)
                close_conditions["stoch_close_short_more"] = params.get("stoch_short_more", 1)
                close_conditions["stoch_close_activate_cross"] = params.get("activate_stoch_cross", False)
                close_conditions["stoch_close_cross_long_level"] = params.get("stoch_cross_long_level", 80)
                close_conditions["stoch_close_cross_short_level"] = params.get("stoch_cross_short_level", 20)
            elif block_type == "close_psar":
                close_conditions["psar_close_enable"] = True
                close_conditions["psar_close_opposite"] = params.get("psar_opposite", False)
                close_conditions["psar_close_profit_only"] = params.get("psar_close_profit_only", False)
                close_conditions["psar_close_min_profit"] = params.get("psar_close_min_profit", 1.0)
                close_conditions["psar_close_start"] = params.get("psar_start", 0.02)
                close_conditions["psar_close_increment"] = params.get("psar_increment", 0.02)
                close_conditions["psar_close_maximum"] = params.get("psar_maximum", 0.2)
                close_conditions["psar_close_nth_bar"] = params.get("psar_close_nth_bar", 1)
            elif block_type == "time_bars_close":
                close_conditions["time_bars_close_enable"] = True
                close_conditions["close_after_bars"] = params.get("close_after_bars", 20)
                close_conditions["close_only_profit"] = params.get("close_only_profit", True)
                close_conditions["close_min_profit"] = params.get("close_min_profit", 0.5)
                close_conditions["close_max_bars"] = params.get("close_max_bars", 100)

        # Indent Order (Session 5.5): extract from action block
        indent_order: dict[str, Any] = {}
        for _block_id, block in self.blocks.items():
            block_type = block.get("type", "")
            params = block.get("params") or block.get("config") or {}
            if block_type == "indent_order":
                indent_order["enabled"] = params.get("indent_enable", True)
                indent_order["indent_percent"] = params.get("indent_percent", 0.1)
                indent_order["cancel_after_bars"] = params.get("indent_cancel_bars", 10)
                break

        dca_config["close_conditions"] = close_conditions
        dca_config["indent_order"] = indent_order
        return dca_config

    def has_dca_blocks(self) -> bool:
        """
        Check if strategy contains any DCA grid blocks.

        Returns:
            True if any block has category="dca_grid" or is 'dca' type from entry_mgmt/entry_refinement
        """
        for block in self.blocks.values():
            category = block.get("category", "")
            block_type = block.get("type", "")

            # New format: 'dca' block from entry_mgmt/entry_refinement category
            if category in ("entry_refinement", "entry_mgmt") and block_type == "dca":
                return True

            # Old format: dca_grid category
            if category == "dca_grid" and block_type == "dca_grid_enable":
                params = block.get("params") or block.get("config") or {}
                if params.get("enabled", True):
                    return True
        return False

    @classmethod
    def _check_registry_consistency(cls) -> list[str]:
        """Cross-check BLOCK_REGISTRY against _BLOCK_CATEGORY_MAP.

        Returns a list of human-readable problem descriptions so callers can
        decide how to surface them (log, raise, print).  An empty list means
        everything is consistent.

        Checks performed:
          A. Every "indicator" entry in _BLOCK_CATEGORY_MAP must appear in
             BLOCK_REGISTRY — otherwise the adapter will call a handler that
             does not exist and return {}.
          B. Every key in BLOCK_REGISTRY must appear in _BLOCK_CATEGORY_MAP
             (category == "indicator") — otherwise a registered handler is
             unreachable from the graph execution path.
          C. Every entry in BLOCK_REGISTRY must declare at least one output key.
          D. Every param_alias value must differ from its key (a self-alias is
             always a no-op and usually a copy-paste mistake).
        """
        from backend.backtesting.indicator_handlers import BLOCK_REGISTRY

        problems: list[str] = []

        # Collect all "indicator" block types from the category map
        indicator_types_in_map = {k for k, v in cls._BLOCK_CATEGORY_MAP.items() if v == "indicator"}

        # A: in map but missing from registry
        for btype in indicator_types_in_map:
            if btype not in BLOCK_REGISTRY:
                problems.append(
                    f"[A] '{btype}' is 'indicator' in _BLOCK_CATEGORY_MAP but "
                    f"has no entry in BLOCK_REGISTRY — _execute_indicator will "
                    f"return {{}} for this block."
                )

        # B: in registry but missing from map (or wrong category)
        for btype in BLOCK_REGISTRY:
            cat = cls._BLOCK_CATEGORY_MAP.get(btype)
            if cat != "indicator":
                problems.append(
                    f"[B] '{btype}' is in BLOCK_REGISTRY but _BLOCK_CATEGORY_MAP "
                    f"has category={cat!r} (expected 'indicator') — handler is "
                    f"unreachable from the graph execution path."
                )

        # C: empty outputs declaration
        for btype, entry in BLOCK_REGISTRY.items():
            if not entry.get("outputs"):
                problems.append(
                    f"[C] '{btype}' BLOCK_REGISTRY entry has no 'outputs' list — "
                    f"add the keys returned by its handler so mismatches are detected."
                )

        # D: self-alias (no-op)
        for btype, entry in BLOCK_REGISTRY.items():
            for old, new in (entry.get("param_aliases") or {}).items():
                if old == new:
                    problems.append(
                        f"[D] '{btype}' param_aliases has self-alias '{old}' -> '{new}' "
                        f"(no-op — remove it or fix the alias target)."
                    )

        return problems

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """
        Generate trading signals from OHLCV data by executing the strategy graph.

        Args:
            ohlcv: DataFrame with columns: open, high, low, close, volume
                   Index should be datetime

        Returns:
            SignalResult with entry/exit signals
        """
        # Clear cache
        self._value_cache.clear()

        # Execute blocks in order
        for block_id in self.execution_order:
            block = self.blocks[block_id]
            block_type = block.get("type")

            # Skip pure strategy node (they just aggregate signals, don't produce own outputs)
            # But DO execute signal blocks (long_entry, short_entry, etc.) even if they are main
            if block_type == "strategy":
                continue

            # Execute block and cache outputs
            outputs = self._execute_block(block_id, ohlcv)
            self._value_cache[block_id] = outputs

            # Diagnostic logging for signal tracing
            if outputs:
                for port_id, series in outputs.items():
                    if hasattr(series, "sum") and series.dtype == bool:
                        true_count = int(series.sum())
                        if true_count > 0:
                            logger.debug(
                                f"[SignalTrace] Block '{block_type}' ({block_id}) "
                                f"port '{port_id}': {true_count} True signals"
                            )

        # Find main strategy node and collect entry/exit signals
        main_node_id = None
        main_node = None
        for block_id, block in self.blocks.items():
            if block.get("type") == "strategy" or block.get("isMain"):
                main_node_id = block_id
                main_node = block
                break

        # Initialize signals
        n = len(ohlcv)
        entries = pd.Series([False] * n, index=ohlcv.index)
        exits = pd.Series([False] * n, index=ohlcv.index)
        short_entries = pd.Series([False] * n, index=ohlcv.index)
        short_exits = pd.Series([False] * n, index=ohlcv.index)

        # Per-signal profit_only tracking (Feature 1 — close_cond blocks)
        profit_only_exits = pd.Series(False, index=ohlcv.index)
        profit_only_short_exits = pd.Series(False, index=ohlcv.index)
        min_profit_for_exits: float = 0.0
        min_profit_for_short_exits: float = 0.0

        # Track whether main node received signals via connections
        has_connections_to_main = False

        if main_node_id:
            # Case 1: Main node is a signal block (long_entry, short_entry, etc.)
            # Its outputs should directly map to signals.
            # NOTE: type="strategy" main nodes are skipped during execution, so
            # they won't appear in _value_cache. This branch handles edge cases
            # where a signal block is marked as main.
            case1_found = False
            if main_node_id in self._value_cache:
                main_outputs = self._value_cache[main_node_id]
                main_type = main_node.get("type", "") if main_node else ""

                # Map signal block outputs directly
                if "entry_long" in main_outputs:
                    entries = entries | main_outputs["entry_long"]
                    case1_found = True
                if "entry_short" in main_outputs:
                    short_entries = short_entries | main_outputs["entry_short"]
                    case1_found = True
                if "exit_long" in main_outputs:
                    exits = exits | main_outputs["exit_long"]
                    case1_found = True
                if "exit_short" in main_outputs:
                    short_exits = short_exits | main_outputs["exit_short"]
                    case1_found = True

                # Also check for generic "signal" output based on block type
                if "signal" in main_outputs:
                    signal = main_outputs["signal"]
                    if main_type in ["long_entry", "entry_long", "buy_signal"]:
                        entries = entries | signal
                        case1_found = True
                    elif main_type in ["short_entry", "entry_short", "sell_signal"]:
                        short_entries = short_entries | signal
                        case1_found = True
                    elif main_type in ["long_exit", "exit_long", "close_long"]:
                        exits = exits | signal
                        case1_found = True
                    elif main_type in ["short_exit", "exit_short", "close_short"]:
                        short_exits = short_exits | signal
                        case1_found = True

                if case1_found:
                    logger.debug(
                        f"[SignalRouting] Case 1: main node '{main_node_id}' "
                        f"had cached outputs, skipping connection scan"
                    )

            # Case 2: Main node is a pure strategy aggregator — collect from
            # connections ONLY when Case 1 didn't produce signals (avoid
            # double-counting if main node is both cached and wired to).
            # Port alias map is defined at class level: self._SIGNAL_PORT_ALIASES
            # e.g. frontend sends "long" but backend might return "bullish".

            if not case1_found:
                for conn in self.connections:
                    target_id = conn["target_id"]
                    if target_id == main_node_id:
                        has_connections_to_main = True
                        source_id = conn["source_id"]
                        source_port = conn["source_port"]
                        target_port = conn["target_port"]

                        if source_id in self._value_cache:
                            source_outputs = self._value_cache[source_id]

                            # ── Special case: close_cond port ──────────────────────
                            # Close-condition blocks output their signals under
                            # "exit_long" / "exit_short" keys, NOT as a single aliased
                            # signal. Their frontend output port is named "config" which
                            # does NOT appear in _execute_close_condition output — so
                            # standard signal resolution yields signal=None and skips the
                            # connection. Handle close_cond BEFORE signal resolution to
                            # prevent the dead-code bug (RSI/channel/MA-cross exits were
                            # silently dropped).
                            if target_port == "close_cond":
                                raw = source_outputs
                                # Collect profit_only flags from this close_cond block
                                has_po = raw.get("profit_only")  # pd.Series[bool] or None
                                min_pv = raw.get("min_profit")  # pd.Series[float] or None
                                # min_profit in params is in percent (1.0 = 1%);
                                # convert to decimal fraction for the engine.
                                mp_decimal = float(min_pv.iloc[0]) / 100.0 if min_pv is not None else 0.0

                                if "exit_long" in raw:
                                    exits = exits | raw["exit_long"]
                                    if has_po is not None:
                                        profit_only_exits = profit_only_exits | raw["exit_long"]
                                        min_profit_for_exits = max(min_profit_for_exits, mp_decimal)
                                if "exit_short" in raw:
                                    short_exits = short_exits | raw["exit_short"]
                                    if has_po is not None:
                                        profit_only_short_exits = profit_only_short_exits | raw["exit_short"]
                                        min_profit_for_short_exits = max(min_profit_for_short_exits, mp_decimal)
                                if "exit" in raw and "exit_long" not in raw and "exit_short" not in raw:
                                    exits = exits | raw["exit"]
                                    short_exits = short_exits | raw["exit"]
                                logger.debug(
                                    f"[SignalRouting] close_cond port: block '{source_id}' "
                                    f"-> exits updated from {list(raw.keys())}"
                                )
                                continue

                            # ── Config ports: router handles, no signal routing ─────
                            if target_port in ("sl_tp", "sltp", "dca", "dca_grid"):
                                logger.debug(
                                    f"[SignalRouting] Config port '{target_port}': block "
                                    f"'{source_id}' -> params handled by router, no signal extracted."
                                )
                                continue

                            # Resolve source port: direct match, then aliases, then single-output fallback
                            signal = None
                            if source_port in source_outputs:
                                signal = source_outputs[source_port]
                            else:
                                # Try port aliases (e.g. "long" в†' "bullish")
                                for alias in self._SIGNAL_PORT_ALIASES.get(source_port, []):
                                    if alias in source_outputs:
                                        signal = source_outputs[alias]
                                        logger.debug(
                                            f"[SignalRouting] Port alias: '{source_port}' в†' '{alias}' "
                                            f"for block {source_id}"
                                        )
                                        break
                                # Last resort: single-output block в†' use that output
                                if signal is None and len(source_outputs) == 1:
                                    signal = next(iter(source_outputs.values()))
                                    logger.debug(
                                        f"[SignalRouting] Single-output fallback for block {source_id}, "
                                        f"port '{source_port}' not found, using only output"
                                    )

                            if signal is None:
                                logger.warning(
                                    f"[SignalRouting] Port '{source_port}' not found in block "
                                    f"'{source_id}' outputs {list(source_outputs.keys())}. "
                                    f"Signal dropped! Check block output port names."
                                )
                                continue

                            # Map to appropriate signal series
                            # Support old format (entry_long/entry_short),
                            # new (entry/exit), and action aliases (buy/sell)
                            if target_port in ("entry_long", "buy"):
                                entries = entries | signal
                            elif target_port in ("exit_long", "close_long"):
                                exits = exits | signal
                            elif target_port in ("entry_short", "sell"):
                                short_entries = short_entries | signal
                            elif target_port in ("exit_short", "close_short"):
                                short_exits = short_exits | signal
                            elif target_port == "entry":
                                # Universal entry - applies to both long and short based on direction
                                entries = entries | signal
                                short_entries = short_entries | signal
                            elif target_port == "exit":
                                # Universal exit - applies to both long and short
                                exits = exits | signal
                                short_exits = short_exits | signal
                            else:
                                logger.warning(
                                    f"[SignalRouting] Unrecognised target port '{target_port}' "
                                    f"on strategy node from block '{source_id}' "
                                    f"(outputs: {list(source_outputs.keys())}). Signal dropped."
                                )

        # Fallback: Look for signal blocks by category ONLY when:
        # 1. No main node exists at all, OR
        # 2. Main node exists but has NO incoming connections AND produced 0 signals.
        # 3. (Bug #2 fix) Connections exist but ALL blocks produced 0 signals --
        #    log diagnostic warning and enable fallback so user is not left with 0 trades.
        use_fallback = not main_node_id or (
            not has_connections_to_main and entries.sum() == 0 and short_entries.sum() == 0
        )

        if has_connections_to_main and not use_fallback and entries.sum() == 0 and short_entries.sum() == 0:
            _conn_count = sum(1 for conn in self.connections if conn.get("target_id") == main_node_id)
            logger.warning(
                "[SignalRouting] Strategy '%s': %d connection(s) to main node but "
                "ALL signal series are empty (0 long, 0 short entries). "
                "Possible causes: indicator period > data length, wrong port wiring, "
                "or block execution error. Enabling category-based fallback routing.",
                self.name,
                _conn_count,
            )
            use_fallback = True  # Bug #2 fix: don't silently return 0 trades

        if use_fallback:
            for block_id, block in self.blocks.items():
                block_type = block.get("type", "")
                category = block.get("category", "")

                # Signal category blocks
                if category == "signal" and block_id in self._value_cache:
                    outputs = self._value_cache[block_id]

                    if block_type in ["long_entry", "entry_long", "buy_signal"]:
                        if "signal" in outputs:
                            entries = entries | outputs["signal"]
                        if "entry_long" in outputs:
                            entries = entries | outputs["entry_long"]

                    elif block_type in ["short_entry", "entry_short", "sell_signal"]:
                        if "signal" in outputs:
                            short_entries = short_entries | outputs["signal"]
                        if "entry_short" in outputs:
                            short_entries = short_entries | outputs["entry_short"]

                    elif block_type in ["long_exit", "exit_long", "close_long"]:
                        if "signal" in outputs:
                            exits = exits | outputs["signal"]
                        if "exit_long" in outputs:
                            exits = exits | outputs["exit_long"]

                    elif block_type in ["short_exit", "exit_short", "close_short"]:
                        if "signal" in outputs:
                            short_exits = short_exits | outputs["signal"]
                        if "exit_short" in outputs:
                            short_exits = short_exits | outputs["exit_short"]

                # Also check action blocks (buy, sell, close) if no signal blocks found
                elif category == "action" and block_id in self._value_cache:
                    outputs = self._value_cache[block_id]
                    if block_type in ["buy", "buy_market", "buy_limit"]:
                        if "entry_long" in outputs:
                            entries = entries | outputs["entry_long"]
                        elif "signal" in outputs:
                            entries = entries | outputs["signal"]
                    elif block_type in ["sell", "sell_market", "sell_limit"]:
                        if "entry_short" in outputs:
                            short_entries = short_entries | outputs["entry_short"]
                        elif "signal" in outputs:
                            short_entries = short_entries | outputs["signal"]
                    elif block_type == "close_long":
                        if "exit_long" in outputs:
                            exits = exits | outputs["exit_long"]
                        elif "signal" in outputs:
                            exits = exits | outputs["signal"]
                    elif block_type == "close_short":
                        if "exit_short" in outputs:
                            short_exits = short_exits | outputs["exit_short"]
                        elif "signal" in outputs:
                            short_exits = short_exits | outputs["signal"]

        # ========== Collect ATR exit data for engine ==========
        extra_data: dict = {}
        for block_id, block in self.blocks.items():
            if block.get("type") == "atr_exit" and block_id in self._value_cache:
                cached = self._value_cache[block_id]
                if cached.get("use_atr_sl"):
                    extra_data["use_atr_sl"] = True
                    extra_data["atr_sl"] = cached["atr_sl"]  # pd.Series
                    extra_data["atr_sl_mult"] = cached["atr_sl_mult"]
                    extra_data["atr_sl_on_wicks"] = cached.get("atr_sl_on_wicks", False)
                if cached.get("use_atr_tp"):
                    extra_data["use_atr_tp"] = True
                    extra_data["atr_tp"] = cached["atr_tp"]  # pd.Series
                    extra_data["atr_tp_mult"] = cached["atr_tp_mult"]
                    extra_data["atr_tp_on_wicks"] = cached.get("atr_tp_on_wicks", False)
                break  # Only one atr_exit block expected

        # ========== Collect trailing_stop_exit data for engine ==========
        for block_id, block in self.blocks.items():
            if block.get("type") == "trailing_stop_exit" and block_id in self._value_cache:
                cached = self._value_cache[block_id]
                activation = cached.get("trailing_activation_percent")
                trail_dist = cached.get("trailing_percent")
                if activation is not None and trail_dist is not None:
                    extra_data["use_trailing_stop"] = True
                    extra_data["trailing_activation_percent"] = float(activation)
                    extra_data["trailing_percent"] = float(trail_dist)
                    extra_data["trail_type"] = cached.get("trail_type", "percent")
                break  # Only one trailing_stop_exit block expected

        # ========== Collect profit_only exit data for engine (Feature 1) ==========
        # Only write to extra_data when at least one close_cond block activated
        # profit_only — avoids unnecessary numpy work in the engine hot loop.
        if profit_only_exits.any() or profit_only_short_exits.any():
            extra_data["profit_only_exits"] = profit_only_exits  # pd.Series[bool]
            extra_data["profit_only_short_exits"] = profit_only_short_exits
            extra_data["min_profit_exits"] = min_profit_for_exits  # float, decimal fraction
            extra_data["min_profit_short_exits"] = min_profit_for_short_exits
            logger.debug(
                "[SignalRouting] profit_only_exits: long_bars={} min={:.4f}, short_bars={} min={:.4f}",
                int(profit_only_exits.sum()),
                min_profit_for_exits,
                int(profit_only_short_exits.sum()),
                min_profit_for_short_exits,
            )

        logger.info(
            f"[SignalSummary] Strategy '{self.name}': "
            f"entries={int(entries.sum())}, exits={int(exits.sum())}, "
            f"short_entries={int(short_entries.sum())}, short_exits={int(short_exits.sum())}, "
            f"blocks={len(self.blocks)}, connections={len(self.connections)}"
        )

        return SignalResult(
            entries=entries,
            exits=exits,
            short_entries=short_entries,
            short_exits=short_exits,
            extra_data=extra_data if extra_data else None,
        )

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        """Get default parameters (not used for builder strategies)"""
        return {}

    def __repr__(self) -> str:
        return (
            f"StrategyBuilderAdapter(name='{self.name}', "
            f"blocks={len(self.blocks)}, connections={len(self.connections)})"
        )
