"""
Unit tests for:
  backend/backtesting/strategy_builder/graph_parser.py
  backend/backtesting/strategy_builder/topology.py

These modules contain pure functions with no side-effects, so tests
are straightforward.
"""

from __future__ import annotations

from backend.backtesting.strategy_builder.graph_parser import (
    normalize_connections,
    parse_source_id,
    parse_source_port,
    parse_target_id,
    parse_target_port,
)
from backend.backtesting.strategy_builder.topology import (
    BLOCK_CATEGORY_MAP,
    build_execution_order,
    infer_category,
)

# ---------------------------------------------------------------------------
# graph_parser — parse_source_id
# ---------------------------------------------------------------------------


class TestParseSourceId:
    def test_nested_source_dict(self):
        conn = {"source": {"blockId": "block_1"}, "target": {}}
        assert parse_source_id(conn) == "block_1"

    def test_source_string(self):
        assert parse_source_id({"source": "block_2"}) == "block_2"

    def test_source_id_flat(self):
        assert parse_source_id({"source_id": "block_3"}) == "block_3"

    def test_source_block_key(self):
        assert parse_source_id({"source_block": "block_4"}) == "block_4"

    def test_from_key_fallback(self):
        assert parse_source_id({"from": "block_5"}) == "block_5"

    def test_empty_connection_returns_empty(self):
        assert parse_source_id({}) == ""


class TestParseTargetId:
    def test_nested_target_dict(self):
        conn = {"target": {"blockId": "t_1"}}
        assert parse_target_id(conn) == "t_1"

    def test_target_string(self):
        assert parse_target_id({"target": "t_2"}) == "t_2"

    def test_target_id_flat(self):
        assert parse_target_id({"target_id": "t_3"}) == "t_3"

    def test_to_key_fallback(self):
        assert parse_target_id({"to": "t_4"}) == "t_4"


class TestParseSourcePort:
    def test_nested_source_portid(self):
        conn = {"source": {"portId": "long"}}
        assert parse_source_port(conn) == "long"

    def test_nested_source_missing_portid_returns_empty(self):
        # Bug #6 fix: missing portId should NOT default to "value"
        conn = {"source": {}}
        assert parse_source_port(conn) == ""

    def test_source_port_flat(self):
        assert parse_source_port({"source_port": "output"}) == "output"

    def test_source_output_key(self):
        assert parse_source_port({"source_output": "signal"}) == "signal"

    def test_camelcase_sourceport(self):
        assert parse_source_port({"sourcePort": "value"}) == "value"

    def test_fromport_fallback(self):
        assert parse_source_port({"fromPort": "bullish"}) == "bullish"


class TestParseTargetPort:
    def test_nested_target_portid(self):
        conn = {"target": {"portId": "entry_long"}}
        assert parse_target_port(conn) == "entry_long"

    def test_nested_target_missing_portid_returns_empty(self):
        conn = {"target": {}}
        assert parse_target_port(conn) == ""

    def test_target_port_flat(self):
        assert parse_target_port({"target_port": "exit_long"}) == "exit_long"

    def test_toport_fallback(self):
        assert parse_target_port({"toPort": "entry_short"}) == "entry_short"


# ---------------------------------------------------------------------------
# graph_parser — normalize_connections
# ---------------------------------------------------------------------------


class TestNormalizeConnections:
    def test_empty_list(self):
        assert normalize_connections([]) == []

    def test_normalizes_flat_format(self):
        raw = [{"source_id": "a", "target_id": "b", "source_port": "long", "target_port": "entry_long"}]
        result = normalize_connections(raw)
        assert result == [{"source_id": "a", "target_id": "b", "source_port": "long", "target_port": "entry_long"}]

    def test_normalizes_nested_format(self):
        raw = [
            {
                "source": {"blockId": "rsi_1", "portId": "long"},
                "target": {"blockId": "strat_node", "portId": "entry_long"},
            }
        ]
        result = normalize_connections(raw)
        assert result[0]["source_id"] == "rsi_1"
        assert result[0]["target_id"] == "strat_node"
        assert result[0]["source_port"] == "long"
        assert result[0]["target_port"] == "entry_long"

    def test_normalizes_from_to_format(self):
        raw = [{"from": "a", "to": "b", "fromPort": "out", "toPort": "in"}]
        result = normalize_connections(raw)
        assert result[0] == {"source_id": "a", "target_id": "b", "source_port": "out", "target_port": "in"}

    def test_output_keys_always_canonical(self):
        raw = [{"source_id": "x", "target_id": "y", "source_port": "p", "target_port": "q"}]
        r = normalize_connections(raw)[0]
        assert set(r.keys()) == {"source_id", "target_id", "source_port", "target_port"}


# ---------------------------------------------------------------------------
# topology — infer_category
# ---------------------------------------------------------------------------


class TestInferCategory:
    def test_known_indicator(self):
        assert infer_category("rsi") == "indicator"
        assert infer_category("ema") == "indicator"
        assert infer_category("macd") == "indicator"

    def test_known_condition(self):
        assert infer_category("crossover") == "condition"
        assert infer_category("greater_than") == "condition"

    def test_known_action(self):
        assert infer_category("buy") == "action"
        assert infer_category("stop_loss") == "action"

    def test_known_strategy(self):
        assert infer_category("strategy") == "strategy"

    def test_known_filter(self):
        assert infer_category("rsi_filter") == "filter"

    def test_prefix_heuristic_indicator(self):
        assert infer_category("indicator_custom") == "indicator"

    def test_prefix_heuristic_condition(self):
        assert infer_category("condition_custom") == "condition"

    def test_unknown_falls_back_to_indicator(self):
        assert infer_category("completely_unknown_xyz") == "indicator"

    def test_close_conditions(self):
        assert infer_category("close_by_time") == "close_conditions"
        assert infer_category("close_rsi") == "close_conditions"


class TestBlockCategoryMap:
    def test_map_is_not_empty(self):
        assert len(BLOCK_CATEGORY_MAP) > 50

    def test_all_values_are_strings(self):
        assert all(isinstance(v, str) for v in BLOCK_CATEGORY_MAP.values())

    def test_divergence_present(self):
        assert BLOCK_CATEGORY_MAP.get("divergence") == "divergence"

    def test_dca_present(self):
        assert BLOCK_CATEGORY_MAP.get("dca") == "dca_grid"


# ---------------------------------------------------------------------------
# topology — build_execution_order
# ---------------------------------------------------------------------------


class TestBuildExecutionOrder:
    def _make_blocks(self, *ids: str) -> dict:
        return {bid: {"type": "rsi", "id": bid} for bid in ids}

    def _conn(self, src: str, tgt: str) -> dict:
        return {"source_id": src, "target_id": tgt, "source_port": "long", "target_port": "entry_long"}

    def test_single_block_no_connections(self):
        blocks = self._make_blocks("a")
        order = build_execution_order(blocks, [])
        assert order == ["a"]

    def test_linear_chain(self):
        # a → b → c
        blocks = self._make_blocks("a", "b", "c")
        conns = [self._conn("a", "b"), self._conn("b", "c")]
        order = build_execution_order(blocks, conns)
        assert order.index("a") < order.index("b") < order.index("c")

    def test_parallel_sources(self):
        # a → c, b → c
        blocks = self._make_blocks("a", "b", "c")
        conns = [self._conn("a", "c"), self._conn("b", "c")]
        order = build_execution_order(blocks, conns)
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("c")

    def test_all_blocks_included(self):
        # disconnected block "d" must still appear
        blocks = self._make_blocks("a", "b", "d")
        conns = [self._conn("a", "b")]
        order = build_execution_order(blocks, conns)
        assert set(order) == {"a", "b", "d"}

    def test_empty_graph(self):
        assert build_execution_order({}, []) == []

    def test_cycle_still_includes_all_blocks(self):
        # a → b → a (cycle)
        blocks = self._make_blocks("a", "b")
        conns = [self._conn("a", "b"), self._conn("b", "a")]
        order = build_execution_order(blocks, conns)
        assert set(order) == {"a", "b"}
