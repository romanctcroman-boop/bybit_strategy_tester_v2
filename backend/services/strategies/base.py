"""
Strategy Library Base Classes and Registry.

Provides common infrastructure for all strategies:
- StrategyInfo: Metadata about a strategy
- ParameterSpec: Parameter specification for optimization
- StrategyRegistry: Central registry for all strategies
"""

import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from backend.services.live_trading.strategy_runner import (
    BaseStrategy,
    SignalType,
    StrategyConfig,
    TradingSignal,
)

logger = logging.getLogger(__name__)


class StrategyCategory(Enum):
    """Strategy category for organization."""

    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    GRID_TRADING = "grid_trading"
    DCA = "dca"
    SCALPING = "scalping"
    SWING_TRADING = "swing_trading"
    ARBITRAGE = "arbitrage"
    CUSTOM = "custom"


class ParameterType(Enum):
    """Parameter types for optimization."""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    CATEGORICAL = "categorical"


@dataclass
class ParameterSpec:
    """
    Specification for a strategy parameter.

    Used for parameter optimization with tools like Optuna.
    """

    name: str
    param_type: ParameterType
    default: Any
    description: str = ""

    # Numeric bounds (for INT, FLOAT)
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None

    # Categorical options (for CATEGORICAL)
    choices: list[Any] | None = None

    # Optimization settings
    optimize: bool = True
    log_scale: bool = False  # Use logarithmic scale for optimization

    def to_optuna_spec(self) -> dict[str, Any]:
        """Convert to Optuna parameter specification."""
        spec = {
            "name": self.name,
            "type": self.param_type.value,
        }

        if self.param_type == ParameterType.INT:
            spec["low"] = int(self.min_value or 1)
            spec["high"] = int(self.max_value or 100)
            if self.step:
                spec["step"] = int(self.step)

        elif self.param_type == ParameterType.FLOAT:
            spec["low"] = self.min_value or 0.0
            spec["high"] = self.max_value or 1.0
            if self.step:
                spec["step"] = self.step
            if self.log_scale:
                spec["log"] = True

        elif self.param_type == ParameterType.BOOL:
            spec["choices"] = [True, False]

        elif self.param_type == ParameterType.CATEGORICAL:
            spec["choices"] = self.choices or []

        return spec


@dataclass
class StrategyInfo:
    """
    Metadata about a trading strategy.

    Contains all information needed to display, configure, and optimize.
    """

    id: str
    name: str
    description: str
    category: StrategyCategory
    version: str = "1.0.0"
    author: str = "System"

    # Requirements
    min_candles: int = 50  # Minimum candles needed
    recommended_timeframes: list[str] = field(
        default_factory=lambda: ["15", "60", "240"]
    )
    suitable_markets: list[str] = field(
        default_factory=lambda: ["crypto", "forex", "stocks"]
    )

    # Performance characteristics
    avg_trades_per_day: float = 1.0
    expected_win_rate: float = 0.5
    expected_risk_reward: float = 2.0
    typical_holding_period: str = "hours"  # minutes, hours, days, weeks

    # Risk profile
    risk_level: str = "moderate"  # conservative, moderate, aggressive
    max_drawdown_expected: float = 0.15  # 15%

    # Parameters
    parameters: list[ParameterSpec] = field(default_factory=list)

    # Tags for search/filter
    tags: list[str] = field(default_factory=list)

    def get_optimization_space(self) -> dict[str, dict[str, Any]]:
        """Get parameter space for optimization."""
        return {p.name: p.to_optuna_spec() for p in self.parameters if p.optimize}

    def get_defaults(self) -> dict[str, Any]:
        """Get default parameter values."""
        return {p.name: p.default for p in self.parameters}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "author": self.author,
            "min_candles": self.min_candles,
            "recommended_timeframes": self.recommended_timeframes,
            "suitable_markets": self.suitable_markets,
            "avg_trades_per_day": self.avg_trades_per_day,
            "expected_win_rate": self.expected_win_rate,
            "expected_risk_reward": self.expected_risk_reward,
            "typical_holding_period": self.typical_holding_period,
            "risk_level": self.risk_level,
            "max_drawdown_expected": self.max_drawdown_expected,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.param_type.value,
                    "default": p.default,
                    "description": p.description,
                    "min_value": p.min_value,
                    "max_value": p.max_value,
                    "step": p.step,
                    "choices": p.choices,
                    "optimize": p.optimize,
                }
                for p in self.parameters
            ],
            "tags": self.tags,
        }


class LibraryStrategy(BaseStrategy):
    """
    Extended base class for library strategies.

    Adds:
    - Strategy info/metadata
    - Parameter validation
    - Performance tracking
    - Signal history
    """

    # Override in subclass
    STRATEGY_INFO: StrategyInfo = None

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config)

        # Store parameters
        self._params = params

        # Apply defaults for missing params
        if self.STRATEGY_INFO:
            defaults = self.STRATEGY_INFO.get_defaults()
            for name, default in defaults.items():
                if name not in self._params:
                    self._params[name] = default

        # Signal history
        self._signal_history: list[TradingSignal] = []
        self._max_signal_history = 100

        # Performance tracking
        self._signals_total = 0
        self._signals_by_type: dict[SignalType, int] = {
            SignalType.BUY: 0,
            SignalType.SELL: 0,
            SignalType.CLOSE_LONG: 0,
            SignalType.CLOSE_SHORT: 0,
            SignalType.HOLD: 0,
        }

    @classmethod
    def get_info(cls) -> StrategyInfo | None:
        """Get strategy metadata."""
        return cls.STRATEGY_INFO

    def get_params(self) -> dict[str, Any]:
        """Get current parameter values."""
        return self._params.copy()

    def get_param(self, name: str, default: Any = None) -> Any:
        """Get a specific parameter value."""
        return self._params.get(name, default)

    def set_param(self, name: str, value: Any):
        """Set a parameter value."""
        self._params[name] = value

    def record_signal(self, signal: TradingSignal):
        """Record a generated signal."""
        self._signals_total += 1
        self._signals_by_type[signal.signal_type] = (
            self._signals_by_type.get(signal.signal_type, 0) + 1
        )

        self._signal_history.append(signal)
        if len(self._signal_history) > self._max_signal_history:
            self._signal_history = self._signal_history[-self._max_signal_history :]

    def get_signal_stats(self) -> dict[str, Any]:
        """Get signal generation statistics."""
        return {
            "total_signals": self._signals_total,
            "by_type": {k.value: v for k, v in self._signals_by_type.items()},
            "recent_signals": len(self._signal_history),
        }

    def create_signal(
        self,
        signal_type: SignalType,
        price: float = 0.0,
        reason: str = "",
        confidence: float = 1.0,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        **metadata,
    ) -> TradingSignal:
        """Helper to create and record a signal."""
        signal = TradingSignal(
            signal_type=signal_type,
            symbol=self.config.symbol,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reason=reason,
            metadata=metadata,
        )
        self.record_signal(signal)
        return signal

    def warmup_complete(self) -> bool:
        """Check if strategy has enough data to generate signals."""
        if self.STRATEGY_INFO:
            return len(self._candles) >= self.STRATEGY_INFO.min_candles
        return len(self._candles) >= 50

    @abstractmethod
    def on_candle(self, candle: dict) -> TradingSignal | None:
        """Process candle and generate signal. Must be implemented."""
        pass


class StrategyRegistry:
    """
    Central registry for all available strategies.

    Provides discovery, filtering, and instantiation of strategies.
    """

    _instance: Optional["StrategyRegistry"] = None
    _strategies: dict[str, type[LibraryStrategy]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, strategy_class: type[LibraryStrategy]):
        """Register a strategy class."""
        if strategy_class.STRATEGY_INFO:
            strategy_id = strategy_class.STRATEGY_INFO.id
            cls._strategies[strategy_id] = strategy_class
            logger.debug(f"Registered strategy: {strategy_id}")
        else:
            logger.warning(f"Strategy {strategy_class.__name__} has no STRATEGY_INFO")

    @classmethod
    def get(cls, strategy_id: str) -> type[LibraryStrategy] | None:
        """Get strategy class by ID."""
        return cls._strategies.get(strategy_id)

    @classmethod
    def list_all(cls) -> list[StrategyInfo]:
        """List all registered strategies."""
        return [s.STRATEGY_INFO for s in cls._strategies.values() if s.STRATEGY_INFO]

    @classmethod
    def list_by_category(cls, category: StrategyCategory) -> list[StrategyInfo]:
        """List strategies by category."""
        return [
            s.STRATEGY_INFO
            for s in cls._strategies.values()
            if s.STRATEGY_INFO and s.STRATEGY_INFO.category == category
        ]

    @classmethod
    def search(
        cls,
        query: str | None = None,
        category: StrategyCategory | None = None,
        risk_level: str | None = None,
        tags: list[str] | None = None,
    ) -> list[StrategyInfo]:
        """Search strategies with filters."""
        results = []

        for strategy_class in cls._strategies.values():
            info = strategy_class.STRATEGY_INFO
            if not info:
                continue

            # Filter by category
            if category and info.category != category:
                continue

            # Filter by risk level
            if risk_level and info.risk_level != risk_level:
                continue

            # Filter by tags
            if tags and not any(t in info.tags for t in tags):
                continue

            # Filter by query
            if query:
                query_lower = query.lower()
                searchable = (
                    f"{info.name} {info.description} {' '.join(info.tags)}"
                ).lower()
                if query_lower not in searchable:
                    continue

            results.append(info)

        return results

    @classmethod
    def create(
        cls, strategy_id: str, config: StrategyConfig, **params
    ) -> LibraryStrategy | None:
        """Create strategy instance by ID."""
        strategy_class = cls.get(strategy_id)
        if not strategy_class:
            logger.error(f"Strategy not found: {strategy_id}")
            return None

        try:
            return strategy_class(config, **params)
        except Exception as e:
            logger.error(f"Failed to create strategy {strategy_id}: {e}")
            return None

    @classmethod
    def get_optimization_space(cls, strategy_id: str) -> dict[str, dict[str, Any]]:
        """Get optimization parameter space for a strategy."""
        strategy_class = cls.get(strategy_id)
        if not strategy_class or not strategy_class.STRATEGY_INFO:
            return {}
        return strategy_class.STRATEGY_INFO.get_optimization_space()


def register_strategy(strategy_class: type[LibraryStrategy]):
    """Decorator to register a strategy."""
    StrategyRegistry.register(strategy_class)
    return strategy_class


# Helper functions for creating signals with common patterns
def calculate_stop_loss(
    entry_price: float, side: str, atr: float, multiplier: float = 2.0
) -> float:
    """Calculate stop loss based on ATR."""
    if side.lower() == "buy":
        return entry_price - (atr * multiplier)
    else:
        return entry_price + (atr * multiplier)


def calculate_take_profit(
    entry_price: float, stop_loss: float, risk_reward: float = 2.0
) -> float:
    """Calculate take profit based on risk/reward ratio."""
    risk = abs(entry_price - stop_loss)
    if entry_price > stop_loss:  # Long
        return entry_price + (risk * risk_reward)
    else:  # Short
        return entry_price - (risk * risk_reward)
