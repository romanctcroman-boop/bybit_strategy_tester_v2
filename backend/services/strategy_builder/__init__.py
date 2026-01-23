"""
Strategy Builder Module

Visual strategy builder with:
- Block-based strategy composition
- Custom indicator support
- Code generation
- Strategy templates
- Validation and testing
"""

from .builder import (
    BlockType,
    ConnectionType,
    StrategyBlock,
    StrategyBuilder,
    StrategyGraph,
)
from .code_generator import (
    CodeGenerator,
    CodeTemplate,
    GeneratedStrategy,
    GenerationOptions,
)
from .indicators import (
    CustomIndicator,
    IndicatorLibrary,
    IndicatorParameter,
    IndicatorType,
)
from .templates import (
    StrategyTemplate,
    StrategyTemplateManager,
    TemplateCategory,
)
from .validator import (
    StrategyValidator,
    ValidationError,
    ValidationResult,
    ValidationWarning,
)

__all__ = [
    # Builder
    "StrategyBuilder",
    "StrategyBlock",
    "BlockType",
    "ConnectionType",
    "StrategyGraph",
    # Indicators
    "IndicatorLibrary",
    "CustomIndicator",
    "IndicatorType",
    "IndicatorParameter",
    # Code Generator
    "CodeGenerator",
    "GeneratedStrategy",
    "CodeTemplate",
    "GenerationOptions",
    # Templates
    "StrategyTemplateManager",
    "StrategyTemplate",
    "TemplateCategory",
    # Validator
    "StrategyValidator",
    "ValidationResult",
    "ValidationError",
    "ValidationWarning",
]
