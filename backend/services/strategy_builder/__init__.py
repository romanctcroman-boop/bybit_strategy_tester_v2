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
    "BlockType",
    # Code Generator
    "CodeGenerator",
    "CodeTemplate",
    "ConnectionType",
    "CustomIndicator",
    "GeneratedStrategy",
    "GenerationOptions",
    # Indicators
    "IndicatorLibrary",
    "IndicatorParameter",
    "IndicatorType",
    "StrategyBlock",
    # Builder
    "StrategyBuilder",
    "StrategyGraph",
    "StrategyTemplate",
    # Templates
    "StrategyTemplateManager",
    # Validator
    "StrategyValidator",
    "TemplateCategory",
    "ValidationError",
    "ValidationResult",
    "ValidationWarning",
]
