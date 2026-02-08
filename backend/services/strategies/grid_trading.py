"""
Grid Trading Strategy.

Automated grid trading that places buy/sell orders at regular intervals.
Profits from price oscillation within a range.
"""

import logging
from dataclasses import dataclass

from backend.services.live_trading.strategy_runner import (
    SignalType,
    StrategyConfig,
    TradingSignal,
)
from backend.services.strategies.base import (
    LibraryStrategy,
    ParameterSpec,
    ParameterType,
    StrategyCategory,
    StrategyInfo,
    register_strategy,
)

logger = logging.getLogger(__name__)


@dataclass
class GridLevel:
    """Represents a grid level."""

    price: float
    type: str  # "buy" or "sell"
    order_id: str | None = None
    filled: bool = False
    fill_price: float | None = None


@dataclass
class GridTradingParams:
    """Parameters for Grid Trading strategy."""

    grid_lower: float = 0.0  # Lower bound (0 = auto from ATR)
    grid_upper: float = 0.0  # Upper bound (0 = auto from ATR)
    num_grids: int = 10
    position_per_grid: float = 1.0  # % of equity per grid
    atr_range_multiplier: float = 3.0  # For auto range calculation
    take_profit_per_grid: bool = True
    max_open_grids: int = 5


GRID_TRADING_INFO = StrategyInfo(
    id="grid_trading",
    name="Grid Trading",
    description="""
    Automated grid trading strategy.

    Places a grid of buy and sell orders at regular price intervals.
    Profits from price oscillation within the defined range.

    How it works:
    1. Define price range (upper, lower bounds)
    2. Divide range into N equal grid levels
    3. Place buy orders below current price
    4. Place sell orders above current price
    5. When buy fills, place sell at next grid up (and vice versa)

    Best for: Ranging/sideways markets with good volatility.
    Avoid in: Strong trending markets (risk of all grids filling one direction).

    Risk: Can accumulate large positions if price moves strongly in one direction.
    """,
    category=StrategyCategory.GRID_TRADING,
    version="1.0.0",
    author="System",
    min_candles=50,
    recommended_timeframes=["5", "15", "60"],
    suitable_markets=["crypto", "forex"],
    avg_trades_per_day=10.0,
    expected_win_rate=0.85,  # High win rate but small wins
    expected_risk_reward=0.5,  # Small profits per trade
    typical_holding_period="minutes",
    risk_level="moderate",
    max_drawdown_expected=0.20,
    parameters=[
        ParameterSpec(
            name="grid_lower",
            param_type=ParameterType.FLOAT,
            default=0.0,
            description="Lower grid bound (0 = auto)",
            min_value=0.0,
            max_value=1000000.0,
            optimize=False,
        ),
        ParameterSpec(
            name="grid_upper",
            param_type=ParameterType.FLOAT,
            default=0.0,
            description="Upper grid bound (0 = auto)",
            min_value=0.0,
            max_value=1000000.0,
            optimize=False,
        ),
        ParameterSpec(
            name="num_grids",
            param_type=ParameterType.INT,
            default=10,
            description="Number of grid levels",
            min_value=5,
            max_value=50,
            step=5,
        ),
        ParameterSpec(
            name="position_per_grid",
            param_type=ParameterType.FLOAT,
            default=1.0,
            description="% of equity per grid order",
            min_value=0.5,
            max_value=5.0,
            step=0.5,
        ),
        ParameterSpec(
            name="atr_range_multiplier",
            param_type=ParameterType.FLOAT,
            default=3.0,
            description="ATR multiplier for auto range",
            min_value=2.0,
            max_value=6.0,
            step=0.5,
        ),
        ParameterSpec(
            name="take_profit_per_grid",
            param_type=ParameterType.BOOL,
            default=True,
            description="Take profit at each grid level",
        ),
        ParameterSpec(
            name="max_open_grids",
            param_type=ParameterType.INT,
            default=5,
            description="Maximum open positions",
            min_value=1,
            max_value=20,
            step=1,
        ),
    ],
    tags=["grid", "automation", "range", "scalping"],
)


@register_strategy
class GridTradingStrategy(LibraryStrategy):
    """
    Grid Trading Strategy.

    Automatically places buy/sell orders at grid levels.
    """

    STRATEGY_INFO = GRID_TRADING_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        # Grid state
        self._grid_initialized: bool = False
        self._grid_levels: list[GridLevel] = []
        self._grid_lower: float = 0.0
        self._grid_upper: float = 0.0
        self._grid_step: float = 0.0

        # Position tracking
        self._open_positions: dict[float, dict] = {}  # price -> position info
        self._last_signal_price: float | None = None

    def _initialize_grid(self, current_price: float, atr: float):
        """Initialize grid levels around current price."""
        lower = self.get_param("grid_lower", 0.0)
        upper = self.get_param("grid_upper", 0.0)
        num_grids = self.get_param("num_grids", 10)
        atr_mult = self.get_param("atr_range_multiplier", 3.0)

        # Auto-calculate range if not specified
        if lower <= 0 or upper <= 0:
            range_size = atr * atr_mult
            self._grid_lower = current_price - range_size
            self._grid_upper = current_price + range_size
        else:
            self._grid_lower = lower
            self._grid_upper = upper

        # Calculate grid step
        self._grid_step = (self._grid_upper - self._grid_lower) / num_grids

        # Create grid levels
        self._grid_levels = []
        for i in range(num_grids + 1):
            price = self._grid_lower + (i * self._grid_step)
            level_type = "buy" if price < current_price else "sell"
            self._grid_levels.append(GridLevel(price=price, type=level_type))

        self._grid_initialized = True
        logger.info(
            f"Grid initialized: {self._grid_lower:.2f} - {self._grid_upper:.2f}, "
            f"step: {self._grid_step:.2f}, levels: {len(self._grid_levels)}"
        )

    def _find_nearest_grid(self, price: float, direction: str) -> GridLevel | None:
        """Find nearest unfilled grid level in given direction."""
        candidates = []

        for level in self._grid_levels:
            if level.filled:
                continue

            if (direction == "down" and level.type == "buy" and level.price < price) or (direction == "up" and level.type == "sell" and level.price > price):
                candidates.append(level)

        if not candidates:
            return None

        if direction == "down":
            return max(candidates, key=lambda x: x.price)  # Nearest below
        else:
            return min(candidates, key=lambda x: x.price)  # Nearest above

    def on_candle(self, candle: dict) -> TradingSignal | None:
        """Process candle and generate grid trading signals."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        close = candle["close"]
        low = candle["low"]
        high = candle["high"]

        # Initialize grid on first valid candle
        if not self._grid_initialized:
            atr = self.atr(14)
            if atr > 0:
                self._initialize_grid(close, atr)
            return None

        max_open = self.get_param("max_open_grids", 5)

        # Check for grid level crossings
        for level in self._grid_levels:
            if level.filled:
                continue

            # Price crossed this level
            if low <= level.price <= high:
                # Check max positions
                if len(self._open_positions) >= max_open:
                    continue

                # Avoid repeated signals at same level
                if (
                    self._last_signal_price
                    and abs(self._last_signal_price - level.price)
                    < self._grid_step * 0.5
                ):
                    continue

                if level.type == "buy":
                    # Buy at this level
                    signal = self.create_signal(
                        signal_type=SignalType.BUY,
                        price=level.price,
                        take_profit=level.price + self._grid_step,
                        stop_loss=self._grid_lower,
                        reason=f"Grid BUY at {level.price:.2f}",
                        confidence=0.6,
                        grid_level=level.price,
                        grid_type="buy",
                    )

                    level.filled = True
                    level.fill_price = close
                    self._open_positions[level.price] = {
                        "type": "long",
                        "entry": close,
                        "target": level.price + self._grid_step,
                    }
                    self._last_signal_price = level.price

                    # Convert corresponding sell level to take profit target
                    self._update_grid_after_fill(level.price, "buy")

                    return signal

                elif level.type == "sell":
                    # Sell at this level
                    signal = self.create_signal(
                        signal_type=SignalType.SELL,
                        price=level.price,
                        take_profit=level.price - self._grid_step,
                        stop_loss=self._grid_upper,
                        reason=f"Grid SELL at {level.price:.2f}",
                        confidence=0.6,
                        grid_level=level.price,
                        grid_type="sell",
                    )

                    level.filled = True
                    level.fill_price = close
                    self._open_positions[level.price] = {
                        "type": "short",
                        "entry": close,
                        "target": level.price - self._grid_step,
                    }
                    self._last_signal_price = level.price

                    # Convert corresponding buy level
                    self._update_grid_after_fill(level.price, "sell")

                    return signal

        # Check for take profit on open positions
        positions_to_close = []
        for entry_price, pos in self._open_positions.items():
            if pos["type"] == "long" and high >= pos["target"]:
                positions_to_close.append((entry_price, "long", pos["target"]))
            elif pos["type"] == "short" and low <= pos["target"]:
                positions_to_close.append((entry_price, "short", pos["target"]))

        # Generate close signals for take profits
        for entry_price, pos_type, target in positions_to_close:
            if pos_type == "long":
                signal = self.create_signal(
                    signal_type=SignalType.CLOSE_LONG,
                    price=target,
                    reason=f"Grid TP at {target:.2f}",
                    confidence=0.7,
                )
            else:
                signal = self.create_signal(
                    signal_type=SignalType.CLOSE_SHORT,
                    price=target,
                    reason=f"Grid TP at {target:.2f}",
                    confidence=0.7,
                )

            # Reset grid level
            del self._open_positions[entry_price]
            for level in self._grid_levels:
                if abs(level.price - entry_price) < 0.01:
                    level.filled = False
                    break

            return signal

        return None

    def _update_grid_after_fill(self, filled_price: float, filled_type: str):
        """Update grid levels after a fill."""
        # After a buy fills, the next grid up becomes the take profit (sell)
        # After a sell fills, the next grid down becomes the take profit (buy)
        pass  # Simple implementation - TP is handled in position tracking


# Factory functions
def create_conservative_grid_strategy(config: StrategyConfig) -> GridTradingStrategy:
    """Create conservative grid strategy (wider grids, fewer positions)."""
    return GridTradingStrategy(
        config,
        num_grids=6,
        position_per_grid=0.5,
        atr_range_multiplier=4.0,
        max_open_grids=3,
    )


def create_moderate_grid_strategy(config: StrategyConfig) -> GridTradingStrategy:
    """Create moderate grid strategy."""
    return GridTradingStrategy(
        config,
        num_grids=10,
        position_per_grid=1.0,
        atr_range_multiplier=3.0,
        max_open_grids=5,
    )
