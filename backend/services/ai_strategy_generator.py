"""
AI Strategy Generator Service.

Generates trading strategies using AI/LLM based on:
- Market pattern descriptions
- Technical analysis preferences
- Risk parameters
- Backtesting requirements

Uses DeepSeek for code generation and strategy validation.
"""

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class GenerationStatus(str, Enum):
    """Strategy generation status."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    VALIDATING = "validating"
    BACKTESTING = "backtesting"
    COMPLETED = "completed"
    FAILED = "failed"


class PatternType(str, Enum):
    """Common pattern types for strategy generation."""

    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    MOMENTUM = "momentum"
    SCALPING = "scalping"
    SWING_TRADING = "swing_trading"
    GRID_TRADING = "grid_trading"
    DCA = "dca"
    CUSTOM = "custom"


class IndicatorType(str, Enum):
    """Available indicators."""

    RSI = "rsi"
    MACD = "macd"
    BOLLINGER_BANDS = "bollinger_bands"
    EMA = "ema"
    SMA = "sma"
    ATR = "atr"
    STOCHASTIC = "stochastic"
    ADX = "adx"
    VWAP = "vwap"
    VOLUME = "volume"
    ICHIMOKU = "ichimoku"
    SUPERTREND = "supertrend"


@dataclass
class GenerationRequest:
    """Request for AI strategy generation."""

    # Basic info
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""

    # Pattern specification
    pattern_type: PatternType = PatternType.TREND_FOLLOWING
    pattern_description: str = ""

    # Indicators to use
    indicators: list[IndicatorType] = field(default_factory=list)
    custom_conditions: str = ""

    # Risk parameters
    max_drawdown: float = 0.15  # 15%
    risk_per_trade: float = 0.02  # 2%
    target_win_rate: float = 0.5
    target_risk_reward: float = 2.0

    # Backtesting requirements
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT"])
    timeframes: list[str] = field(default_factory=lambda: ["60", "240"])
    min_backtest_period_days: int = 30

    # Advanced
    use_ml_features: bool = False
    multi_timeframe: bool = False
    position_sizing: str = "fixed"  # fixed, kelly, volatility_adjusted

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class GeneratedStrategy:
    """Generated strategy result."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = ""

    # Strategy code
    name: str = ""
    code: str = ""
    class_name: str = ""

    # Metadata
    description: str = ""
    pattern_type: PatternType = PatternType.CUSTOM
    indicators_used: list[str] = field(default_factory=list)

    # Parameters schema
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    default_params: dict[str, Any] = field(default_factory=dict)

    # Backtest results (if ran)
    backtest_results: dict[str, Any] | None = None

    # Status
    status: GenerationStatus = GenerationStatus.PENDING
    error_message: str | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    # Validation
    is_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)


# ============================================================================
# Prompt Templates
# ============================================================================

STRATEGY_GENERATION_SYSTEM_PROMPT = """You are an expert quantitative trading strategy developer.
You specialize in creating Python trading strategies for the cryptocurrency market.

Your strategies must:
1. Follow the BaseStrategy pattern (inherit from LibraryStrategy)
2. Use proper technical indicators from pandas_ta or manual calculation
3. Include clear entry/exit conditions
4. Have proper risk management (stop-loss, take-profit)
5. Be well-documented with docstrings
6. Include ParameterSpec definitions for optimization

IMPORTANT PATTERNS:
- Import from: backend.services.live_trading.strategy_runner
- Import from: backend.services.strategies.base
- Use StrategyInfo for metadata
- Use ParameterSpec for parameters
- Implement generate_signals(df, params) -> List[TradingSignal]

Example structure:
```python
from dataclasses import dataclass
from typing import List
from backend.services.live_trading.strategy_runner import SignalType, TradingSignal
from backend.services.strategies.base import (
    LibraryStrategy, ParameterSpec, ParameterType,
    StrategyCategory, StrategyInfo, register_strategy,
    calculate_stop_loss, calculate_take_profit
)

@dataclass
class MyStrategyParams:
    param1: int = 14
    param2: float = 0.5

MY_STRATEGY_INFO = StrategyInfo(
    id="my_strategy",
    name="My Strategy",
    description="Description here",
    category=StrategyCategory.TREND_FOLLOWING,
    parameters=[
        ParameterSpec(name="param1", param_type=ParameterType.INT, default=14, min_value=5, max_value=30),
    ]
)

@register_strategy(MY_STRATEGY_INFO)
class MyStrategy(LibraryStrategy):
    def __init__(self):
        super().__init__(MY_STRATEGY_INFO)

    def generate_signals(self, df, params=None) -> List[TradingSignal]:
        # Implementation
        pass
```
"""

STRATEGY_GENERATION_USER_TEMPLATE = """Create a trading strategy with the following specifications:

**Strategy Name:** {name}
**Pattern Type:** {pattern_type}
**Description:** {description}

**Technical Indicators to Use:**
{indicators_list}

**Entry/Exit Conditions:**
{conditions}

**Risk Parameters:**
- Maximum Drawdown Target: {max_drawdown:.1%}
- Risk Per Trade: {risk_per_trade:.1%}
- Target Win Rate: {target_win_rate:.1%}
- Target Risk/Reward Ratio: {risk_reward:.1f}

**Position Sizing Method:** {position_sizing}
**Multi-timeframe Analysis:** {multi_timeframe}

**Additional Requirements:**
{custom_conditions}

Please generate a complete Python strategy class that:
1. Follows the LibraryStrategy pattern
2. Includes all necessary imports
3. Has proper ParameterSpec definitions
4. Implements generate_signals() method
5. Uses stop-loss and take-profit based on ATR
6. Is well-documented

Return ONLY the Python code, no explanations."""


VALIDATION_PROMPT = """Review this trading strategy code for correctness and safety:

```python
{code}
```

Check for:
1. Correct imports and class inheritance
2. Proper implementation of generate_signals()
3. Risk management (stop-loss/take-profit)
4. No runtime errors (syntax, undefined variables)
5. Parameter bounds are reasonable
6. No look-ahead bias

Return a JSON response:
{{
    "is_valid": true/false,
    "errors": ["error1", "error2"],
    "warnings": ["warning1"],
    "suggestions": ["suggestion1"]
}}"""


# ============================================================================
# AI Strategy Generator Service
# ============================================================================


class AIStrategyGenerator:
    """
    AI-powered strategy generation service.

    Uses DeepSeek to generate trading strategies based on user specifications.
    """

    def __init__(self):
        self._agent_interface = None
        self._generation_cache: dict[str, GeneratedStrategy] = {}
        self._active_generations: dict[str, asyncio.Task] = {}

    async def _get_agent(self):
        """Get the unified agent interface lazily."""
        if self._agent_interface is None:
            try:
                from backend.agents.unified_agent_interface import (
                    AgentType,
                    UnifiedAgentInterface,
                )

                self._agent_interface = UnifiedAgentInterface()
                self._agent_type = AgentType.DEEPSEEK
            except ImportError as e:
                logger.error(f"Failed to import agent interface: {e}")
                raise RuntimeError("Agent interface not available")
        return self._agent_interface

    async def generate_strategy(
        self,
        request: GenerationRequest,
        auto_backtest: bool = False,
    ) -> GeneratedStrategy:
        """
        Generate a trading strategy from specifications.

        Args:
            request: Generation request with specifications
            auto_backtest: Whether to run automatic backtesting

        Returns:
            GeneratedStrategy with generated code and results
        """
        strategy = GeneratedStrategy(
            request_id=request.request_id,
            name=request.name or f"AI_Strategy_{request.request_id[:8]}",
            pattern_type=request.pattern_type,
            status=GenerationStatus.ANALYZING,
        )

        try:
            # Store in cache
            self._generation_cache[strategy.id] = strategy

            # Step 1: Analyze request
            logger.info(f"Analyzing strategy request: {request.request_id}")
            strategy.status = GenerationStatus.ANALYZING

            # Step 2: Generate code
            logger.info(f"Generating strategy code for: {request.name}")
            strategy.status = GenerationStatus.GENERATING

            code = await self._generate_code(request)
            strategy.code = code
            strategy.class_name = self._extract_class_name(code)
            strategy.indicators_used = [i.value for i in request.indicators]

            # Step 3: Validate
            logger.info(f"Validating generated strategy: {strategy.name}")
            strategy.status = GenerationStatus.VALIDATING

            validation_result = await self._validate_code(code)
            strategy.is_valid = validation_result.get("is_valid", False)
            strategy.validation_errors = validation_result.get("errors", [])

            if not strategy.is_valid:
                strategy.status = GenerationStatus.FAILED
                strategy.error_message = "; ".join(strategy.validation_errors)
                return strategy

            # Step 4: Extract parameters
            strategy.parameters = self._extract_parameters(code)
            strategy.default_params = self._extract_defaults(code)

            # Step 5: Auto-backtest if requested
            if auto_backtest:
                logger.info(f"Running auto-backtest for: {strategy.name}")
                strategy.status = GenerationStatus.BACKTESTING
                strategy.backtest_results = await self._run_backtest(strategy, request)

            # Done
            strategy.status = GenerationStatus.COMPLETED
            strategy.completed_at = datetime.now(UTC)

            logger.info(f"Strategy generation completed: {strategy.id}")
            return strategy

        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            strategy.status = GenerationStatus.FAILED
            strategy.error_message = str(e)
            return strategy

    async def _generate_code(self, request: GenerationRequest) -> str:
        """Generate strategy code using AI."""
        agent = await self._get_agent()

        # Build indicators list
        indicators_list = (
            "\n".join([f"- {ind.value.upper()}" for ind in request.indicators])
            if request.indicators
            else "- RSI\n- ATR (for stop-loss)"
        )

        # Build conditions
        conditions = request.pattern_description or self._get_default_conditions(request.pattern_type)

        # Build prompt
        prompt = STRATEGY_GENERATION_USER_TEMPLATE.format(
            name=request.name or f"AI_{request.pattern_type.value}",
            pattern_type=request.pattern_type.value.replace("_", " ").title(),
            description=request.description or f"AI-generated {request.pattern_type.value} strategy",
            indicators_list=indicators_list,
            conditions=conditions,
            max_drawdown=request.max_drawdown,
            risk_per_trade=request.risk_per_trade,
            target_win_rate=request.target_win_rate,
            risk_reward=request.target_risk_reward,
            position_sizing=request.position_sizing,
            multi_timeframe="Yes" if request.multi_timeframe else "No",
            custom_conditions=request.custom_conditions or "None",
        )

        # Call AI using query_deepseek directly (simpler API)
        response = await agent.query_deepseek(
            prompt=prompt,
            system_prompt=STRATEGY_GENERATION_SYSTEM_PROMPT,
            max_tokens=4000,
        )

        # Extract code from response
        code = self._extract_code_block(response.get("response", ""))
        return code

    async def _validate_code(self, code: str) -> dict[str, Any]:
        """Validate generated code using AI + static analysis."""
        # First, try static validation
        static_errors = self._static_validate(code)
        if static_errors:
            return {
                "is_valid": False,
                "errors": static_errors,
                "warnings": [],
                "suggestions": [],
            }

        # Then use AI for semantic validation
        try:
            agent = await self._get_agent()

            response = await agent.query_deepseek(
                prompt=VALIDATION_PROMPT.format(code=code),
                max_tokens=2000,
            )

            # Parse JSON response
            result = self._parse_json_response(response.get("response", ""))
            return result

        except Exception as e:
            logger.warning(f"AI validation failed, using static only: {e}")
            return {
                "is_valid": True,  # Trust static validation
                "errors": [],
                "warnings": [f"AI validation unavailable: {e}"],
                "suggestions": [],
            }

    def _static_validate(self, code: str) -> list[str]:
        """Static validation of Python code."""
        errors = []

        # Check syntax
        try:
            compile(code, "<generated>", "exec")
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            return errors

        # Check required elements
        required_patterns = [
            (r"class\s+\w+\s*\(.*LibraryStrategy", "Must inherit from LibraryStrategy"),
            (r"def\s+generate_signals\s*\(", "Must implement generate_signals()"),
            (r"StrategyInfo\s*\(", "Must define StrategyInfo"),
            (r"from\s+backend\.services", "Must import from backend.services"),
        ]

        for pattern, message in required_patterns:
            if not re.search(pattern, code):
                errors.append(message)

        # Check for dangerous patterns
        dangerous_patterns = [
            (r"\bexec\s*\(", "Dangerous: exec() call found"),
            (r"\beval\s*\(", "Dangerous: eval() call found"),
            (r"\b__import__\s*\(", "Dangerous: __import__() call found"),
            (r"\bos\.system\s*\(", "Dangerous: os.system() call found"),
            (r"\bsubprocess", "Dangerous: subprocess usage found"),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, code):
                errors.append(message)

        return errors

    def _extract_class_name(self, code: str) -> str:
        """Extract the main strategy class name from code."""
        match = re.search(r"class\s+(\w+)\s*\(.*LibraryStrategy", code)
        if match:
            return match.group(1)
        return "GeneratedStrategy"

    def _extract_parameters(self, code: str) -> dict[str, dict[str, Any]]:
        """Extract parameter specifications from code."""
        parameters = {}

        # Find ParameterSpec definitions
        pattern = r'ParameterSpec\s*\(\s*name\s*=\s*["\'](\w+)["\'].*?\)'
        for match in re.finditer(pattern, code, re.DOTALL):
            param_name = match.group(1)
            param_text = match.group(0)

            # Extract attributes
            param_info = {"name": param_name}

            # Type
            type_match = re.search(r"param_type\s*=\s*ParameterType\.(\w+)", param_text)
            if type_match:
                param_info["type"] = type_match.group(1).lower()

            # Default
            default_match = re.search(r'default\s*=\s*([\d.]+|True|False|["\'][^"\']+["\'])', param_text)
            if default_match:
                param_info["default"] = self._parse_value(default_match.group(1))

            # Min/Max
            min_match = re.search(r"min_value\s*=\s*([\d.]+)", param_text)
            max_match = re.search(r"max_value\s*=\s*([\d.]+)", param_text)
            if min_match:
                param_info["min"] = float(min_match.group(1))
            if max_match:
                param_info["max"] = float(max_match.group(1))

            parameters[param_name] = param_info

        return parameters

    def _extract_defaults(self, code: str) -> dict[str, Any]:
        """Extract default parameter values."""
        defaults = {}
        for name, info in self._extract_parameters(code).items():
            if "default" in info:
                defaults[name] = info["default"]
        return defaults

    def _extract_code_block(self, response: str) -> str:
        """Extract Python code from markdown code blocks."""
        # Try to find ```python ... ``` blocks
        pattern = r"```python\s*\n(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try generic code blocks
        pattern = r"```\s*\n(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Return as-is if no code blocks
        return response.strip()

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON from AI response."""
        # Try to find JSON in response
        pattern = r"\{[^{}]*\}"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            try:
                parsed: dict[str, Any] = json.loads(match.group(0))
                return parsed  # type: ignore[return-value]
            except json.JSONDecodeError:
                pass

        # Default response
        return {
            "is_valid": True,
            "errors": [],
            "warnings": ["Could not parse AI validation response"],
            "suggestions": [],
        }

    def _parse_value(self, value_str: str) -> Any:
        """Parse a string value to Python type."""
        value_str = value_str.strip()
        if value_str in ("True", "true"):
            return True
        if value_str in ("False", "false"):
            return False
        if value_str.startswith(("'", '"')):
            return value_str[1:-1]
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str

    def _get_default_conditions(self, pattern_type: PatternType) -> str:
        """Get default entry/exit conditions for pattern type."""
        conditions = {
            PatternType.TREND_FOLLOWING: """
            Entry: Price above EMA, EMA rising, RSI in range filter (long_rsi_more=50, long_rsi_less=100;
            more=LOWER bound, less=UPPER bound, engine: RSI > more AND RSI < less)
            Exit: Price below EMA or RSI cross level triggers (cross_short_level=40)
            RSI modes: use Range filter for trend confirmation, Cross level for exit signals
            MACD: use_macd_cross_zero=true for trend direction, or use_macd_cross_signal=true
            for MACD/Signal crossover entries. Modes combine with OR logic.
            """,
            PatternType.MEAN_REVERSION: """
            Entry: Price at Bollinger Band extremes, RSI cross level (cross_long_level=30, cross_short_level=70)
            Exit: Price returns to middle band or RSI crosses opposite level
            RSI modes: use Cross level for entry timing, Range filter for confirmation
            """,
            PatternType.BREAKOUT: """
            Entry: Price breaks above resistance with volume confirmation
            Exit: Stop below breakout level, take profit at ATR multiples
            """,
            PatternType.MOMENTUM: """
            Entry: Strong momentum — RSI range filter (long_rsi_more=60, long_rsi_less=100;
            more=LOWER bound, less=UPPER bound) or MACD cross signal
            (use_macd_cross_signal=true, signal_only_if_macd_positive=true for mean-reversion filter)
            Exit: Momentum weakening (RSI cross level triggers) or MACD cross zero reversal
            RSI modes: combine Range filter for strength + Cross level for reversals
            MACD modes: Cross Signal for entries, Cross Zero for confirmation. OR logic — either fires.
            signal_memory_bars extends MACD signals for N bars (default 5).
            """,
            PatternType.SCALPING: """
            Entry: Quick reversal signals on short timeframe
            Exit: Small profit targets (0.5-1% per trade)
            """,
            PatternType.SWING_TRADING: """
            Entry: Trend continuation after pullback
            Exit: Hold for larger moves, trail stop-loss
            """,
            PatternType.GRID_TRADING: """
            Entry: Buy at grid levels below current price
            Sell: Sell at grid levels above current price
            """,
            PatternType.DCA: """
            Entry: Regular interval purchases (time-based)
            Exit: Accumulated position sold at target
            """,
        }
        return conditions.get(pattern_type, "Define custom entry/exit logic")

    async def _run_backtest(
        self,
        strategy: GeneratedStrategy,
        request: GenerationRequest,
    ) -> dict[str, Any]:
        """Run automatic backtesting on generated strategy."""
        try:
            # Import backtest executor
            from backend.ml.ai_backtest_executor import AIBacktestExecutor

            executor = AIBacktestExecutor()

            # Run backtest for each symbol/timeframe
            results = {}
            for symbol in request.symbols[:2]:  # Limit to 2 symbols
                for tf in request.timeframes[:2]:  # Limit to 2 timeframes
                    key = f"{symbol}_{tf}"
                    result = await executor.run_backtest(
                        strategy_code=strategy.code,
                        symbol=symbol,
                        timeframe=tf,
                        days=request.min_backtest_period_days,
                    )
                    results[key] = result

            # Aggregate results
            total_return = sum(r.get("total_return", 0) for r in results.values()) / len(results)
            win_rate = sum(r.get("win_rate", 0) for r in results.values()) / len(results)
            max_dd = min(r.get("max_drawdown", 0) for r in results.values())

            return {
                "total_return": total_return,
                "win_rate": win_rate,
                "max_drawdown": max_dd,
                "sharpe_ratio": sum(r.get("sharpe_ratio", 0) for r in results.values()) / len(results),
                "total_trades": sum(r.get("total_trades", 0) for r in results.values()),
                "detailed_results": results,
            }

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return {
                "error": str(e),
                "total_return": 0,
                "win_rate": 0,
            }

    def get_generation_status(self, strategy_id: str) -> GeneratedStrategy | None:
        """Get status of a generation request."""
        return self._generation_cache.get(strategy_id)

    def list_generations(self, limit: int = 50) -> list[GeneratedStrategy]:
        """List recent generations."""
        strategies = list(self._generation_cache.values())
        strategies.sort(key=lambda s: s.created_at, reverse=True)
        return strategies[:limit]


# ============================================================================
# Singleton Instance
# ============================================================================

_generator_instance: AIStrategyGenerator | None = None


def get_ai_strategy_generator() -> AIStrategyGenerator:
    """Get the singleton AI Strategy Generator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = AIStrategyGenerator()
    return _generator_instance
