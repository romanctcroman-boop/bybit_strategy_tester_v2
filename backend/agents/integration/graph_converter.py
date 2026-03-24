"""
StrategyDefToGraphConverter — bridges LLM-generated StrategyDefinition to the
Strategy Builder graph format consumed by StrategyBuilderAdapter.

Instead of the legacy BacktestBridge (only 6 strategy types), this converter
translates the full StrategyDefinition into a strategy_graph dict with 40+
block types, enabling the StrategyBuilderAdapter to execute the full
signal pipeline with all indicator modes, filter gates, and port wiring.

Output graph format matches StrategyBuilderAdapter.__init__(strategy_graph):
{
    "name": str,
    "interval": str,            # e.g. "15"
    "blocks": [
        {"id": str, "type": str, "params": dict, "isMain": bool},
        ...
    ],
    "connections": [
        {"from": str, "fromPort": str, "to": str, "toPort": str},
        ...
    ],
}
"""

from __future__ import annotations

import itertools
from typing import Any

from loguru import logger

from backend.agents.prompts.response_parser import Filter, Signal, StrategyDefinition

# =============================================================================
# Block type configuration tables
# =============================================================================

# Category A: blocks that produce long / short boolean outputs directly
# Key = Signal.type (as returned by response_parser after normalization)
# Value:
#   block_type   — strategy builder block type identifier
#   activate     — params to merge that enable the signal mode
#   param_renames — LLM param name → block param name (for mismatches)
#   default_params — fallback params if LLM does not supply them
_SIGNAL_CAT_A: dict[str, dict[str, Any]] = {
    "RSI": {
        "block_type": "rsi",
        # Legacy mode activates automatically when oversold/overbought present.
        # If neither present, set use_long_range + oversold zone defaults.
        "activate": {},
        "param_renames": {},
        "default_params": {"period": 14, "oversold": 30, "overbought": 70},
    },
    "MACD": {
        "block_type": "macd",
        "activate": {"use_macd_cross_signal": True},
        "param_renames": {},
        "default_params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
    },
    "Stochastic": {
        "block_type": "stochastic",
        "activate": {"use_stoch_kd_cross": True},
        "param_renames": {
            "k_period": "stoch_k_length",
            "d_period": "stoch_d_smoothing",
            "smooth": "stoch_k_smoothing",
        },
        "default_params": {
            "stoch_k_length": 14,
            "stoch_k_smoothing": 3,
            "stoch_d_smoothing": 3,
        },
    },
    "SuperTrend": {
        "block_type": "supertrend",
        "activate": {"use_supertrend": True},
        "param_renames": {},
        "default_params": {"period": 10, "multiplier": 3.0},
    },
    # EMA/SMA crossovers map to two_mas with use_ma_cross
    "EMA_Crossover": {
        "block_type": "two_mas",
        "activate": {"use_ma_cross": True},
        "param_renames": {"fast_period": "ma1_length", "slow_period": "ma2_length"},
        "default_params": {
            "ma1_length": 20,
            "ma1_smoothing": "EMA",
            "ma2_length": 50,
            "ma2_smoothing": "EMA",
        },
    },
    "SMA_Crossover": {
        "block_type": "two_mas",
        "activate": {"use_ma_cross": True},
        "param_renames": {"fast_period": "ma1_length", "slow_period": "ma2_length"},
        "default_params": {
            "ma1_length": 20,
            "ma1_smoothing": "SMA",
            "ma2_length": 50,
            "ma2_smoothing": "SMA",
        },
    },
    # Single EMA/SMA used as a price filter — remap to two_mas MA1 filter mode
    # long when price > MA1, short when price < MA1
    "EMA": {
        "block_type": "two_mas",
        "activate": {"use_ma1_filter": True},
        "param_renames": {"period": "ma1_length", "fast_period": "ma1_length"},
        "default_params": {
            "ma1_length": 20,
            "ma1_smoothing": "EMA",
            "ma2_length": 50,  # required field, not used in filter mode
            "ma2_smoothing": "EMA",
        },
    },
    "SMA": {
        "block_type": "two_mas",
        "activate": {"use_ma1_filter": True},
        "param_renames": {"period": "ma1_length", "fast_period": "ma1_length"},
        "default_params": {
            "ma1_length": 20,
            "ma1_smoothing": "SMA",
            "ma2_length": 50,
            "ma2_smoothing": "SMA",
        },
    },
}

# Category B: blocks that produce only a value output.
# These require an auxiliary "condition" block pattern:
#   indicator_block → condition_block (port "a")
#   constant_block  → condition_block (port "b")
#   condition_block → strategy_node (long/short entry)
#
# long_condition / short_condition: "less_than" | "greater_than" | "crossover" | "crossunder"
# long_threshold / short_threshold: default constant value
_SIGNAL_CAT_B: dict[str, dict[str, Any]] = {
    "CCI": {
        "block_type": "cci",
        "output_port": "value",
        "param_renames": {},
        "default_params": {"period": 20},
        # long when CCI < oversold, short when CCI > overbought
        "long_condition": "less_than",
        "long_threshold_key": "oversold",
        "long_threshold_default": -100.0,
        "short_condition": "greater_than",
        "short_threshold_key": "overbought",
        "short_threshold_default": 100.0,
    },
    "Williams_R": {
        "block_type": "williams_r",
        "output_port": "value",
        "param_renames": {},
        "default_params": {"period": 14},
        "long_condition": "less_than",
        "long_threshold_key": "oversold",
        "long_threshold_default": -80.0,
        "short_condition": "greater_than",
        "short_threshold_key": "overbought",
        "short_threshold_default": -20.0,
    },
    "ADX": {
        "block_type": "adx",
        "output_port": "value",
        "param_renames": {},
        "default_params": {"period": 14},
        # ADX > threshold = trending (use as filter, same signal for long and short)
        "long_condition": "greater_than",
        "long_threshold_key": "threshold",
        "long_threshold_default": 25.0,
        "short_condition": "greater_than",
        "short_threshold_key": "threshold",
        "short_threshold_default": 25.0,
    },
    "ATR": {
        "block_type": "atr",
        "output_port": "value",
        "param_renames": {},
        "default_params": {"period": 14},
        # ATR > threshold = high volatility filter
        "long_condition": "greater_than",
        "long_threshold_key": "threshold",
        "long_threshold_default": 0.0,
        "short_condition": "greater_than",
        "short_threshold_key": "threshold",
        "short_threshold_default": 0.0,
    },
    "VWAP": {
        "block_type": "vwap",
        "output_port": "value",
        "param_renames": {},
        "default_params": {},
        # long when price > VWAP (need price block)
        "long_condition": "crossover",  # uses price_block a, indicator b
        "long_threshold_key": None,
        "long_threshold_default": None,
        "short_condition": "crossunder",
        "short_threshold_key": None,
        "short_threshold_default": None,
        "use_price_as_a": True,  # special: compare close price vs indicator value
    },
    "OBV": {
        "block_type": "obv",
        "output_port": "value",
        "param_renames": {},
        "default_params": {},
        # OBV is typically used as a divergence / trend-confirmation filter.
        # Fallback: greater_than 0 (rising OBV → long)
        "long_condition": "greater_than",
        "long_threshold_key": "threshold",
        "long_threshold_default": 0.0,
        "short_condition": "less_than",
        "short_threshold_key": "threshold",
        "short_threshold_default": 0.0,
    },
    "Bollinger": {
        "block_type": "bollinger",
        "output_port": "lower",  # long: close crossover lower band
        "param_renames": {},
        "default_params": {"period": 20, "std_dev": 2.0},
        "long_condition": "crossover",  # close crosses above lower band
        "long_threshold_key": None,
        "long_threshold_default": None,
        "short_condition": "crossunder",  # close crosses below upper band
        "short_threshold_key": None,
        "short_threshold_default": None,
        "use_price_as_a": True,
        "short_output_port": "upper",  # short: compare against upper band
    },
}

# Category A filter blocks: produce long/short directly when activated
_FILTER_BLOCK_MAP: dict[str, dict[str, Any]] = {
    "Volatility": {
        "block_type": "atr_volatility",
        "activate": {"use_atr_volatility": True},
        "param_renames": {
            "atr_fast": "atr_length1",
            "atr_slow": "atr_length2",
            "diff_percent": "atr_diff_percent",
        },
        "default_params": {"atr_length1": 20, "atr_length2": 100, "atr_diff_percent": 10},
    },
    "Volume": {
        "block_type": "volume_filter",
        "activate": {"use_volume_filter": True},
        "param_renames": {
            "vol_fast": "vol_length1",
            "vol_slow": "vol_length2",
            "diff_percent": "vol_diff_percent",
        },
        "default_params": {"vol_length1": 20, "vol_length2": 100, "vol_diff_percent": 10},
    },
    "Trend": {
        # Price-above-MA trend filter via two_mas
        "block_type": "two_mas",
        "activate": {"use_ma1_filter": True},
        "param_renames": {"period": "ma1_length"},
        "default_params": {
            "ma1_length": 50,
            "ma1_smoothing": "EMA",
            "ma2_length": 100,
            "ma2_smoothing": "EMA",
        },
    },
    "ADX": {
        "block_type": "adx",
        "activate": {},  # value-only — needs condition block
        "param_renames": {},
        "default_params": {"period": 14},
        "needs_condition": True,
        "condition_type": "greater_than",
        "threshold_default": 25.0,
    },
    "Time": None,  # No equivalent block — skip with warning
}


# =============================================================================
# Converter
# =============================================================================


class StrategyDefToGraphConverter:
    """
    Converts a StrategyDefinition (LLM output) to a strategy_graph dict
    that StrategyBuilderAdapter can execute.

    Usage:
        converter = StrategyDefToGraphConverter()
        graph, warnings = converter.convert(strategy_def, interval="15")
        adapter = StrategyBuilderAdapter(graph)
        signal_result = adapter.generate_signals(ohlcv_df)
    """

    def __init__(self) -> None:
        self._id_counter = itertools.count(1)

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}_{next(self._id_counter)}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(
        self,
        strategy_def: StrategyDefinition,
        interval: str = "15",
    ) -> tuple[dict[str, Any], list[str]]:
        """
        Convert a StrategyDefinition to a strategy_graph dict.

        Args:
            strategy_def: LLM-generated strategy definition
            interval: Chart interval for "Chart" timeframe resolution (default "15")

        Returns:
            (strategy_graph, warnings) where warnings is a list of human-readable
            messages about any conversion decisions or unsupported features.
        """
        self._id_counter = itertools.count(1)  # reset per call
        warnings: list[str] = []
        blocks: list[dict[str, Any]] = []
        connections: list[dict[str, Any]] = []

        strategy_node_id = "strategy_node"
        blocks.append({"id": strategy_node_id, "type": "strategy", "params": {}, "isMain": True})

        logic = (strategy_def.entry_conditions.logic if strategy_def.entry_conditions else "AND").upper()

        # ── Build signal blocks ──────────────────────────────────────────
        long_signal_ids: list[tuple[str, str]] = []  # (block_id, output_port)
        short_signal_ids: list[tuple[str, str]] = []

        for signal in strategy_def.signals:
            long_out, short_out, new_blocks, new_conns, warn = self._build_signal(signal, blocks, interval)
            warnings.extend(warn)
            blocks.extend(new_blocks)
            connections.extend(new_conns)
            if long_out:
                long_signal_ids.append(long_out)
            if short_out:
                short_signal_ids.append(short_out)

        # ── Build filter blocks ──────────────────────────────────────────
        filter_long_ids: list[tuple[str, str]] = []
        filter_short_ids: list[tuple[str, str]] = []

        for flt in strategy_def.filters:
            long_out, short_out, new_blocks, new_conns, warn = self._build_filter(flt, blocks, interval)
            warnings.extend(warn)
            blocks.extend(new_blocks)
            connections.extend(new_conns)
            if long_out:
                filter_long_ids.append(long_out)
            if short_out:
                filter_short_ids.append(short_out)

        # ── Combine signals + filters and wire to strategy_node ──────────
        all_long = long_signal_ids + filter_long_ids
        all_short = short_signal_ids + filter_short_ids

        if all_long:
            long_src, new_blocks, new_conns = self._combine_signals(all_long, logic, "long")
            blocks.extend(new_blocks)
            connections.extend(new_conns)
            connections.append(
                {
                    "from": long_src[0],
                    "fromPort": long_src[1],
                    "to": strategy_node_id,
                    "toPort": "entry_long",
                }
            )
        else:
            warnings.append("No long signals generated — strategy_node entry_long will be empty")

        if all_short:
            short_src, new_blocks, new_conns = self._combine_signals(all_short, logic, "short")
            blocks.extend(new_blocks)
            connections.extend(new_conns)
            connections.append(
                {
                    "from": short_src[0],
                    "fromPort": short_src[1],
                    "to": strategy_node_id,
                    "toPort": "entry_short",
                }
            )

        graph = {
            "name": strategy_def.strategy_name,
            "description": strategy_def.description,
            "interval": interval,
            "blocks": blocks,
            "connections": connections,
        }

        logger.info(
            f"[GraphConverter] '{strategy_def.strategy_name}' → "
            f"{len(blocks)} blocks, {len(connections)} connections"
            + (f", {len(warnings)} warnings" if warnings else "")
        )
        return graph, warnings

    # ------------------------------------------------------------------
    # Signal builders
    # ------------------------------------------------------------------

    def _build_signal(
        self,
        signal: Signal,
        existing_blocks: list[dict[str, Any]],
        interval: str,
    ) -> tuple[
        tuple[str, str] | None,  # long (block_id, port)
        tuple[str, str] | None,  # short (block_id, port)
        list[dict[str, Any]],  # new blocks
        list[dict[str, Any]],  # new connections
        list[str],  # warnings
    ]:
        sig_type = signal.type
        new_blocks: list[dict[str, Any]] = []
        new_conns: list[dict[str, Any]] = []
        warn: list[str] = []

        # Category A?
        if sig_type in _SIGNAL_CAT_A:
            cfg = _SIGNAL_CAT_A[sig_type]
            block_id = self._next_id(cfg["block_type"])
            params = self._build_params(
                signal.params,
                cfg["default_params"],
                cfg["param_renames"],
                cfg["activate"],
                interval,
            )
            # RSI legacy mode: if no range/cross flags set, ensure oversold/overbought are present
            if sig_type == "RSI" and not any(
                params.get(k) for k in ("use_long_range", "use_cross_level", "use_short_range")
            ):
                params.setdefault("oversold", 30)
                params.setdefault("overbought", 70)
            new_blocks.append({"id": block_id, "type": cfg["block_type"], "params": params, "isMain": False})
            return (block_id, "long"), (block_id, "short"), new_blocks, new_conns, warn

        # Category B?
        if sig_type in _SIGNAL_CAT_B:
            cfg = _SIGNAL_CAT_B[sig_type]
            ind_id = self._next_id(cfg["block_type"])
            ind_params = self._build_params(
                signal.params,
                cfg["default_params"],
                cfg.get("param_renames", {}),
                {},
                interval,
            )
            new_blocks.append({"id": ind_id, "type": cfg["block_type"], "params": ind_params, "isMain": False})

            # Build long condition block
            long_out = self._build_cat_b_condition(cfg, ind_id, signal.params, "long", new_blocks, new_conns)
            # Build short condition block
            short_out = self._build_cat_b_condition(cfg, ind_id, signal.params, "short", new_blocks, new_conns)

            warn.append(
                f"Signal '{sig_type}' is a value-only indicator — "
                f"wrapped with condition blocks (threshold-based signal)"
            )
            return long_out, short_out, new_blocks, new_conns, warn

        # Unknown type — warn and skip
        warn.append(f"Unknown signal type '{sig_type}' — skipped")
        return None, None, new_blocks, new_conns, warn

    def _build_cat_b_condition(
        self,
        cfg: dict[str, Any],
        ind_id: str,
        signal_params: dict[str, Any],
        direction: str,  # "long" or "short"
        new_blocks: list[dict[str, Any]],
        new_conns: list[dict[str, Any]],
    ) -> tuple[str, str] | None:
        """Build condition block for Category B indicator."""
        cond_key = f"{direction}_condition"
        thresh_key = f"{direction}_threshold_key"
        thresh_default = f"{direction}_threshold_default"

        condition_type = cfg.get(cond_key)
        if not condition_type:
            return None

        out_port = cfg["output_port"]
        if direction == "short" and "short_output_port" in cfg:
            out_port = cfg["short_output_port"]

        use_price_as_a = cfg.get("use_price_as_a", False)
        threshold_key_name = cfg.get(thresh_key)
        threshold_value = cfg.get(thresh_default)
        if threshold_key_name and threshold_key_name in signal_params:
            try:
                threshold_value = float(signal_params[threshold_key_name])
            except (TypeError, ValueError):
                pass

        cond_id = self._next_id("cond")

        if use_price_as_a:
            # Need a price input block: close price for port "a"
            price_id = self._next_id("price_input")
            new_blocks.append({"id": price_id, "type": "input", "params": {"input_type": "price"}, "isMain": False})
            new_blocks.append(
                {"id": cond_id, "type": "condition", "params": {"condition_type": condition_type}, "isMain": False}
            )
            new_conns.append({"from": price_id, "fromPort": "close", "to": cond_id, "toPort": "a"})
            new_conns.append({"from": ind_id, "fromPort": out_port, "to": cond_id, "toPort": "b"})
        elif threshold_value is not None:
            # Use a constant block for the threshold
            const_id = self._next_id("const")
            new_blocks.append(
                {
                    "id": const_id,
                    "type": "input",
                    "params": {"input_type": "constant", "value": threshold_value},
                    "isMain": False,
                }
            )
            new_blocks.append(
                {"id": cond_id, "type": "condition", "params": {"condition_type": condition_type}, "isMain": False}
            )
            new_conns.append({"from": ind_id, "fromPort": out_port, "to": cond_id, "toPort": "a"})
            new_conns.append({"from": const_id, "fromPort": "value", "to": cond_id, "toPort": "b"})
        else:
            # No threshold, no price — skip
            return None

        return cond_id, "result"

    # ------------------------------------------------------------------
    # Filter builder
    # ------------------------------------------------------------------

    def _build_filter(
        self,
        flt: Filter,
        existing_blocks: list[dict[str, Any]],
        interval: str,
    ) -> tuple[
        tuple[str, str] | None,
        tuple[str, str] | None,
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[str],
    ]:
        new_blocks: list[dict[str, Any]] = []
        new_conns: list[dict[str, Any]] = []
        warn: list[str] = []

        # Normalize filter type
        flt_type = flt.type
        cfg = _FILTER_BLOCK_MAP.get(flt_type)
        if cfg is None:
            if flt_type == "Time":
                warn.append("Time filter not supported as a block — skipped")
            else:
                warn.append(f"Unknown filter type '{flt_type}' — skipped")
            return None, None, new_blocks, new_conns, warn

        if cfg.get("needs_condition"):
            # ADX filter via condition block
            ind_id = self._next_id(cfg["block_type"])
            ind_params = self._build_params(
                flt.params,
                cfg.get("default_params", {}),
                cfg.get("param_renames", {}),
                {},
                interval,
            )
            new_blocks.append({"id": ind_id, "type": cfg["block_type"], "params": ind_params, "isMain": False})
            threshold = float(flt.params.get("threshold", cfg.get("threshold_default", 25.0)))
            const_id = self._next_id("const")
            cond_id = self._next_id("cond")
            new_blocks.append(
                {
                    "id": const_id,
                    "type": "input",
                    "params": {"input_type": "constant", "value": threshold},
                    "isMain": False,
                }
            )
            new_blocks.append(
                {
                    "id": cond_id,
                    "type": "condition",
                    "params": {"condition_type": cfg.get("condition_type", "greater_than")},
                    "isMain": False,
                }
            )
            new_conns.append({"from": ind_id, "fromPort": "value", "to": cond_id, "toPort": "a"})
            new_conns.append({"from": const_id, "fromPort": "value", "to": cond_id, "toPort": "b"})
            # Filter applies equally to both directions
            return (cond_id, "result"), (cond_id, "result"), new_blocks, new_conns, warn

        # Standard Category A filter block
        block_id = self._next_id(cfg["block_type"])
        params = self._build_params(
            flt.params,
            cfg.get("default_params", {}),
            cfg.get("param_renames", {}),
            cfg.get("activate", {}),
            interval,
        )
        new_blocks.append({"id": block_id, "type": cfg["block_type"], "params": params, "isMain": False})
        return (block_id, "long"), (block_id, "short"), new_blocks, new_conns, warn

    # ------------------------------------------------------------------
    # Signal combining
    # ------------------------------------------------------------------

    def _combine_signals(
        self,
        signal_ids: list[tuple[str, str]],  # [(block_id, port), ...]
        logic: str,  # "AND" or "OR"
        direction: str,  # "long" or "short" (for id naming)
    ) -> tuple[
        tuple[str, str],  # final output (block_id, port)
        list[dict[str, Any]],  # new blocks
        list[dict[str, Any]],  # new connections
    ]:
        """Combine N signals using AND/OR logic blocks.

        and/or blocks support up to 3 inputs (ports a, b, c).
        For >3 signals, chains logic blocks: logic(logic(a,b,c), d, e), ...
        """
        new_blocks: list[dict[str, Any]] = []
        new_conns: list[dict[str, Any]] = []

        if len(signal_ids) == 1:
            return signal_ids[0], new_blocks, new_conns

        logic_type = "and" if logic == "AND" else "or"
        current_signals = list(signal_ids)

        while len(current_signals) > 1:
            # Take up to 3 from the front
            chunk = current_signals[:3]
            remaining = current_signals[3:]

            gate_id = self._next_id(f"{logic_type}_{direction}")
            new_blocks.append({"id": gate_id, "type": logic_type, "params": {}, "isMain": False})

            ports = ["a", "b", "c"]
            for port, (src_id, src_port) in zip(ports, chunk):
                new_conns.append({"from": src_id, "fromPort": src_port, "to": gate_id, "toPort": port})

            # The output of this gate becomes a new signal for the next round
            current_signals = [(gate_id, "output")] + remaining

        return current_signals[0], new_blocks, new_conns

    # ------------------------------------------------------------------
    # Param building helpers
    # ------------------------------------------------------------------

    def _build_params(
        self,
        llm_params: dict[str, Any],
        defaults: dict[str, Any],
        renames: dict[str, str],
        activate: dict[str, Any],
        interval: str,
    ) -> dict[str, Any]:
        """Merge LLM params → renames → defaults → activation flags."""
        params: dict[str, Any] = dict(defaults)

        for k, v in llm_params.items():
            # Apply rename if known, otherwise pass through as-is
            dest_key = renames.get(k, k)
            params[dest_key] = v

        # Activation flags (override anything — these are mode switches)
        params.update(activate)

        # Resolve "Chart" timeframe
        if params.get("timeframe") == "Chart":
            params["timeframe"] = interval

        return params
