"""
Unit tests for StrategyDefToGraphConverter.

Tests cover:
- Category A signals (RSI, MACD, Stochastic, SuperTrend, EMA_Crossover, SMA_Crossover, EMA, SMA)
- Category B signals (CCI, Williams_R, Bollinger, ADX, VWAP, OBV, ATR)
- Filter blocks (Volatility, Volume, Trend, ADX, Time)
- Signal combining (AND/OR, 1/2/3/4+ signals)
- Param renaming (Two MAs fast_period → ma1_length)
- Mode activation flags
- Strategy node presence (isMain=True)
- Graph structure integrity
"""

from __future__ import annotations

from backend.agents.integration.graph_converter import StrategyDefToGraphConverter
from backend.agents.prompts.response_parser import (
    EntryConditions,
    Filter,
    Signal,
    StrategyDefinition,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_strategy(
    signals: list[Signal],
    filters: list[Filter] | None = None,
    logic: str = "AND",
    name: str = "Test Strategy",
) -> StrategyDefinition:
    return StrategyDefinition(
        strategy_name=name,
        signals=signals,
        filters=filters or [],
        entry_conditions=EntryConditions(logic=logic),
    )


def _blocks_by_type(graph: dict, btype: str) -> list[dict]:
    return [b for b in graph["blocks"] if b["type"] == btype]


def _block_by_id(graph: dict, bid: str) -> dict | None:
    return next((b for b in graph["blocks"] if b["id"] == bid), None)


def _conns_to(graph: dict, target_id: str) -> list[dict]:
    return [c for c in graph["connections"] if c["to"] == target_id]


def _conns_from(graph: dict, source_id: str) -> list[dict]:
    return [c for c in graph["connections"] if c["from"] == source_id]


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


def test_graph_has_strategy_node():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="RSI", params={"period": 14})])
    graph, _ = conv.convert(strat, interval="15")

    assert graph["interval"] == "15"
    strategy_nodes = [b for b in graph["blocks"] if b.get("isMain")]
    assert len(strategy_nodes) == 1
    assert strategy_nodes[0]["type"] == "strategy"


def test_graph_name_and_interval():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        [Signal(id="s1", type="MACD", params={})],
        name="My MACD Strategy",
    )
    graph, _ = conv.convert(strat, interval="60")
    assert graph["name"] == "My MACD Strategy"
    assert graph["interval"] == "60"


# ---------------------------------------------------------------------------
# Category A — direct long/short
# ---------------------------------------------------------------------------


def test_rsi_legacy_mode():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="RSI", params={"period": 14, "oversold": 30, "overbought": 70})])
    graph, warnings = conv.convert(strat)

    rsi_blocks = _blocks_by_type(graph, "rsi")
    assert len(rsi_blocks) == 1
    params = rsi_blocks[0]["params"]
    assert params["period"] == 14
    assert params["oversold"] == 30
    assert params["overbought"] == 70
    # No unexpected activation warnings
    assert not warnings


def test_rsi_defaults_when_no_params():
    """RSI without oversold/overbought should get defaults injected."""
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="RSI", params={})])
    graph, _ = conv.convert(strat)

    rsi_block = _blocks_by_type(graph, "rsi")[0]
    assert "oversold" in rsi_block["params"]
    assert "overbought" in rsi_block["params"]


def test_macd_activation_flag():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="MACD", params={"fast_period": 12, "slow_period": 26})])
    graph, _ = conv.convert(strat)

    macd_block = _blocks_by_type(graph, "macd")[0]
    assert macd_block["params"]["use_macd_cross_signal"] is True


def test_stochastic_param_rename_and_activation():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="Stochastic", params={"k_period": 14, "d_period": 3, "smooth": 3})])
    graph, _ = conv.convert(strat)

    stoch = _blocks_by_type(graph, "stochastic")[0]
    assert stoch["params"]["stoch_k_length"] == 14
    assert stoch["params"]["stoch_d_smoothing"] == 3
    assert stoch["params"]["stoch_k_smoothing"] == 3
    assert stoch["params"]["use_stoch_kd_cross"] is True


def test_supertrend_activation():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="SuperTrend", params={"period": 10, "multiplier": 3.0})])
    graph, _ = conv.convert(strat)

    st = _blocks_by_type(graph, "supertrend")[0]
    assert st["params"]["use_supertrend"] is True
    assert st["params"]["period"] == 10


def test_ema_crossover_maps_to_two_mas():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="EMA_Crossover", params={"fast_period": 9, "slow_period": 21})])
    graph, _ = conv.convert(strat)

    tm = _blocks_by_type(graph, "two_mas")[0]
    assert tm["params"]["ma1_length"] == 9
    assert tm["params"]["ma2_length"] == 21
    assert tm["params"]["ma1_smoothing"] == "EMA"
    assert tm["params"]["use_ma_cross"] is True


def test_sma_crossover_maps_to_two_mas():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="SMA_Crossover", params={"fast_period": 10, "slow_period": 30})])
    graph, _ = conv.convert(strat)

    tm = _blocks_by_type(graph, "two_mas")[0]
    assert tm["params"]["ma1_smoothing"] == "SMA"
    assert tm["params"]["use_ma_cross"] is True


def test_ema_single_maps_to_ma1_filter():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="EMA", params={"period": 50})])
    graph, _ = conv.convert(strat)

    tm = _blocks_by_type(graph, "two_mas")[0]
    assert tm["params"]["ma1_length"] == 50
    assert tm["params"]["use_ma1_filter"] is True
    assert tm["params"].get("use_ma_cross") is not True


def test_sma_single_maps_to_ma1_filter():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="SMA", params={"period": 20})])
    graph, _ = conv.convert(strat)

    tm = _blocks_by_type(graph, "two_mas")[0]
    assert tm["params"]["ma1_smoothing"] == "SMA"
    assert tm["params"]["use_ma1_filter"] is True


# ---------------------------------------------------------------------------
# Category B — condition block wrapping
# ---------------------------------------------------------------------------


def test_cci_generates_condition_blocks():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="CCI", params={"period": 20, "oversold": -100, "overbought": 100})])
    graph, warnings = conv.convert(strat)

    assert _blocks_by_type(graph, "cci"), "CCI indicator block missing"
    # Condition blocks use operation-specific types: "less_than" (long) and "greater_than" (short)
    long_conds = _blocks_by_type(graph, "less_than")
    short_conds = _blocks_by_type(graph, "greater_than")
    assert len(long_conds) == 1, "Expected 1 'less_than' condition block for CCI long"
    assert len(short_conds) == 1, "Expected 1 'greater_than' condition block for CCI short"
    assert any("CCI" in w for w in warnings)


def test_williams_r_generates_condition_blocks():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="Williams_R", params={"period": 14})])
    graph, _ = conv.convert(strat)

    assert _blocks_by_type(graph, "williams_r")
    # Condition blocks use operation-specific types: "less_than" (long) and "greater_than" (short)
    assert len(_blocks_by_type(graph, "less_than")) == 1
    assert len(_blocks_by_type(graph, "greater_than")) == 1


def test_bollinger_generates_condition_blocks_with_price_input():
    """Bollinger is now Cat A via keltner_bollinger — direct long/short output."""
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="Bollinger", params={"period": 20, "std_dev": 2.0})])
    graph, _ = conv.convert(strat)

    # Should produce a keltner_bollinger block (Cat A), not condition/input blocks
    kb_blocks = _blocks_by_type(graph, "keltner_bollinger")
    assert len(kb_blocks) == 1, "Expected keltner_bollinger block for Bollinger"
    params = kb_blocks[0]["params"]
    assert params.get("channel_type") == "Bollinger Bands"
    assert params.get("use_channel") is True
    assert params.get("bb_length") == 20
    assert params.get("bb_deviation") == 2.0


def test_unknown_signal_type_skipped_with_warning():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="RSI", params={})])
    # Manually inject unknown after construction
    strat.signals[0].type = "FakeIndicator"  # type: ignore[assignment]
    graph, warnings = conv.convert(strat)

    assert any("FakeIndicator" in w for w in warnings)
    # Only strategy_node should be in blocks (no signal blocks added)
    assert len([b for b in graph["blocks"] if b["type"] != "strategy"]) == 0


# ---------------------------------------------------------------------------
# Signal combining — AND / OR logic
# ---------------------------------------------------------------------------


def test_single_signal_direct_connection():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="RSI", params={"period": 14})])
    graph, _ = conv.convert(strat)

    # Connection: rsi → strategy_node (entry_long)
    conns_to_strategy = _conns_to(graph, "strategy_node")
    entry_long_conns = [c for c in conns_to_strategy if c["toPort"] == "entry_long"]
    assert len(entry_long_conns) == 1
    # Should be direct, no and/or gate
    assert not _blocks_by_type(graph, "and")
    assert not _blocks_by_type(graph, "or")


def test_two_signals_and_creates_and_gate():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        [
            Signal(id="s1", type="RSI", params={"period": 14}),
            Signal(id="s2", type="MACD", params={}),
        ],
        logic="AND",
    )
    graph, _ = conv.convert(strat)

    and_blocks = _blocks_by_type(graph, "and")
    assert len(and_blocks) >= 1
    # and block must connect to strategy_node
    and_id = and_blocks[0]["id"]
    assert any(c["from"] == and_id and c["to"] == "strategy_node" for c in graph["connections"])


def test_two_signals_or_creates_or_gate():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        [
            Signal(id="s1", type="RSI", params={}),
            Signal(id="s2", type="SuperTrend", params={}),
        ],
        logic="OR",
    )
    graph, _ = conv.convert(strat)

    or_blocks = _blocks_by_type(graph, "or")
    assert len(or_blocks) >= 1


def test_three_signals_single_and_gate_with_port_c():
    """Three signals should fit in one and-block per direction (ports a, b, c).

    The converter creates separate AND gates for long and short paths,
    so 3 Cat-A signals → 2 and-gates total (and_long + and_short).
    """
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        [
            Signal(id="s1", type="RSI", params={}),
            Signal(id="s2", type="MACD", params={}),
            Signal(id="s3", type="SuperTrend", params={}),
        ],
        logic="AND",
    )
    graph, _ = conv.convert(strat)

    and_blocks = _blocks_by_type(graph, "and")
    # One gate per direction (long + short) = 2 total
    assert len(and_blocks) == 2
    # Each gate should consume all 3 ports (a, b, c)
    for gate in and_blocks:
        ports_used = {c["toPort"] for c in _conns_to(graph, gate["id"])}
        assert ports_used == {"a", "b", "c"}, f"Gate {gate['id']} ports: {ports_used}"


def test_four_signals_chains_two_and_gates():
    """4 signals: and1(a,b,c) + signal4 → and2(a,b) per direction.

    The converter creates separate AND gate chains for long and short:
    - long:  and_long_1(RSI, MACD, ST) → and_long_2(output, Stoch) → entry_long
    - short: and_short_3(RSI, MACD, ST) → and_short_4(output, Stoch) → entry_short
    Total: 4 and-blocks (2 per direction).
    """
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        [
            Signal(id="s1", type="RSI", params={}),
            Signal(id="s2", type="MACD", params={}),
            Signal(id="s3", type="SuperTrend", params={}),
            Signal(id="s4", type="Stochastic", params={}),
        ],
        logic="AND",
    )
    graph, _ = conv.convert(strat)

    and_blocks = _blocks_by_type(graph, "and")
    # 2 gate stages × 2 directions = 4 and-blocks
    assert len(and_blocks) == 4


# ---------------------------------------------------------------------------
# Filter blocks
# ---------------------------------------------------------------------------


def test_volatility_filter_maps_to_atr_volatility():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        signals=[Signal(id="s1", type="RSI", params={})],
        filters=[Filter(id="f1", type="Volatility", params={"atr_fast": 10, "atr_slow": 50})],
    )
    graph, _ = conv.convert(strat)

    assert _blocks_by_type(graph, "atr_volatility")
    atv = _blocks_by_type(graph, "atr_volatility")[0]
    assert atv["params"]["atr_length1"] == 10
    assert atv["params"]["atr_length2"] == 50
    assert atv["params"]["use_atr_volatility"] is True


def test_volume_filter_maps_to_volume_filter_block():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        signals=[Signal(id="s1", type="RSI", params={})],
        filters=[Filter(id="f1", type="Volume", params={})],
    )
    graph, _ = conv.convert(strat)

    assert _blocks_by_type(graph, "volume_filter")
    vf = _blocks_by_type(graph, "volume_filter")[0]
    assert vf["params"]["use_volume_filter"] is True


def test_trend_filter_maps_to_two_mas_ma1_filter():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        signals=[Signal(id="s1", type="RSI", params={})],
        filters=[Filter(id="f1", type="Trend", params={"period": 50})],
    )
    graph, _ = conv.convert(strat)

    two_mas_blocks = _blocks_by_type(graph, "two_mas")
    assert two_mas_blocks
    assert any(b["params"].get("use_ma1_filter") for b in two_mas_blocks)


def test_time_filter_skipped_with_warning():
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        signals=[Signal(id="s1", type="RSI", params={})],
        filters=[Filter(id="f1", type="Time", params={})],
    )
    graph, warnings = conv.convert(strat)

    assert any("Time" in w for w in warnings)


# ---------------------------------------------------------------------------
# Graph integrity checks
# ---------------------------------------------------------------------------


def test_all_connections_reference_valid_blocks():
    """Every connection source/target must be a known block id."""
    conv = StrategyDefToGraphConverter()
    strat = make_strategy(
        [
            Signal(id="s1", type="RSI", params={}),
            Signal(id="s2", type="MACD", params={}),
        ],
        filters=[Filter(id="f1", type="Volume", params={})],
    )
    graph, _ = conv.convert(strat)

    block_ids = {b["id"] for b in graph["blocks"]}
    for conn in graph["connections"]:
        assert conn["from"] in block_ids, f"Connection source '{conn['from']}' not a valid block"
        assert conn["to"] in block_ids, f"Connection target '{conn['to']}' not a valid block"


def test_converter_is_stateless_across_calls():
    """Multiple convert() calls should produce independent id counters."""
    conv = StrategyDefToGraphConverter()
    strat = make_strategy([Signal(id="s1", type="RSI", params={})])

    graph1, _ = conv.convert(strat)
    graph2, _ = conv.convert(strat)

    # Both should have the same structure
    assert len(graph1["blocks"]) == len(graph2["blocks"])
    # IDs should be the same (counter resets each call)
    ids1 = {b["id"] for b in graph1["blocks"]}
    ids2 = {b["id"] for b in graph2["blocks"]}
    assert ids1 == ids2
