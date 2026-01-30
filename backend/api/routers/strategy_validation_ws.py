"""
WebSocket Strategy Validation Endpoint.

Provides real-time validation for Strategy Builder:
- Instant parameter validation on change
- Block connection validation
- Strategy completeness checks
- Live error/warning feedback

Protocol:
1. Client connects: ws://host/api/v1/strategy-builder/ws/validate
2. Client sends validation requests as JSON
3. Server responds with validation results in real-time
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy-builder", tags=["Strategy Builder WebSocket"])


# =============================================================================
# MODELS
# =============================================================================


class ValidationSeverity(str, Enum):
    """Validation message severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"


class MessageType(str, Enum):
    """WebSocket message types."""

    VALIDATE_BLOCK = "validate_block"
    VALIDATE_PARAM = "validate_param"
    VALIDATE_CONNECTION = "validate_connection"
    VALIDATE_STRATEGY = "validate_strategy"
    VALIDATION_RESULT = "validation_result"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class ValidationMessage:
    """Individual validation message."""

    severity: ValidationSeverity
    message: str
    field: str | None = None
    code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "message": self.message,
            "field": self.field,
            "code": self.code,
        }


@dataclass
class ValidationResult:
    """Complete validation result."""

    valid: bool
    messages: list[ValidationMessage]
    block_id: str | None = None
    param_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "messages": [m.to_dict() for m in self.messages],
            "block_id": self.block_id,
            "param_name": self.param_name,
        }


class ValidateBlockRequest(BaseModel):
    """Request to validate a block."""

    type: str = MessageType.VALIDATE_BLOCK.value
    block_id: str
    block_type: str
    params: dict[str, Any] = Field(default_factory=dict)


class ValidateParamRequest(BaseModel):
    """Request to validate a single parameter."""

    type: str = MessageType.VALIDATE_PARAM.value
    block_id: str
    block_type: str
    param_name: str
    param_value: Any


class ValidateConnectionRequest(BaseModel):
    """Request to validate a connection between blocks."""

    type: str = MessageType.VALIDATE_CONNECTION.value
    source_block_id: str
    source_block_type: str
    source_output: str
    target_block_id: str
    target_block_type: str
    target_input: str


class ValidateStrategyRequest(BaseModel):
    """Request to validate entire strategy."""

    type: str = MessageType.VALIDATE_STRATEGY.value
    blocks: list[dict[str, Any]]
    connections: list[dict[str, Any]]


# =============================================================================
# VALIDATION RULES
# =============================================================================


BLOCK_VALIDATION_RULES: dict[str, dict[str, dict[str, Any]]] = {
    # Price Action
    "price_above": {
        "threshold": {"type": "number", "min": 0, "required": True},
    },
    "price_below": {
        "threshold": {"type": "number", "min": 0, "required": True},
    },
    "price_cross_above": {
        "threshold": {"type": "number", "min": 0, "required": True},
    },
    "price_cross_below": {
        "threshold": {"type": "number", "min": 0, "required": True},
    },
    # RSI
    "rsi": {
        "period": {"type": "integer", "min": 2, "max": 500, "default": 14},
        "overbought": {"type": "number", "min": 50, "max": 100, "default": 70},
        "oversold": {"type": "number", "min": 0, "max": 50, "default": 30},
    },
    "rsi_cross_above": {
        "period": {"type": "integer", "min": 2, "max": 500, "default": 14},
        "level": {"type": "number", "min": 0, "max": 100, "default": 30},
    },
    "rsi_cross_below": {
        "period": {"type": "integer", "min": 2, "max": 500, "default": 14},
        "level": {"type": "number", "min": 0, "max": 100, "default": 70},
    },
    "rsi_divergence": {
        "period": {"type": "integer", "min": 2, "max": 500, "default": 14},
        "lookback": {"type": "integer", "min": 5, "max": 200, "default": 20},
        "divergence_type": {"type": "select", "options": ["bullish", "bearish", "both"], "default": "both"},
    },
    # MACD
    "macd_cross": {
        "fast_period": {"type": "integer", "min": 2, "max": 200, "default": 12},
        "slow_period": {"type": "integer", "min": 2, "max": 200, "default": 26},
        "signal_period": {"type": "integer", "min": 2, "max": 100, "default": 9},
    },
    "macd_histogram": {
        "fast_period": {"type": "integer", "min": 2, "max": 200, "default": 12},
        "slow_period": {"type": "integer", "min": 2, "max": 200, "default": 26},
        "signal_period": {"type": "integer", "min": 2, "max": 100, "default": 9},
        "threshold": {"type": "number", "min": 0, "default": 0},
    },
    "macd_divergence": {
        "fast_period": {"type": "integer", "min": 2, "max": 200, "default": 12},
        "slow_period": {"type": "integer", "min": 2, "max": 200, "default": 26},
        "signal_period": {"type": "integer", "min": 2, "max": 100, "default": 9},
        "lookback": {"type": "integer", "min": 5, "max": 200, "default": 20},
    },
    # Moving Averages
    "ma_cross": {
        "fast_period": {"type": "integer", "min": 2, "max": 500, "default": 9},
        "slow_period": {"type": "integer", "min": 2, "max": 500, "default": 21},
        "ma_type": {"type": "select", "options": ["sma", "ema", "wma"], "default": "ema"},
    },
    "price_above_ma": {
        "period": {"type": "integer", "min": 2, "max": 500, "default": 20},
        "ma_type": {"type": "select", "options": ["sma", "ema", "wma"], "default": "sma"},
    },
    "price_below_ma": {
        "period": {"type": "integer", "min": 2, "max": 500, "default": 20},
        "ma_type": {"type": "select", "options": ["sma", "ema", "wma"], "default": "sma"},
    },
    # Bollinger Bands
    "bb_breakout": {
        "period": {"type": "integer", "min": 5, "max": 200, "default": 20},
        "std_dev": {"type": "number", "min": 0.5, "max": 5, "default": 2},
    },
    "bb_squeeze": {
        "period": {"type": "integer", "min": 5, "max": 200, "default": 20},
        "std_dev": {"type": "number", "min": 0.5, "max": 5, "default": 2},
        "squeeze_threshold": {"type": "number", "min": 0, "max": 1, "default": 0.1},
    },
    # Stochastic
    "stoch_cross": {
        "k_period": {"type": "integer", "min": 2, "max": 100, "default": 14},
        "d_period": {"type": "integer", "min": 2, "max": 100, "default": 3},
        "smooth_k": {"type": "integer", "min": 1, "max": 50, "default": 3},
    },
    "stoch_overbought": {
        "k_period": {"type": "integer", "min": 2, "max": 100, "default": 14},
        "d_period": {"type": "integer", "min": 2, "max": 100, "default": 3},
        "overbought": {"type": "number", "min": 50, "max": 100, "default": 80},
    },
    "stoch_oversold": {
        "k_period": {"type": "integer", "min": 2, "max": 100, "default": 14},
        "d_period": {"type": "integer", "min": 2, "max": 100, "default": 3},
        "oversold": {"type": "number", "min": 0, "max": 50, "default": 20},
    },
    # Volume
    "volume_spike": {
        "period": {"type": "integer", "min": 2, "max": 200, "default": 20},
        "multiplier": {"type": "number", "min": 1, "max": 10, "default": 2},
    },
    "volume_above_avg": {
        "period": {"type": "integer", "min": 2, "max": 200, "default": 20},
        "multiplier": {"type": "number", "min": 1, "max": 10, "default": 1.5},
    },
    # ATR
    "atr_filter": {
        "period": {"type": "integer", "min": 2, "max": 200, "default": 14},
        "multiplier": {"type": "number", "min": 0.1, "max": 10, "default": 1.5},
    },
    "atr_exit": {
        "period": {"type": "integer", "min": 2, "max": 200, "default": 14},
        "multiplier": {"type": "number", "min": 0.1, "max": 10, "default": 2},
    },
    # Candlestick Patterns
    "engulfing": {
        "direction": {"type": "select", "options": ["bullish", "bearish", "both"], "default": "both"},
    },
    "hammer": {
        "min_wick_ratio": {"type": "number", "min": 1, "max": 5, "default": 2},
    },
    "doji": {
        "body_threshold": {"type": "number", "min": 0, "max": 0.5, "default": 0.1},
    },
    "pin_bar": {
        "min_wick_ratio": {"type": "number", "min": 1.5, "max": 5, "default": 2.5},
    },
    "morning_star": {},
    "evening_star": {},
    "three_soldiers": {},
    "three_crows": {},
    # Exotic Patterns (new!)
    "three_line_strike": {
        "direction": {"type": "select", "options": ["bullish", "bearish", "both"], "default": "both"},
    },
    "kicker": {
        "direction": {"type": "select", "options": ["bullish", "bearish", "both"], "default": "both"},
        "lookback": {"type": "integer", "min": 5, "max": 50, "default": 10},
    },
    "abandoned_baby": {
        "direction": {"type": "select", "options": ["bullish", "bearish", "both"], "default": "both"},
        "doji_threshold": {"type": "number", "min": 0.01, "max": 0.3, "default": 0.1},
    },
    "belt_hold": {
        "direction": {"type": "select", "options": ["bullish", "bearish", "both"], "default": "both"},
        "body_ratio": {"type": "number", "min": 0.5, "max": 1, "default": 0.8},
    },
    "counterattack": {
        "direction": {"type": "select", "options": ["bullish", "bearish", "both"], "default": "both"},
        "tolerance": {"type": "number", "min": 0.001, "max": 0.01, "default": 0.002},
    },
    "gap_pattern": {
        "type": {"type": "select", "options": ["up", "down", "filled", "unfilled"], "default": "up"},
        "min_gap_ratio": {"type": "number", "min": 0.001, "max": 0.05, "default": 0.003},
    },
    "ladder_pattern": {
        "direction": {"type": "select", "options": ["bottom", "top", "both"], "default": "both"},
    },
    "stick_sandwich": {
        "direction": {"type": "select", "options": ["bullish", "bearish", "both"], "default": "both"},
        "tolerance": {"type": "number", "min": 0.001, "max": 0.01, "default": 0.002},
    },
    "homing_pigeon": {},
    "matching_low_high": {
        "type": {"type": "select", "options": ["low", "high", "both"], "default": "both"},
        "tolerance": {"type": "number", "min": 0.0005, "max": 0.01, "default": 0.001},
    },
    # Entry/Exit
    "entry_long": {},
    "entry_short": {},
    "exit_long": {},
    "exit_short": {},
    "stop_loss": {
        "percent": {"type": "number", "min": 0.1, "max": 50, "default": 2},
        "atr_multiplier": {"type": "number", "min": 0.5, "max": 10, "required": False},
    },
    "take_profit": {
        "percent": {"type": "number", "min": 0.1, "max": 100, "default": 4},
        "atr_multiplier": {"type": "number", "min": 0.5, "max": 10, "required": False},
    },
    "trailing_stop": {
        "percent": {"type": "number", "min": 0.1, "max": 50, "default": 1},
        "activation_percent": {"type": "number", "min": 0, "max": 50, "default": 1},
    },
    # Logic
    "and": {},
    "or": {},
    "not": {},
    "delay": {
        "bars": {"type": "integer", "min": 1, "max": 100, "default": 1},
    },
    "sequence": {
        "max_bars": {"type": "integer", "min": 1, "max": 100, "default": 5},
    },
    # Risk Management
    "position_size": {
        "type": {"type": "select", "options": ["fixed", "percent", "kelly"], "default": "percent"},
        "value": {"type": "number", "min": 0.1, "max": 100, "default": 10},
        "max_risk_percent": {"type": "number", "min": 0.1, "max": 50, "default": 2},
    },
    "max_positions": {
        "max": {"type": "integer", "min": 1, "max": 100, "default": 3},
    },
    # ==========================================================================
    # DCA CLOSE CONDITIONS (Session 5.5)
    # ==========================================================================
    "rsi_close": {
        "rsi_close_length": {"type": "integer", "min": 2, "max": 200, "default": 14},
        "rsi_close_min_profit": {"type": "number", "min": 0, "max": 100, "default": 0.5},
        "rsi_close_reach_long_more": {"type": "number", "min": 0, "max": 100, "default": 70},
        "rsi_close_reach_long_less": {"type": "number", "min": 0, "max": 100, "default": 0},
        "rsi_close_reach_short_more": {"type": "number", "min": 0, "max": 100, "default": 100},
        "rsi_close_reach_short_less": {"type": "number", "min": 0, "max": 100, "default": 30},
        "rsi_close_cross_long_level": {"type": "number", "min": 0, "max": 100, "default": 70},
        "rsi_close_cross_short_level": {"type": "number", "min": 0, "max": 100, "default": 30},
    },
    "stoch_close": {
        "stoch_close_k_length": {"type": "integer", "min": 1, "max": 200, "default": 14},
        "stoch_close_k_smooth": {"type": "integer", "min": 1, "max": 50, "default": 1},
        "stoch_close_d_smooth": {"type": "integer", "min": 1, "max": 50, "default": 3},
        "stoch_close_min_profit": {"type": "number", "min": 0, "max": 100, "default": 0.5},
        "stoch_close_reach_long_more": {"type": "number", "min": 0, "max": 100, "default": 80},
        "stoch_close_reach_long_less": {"type": "number", "min": 0, "max": 100, "default": 0},
        "stoch_close_reach_short_more": {"type": "number", "min": 0, "max": 100, "default": 100},
        "stoch_close_reach_short_less": {"type": "number", "min": 0, "max": 100, "default": 20},
    },
    "channel_close": {
        "channel_close_keltner_length": {"type": "integer", "min": 1, "max": 200, "default": 20},
        "channel_close_keltner_mult": {"type": "number", "min": 0.1, "max": 10, "default": 2.0},
        "channel_close_bb_length": {"type": "integer", "min": 1, "max": 200, "default": 20},
        "channel_close_bb_deviation": {"type": "number", "min": 0.1, "max": 10, "default": 2.0},
    },
    "ma_close": {
        "ma_close_min_profit": {"type": "number", "min": 0, "max": 100, "default": 0.5},
        "ma_close_ma1_length": {"type": "integer", "min": 1, "max": 500, "default": 9},
        "ma_close_ma2_length": {"type": "integer", "min": 1, "max": 500, "default": 21},
    },
    "psar_close": {
        "psar_close_min_profit": {"type": "number", "min": 0, "max": 100, "default": 0.5},
        "psar_close_start": {"type": "number", "min": 0.001, "max": 1, "default": 0.02},
        "psar_close_increment": {"type": "number", "min": 0.001, "max": 1, "default": 0.02},
        "psar_close_maximum": {"type": "number", "min": 0.01, "max": 1, "default": 0.2},
        "psar_close_nth_bar": {"type": "integer", "min": 0, "max": 100, "default": 0},
    },
    "time_bars_close": {
        "close_after_bars": {"type": "integer", "min": 1, "max": 1000, "default": 20},
        "close_min_profit": {"type": "number", "min": 0, "max": 100, "default": 0.5},
        "close_max_bars": {"type": "integer", "min": 1, "max": 10000, "default": 100},
    },
    # ==========================================================================
    # NEW FILTERS (Session 5.5)
    # ==========================================================================
    "rvi_filter": {
        "rvi_length": {"type": "integer", "min": 1, "max": 200, "default": 10},
        "rvi_ma_length": {"type": "integer", "min": 1, "max": 200, "default": 14},
        "rvi_long_more": {"type": "number", "min": 0, "max": 100, "default": 50},
        "rvi_long_less": {"type": "number", "min": 0, "max": 100, "default": 100},
        "rvi_short_more": {"type": "number", "min": 0, "max": 100, "default": 0},
        "rvi_short_less": {"type": "number", "min": 0, "max": 100, "default": 50},
    },
    "indent_order": {
        "indent_percent": {"type": "number", "min": 0.01, "max": 10, "default": 0.1},
        "indent_cancel_bars": {"type": "integer", "min": 1, "max": 100, "default": 10},
    },
    # Extended ATR SL/TP
    "atr_stop": {
        "atr_sl_period": {"type": "integer", "min": 1, "max": 200, "default": 14},
        "atr_sl_multiplier": {"type": "number", "min": 0.1, "max": 20, "default": 2.0},
        "atr_tp_period": {"type": "integer", "min": 1, "max": 200, "default": 14},
        "atr_tp_multiplier": {"type": "number", "min": 0.1, "max": 20, "default": 3.0},
    },
}


# Connection compatibility rules
CONNECTION_RULES: dict[str, list[str]] = {
    # Block types that can connect to entry signals
    "entry_long": [
        "and",
        "or",
        "rsi",
        "macd_cross",
        "ma_cross",
        "bb_breakout",
        "engulfing",
        "hammer",
        "stoch_cross",
        "volume_spike",
        "price_above",
        "price_below",
        "doji",
        "pin_bar",
        "morning_star",
        "three_soldiers",
        "three_line_strike",
        "kicker",
        "abandoned_baby",
        "belt_hold",
        "counterattack",
        "gap_pattern",
        "ladder_pattern",
        "stick_sandwich",
        "homing_pigeon",
        "matching_low_high",
    ],
    "entry_short": [
        "and",
        "or",
        "rsi",
        "macd_cross",
        "ma_cross",
        "bb_breakout",
        "engulfing",
        "hammer",
        "stoch_cross",
        "volume_spike",
        "price_above",
        "price_below",
        "doji",
        "pin_bar",
        "evening_star",
        "three_crows",
        "three_line_strike",
        "kicker",
        "abandoned_baby",
        "belt_hold",
        "counterattack",
        "gap_pattern",
        "ladder_pattern",
        "stick_sandwich",
        "matching_low_high",
    ],
    # Logic gates accept any signal
    "and": ["*"],
    "or": ["*"],
    "not": ["*"],
}


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def validate_param_value(
    param_name: str,
    param_value: Any,
    rules: dict[str, Any],
) -> list[ValidationMessage]:
    """Validate a single parameter value against its rules."""
    messages: list[ValidationMessage] = []

    if param_name not in rules:
        # Unknown parameter - just info
        return []

    rule = rules[param_name]
    param_type = rule.get("type", "any")
    required = rule.get("required", False)

    # Check required
    if param_value is None:
        if required:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"Parameter '{param_name}' is required",
                    field=param_name,
                    code="REQUIRED",
                )
            )
        return messages

    # Type validation
    if param_type == "integer":
        if not isinstance(param_value, int) or isinstance(param_value, bool):
            # Try to parse float as int
            if isinstance(param_value, float) and param_value.is_integer():
                param_value = int(param_value)
            else:
                messages.append(
                    ValidationMessage(
                        severity=ValidationSeverity.ERROR,
                        message=f"'{param_name}' must be an integer",
                        field=param_name,
                        code="TYPE_ERROR",
                    )
                )
                return messages

        # Range validation
        min_val = rule.get("min")
        max_val = rule.get("max")
        if min_val is not None and param_value < min_val:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"'{param_name}' must be >= {min_val}",
                    field=param_name,
                    code="MIN_VALUE",
                )
            )
        if max_val is not None and param_value > max_val:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"'{param_name}' must be <= {max_val}",
                    field=param_name,
                    code="MAX_VALUE",
                )
            )

    elif param_type == "number":
        if not isinstance(param_value, (int, float)) or isinstance(param_value, bool):
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"'{param_name}' must be a number",
                    field=param_name,
                    code="TYPE_ERROR",
                )
            )
            return messages

        min_val = rule.get("min")
        max_val = rule.get("max")
        if min_val is not None and param_value < min_val:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"'{param_name}' must be >= {min_val}",
                    field=param_name,
                    code="MIN_VALUE",
                )
            )
        if max_val is not None and param_value > max_val:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"'{param_name}' must be <= {max_val}",
                    field=param_name,
                    code="MAX_VALUE",
                )
            )

    elif param_type == "select":
        options = rule.get("options", [])
        if param_value not in options:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"'{param_name}' must be one of: {', '.join(options)}",
                    field=param_name,
                    code="INVALID_OPTION",
                )
            )

    elif param_type == "boolean":
        if not isinstance(param_value, bool):
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"'{param_name}' must be true or false",
                    field=param_name,
                    code="TYPE_ERROR",
                )
            )

    return messages


def validate_block(block_type: str, params: dict[str, Any]) -> ValidationResult:
    """Validate a block and all its parameters."""
    messages: list[ValidationMessage] = []

    # Check if block type is known
    if block_type not in BLOCK_VALIDATION_RULES:
        # Unknown block type - just warning
        messages.append(
            ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message=f"Unknown block type: '{block_type}'",
                code="UNKNOWN_BLOCK",
            )
        )
        return ValidationResult(valid=True, messages=messages)

    rules = BLOCK_VALIDATION_RULES[block_type]

    # Validate each parameter
    for param_name, _rule in rules.items():
        param_value = params.get(param_name)
        param_messages = validate_param_value(param_name, param_value, rules)
        messages.extend(param_messages)

    # Check for extra unknown parameters (warning only)
    for param_name in params:
        if param_name not in rules and param_name not in ["enabled", "label", "description"]:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.INFO,
                    message=f"Unknown parameter: '{param_name}'",
                    field=param_name,
                    code="UNKNOWN_PARAM",
                )
            )

    # Block-specific cross-validation
    messages.extend(_cross_validate_block(block_type, params))

    valid = not any(m.severity == ValidationSeverity.ERROR for m in messages)
    return ValidationResult(valid=valid, messages=messages)


def _cross_validate_block(block_type: str, params: dict[str, Any]) -> list[ValidationMessage]:
    """Cross-validate parameters within a block."""
    messages: list[ValidationMessage] = []

    # MACD: fast < slow
    if block_type in ["macd_cross", "macd_histogram", "macd_divergence"]:
        fast = params.get("fast_period", 12)
        slow = params.get("slow_period", 26)
        if fast >= slow:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message="Fast period must be less than slow period",
                    field="fast_period",
                    code="CROSS_VALIDATION",
                )
            )

    # MA cross: fast < slow
    if block_type == "ma_cross":
        fast = params.get("fast_period", 9)
        slow = params.get("slow_period", 21)
        if fast >= slow:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message="Fast period must be less than slow period",
                    field="fast_period",
                    code="CROSS_VALIDATION",
                )
            )

    # RSI: oversold < overbought
    if block_type == "rsi":
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)
        if oversold >= overbought:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message="Oversold level must be less than overbought level",
                    field="oversold",
                    code="CROSS_VALIDATION",
                )
            )

    # Stochastic: oversold < overbought
    if block_type in ["stoch_overbought", "stoch_oversold"]:
        if block_type == "stoch_overbought":
            overbought = params.get("overbought", 80)
            if overbought < 50:
                messages.append(
                    ValidationMessage(
                        severity=ValidationSeverity.WARNING,
                        message="Overbought level below 50 is unusual",
                        field="overbought",
                        code="UNUSUAL_VALUE",
                    )
                )
        if block_type == "stoch_oversold":
            oversold = params.get("oversold", 20)
            if oversold > 50:
                messages.append(
                    ValidationMessage(
                        severity=ValidationSeverity.WARNING,
                        message="Oversold level above 50 is unusual",
                        field="oversold",
                        code="UNUSUAL_VALUE",
                    )
                )

    return messages


def validate_connection(
    source_type: str,
    source_output: str,
    target_type: str,
    target_input: str,
) -> ValidationResult:
    """Validate a connection between two blocks."""
    messages: list[ValidationMessage] = []

    # Check if target accepts connections
    if target_type in CONNECTION_RULES:
        allowed_sources = CONNECTION_RULES[target_type]
        if "*" not in allowed_sources and source_type not in allowed_sources:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"Block '{source_type}' cannot connect to '{target_type}'",
                    code="INVALID_CONNECTION",
                )
            )

    # Output/input compatibility
    # (simplified - in real app would check signal types)
    signal_outputs = ["signal", "condition", "trigger"]
    value_outputs = ["value", "price", "indicator"]

    if source_output in signal_outputs and target_input in value_outputs:
        messages.append(
            ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message="Connecting signal output to value input may not work as expected",
                code="TYPE_MISMATCH",
            )
        )

    valid = not any(m.severity == ValidationSeverity.ERROR for m in messages)
    return ValidationResult(valid=valid, messages=messages)


def validate_strategy(
    blocks: list[dict[str, Any]],
    connections: list[dict[str, Any]],
) -> ValidationResult:
    """Validate entire strategy structure."""
    messages: list[ValidationMessage] = []

    # Check for entry points
    has_entry_long = any(b.get("type") == "entry_long" for b in blocks)
    has_entry_short = any(b.get("type") == "entry_short" for b in blocks)

    if not has_entry_long and not has_entry_short:
        messages.append(
            ValidationMessage(
                severity=ValidationSeverity.ERROR,
                message="Strategy must have at least one entry block (entry_long or entry_short)",
                code="NO_ENTRY",
            )
        )

    # Check for exit points
    exit_block_types = [
        "exit_long", "exit_short", "stop_loss", "take_profit", "trailing_stop",
        # DCA Close Conditions
        "rsi_close", "stoch_close", "channel_close", "ma_close", "psar_close", "time_bars_close",
    ]
    has_exit = any(b.get("type") in exit_block_types for b in blocks)

    if not has_exit:
        messages.append(
            ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message="Strategy has no exit blocks - positions may not close properly",
                code="NO_EXIT",
            )
        )

    # Check for unconnected blocks
    connected_blocks = set()
    for conn in connections:
        connected_blocks.add(conn.get("source_block_id"))
        connected_blocks.add(conn.get("target_block_id"))

    for block in blocks:
        block_id = block.get("id")
        block_type = block.get("type", "")
        # Entry/exit blocks don't need to be connected to something
        is_entry_exit = block_type in ["entry_long", "entry_short", "exit_long", "exit_short"]
        if not is_entry_exit and block_id and block_id not in connected_blocks:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.INFO,
                    message=f"Block '{block_type}' ({block_id}) is not connected",
                    code="UNCONNECTED_BLOCK",
                )
            )

    # Validate each block
    error_count = 0
    for block in blocks:
        block_type = block.get("type", "")
        params = block.get("params", block.get("parameters", {}))
        result = validate_block(block_type, params)
        if not result.valid:
            error_count += 1
            for msg in result.messages:
                if msg.severity == ValidationSeverity.ERROR:
                    messages.append(
                        ValidationMessage(
                            severity=ValidationSeverity.ERROR,
                            message=f"Block '{block_type}': {msg.message}",
                            field=f"{block.get('id', '?')}.{msg.field}" if msg.field else None,
                            code=msg.code,
                        )
                    )

    if error_count > 0:
        messages.insert(
            0,
            ValidationMessage(
                severity=ValidationSeverity.ERROR,
                message=f"{error_count} block(s) have validation errors",
                code="BLOCK_ERRORS",
            ),
        )

    valid = not any(m.severity == ValidationSeverity.ERROR for m in messages)
    return ValidationResult(valid=valid, messages=messages)


# =============================================================================
# WEBSOCKET HANDLER
# =============================================================================


class ValidationWebSocketManager:
    """Manages WebSocket connections for validation."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Validation WS connected: {client_id}")

    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Validation WS disconnected: {client_id}")

    async def send_result(self, client_id: str, result: dict[str, Any]):
        """Send validation result to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(result)


manager = ValidationWebSocketManager()


@router.websocket("/ws/validate")
async def validation_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time strategy validation.

    Protocol:
    - Send JSON messages with 'type' field
    - Receive validation results as JSON

    Message Types:
    - validate_block: Validate a single block
    - validate_param: Validate a single parameter
    - validate_connection: Validate a connection
    - validate_strategy: Validate entire strategy
    - heartbeat: Keep connection alive
    """
    import uuid

    client_id = str(uuid.uuid4())

    await manager.connect(websocket, client_id)

    try:
        # Send welcome message
        await websocket.send_json(
            {
                "type": "connected",
                "client_id": client_id,
                "message": "Validation WebSocket connected",
            }
        )

        while True:
            try:
                # Receive message
                data = await websocket.receive_json()

                msg_type = data.get("type", "")

                if msg_type == MessageType.HEARTBEAT.value:
                    await websocket.send_json({"type": "heartbeat", "status": "ok"})

                elif msg_type == MessageType.VALIDATE_BLOCK.value:
                    block_type = data.get("block_type", "")
                    params = data.get("params", {})
                    block_id = data.get("block_id")

                    result = validate_block(block_type, params)
                    result.block_id = block_id

                    await websocket.send_json(
                        {
                            "type": MessageType.VALIDATION_RESULT.value,
                            "request_type": MessageType.VALIDATE_BLOCK.value,
                            **result.to_dict(),
                        }
                    )

                elif msg_type == MessageType.VALIDATE_PARAM.value:
                    block_type = data.get("block_type", "")
                    param_name = data.get("param_name", "")
                    param_value = data.get("param_value")
                    block_id = data.get("block_id")

                    rules = BLOCK_VALIDATION_RULES.get(block_type, {})
                    messages = validate_param_value(param_name, param_value, rules)

                    valid = not any(m.severity == ValidationSeverity.ERROR for m in messages)
                    result = ValidationResult(
                        valid=valid,
                        messages=messages,
                        block_id=block_id,
                        param_name=param_name,
                    )

                    await websocket.send_json(
                        {
                            "type": MessageType.VALIDATION_RESULT.value,
                            "request_type": MessageType.VALIDATE_PARAM.value,
                            **result.to_dict(),
                        }
                    )

                elif msg_type == MessageType.VALIDATE_CONNECTION.value:
                    result = validate_connection(
                        source_type=data.get("source_block_type", ""),
                        source_output=data.get("source_output", "signal"),
                        target_type=data.get("target_block_type", ""),
                        target_input=data.get("target_input", "input"),
                    )

                    await websocket.send_json(
                        {
                            "type": MessageType.VALIDATION_RESULT.value,
                            "request_type": MessageType.VALIDATE_CONNECTION.value,
                            **result.to_dict(),
                        }
                    )

                elif msg_type == MessageType.VALIDATE_STRATEGY.value:
                    blocks = data.get("blocks", [])
                    connections = data.get("connections", [])

                    result = validate_strategy(blocks, connections)

                    await websocket.send_json(
                        {
                            "type": MessageType.VALIDATION_RESULT.value,
                            "request_type": MessageType.VALIDATE_STRATEGY.value,
                            **result.to_dict(),
                        }
                    )

                else:
                    await websocket.send_json(
                        {
                            "type": MessageType.ERROR.value,
                            "message": f"Unknown message type: {msg_type}",
                        }
                    )

            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": MessageType.ERROR.value,
                        "message": "Invalid JSON",
                    }
                )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        manager.disconnect(client_id)
