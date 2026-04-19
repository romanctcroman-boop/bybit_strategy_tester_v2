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

import contextlib
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
        # generate_on_trend_change=True fires only on direction flip (not every bar).
        # Without it, SuperTrend outputs True on ~50% of all bars → commission bleed.
        "activate": {"use_supertrend": True, "generate_on_trend_change": True},
        "param_renames": {},
        "default_params": {"period": 10, "multiplier": 3.0},
    },
    # Bollinger Bands — use keltner_bollinger block (outputs long/short bool directly)
    # Rebound mode: long when price bounces off lower band, short when off upper band
    "Bollinger": {
        "block_type": "keltner_bollinger",
        "activate": {
            "use_channel": True,
            "channel_type": "Bollinger Bands",
            "channel_mode": "Rebound",
            "enter_conditions": "Out-of-band closure",
        },
        "param_renames": {
            "period": "bb_length",
            "std_dev": "bb_deviation",
            "bb_period": "bb_length",
        },
        "default_params": {"bb_length": 20, "bb_deviation": 2.0},
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
    # VWAP: price-relative signal using MA1 filter (price > MA1 → long, price < MA1 → short)
    # Approximates VWAP behaviour with a 50-period EMA (volume-weighting not available in blocks)
    "VWAP": {
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
    # ATR removed from Cat B signals — ATR > 0 is always true (useless).
    # Use "Volatility" filter type instead for ATR-based volatility gating.
    # Bollinger moved to Cat A via keltner_bollinger (see _SIGNAL_CAT_A)
    # VWAP moved to Cat A via two_mas (use_price_as_a path requires unsupported "input" block)
    # OBV removed — threshold comparisons on cumulative OBV are unreliable; use Volume filter instead
}

# Divergence is handled separately: it's a Cat A block (outputs long/short bool directly)
# without needing activation params. Added to _SIGNAL_CAT_A below.
_SIGNAL_CAT_A["Divergence"] = {
    "block_type": "divergence",
    "activate": {},
    "param_renames": {},
    "default_params": {},
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
    "SuperTrend": {
        # SuperTrend trend-direction filter: long when price above ST, short when below.
        # generate_on_trend_change=True prevents it from firing on every bar.
        "block_type": "supertrend",
        "activate": {},
        "param_renames": {},
        "default_params": {"period": 10, "multiplier": 3.0, "generate_on_trend_change": True},
    },
    "Highest/Lowest Bar": {
        # Breakout filter: passes long when current bar is a new high over lookback,
        # passes short when current bar is a new low.
        "block_type": "highest_lowest_bar",
        "activate": {"use_highest_lowest": True},
        "param_renames": {"lookback": "hl_lookback_bars"},
        "default_params": {"hl_lookback_bars": 10, "hl_price_percent": 0, "hl_atr_percent": 0},
    },
    "Time": None,  # No equivalent block — skip with warning
}

# Aliases for filter type names the LLM commonly produces that differ from canonical names
_FILTER_TYPE_ALIASES: dict[str, str] = {
    # Volatility
    "ATR Volatility": "Volatility",
    "ATR_Volatility": "Volatility",
    "Volatility Filter": "Volatility",
    "ATR Filter": "Volatility",
    # Volume
    "Volume Filter": "Volume",
    "Volume_Filter": "Volume",
    "Volume Confirmation": "Volume",
    # Trend
    "Trend Filter": "Trend",
    "Trend_Filter": "Trend",
    "MA Filter": "Trend",
    "EMA Filter": "Trend",
    "Moving Average Filter": "Trend",
    # ADX
    "ADX Filter": "ADX",
    "ADX Trend": "ADX",
    "Trend Strength": "ADX",
    # SuperTrend filter variants
    "Supertrend": "SuperTrend",
    "Super Trend": "SuperTrend",
    "SuperTrend Filter": "SuperTrend",
    "Supertrend Filter": "SuperTrend",
    "ST Filter": "SuperTrend",
    # Highest/Lowest Bar variants
    "Highest Lowest Bar": "Highest/Lowest Bar",
    "HighestLowest": "Highest/Lowest Bar",
    "Breakout Filter": "Highest/Lowest Bar",
    "New High/Low": "Highest/Lowest Bar",
    # Two MAs / MA Crossover used as a filter — treat as Trend filter
    "Two MAs": "Trend",
    "Two MA": "Trend",
    "MA Crossover": "Trend",
    "MA Cross Filter": "Trend",
    "Moving Average Cross": "Trend",
    "Dual MA": "Trend",
    "Double MA": "Trend",
}

# Aliases for signal type names the LLM commonly produces
_SIGNAL_TYPE_ALIASES: dict[str, str] = {
    # Bollinger variants
    "Bollinger Bands": "Bollinger",
    "Bollinger Band": "Bollinger",
    "Bollinger Channel": "Bollinger",
    "Keltner/Bollinger Channel": "Bollinger",
    "BB": "Bollinger",
    # VWAP variants
    "VWAP Filter": "VWAP",
    "Volume Weighted": "VWAP",
    # SuperTrend variants
    "Supertrend": "SuperTrend",
    "Super Trend": "SuperTrend",
    # EMA/SMA crossover variants
    "EMA Cross": "EMA_Crossover",
    "EMA Crossover": "EMA_Crossover",
    "SMA Cross": "SMA_Crossover",
    "SMA Crossover": "SMA_Crossover",
    # MACD variants
    "MACD Cross": "MACD",
    "MACD Crossover": "MACD",
    # Stochastic variants
    "Stoch": "Stochastic",
    "Stochastic RSI": "Stochastic",
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
        # IMPORTANT: Filters are symmetric (same True/False for long and short).
        # They must ALWAYS be AND-combined with the signal result — never OR-combined.
        # OR-combining a symmetric filter with signals creates simultaneous long+short
        # entries on the same bar, causing engine confusion and 0 completed trades.
        # Strategy: combine signals with entry logic (AND/OR), then AND all filters.

        def _wire_direction(
            signal_ids: list[tuple[str, str]],
            filter_ids: list[tuple[str, str]],
            direction: str,
            port: str,
        ) -> None:
            if not signal_ids and not filter_ids:
                warnings.append(f"No {direction} signals generated — strategy_node {port} will be empty")
                return

            # Combine directional signals with the strategy's entry logic
            if signal_ids:
                sig_src, new_b, new_c = self._combine_signals(signal_ids, logic, direction)
                blocks.extend(new_b)
                connections.extend(new_c)
            else:
                sig_src = None

            # Always AND-combine filters with the signal result
            if filter_ids and sig_src is not None:
                # AND gate: [signals_result, filter1, filter2, ...]
                final_src, new_b, new_c = self._combine_signals(
                    [sig_src, *filter_ids], "AND", f"{direction}_filter_gate"
                )
                blocks.extend(new_b)
                connections.extend(new_c)
            elif filter_ids:
                # No signal blocks — only filters: AND-combine filters only
                final_src, new_b, new_c = self._combine_signals(filter_ids, "AND", f"{direction}_filter_gate")
                blocks.extend(new_b)
                connections.extend(new_c)
            else:
                final_src = sig_src

            connections.append({"from": final_src[0], "fromPort": final_src[1], "to": strategy_node_id, "toPort": port})

        _wire_direction(long_signal_ids, filter_long_ids, "long", "entry_long")
        _wire_direction(short_signal_ids, filter_short_ids, "short", "entry_short")

        # ── Exit conditions → static_sltp block ─────────────────────────
        self._build_exit_block(strategy_def, strategy_node_id, blocks, connections, warnings)

        # ── Remove orphan blocks (not connected to strategy_node) ────────
        n_before = len(blocks)
        blocks, connections = self._remove_orphans(blocks, connections, strategy_node_id)
        n_removed = n_before - len(blocks)
        if n_removed:
            warnings.append(f"Removed {n_removed} orphan block(s) not connected to strategy node")

        self._assign_layout_positions(blocks)
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
    # Layout helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assign_layout_positions(blocks: list[dict[str, Any]]) -> None:
        """Assign x/y canvas positions so blocks don't pile up at (100,100).

        Column layout:
          Col 0 (x=80):   indicator blocks
          Col 1 (x=380):  condition / filter blocks
          Col 2 (x=650):  logic gate blocks (and / or / not)
          Col 3 (x=920):  strategy node
        """
        _COL_X = {
            "indicator": 80,
            "condition": 380,
            "filter": 380,
            "logic": 650,
            "strategy": 920,
        }
        _ROW_H = 110  # vertical spacing between blocks in the same column
        _col_y: dict[str, int] = dict.fromkeys(_COL_X, 80)

        def _col_key(block: dict[str, Any]) -> str:
            btype = block.get("type", "")
            if btype == "strategy":
                return "strategy"
            if btype in ("condition", "filter", "atr_volatility", "volume_filter"):
                return "condition"
            if btype in ("and", "or", "not"):
                return "logic"
            return "indicator"

        for block in blocks:
            if block.get("x") and block.get("y"):
                continue  # already positioned
            col = _col_key(block)
            block["x"] = _COL_X[col]
            block["y"] = _col_y[col]
            _col_y[col] += _ROW_H

    # ------------------------------------------------------------------
    # Exit condition helpers
    # ------------------------------------------------------------------

    def _build_exit_block(
        self,
        strategy_def: StrategyDefinition,
        strategy_node_id: str,
        blocks: list[dict[str, Any]],
        connections: list[dict[str, Any]],
        warnings: list[str],
    ) -> None:
        """Create a static_sltp block from exit_conditions and wire to sl_tp port."""
        # Skip if a static_sltp block already exists in the graph (LLM included one)
        if any(b.get("type") == "static_sltp" for b in blocks):
            logger.debug("[GraphConverter] static_sltp already present — skipping auto-add")
            return

        ec = getattr(strategy_def, "exit_conditions", None)
        if not ec:
            return  # engine SL/TP defaults apply — not a warning condition

        tp_val = float(getattr(ec.take_profit, "value", 0.0) or 0.0) if ec.take_profit else 0.0
        sl_val = float(getattr(ec.stop_loss, "value", 0.0) or 0.0) if ec.stop_loss else 0.0

        # Clamp to sensible range: 0.3% – 20%
        tp_pct = max(0.3, min(20.0, tp_val)) if tp_val > 0 else 2.0
        sl_pct = max(0.3, min(20.0, sl_val)) if sl_val > 0 else 1.5

        block_id = f"static_sltp_{next(self._id_counter)}"
        blocks.append(
            {
                "id": block_id,
                "type": "static_sltp",
                "params": {
                    "take_profit_percent": round(tp_pct, 2),
                    "stop_loss_percent": round(sl_pct, 2),
                    "activate_breakeven": False,
                    "close_only_in_profit": False,
                },
            }
        )
        connections.append(
            {
                "from": block_id,
                "fromPort": "exit",
                "to": strategy_node_id,
                "toPort": "sl_tp",
            }
        )
        logger.debug(f"[GraphConverter] Added static_sltp: TP={tp_pct}% SL={sl_pct}%")

    @staticmethod
    def _remove_orphans(
        blocks: list[dict[str, Any]],
        connections: list[dict[str, Any]],
        strategy_node_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Remove blocks that have no path to the strategy node.

        Walks backwards from strategy_node through connections to find all
        reachable block IDs. Blocks not in that set are orphans and are dropped.
        """
        # Build reverse map: target_id → set of source_ids
        reverse: dict[str, set[str]] = {}
        for conn in connections:
            src = conn.get("from", "")
            tgt = conn.get("to", "")
            if src and tgt:
                reverse.setdefault(tgt, set()).add(src)

        # BFS backwards from strategy_node
        reachable: set[str] = {strategy_node_id}
        queue = [strategy_node_id]
        while queue:
            node = queue.pop()
            for src in reverse.get(node, set()):
                if src not in reachable:
                    reachable.add(src)
                    queue.append(src)

        kept_blocks = [b for b in blocks if b.get("id") in reachable]
        kept_conns = [c for c in connections if c.get("from") in reachable and c.get("to") in reachable]
        return kept_blocks, kept_conns

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
        sig_type = _SIGNAL_TYPE_ALIASES.get(signal.type, signal.type)
        if sig_type != signal.type:
            logger.debug(f"[GraphConverter] Signal alias: '{signal.type}' → '{sig_type}'")
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
            # RSI: always force edge-triggered (cross_level) mode to prevent high-frequency signals.
            # Range mode fires 8-69% of bars → commission bleed. Cross mode fires only at threshold crossing.
            if sig_type == "RSI":
                oversold = float(params.get("oversold", params.get("cross_long_level", 30)))
                overbought = float(params.get("overbought", params.get("cross_short_level", 70)))
                params["use_cross_level"] = True
                params["cross_long_level"] = oversold
                params["cross_short_level"] = overbought
                # Clear range-mode flags so they don't interfere
                params.pop("use_long_range", None)
                params.pop("use_short_range", None)
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
            with contextlib.suppress(TypeError, ValueError):
                threshold_value = float(signal_params[threshold_key_name])

        cond_id = self._next_id("cond")

        if use_price_as_a:
            # VWAP-like compare: price vs indicator value.
            # "input"/"price" block types are not in BLOCK_REGISTRY — skip this path.
            # Callers should use Cat A (two_mas) instead of Cat B for VWAP.
            return None
        elif threshold_value is not None:
            # Use the actual condition block type (e.g. "greater_than", "less_than")
            # and embed the threshold in params["threshold_b"] — no constant block needed.
            new_blocks.append(
                {
                    "id": cond_id,
                    "type": condition_type,  # "greater_than" / "less_than" — in BLOCK_CATEGORY_MAP
                    "params": {"threshold_b": threshold_value},
                    "isMain": False,
                }
            )
            new_conns.append({"from": ind_id, "fromPort": out_port, "to": cond_id, "toPort": "a"})
        else:
            # No threshold — skip
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

        # Normalize filter type (apply aliases first)
        flt_type = _FILTER_TYPE_ALIASES.get(flt.type, flt.type)
        if flt_type != flt.type:
            logger.debug(f"[GraphConverter] Filter alias: '{flt.type}' → '{flt_type}'")
        cfg = _FILTER_BLOCK_MAP.get(flt_type)
        if cfg is None:
            if flt_type == "Time":
                warn.append("Time filter not supported as a block — skipped")
            else:
                warn.append(f"Unknown filter type '{flt.type}' — skipped")
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
            cond_type = cfg.get("condition_type", "greater_than")
            cond_id = self._next_id("cond")
            new_blocks.append(
                {
                    "id": cond_id,
                    "type": cond_type,  # actual type e.g. "greater_than" — in BLOCK_CATEGORY_MAP
                    "params": {"threshold_b": threshold},
                    "isMain": False,
                }
            )
            new_conns.append({"from": ind_id, "fromPort": "value", "to": cond_id, "toPort": "a"})
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
            for port, (src_id, src_port) in zip(ports, chunk, strict=False):
                new_conns.append({"from": src_id, "fromPort": src_port, "to": gate_id, "toPort": port})

            # The output of this gate becomes a new signal for the next round.
            # Use "result" (actual block output key) to avoid PortResolver fallback warnings.
            current_signals = [(gate_id, "result"), *remaining]

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
