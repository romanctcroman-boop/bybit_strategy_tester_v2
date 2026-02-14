"""
Strategy Parameter Validator

Validates and sanitizes strategy parameters before agent-driven backtest execution.
Enforces guardrails to prevent:
- Extreme leverage (liquidation risk)
- Invalid parameter ranges
- Excessive resource consumption (date ranges, grid counts)
- Strategy-specific constraint violations

Thread-safe and stateless — safe for concurrent use.

References:
- Bybit max leverage: 125x (perpetual contracts)
- Commission: 0.0007 (TradingView parity — NEVER change)
- Data retention: from 2025-01-01 only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger


class RiskLevel(str, Enum):
    """Risk classification for strategy configurations."""

    SAFE = "safe"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"
    REJECTED = "rejected"


@dataclass
class ValidationResult:
    """Result of strategy parameter validation."""

    is_valid: bool
    risk_level: RiskLevel
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_params: dict[str, Any] = field(default_factory=dict)
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "risk_level": self.risk_level.value,
            "errors": self.errors,
            "warnings": self.warnings,
            "sanitized_params": self.sanitized_params,
            "details": self.details,
        }


# ============================================================================
# Strategy-specific parameter constraints
# ============================================================================

STRATEGY_CONSTRAINTS: dict[str, dict[str, dict[str, Any]]] = {
    "rsi": {
        "period": {"type": int, "min": 2, "max": 200, "default": 14},
        "overbought": {"type": (int, float), "min": 50, "max": 100, "default": 70},
        "oversold": {"type": (int, float), "min": 0, "max": 50, "default": 30},
    },
    "macd": {
        "fast_period": {"type": int, "min": 2, "max": 100, "default": 12},
        "slow_period": {"type": int, "min": 5, "max": 200, "default": 26},
        "signal_period": {"type": int, "min": 2, "max": 50, "default": 9},
    },
    "sma_crossover": {
        "fast_period": {"type": int, "min": 2, "max": 200, "default": 10},
        "slow_period": {"type": int, "min": 5, "max": 500, "default": 50},
    },
    "bollinger_bands": {
        "period": {"type": int, "min": 5, "max": 200, "default": 20},
        "std_dev": {"type": (int, float), "min": 0.5, "max": 5.0, "default": 2.0},
    },
    "grid": {
        "grid_count": {"type": int, "min": 2, "max": 200, "default": 10},
        "upper_price": {"type": (int, float), "min": 0.01, "max": 1_000_000},
        "lower_price": {"type": (int, float), "min": 0.01, "max": 1_000_000},
    },
    "dca": {
        "dca_count": {"type": int, "min": 1, "max": 50, "default": 5},
        "dca_step_pct": {"type": (int, float), "min": 0.1, "max": 20.0, "default": 1.0},
    },
    "martingale": {
        "multiplier": {"type": (int, float), "min": 1.1, "max": 5.0, "default": 2.0},
        "max_trades": {"type": int, "min": 1, "max": 20, "default": 5},
    },
}

# Global limits
VALID_INTERVALS = {"1", "5", "15", "30", "60", "240", "D", "W", "M"}
DATA_START_DATE = datetime(2025, 1, 1, tzinfo=UTC)
MAX_DATE_RANGE_DAYS = 730  # 2 years
MIN_CAPITAL = 100.0
MAX_CAPITAL = 100_000_000.0
MAX_LEVERAGE = 125
LEVERAGE_WARNING_THRESHOLD = 50


class StrategyValidator:
    """
    Validates and sanitizes strategy configurations for agent execution.

    Ensures all parameters are within safe bounds before allowing
    a backtest to run. Provides risk classification for the
    overall configuration.

    Example:
        validator = StrategyValidator()
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14, "overbought": 70, "oversold": 30},
            leverage=10,
            initial_capital=10000,
        )
        if result.is_valid:
            # Safe to run backtest
            ...
    """

    def validate(
        self,
        strategy_type: str,
        strategy_params: dict[str, Any],
        leverage: float = 1.0,
        initial_capital: float = 10000.0,
        interval: str = "15",
        start_date: str | None = None,
        end_date: str | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> ValidationResult:
        """
        Validate a complete strategy configuration.

        Args:
            strategy_type: Strategy name
            strategy_params: Strategy-specific parameters
            leverage: Leverage multiplier
            initial_capital: Starting capital
            interval: Timeframe string
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
            stop_loss: Stop loss fraction
            take_profit: Take profit fraction

        Returns:
            ValidationResult with errors, warnings, and risk level
        """
        errors: list[str] = []
        warnings: list[str] = []
        sanitized = dict(strategy_params)

        # 1. Validate strategy type
        valid_types = set(STRATEGY_CONSTRAINTS.keys()) | {"custom", "advanced"}
        if strategy_type not in valid_types:
            errors.append(f"Unknown strategy '{strategy_type}'. Valid: {sorted(valid_types)}")

        # 2. Validate interval
        if interval not in VALID_INTERVALS:
            errors.append(f"Invalid interval '{interval}'. Valid: {sorted(VALID_INTERVALS)}")

        # 3. Validate capital
        if initial_capital < MIN_CAPITAL:
            errors.append(f"Capital too low: {initial_capital} < {MIN_CAPITAL}")
        elif initial_capital > MAX_CAPITAL:
            errors.append(f"Capital too high: {initial_capital} > {MAX_CAPITAL}")

        # 4. Validate leverage
        if leverage > MAX_LEVERAGE:
            errors.append(f"Leverage {leverage}x exceeds Bybit max ({MAX_LEVERAGE}x)")
        elif leverage > LEVERAGE_WARNING_THRESHOLD:
            warnings.append(
                f"High leverage ({leverage}x) — significant liquidation risk. "
                f"Consider reducing to {LEVERAGE_WARNING_THRESHOLD}x or below."
            )
        if leverage < 1:
            errors.append("Leverage must be >= 1")

        # 5. Validate dates
        if start_date and end_date:
            try:
                sd = datetime.fromisoformat(start_date).replace(tzinfo=UTC)
                ed = datetime.fromisoformat(end_date).replace(tzinfo=UTC)

                if sd >= ed:
                    errors.append("start_date must be before end_date")
                if sd < DATA_START_DATE:
                    warnings.append(
                        f"Start date {start_date} is before data retention start "
                        f"(2025-01-01). Data may not be available."
                    )
                if (ed - sd).days > MAX_DATE_RANGE_DAYS:
                    warnings.append(
                        f"Date range ({(ed - sd).days} days) exceeds recommended max ({MAX_DATE_RANGE_DAYS} days)"
                    )
            except ValueError as e:
                errors.append(f"Invalid date format: {e}")

        # 6. Validate stop loss / take profit
        if stop_loss is not None:
            if stop_loss < 0.001 or stop_loss > 0.5:
                errors.append(f"stop_loss must be 0.001 — 0.5, got {stop_loss}")
            if leverage > 20 and stop_loss and stop_loss < 0.005:
                warnings.append("Very tight stop loss with high leverage — likely frequent stop-outs")

        if take_profit is not None and (take_profit < 0.001 or take_profit > 1.0):
            errors.append(f"take_profit must be 0.001 — 1.0, got {take_profit}")

        if stop_loss and take_profit:
            rr = take_profit / stop_loss
            if rr < 1.0:
                warnings.append(f"Risk-reward ratio ({rr:.2f}) < 1.0 — reward is less than risk")

        # 7. Validate strategy-specific parameters
        if strategy_type in STRATEGY_CONSTRAINTS:
            constraints = STRATEGY_CONSTRAINTS[strategy_type]
            for param_name, constraint in constraints.items():
                if param_name not in strategy_params:
                    if "default" in constraint:
                        sanitized[param_name] = constraint["default"]
                        warnings.append(f"Missing param '{param_name}', using default: {constraint['default']}")
                    continue

                value = strategy_params[param_name]

                # Type check
                expected = constraint["type"]
                if not isinstance(value, expected):
                    errors.append(f"Param '{param_name}' must be {expected}, got {type(value).__name__}")
                    continue

                # Range check
                if "min" in constraint and value < constraint["min"]:
                    errors.append(f"Param '{param_name}' = {value} below min ({constraint['min']})")
                if "max" in constraint and value > constraint["max"]:
                    errors.append(f"Param '{param_name}' = {value} above max ({constraint['max']})")

            # Strategy-specific cross-validation
            if strategy_type == "macd":
                fast = sanitized.get("fast_period", 12)
                slow = sanitized.get("slow_period", 26)
                if isinstance(fast, int) and isinstance(slow, int) and fast >= slow:
                    errors.append(f"MACD fast_period ({fast}) must be less than slow_period ({slow})")

            if strategy_type == "sma_crossover":
                fast = sanitized.get("fast_period", 10)
                slow = sanitized.get("slow_period", 50)
                if isinstance(fast, int) and isinstance(slow, int) and fast >= slow:
                    errors.append(f"SMA fast_period ({fast}) must be less than slow_period ({slow})")

            if strategy_type == "grid":
                upper = sanitized.get("upper_price")
                lower = sanitized.get("lower_price")
                if upper and lower and upper <= lower:
                    errors.append(f"Grid upper_price ({upper}) must be greater than lower_price ({lower})")

        # 8. Determine risk level
        risk_level = self._assess_risk(
            errors=errors,
            warnings=warnings,
            leverage=leverage,
            stop_loss=stop_loss,
        )

        is_valid = len(errors) == 0

        result = ValidationResult(
            is_valid=is_valid,
            risk_level=risk_level,
            errors=errors,
            warnings=warnings,
            sanitized_params=sanitized,
            details=f"Validated {strategy_type} with {len(sanitized)} params",
        )

        if not is_valid:
            logger.warning(f"Strategy validation failed: {strategy_type} — {len(errors)} errors")

        return result

    def _assess_risk(
        self,
        errors: list[str],
        warnings: list[str],
        leverage: float,
        stop_loss: float | None,
    ) -> RiskLevel:
        """Assess overall risk level of the configuration."""
        if errors:
            return RiskLevel.REJECTED

        if leverage > 100:
            return RiskLevel.EXTREME
        if leverage > 50:
            return RiskLevel.HIGH
        if leverage > 20 or len(warnings) >= 3:
            return RiskLevel.MODERATE
        if stop_loss is None and leverage > 5:
            return RiskLevel.MODERATE

        return RiskLevel.SAFE


__all__ = [
    "STRATEGY_CONSTRAINTS",
    "RiskLevel",
    "StrategyValidator",
    "ValidationResult",
]
