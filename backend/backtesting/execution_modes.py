"""
Execution Modes Module

TradingView strategy execution modes for controlling when orders are processed.

Execution Modes:
1. on_bar_close (default): Strategy calculates on bar close, orders execute on next bar open
2. on_each_tick / calc_on_every_tick: Strategy calculates on every price update
3. on_order_fills: Strategy recalculates after each order fill

TradingView behavior:
- In backtesting: only on_bar_close is meaningful
- calc_on_every_tick = true is for real-time execution
- process_orders_on_close affects when orders are queued vs executed
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from loguru import logger


class ExecutionMode(str, Enum):
    """Strategy execution mode."""

    ON_BAR_CLOSE = "on_bar_close"  # Default: calculate on close, execute on next open
    ON_EACH_TICK = "on_each_tick"  # Real-time: calculate on every tick
    ON_ORDER_FILLS = "on_order_fills"  # Recalculate after each fill


@dataclass
class ExecutionContext:
    """Context for strategy execution."""

    mode: ExecutionMode
    current_bar: int
    bar_timestamp: int  # Unix timestamp
    price: float
    is_bar_close: bool
    is_order_fill: bool
    tick_id: int  # For tick-by-tick mode


class ExecutionController:
    """
    Controls strategy execution timing and order processing.

    TradingView execution logic:
    - on_bar_close: Most common, all calculations happen at bar close
    - calc_on_every_tick: For real-time, not meaningful in backtest
    - process_orders_on_close: Queue orders until bar close
    """

    def __init__(
        self,
        execution_mode: str = "on_bar_close",
        calc_on_every_tick: bool = False,
        process_orders_on_close: bool = True,
    ):
        """
        Initialize Execution Controller.

        Args:
            execution_mode: 'on_bar_close', 'on_each_tick', 'on_order_fills'
            calc_on_every_tick: Enable tick-by-tick calculation
            process_orders_on_close: Process orders at bar close only
        """
        self.mode = ExecutionMode(execution_mode)
        self.calc_on_every_tick = calc_on_every_tick
        self.process_orders_on_close = process_orders_on_close

        self._pending_orders: list[dict] = []
        self._fills_this_bar: list[dict] = []
        self._current_bar = 0
        self._tick_id = 0

        logger.info(
            f"Execution Controller: mode={self.mode.value}, "
            f"calc_every_tick={calc_on_every_tick}, "
            f"process_on_close={process_orders_on_close}"
        )

    def should_calculate(
        self, is_bar_close: bool, is_tick: bool = False, is_order_fill: bool = False
    ) -> bool:
        """
        Determine if strategy should calculate based on current event.

        Args:
            is_bar_close: Is this a bar close event?
            is_tick: Is this a tick event?
            is_order_fill: Is this an order fill event?

        Returns:
            True if strategy should calculate
        """
        if self.mode == ExecutionMode.ON_BAR_CLOSE:
            return is_bar_close

        elif self.mode == ExecutionMode.ON_EACH_TICK:
            # In backtest, simulate with bar close only
            # Real-time would need tick data
            return is_bar_close or (is_tick and self.calc_on_every_tick)

        elif self.mode == ExecutionMode.ON_ORDER_FILLS:
            # Calculate on bar close AND after each fill
            return is_bar_close or is_order_fill

        return is_bar_close

    def should_process_orders(self, is_bar_close: bool) -> bool:
        """
        Determine if pending orders should be processed now.

        Args:
            is_bar_close: Is this bar close?

        Returns:
            True if orders should be processed
        """
        if self.process_orders_on_close:
            return is_bar_close
        return True  # Process immediately

    def queue_order(self, order: dict) -> None:
        """
        Queue an order for processing.

        Args:
            order: Order dict with type, price, side, etc.
        """
        order["queued_bar"] = self._current_bar
        order["queued_tick"] = self._tick_id
        self._pending_orders.append(order)
        logger.debug(f"Order queued: {order}")

    def get_pending_orders(self) -> list[dict]:
        """Get list of pending orders."""
        return self._pending_orders.copy()

    def clear_pending_orders(self) -> list[dict]:
        """Clear and return all pending orders."""
        orders = self._pending_orders
        self._pending_orders = []
        return orders

    def record_fill(self, fill: dict) -> None:
        """
        Record an order fill.

        Args:
            fill: Fill dict with price, size, etc.
        """
        fill["bar"] = self._current_bar
        fill["tick"] = self._tick_id
        self._fills_this_bar.append(fill)
        logger.debug(f"Fill recorded: {fill}")

    def get_fills_this_bar(self) -> list[dict]:
        """Get fills that occurred on current bar."""
        return self._fills_this_bar.copy()

    def advance_bar(self) -> None:
        """Advance to next bar, clearing per-bar state."""
        self._current_bar += 1
        self._fills_this_bar = []
        self._tick_id = 0

    def advance_tick(self) -> None:
        """Advance tick counter within bar."""
        self._tick_id += 1

    def create_context(
        self,
        bar_timestamp: int,
        price: float,
        is_bar_close: bool = True,
        is_order_fill: bool = False,
    ) -> ExecutionContext:
        """
        Create execution context for current state.

        Args:
            bar_timestamp: Unix timestamp
            price: Current price
            is_bar_close: Is bar close event
            is_order_fill: Is order fill event

        Returns:
            ExecutionContext
        """
        return ExecutionContext(
            mode=self.mode,
            current_bar=self._current_bar,
            bar_timestamp=bar_timestamp,
            price=price,
            is_bar_close=is_bar_close,
            is_order_fill=is_order_fill,
            tick_id=self._tick_id,
        )


class IntrabarSimulator:
    """
    Simulates intrabar execution for on_each_tick mode.

    Since backtests only have OHLC, this simulates tick-by-tick
    execution by generating synthetic ticks from the bar.
    """

    def __init__(self, ticks_per_bar: int = 4):
        """
        Initialize Intrabar Simulator.

        Args:
            ticks_per_bar: Number of synthetic ticks per bar
        """
        self.ticks_per_bar = ticks_per_bar

    def generate_ticks(
        self, open_price: float, high_price: float, low_price: float, close_price: float
    ) -> list[float]:
        """
        Generate synthetic ticks from OHLC.

        Uses TradingView heuristic:
        - If Open closer to High: O → H → L → C
        - If Open closer to Low: O → L → H → C

        Args:
            open_price: Bar open
            high_price: Bar high
            low_price: Bar low
            close_price: Bar close

        Returns:
            List of tick prices
        """
        o, h, c = open_price, high_price, close_price
        low = low_price

        if abs(o - h) < abs(o - low):
            # Open closer to high - went up first
            return [o, h, low, c]
        else:
            # Open closer to low - went down first
            return [o, low, h, c]

    def simulate_bar_execution(
        self,
        ohlc: dict,
        strategy_callback: Callable[[float, int], None],
        controller: ExecutionController,
    ) -> None:
        """
        Simulate tick-by-tick execution within a bar.

        Args:
            ohlc: Dict with open, high, low, close
            strategy_callback: Function to call on each tick (price, tick_id)
            controller: ExecutionController instance
        """
        ticks = self.generate_ticks(
            ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"]
        )

        for i, price in enumerate(ticks):
            controller.advance_tick()
            is_last = i == len(ticks) - 1

            if controller.should_calculate(is_bar_close=is_last, is_tick=True):
                strategy_callback(price, controller._tick_id)


def create_execution_controller(config) -> ExecutionController:
    """
    Create ExecutionController from BacktestConfig.

    Args:
        config: BacktestConfig object

    Returns:
        Configured ExecutionController
    """
    return ExecutionController(
        execution_mode=getattr(config, "execution_mode", "on_bar_close"),
        calc_on_every_tick=getattr(config, "calc_on_every_tick", False),
        process_orders_on_close=getattr(config, "process_orders_on_close", True),
    )
