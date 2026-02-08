"""
Tests for Strategy Builder validation improvements

Tests enhanced validation including:
- Entry signals to main strategy node
- Port type compatibility
- Parameter range validation
"""

import pytest

from backend.services.strategy_builder.builder import (
    BlockConnection,
    BlockInput,
    BlockOutput,
    BlockType,
    ConnectionType,
    StrategyBlock,
    StrategyBuilder,
    StrategyGraph,
)
from backend.services.strategy_builder.validator import (
    StrategyValidator,
    ValidationSeverity,
)


@pytest.fixture
def validator():
    """Create validator instance"""
    return StrategyValidator()


@pytest.fixture
def empty_graph():
    """Create empty graph"""
    return StrategyGraph(
        id="test",
        name="Test Strategy",
        description="",
        timeframe="1h",
        symbols=["BTCUSDT"],
    )


@pytest.fixture
def graph_without_entry_signals():
    """Create graph without entry signals to main node"""
    graph = StrategyGraph(
        id="test",
        name="Test Strategy",
        description="",
        timeframe="1h",
        symbols=["BTCUSDT"],
    )

    # Add price block
    price_block = StrategyBlock(
        id="price",
        block_type=BlockType.CANDLE_DATA,
        name="Price",
        position_x=100,
        position_y=100,
    )
    graph.add_block(price_block)

    # Add RSI block
    rsi_block = StrategyBlock(
        id="rsi",
        block_type=BlockType.INDICATOR_RSI,
        name="RSI",
        position_x=300,
        position_y=100,
        parameters={"period": 14},
    )
    graph.add_block(rsi_block)

    # Add main strategy node
    main_block = StrategyBlock(
        id="main",
        block_type=BlockType.OUTPUT_SIGNAL,
        name="Strategy",
        position_x=500,
        position_y=100,
    )
    main_block.isMain = True  # Mark as main node
    graph.add_block(main_block)

    # Connect price to RSI (but not to main node)
    conn = BlockConnection(
        id="conn1",
        source_block_id="price",
        source_output="close",
        target_block_id="rsi",
        target_input="source",
        connection_type=ConnectionType.DATA_FLOW,
    )
    graph.connections.append(conn)

    return graph


@pytest.fixture
def valid_graph():
    """Create valid graph with entry signals"""
    builder = StrategyBuilder()
    graph = StrategyGraph(
        id="test",
        name="Test Strategy",
        description="",
        timeframe="1h",
        symbols=["BTCUSDT"],
    )

    # Add price block using builder (to get proper inputs/outputs)
    price_block = builder.add_block(
        graph,
        BlockType.CANDLE_DATA,
        x=100,
        y=100,
    )
    price_block.id = "price"  # Set fixed ID for testing
    price_block.name = "Price"

    # Add RSI block
    rsi_block = builder.add_block(
        graph,
        BlockType.INDICATOR_RSI,
        x=300,
        y=100,
        parameters={"period": 14},
    )
    rsi_block.id = "rsi"
    rsi_block.name = "RSI"

    # Add constant block (using CANDLE_DATA as workaround)
    const_block = builder.add_block(
        graph,
        BlockType.CANDLE_DATA,
        x=100,
        y=200,
    )
    const_block.id = "const"
    const_block.name = "Constant 30"
    # Add value output for constant
    const_block.outputs.append(BlockOutput(name="value", data_type="float"))

    # Add less than condition
    lt_block = builder.add_block(
        graph,
        BlockType.CONDITION_COMPARE,
        x=500,
        y=150,
    )
    lt_block.id = "less_than"
    lt_block.name = "Less Than"

    # Add main strategy node
    main_block = builder.add_block(
        graph,
        BlockType.OUTPUT_SIGNAL,
        x=700,
        y=150,
    )
    main_block.id = "main"
    main_block.name = "Strategy"
    main_block.isMain = True
    # Replace default "signal" input with entry_long/entry_short for main strategy node
    main_block.inputs = [
        BlockInput(name="entry_long", data_type="bool", required=False),
        BlockInput(name="entry_short", data_type="bool", required=False),
        BlockInput(name="exit_long", data_type="bool", required=False),
        BlockInput(name="exit_short", data_type="bool", required=False),
    ]

    # Update graph.blocks dict with fixed IDs (builder creates new blocks with UUIDs)
    graph.blocks = {
        "price": price_block,
        "rsi": rsi_block,
        "const": const_block,
        "less_than": lt_block,
        "main": main_block,
    }

    # Connect blocks using fixed IDs
    conn1 = BlockConnection(
        id="conn1",
        source_block_id="price",
        source_output="close",
        target_block_id="rsi",
        target_input="source",
        connection_type=ConnectionType.DATA_FLOW,
    )
    graph.connections.append(conn1)

    conn2 = BlockConnection(
        id="conn2",
        source_block_id="rsi",
        source_output="rsi",
        target_block_id="less_than",
        target_input="left",  # CONDITION_COMPARE uses "left" and "right", not "a" and "b"
        connection_type=ConnectionType.DATA_FLOW,
    )
    graph.connections.append(conn2)

    conn3 = BlockConnection(
        id="conn3",
        source_block_id="const",
        source_output="value",
        target_block_id="less_than",
        target_input="right",
        connection_type=ConnectionType.DATA_FLOW,
    )
    graph.connections.append(conn3)

    # Connect condition to main node entry_long
    conn4 = BlockConnection(
        id="conn4",
        source_block_id="less_than",
        source_output="result",
        target_block_id="main",
        target_input="entry_long",
        connection_type=ConnectionType.DATA_FLOW,
    )
    graph.connections.append(conn4)

    return graph


class TestStrategyValidation:
    """Tests for strategy validation"""

    def test_empty_graph_validation(self, validator, empty_graph):
        """Test validation of empty graph"""
        result = validator.validate(empty_graph)

        assert not result.is_valid, "Empty graph should be invalid"
        assert len(result.errors) > 0, "Should have validation errors"
        assert any(
            e.code == "EMPTY_GRAPH" for e in result.errors
        ), "Should have EMPTY_GRAPH error"

    def test_no_entry_signals_validation(self, validator, graph_without_entry_signals):
        """Test validation when main node has no entry signals"""
        result = validator.validate(graph_without_entry_signals)

        assert not result.is_valid, "Graph without entry signals should be invalid"
        assert any(
            e.code == "NO_ENTRY_SIGNALS" for e in result.errors
        ), "Should have NO_ENTRY_SIGNALS error"

    def test_valid_graph_validation(self, validator, valid_graph):
        """Test validation of valid graph"""
        result = validator.validate(valid_graph)

        if not result.is_valid:
            error_messages = [f"{e.code}: {e.message}" for e in result.errors if e.severity == ValidationSeverity.ERROR]
            pytest.fail(f"Validation failed with errors: {error_messages}")

        assert result.is_valid, "Valid graph should pass validation"
        assert (
            len([e for e in result.errors if e.severity == ValidationSeverity.ERROR])
            == 0
        ), f"Should have no errors, but got: {[e.message for e in result.errors if e.severity == ValidationSeverity.ERROR]}"

    def test_parameter_validation(self, validator):
        """Test parameter range validation"""
        graph = StrategyGraph(
            id="test",
            name="Test",
            description="",
            timeframe="1h",
            symbols=["BTCUSDT"],
        )

        # Add RSI with invalid period (negative)
        rsi_block = StrategyBlock(
            id="rsi",
            block_type=BlockType.INDICATOR_RSI,
            name="RSI",
            position_x=100,
            position_y=100,
            parameters={"period": -5},  # Invalid: negative
        )
        graph.add_block(rsi_block)

        result = validator.validate(graph)

        # Should have parameter validation errors/warnings
        assert len(result.errors) > 0 or len(result.warnings) > 0
