"""
Visual Strategy Builder

Block-based strategy composition system that allows users to
visually construct trading strategies by connecting blocks.

Block Types:
- Data Sources (candles, orderbook, trades)
- Indicators (RSI, MACD, Bollinger, custom)
- Conditions (comparisons, logical operators)
- Actions (buy, sell, set stop-loss)
- Filters (time, volume, volatility)
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class BlockType(Enum):
    """Types of blocks in strategy builder"""

    # Data Sources
    CANDLE_DATA = "candle_data"
    ORDERBOOK_DATA = "orderbook_data"
    TRADE_DATA = "trade_data"
    EXTERNAL_DATA = "external_data"

    # Indicators
    INDICATOR_RSI = "indicator_rsi"
    INDICATOR_MACD = "indicator_macd"
    INDICATOR_BOLLINGER = "indicator_bollinger"
    INDICATOR_SMA = "indicator_sma"
    INDICATOR_EMA = "indicator_ema"
    INDICATOR_ATR = "indicator_atr"
    INDICATOR_STOCHASTIC = "indicator_stochastic"
    INDICATOR_ADX = "indicator_adx"
    INDICATOR_CUSTOM = "indicator_custom"

    # Conditions
    CONDITION_COMPARE = "condition_compare"
    CONDITION_CROSS = "condition_cross"
    CONDITION_THRESHOLD = "condition_threshold"
    CONDITION_RANGE = "condition_range"
    CONDITION_AND = "condition_and"
    CONDITION_OR = "condition_or"
    CONDITION_NOT = "condition_not"

    # Actions
    ACTION_BUY = "action_buy"
    ACTION_SELL = "action_sell"
    ACTION_CLOSE = "action_close"
    ACTION_SET_STOP_LOSS = "action_set_stop_loss"
    ACTION_SET_TAKE_PROFIT = "action_set_take_profit"
    ACTION_TRAILING_STOP = "action_trailing_stop"
    ACTION_SCALE_IN = "action_scale_in"
    ACTION_SCALE_OUT = "action_scale_out"

    # Filters
    FILTER_TIME = "filter_time"
    FILTER_VOLUME = "filter_volume"
    FILTER_TREND = "filter_trend"
    FILTER_LIQUIDITY = "filter_liquidity"

    # Risk Management
    RISK_POSITION_SIZE = "risk_position_size"
    RISK_MAX_DRAWDOWN = "risk_max_drawdown"
    RISK_DAILY_LIMIT = "risk_daily_limit"
    RISK_CORRELATION = "risk_correlation"

    # Output
    OUTPUT_SIGNAL = "output_signal"
    OUTPUT_LOG = "output_log"
    OUTPUT_ALERT = "output_alert"


class ConnectionType(Enum):
    """Types of connections between blocks"""

    DATA_FLOW = "data_flow"  # Data passes from one block to another
    CONDITION = "condition"  # Conditional connection (if true)
    TRIGGER = "trigger"  # Event trigger
    PARAMETER = "parameter"  # Parameter binding


@dataclass
class BlockInput:
    """Input port for a block"""

    name: str
    data_type: str  # "float", "bool", "series", "candle", "signal"
    required: bool = True
    description: str = ""
    default_value: Any = None


@dataclass
class BlockOutput:
    """Output port for a block"""

    name: str
    data_type: str
    description: str = ""


@dataclass
class BlockParameter:
    """Configurable parameter for a block"""

    name: str
    param_type: str  # "int", "float", "bool", "string", "choice"
    default: Any
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[List[Any]] = None
    step: Optional[float] = None


@dataclass
class StrategyBlock:
    """
    A single block in the strategy builder

    Blocks are the building blocks of a visual strategy.
    Each block has inputs, outputs, and parameters.
    """

    id: str
    block_type: BlockType
    name: str

    # Position in visual editor
    position_x: float = 0
    position_y: float = 0

    # Configuration
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Ports (defined by block type)
    inputs: List[BlockInput] = field(default_factory=list)
    outputs: List[BlockOutput] = field(default_factory=list)

    # Custom code (for custom blocks)
    custom_code: Optional[str] = None

    # Metadata
    color: str = "#4CAF50"
    icon: str = "block"
    description: str = ""
    enabled: bool = True

    # Validation
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "block_type": self.block_type.value,
            "name": self.name,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "parameters": self.parameters,
            "inputs": [
                {"name": i.name, "data_type": i.data_type, "required": i.required}
                for i in self.inputs
            ],
            "outputs": [
                {"name": o.name, "data_type": o.data_type} for o in self.outputs
            ],
            "custom_code": self.custom_code,
            "color": self.color,
            "icon": self.icon,
            "description": self.description,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyBlock":
        """Create from dictionary"""
        inputs = [BlockInput(**i) for i in data.get("inputs", [])]
        outputs = [BlockOutput(**o) for o in data.get("outputs", [])]

        return cls(
            id=data["id"],
            block_type=BlockType(data["block_type"]),
            name=data["name"],
            position_x=data.get("position_x", 0),
            position_y=data.get("position_y", 0),
            parameters=data.get("parameters", {}),
            inputs=inputs,
            outputs=outputs,
            custom_code=data.get("custom_code"),
            color=data.get("color", "#4CAF50"),
            icon=data.get("icon", "block"),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
        )


@dataclass
class BlockConnection:
    """Connection between two blocks"""

    id: str
    source_block_id: str
    source_output: str
    target_block_id: str
    target_input: str
    connection_type: ConnectionType = ConnectionType.DATA_FLOW

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "source_block_id": self.source_block_id,
            "source_output": self.source_output,
            "target_block_id": self.target_block_id,
            "target_input": self.target_input,
            "connection_type": self.connection_type.value,
        }


@dataclass
class StrategyGraph:
    """
    Graph representation of a visual strategy

    Contains blocks and their connections.
    """

    id: str
    name: str
    description: str = ""

    # Graph structure
    blocks: Dict[str, StrategyBlock] = field(default_factory=dict)
    connections: List[BlockConnection] = field(default_factory=list)

    # Metadata
    version: str = "1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    author: str = ""
    tags: List[str] = field(default_factory=list)

    # Settings
    timeframe: str = "1h"
    symbols: List[str] = field(default_factory=list)

    def add_block(self, block: StrategyBlock) -> None:
        """Add a block to the graph"""
        self.blocks[block.id] = block
        self.updated_at = datetime.now(timezone.utc)

    def remove_block(self, block_id: str) -> bool:
        """Remove a block and its connections"""
        if block_id not in self.blocks:
            return False

        del self.blocks[block_id]

        # Remove connections to/from this block
        self.connections = [
            c
            for c in self.connections
            if c.source_block_id != block_id and c.target_block_id != block_id
        ]

        self.updated_at = datetime.now(timezone.utc)
        return True

    def connect(
        self,
        source_id: str,
        source_output: str,
        target_id: str,
        target_input: str,
        connection_type: ConnectionType = ConnectionType.DATA_FLOW,
    ) -> BlockConnection:
        """Connect two blocks"""
        connection = BlockConnection(
            id=str(uuid.uuid4()),
            source_block_id=source_id,
            source_output=source_output,
            target_block_id=target_id,
            target_input=target_input,
            connection_type=connection_type,
        )
        self.connections.append(connection)
        self.updated_at = datetime.now(timezone.utc)
        return connection

    def disconnect(self, connection_id: str) -> bool:
        """Remove a connection"""
        for i, conn in enumerate(self.connections):
            if conn.id == connection_id:
                del self.connections[i]
                self.updated_at = datetime.now(timezone.utc)
                return True
        return False

    def get_execution_order(self) -> List[str]:
        """Get topologically sorted execution order"""
        # Build adjacency list
        graph: Dict[str, Set[str]] = {block_id: set() for block_id in self.blocks}
        in_degree: Dict[str, int] = {block_id: 0 for block_id in self.blocks}

        for conn in self.connections:
            if conn.source_block_id in graph and conn.target_block_id in graph:
                graph[conn.source_block_id].add(conn.target_block_id)
                in_degree[conn.target_block_id] += 1

        # Kahn's algorithm
        queue = [bid for bid, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)

            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.blocks):
            raise ValueError("Graph contains a cycle")

        return order

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "blocks": {bid: block.to_dict() for bid, block in self.blocks.items()},
            "connections": [c.to_dict() for c in self.connections],
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "author": self.author,
            "tags": self.tags,
            "timeframe": self.timeframe,
            "symbols": self.symbols,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyGraph":
        """Create from dictionary"""
        blocks = {
            bid: StrategyBlock.from_dict(bdata)
            for bid, bdata in data.get("blocks", {}).items()
        }

        connections = [
            BlockConnection(
                id=c["id"],
                source_block_id=c["source_block_id"],
                source_output=c["source_output"],
                target_block_id=c["target_block_id"],
                target_input=c["target_input"],
                connection_type=ConnectionType(c.get("connection_type", "data_flow")),
            )
            for c in data.get("connections", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            blocks=blocks,
            connections=connections,
            version=data.get("version", "1.0"),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(timezone.utc),
            author=data.get("author", ""),
            tags=data.get("tags", []),
            timeframe=data.get("timeframe", "1h"),
            symbols=data.get("symbols", []),
        )


# Block Factory - Creates blocks with proper inputs/outputs
BLOCK_DEFINITIONS: Dict[BlockType, Dict[str, Any]] = {
    # Data Sources
    BlockType.CANDLE_DATA: {
        "name": "Candle Data",
        "color": "#2196F3",
        "icon": "candlestick_chart",
        "inputs": [],
        "outputs": [
            {"name": "open", "data_type": "series"},
            {"name": "high", "data_type": "series"},
            {"name": "low", "data_type": "series"},
            {"name": "close", "data_type": "series"},
            {"name": "volume", "data_type": "series"},
        ],
        "parameters": [
            {"name": "symbol", "param_type": "string", "default": "BTCUSDT"},
            {
                "name": "timeframe",
                "param_type": "choice",
                "default": "1h",
                "choices": ["1m", "5m", "15m", "1h", "4h", "1d"],
            },
            {
                "name": "limit",
                "param_type": "int",
                "default": 100,
                "min_value": 10,
                "max_value": 1000,
            },
        ],
    },
    # Indicators
    BlockType.INDICATOR_RSI: {
        "name": "RSI",
        "color": "#9C27B0",
        "icon": "trending_up",
        "inputs": [{"name": "source", "data_type": "series", "required": True}],
        "outputs": [{"name": "rsi", "data_type": "series"}],
        "parameters": [
            {
                "name": "period",
                "param_type": "int",
                "default": 14,
                "min_value": 2,
                "max_value": 100,
            },
        ],
    },
    BlockType.INDICATOR_MACD: {
        "name": "MACD",
        "color": "#9C27B0",
        "icon": "stacked_line_chart",
        "inputs": [{"name": "source", "data_type": "series", "required": True}],
        "outputs": [
            {"name": "macd_line", "data_type": "series"},
            {"name": "signal_line", "data_type": "series"},
            {"name": "histogram", "data_type": "series"},
        ],
        "parameters": [
            {
                "name": "fast_period",
                "param_type": "int",
                "default": 12,
                "min_value": 2,
                "max_value": 50,
            },
            {
                "name": "slow_period",
                "param_type": "int",
                "default": 26,
                "min_value": 5,
                "max_value": 100,
            },
            {
                "name": "signal_period",
                "param_type": "int",
                "default": 9,
                "min_value": 2,
                "max_value": 50,
            },
        ],
    },
    BlockType.INDICATOR_BOLLINGER: {
        "name": "Bollinger Bands",
        "color": "#9C27B0",
        "icon": "area_chart",
        "inputs": [{"name": "source", "data_type": "series", "required": True}],
        "outputs": [
            {"name": "upper", "data_type": "series"},
            {"name": "middle", "data_type": "series"},
            {"name": "lower", "data_type": "series"},
            {"name": "bandwidth", "data_type": "series"},
        ],
        "parameters": [
            {
                "name": "period",
                "param_type": "int",
                "default": 20,
                "min_value": 5,
                "max_value": 100,
            },
            {
                "name": "std_dev",
                "param_type": "float",
                "default": 2.0,
                "min_value": 0.5,
                "max_value": 5.0,
            },
        ],
    },
    BlockType.INDICATOR_EMA: {
        "name": "EMA",
        "color": "#9C27B0",
        "icon": "show_chart",
        "inputs": [{"name": "source", "data_type": "series", "required": True}],
        "outputs": [{"name": "ema", "data_type": "series"}],
        "parameters": [
            {
                "name": "period",
                "param_type": "int",
                "default": 20,
                "min_value": 2,
                "max_value": 500,
            },
        ],
    },
    BlockType.INDICATOR_SMA: {
        "name": "SMA",
        "color": "#9C27B0",
        "icon": "show_chart",
        "inputs": [{"name": "source", "data_type": "series", "required": True}],
        "outputs": [{"name": "sma", "data_type": "series"}],
        "parameters": [
            {
                "name": "period",
                "param_type": "int",
                "default": 20,
                "min_value": 2,
                "max_value": 500,
            },
        ],
    },
    BlockType.INDICATOR_ATR: {
        "name": "ATR",
        "color": "#9C27B0",
        "icon": "swap_vert",
        "inputs": [
            {"name": "high", "data_type": "series", "required": True},
            {"name": "low", "data_type": "series", "required": True},
            {"name": "close", "data_type": "series", "required": True},
        ],
        "outputs": [{"name": "atr", "data_type": "series"}],
        "parameters": [
            {
                "name": "period",
                "param_type": "int",
                "default": 14,
                "min_value": 2,
                "max_value": 100,
            },
        ],
    },
    BlockType.INDICATOR_CUSTOM: {
        "name": "Custom Indicator",
        "color": "#FF5722",
        "icon": "code",
        "inputs": [{"name": "source", "data_type": "series", "required": True}],
        "outputs": [{"name": "result", "data_type": "series"}],
        "parameters": [
            {"name": "code", "param_type": "string", "default": "return source"},
        ],
    },
    # Conditions
    BlockType.CONDITION_COMPARE: {
        "name": "Compare",
        "color": "#FFC107",
        "icon": "compare_arrows",
        "inputs": [
            {"name": "left", "data_type": "series", "required": True},
            {"name": "right", "data_type": "series", "required": True},
        ],
        "outputs": [{"name": "result", "data_type": "bool"}],
        "parameters": [
            {
                "name": "operator",
                "param_type": "choice",
                "default": ">",
                "choices": [">", "<", ">=", "<=", "==", "!="],
            },
        ],
    },
    BlockType.CONDITION_CROSS: {
        "name": "Crossover",
        "color": "#FFC107",
        "icon": "swap_horiz",
        "inputs": [
            {"name": "fast", "data_type": "series", "required": True},
            {"name": "slow", "data_type": "series", "required": True},
        ],
        "outputs": [
            {"name": "cross_above", "data_type": "bool"},
            {"name": "cross_below", "data_type": "bool"},
        ],
        "parameters": [],
    },
    BlockType.CONDITION_THRESHOLD: {
        "name": "Threshold",
        "color": "#FFC107",
        "icon": "horizontal_rule",
        "inputs": [{"name": "value", "data_type": "series", "required": True}],
        "outputs": [
            {"name": "above", "data_type": "bool"},
            {"name": "below", "data_type": "bool"},
        ],
        "parameters": [
            {"name": "threshold", "param_type": "float", "default": 50.0},
        ],
    },
    BlockType.CONDITION_AND: {
        "name": "AND",
        "color": "#FFC107",
        "icon": "join_inner",
        "inputs": [
            {"name": "condition1", "data_type": "bool", "required": True},
            {"name": "condition2", "data_type": "bool", "required": True},
        ],
        "outputs": [{"name": "result", "data_type": "bool"}],
        "parameters": [],
    },
    BlockType.CONDITION_OR: {
        "name": "OR",
        "color": "#FFC107",
        "icon": "join_full",
        "inputs": [
            {"name": "condition1", "data_type": "bool", "required": True},
            {"name": "condition2", "data_type": "bool", "required": True},
        ],
        "outputs": [{"name": "result", "data_type": "bool"}],
        "parameters": [],
    },
    # Actions
    BlockType.ACTION_BUY: {
        "name": "Buy",
        "color": "#4CAF50",
        "icon": "add_shopping_cart",
        "inputs": [{"name": "trigger", "data_type": "bool", "required": True}],
        "outputs": [{"name": "signal", "data_type": "signal"}],
        "parameters": [
            {
                "name": "size_pct",
                "param_type": "float",
                "default": 100.0,
                "min_value": 1,
                "max_value": 100,
            },
            {
                "name": "order_type",
                "param_type": "choice",
                "default": "market",
                "choices": ["market", "limit"],
            },
        ],
    },
    BlockType.ACTION_SELL: {
        "name": "Sell",
        "color": "#F44336",
        "icon": "remove_shopping_cart",
        "inputs": [{"name": "trigger", "data_type": "bool", "required": True}],
        "outputs": [{"name": "signal", "data_type": "signal"}],
        "parameters": [
            {
                "name": "size_pct",
                "param_type": "float",
                "default": 100.0,
                "min_value": 1,
                "max_value": 100,
            },
            {
                "name": "order_type",
                "param_type": "choice",
                "default": "market",
                "choices": ["market", "limit"],
            },
        ],
    },
    BlockType.ACTION_SET_STOP_LOSS: {
        "name": "Stop Loss",
        "color": "#FF9800",
        "icon": "shield",
        "inputs": [{"name": "trigger", "data_type": "bool", "required": True}],
        "outputs": [{"name": "signal", "data_type": "signal"}],
        "parameters": [
            {
                "name": "stop_type",
                "param_type": "choice",
                "default": "percent",
                "choices": ["percent", "atr", "fixed"],
            },
            {"name": "value", "param_type": "float", "default": 2.0},
        ],
    },
    BlockType.ACTION_SET_TAKE_PROFIT: {
        "name": "Take Profit",
        "color": "#4CAF50",
        "icon": "emoji_events",
        "inputs": [{"name": "trigger", "data_type": "bool", "required": True}],
        "outputs": [{"name": "signal", "data_type": "signal"}],
        "parameters": [
            {
                "name": "tp_type",
                "param_type": "choice",
                "default": "percent",
                "choices": ["percent", "atr", "fixed"],
            },
            {"name": "value", "param_type": "float", "default": 4.0},
        ],
    },
    # Filters
    BlockType.FILTER_TIME: {
        "name": "Time Filter",
        "color": "#607D8B",
        "icon": "schedule",
        "inputs": [{"name": "signal", "data_type": "bool", "required": True}],
        "outputs": [{"name": "filtered", "data_type": "bool"}],
        "parameters": [
            {
                "name": "start_hour",
                "param_type": "int",
                "default": 8,
                "min_value": 0,
                "max_value": 23,
            },
            {
                "name": "end_hour",
                "param_type": "int",
                "default": 20,
                "min_value": 0,
                "max_value": 23,
            },
            {"name": "days", "param_type": "string", "default": "Mon,Tue,Wed,Thu,Fri"},
        ],
    },
    BlockType.FILTER_VOLUME: {
        "name": "Volume Filter",
        "color": "#607D8B",
        "icon": "bar_chart",
        "inputs": [
            {"name": "signal", "data_type": "bool", "required": True},
            {"name": "volume", "data_type": "series", "required": True},
        ],
        "outputs": [{"name": "filtered", "data_type": "bool"}],
        "parameters": [
            {"name": "min_volume_ratio", "param_type": "float", "default": 1.5},
            {"name": "lookback", "param_type": "int", "default": 20},
        ],
    },
    # Risk Management
    BlockType.RISK_POSITION_SIZE: {
        "name": "Position Sizing",
        "color": "#795548",
        "icon": "calculate",
        "inputs": [
            {"name": "signal", "data_type": "signal", "required": True},
            {"name": "atr", "data_type": "series", "required": False},
        ],
        "outputs": [{"name": "sized_signal", "data_type": "signal"}],
        "parameters": [
            {
                "name": "method",
                "param_type": "choice",
                "default": "fixed",
                "choices": ["fixed", "kelly", "risk_pct", "volatility"],
            },
            {"name": "risk_per_trade", "param_type": "float", "default": 1.0},
            {"name": "max_position_pct", "param_type": "float", "default": 10.0},
        ],
    },
    # Output
    BlockType.OUTPUT_SIGNAL: {
        "name": "Signal Output",
        "color": "#00BCD4",
        "icon": "output",
        "inputs": [{"name": "signal", "data_type": "signal", "required": True}],
        "outputs": [],
        "parameters": [],
    },
}


class StrategyBuilder:
    """
    Visual Strategy Builder

    Example:
        builder = StrategyBuilder()

        # Create a new strategy
        graph = builder.create_strategy("My RSI Strategy")

        # Add blocks
        candles = builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=100)
        rsi = builder.add_block(graph, BlockType.INDICATOR_RSI, x=300, y=100)
        threshold = builder.add_block(graph, BlockType.CONDITION_THRESHOLD, x=500, y=100)
        buy = builder.add_block(graph, BlockType.ACTION_BUY, x=700, y=50)
        sell = builder.add_block(graph, BlockType.ACTION_SELL, x=700, y=150)

        # Connect blocks
        builder.connect(graph, candles.id, "close", rsi.id, "source")
        builder.connect(graph, rsi.id, "rsi", threshold.id, "value")
        builder.connect(graph, threshold.id, "below", buy.id, "trigger")  # RSI < 30
        builder.connect(graph, threshold.id, "above", sell.id, "trigger")  # RSI > 70

        # Configure
        builder.set_parameter(threshold, "threshold", 30)  # Oversold

        # Generate code
        code = builder.generate_code(graph)
    """

    def __init__(self):
        self.strategies: Dict[str, StrategyGraph] = {}

    def create_strategy(
        self,
        name: str,
        description: str = "",
        timeframe: str = "1h",
        symbols: Optional[List[str]] = None,
    ) -> StrategyGraph:
        """Create a new strategy"""
        strategy = StrategyGraph(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            timeframe=timeframe,
            symbols=symbols or ["BTCUSDT"],
        )
        self.strategies[strategy.id] = strategy
        return strategy

    def add_block(
        self,
        graph: StrategyGraph,
        block_type: BlockType,
        x: float = 0,
        y: float = 0,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> StrategyBlock:
        """Add a block to the strategy"""
        definition = BLOCK_DEFINITIONS.get(block_type, {})

        # Create inputs
        inputs = [
            BlockInput(
                name=i["name"],
                data_type=i["data_type"],
                required=i.get("required", True),
            )
            for i in definition.get("inputs", [])
        ]

        # Create outputs
        outputs = [
            BlockOutput(
                name=o["name"],
                data_type=o["data_type"],
            )
            for o in definition.get("outputs", [])
        ]

        # Default parameters
        default_params = {
            p["name"]: p["default"] for p in definition.get("parameters", [])
        }
        if parameters:
            default_params.update(parameters)

        block = StrategyBlock(
            id=str(uuid.uuid4()),
            block_type=block_type,
            name=definition.get("name", block_type.value),
            position_x=x,
            position_y=y,
            inputs=inputs,
            outputs=outputs,
            parameters=default_params,
            color=definition.get("color", "#4CAF50"),
            icon=definition.get("icon", "block"),
        )

        graph.add_block(block)
        return block

    def connect(
        self,
        graph: StrategyGraph,
        source_id: str,
        source_output: str,
        target_id: str,
        target_input: str,
    ) -> BlockConnection:
        """Connect two blocks"""
        return graph.connect(source_id, source_output, target_id, target_input)

    def set_parameter(self, block: StrategyBlock, name: str, value: Any) -> None:
        """Set a block parameter"""
        block.parameters[name] = value

    def validate(self, graph: StrategyGraph) -> List[str]:
        """Validate strategy graph"""
        errors = []

        # Check for empty graph
        if not graph.blocks:
            errors.append("Strategy has no blocks")
            return errors

        # Check for data source
        has_data_source = any(
            b.block_type in [BlockType.CANDLE_DATA, BlockType.ORDERBOOK_DATA]
            for b in graph.blocks.values()
        )
        if not has_data_source:
            errors.append("Strategy needs a data source block")

        # Check for output
        has_output = any(
            b.block_type
            in [BlockType.OUTPUT_SIGNAL, BlockType.ACTION_BUY, BlockType.ACTION_SELL]
            for b in graph.blocks.values()
        )
        if not has_output:
            errors.append("Strategy needs an action or output block")

        # Check connections
        connected_inputs: Set[Tuple[str, str]] = set()
        for conn in graph.connections:
            # Check source exists
            if conn.source_block_id not in graph.blocks:
                errors.append(
                    f"Connection references non-existent source block: {conn.source_block_id}"
                )

            # Check target exists
            if conn.target_block_id not in graph.blocks:
                errors.append(
                    f"Connection references non-existent target block: {conn.target_block_id}"
                )

            connected_inputs.add((conn.target_block_id, conn.target_input))

        # Check required inputs
        for block_id, block in graph.blocks.items():
            for inp in block.inputs:
                if inp.required and (block_id, inp.name) not in connected_inputs:
                    errors.append(
                        f"Block '{block.name}' has unconnected required input: {inp.name}"
                    )

        # Check for cycles
        try:
            graph.get_execution_order()
        except ValueError as e:
            errors.append(str(e))

        return errors

    def get_available_blocks(self) -> List[Dict[str, Any]]:
        """Get list of available block types"""
        result = []
        for block_type, definition in BLOCK_DEFINITIONS.items():
            result.append(
                {
                    "type": block_type.value,
                    "name": definition.get("name", block_type.value),
                    "color": definition.get("color", "#4CAF50"),
                    "icon": definition.get("icon", "block"),
                    "inputs": definition.get("inputs", []),
                    "outputs": definition.get("outputs", []),
                    "parameters": definition.get("parameters", []),
                    "category": block_type.value.split("_")[0],
                }
            )
        return result

    def save_strategy(self, graph: StrategyGraph, path: str) -> None:
        """Save strategy to file"""
        with open(path, "w") as f:
            json.dump(graph.to_dict(), f, indent=2)

    def load_strategy(self, path: str) -> StrategyGraph:
        """Load strategy from file"""
        with open(path, "r") as f:
            data = json.load(f)

        graph = StrategyGraph.from_dict(data)
        self.strategies[graph.id] = graph
        return graph

    def clone_strategy(self, graph: StrategyGraph) -> StrategyGraph:
        """Create a copy of a strategy"""
        data = graph.to_dict()
        data["id"] = str(uuid.uuid4())
        data["name"] = f"{graph.name} (Copy)"
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        new_graph = StrategyGraph.from_dict(data)
        self.strategies[new_graph.id] = new_graph
        return new_graph

    def get_block_definition(self, block_type: BlockType) -> Dict[str, Any]:
        """Get block definition"""
        return BLOCK_DEFINITIONS.get(block_type, {})
