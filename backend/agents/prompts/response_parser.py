"""
Response Parser for LLM Trading Strategy outputs.

Parses LLM text responses into structured StrategyDefinition objects:
- JSON extraction from markdown/text
- Auto-fixing common JSON errors
- Validation against platform constraints
- Fallback parsing strategies

Also defines Pydantic models for strategy representation.
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, field_validator

# =============================================================================
# STRATEGY DEFINITION MODELS
# =============================================================================


class Signal(BaseModel):
    """A single trading signal (indicator-based)."""

    id: str = Field(description="Unique signal ID, e.g. 'signal_1'")
    type: str = Field(
        description="Indicator type: RSI, MACD, EMA_Crossover, SMA_Crossover, Bollinger, SuperTrend, Stochastic, CCI"
    )
    params: dict[str, Any] = Field(default_factory=dict, description="Indicator parameters")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Signal weight 0-1")
    condition: str = Field(default="", description="Human-readable condition description")

    @field_validator("type")
    @classmethod
    def validate_signal_type(cls, v: str) -> str:
        """Validate signal type is supported."""
        allowed = {
            "RSI",
            "MACD",
            "EMA_Crossover",
            "SMA_Crossover",
            "Bollinger",
            "SuperTrend",
            "Stochastic",
            "CCI",
            "ATR",
            "ADX",
            "Williams_R",
            "EMA",
            "SMA",
            "VWAP",
            "OBV",
        }
        # Normalize common variations
        normalized = v.replace(" ", "_").replace("-", "_")
        # Case-insensitive match
        for a in allowed:
            if normalized.lower() == a.lower():
                return a
        logger.warning(f"Unknown signal type '{v}', allowing as custom")
        return v


class Filter(BaseModel):
    """A trade filter condition."""

    id: str = Field(description="Unique filter ID, e.g. 'filter_1'")
    type: str = Field(description="Filter type: Volume, Trend, Volatility, Time, ADX")
    params: dict[str, Any] = Field(default_factory=dict)
    condition: str = Field(default="", description="Human-readable condition")


class ExitCondition(BaseModel):
    """Exit condition (take-profit or stop-loss)."""

    type: str = Field(description="Exit type: fixed_pct, trailing, atr_based")
    value: float = Field(description="Exit value (percentage or multiplier)")
    description: str = Field(default="")


class ExitConditions(BaseModel):
    """Complete exit conditions."""

    take_profit: ExitCondition | None = None
    stop_loss: ExitCondition | None = None


class EntryConditions(BaseModel):
    """Entry conditions for long/short."""

    long: str = Field(default="", description="Long entry condition")
    short: str = Field(default="", description="Short entry condition")
    logic: str = Field(default="AND", description="Combination logic: AND, OR")


class PositionManagement(BaseModel):
    """Position sizing and management."""

    size_pct: float = Field(default=100, ge=1, le=100, description="Position size as % of capital")
    max_positions: int = Field(default=1, ge=1, le=10, description="Max concurrent positions")


class OptimizationHints(BaseModel):
    """Hints for parameter optimization."""

    parameters_to_optimize: list[str] = Field(default_factory=list)
    ranges: dict[str, list[float]] = Field(default_factory=dict)
    primary_objective: str = Field(default="sharpe_ratio")


class AgentMetadata(BaseModel):
    """Metadata about the generating agent."""

    agent_name: str = Field(default="unknown")
    model: str = Field(default="")
    specialization: str = Field(default="")
    timestamp: str = Field(default="")


class StrategyDefinition(BaseModel):
    """
    Complete LLM-generated trading strategy definition.

    This is the canonical output format that all LLM responses
    are parsed into. It can be converted to BacktestEngine format
    via BacktestBridge.
    """

    strategy_name: str = Field(description="Human-readable strategy name")
    description: str = Field(default="", description="Strategy description")
    signals: list[Signal] = Field(default_factory=list, description="Trading signals/indicators")
    filters: list[Filter] = Field(default_factory=list, description="Trade filters")
    entry_conditions: EntryConditions | None = None
    exit_conditions: ExitConditions | None = None
    position_management: PositionManagement | None = None
    optimization_hints: OptimizationHints | None = None
    agent_metadata: AgentMetadata | None = None

    @field_validator("signals")
    @classmethod
    def validate_signals_not_empty(cls, v: list[Signal]) -> list[Signal]:
        """Strategy must have at least 1 signal."""
        if not v:
            raise ValueError("Strategy must have at least 1 signal")
        return v

    def get_primary_signal_type(self) -> str:
        """Get the primary (highest weight) signal type."""
        if not self.signals:
            return "unknown"
        return max(self.signals, key=lambda s: s.weight).type

    def get_strategy_type_for_engine(self) -> str:
        """Map to engine strategy type (rsi, ema_crossover, macd, etc.)."""
        primary = self.get_primary_signal_type().lower()
        mapping = {
            "rsi": "rsi",
            "macd": "macd",
            "ema_crossover": "ema_crossover",
            "ema": "ema_crossover",
            "sma_crossover": "sma_crossover",
            "sma": "sma_crossover",
            "bollinger": "bollinger",
            "supertrend": "supertrend",
            "stochastic": "stochastic",
        }
        return mapping.get(primary, "rsi")  # fallback to RSI

    def get_engine_params(self) -> dict[str, Any]:
        """Extract engine-compatible parameters from signals."""
        params: dict[str, Any] = {}
        for signal in self.signals:
            signal_type = signal.type.lower()
            if signal_type == "rsi":
                params["period"] = signal.params.get("period", 14)
                params["overbought"] = signal.params.get("overbought", 70)
                params["oversold"] = signal.params.get("oversold", 30)
            elif signal_type == "macd":
                params["fast_period"] = signal.params.get("fast_period", 12)
                params["slow_period"] = signal.params.get("slow_period", 26)
                params["signal_period"] = signal.params.get("signal_period", 9)
            elif signal_type in ("ema_crossover", "ema"):
                params["fast_period"] = signal.params.get("fast_period", signal.params.get("fast", 9))
                params["slow_period"] = signal.params.get("slow_period", signal.params.get("slow", 21))
            elif signal_type in ("sma_crossover", "sma"):
                params["fast_period"] = signal.params.get("fast_period", signal.params.get("fast", 10))
                params["slow_period"] = signal.params.get("slow_period", signal.params.get("slow", 30))
            elif signal_type == "bollinger":
                params["period"] = signal.params.get("period", 20)
                params["std_dev"] = signal.params.get("std_dev", 2.0)
        return params

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict."""
        return self.model_dump(exclude_none=True)


# =============================================================================
# VALIDATION RESULT
# =============================================================================


class ValidationIssue(BaseModel):
    """A single validation issue."""

    severity: str = Field(description="critical, warning, info")
    field: str = Field(description="Field path, e.g. 'signals[0].params.period'")
    message: str


class ValidationResult(BaseModel):
    """Result of strategy validation."""

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)


# =============================================================================
# RESPONSE PARSER
# =============================================================================


class ResponseParser:
    """
    Parses LLM text responses into StrategyDefinition objects.

    Handles:
    - JSON extraction from markdown code blocks
    - Auto-fixing common JSON formatting errors
    - Multi-strategy fallback parsing
    - Validation against platform constraints

    Example:
        parser = ResponseParser()
        result = parser.parse_strategy(llm_response_text, agent_name="deepseek")
        if result:
            print(result.strategy_name)
            print(result.signals)
    """

    # Supported indicator types with valid parameter ranges
    INDICATOR_CONSTRAINTS: dict[str, dict[str, tuple[float, float]]] = {
        "RSI": {"period": (2, 100), "overbought": (50, 100), "oversold": (0, 50)},
        "MACD": {"fast_period": (2, 50), "slow_period": (10, 100), "signal_period": (2, 50)},
        "EMA_Crossover": {"fast_period": (2, 100), "slow_period": (5, 200)},
        "SMA_Crossover": {"fast_period": (2, 100), "slow_period": (5, 200)},
        "Bollinger": {"period": (5, 100), "std_dev": (0.5, 4.0)},
        "Stochastic": {"k_period": (2, 50), "d_period": (2, 50)},
        "CCI": {"period": (5, 100)},
        "ATR": {"period": (2, 100)},
        "ADX": {"period": (5, 50)},
        "SuperTrend": {"period": (5, 50), "multiplier": (1.0, 5.0)},
    }

    def parse_strategy(
        self,
        llm_response: str,
        agent_name: str = "unknown",
    ) -> StrategyDefinition | None:
        """
        Parse LLM response text into a StrategyDefinition.

        Args:
            llm_response: Raw text from LLM API
            agent_name: Name of the generating agent

        Returns:
            StrategyDefinition or None if parsing failed
        """
        if not llm_response or not llm_response.strip():
            logger.warning("Empty LLM response, cannot parse")
            return None

        # Step 1: Extract JSON from response
        json_str = self._extract_json(llm_response)
        if not json_str:
            logger.warning("No JSON found in LLM response")
            return None

        # Step 2: Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}, attempting fix")
            fixed = self._fix_json(json_str)
            if fixed:
                try:
                    data = json.loads(fixed)
                except json.JSONDecodeError:
                    logger.error("JSON fix failed, giving up")
                    return None
            else:
                return None

        # Step 3: Normalize and build StrategyDefinition
        try:
            strategy = self._build_strategy(data, agent_name)
            logger.info(
                f"Parsed strategy '{strategy.strategy_name}' with {len(strategy.signals)} signals from {agent_name}"
            )
            return strategy
        except Exception as e:
            logger.error(f"Failed to build StrategyDefinition: {e}")
            return None

    def validate_strategy(self, strategy: StrategyDefinition) -> ValidationResult:
        """
        Validate a parsed strategy against platform constraints.

        Args:
            strategy: Parsed StrategyDefinition

        Returns:
            ValidationResult with issues and quality score
        """
        issues: list[ValidationIssue] = []
        warnings: list[str] = []

        # Check signals
        if not strategy.signals:
            issues.append(
                ValidationIssue(
                    severity="critical",
                    field="signals",
                    message="Strategy has no signals",
                )
            )

        for i, signal in enumerate(strategy.signals):
            signal_issues = self._validate_signal_params(signal, i)
            issues.extend(signal_issues)

        # Check exit conditions
        if not strategy.exit_conditions:
            warnings.append("No exit conditions defined — will use default SL/TP")
        else:
            if strategy.exit_conditions.take_profit:
                tp = strategy.exit_conditions.take_profit.value
                if tp > 20:
                    warnings.append(f"Take profit of {tp}% may be too high for intraday trading")
            if strategy.exit_conditions.stop_loss:
                sl = strategy.exit_conditions.stop_loss.value
                if sl > 10:
                    warnings.append(f"Stop loss of {sl}% may be too wide")
                if sl < 0.1:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            field="exit_conditions.stop_loss.value",
                            message=f"Stop loss of {sl}% is extremely tight",
                        )
                    )

        # Check signal count
        if len(strategy.signals) > 4:
            warnings.append(f"Too many signals ({len(strategy.signals)}), consider reducing to 2-4")

        # Calculate quality score
        critical_count = sum(1 for i in issues if i.severity == "critical")
        warning_count = sum(1 for i in issues if i.severity == "warning") + len(warnings)

        quality_score = max(0.0, 1.0 - critical_count * 0.3 - warning_count * 0.1)

        is_valid = critical_count == 0

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            warnings=warnings,
            quality_score=quality_score,
        )

    def _extract_json(self, text: str) -> str | None:
        """
        Extract JSON from LLM response text.

        Tries multiple strategies:
        1. Markdown code block ```json ... ```
        2. Generic code block ``` ... ```
        3. Raw JSON object { ... }
        """
        # Strategy 1: ```json ... ```
        match = re.search(r"```json\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Strategy 2: ``` ... ```
        match = re.search(r"```\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            if candidate.startswith("{"):
                return candidate

        # Strategy 3: Find outermost { ... }
        brace_start = text.find("{")
        if brace_start >= 0:
            # Find matching closing brace
            depth = 0
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return text[brace_start : i + 1]

        return None

    def _fix_json(self, json_str: str) -> str | None:
        """
        Attempt to fix common JSON formatting errors.

        Fixes:
        - Trailing commas
        - Single quotes → double quotes
        - Unquoted keys
        - Comments (// and /* */)
        """
        fixed = json_str

        # Remove comments
        fixed = re.sub(r"//.*?\n", "\n", fixed)
        fixed = re.sub(r"/\*.*?\*/", "", fixed, flags=re.DOTALL)

        # Fix trailing commas (,] and ,})
        fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

        # Fix single quotes to double quotes (careful with apostrophes)
        # Only replace when it looks like a JSON key/value pattern
        fixed = re.sub(r"'(\w+)'(\s*:)", r'"\1"\2', fixed)
        fixed = re.sub(r":\s*'([^']*)'", r': "\1"', fixed)

        try:
            json.loads(fixed)
            return fixed
        except json.JSONDecodeError:
            return None

    def _build_strategy(self, data: dict[str, Any], agent_name: str) -> StrategyDefinition:
        """Build StrategyDefinition from parsed JSON dict."""
        # Normalize signal objects
        signals = []
        for i, s in enumerate(data.get("signals", [])):
            signals.append(
                Signal(
                    id=s.get("id", f"signal_{i + 1}"),
                    type=s.get("type", "RSI"),
                    params=s.get("params", {}),
                    weight=float(s.get("weight", 1.0)),
                    condition=s.get("condition", ""),
                )
            )

        # Normalize filters
        filters = []
        for i, f in enumerate(data.get("filters", [])):
            filters.append(
                Filter(
                    id=f.get("id", f"filter_{i + 1}"),
                    type=f.get("type", "Volume"),
                    params=f.get("params", {}),
                    condition=f.get("condition", ""),
                )
            )

        # Entry conditions
        entry_raw = data.get("entry_conditions", {})
        entry_conditions = None
        if entry_raw:
            entry_conditions = EntryConditions(
                long=entry_raw.get("long", ""),
                short=entry_raw.get("short", ""),
                logic=entry_raw.get("logic", "AND"),
            )

        # Exit conditions
        exit_raw = data.get("exit_conditions", {})
        exit_conditions = None
        if exit_raw:
            tp_raw = exit_raw.get("take_profit", {})
            sl_raw = exit_raw.get("stop_loss", {})
            exit_conditions = ExitConditions(
                take_profit=ExitCondition(**tp_raw) if tp_raw else None,
                stop_loss=ExitCondition(**sl_raw) if sl_raw else None,
            )

        # Position management
        pm_raw = data.get("position_management", {})
        position_mgmt = PositionManagement(**pm_raw) if pm_raw else PositionManagement()

        # Optimization hints
        oh_raw = data.get("optimization_hints", {})
        opt_hints = OptimizationHints(**oh_raw) if oh_raw else None

        # Agent metadata
        agent_meta = AgentMetadata(agent_name=agent_name)

        return StrategyDefinition(
            strategy_name=data.get("strategy_name", data.get("name", "LLM_Generated_Strategy")),
            description=data.get("description", ""),
            signals=signals,
            filters=filters,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            position_management=position_mgmt,
            optimization_hints=opt_hints,
            agent_metadata=agent_meta,
        )

    def _validate_signal_params(self, signal: Signal, index: int) -> list[ValidationIssue]:
        """Validate signal parameters against known constraints."""
        issues: list[ValidationIssue] = []
        constraints = self.INDICATOR_CONSTRAINTS.get(signal.type, {})

        for param_name, (min_val, max_val) in constraints.items():
            if param_name in signal.params:
                value = signal.params[param_name]
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    issues.append(
                        ValidationIssue(
                            severity="critical",
                            field=f"signals[{index}].params.{param_name}",
                            message=f"Parameter '{param_name}' must be numeric, got '{value}'",
                        )
                    )
                    continue

                if value < min_val or value > max_val:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            field=f"signals[{index}].params.{param_name}",
                            message=(
                                f"Parameter '{param_name}' value {value} "
                                f"is outside recommended range [{min_val}, {max_val}]"
                            ),
                        )
                    )

        return issues
