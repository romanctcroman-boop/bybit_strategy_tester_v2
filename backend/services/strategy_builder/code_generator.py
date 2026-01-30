"""
Strategy Code Generator

Generates executable Python code from visual strategy graphs.

Features:
- Converts block graphs to Python code
- Generates optimized indicator calculations
- Creates backtestable strategy classes
- Supports code templates and customization
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .builder import (
    BlockType,
    StrategyBlock,
    StrategyGraph,
)

logger = logging.getLogger(__name__)


class CodeTemplate(Enum):
    """Available code templates"""

    BASIC = "basic"  # Simple strategy class
    BACKTEST = "backtest"  # Backtesting-ready
    LIVE = "live"  # Live trading ready
    OPTIMIZATION = "optimization"  # For parameter optimization


@dataclass
class GenerationOptions:
    """Options for code generation"""

    template: CodeTemplate = CodeTemplate.BACKTEST
    include_comments: bool = True
    include_logging: bool = True
    include_validation: bool = True
    include_metrics: bool = True
    async_mode: bool = False
    use_pandas: bool = True
    indent: str = "    "
    max_line_length: int = 100


@dataclass
class GeneratedStrategy:
    """Generated strategy code and metadata"""

    code: str
    strategy_name: str
    strategy_id: str
    version: str
    generated_at: datetime
    source_graph_id: str
    dependencies: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "code": self.code,
            "strategy_name": self.strategy_name,
            "strategy_id": self.strategy_id,
            "version": self.version,
            "generated_at": self.generated_at.isoformat(),
            "source_graph_id": self.source_graph_id,
            "dependencies": self.dependencies,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class CodeGenerator:
    """
    Generates Python code from strategy graphs

    Example:
        generator = CodeGenerator()
        result = generator.generate(graph, GenerationOptions(
            template=CodeTemplate.BACKTEST,
            include_comments=True,
        ))

        print(result.code)
    """

    def __init__(self):
        self.templates: Dict[CodeTemplate, str] = {
            CodeTemplate.BASIC: TEMPLATE_BASIC,
            CodeTemplate.BACKTEST: TEMPLATE_BACKTEST,
            CodeTemplate.LIVE: TEMPLATE_LIVE,
            CodeTemplate.OPTIMIZATION: TEMPLATE_OPTIMIZATION,
        }

        # Block type to code mapping
        self.block_generators: Dict[BlockType, callable] = {
            BlockType.CANDLE_DATA: self._gen_candle_data,
            BlockType.INDICATOR_RSI: self._gen_rsi,
            BlockType.INDICATOR_MACD: self._gen_macd,
            BlockType.INDICATOR_BOLLINGER: self._gen_bollinger,
            BlockType.INDICATOR_EMA: self._gen_ema,
            BlockType.INDICATOR_SMA: self._gen_sma,
            BlockType.INDICATOR_ATR: self._gen_atr,
            BlockType.INDICATOR_STOCHASTIC: self._gen_stochastic,
            BlockType.INDICATOR_CUSTOM: self._gen_custom_indicator,
            BlockType.CONDITION_COMPARE: self._gen_compare,
            BlockType.CONDITION_CROSS: self._gen_cross,
            BlockType.CONDITION_THRESHOLD: self._gen_threshold,
            BlockType.CONDITION_AND: self._gen_and,
            BlockType.CONDITION_OR: self._gen_or,
            BlockType.CONDITION_NOT: self._gen_not,
            BlockType.ACTION_BUY: self._gen_buy,
            BlockType.ACTION_SELL: self._gen_sell,
            BlockType.ACTION_SET_STOP_LOSS: self._gen_stop_loss,
            BlockType.ACTION_SET_TAKE_PROFIT: self._gen_take_profit,
            BlockType.FILTER_TIME: self._gen_time_filter,
            BlockType.FILTER_VOLUME: self._gen_volume_filter,
            BlockType.RISK_POSITION_SIZE: self._gen_position_size,
            BlockType.OUTPUT_SIGNAL: self._gen_output,
        }

    def generate(
        self, graph: StrategyGraph, options: Optional[GenerationOptions] = None
    ) -> GeneratedStrategy:
        """
        Generate Python code from strategy graph

        Args:
            graph: Strategy graph to convert
            options: Generation options

        Returns:
            GeneratedStrategy with code and metadata
        """
        options = options or GenerationOptions()
        errors: List[str] = []
        warnings: List[str] = []

        # Validate graph first
        validation_errors = self._validate_graph(graph)
        if validation_errors:
            errors.extend(validation_errors)
            return GeneratedStrategy(
                code="",
                strategy_name=graph.name,
                strategy_id=graph.id,
                version="1.0",
                generated_at=datetime.now(timezone.utc),
                source_graph_id=graph.id,
                errors=errors,
            )

        try:
            # Get execution order
            execution_order = graph.get_execution_order()

            # Build connection map
            connections = self._build_connection_map(graph)

            # Generate code for each block
            block_code = {}
            variables = {}

            for block_id in execution_order:
                block = graph.blocks[block_id]
                if not block.enabled:
                    continue

                code, var_name = self._generate_block_code(
                    block, connections, variables, options
                )
                block_code[block_id] = code
                variables[block_id] = var_name

            # Combine into full strategy
            full_code = self._assemble_strategy(graph, block_code, variables, options)

            # Determine dependencies
            dependencies = self._get_dependencies(graph, options)

            return GeneratedStrategy(
                code=full_code,
                strategy_name=self._sanitize_name(graph.name),
                strategy_id=graph.id,
                version=graph.version,
                generated_at=datetime.now(timezone.utc),
                source_graph_id=graph.id,
                dependencies=dependencies,
                warnings=warnings,
            )

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            errors.append(str(e))
            return GeneratedStrategy(
                code="",
                strategy_name=graph.name,
                strategy_id=graph.id,
                version="1.0",
                generated_at=datetime.now(timezone.utc),
                source_graph_id=graph.id,
                errors=errors,
            )

    def _validate_graph(self, graph: StrategyGraph) -> List[str]:
        """Validate graph before generation"""
        errors = []

        if not graph.blocks:
            errors.append("Strategy has no blocks")
            return errors

        # Check for data source
        has_data = any(
            b.block_type in [BlockType.CANDLE_DATA, BlockType.ORDERBOOK_DATA]
            for b in graph.blocks.values()
        )
        if not has_data:
            errors.append("Strategy needs a data source")

        # Check for action/output
        has_action = any(
            b.block_type
            in [BlockType.ACTION_BUY, BlockType.ACTION_SELL, BlockType.OUTPUT_SIGNAL]
            for b in graph.blocks.values()
        )
        if not has_action:
            errors.append("Strategy needs at least one action or output")

        return errors

    def _build_connection_map(
        self, graph: StrategyGraph
    ) -> Dict[str, Dict[str, tuple]]:
        """
        Build a map of connections for quick lookup

        Returns:
            {target_block_id: {input_name: (source_block_id, output_name)}}
        """
        connections: Dict[str, Dict[str, tuple]] = {}

        for conn in graph.connections:
            if conn.target_block_id not in connections:
                connections[conn.target_block_id] = {}

            connections[conn.target_block_id][conn.target_input] = (
                conn.source_block_id,
                conn.source_output,
            )

        return connections

    def _generate_block_code(
        self,
        block: StrategyBlock,
        connections: Dict[str, Dict[str, tuple]],
        variables: Dict[str, str],
        options: GenerationOptions,
    ) -> tuple:
        """
        Generate code for a single block

        Returns:
            (code_string, variable_name)
        """
        generator = self.block_generators.get(block.block_type)

        if not generator:
            # Unsupported block type
            var_name = self._make_var_name(block)
            code = f"{options.indent}# Unsupported block: {block.block_type.value}\n"
            code += f"{options.indent}{var_name} = None\n"
            return code, var_name

        # Get input variables
        input_vars = {}
        if block.id in connections:
            for input_name, (source_id, output_name) in connections[block.id].items():
                if source_id in variables:
                    input_vars[input_name] = f"{variables[source_id]}['{output_name}']"

        return generator(block, input_vars, options)

    def _make_var_name(self, block: StrategyBlock) -> str:
        """Create a valid Python variable name for a block"""
        name = re.sub(r"[^a-zA-Z0-9_]", "_", block.name.lower())
        name = re.sub(r"_+", "_", name)
        if name[0].isdigit():
            name = f"b_{name}"
        return f"{name}_{block.id[:8]}"

    def _sanitize_name(self, name: str) -> str:
        """Sanitize strategy name for class name"""
        name = re.sub(r"[^a-zA-Z0-9]", "", name.title())
        if not name or name[0].isdigit():
            name = f"Strategy{name}"
        return name

    def _assemble_strategy(
        self,
        graph: StrategyGraph,
        block_code: Dict[str, str],
        variables: Dict[str, str],
        options: GenerationOptions,
    ) -> str:
        """Assemble all block code into a complete strategy"""
        template = self.templates.get(options.template, TEMPLATE_BACKTEST)

        # Build imports
        imports = self._build_imports(graph, options)

        # Build init code
        init_code = self._build_init(graph, options)

        # Build calculate code
        calculate_code = "\n".join(block_code.values())

        # Build signal extraction
        signal_code = self._build_signal_extraction(graph, variables, options)

        # Fill template
        strategy_name = self._sanitize_name(graph.name)

        code = template.format(
            strategy_name=strategy_name,
            imports=imports,
            init_code=init_code,
            calculate_code=calculate_code,
            signal_code=signal_code,
            parameters=self._build_parameters(graph),
            description=graph.description or f"Generated strategy: {graph.name}",
            version=graph.version,
            timeframe=graph.timeframe,
            symbols=", ".join(f"'{s}'" for s in graph.symbols),
        )

        return code

    def _build_imports(self, graph: StrategyGraph, options: GenerationOptions) -> str:
        """Build import statements"""
        imports = [
            "import numpy as np",
        ]

        if options.use_pandas:
            imports.append("import pandas as pd")

        if options.include_logging:
            imports.append("import logging")

        imports.append("from typing import Dict, List, Optional, Any")
        imports.append("from dataclasses import dataclass, field")
        imports.append("from datetime import datetime")
        imports.append("from enum import Enum")

        return "\n".join(imports)

    def _build_init(self, graph: StrategyGraph, options: GenerationOptions) -> str:
        """Build initialization code"""
        indent = options.indent * 2

        lines = [
            f'{indent}self.timeframe = "{graph.timeframe}"',
            f"{indent}self.symbols = [{', '.join(repr(s) for s in graph.symbols)}]",
        ]

        # Add parameters
        for block in graph.blocks.values():
            for param_name, param_value in block.parameters.items():
                var_name = self._make_var_name(block)
                lines.append(
                    f"{indent}self.{var_name}_{param_name} = {repr(param_value)}"
                )

        return "\n".join(lines)

    def _build_parameters(self, graph: StrategyGraph) -> str:
        """Build parameter definitions"""
        params = []

        for block in graph.blocks.values():
            for param_name, param_value in block.parameters.items():
                var_name = self._make_var_name(block)
                params.append(
                    f'        "{var_name}_{param_name}": {repr(param_value)},'
                )

        return "\n".join(params) if params else "        # No parameters"

    def _build_signal_extraction(
        self,
        graph: StrategyGraph,
        variables: Dict[str, str],
        options: GenerationOptions,
    ) -> str:
        """Build signal extraction code
        
        For Strategy Builder graphs, we need to extract signals from connections
        to the main strategy node (entry_long, exit_long, entry_short, exit_short).
        The generated code processes data vectorized, so we iterate through bars
        and check signal conditions at each bar index.
        """
        indent = options.indent * 2
        lines = []

        # Find main strategy node (can be OUTPUT_SIGNAL with name "strategy" or isMain flag)
        main_node_id = None
        for block_id, block in graph.blocks.items():
            # Check for main strategy node by type or name
            if block.block_type == BlockType.OUTPUT_SIGNAL and (
                block.name.lower() == "strategy" or getattr(block, "isMain", False)
            ):
                main_node_id = block_id
                break

        if not main_node_id:
            # Fallback: look for action blocks (old style)
            for block_id, block in graph.blocks.items():
                if block.block_type in [BlockType.ACTION_BUY, BlockType.ACTION_SELL]:
                    var_name = variables.get(block_id)
                    if var_name:
                        action = (
                            "buy" if block.block_type == BlockType.ACTION_BUY else "sell"
                        )
                        lines.append(f'{indent}if {var_name}.get("signal"):')
                        lines.append(
                            f'{indent}    signals.append({{"action": "{action}", "block": "{block.name}"}})'
                        )
        else:
            # New style: extract signals from connections to main node
            # Find connections to main node ports
            entry_long_var = None
            exit_long_var = None
            entry_short_var = None
            exit_short_var = None

            for conn in graph.connections:
                if conn.target_block_id == main_node_id:
                    source_var = variables.get(conn.source_block_id)
                    if source_var:
                        if conn.target_input == "entry_long":
                            entry_long_var = source_var
                        elif conn.target_input == "exit_long":
                            exit_long_var = source_var
                        elif conn.target_input == "entry_short":
                            entry_short_var = source_var
                        elif conn.target_input == "exit_short":
                            exit_short_var = source_var

            # Generate bar-by-bar signal extraction
            # Since calculate_code processes data vectorized, we need to iterate
            # through bars and check signal conditions
            lines.append(f"{indent}# Extract signals bar by bar")
            lines.append(f"{indent}n = len(candles['close'])")
            lines.append(f"{indent}for i in range(n):")
            
            if entry_long_var:
                # Check if signal is True at bar i
                lines.append(f'{indent}    if i < len({entry_long_var}.get("result", [])) and {entry_long_var}.get("result", [False])[i]:')
                lines.append(f'{indent}        signals.append({{"action": "buy", "index": i}})')
            
            if exit_long_var:
                lines.append(f'{indent}    if i < len({exit_long_var}.get("result", [])) and {exit_long_var}.get("result", [False])[i]:')
                lines.append(f'{indent}        signals.append({{"action": "sell", "index": i}})')
            
            if entry_short_var:
                lines.append(f'{indent}    if i < len({entry_short_var}.get("result", [])) and {entry_short_var}.get("result", [False])[i]:')
                lines.append(f'{indent}        signals.append({{"action": "short", "index": i}})')
            
            if exit_short_var:
                lines.append(f'{indent}    if i < len({exit_short_var}.get("result", [])) and {exit_short_var}.get("result", [False])[i]:')
                lines.append(f'{indent}        signals.append({{"action": "close", "index": i}})')

        if not lines:
            lines.append(f"{indent}# No signal extraction logic found")

        return "\n".join(lines)

    def _get_dependencies(
        self, graph: StrategyGraph, options: GenerationOptions
    ) -> List[str]:
        """Get list of required dependencies"""
        deps = ["numpy"]

        if options.use_pandas:
            deps.append("pandas")

        return deps

    # === Block Code Generators ===

    def _gen_candle_data(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate candle data block code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2

        code = f"""
{indent}# Candle Data: {block.name}
{indent}{var_name} = {{
{indent}    'open': candles['open'],
{indent}    'high': candles['high'],
{indent}    'low': candles['low'],
{indent}    'close': candles['close'],
{indent}    'volume': candles['volume'],
{indent}}}
"""
        return code, var_name

    def _gen_rsi(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate RSI indicator code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        period = block.parameters.get("period", 14)
        source = inputs.get("source", "candles['close']")

        code = f"""
{indent}# RSI: {block.name}
{indent}def calc_rsi_{var_name}(source, period={period}):
{indent}    delta = np.diff(source, prepend=source[0])
{indent}    gains = np.where(delta > 0, delta, 0)
{indent}    losses = np.where(delta < 0, -delta, 0)
{indent}    alpha = 1 / period
{indent}    avg_gain = np.zeros_like(source, dtype=float)
{indent}    avg_loss = np.zeros_like(source, dtype=float)
{indent}    avg_gain[period] = np.mean(gains[1:period + 1])
{indent}    avg_loss[period] = np.mean(losses[1:period + 1])
{indent}    for i in range(period + 1, len(source)):
{indent}        avg_gain[i] = alpha * gains[i] + (1 - alpha) * avg_gain[i - 1]
{indent}        avg_loss[i] = alpha * losses[i] + (1 - alpha) * avg_loss[i - 1]
{indent}    rs = avg_gain / (avg_loss + 1e-10)
{indent}    rsi = 100 - (100 / (1 + rs))
{indent}    rsi[:period] = np.nan
{indent}    return rsi
{indent}{var_name} = {{'rsi': calc_rsi_{var_name}({source})}}
"""
        return code, var_name

    def _gen_macd(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate MACD indicator code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        fast = block.parameters.get("fast_period", 12)
        slow = block.parameters.get("slow_period", 26)
        signal = block.parameters.get("signal_period", 9)
        source = inputs.get("source", "candles['close']")

        code = f"""
{indent}# MACD: {block.name}
{indent}def calc_ema(src, period):
{indent}    alpha = 2 / (period + 1)
{indent}    ema = np.zeros_like(src, dtype=float)
{indent}    ema[0] = src[0]
{indent}    for i in range(1, len(src)):
{indent}        ema[i] = alpha * src[i] + (1 - alpha) * ema[i - 1]
{indent}    return ema
{indent}macd_fast_{var_name} = calc_ema({source}, {fast})
{indent}macd_slow_{var_name} = calc_ema({source}, {slow})
{indent}macd_line_{var_name} = macd_fast_{var_name} - macd_slow_{var_name}
{indent}signal_line_{var_name} = calc_ema(macd_line_{var_name}, {signal})
{indent}histogram_{var_name} = macd_line_{var_name} - signal_line_{var_name}
{indent}{var_name} = {{
{indent}    'macd_line': macd_line_{var_name},
{indent}    'signal_line': signal_line_{var_name},
{indent}    'histogram': histogram_{var_name},
{indent}}}
"""
        return code, var_name

    def _gen_bollinger(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate Bollinger Bands code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        period = block.parameters.get("period", 20)
        std_dev = block.parameters.get("std_dev", 2.0)
        source = inputs.get("source", "candles['close']")

        code = f"""
{indent}# Bollinger Bands: {block.name}
{indent}bb_source_{var_name} = {source}
{indent}bb_sma_{var_name} = np.convolve(bb_source_{var_name}, np.ones({period}) / {period}, mode='full')[:{period}+len(bb_source_{var_name})-{period}]
{indent}bb_sma_{var_name} = np.concatenate([np.full({period}-1, np.nan), bb_sma_{var_name}])[:len(bb_source_{var_name})]
{indent}bb_std_{var_name} = np.full_like(bb_source_{var_name}, np.nan, dtype=float)
{indent}for i in range({period} - 1, len(bb_source_{var_name})):
{indent}    bb_std_{var_name}[i] = np.std(bb_source_{var_name}[i - {period} + 1:i + 1])
{indent}{var_name} = {{
{indent}    'upper': bb_sma_{var_name} + {std_dev} * bb_std_{var_name},
{indent}    'middle': bb_sma_{var_name},
{indent}    'lower': bb_sma_{var_name} - {std_dev} * bb_std_{var_name},
{indent}}}
"""
        return code, var_name

    def _gen_ema(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate EMA code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        period = block.parameters.get("period", 20)
        source = inputs.get("source", "candles['close']")

        code = f"""
{indent}# EMA: {block.name}
{indent}def calc_ema_{var_name}(src, period={period}):
{indent}    alpha = 2 / (period + 1)
{indent}    ema = np.zeros_like(src, dtype=float)
{indent}    ema[0] = src[0]
{indent}    for i in range(1, len(src)):
{indent}        ema[i] = alpha * src[i] + (1 - alpha) * ema[i - 1]
{indent}    return ema
{indent}{var_name} = {{'ema': calc_ema_{var_name}({source})}}
"""
        return code, var_name

    def _gen_sma(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate SMA code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        period = block.parameters.get("period", 20)
        source = inputs.get("source", "candles['close']")

        code = f"""
{indent}# SMA: {block.name}
{indent}sma_vals_{var_name} = np.convolve({source}, np.ones({period}) / {period}, mode='full')[:len({source})]
{indent}sma_vals_{var_name}[:{period}-1] = np.nan
{indent}{var_name} = {{'sma': sma_vals_{var_name}}}
"""
        return code, var_name

    def _gen_atr(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate ATR code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        period = block.parameters.get("period", 14)
        high = inputs.get("high", "candles['high']")
        low = inputs.get("low", "candles['low']")
        close = inputs.get("close", "candles['close']")

        code = f"""
{indent}# ATR: {block.name}
{indent}atr_high_{var_name} = {high}
{indent}atr_low_{var_name} = {low}
{indent}atr_close_{var_name} = {close}
{indent}atr_prev_close_{var_name} = np.roll(atr_close_{var_name}, 1)
{indent}atr_prev_close_{var_name}[0] = atr_close_{var_name}[0]
{indent}tr_{var_name} = np.maximum(
{indent}    atr_high_{var_name} - atr_low_{var_name},
{indent}    np.maximum(
{indent}        np.abs(atr_high_{var_name} - atr_prev_close_{var_name}),
{indent}        np.abs(atr_low_{var_name} - atr_prev_close_{var_name})
{indent}    )
{indent})
{indent}atr_alpha_{var_name} = 2 / ({period} + 1)
{indent}atr_vals_{var_name} = np.zeros_like(tr_{var_name}, dtype=float)
{indent}atr_vals_{var_name}[0] = tr_{var_name}[0]
{indent}for i in range(1, len(tr_{var_name})):
{indent}    atr_vals_{var_name}[i] = atr_alpha_{var_name} * tr_{var_name}[i] + (1 - atr_alpha_{var_name}) * atr_vals_{var_name}[i - 1]
{indent}{var_name} = {{'atr': atr_vals_{var_name}, 'tr': tr_{var_name}}}
"""
        return code, var_name

    def _gen_stochastic(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate Stochastic code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        k_period = block.parameters.get("k_period", 14)
        d_period = block.parameters.get("d_period", 3)

        code = f"""
{indent}# Stochastic: {block.name}
{indent}stoch_k_{var_name} = np.full(len(candles['close']), np.nan, dtype=float)
{indent}for i in range({k_period} - 1, len(candles['close'])):
{indent}    highest = np.max(candles['high'][i - {k_period} + 1:i + 1])
{indent}    lowest = np.min(candles['low'][i - {k_period} + 1:i + 1])
{indent}    if highest - lowest > 0:
{indent}        stoch_k_{var_name}[i] = (candles['close'][i] - lowest) / (highest - lowest) * 100
{indent}stoch_d_{var_name} = np.convolve(stoch_k_{var_name}, np.ones({d_period}) / {d_period}, mode='full')[:len(stoch_k_{var_name})]
{indent}{var_name} = {{'k': stoch_k_{var_name}, 'd': stoch_d_{var_name}}}
"""
        return code, var_name

    def _gen_custom_indicator(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate custom indicator code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        custom_code = block.custom_code or "return {'result': source}"

        code = f"""
{indent}# Custom Indicator: {block.name}
{indent}def custom_{var_name}(source):
{indent}    {custom_code.replace(chr(10), chr(10) + indent + "    ")}
{indent}{var_name} = custom_{var_name}({inputs.get("source", "candles['close']")})
"""
        return code, var_name

    def _gen_compare(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate comparison condition code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        operator = block.parameters.get("operator", ">")
        left = inputs.get("left", "0")
        right = inputs.get("right", "0")

        code = f"""
{indent}# Compare: {block.name}
{indent}{var_name} = {{'result': {left} {operator} {right}}}
"""
        return code, var_name

    def _gen_cross(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate crossover condition code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        fast = inputs.get("fast", "np.zeros(1)")
        slow = inputs.get("slow", "np.zeros(1)")

        code = f"""
{indent}# Crossover: {block.name}
{indent}cross_fast_{var_name} = {fast}
{indent}cross_slow_{var_name} = {slow}
{indent}cross_above_{var_name} = np.zeros(len(cross_fast_{var_name}), dtype=bool)
{indent}cross_below_{var_name} = np.zeros(len(cross_fast_{var_name}), dtype=bool)
{indent}for i in range(1, len(cross_fast_{var_name})):
{indent}    cross_above_{var_name}[i] = cross_fast_{var_name}[i] > cross_slow_{var_name}[i] and cross_fast_{var_name}[i-1] <= cross_slow_{var_name}[i-1]
{indent}    cross_below_{var_name}[i] = cross_fast_{var_name}[i] < cross_slow_{var_name}[i] and cross_fast_{var_name}[i-1] >= cross_slow_{var_name}[i-1]
{indent}{var_name} = {{'cross_above': cross_above_{var_name}, 'cross_below': cross_below_{var_name}}}
"""
        return code, var_name

    def _gen_threshold(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate threshold condition code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        threshold = block.parameters.get("threshold", 50.0)
        value = inputs.get("value", "np.zeros(1)")

        code = f"""
{indent}# Threshold: {block.name}
{indent}thresh_val_{var_name} = {value}
{indent}{var_name} = {{
{indent}    'above': thresh_val_{var_name} > {threshold},
{indent}    'below': thresh_val_{var_name} < {threshold},
{indent}}}
"""
        return code, var_name

    def _gen_and(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate AND condition code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        cond1 = inputs.get("condition1", "False")
        cond2 = inputs.get("condition2", "False")

        code = f"""
{indent}# AND: {block.name}
{indent}{var_name} = {{'result': np.logical_and({cond1}, {cond2})}}
"""
        return code, var_name

    def _gen_or(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate OR condition code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        cond1 = inputs.get("condition1", "False")
        cond2 = inputs.get("condition2", "False")

        code = f"""
{indent}# OR: {block.name}
{indent}{var_name} = {{'result': np.logical_or({cond1}, {cond2})}}
"""
        return code, var_name

    def _gen_not(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate NOT condition code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        cond = inputs.get("condition", "False")

        code = f"""
{indent}# NOT: {block.name}
{indent}{var_name} = {{'result': np.logical_not({cond})}}
"""
        return code, var_name

    def _gen_buy(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate buy action code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        size_pct = block.parameters.get("size_pct", 100.0)
        order_type = block.parameters.get("order_type", "market")
        trigger = inputs.get("trigger", "False")

        code = f"""
{indent}# Buy: {block.name}
{indent}{var_name} = {{
{indent}    'signal': {trigger},
{indent}    'action': 'buy',
{indent}    'size_pct': {size_pct},
{indent}    'order_type': '{order_type}',
{indent}}}
"""
        return code, var_name

    def _gen_sell(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate sell action code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        size_pct = block.parameters.get("size_pct", 100.0)
        order_type = block.parameters.get("order_type", "market")
        trigger = inputs.get("trigger", "False")

        code = f"""
{indent}# Sell: {block.name}
{indent}{var_name} = {{
{indent}    'signal': {trigger},
{indent}    'action': 'sell',
{indent}    'size_pct': {size_pct},
{indent}    'order_type': '{order_type}',
{indent}}}
"""
        return code, var_name

    def _gen_stop_loss(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate stop loss code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        stop_type = block.parameters.get("stop_type", "percent")
        value = block.parameters.get("value", 2.0)

        code = f"""
{indent}# Stop Loss: {block.name}
{indent}{var_name} = {{
{indent}    'action': 'stop_loss',
{indent}    'stop_type': '{stop_type}',
{indent}    'value': {value},
{indent}}}
"""
        return code, var_name

    def _gen_take_profit(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate take profit code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        tp_type = block.parameters.get("tp_type", "percent")
        value = block.parameters.get("value", 4.0)

        code = f"""
{indent}# Take Profit: {block.name}
{indent}{var_name} = {{
{indent}    'action': 'take_profit',
{indent}    'tp_type': '{tp_type}',
{indent}    'value': {value},
{indent}}}
"""
        return code, var_name

    def _gen_time_filter(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate time filter code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        start_hour = block.parameters.get("start_hour", 8)
        end_hour = block.parameters.get("end_hour", 20)
        signal = inputs.get("signal", "True")

        code = f"""
{indent}# Time Filter: {block.name}
{indent}# Note: Time filtering requires timestamp data
{indent}tf_signal_{var_name} = {signal}
{indent}# Apply time filter: {start_hour}:00 - {end_hour}:00
{indent}{var_name} = {{'filtered': tf_signal_{var_name}}}
"""
        return code, var_name

    def _gen_volume_filter(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate volume filter code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        min_ratio = block.parameters.get("min_volume_ratio", 1.5)
        lookback = block.parameters.get("lookback", 20)
        signal = inputs.get("signal", "True")
        volume = inputs.get("volume", "candles['volume']")

        code = f"""
{indent}# Volume Filter: {block.name}
{indent}vf_signal_{var_name} = {signal}
{indent}vf_volume_{var_name} = {volume}
{indent}vf_avg_volume_{var_name} = np.convolve(vf_volume_{var_name}, np.ones({lookback}) / {lookback}, mode='full')[:len(vf_volume_{var_name})]
{indent}vf_high_volume_{var_name} = vf_volume_{var_name} > ({min_ratio} * vf_avg_volume_{var_name})
{indent}{var_name} = {{'filtered': np.logical_and(vf_signal_{var_name}, vf_high_volume_{var_name})}}
"""
        return code, var_name

    def _gen_position_size(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate position sizing code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        method = block.parameters.get("method", "fixed")
        risk_per_trade = block.parameters.get("risk_per_trade", 1.0)
        max_position = block.parameters.get("max_position_pct", 10.0)

        code = f"""
{indent}# Position Sizing: {block.name}
{indent}# Method: {method}, Risk: {risk_per_trade}%, Max: {max_position}%
{indent}{var_name} = {{
{indent}    'method': '{method}',
{indent}    'risk_per_trade': {risk_per_trade},
{indent}    'max_position_pct': {max_position},
{indent}}}
"""
        return code, var_name

    def _gen_output(
        self, block: StrategyBlock, inputs: Dict[str, str], options: GenerationOptions
    ) -> tuple:
        """Generate output block code"""
        var_name = self._make_var_name(block)
        indent = options.indent * 2
        signal = inputs.get("signal", "None")

        code = f"""
{indent}# Output: {block.name}
{indent}{var_name} = {{'output': {signal}}}
"""
        return code, var_name


# Code Templates
TEMPLATE_BASIC = '''"""
{description}

Version: {version}
Generated by Visual Strategy Builder
"""

{imports}

class {strategy_name}:
    """Generated strategy: {strategy_name}"""

    PARAMETERS = {{
{parameters}
    }}

    def __init__(self):
{init_code}

    def calculate(self, candles: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
        """Calculate strategy signals"""
        signals = []
{calculate_code}
{signal_code}
        return signals
'''

TEMPLATE_BACKTEST = '''"""
{description}

Version: {version}
Generated by Visual Strategy Builder
Optimized for backtesting
"""

{imports}

class {strategy_name}:
    """
    Backtesting-ready strategy

    Timeframe: {timeframe}
    Symbols: [{symbols}]
    """

    PARAMETERS = {{
{parameters}
    }}

    def __init__(self, **kwargs):
        """Initialize strategy with optional parameter overrides"""
{init_code}

        # Override with kwargs
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        # Performance tracking
        self.signals_generated = 0
        self.last_signal_time = None

    def calculate(self, candles: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
        """
        Calculate strategy signals from candle data

        Args:
            candles: Dictionary with 'open', 'high', 'low', 'close', 'volume' arrays

        Returns:
            List of signal dictionaries
        """
        signals = []

        # Validate input
        required = ['open', 'high', 'low', 'close', 'volume']
        for key in required:
            if key not in candles:
                return []
{calculate_code}
{signal_code}

        self.signals_generated += len(signals)
        return signals

    def get_parameter_ranges(self) -> Dict[str, tuple]:
        """Get parameter optimization ranges"""
        return {{
            name: (val * 0.5, val * 2.0, val * 0.1)
            for name, val in self.PARAMETERS.items()
            if isinstance(val, (int, float))
        }}
'''

TEMPLATE_LIVE = '''"""
{description}

Version: {version}
Generated by Visual Strategy Builder
Optimized for live trading
"""

{imports}
import asyncio
import logging

logger = logging.getLogger(__name__)

class {strategy_name}:
    """
    Live trading strategy

    Timeframe: {timeframe}
    Symbols: [{symbols}]
    """

    PARAMETERS = {{
{parameters}
    }}

    def __init__(self, **kwargs):
        """Initialize strategy"""
{init_code}

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.is_running = False
        self.current_position = None
        self.pending_orders = []

    async def on_candle(self, candles: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
        """Process new candle data"""
        try:
            signals = self.calculate(candles)

            for signal in signals:
                logger.info(f"Signal generated: {{signal}}")

            return signals
        except Exception as e:
            logger.error(f"Error processing candle: {{e}}")
            return []

    def calculate(self, candles: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
        """Calculate strategy signals"""
        signals = []
{calculate_code}
{signal_code}
        return signals

    async def start(self):
        """Start live trading"""
        self.is_running = True
        logger.info(f"{{self.__class__.__name__}} started")

    async def stop(self):
        """Stop live trading"""
        self.is_running = False
        logger.info(f"{{self.__class__.__name__}} stopped")
'''

TEMPLATE_OPTIMIZATION = '''"""
{description}

Version: {version}
Generated by Visual Strategy Builder
Optimized for parameter optimization
"""

{imports}
from optuna import Trial

class {strategy_name}:
    """
    Optimization-ready strategy
    """

    PARAMETERS = {{
{parameters}
    }}

    @classmethod
    def suggest_parameters(cls, trial: Trial) -> Dict[str, Any]:
        """Suggest parameters for Optuna optimization"""
        params = {{}}

        for name, default in cls.PARAMETERS.items():
            if isinstance(default, int):
                params[name] = trial.suggest_int(name, max(1, default // 2), default * 2)
            elif isinstance(default, float):
                params[name] = trial.suggest_float(name, default * 0.5, default * 2.0)
            elif isinstance(default, bool):
                params[name] = trial.suggest_categorical(name, [True, False])

        return params

    def __init__(self, **kwargs):
        """Initialize with parameters"""
{init_code}

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def calculate(self, candles: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
        """Calculate strategy signals"""
        signals = []
{calculate_code}
{signal_code}
        return signals

    def evaluate(self, candles: Dict[str, np.ndarray]) -> float:
        """Evaluate strategy performance (for optimization)"""
        signals = self.calculate(candles)

        # Simple evaluation: count profitable signals
        # Override this for custom evaluation logic
        return len(signals)
'''
