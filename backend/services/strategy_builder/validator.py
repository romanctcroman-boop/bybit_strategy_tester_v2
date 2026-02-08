"""
Strategy Validator

Validates visual strategy graphs for correctness, safety, and performance.

Validation Categories:
- Structural: Graph connectivity, cycles, required blocks
- Logical: Parameter ranges, type compatibility
- Performance: Complexity, lookback requirements
- Safety: Risk limits, position sizing
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from .builder import (
    BlockType,
    StrategyGraph,
)

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""

    ERROR = "error"  # Prevents execution
    WARNING = "warning"  # May cause issues
    INFO = "info"  # Optimization hints


@dataclass
class ValidationError:
    """A validation error"""

    code: str
    message: str
    severity: ValidationSeverity
    block_id: str | None = None
    block_name: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "block_id": self.block_id,
            "block_name": self.block_name,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationWarning:
    """A validation warning"""

    code: str
    message: str
    block_id: str | None = None
    block_name: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "code": self.code,
            "message": self.message,
            "block_id": self.block_id,
            "block_name": self.block_name,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Result of strategy validation"""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    # Metrics
    block_count: int = 0
    connection_count: int = 0
    complexity_score: float = 0.0
    estimated_lookback: int = 0

    # Timestamp
    validated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "info": self.info,
            "block_count": self.block_count,
            "connection_count": self.connection_count,
            "complexity_score": self.complexity_score,
            "estimated_lookback": self.estimated_lookback,
            "validated_at": self.validated_at.isoformat(),
        }


class StrategyValidator:
    """
    Validates strategy graphs

    Example:
        validator = StrategyValidator()
        result = validator.validate(graph)

        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error.message}")

        for warning in result.warnings:
            print(f"Warning: {warning.message}")
    """

    def __init__(self):
        # Block type requirements
        self.data_sources = {
            BlockType.CANDLE_DATA,
            BlockType.ORDERBOOK_DATA,
            BlockType.TRADE_DATA,
            BlockType.EXTERNAL_DATA,
        }

        self.action_blocks = {
            BlockType.ACTION_BUY,
            BlockType.ACTION_SELL,
            BlockType.ACTION_CLOSE,
            BlockType.OUTPUT_SIGNAL,
        }

        # Parameter validation rules
        self.parameter_rules: dict[str, dict[str, Any]] = {
            "period": {"min": 1, "max": 1000, "type": int},
            "fast_period": {"min": 1, "max": 500, "type": int},
            "slow_period": {"min": 2, "max": 1000, "type": int},
            "signal_period": {"min": 1, "max": 100, "type": int},
            "std_dev": {"min": 0.1, "max": 10.0, "type": float},
            "threshold": {"min": -1000, "max": 1000, "type": float},
            "size_pct": {"min": 0.1, "max": 100, "type": float},
            "value": {"min": 0.001, "max": 100, "type": float},
        }

        # Lookback requirements by indicator
        self.lookback_requirements = {
            BlockType.INDICATOR_RSI: lambda p: p.get("period", 14) + 1,
            BlockType.INDICATOR_MACD: lambda p: p.get("slow_period", 26)
            + p.get("signal_period", 9),
            BlockType.INDICATOR_BOLLINGER: lambda p: p.get("period", 20),
            BlockType.INDICATOR_EMA: lambda p: p.get("period", 20) * 2,
            BlockType.INDICATOR_SMA: lambda p: p.get("period", 20),
            BlockType.INDICATOR_ATR: lambda p: p.get("period", 14) + 1,
            BlockType.INDICATOR_STOCHASTIC: lambda p: p.get("k_period", 14)
            + p.get("d_period", 3),
        }

    def validate(self, graph: StrategyGraph) -> ValidationResult:
        """
        Perform full validation of a strategy graph

        Args:
            graph: Strategy graph to validate

        Returns:
            ValidationResult with errors, warnings, and metrics
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []
        info: list[str] = []

        # Structural validation
        errors.extend(self._validate_structure(graph))

        # Connection validation
        errors.extend(self._validate_connections(graph))

        # Parameter validation
        param_errors, param_warnings = self._validate_parameters(graph)
        errors.extend(param_errors)
        warnings.extend(param_warnings)

        # Cycle detection
        cycle_errors = self._detect_cycles(graph)
        errors.extend(cycle_errors)

        # Risk validation
        risk_warnings = self._validate_risk(graph)
        warnings.extend(risk_warnings)

        # Performance analysis
        perf_warnings, perf_info = self._analyze_performance(graph)
        warnings.extend(perf_warnings)
        info.extend(perf_info)

        # Calculate metrics
        complexity = self._calculate_complexity(graph)
        lookback = self._estimate_lookback(graph)

        is_valid = (
            len([e for e in errors if e.severity == ValidationSeverity.ERROR]) == 0
        )

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            info=info,
            block_count=len(graph.blocks),
            connection_count=len(graph.connections),
            complexity_score=complexity,
            estimated_lookback=lookback,
        )

    def _validate_structure(self, graph: StrategyGraph) -> list[ValidationError]:
        """Validate graph structure"""
        errors = []

        # Check for empty graph
        if not graph.blocks:
            errors.append(
                ValidationError(
                    code="EMPTY_GRAPH",
                    message="Strategy has no blocks",
                    severity=ValidationSeverity.ERROR,
                    suggestion="Add at least a data source and an action block",
                )
            )
            return errors

        # Check for data source
        has_data_source = any(
            b.block_type in self.data_sources for b in graph.blocks.values()
        )
        if not has_data_source:
            errors.append(
                ValidationError(
                    code="NO_DATA_SOURCE",
                    message="Strategy needs a data source block",
                    severity=ValidationSeverity.ERROR,
                    suggestion="Add a Candle Data or other data source block",
                )
            )

        # Check for action/output
        has_action = any(
            b.block_type in self.action_blocks for b in graph.blocks.values()
        )
        if not has_action:
            errors.append(
                ValidationError(
                    code="NO_ACTION",
                    message="Strategy needs at least one action or output block",
                    severity=ValidationSeverity.ERROR,
                    suggestion="Add a Buy, Sell, or Signal Output block",
                )
            )

        # Check for main strategy node and entry signals
        main_node = None
        for block_id, block in graph.blocks.items():
            if block.block_type == BlockType.OUTPUT_SIGNAL and (
                block.name.lower() == "strategy" or getattr(block, "isMain", False)
            ):
                main_node = block_id
                break

        if main_node:
            # Check if entry signals are connected to main node
            # Frontend uses ports: entry_long, entry_short, exit_long, exit_short
            # But OUTPUT_SIGNAL block definition only has "signal" input
            # So we check for connections to main node regardless of input name
            # OR check if main node has custom inputs (entry_long, etc.)
            main_block = graph.blocks[main_node]
            main_inputs = [inp.name for inp in main_block.inputs]

            # Check for connections to main node
            main_connections = [
                conn
                for conn in graph.connections
                if conn.target_block_id == main_node
            ]

            # If main node has entry_long/entry_short inputs, require them
            if "entry_long" in main_inputs or "entry_short" in main_inputs:
                entry_connections = [
                    conn
                    for conn in main_connections
                    if conn.target_input in ["entry_long", "entry_short"]
                ]
                if not entry_connections:
                    errors.append(
                        ValidationError(
                            code="NO_ENTRY_SIGNALS",
                            message="Main strategy node has no entry signals connected",
                            severity=ValidationSeverity.ERROR,
                            block_id=main_node,
                            suggestion="Connect at least one condition block to entry_long or entry_short port",
                        )
                    )
            # Otherwise, just check that main node has some connections
            elif not main_connections:
                errors.append(
                    ValidationError(
                        code="NO_ENTRY_SIGNALS",
                        message="Main strategy node has no signals connected",
                        severity=ValidationSeverity.ERROR,
                        block_id=main_node,
                        suggestion="Connect at least one condition block to the main strategy node",
                    )
                )

        # Check for orphan blocks (not connected to anything)
        connected_blocks = self._get_connected_blocks(graph)
        for block_id, block in graph.blocks.items():
            if block_id not in connected_blocks:
                # Data sources don't need incoming connections
                if block.block_type not in self.data_sources:
                    errors.append(
                        ValidationError(
                            code="ORPHAN_BLOCK",
                            message=f"Block '{block.name}' is not connected",
                            severity=ValidationSeverity.WARNING,
                            block_id=block_id,
                            block_name=block.name,
                            suggestion="Connect this block or remove it",
                        )
                    )

        return errors

    def _validate_connections(self, graph: StrategyGraph) -> list[ValidationError]:
        """Validate connections between blocks"""
        errors = []

        # Track connected inputs
        connected_inputs: dict[str, set[str]] = {bid: set() for bid in graph.blocks}

        for conn in graph.connections:
            # Check source block exists
            if conn.source_block_id not in graph.blocks:
                errors.append(
                    ValidationError(
                        code="INVALID_SOURCE",
                        message="Connection references non-existent source block",
                        severity=ValidationSeverity.ERROR,
                        suggestion="Remove or fix this connection",
                    )
                )
                continue

            # Check target block exists
            if conn.target_block_id not in graph.blocks:
                errors.append(
                    ValidationError(
                        code="INVALID_TARGET",
                        message="Connection references non-existent target block",
                        severity=ValidationSeverity.ERROR,
                        suggestion="Remove or fix this connection",
                    )
                )
                continue

            source_block = graph.blocks[conn.source_block_id]
            target_block = graph.blocks[conn.target_block_id]

            # Check output exists
            output_names = [o.name for o in source_block.outputs]
            if conn.source_output not in output_names:
                errors.append(
                    ValidationError(
                        code="INVALID_OUTPUT",
                        message=f"Block '{source_block.name}' has no output '{conn.source_output}'",
                        severity=ValidationSeverity.ERROR,
                        block_id=conn.source_block_id,
                        block_name=source_block.name,
                        suggestion=f"Valid outputs: {', '.join(output_names)}",
                    )
                )

            # Check input exists
            input_names = [i.name for i in target_block.inputs]
            if conn.target_input not in input_names:
                errors.append(
                    ValidationError(
                        code="INVALID_INPUT",
                        message=f"Block '{target_block.name}' has no input '{conn.target_input}'",
                        severity=ValidationSeverity.ERROR,
                        block_id=conn.target_block_id,
                        block_name=target_block.name,
                        suggestion=f"Valid inputs: {', '.join(input_names)}",
                    )
                )

            # Track connected inputs
            connected_inputs[conn.target_block_id].add(conn.target_input)

            # Type compatibility check
            output = next(
                (o for o in source_block.outputs if o.name == conn.source_output), None
            )
            input_port = next(
                (i for i in target_block.inputs if i.name == conn.target_input), None
            )

            if output and input_port:
                if not self._types_compatible(output.data_type, input_port.data_type):
                    errors.append(
                        ValidationError(
                            code="TYPE_MISMATCH",
                            message=f"Type mismatch: '{output.data_type}' → '{input_port.data_type}'",
                            severity=ValidationSeverity.WARNING,
                            block_id=conn.target_block_id,
                            block_name=target_block.name,
                            suggestion="Ensure data types are compatible",
                        )
                    )

        # Check required inputs
        for block_id, block in graph.blocks.items():
            for inp in block.inputs:
                if inp.required and inp.name not in connected_inputs.get(
                    block_id, set()
                ):
                    errors.append(
                        ValidationError(
                            code="MISSING_INPUT",
                            message=f"Block '{block.name}' has unconnected required input: {inp.name}",
                            severity=ValidationSeverity.ERROR,
                            block_id=block_id,
                            block_name=block.name,
                            suggestion=f"Connect a block to the '{inp.name}' input",
                        )
                    )

        return errors

    def _validate_parameters(self, graph: StrategyGraph) -> tuple:
        """Validate block parameters"""
        errors = []
        warnings = []

        for block_id, block in graph.blocks.items():
            for param_name, param_value in block.parameters.items():
                rule = self.parameter_rules.get(param_name)

                if rule:
                    # Type check
                    expected_type = rule.get("type")
                    if expected_type and not isinstance(param_value, expected_type):
                        if expected_type is int and isinstance(param_value, float):
                            # Allow float for int (will be converted)
                            pass
                        else:
                            errors.append(
                                ValidationError(
                                    code="INVALID_PARAM_TYPE",
                                    message=f"Parameter '{param_name}' should be {expected_type.__name__}",
                                    severity=ValidationSeverity.ERROR,
                                    block_id=block_id,
                                    block_name=block.name,
                                )
                            )

                    # Range check
                    min_val = rule.get("min")
                    max_val = rule.get("max")

                    if min_val is not None and param_value < min_val:
                        errors.append(
                            ValidationError(
                                code="PARAM_TOO_LOW",
                                message=f"Parameter '{param_name}' value {param_value} is below minimum {min_val}",
                                severity=ValidationSeverity.ERROR,
                                block_id=block_id,
                                block_name=block.name,
                            )
                        )

                    if max_val is not None and param_value > max_val:
                        errors.append(
                            ValidationError(
                                code="PARAM_TOO_HIGH",
                                message=f"Parameter '{param_name}' value {param_value} exceeds maximum {max_val}",
                                severity=ValidationSeverity.ERROR,
                                block_id=block_id,
                                block_name=block.name,
                            )
                        )

                # Specific parameter checks
                if param_name == "period" and param_value < 2:
                    warnings.append(
                        ValidationWarning(
                            code="SHORT_PERIOD",
                            message=f"Period {param_value} is very short, may cause noise",
                            block_id=block_id,
                            block_name=block.name,
                            suggestion="Consider using a longer period for stability",
                        )
                    )

                if param_name == "size_pct" and param_value > 50:
                    warnings.append(
                        ValidationWarning(
                            code="LARGE_POSITION",
                            message=f"Position size {param_value}% is large",
                            block_id=block_id,
                            block_name=block.name,
                            suggestion="Consider smaller position sizes for risk management",
                        )
                    )

            # MACD specific: fast must be less than slow
            if block.block_type == BlockType.INDICATOR_MACD:
                fast = block.parameters.get("fast_period", 12)
                slow = block.parameters.get("slow_period", 26)
                if fast >= slow:
                    errors.append(
                        ValidationError(
                            code="MACD_PERIOD_ERROR",
                            message="MACD fast period must be less than slow period",
                            severity=ValidationSeverity.ERROR,
                            block_id=block_id,
                            block_name=block.name,
                        )
                    )

        return errors, warnings

    def _detect_cycles(self, graph: StrategyGraph) -> list[ValidationError]:
        """Detect cycles in the graph"""
        errors = []

        try:
            graph.get_execution_order()
        except ValueError:
            errors.append(
                ValidationError(
                    code="CYCLE_DETECTED",
                    message="Strategy graph contains a cycle (circular dependency)",
                    severity=ValidationSeverity.ERROR,
                    suggestion="Remove connections that create circular dependencies",
                )
            )

        return errors

    def _validate_risk(self, graph: StrategyGraph) -> list[ValidationWarning]:
        """Validate risk management"""
        warnings = []

        has_stop_loss = any(
            b.block_type == BlockType.ACTION_SET_STOP_LOSS
            for b in graph.blocks.values()
        )

        has_take_profit = any(
            b.block_type == BlockType.ACTION_SET_TAKE_PROFIT
            for b in graph.blocks.values()
        )

        has_position_sizing = any(
            b.block_type == BlockType.RISK_POSITION_SIZE for b in graph.blocks.values()
        )

        if not has_stop_loss:
            warnings.append(
                ValidationWarning(
                    code="NO_STOP_LOSS",
                    message="Strategy has no stop loss configured",
                    suggestion="Add a Stop Loss block for risk management",
                )
            )

        if not has_take_profit:
            warnings.append(
                ValidationWarning(
                    code="NO_TAKE_PROFIT",
                    message="Strategy has no take profit configured",
                    suggestion="Consider adding a Take Profit block",
                )
            )

        if not has_position_sizing:
            warnings.append(
                ValidationWarning(
                    code="NO_POSITION_SIZING",
                    message="Strategy has no position sizing configured",
                    suggestion="Add Position Sizing block for proper risk management",
                )
            )

        # Check for multiple buy/sell without risk management
        buy_count = sum(
            1 for b in graph.blocks.values() if b.block_type == BlockType.ACTION_BUY
        )
        sell_count = sum(
            1 for b in graph.blocks.values() if b.block_type == BlockType.ACTION_SELL
        )

        if buy_count > 0 and sell_count == 0:
            warnings.append(
                ValidationWarning(
                    code="NO_EXIT",
                    message="Strategy has buy signals but no sell signals",
                    suggestion="Add a Sell block to define exit conditions",
                )
            )

        return warnings

    def _analyze_performance(self, graph: StrategyGraph) -> tuple:
        """Analyze performance characteristics"""
        warnings = []
        info = []

        # Count indicator blocks
        indicator_count = sum(
            1
            for b in graph.blocks.values()
            if b.block_type.value.startswith("indicator_")
        )

        if indicator_count > 5:
            warnings.append(
                ValidationWarning(
                    code="MANY_INDICATORS",
                    message=f"Strategy uses {indicator_count} indicators, may be overcomplicated",
                    suggestion="Consider simplifying to avoid overfitting",
                )
            )

        # Check for conflicting conditions
        and_count = sum(
            1 for b in graph.blocks.values() if b.block_type == BlockType.CONDITION_AND
        )
        or_count = sum(
            1 for b in graph.blocks.values() if b.block_type == BlockType.CONDITION_OR
        )

        if and_count > 3:
            info.append(
                f"Strategy uses {and_count} AND conditions - signals may be rare"
            )

        if or_count > 3:
            info.append(
                f"Strategy uses {or_count} OR conditions - signals may be frequent"
            )

        # Timeframe hints
        has_scalping_indicators = any(
            b.block_type in [BlockType.INDICATOR_RSI, BlockType.INDICATOR_STOCHASTIC]
            and b.parameters.get("period", 14) < 10
            for b in graph.blocks.values()
        )

        if has_scalping_indicators and graph.timeframe in ["4h", "1d"]:
            warnings.append(
                ValidationWarning(
                    code="TIMEFRAME_MISMATCH",
                    message="Short-period indicators on long timeframe may be suboptimal",
                    suggestion="Consider shorter timeframe or longer indicator periods",
                )
            )

        return warnings, info

    def _calculate_complexity(self, graph: StrategyGraph) -> float:
        """Calculate complexity score (0-100)"""
        if not graph.blocks:
            return 0.0

        # Base complexity from block count
        block_score = min(len(graph.blocks) * 5, 30)

        # Connection complexity
        conn_score = min(len(graph.connections) * 2, 20)

        # Indicator complexity
        indicator_weights = {
            BlockType.INDICATOR_MACD: 3,
            BlockType.INDICATOR_BOLLINGER: 2,
            BlockType.INDICATOR_STOCHASTIC: 2,
            BlockType.INDICATOR_RSI: 1,
            BlockType.INDICATOR_EMA: 1,
            BlockType.INDICATOR_SMA: 1,
            BlockType.INDICATOR_CUSTOM: 5,
        }

        indicator_score = sum(
            indicator_weights.get(b.block_type, 1)
            for b in graph.blocks.values()
            if b.block_type.value.startswith("indicator_")
        )
        indicator_score = min(indicator_score * 3, 30)

        # Condition complexity
        condition_score = (
            sum(
                1
                for b in graph.blocks.values()
                if b.block_type.value.startswith("condition_")
            )
            * 2
        )
        condition_score = min(condition_score, 20)

        return min(block_score + conn_score + indicator_score + condition_score, 100)

    def _estimate_lookback(self, graph: StrategyGraph) -> int:
        """Estimate minimum lookback period required"""
        max_lookback = 0

        for block in graph.blocks.values():
            if block.block_type in self.lookback_requirements:
                calc = self.lookback_requirements[block.block_type]
                lookback = calc(block.parameters)
                max_lookback = max(max_lookback, lookback)

        return max_lookback

    def _get_connected_blocks(self, graph: StrategyGraph) -> set[str]:
        """Get all blocks that are connected"""
        connected = set()

        for conn in graph.connections:
            connected.add(conn.source_block_id)
            connected.add(conn.target_block_id)

        return connected

    def _types_compatible(self, source_type: str, target_type: str) -> bool:
        """Check if data types are compatible"""
        # Exact match
        if source_type == target_type:
            return True

        # Compatible type pairs
        compatible_pairs = [
            ("series", "float"),
            ("float", "series"),
            ("bool", "signal"),
            ("signal", "bool"),
        ]

        return (source_type, target_type) in compatible_pairs

    def validate_for_backtest(self, graph: StrategyGraph) -> ValidationResult:
        """Validate specifically for backtesting"""
        result = self.validate(graph)

        # Additional backtest-specific checks
        if result.estimated_lookback > 500:
            result.warnings.append(
                ValidationWarning(
                    code="LONG_LOOKBACK",
                    message=f"Strategy requires {result.estimated_lookback} bars of lookback data",
                    suggestion="Ensure you have enough historical data",
                )
            )

        return result

    def validate_for_live(self, graph: StrategyGraph) -> ValidationResult:
        """Validate specifically for live trading"""
        result = self.validate(graph)

        # Live trading requires risk management
        has_stop = any(
            b.block_type == BlockType.ACTION_SET_STOP_LOSS
            for b in graph.blocks.values()
        )

        if not has_stop:
            result.errors.append(
                ValidationError(
                    code="LIVE_NO_STOP",
                    message="Live trading requires a stop loss",
                    severity=ValidationSeverity.ERROR,
                    suggestion="Add a Stop Loss block before going live",
                )
            )
            result.is_valid = False

        return result
