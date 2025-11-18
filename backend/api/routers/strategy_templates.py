"""
Strategy Template Library API

Provides pre-built strategy templates with default parameters:
- Bollinger Bands Mean Reversion
- RSI Oversold/Overbought
- Moving Average Crossover

Each template includes:
- Parameter schema with default values
- Parameter validation rules
- Strategy description and use cases
- Expected performance characteristics
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/strategies/templates", tags=["strategy-templates"])


class ParameterSchema(BaseModel):
    """Schema for strategy parameter"""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (int, float, bool, string)")
    default: Any = Field(..., description="Default value")
    min: float | None = Field(None, description="Minimum value (for numeric types)")
    max: float | None = Field(None, description="Maximum value (for numeric types)")
    description: str = Field(..., description="Parameter description")
    options: list[Any] | None = Field(None, description="Valid options (for categorical parameters)")


class StrategyTemplate(BaseModel):
    """Strategy template definition"""
    id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Strategy description")
    category: str = Field(..., description="Strategy category")
    parameters: list[ParameterSchema] = Field(..., description="Parameter schema")
    use_cases: list[str] = Field(..., description="Recommended use cases")
    expected_performance: dict[str, str] = Field(..., description="Expected performance characteristics")


# ============================================================================
# TEMPLATE DEFINITIONS
# ============================================================================

STRATEGY_TEMPLATES = {
    "bollinger_mean_reversion": {
        "id": "bollinger_mean_reversion",
        "name": "Bollinger Bands Mean Reversion",
        "description": "Mean-reversion strategy using Bollinger Bands. Enters when price touches bands (oversold/overbought) and exits at middle band.",
        "category": "Indicator-Based",
        "parameters": [
            {
                "name": "bb_period",
                "type": "int",
                "default": 20,
                "min": 5,
                "max": 100,
                "description": "Bollinger Bands period (rolling window for SMA and standard deviation)",
                "options": None
            },
            {
                "name": "bb_std_dev",
                "type": "float",
                "default": 2.0,
                "min": 0.5,
                "max": 5.0,
                "description": "Standard deviation multiplier for band width",
                "options": None
            },
            {
                "name": "entry_threshold_pct",
                "type": "float",
                "default": 0.05,
                "min": 0.0,
                "max": 2.0,
                "description": "Entry threshold percentage beyond band (0.05 = 0.05%)",
                "options": None
            },
            {
                "name": "stop_loss_pct",
                "type": "float",
                "default": 0.8,
                "min": 0.1,
                "max": 5.0,
                "description": "Stop loss percentage from entry price",
                "options": None
            },
            {
                "name": "max_holding_bars",
                "type": "int",
                "default": 48,
                "min": 1,
                "max": 500,
                "description": "Maximum bars to hold position before forced exit",
                "options": None
            }
        ],
        "use_cases": [
            "Range-bound markets with low volatility",
            "Sideways consolidation periods",
            "Mean-reverting cryptocurrencies (BTC, ETH on 5m-1h timeframes)",
            "High-liquidity pairs with tight spreads"
        ],
        "expected_performance": {
            "win_rate": "55-65%",
            "sharpe_ratio": "1.2-2.0",
            "max_drawdown": "5-15%",
            "avg_trade_duration": "2-8 hours (on 5m timeframe)",
            "best_timeframes": "5m, 15m, 1h",
            "best_symbols": "BTCUSDT, ETHUSDT, high-volume pairs"
        }
    },
    
    "rsi_oversold_overbought": {
        "id": "rsi_oversold_overbought",
        "name": "RSI Oversold/Overbought",
        "description": "Momentum strategy using RSI indicator. Enters when RSI reaches extreme levels (oversold <30, overbought >70) with Support/Resistance confirmation.",
        "category": "Indicator-Based",
        "parameters": [
            {
                "name": "rsi_period",
                "type": "int",
                "default": 14,
                "min": 2,
                "max": 50,
                "description": "RSI calculation period (standard is 14)",
                "options": None
            },
            {
                "name": "rsi_oversold",
                "type": "float",
                "default": 30.0,
                "min": 10.0,
                "max": 40.0,
                "description": "RSI oversold threshold for LONG entries",
                "options": None
            },
            {
                "name": "rsi_overbought",
                "type": "float",
                "default": 70.0,
                "min": 60.0,
                "max": 90.0,
                "description": "RSI overbought threshold for SHORT entries",
                "options": None
            },
            {
                "name": "lookback_bars",
                "type": "int",
                "default": 100,
                "min": 20,
                "max": 500,
                "description": "Lookback period for Support/Resistance detection",
                "options": None
            },
            {
                "name": "stop_loss_pct",
                "type": "float",
                "default": 0.8,
                "min": 0.1,
                "max": 5.0,
                "description": "Stop loss percentage from entry price",
                "options": None
            },
            {
                "name": "max_holding_bars",
                "type": "int",
                "default": 48,
                "min": 1,
                "max": 500,
                "description": "Maximum bars to hold position before forced exit",
                "options": None
            }
        ],
        "use_cases": [
            "Trending markets with corrections",
            "Cryptocurrency pairs with strong momentum",
            "Swing trading on 1h-4h timeframes",
            "Markets with clear support/resistance levels"
        ],
        "expected_performance": {
            "win_rate": "50-60%",
            "sharpe_ratio": "1.0-1.8",
            "max_drawdown": "8-20%",
            "avg_trade_duration": "4-24 hours (on 1h timeframe)",
            "best_timeframes": "1h, 4h, 1d",
            "best_symbols": "BTCUSDT, ETHUSDT, trending altcoins"
        }
    },
    
    "ma_crossover": {
        "id": "ma_crossover",
        "name": "Moving Average Crossover",
        "description": "Classic trend-following strategy. Enters LONG when fast MA crosses above slow MA, SHORT when fast MA crosses below slow MA. Uses EMA for faster response to price changes.",
        "category": "Indicator-Based",
        "parameters": [
            {
                "name": "fast_period",
                "type": "int",
                "default": 10,
                "min": 2,
                "max": 50,
                "description": "Fast moving average period (shorter timeframe)",
                "options": None
            },
            {
                "name": "slow_period",
                "type": "int",
                "default": 30,
                "min": 10,
                "max": 200,
                "description": "Slow moving average period (longer timeframe)",
                "options": None
            },
            {
                "name": "ma_type",
                "type": "string",
                "default": "EMA",
                "min": None,
                "max": None,
                "description": "Moving average type",
                "options": ["SMA", "EMA", "WMA"]
            },
            {
                "name": "stop_loss_pct",
                "type": "float",
                "default": 1.5,
                "min": 0.5,
                "max": 10.0,
                "description": "Stop loss percentage from entry price",
                "options": None
            },
            {
                "name": "take_profit_pct",
                "type": "float",
                "default": 3.0,
                "min": 0.5,
                "max": 20.0,
                "description": "Take profit percentage from entry price",
                "options": None
            },
            {
                "name": "min_separation_pct",
                "type": "float",
                "default": 0.1,
                "min": 0.0,
                "max": 2.0,
                "description": "Minimum separation between MAs to confirm trend (prevents choppy signals)",
                "options": None
            }
        ],
        "use_cases": [
            "Strong trending markets (bull or bear)",
            "Longer timeframes (4h, 1d) for swing trading",
            "Cryptocurrencies with sustained directional movement",
            "Lower frequency trading (2-10 trades per month)"
        ],
        "expected_performance": {
            "win_rate": "40-50%",
            "sharpe_ratio": "0.8-1.5",
            "max_drawdown": "15-30%",
            "avg_trade_duration": "1-7 days (on 4h timeframe)",
            "best_timeframes": "4h, 1d, 1w",
            "best_symbols": "BTCUSDT, ETHUSDT, major altcoins in trending markets"
        }
    }
}


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/", response_model=list[StrategyTemplate])
async def list_strategy_templates(
    category: str | None = Query(None, description="Filter by category")
) -> list[StrategyTemplate]:
    """
    Get list of available strategy templates
    
    Returns all pre-built strategy templates with complete parameter schemas.
    Each template is production-ready and can be used immediately for backtesting.
    
    Args:
        category: Optional filter by strategy category (e.g., "Indicator-Based")
    
    Returns:
        List of strategy templates with parameters, use cases, and expected performance
    """
    templates = list(STRATEGY_TEMPLATES.values())
    
    if category:
        templates = [t for t in templates if t["category"].lower() == category.lower()]
    
    return templates


@router.get("/{template_id}", response_model=StrategyTemplate)
async def get_strategy_template(template_id: str) -> StrategyTemplate:
    """
    Get specific strategy template by ID
    
    Returns detailed information about a single strategy template including:
    - Complete parameter schema with validation rules
    - Default values and recommended ranges
    - Use cases and performance expectations
    - Implementation details
    
    Args:
        template_id: Template identifier (e.g., "bollinger_mean_reversion")
    
    Returns:
        Complete strategy template definition
    
    Raises:
        404: Template not found
    """
    if template_id not in STRATEGY_TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_id}' not found. Available: {list(STRATEGY_TEMPLATES.keys())}"
        )
    
    return STRATEGY_TEMPLATES[template_id]


@router.get("/categories/list")
async def list_template_categories() -> dict[str, Any]:
    """
    Get list of available template categories
    
    Returns unique categories across all templates with counts.
    Useful for filtering templates by type.
    
    Returns:
        Dict with category names and counts
    """
    categories = {}
    for template in STRATEGY_TEMPLATES.values():
        category = template["category"]
        categories[category] = categories.get(category, 0) + 1
    
    return {
        "categories": categories,
        "total_templates": len(STRATEGY_TEMPLATES)
    }


@router.post("/validate")
async def validate_strategy_parameters(
    template_id: str = Query(..., description="Template ID to validate against"),
    parameters: dict[str, Any] = ...
) -> dict[str, Any]:
    """
    Validate strategy parameters against template schema
    
    Checks if provided parameters:
    - Match expected types
    - Fall within valid ranges
    - Include all required parameters
    - Don't include unknown parameters
    
    Args:
        template_id: Template to validate against
        parameters: Parameter dict to validate
    
    Returns:
        Validation result with errors (if any) and normalized parameters
    """
    if template_id not in STRATEGY_TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_id}' not found"
        )
    
    template = STRATEGY_TEMPLATES[template_id]
    param_schema = {p["name"]: p for p in template["parameters"]}
    
    errors = []
    normalized = {}
    
    # Check for unknown parameters
    for param_name in parameters:
        if param_name not in param_schema:
            errors.append(f"Unknown parameter: '{param_name}'")
    
    # Validate each parameter in schema
    for param_name, schema in param_schema.items():
        value = parameters.get(param_name)
        
        # Use default if not provided
        if value is None:
            normalized[param_name] = schema["default"]
            continue
        
        # Type validation
        expected_type = schema["type"]
        if expected_type == "int" and not isinstance(value, int):
            errors.append(f"Parameter '{param_name}' must be int, got {type(value).__name__}")
            continue
        elif expected_type == "float" and not isinstance(value, (int, float)):
            errors.append(f"Parameter '{param_name}' must be float, got {type(value).__name__}")
            continue
        elif expected_type == "string" and not isinstance(value, str):
            errors.append(f"Parameter '{param_name}' must be string, got {type(value).__name__}")
            continue
        elif expected_type == "bool" and not isinstance(value, bool):
            errors.append(f"Parameter '{param_name}' must be bool, got {type(value).__name__}")
            continue
        
        # Range validation for numeric types
        if expected_type in ["int", "float"]:
            if schema["min"] is not None and value < schema["min"]:
                errors.append(f"Parameter '{param_name}' must be >= {schema['min']}, got {value}")
            if schema["max"] is not None and value > schema["max"]:
                errors.append(f"Parameter '{param_name}' must be <= {schema['max']}, got {value}")
        
        # Options validation for categorical parameters
        if schema["options"] is not None and value not in schema["options"]:
            errors.append(f"Parameter '{param_name}' must be one of {schema['options']}, got {value}")
        
        normalized[param_name] = value
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "normalized_parameters": normalized if len(errors) == 0 else None
    }
