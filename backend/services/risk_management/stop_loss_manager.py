"""
Stop Loss Management Module.

Provides advanced stop loss strategies:
- Fixed stop loss
- Trailing stop loss
- Breakeven stop
- Time-based stop
- Volatility-based stop (ATR)
- Chandelier exit
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StopLossType(str, Enum):
    """Stop loss types."""

    FIXED = "fixed"
    TRAILING = "trailing"
    TRAILING_PERCENT = "trailing_percent"
    BREAKEVEN = "breakeven"
    TIME_BASED = "time_based"
    ATR_BASED = "atr_based"
    CHANDELIER = "chandelier"
    PARABOLIC_SAR = "parabolic_sar"


class StopLossState(str, Enum):
    """Stop loss states."""

    PENDING = "pending"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    MOVED_TO_BREAKEVEN = "breakeven"


@dataclass
class StopLossOrder:
    """Stop loss order representation."""

    id: str
    symbol: str
    side: str  # "long" or "short"
    stop_type: StopLossType
    initial_stop: float
    current_stop: float
    entry_price: float
    position_size: float
    state: StopLossState = StopLossState.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggered_at: Optional[datetime] = None
    triggered_price: Optional[float] = None

    # Trailing specific
    trail_distance: float = 0.0
    trail_percent: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = float("inf")

    # Breakeven specific
    breakeven_trigger_pct: float = 0.0
    breakeven_offset: float = 0.0
    is_at_breakeven: bool = False

    # Time-based specific
    time_limit: Optional[timedelta] = None
    expire_at: Optional[datetime] = None

    # ATR-based specific
    atr_multiplier: float = 2.0
    current_atr: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "stop_type": self.stop_type.value,
            "initial_stop": self.initial_stop,
            "current_stop": self.current_stop,
            "entry_price": self.entry_price,
            "position_size": self.position_size,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "triggered_at": self.triggered_at.isoformat()
            if self.triggered_at
            else None,
            "triggered_price": self.triggered_price,
            "trail_distance": self.trail_distance,
            "trail_percent": self.trail_percent,
            "is_at_breakeven": self.is_at_breakeven,
        }


@dataclass
class StopLossConfig:
    """Stop loss configuration."""

    # Trailing
    trail_distance: float = 50.0  # Fixed distance in price
    trail_percent: float = 2.0  # Trailing percent

    # Breakeven
    breakeven_trigger_pct: float = 1.0  # % profit to move to breakeven
    breakeven_offset: float = 5.0  # Offset above entry (buffer)

    # Time-based
    max_hold_time: timedelta = timedelta(hours=24)

    # ATR
    atr_multiplier: float = 2.0
    atr_period: int = 14

    # Chandelier
    chandelier_multiplier: float = 3.0
    chandelier_period: int = 22

    # General
    min_stop_distance_pct: float = 0.1  # Minimum 0.1% from current price
    max_stop_distance_pct: float = 10.0  # Maximum 10% from entry


class StopLossManager:
    """
    Manages stop loss orders for positions.

    Features:
    - Multiple stop loss types
    - Automatic trailing
    - Breakeven movement
    - Time-based expiration
    - Volatility adaptation

    Usage:
        manager = StopLossManager()

        # Create trailing stop
        stop = manager.create_stop(
            symbol="BTCUSDT",
            side="long",
            entry_price=50000,
            position_size=0.1,
            stop_type=StopLossType.TRAILING_PERCENT,
            trail_percent=2.0
        )

        # Update on price change
        triggered = manager.update(stop.id, current_price=51000)

        # Check if triggered
        if triggered:
            print(f"Stop triggered at {stop.triggered_price}")
    """

    def __init__(self, config: Optional[StopLossConfig] = None):
        self.config = config or StopLossConfig()
        self.stops: Dict[str, StopLossOrder] = {}
        self.stop_counter = 0

        # Callbacks
        self.on_stop_triggered: Optional[Callable[[StopLossOrder], None]] = None
        self.on_stop_moved: Optional[Callable[[StopLossOrder, float], None]] = None

        logger.info("StopLossManager initialized")

    def _generate_id(self) -> str:
        """Generate unique stop ID."""
        self.stop_counter += 1
        return f"SL_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{self.stop_counter}"

    def create_stop(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        position_size: float,
        stop_type: StopLossType = StopLossType.FIXED,
        initial_stop: Optional[float] = None,
        trail_distance: Optional[float] = None,
        trail_percent: Optional[float] = None,
        breakeven_trigger_pct: Optional[float] = None,
        time_limit: Optional[timedelta] = None,
        atr_value: Optional[float] = None,
        atr_multiplier: Optional[float] = None,
    ) -> StopLossOrder:
        """
        Create a new stop loss order.

        Args:
            symbol: Trading symbol
            side: Position side ("long" or "short")
            entry_price: Entry price
            position_size: Position size
            stop_type: Type of stop loss
            initial_stop: Initial stop price (for FIXED type)
            trail_distance: Trailing distance in price units
            trail_percent: Trailing percent
            breakeven_trigger_pct: % profit to trigger breakeven
            time_limit: Time limit for TIME_BASED stop
            atr_value: Current ATR value
            atr_multiplier: ATR multiplier for stop distance

        Returns:
            StopLossOrder
        """
        stop_id = self._generate_id()

        # Determine initial stop price
        if initial_stop:
            stop_price = initial_stop
        elif stop_type == StopLossType.ATR_BASED and atr_value:
            mult = atr_multiplier or self.config.atr_multiplier
            distance = atr_value * mult
            if side == "long":
                stop_price = entry_price - distance
            else:
                stop_price = entry_price + distance
        elif stop_type == StopLossType.TRAILING and trail_distance:
            if side == "long":
                stop_price = entry_price - trail_distance
            else:
                stop_price = entry_price + trail_distance
        elif stop_type == StopLossType.TRAILING_PERCENT and trail_percent:
            distance = entry_price * (trail_percent / 100)
            if side == "long":
                stop_price = entry_price - distance
            else:
                stop_price = entry_price + distance
        else:
            # Default 2% stop
            distance = entry_price * 0.02
            if side == "long":
                stop_price = entry_price - distance
            else:
                stop_price = entry_price + distance

        # Create stop order
        stop = StopLossOrder(
            id=stop_id,
            symbol=symbol,
            side=side,
            stop_type=stop_type,
            initial_stop=stop_price,
            current_stop=stop_price,
            entry_price=entry_price,
            position_size=position_size,
            state=StopLossState.ACTIVE,
            trail_distance=trail_distance or self.config.trail_distance,
            trail_percent=trail_percent or self.config.trail_percent,
            highest_price=entry_price,
            lowest_price=entry_price,
            breakeven_trigger_pct=breakeven_trigger_pct
            or self.config.breakeven_trigger_pct,
            breakeven_offset=self.config.breakeven_offset,
            time_limit=time_limit or self.config.max_hold_time,
            atr_multiplier=atr_multiplier or self.config.atr_multiplier,
            current_atr=atr_value or 0.0,
        )

        # Set expiry for time-based
        if stop_type == StopLossType.TIME_BASED and stop.time_limit:
            stop.expire_at = datetime.now(timezone.utc) + stop.time_limit

        self.stops[stop_id] = stop
        logger.info(
            f"Created {stop_type.value} stop for {symbol} {side}: "
            f"entry=${entry_price:.2f}, stop=${stop_price:.2f}"
        )

        return stop

    def update(
        self,
        stop_id: str,
        current_price: float,
        current_atr: Optional[float] = None,
    ) -> bool:
        """
        Update stop loss based on current price.

        Args:
            stop_id: Stop order ID
            current_price: Current market price
            current_atr: Current ATR value (for ATR-based)

        Returns:
            True if stop was triggered
        """
        stop = self.stops.get(stop_id)
        if not stop or stop.state != StopLossState.ACTIVE:
            return False

        stop.updated_at = datetime.now(timezone.utc)

        # Check time-based expiration
        if stop.stop_type == StopLossType.TIME_BASED:
            if stop.expire_at and datetime.now(timezone.utc) >= stop.expire_at:
                return self._trigger_stop(stop, current_price, "time_expired")

        # Update highest/lowest
        if current_price > stop.highest_price:
            stop.highest_price = current_price
        if current_price < stop.lowest_price:
            stop.lowest_price = current_price

        # Check if stop is hit
        if self._is_stop_hit(stop, current_price):
            return self._trigger_stop(stop, current_price, "price_hit")

        # Update trailing stops
        if stop.stop_type in (StopLossType.TRAILING, StopLossType.TRAILING_PERCENT):
            self._update_trailing(stop, current_price)
        elif stop.stop_type == StopLossType.CHANDELIER:
            self._update_chandelier(stop, current_price, current_atr)
        elif stop.stop_type == StopLossType.ATR_BASED and current_atr:
            self._update_atr_stop(stop, current_price, current_atr)

        # Check breakeven
        if stop.stop_type == StopLossType.BREAKEVEN or not stop.is_at_breakeven:
            self._check_breakeven(stop, current_price)

        return False

    def _is_stop_hit(self, stop: StopLossOrder, current_price: float) -> bool:
        """Check if stop price is hit."""
        if stop.side == "long":
            return current_price <= stop.current_stop
        else:
            return current_price >= stop.current_stop

    def _trigger_stop(self, stop: StopLossOrder, price: float, reason: str) -> bool:
        """Trigger stop loss."""
        stop.state = StopLossState.TRIGGERED
        stop.triggered_at = datetime.now(timezone.utc)
        stop.triggered_price = price

        logger.warning(
            f"Stop triggered for {stop.symbol}: "
            f"reason={reason}, price=${price:.2f}, "
            f"entry=${stop.entry_price:.2f}"
        )

        # Callback
        if self.on_stop_triggered:
            try:
                self.on_stop_triggered(stop)
            except Exception as e:
                logger.error(f"Stop trigger callback error: {e}")

        return True

    def _update_trailing(self, stop: StopLossOrder, current_price: float):
        """Update trailing stop."""
        old_stop = stop.current_stop

        if stop.stop_type == StopLossType.TRAILING_PERCENT:
            distance = current_price * (stop.trail_percent / 100)
        else:
            distance = stop.trail_distance

        if stop.side == "long":
            # For long: trail up, never down
            new_stop = current_price - distance
            if new_stop > stop.current_stop:
                stop.current_stop = new_stop
        else:
            # For short: trail down, never up
            new_stop = current_price + distance
            if new_stop < stop.current_stop:
                stop.current_stop = new_stop

        if stop.current_stop != old_stop:
            stop.updated_at = datetime.now(timezone.utc)
            logger.debug(
                f"Trailing stop moved: {stop.symbol} "
                f"${old_stop:.2f} -> ${stop.current_stop:.2f}"
            )
            if self.on_stop_moved:
                self.on_stop_moved(stop, old_stop)

    def _update_chandelier(
        self,
        stop: StopLossOrder,
        current_price: float,
        current_atr: Optional[float],
    ):
        """Update Chandelier exit stop."""
        if not current_atr:
            return

        old_stop = stop.current_stop
        distance = current_atr * self.config.chandelier_multiplier

        if stop.side == "long":
            # Chandelier for long: highest high - ATR*multiplier
            new_stop = stop.highest_price - distance
            if new_stop > stop.current_stop:
                stop.current_stop = new_stop
        else:
            # Chandelier for short: lowest low + ATR*multiplier
            new_stop = stop.lowest_price + distance
            if new_stop < stop.current_stop:
                stop.current_stop = new_stop

        if stop.current_stop != old_stop:
            stop.updated_at = datetime.now(timezone.utc)
            stop.current_atr = current_atr

    def _update_atr_stop(
        self,
        stop: StopLossOrder,
        current_price: float,
        current_atr: float,
    ):
        """Update ATR-based stop."""
        old_stop = stop.current_stop
        distance = current_atr * stop.atr_multiplier

        if stop.side == "long":
            new_stop = current_price - distance
            # Only move up for longs
            if new_stop > stop.current_stop:
                stop.current_stop = new_stop
        else:
            new_stop = current_price + distance
            # Only move down for shorts
            if new_stop < stop.current_stop:
                stop.current_stop = new_stop

        if stop.current_stop != old_stop:
            stop.updated_at = datetime.now(timezone.utc)
            stop.current_atr = current_atr

    def _check_breakeven(self, stop: StopLossOrder, current_price: float):
        """Check and apply breakeven stop."""
        if stop.is_at_breakeven:
            return

        # Calculate profit %
        if stop.side == "long":
            profit_pct = ((current_price - stop.entry_price) / stop.entry_price) * 100
        else:
            profit_pct = ((stop.entry_price - current_price) / stop.entry_price) * 100

        # Check if we should move to breakeven
        if profit_pct >= stop.breakeven_trigger_pct:
            old_stop = stop.current_stop

            # Move stop to entry + offset
            if stop.side == "long":
                new_stop = stop.entry_price + stop.breakeven_offset
                # Only if it's an improvement
                if new_stop > stop.current_stop:
                    stop.current_stop = new_stop
                    stop.is_at_breakeven = True
            else:
                new_stop = stop.entry_price - stop.breakeven_offset
                if new_stop < stop.current_stop:
                    stop.current_stop = new_stop
                    stop.is_at_breakeven = True

            if stop.is_at_breakeven:
                stop.state = StopLossState.MOVED_TO_BREAKEVEN
                stop.updated_at = datetime.now(timezone.utc)
                logger.info(
                    f"Stop moved to breakeven for {stop.symbol}: "
                    f"${old_stop:.2f} -> ${stop.current_stop:.2f}"
                )
                if self.on_stop_moved:
                    self.on_stop_moved(stop, old_stop)

    def get_stop(self, stop_id: str) -> Optional[StopLossOrder]:
        """Get stop order by ID."""
        return self.stops.get(stop_id)

    def get_stops_for_symbol(self, symbol: str) -> List[StopLossOrder]:
        """Get all stops for a symbol."""
        return [s for s in self.stops.values() if s.symbol == symbol]

    def get_active_stops(self) -> List[StopLossOrder]:
        """Get all active stops."""
        return [
            s
            for s in self.stops.values()
            if s.state in (StopLossState.ACTIVE, StopLossState.MOVED_TO_BREAKEVEN)
        ]

    def cancel_stop(self, stop_id: str) -> bool:
        """Cancel a stop order."""
        stop = self.stops.get(stop_id)
        if stop and stop.state == StopLossState.ACTIVE:
            stop.state = StopLossState.CANCELLED
            stop.updated_at = datetime.now(timezone.utc)
            logger.info(f"Stop cancelled: {stop_id}")
            return True
        return False

    def cancel_all_for_symbol(self, symbol: str) -> int:
        """Cancel all stops for a symbol."""
        count = 0
        for stop in self.get_stops_for_symbol(symbol):
            if self.cancel_stop(stop.id):
                count += 1
        return count

    def modify_stop(
        self,
        stop_id: str,
        new_stop_price: Optional[float] = None,
        trail_percent: Optional[float] = None,
        trail_distance: Optional[float] = None,
    ) -> bool:
        """Modify existing stop order."""
        stop = self.stops.get(stop_id)
        if not stop or stop.state != StopLossState.ACTIVE:
            return False

        if new_stop_price:
            stop.current_stop = new_stop_price
        if trail_percent:
            stop.trail_percent = trail_percent
        if trail_distance:
            stop.trail_distance = trail_distance

        stop.updated_at = datetime.now(timezone.utc)
        logger.info(f"Stop modified: {stop_id}")
        return True

    def update_all(
        self,
        prices: Dict[str, float],
        atr_values: Optional[Dict[str, float]] = None,
    ) -> List[StopLossOrder]:
        """
        Update all stops with current prices.

        Args:
            prices: Dict of symbol -> current price
            atr_values: Dict of symbol -> current ATR

        Returns:
            List of triggered stops
        """
        triggered = []

        for stop in self.get_active_stops():
            price = prices.get(stop.symbol)
            if price:
                atr = atr_values.get(stop.symbol) if atr_values else None
                if self.update(stop.id, price, atr):
                    triggered.append(stop)

        return triggered

    def get_summary(self) -> Dict[str, Any]:
        """Get stop loss manager summary."""
        active = self.get_active_stops()

        return {
            "total_stops": len(self.stops),
            "active_stops": len(active),
            "stops_by_type": {
                t.value: len([s for s in active if s.stop_type == t])
                for t in StopLossType
            },
            "at_breakeven": len([s for s in active if s.is_at_breakeven]),
            "triggered_count": len(
                [s for s in self.stops.values() if s.state == StopLossState.TRIGGERED]
            ),
        }
