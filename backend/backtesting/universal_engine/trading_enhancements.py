"""
Trading Enhancements Module for Universal Math Engine v2.2.

This module provides practical trading enhancements:
1. Order Types: Limit, Stop-Limit, Trailing Stop, OCO
2. Risk Management: Anti-Liquidation, Break-even Stop, Risk-per-Trade, Drawdown Guardian
3. Trading Filters: News Filter, Session Filter, Cooldown Period
4. Market Simulation: Spread Simulation, Position Aging

Author: Universal Math Engine Team
Version: 2.2.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 1. ORDER TYPES MODULE
# =============================================================================


class OrderType(Enum):
    """Types of orders supported."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"  # One-Cancels-Other


class OrderSide(Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass
class Order:
    """Represents a trading order."""

    order_id: str
    order_type: OrderType
    side: OrderSide
    size: float
    price: Optional[float] = None  # For limit orders
    stop_price: Optional[float] = None  # For stop orders
    trailing_delta: Optional[float] = None  # For trailing stops (as decimal)
    time_in_force: str = "GTC"  # GTC, IOC, FOK
    status: OrderStatus = OrderStatus.PENDING
    filled_size: float = 0.0
    filled_price: float = 0.0
    created_at: int = 0  # Timestamp
    expires_at: Optional[int] = None  # For GTD orders


@dataclass
class TrailingStopConfig:
    """Configuration for trailing stop orders."""

    # Trailing distance as percentage (0.01 = 1%)
    trail_percent: float = 0.01

    # Activation price (optional) - only start trailing after this price
    activation_price: Optional[float] = None

    # Callback rate - how much price must move to update stop
    callback_rate: float = 0.001  # 0.1%

    # Use ATR-based trailing
    use_atr: bool = False
    atr_multiplier: float = 2.0


@dataclass
class OCOConfig:
    """Configuration for OCO (One-Cancels-Other) orders."""

    # Take profit price
    take_profit_price: float = 0.0

    # Stop loss price
    stop_loss_price: float = 0.0

    # Optional limit prices for TP/SL
    take_profit_limit: Optional[float] = None
    stop_loss_limit: Optional[float] = None


class OrderManager:
    """
    Manages different order types and their execution.

    Features:
    - Limit orders with price checking
    - Stop-market and stop-limit orders
    - Trailing stop orders
    - OCO (One-Cancels-Other) orders
    """

    def __init__(self):
        """Initialize order manager."""
        self.pending_orders: list[Order] = []
        self.filled_orders: list[Order] = []
        self.order_counter = 0
        self._trailing_highs: dict[str, float] = {}
        self._trailing_lows: dict[str, float] = {}

    def create_market_order(
        self,
        side: OrderSide,
        size: float,
        timestamp: int = 0,
    ) -> Order:
        """Create a market order."""
        self.order_counter += 1
        return Order(
            order_id=f"ORD-{self.order_counter}",
            order_type=OrderType.MARKET,
            side=side,
            size=size,
            created_at=timestamp,
        )

    def create_limit_order(
        self,
        side: OrderSide,
        size: float,
        price: float,
        time_in_force: str = "GTC",
        timestamp: int = 0,
    ) -> Order:
        """Create a limit order."""
        self.order_counter += 1
        order = Order(
            order_id=f"ORD-{self.order_counter}",
            order_type=OrderType.LIMIT,
            side=side,
            size=size,
            price=price,
            time_in_force=time_in_force,
            created_at=timestamp,
        )
        self.pending_orders.append(order)
        return order

    def create_stop_order(
        self,
        side: OrderSide,
        size: float,
        stop_price: float,
        limit_price: Optional[float] = None,
        timestamp: int = 0,
    ) -> Order:
        """Create a stop-market or stop-limit order."""
        self.order_counter += 1
        order_type = OrderType.STOP_LIMIT if limit_price else OrderType.STOP_MARKET
        order = Order(
            order_id=f"ORD-{self.order_counter}",
            order_type=order_type,
            side=side,
            size=size,
            stop_price=stop_price,
            price=limit_price,
            created_at=timestamp,
        )
        self.pending_orders.append(order)
        return order

    def create_trailing_stop(
        self,
        side: OrderSide,
        size: float,
        config: TrailingStopConfig,
        current_price: float,
        timestamp: int = 0,
    ) -> Order:
        """Create a trailing stop order."""
        self.order_counter += 1
        order = Order(
            order_id=f"ORD-{self.order_counter}",
            order_type=OrderType.TRAILING_STOP,
            side=side,
            size=size,
            trailing_delta=config.trail_percent,
            created_at=timestamp,
        )

        # Initialize trailing reference
        if side == OrderSide.SELL:
            self._trailing_highs[order.order_id] = current_price
            order.stop_price = current_price * (1 - config.trail_percent)
        else:
            self._trailing_lows[order.order_id] = current_price
            order.stop_price = current_price * (1 + config.trail_percent)

        self.pending_orders.append(order)
        return order

    def create_oco_order(
        self,
        side: OrderSide,
        size: float,
        config: OCOConfig,
        timestamp: int = 0,
    ) -> tuple[Order, Order]:
        """Create OCO (One-Cancels-Other) orders."""
        # Take profit order
        tp_order = self.create_limit_order(
            side=side,
            size=size,
            price=config.take_profit_price,
            timestamp=timestamp,
        )
        tp_order.order_type = OrderType.OCO

        # Stop loss order
        sl_order = self.create_stop_order(
            side=side,
            size=size,
            stop_price=config.stop_loss_price,
            limit_price=config.stop_loss_limit,
            timestamp=timestamp,
        )
        sl_order.order_type = OrderType.OCO

        return tp_order, sl_order

    def process_bar(
        self,
        high: float,
        low: float,
        close: float,
        timestamp: int,
    ) -> list[Order]:
        """
        Process pending orders against a price bar.

        Args:
            high: Bar high price
            low: Bar low price
            close: Bar close price
            timestamp: Bar timestamp

        Returns:
            List of filled orders
        """
        filled = []
        remaining = []

        for order in self.pending_orders:
            fill_result = self._check_order_fill(order, high, low, close, timestamp)

            if fill_result is not None:
                order.status = OrderStatus.FILLED
                order.filled_size = order.size
                order.filled_price = fill_result
                filled.append(order)
                self.filled_orders.append(order)
            else:
                # Update trailing stops
                if order.order_type == OrderType.TRAILING_STOP:
                    self._update_trailing_stop(order, high, low)
                remaining.append(order)

        self.pending_orders = remaining

        # Handle OCO - cancel paired orders if one filled
        self._cancel_oco_pairs(filled)

        return filled

    def _check_order_fill(
        self,
        order: Order,
        high: float,
        low: float,
        close: float,
        timestamp: int,
    ) -> Optional[float]:
        """Check if order should be filled, return fill price if so."""
        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and low <= order.price:
                return order.price
            elif order.side == OrderSide.SELL and high >= order.price:
                return order.price

        elif order.order_type in (OrderType.STOP_MARKET, OrderType.STOP_LIMIT):
            triggered = False
            if order.side == OrderSide.SELL and low <= order.stop_price:
                triggered = True
            elif order.side == OrderSide.BUY and high >= order.stop_price:
                triggered = True

            if triggered:
                if order.order_type == OrderType.STOP_LIMIT:
                    # Check if limit price also reachable
                    if order.side == OrderSide.SELL and low <= order.price:
                        return order.price
                    elif order.side == OrderSide.BUY and high >= order.price:
                        return order.price
                else:
                    return order.stop_price

        elif order.order_type == OrderType.TRAILING_STOP:
            if order.side == OrderSide.SELL and low <= order.stop_price:
                return order.stop_price
            elif order.side == OrderSide.BUY and high >= order.stop_price:
                return order.stop_price

        elif order.order_type == OrderType.OCO:
            # Check as limit for TP side
            if order.price:
                if order.side == OrderSide.SELL and high >= order.price:
                    return order.price
                elif order.side == OrderSide.BUY and low <= order.price:
                    return order.price
            # Check as stop for SL side
            if order.stop_price:
                if order.side == OrderSide.SELL and low <= order.stop_price:
                    return order.stop_price
                elif order.side == OrderSide.BUY and high >= order.stop_price:
                    return order.stop_price

        return None

    def _update_trailing_stop(self, order: Order, high: float, low: float) -> None:
        """Update trailing stop price based on new high/low."""
        if order.side == OrderSide.SELL:
            # For sell trailing stop, track new highs
            if order.order_id in self._trailing_highs:
                if high > self._trailing_highs[order.order_id]:
                    self._trailing_highs[order.order_id] = high
                    order.stop_price = high * (1 - order.trailing_delta)
        else:
            # For buy trailing stop, track new lows
            if order.order_id in self._trailing_lows:
                if low < self._trailing_lows[order.order_id]:
                    self._trailing_lows[order.order_id] = low
                    order.stop_price = low * (1 + order.trailing_delta)

    def _cancel_oco_pairs(self, filled: list[Order]) -> None:
        """Cancel OCO paired orders when one is filled."""
        oco_filled_ids = {o.order_id for o in filled if o.order_type == OrderType.OCO}
        if oco_filled_ids:
            # Simple approach: cancel all remaining OCO orders
            self.pending_orders = [
                o for o in self.pending_orders if o.order_type != OrderType.OCO
            ]

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        for i, order in enumerate(self.pending_orders):
            if order.order_id == order_id:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.pop(i)
                return True
        return False

    def cancel_all(self) -> int:
        """Cancel all pending orders."""
        count = len(self.pending_orders)
        for order in self.pending_orders:
            order.status = OrderStatus.CANCELLED
        self.pending_orders = []
        return count


# =============================================================================
# 2. RISK MANAGEMENT MODULE
# =============================================================================


@dataclass
class AntiLiquidationConfig:
    """Configuration for anti-liquidation protection."""

    # Enable auto-reduce when approaching liquidation
    enable_auto_reduce: bool = True

    # Margin ratio threshold to trigger (0.8 = 80% of maintenance margin used)
    trigger_margin_ratio: float = 0.7

    # Percentage of position to reduce
    reduce_percent: float = 0.25

    # Enable auto-add margin
    enable_add_margin: bool = False

    # Amount to add as margin (USD)
    margin_add_amount: float = 0.0


@dataclass
class BreakEvenConfig:
    """Configuration for break-even stop."""

    # Enable break-even stop
    enabled: bool = True

    # Profit threshold to activate (0.01 = 1%)
    activation_profit: float = 0.01

    # Offset from entry price (0.001 = 0.1% above/below entry)
    offset: float = 0.001

    # Only activate after N profitable bars
    min_bars_in_profit: int = 1


@dataclass
class RiskPerTradeConfig:
    """Configuration for risk-per-trade limiter."""

    # Maximum risk per trade as % of equity (0.02 = 2%)
    max_risk_percent: float = 0.02

    # Maximum position size as % of equity
    max_position_percent: float = 0.1

    # Minimum risk-reward ratio required
    min_risk_reward: float = 1.5

    # Enable Kelly criterion sizing
    use_kelly: bool = False

    # Kelly fraction (0.5 = half-Kelly)
    kelly_fraction: float = 0.5


@dataclass
class DrawdownGuardianConfig:
    """Configuration for drawdown guardian."""

    # Maximum allowed drawdown (0.1 = 10%)
    max_drawdown: float = 0.1

    # Daily loss limit (0.03 = 3%)
    daily_loss_limit: float = 0.03

    # Number of consecutive losses to pause
    max_consecutive_losses: int = 5

    # Pause duration in bars after hitting limits
    pause_bars: int = 24

    # Reduce position size after losses (0.5 = 50% reduction)
    loss_reduction_factor: float = 0.5

    # Number of losses to trigger reduction
    losses_for_reduction: int = 3


@dataclass
class RiskAction:
    """Action recommended by risk management."""

    action: str  # "allow", "reduce", "close", "pause", "add_margin"
    reason: str
    suggested_size: Optional[float] = None
    pause_until_bar: Optional[int] = None


class RiskManagement:
    """
    Advanced risk management for trading.

    Features:
    - Anti-liquidation protection
    - Break-even stop management
    - Risk-per-trade limiting
    - Drawdown guardian
    """

    def __init__(
        self,
        anti_liq_config: Optional[AntiLiquidationConfig] = None,
        break_even_config: Optional[BreakEvenConfig] = None,
        risk_per_trade_config: Optional[RiskPerTradeConfig] = None,
        drawdown_config: Optional[DrawdownGuardianConfig] = None,
    ):
        """Initialize risk management."""
        self.anti_liq = anti_liq_config or AntiLiquidationConfig()
        self.break_even = break_even_config or BreakEvenConfig()
        self.risk_per_trade = risk_per_trade_config or RiskPerTradeConfig()
        self.drawdown_guard = drawdown_config or DrawdownGuardianConfig()

        # State tracking
        self.peak_equity: float = 0.0
        self.daily_start_equity: float = 0.0
        self.consecutive_losses: int = 0
        self.total_losses_today: int = 0
        self.bars_in_profit: int = 0
        self.pause_until: int = 0
        self.current_bar: int = 0

    def check_anti_liquidation(
        self,
        margin_ratio: float,
        position_size: float,
        unrealized_pnl: float,
    ) -> RiskAction:
        """
        Check if anti-liquidation measures should be taken.

        Args:
            margin_ratio: Current margin ratio (maintenance_margin / equity)
            position_size: Current position size
            unrealized_pnl: Unrealized PnL

        Returns:
            RiskAction with recommendation
        """
        if not self.anti_liq.enable_auto_reduce:
            return RiskAction("allow", "Anti-liquidation disabled")

        if margin_ratio >= self.anti_liq.trigger_margin_ratio:
            reduce_size = position_size * self.anti_liq.reduce_percent

            if (
                self.anti_liq.enable_add_margin
                and unrealized_pnl > -self.anti_liq.margin_add_amount
            ):
                return RiskAction(
                    "add_margin",
                    f"Margin ratio {margin_ratio:.1%} - adding margin",
                    suggested_size=self.anti_liq.margin_add_amount,
                )

            return RiskAction(
                "reduce",
                f"Margin ratio {margin_ratio:.1%} exceeds {self.anti_liq.trigger_margin_ratio:.1%}",
                suggested_size=reduce_size,
            )

        return RiskAction("allow", "Margin ratio within limits")

    def check_break_even(
        self,
        entry_price: float,
        current_price: float,
        is_long: bool,
        current_stop: float,
    ) -> Optional[float]:
        """
        Check if break-even stop should be activated.

        Args:
            entry_price: Position entry price
            current_price: Current market price
            is_long: True for long position
            current_stop: Current stop-loss price

        Returns:
            New stop price if break-even should be activated, None otherwise
        """
        if not self.break_even.enabled:
            return None

        # Calculate profit percentage
        if is_long:
            profit_pct = (current_price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price

        # Check if profit threshold reached
        if profit_pct >= self.break_even.activation_profit:
            self.bars_in_profit += 1

            if self.bars_in_profit >= self.break_even.min_bars_in_profit:
                # Calculate break-even stop with offset
                if is_long:
                    be_stop = entry_price * (1 + self.break_even.offset)
                    # Only move stop up, never down
                    if be_stop > current_stop:
                        return be_stop
                else:
                    be_stop = entry_price * (1 - self.break_even.offset)
                    # Only move stop down, never up
                    if be_stop < current_stop:
                        return be_stop
        else:
            self.bars_in_profit = 0

        return None

    def calculate_position_size(
        self,
        equity: float,
        entry_price: float,
        stop_price: float,
        take_profit_price: Optional[float] = None,
        win_rate: Optional[float] = None,
    ) -> tuple[float, str]:
        """
        Calculate position size based on risk parameters.

        Args:
            equity: Current account equity
            entry_price: Planned entry price
            stop_price: Planned stop-loss price
            take_profit_price: Planned take-profit price (for R:R check)
            win_rate: Historical win rate (for Kelly)

        Returns:
            Tuple of (position_size_usd, reason)
        """
        # Calculate risk per unit
        risk_per_unit = abs(entry_price - stop_price) / entry_price

        if risk_per_unit == 0:
            return 0.0, "Invalid stop price (same as entry)"

        # Maximum risk amount
        max_risk_amount = equity * self.risk_per_trade.max_risk_percent

        # Position size from risk
        position_from_risk = max_risk_amount / risk_per_unit

        # Position size from max position limit
        position_from_limit = equity * self.risk_per_trade.max_position_percent

        # Take minimum
        position_size = min(position_from_risk, position_from_limit)

        # Check risk-reward ratio
        if take_profit_price and self.risk_per_trade.min_risk_reward > 0:
            reward = abs(take_profit_price - entry_price)
            risk = abs(entry_price - stop_price)
            rr_ratio = reward / risk if risk > 0 else 0

            if rr_ratio < self.risk_per_trade.min_risk_reward:
                return (
                    0.0,
                    f"R:R ratio {rr_ratio:.2f} below minimum {self.risk_per_trade.min_risk_reward}",
                )

        # Kelly criterion sizing
        if self.risk_per_trade.use_kelly and win_rate is not None and take_profit_price:
            reward = abs(take_profit_price - entry_price)
            risk = abs(entry_price - stop_price)
            win_loss_ratio = reward / risk if risk > 0 else 1

            # Kelly formula: f = (bp - q) / b
            # b = win/loss ratio, p = win probability, q = 1-p
            kelly_pct = (win_loss_ratio * win_rate - (1 - win_rate)) / win_loss_ratio
            kelly_pct = max(0, kelly_pct * self.risk_per_trade.kelly_fraction)

            kelly_position = equity * kelly_pct
            position_size = min(position_size, kelly_position)

        return position_size, "Position sized by risk parameters"

    def check_drawdown_guardian(
        self,
        current_equity: float,
        last_trade_pnl: Optional[float] = None,
        current_bar: int = 0,
    ) -> RiskAction:
        """
        Check if trading should be paused due to drawdown limits.

        Args:
            current_equity: Current account equity
            last_trade_pnl: PnL of last closed trade (if any)
            current_bar: Current bar number

        Returns:
            RiskAction with recommendation
        """
        self.current_bar = current_bar

        # Update peak equity
        self.peak_equity = max(self.peak_equity, current_equity)

        # Check if still in pause
        if current_bar < self.pause_until:
            return RiskAction(
                "pause",
                f"Trading paused until bar {self.pause_until}",
                pause_until_bar=self.pause_until,
            )

        # Update trade statistics
        if last_trade_pnl is not None:
            if last_trade_pnl < 0:
                self.consecutive_losses += 1
                self.total_losses_today += 1
            else:
                self.consecutive_losses = 0

        # Check consecutive losses
        if self.consecutive_losses >= self.drawdown_guard.max_consecutive_losses:
            self.pause_until = current_bar + self.drawdown_guard.pause_bars
            return RiskAction(
                "pause",
                f"Max consecutive losses ({self.consecutive_losses}) reached",
                pause_until_bar=self.pause_until,
            )

        # Check max drawdown
        if self.peak_equity > 0:
            current_dd = (self.peak_equity - current_equity) / self.peak_equity
            if current_dd >= self.drawdown_guard.max_drawdown:
                self.pause_until = current_bar + self.drawdown_guard.pause_bars
                return RiskAction(
                    "pause",
                    f"Max drawdown {current_dd:.1%} reached",
                    pause_until_bar=self.pause_until,
                )

        # Check daily loss limit
        if self.daily_start_equity > 0:
            daily_loss = (
                self.daily_start_equity - current_equity
            ) / self.daily_start_equity
            if daily_loss >= self.drawdown_guard.daily_loss_limit:
                return RiskAction(
                    "pause",
                    f"Daily loss limit {daily_loss:.1%} reached",
                )

        # Check if size should be reduced
        if self.consecutive_losses >= self.drawdown_guard.losses_for_reduction:
            return RiskAction(
                "reduce",
                f"Position reduction after {self.consecutive_losses} losses",
                suggested_size=self.drawdown_guard.loss_reduction_factor,
            )

        return RiskAction("allow", "All risk checks passed")

    def reset_daily(self, equity: float) -> None:
        """Reset daily counters (call at start of each trading day)."""
        self.daily_start_equity = equity
        self.total_losses_today = 0

    def reset_all(self, equity: float) -> None:
        """Reset all state."""
        self.peak_equity = equity
        self.daily_start_equity = equity
        self.consecutive_losses = 0
        self.total_losses_today = 0
        self.bars_in_profit = 0
        self.pause_until = 0


# =============================================================================
# 3. TRADING FILTERS MODULE
# =============================================================================


class TradingSession(Enum):
    """Trading sessions."""

    ASIA = "asia"  # 00:00-08:00 UTC
    EUROPE = "europe"  # 08:00-16:00 UTC
    US = "us"  # 16:00-24:00 UTC
    OVERLAP_EU_US = "overlap_eu_us"  # 12:00-16:00 UTC


@dataclass
class SessionFilterConfig:
    """Configuration for session-based trading filter."""

    # Sessions to allow trading
    allowed_sessions: list[TradingSession] = field(
        default_factory=lambda: [TradingSession.EUROPE, TradingSession.US]
    )

    # Custom session times (hour in UTC)
    asia_start: int = 0
    asia_end: int = 8
    europe_start: int = 8
    europe_end: int = 16
    us_start: int = 16
    us_end: int = 24

    # Block trading during specific hours
    blocked_hours: list[int] = field(default_factory=list)


@dataclass
class NewsFilterConfig:
    """Configuration for news-based trading filter."""

    # Minutes before news to stop trading
    minutes_before: int = 30

    # Minutes after news to resume trading
    minutes_after: int = 30

    # Impact levels to filter (high, medium, low)
    filter_impact: list[str] = field(default_factory=lambda: ["high"])


@dataclass
class CooldownConfig:
    """Configuration for cooldown period after trades."""

    # Enable cooldown
    enabled: bool = True

    # Cooldown after losing trade (bars)
    cooldown_after_loss: int = 3

    # Cooldown after winning trade (bars)
    cooldown_after_win: int = 1

    # Cooldown after hitting daily limit (bars)
    cooldown_after_limit: int = 24

    # Max trades per day
    max_trades_per_day: int = 10


@dataclass
class NewsEvent:
    """Represents a news event."""

    timestamp: int  # Unix timestamp in ms
    title: str
    impact: str  # "high", "medium", "low"
    currency: str  # "USD", "BTC", etc.


class TradingFilters:
    """
    Trading filters for signal validation.

    Features:
    - Session-based filtering
    - News event filtering
    - Cooldown periods
    """

    def __init__(
        self,
        session_config: Optional[SessionFilterConfig] = None,
        news_config: Optional[NewsFilterConfig] = None,
        cooldown_config: Optional[CooldownConfig] = None,
    ):
        """Initialize trading filters."""
        self.session = session_config or SessionFilterConfig()
        self.news = news_config or NewsFilterConfig()
        self.cooldown = cooldown_config or CooldownConfig()

        # State
        self.news_events: list[NewsEvent] = []
        self.last_trade_bar: int = 0
        self.last_trade_result: Optional[str] = None  # "win" or "loss"
        self.trades_today: int = 0
        self.current_day: int = 0

    def load_news_events(self, events: list[dict]) -> None:
        """Load news events."""
        self.news_events = [
            NewsEvent(
                timestamp=e["timestamp"],
                title=e.get("title", ""),
                impact=e.get("impact", "medium"),
                currency=e.get("currency", "USD"),
            )
            for e in events
        ]
        self.news_events.sort(key=lambda x: x.timestamp)

    def check_session(self, timestamp: int) -> tuple[bool, str]:
        """
        Check if current time is in allowed trading session.

        Args:
            timestamp: Unix timestamp in milliseconds

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Convert to hour (UTC)
        hour = (timestamp // 3600000) % 24

        # Check blocked hours
        if hour in self.session.blocked_hours:
            return False, f"Hour {hour} is blocked"

        # Determine current session
        current_session = None
        if self.session.asia_start <= hour < self.session.asia_end:
            current_session = TradingSession.ASIA
        elif self.session.europe_start <= hour < self.session.europe_end:
            current_session = TradingSession.EUROPE
            # Check overlap
            if hour >= 12 and hour < self.session.europe_end:
                if TradingSession.OVERLAP_EU_US in self.session.allowed_sessions:
                    return True, "EU/US overlap session"
        elif self.session.us_start <= hour < self.session.us_end:
            current_session = TradingSession.US

        if current_session in self.session.allowed_sessions:
            return True, f"{current_session.value} session"

        return False, f"Outside allowed sessions (current: {current_session})"

    def check_news(self, timestamp: int) -> tuple[bool, str]:
        """
        Check if trading is blocked due to upcoming/recent news.

        Args:
            timestamp: Unix timestamp in milliseconds

        Returns:
            Tuple of (is_allowed, reason)
        """
        before_ms = self.news.minutes_before * 60 * 1000
        after_ms = self.news.minutes_after * 60 * 1000

        for event in self.news_events:
            if event.impact not in self.news.filter_impact:
                continue

            # Check if within news window
            if event.timestamp - before_ms <= timestamp <= event.timestamp + after_ms:
                return False, f"News event: {event.title} ({event.impact})"

        return True, "No blocking news events"

    def check_cooldown(self, current_bar: int) -> tuple[bool, str]:
        """
        Check if cooldown period is active.

        Args:
            current_bar: Current bar number

        Returns:
            Tuple of (is_allowed, reason)
        """
        if not self.cooldown.enabled:
            return True, "Cooldown disabled"

        # Check max trades per day
        if self.trades_today >= self.cooldown.max_trades_per_day:
            return (
                False,
                f"Daily trade limit ({self.cooldown.max_trades_per_day}) reached",
            )

        # Check cooldown from last trade
        if self.last_trade_bar > 0:
            bars_since = current_bar - self.last_trade_bar

            if self.last_trade_result == "loss":
                if bars_since < self.cooldown.cooldown_after_loss:
                    return (
                        False,
                        f"Cooldown after loss ({bars_since}/{self.cooldown.cooldown_after_loss} bars)",
                    )
            elif self.last_trade_result == "win":
                if bars_since < self.cooldown.cooldown_after_win:
                    return (
                        False,
                        f"Cooldown after win ({bars_since}/{self.cooldown.cooldown_after_win} bars)",
                    )

        return True, "No cooldown active"

    def can_trade(self, timestamp: int, current_bar: int) -> tuple[bool, list[str]]:
        """
        Check all filters to determine if trading is allowed.

        Args:
            timestamp: Unix timestamp in milliseconds
            current_bar: Current bar number

        Returns:
            Tuple of (is_allowed, list_of_reasons)
        """
        reasons = []

        session_ok, session_reason = self.check_session(timestamp)
        if not session_ok:
            reasons.append(session_reason)

        news_ok, news_reason = self.check_news(timestamp)
        if not news_ok:
            reasons.append(news_reason)

        cooldown_ok, cooldown_reason = self.check_cooldown(current_bar)
        if not cooldown_ok:
            reasons.append(cooldown_reason)

        return len(reasons) == 0, reasons

    def record_trade(self, bar: int, pnl: float, day: int) -> None:
        """Record a completed trade."""
        self.last_trade_bar = bar
        self.last_trade_result = "win" if pnl > 0 else "loss"

        if day != self.current_day:
            self.current_day = day
            self.trades_today = 0

        self.trades_today += 1

    def reset_daily(self, day: int) -> None:
        """Reset daily counters."""
        self.current_day = day
        self.trades_today = 0


# =============================================================================
# 4. MARKET SIMULATION MODULE
# =============================================================================


@dataclass
class SpreadConfig:
    """Configuration for bid-ask spread simulation."""

    # Base spread as percentage (0.0001 = 0.01%)
    base_spread: float = 0.0001

    # Spread multiplier during high volatility
    volatility_multiplier: float = 2.0

    # Spread multiplier during low volume
    low_volume_multiplier: float = 1.5

    # Volume threshold for low volume (as ratio of average)
    low_volume_threshold: float = 0.5

    # Maximum spread cap
    max_spread: float = 0.01


class SpreadSimulator:
    """
    Simulates bid-ask spread for realistic execution.

    Features:
    - Base spread calculation
    - Volatility-adjusted spread
    - Volume-adjusted spread
    """

    def __init__(self, config: Optional[SpreadConfig] = None):
        """Initialize spread simulator."""
        self.config = config or SpreadConfig()
        self.average_volume: float = 0.0

    def set_average_volume(self, volume: float) -> None:
        """Set average volume for reference."""
        self.average_volume = volume

    def calculate_spread(
        self,
        mid_price: float,
        volatility: float = 0.0,
        current_volume: float = 0.0,
    ) -> tuple[float, float]:
        """
        Calculate bid and ask prices.

        Args:
            mid_price: Mid/last price
            volatility: Current volatility (e.g., ATR/price)
            current_volume: Current bar volume

        Returns:
            Tuple of (bid_price, ask_price)
        """
        spread = self.config.base_spread

        # Adjust for volatility
        if volatility > 0:
            spread *= 1 + volatility * self.config.volatility_multiplier

        # Adjust for low volume
        if self.average_volume > 0 and current_volume > 0:
            volume_ratio = current_volume / self.average_volume
            if volume_ratio < self.config.low_volume_threshold:
                spread *= self.config.low_volume_multiplier

        # Apply cap
        spread = min(spread, self.config.max_spread)

        half_spread = spread / 2
        bid = mid_price * (1 - half_spread)
        ask = mid_price * (1 + half_spread)

        return bid, ask

    def get_execution_price(
        self,
        mid_price: float,
        is_buy: bool,
        volatility: float = 0.0,
        current_volume: float = 0.0,
    ) -> float:
        """
        Get execution price including spread.

        Args:
            mid_price: Mid/last price
            is_buy: True for buy, False for sell
            volatility: Current volatility
            current_volume: Current bar volume

        Returns:
            Execution price
        """
        bid, ask = self.calculate_spread(mid_price, volatility, current_volume)
        return ask if is_buy else bid


@dataclass
class PositionAgeMetrics:
    """Metrics related to position age/duration."""

    # Duration in bars
    duration_bars: int = 0

    # Duration in time (milliseconds)
    duration_ms: int = 0

    # Time to max profit
    time_to_max_profit_bars: int = 0

    # Time to max drawdown
    time_to_max_drawdown_bars: int = 0

    # Average profit during holding
    average_unrealized_pnl: float = 0.0

    # Max unrealized profit
    max_unrealized_profit: float = 0.0

    # Max unrealized loss
    max_unrealized_loss: float = 0.0

    # Bars in profit
    bars_in_profit: int = 0

    # Bars in loss
    bars_in_loss: int = 0


class PositionTracker:
    """
    Tracks position metrics over time.

    Features:
    - Duration tracking
    - Unrealized PnL history
    - Time-based analysis
    """

    def __init__(self):
        """Initialize position tracker."""
        self.entry_bar: int = 0
        self.entry_timestamp: int = 0
        self.entry_price: float = 0.0
        self.is_long: bool = True
        self.size: float = 0.0

        self._pnl_history: list[float] = []
        self._max_profit_bar: int = 0
        self._max_drawdown_bar: int = 0
        self._bars_in_profit: int = 0
        self._bars_in_loss: int = 0

    def open_position(
        self,
        entry_bar: int,
        entry_timestamp: int,
        entry_price: float,
        is_long: bool,
        size: float,
    ) -> None:
        """Record position opening."""
        self.entry_bar = entry_bar
        self.entry_timestamp = entry_timestamp
        self.entry_price = entry_price
        self.is_long = is_long
        self.size = size
        self._pnl_history = []
        self._max_profit_bar = 0
        self._max_drawdown_bar = 0
        self._bars_in_profit = 0
        self._bars_in_loss = 0

    def update(self, current_bar: int, current_price: float) -> float:
        """
        Update position with current price.

        Args:
            current_bar: Current bar number
            current_price: Current market price

        Returns:
            Current unrealized PnL
        """
        if self.is_long:
            pnl = (current_price - self.entry_price) * self.size
        else:
            pnl = (self.entry_price - current_price) * self.size

        self._pnl_history.append(pnl)

        # Track max profit/loss timing
        if len(self._pnl_history) > 1:
            if pnl >= max(self._pnl_history[:-1]):
                self._max_profit_bar = current_bar - self.entry_bar
            if pnl <= min(self._pnl_history[:-1]):
                self._max_drawdown_bar = current_bar - self.entry_bar

        # Track bars in profit/loss
        if pnl > 0:
            self._bars_in_profit += 1
        elif pnl < 0:
            self._bars_in_loss += 1

        return pnl

    def close_position(self, exit_bar: int, exit_timestamp: int) -> PositionAgeMetrics:
        """
        Close position and return metrics.

        Args:
            exit_bar: Exit bar number
            exit_timestamp: Exit timestamp

        Returns:
            PositionAgeMetrics with duration and PnL analysis
        """
        if not self._pnl_history:
            return PositionAgeMetrics()

        pnl_array = np.array(self._pnl_history)

        return PositionAgeMetrics(
            duration_bars=exit_bar - self.entry_bar,
            duration_ms=exit_timestamp - self.entry_timestamp,
            time_to_max_profit_bars=self._max_profit_bar,
            time_to_max_drawdown_bars=self._max_drawdown_bar,
            average_unrealized_pnl=float(np.mean(pnl_array)),
            max_unrealized_profit=float(np.max(pnl_array)),
            max_unrealized_loss=float(np.min(pnl_array)),
            bars_in_profit=self._bars_in_profit,
            bars_in_loss=self._bars_in_loss,
        )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Order Types
    "OrderType",
    "OrderSide",
    "OrderStatus",
    "Order",
    "TrailingStopConfig",
    "OCOConfig",
    "OrderManager",
    # Risk Management
    "AntiLiquidationConfig",
    "BreakEvenConfig",
    "RiskPerTradeConfig",
    "DrawdownGuardianConfig",
    "RiskAction",
    "RiskManagement",
    # Trading Filters
    "TradingSession",
    "SessionFilterConfig",
    "NewsFilterConfig",
    "CooldownConfig",
    "NewsEvent",
    "TradingFilters",
    # Market Simulation
    "SpreadConfig",
    "SpreadSimulator",
    "PositionAgeMetrics",
    "PositionTracker",
]
