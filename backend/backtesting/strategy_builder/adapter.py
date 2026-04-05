"""
Strategy Builder Adapter

Converts Strategy Builder visual graphs (blocks + connections) into executable
BaseStrategy instances that can be used with backtesting engines.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger

from backend.backtesting.strategies import BaseStrategy, SignalResult
from backend.backtesting.strategy_builder.block_executor import (
    apply_signal_memory,
    execute_action,
    execute_close_condition,
    execute_condition,
    execute_divergence,
    execute_exit,
    execute_filter,
    execute_input,
    execute_logic,
    execute_position_sizing,
    execute_price_action,
    execute_signal_block,
    execute_time_filter,
)
from backend.backtesting.strategy_builder.graph_parser import normalize_connections
from backend.backtesting.strategy_builder.signal_router import PORT_ALIASES, SIGNAL_PORT_ALIASES
from backend.backtesting.strategy_builder.topology import (
    BLOCK_CATEGORY_MAP,
    build_execution_order,
    infer_category,
)

# Import our custom indicators for extended coverage


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

    # Port alias maps — delegates to signal_router module
    _PORT_ALIASES: dict[str, list[str]] = PORT_ALIASES
    _SIGNAL_PORT_ALIASES: dict[str, list[str]] = SIGNAL_PORT_ALIASES

    def __init__(
        self,
        strategy_graph: dict[str, Any],
        btcusdt_ohlcv: pd.DataFrame | None = None,
        btcusdt_5m_ohlcv: pd.DataFrame | None = None,
    ):
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
            btcusdt_5m_ohlcv: Pre-loaded BTCUSDT 5-minute OHLCV DataFrame for
                intra-bar RSI cross detection (TradingView parity). When provided,
                _handle_rsi will check whether the RSI crossed the level within
                each higher-timeframe bar using 5m ticks — matching TV's
                calc_on_every_tick behaviour. Pass None to disable (bar-close only).
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

        # BTCUSDT 5-minute OHLCV for intra-bar RSI cross detection (TV parity).
        # When provided, _handle_rsi uses 5m ticks to detect RSI crossings that
        # occur within a higher-timeframe bar but don't show at bar close.
        self._btcusdt_5m_ohlcv: pd.DataFrame | None = btcusdt_5m_ohlcv

        # Validate
        self._validate_params()

    # в"Ђв"Ђ Connection normalization в"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђв"Ђ
    # The frontend, AI Builder, and tests send connections in 5+ different
    # key schemas.  _normalize_connections() runs once in __init__ and
    # converts every connection to a flat canonical dict:
    #   {"source_id": str, "target_id": str, "source_port": str, "target_port": str}
    # After that the rest of the codebase does simple key lookups.

    @staticmethod
    def _normalize_connections(raw_connections: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Normalize connections to canonical format once at init time.

        Delegates to :func:`backend.backtesting.strategy_builder.graph_parser.normalize_connections`.
        Kept as a staticmethod for backward compatibility with any code that calls
        ``StrategyBuilderAdapter._normalize_connections()``.
        """
        return normalize_connections(raw_connections)

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
        """Return True if any block requires BTCUSDT OHLCV as an alternative data source.

        Currently detected cases:
        - ``mfi_filter`` block with ``use_btcusdt_mfi=True``  (Фича 3)
        - ``rsi`` block with ``use_btc_source=True``           (RSI on BTC price)

        Called by the router BEFORE constructing the adapter so it can pre-load
        BTCUSDT OHLCV and pass it as the btcusdt_ohlcv kwarg.  Can also be
        called as a static helper by passing a raw strategy_graph dict:

            needs_btc = StrategyBuilderAdapter(graph)._requires_btcusdt_data()
        """
        for block in self.blocks.values():
            btype = block.get("type", "")
            bparams = block.get("params", {})
            if btype == "mfi_filter" and bparams.get("use_btcusdt_mfi", False):
                return True
            if btype == "rsi" and bparams.get("use_btc_source", False):
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
        """Build topological sort of blocks based on connections.

        Delegates to :func:`backend.backtesting.strategy_builder.topology.build_execution_order`.
        """
        return build_execution_order(self.blocks, self.connections)

    # Block type -> category mapping — delegates to topology module
    _BLOCK_CATEGORY_MAP: dict[str, str] = BLOCK_CATEGORY_MAP

    @classmethod
    def _infer_category(cls, block_type: str) -> str:
        """Infer block category from block type when category field is missing.

        Delegates to :func:`backend.backtesting.strategy_builder.topology.infer_category`.
        """
        return infer_category(block_type)

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
    @staticmethod
    def _apply_signal_memory(signal: pd.Series, bars: int) -> pd.Series:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.apply_signal_memory`."""
        return apply_signal_memory(signal, bars)

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
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_condition`."""
        return execute_condition(condition_type, params, inputs)

    def _execute_input(self, input_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_input`."""
        return execute_input(input_type, params, ohlcv)

    def _execute_logic(
        self, logic_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_logic`."""
        return execute_logic(logic_type, params, inputs)

    def _execute_filter(
        self, filter_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_filter`."""
        return execute_filter(filter_type, params, ohlcv, inputs)

    def _execute_signal_block(
        self, signal_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_signal_block`."""
        return execute_signal_block(signal_type, params, inputs)

    def _execute_action(
        self, action_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_action`."""
        return execute_action(action_type, params, inputs)

    def _execute_exit(
        self, exit_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_exit`."""
        return execute_exit(exit_type, params, ohlcv, inputs)

    def _execute_position_sizing(self, sizing_type: str, params: dict[str, Any]) -> dict[str, Any]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_position_sizing`."""
        return execute_position_sizing(sizing_type, params)

    def _execute_time_filter(self, time_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_time_filter`."""
        return execute_time_filter(time_type, params, ohlcv)

    def _execute_price_action(
        self, pattern_type: str, params: dict[str, Any], ohlcv: pd.DataFrame
    ) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_price_action`."""
        return execute_price_action(pattern_type, params, ohlcv)

    def _execute_divergence(self, div_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_divergence`."""
        return execute_divergence(div_type, params, ohlcv)

    def _execute_close_condition(
        self, close_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Delegates to :func:`backend.backtesting.strategy_builder.block_executor.execute_close_condition`."""
        return execute_close_condition(close_type, params, ohlcv, inputs)

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
            # Partial grid placement (1 = all orders at once, 2-4 = place N orders at a time)
            "partial_grid_orders": 1,
            # Grid pullback: re-place grid if price moves this % away without fills (0 = disabled)
            "grid_pullback_percent": 0.0,
        }

        for _block_id, block in self.blocks.items():
            category = block.get("category", "")
            block_type = block.get("type", "")
            params = block.get("params") or block.get("config") or {}

            # Support for Manual Grid (grid_orders) block.
            # Match by block_type regardless of category — category may be missing
            # or inferred incorrectly for blocks saved without explicit category field.
            if block_type == "grid_orders":
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

            # Support for unified 'dca' block (new format).
            # Match by block_type alone — category may be missing, inferred as
            # "dca_grid" (via _BLOCK_CATEGORY_MAP), or correctly set to
            # "entry_mgmt"/"entry_refinement".  Old-format DCA blocks use distinct
            # types (dca_grid_enable, dca_grid_settings, etc.) handled below.
            elif block_type == "dca":
                dca_config["dca_enabled"] = True
                dca_config["dca_grid_size_percent"] = params.get("grid_size_percent", 15.0)
                dca_config["dca_order_count"] = params.get("order_count", 5)
                dca_config["dca_martingale_coef"] = params.get("martingale_coefficient", 1.0)
                # Read direction from block params — this is critical so that a "Long" DCA
                # strategy doesn't accidentally open short positions.
                # Falls back to "both" (the safe default when direction is unspecified).
                block_direction = params.get("direction", params.get("dca_direction", None))
                if block_direction in ("long", "short", "both"):
                    dca_config["dca_direction"] = block_direction
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
                # Partial grid: how many orders to place initially (1-4, 1=all orders at once)
                partial_grid = params.get("partial_grid_orders", 1)
                if partial_grid and int(partial_grid) > 1:
                    dca_config["partial_grid_orders"] = int(partial_grid)
                # Grid pullback: shift grid if price moves X% without fills (0=disabled)
                grid_pullback = params.get("grid_pullback_percent", 0)
                if grid_pullback and float(grid_pullback) > 0:
                    dca_config["grid_pullback_percent"] = float(grid_pullback)
                # grid_trailing — use canonical key "grid_trailing_percent" (router reads this key)
                grid_trailing = params.get("grid_trailing", 0)
                if grid_trailing > 0:
                    dca_config["grid_trailing_percent"] = float(grid_trailing)
                    dca_config["grid_trailing"] = float(grid_trailing)  # backward compat

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
            elif block_type == "close_by_time":
                # extract_dca_config is a metadata query — report params regardless of connectivity.
                # (Connectivity check is only relevant in generate_signals() to prevent orphan activation.)
                _cbt_enabled = bool(params.get("enabled", True))
                if not _cbt_enabled:
                    continue
                # Close by Time node: bars_since_entry, profit_only, min_profit_percent
                bars = int(params.get("bars_since_entry", params.get("bars", 10)))
                close_conditions["time_bars_close_enable"] = True
                close_conditions["close_after_bars"] = max(1, bars)
                close_conditions["close_only_profit"] = bool(params.get("profit_only", False))
                close_conditions["close_min_profit"] = float(params.get("min_profit_percent", 0.5))
                close_conditions["close_max_bars"] = max(1, bars)  # Force close at N bars

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
            True if any block has category="dca_grid" or is 'dca'/'grid_orders' type
            from entry_mgmt/entry_refinement, OR if extract_dca_config() would set
            dca_enabled=True. Kept in sync with extract_dca_config() logic.
        """
        for block in self.blocks.values():
            category = block.get("category", "")
            block_type = block.get("type", "")

            # New format: unified 'dca' block OR manual 'grid_orders' block.
            # Check by block_type regardless of category — category may be missing
            # in blocks saved before explicit category field was added, or may be
            # inferred as "dca_grid" for type="dca" via _BLOCK_CATEGORY_MAP.
            if block_type in ("dca", "grid_orders"):
                return True

            # Old format: dca_grid category — only the enable block counts
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
        # AND-filter accumulators: each appended series is ANDed into entries after routing
        long_filters: list = []
        short_filters: list = []

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
                            elif target_port in ("filter_long", "confirm_long"):
                                # AND-filter: reduces long entries (trend confirmation)
                                long_filters.append(signal.astype(bool))
                                logger.debug(
                                    f"[SignalRouting] filter_long: block '{source_id}' "
                                    f"added AND-filter (True={signal.sum()})"
                                )
                            elif target_port in ("filter_short", "confirm_short"):
                                # AND-filter: reduces short entries (trend confirmation)
                                short_filters.append(signal.astype(bool))
                                logger.debug(
                                    f"[SignalRouting] filter_short: block '{source_id}' "
                                    f"added AND-filter (True={signal.sum()})"
                                )
                            elif target_port in ("filter_entry", "confirm_entry"):
                                # AND-filter for both directions
                                long_filters.append(signal.astype(bool))
                                short_filters.append(signal.astype(bool))
                                logger.debug(
                                    f"[SignalRouting] filter_entry: block '{source_id}' "
                                    f"added AND-filter for both directions (True={signal.sum()})"
                                )
                            else:
                                logger.warning(
                                    f"[SignalRouting] Unrecognised target port '{target_port}' "
                                    f"on strategy node from block '{source_id}' "
                                    f"(outputs: {list(source_outputs.keys())}). Signal dropped."
                                )

        # Apply AND-filters collected via filter_long / filter_short ports
        if long_filters:
            combined_lf = long_filters[0]
            for lf in long_filters[1:]:
                combined_lf = combined_lf & lf
            before = int(entries.sum())
            entries = entries & combined_lf
            logger.info(
                "[SignalRouting] filter_long applied: %d -> %d long entries (%d filtered out)",
                before,
                int(entries.sum()),
                before - int(entries.sum()),
            )
        if short_filters:
            combined_sf = short_filters[0]
            for sf in short_filters[1:]:
                combined_sf = combined_sf & sf
            before = int(short_entries.sum())
            short_entries = short_entries & combined_sf
            logger.info(
                "[SignalRouting] filter_short applied: %d -> %d short entries (%d filtered out)",
                before,
                int(short_entries.sum()),
                before - int(short_entries.sum()),
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
            # If AND-filters were applied, 0 entries is a legitimate market result
            # (e.g. downtrend filtered all signals) — don't trigger fallback.
            if long_filters or short_filters:
                logger.info(
                    "[SignalRouting] Strategy '%s': 0 entries after filter_long/filter_short — "
                    "legitimate (no signals in trend direction). Fallback suppressed.",
                    self.name,
                )
            else:
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
            block_type_ex = block.get("type", "")
            if block_type_ex in ("atr_exit", "atr_stop") and block_id in self._value_cache:
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
                break  # Only one atr_exit/atr_stop block expected

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

        # ========== Collect time_exit data for engine ==========
        for block_id, block in self.blocks.items():
            if block.get("type") in ("time_exit", "close_by_time") and block_id in self._value_cache:
                cached = self._value_cache[block_id]
                max_b = cached.get("max_bars")
                if max_b is not None:
                    # max_bars stored as pd.Series (all same value) or scalar
                    val = int(max_b.iloc[0]) if hasattr(max_b, "iloc") else int(max_b)
                    if val > 0:
                        extra_data["max_bars_in_trade"] = val
                # Pass profit_only config from close_by_time block to engine.
                # These are pd.Series of constant True/False — read first element.
                po_series = cached.get("profit_only")
                if po_series is not None:
                    po_val = bool(po_series.iloc[0]) if hasattr(po_series, "iloc") else bool(po_series)
                    if po_val:
                        mp_series = cached.get("min_profit")
                        mp_val = float(mp_series.iloc[0]) if mp_series is not None else 0.0
                        # min_profit_percent stored as percent (0.6 = 0.6%), convert to decimal
                        extra_data["time_exit_profit_only"] = True
                        extra_data["time_exit_min_profit"] = mp_val / 100.0
                break

        # ========== Collect breakeven_exit data for engine ==========
        for block_id, block in self.blocks.items():
            if block.get("type") in ("breakeven_exit", "break_even_exit") and block_id in self._value_cache:
                cached = self._value_cache[block_id]
                trigger = cached.get("breakeven_trigger")
                if trigger is not None:
                    # trigger is in percent (1.0 = 1%) — convert to decimal for engine
                    extra_data["breakeven_enabled"] = True
                    extra_data["breakeven_activation_pct"] = float(trigger) / 100.0
                    extra_data["breakeven_offset"] = 0.0  # move to exact entry price
                break

        # ========== Collect partial_close data for engine ==========
        for block_id, block in self.blocks.items():
            if block.get("type") == "partial_close" and block_id in self._value_cache:
                cached = self._value_cache[block_id]
                targets = cached.get("partial_targets")
                if targets:
                    extra_data["partial_close_targets"] = targets
                break

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
