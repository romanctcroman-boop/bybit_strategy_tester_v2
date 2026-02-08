"""
Advanced Backtest Engine

Provides enhanced backtesting with:
- Realistic execution simulation
- Multiple fill models (market, limit, stop)
- Commission and fee handling
- Position and margin management
- Event-driven architecture

Usage:
    from backend.services.advanced_backtesting.engine import (
        AdvancedBacktestEngine,
        BacktestConfig,
    )

    engine = AdvancedBacktestEngine(config)
    results = engine.run(data, strategy)
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np

from .slippage import CompositeSlippage, SlippageModel, SlippageResult

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    """Order sides."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order statuses."""

    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(Enum):
    """Position sides."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class BacktestConfig:
    """Configuration for backtest engine."""

    # Capital & Leverage
    initial_capital: float = 10000.0
    leverage: float = 1.0
    max_position_size: float = 1.0  # As fraction of capital

    # Fees
    maker_fee: float = 0.0002  # 0.02%
    taker_fee: float = 0.0006  # 0.06%
    funding_rate: float = 0.0001  # Per 8 hours
    apply_funding: bool = True
    funding_interval_minutes: int | None = 480  # default 8h
    funding_interval_candles: int | None = None  # override minutes when provided
    funding_rate_by_symbol: dict[str, float] | None = None
    funding_rate_field: str = "funding_rate"

    # Execution
    slippage_model: SlippageModel | None = None
    fill_model: str = "realistic"  # 'instant', 'realistic', 'pessimistic'
    partial_fills: bool = True
    order_latency_ms: int = 50  # Simulated latency

    # Risk Management
    max_drawdown_limit: float = 0.25  # Stop trading at 25% DD
    daily_loss_limit: float = 0.05  # 5% daily loss limit
    position_limit: int = 5  # Max concurrent positions

    # Margin
    margin_type: str = "cross"  # 'cross' or 'isolated'
    maintenance_margin: float = 0.005  # 0.5%
    liquidation_penalty_pct: float = 0.002  # 0.2% notional penalty when liquidated
    maintenance_margin_by_symbol: dict[str, float] | None = None
    maintenance_vol_multiplier: float = 0.0  # adds vol * multiplier to base margin

    # Time
    start_date: datetime | None = None
    end_date: datetime | None = None
    trading_hours: tuple[int, int] | None = None  # (start_hour, end_hour) UTC

    def __post_init__(self):
        if self.slippage_model is None:
            self.slippage_model = CompositeSlippage()


@dataclass
class Order:
    """Represents a trading order."""

    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None  # For limit orders
    stop_price: float | None = None  # For stop orders

    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    filled_at: datetime | None = None

    # Execution details
    commission: float = 0.0
    slippage: float = 0.0

    # Risk management
    take_profit: float | None = None
    stop_loss: float | None = None
    trailing_stop_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": round(self.average_fill_price, 8),
            "commission": round(self.commission, 8),
            "slippage": round(self.slippage, 8),
            "created_at": self.created_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
        }


@dataclass
class Position:
    """Represents an open position."""

    symbol: str
    side: PositionSide
    entry_price: float
    quantity: float

    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    entry_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_update: datetime | None = None

    # Risk
    liquidation_price: float | None = None
    margin_used: float = 0.0
    leverage: float = 1.0

    entry_commission_total: float = 0.0
    funding_paid: float = 0.0

    # Orders
    take_profit_price: float | None = None
    stop_loss_price: float | None = None
    trailing_stop_pct: float | None = None  # e.g. 0.01 = 1%
    trail_anchor: float | None = None  # highest (long) / lowest (short) price seen

    # MAE/MFE tracking (TradingView compatible)
    peak_price: float | None = None  # highest price seen (for MFE long / MAE short)
    trough_price: float | None = None  # lowest price seen (for MAE long / MFE short)

    def update_pnl(self, current_price: float):
        """Update unrealized PnL."""
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        elif self.side == PositionSide.SHORT:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity

    def update_excursions(self, high: float, low: float):
        """Update MAE/MFE tracking with current candle high/low.

        For LONG positions:
          - MFE = highest price seen (peak_price)
          - MAE = lowest price seen (trough_price)
        For SHORT positions:
          - MFE = lowest price seen (trough_price)
          - MAE = highest price seen (peak_price)
        """
        # Initialize on first call
        if self.peak_price is None:
            self.peak_price = high
        if self.trough_price is None:
            self.trough_price = low

        # Update extremes
        self.peak_price = max(self.peak_price, high)
        self.trough_price = min(self.trough_price, low)

    def calculate_mfe(self) -> float:
        """Calculate Maximum Favorable Excursion as percentage.

        MFE = best unrealized profit during the trade.
        """
        if self.side == PositionSide.LONG:
            # For long: MFE when price goes up (peak)
            if self.peak_price:
                return (self.peak_price - self.entry_price) / self.entry_price * 100
        else:
            # For short: MFE when price goes down (trough)
            if self.trough_price:
                return (self.entry_price - self.trough_price) / self.entry_price * 100
        return 0.0

    def calculate_mae(self) -> float:
        """Calculate Maximum Adverse Excursion as percentage.

        MAE = worst unrealized loss during the trade.
        """
        if self.side == PositionSide.LONG:
            # For long: MAE when price goes down (trough)
            if self.trough_price:
                return (self.entry_price - self.trough_price) / self.entry_price * 100
        else:
            # For short: MAE when price goes up (peak)
            if self.peak_price:
                return (self.peak_price - self.entry_price) / self.entry_price * 100
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": round(self.entry_price, 8),
            "quantity": self.quantity,
            "unrealized_pnl": round(self.unrealized_pnl, 4),
            "realized_pnl": round(self.realized_pnl, 4),
            "entry_time": self.entry_time.isoformat(),
            "leverage": self.leverage,
            "margin_used": round(self.margin_used, 4),
        }


@dataclass
class Trade:
    """Represents a completed trade."""

    id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float

    pnl: float = 0.0
    pnl_pct: float = 0.0

    entry_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    exit_time: datetime | None = None
    duration_seconds: int = 0

    # Costs
    commission: float = 0.0
    slippage: float = 0.0
    funding_fees: float = 0.0
    liquidation_penalty: float = 0.0
    reason: str = "regular"

    # Analytics
    max_favorable_excursion: float = 0.0  # MFE
    max_adverse_excursion: float = 0.0  # MAE
    r_multiple: float | None = None  # Risk multiple

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": round(self.entry_price, 8),
            "exit_price": round(self.exit_price, 8),
            "quantity": self.quantity,
            "pnl": round(self.pnl, 4),
            "pnl_pct": round(self.pnl_pct * 100, 2),
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "duration_seconds": self.duration_seconds,
            "commission": round(self.commission, 4),
            "slippage": round(self.slippage, 4),
            "funding_fees": round(self.funding_fees, 4),
            "liquidation_penalty": round(self.liquidation_penalty, 4),
            "reason": self.reason,
            "mfe": round(self.max_favorable_excursion * 100, 2),
            "mae": round(self.max_adverse_excursion * 100, 2),
            "r_multiple": round(self.r_multiple, 2) if self.r_multiple else None,
        }


@dataclass
class ExecutionSimulator:
    """Simulates realistic order execution."""

    config: BacktestConfig

    def simulate_fill(
        self,
        order: Order,
        candle: dict[str, Any],
        slippage_result: SlippageResult,
    ) -> tuple[bool, float, float]:
        """
        Simulate order fill.

        Args:
            order: Order to fill
            candle: Current candle data
            slippage_result: Calculated slippage

        Returns:
            Tuple of (filled, fill_price, fill_quantity)
        """
        if order.order_type == OrderType.MARKET:
            return self._fill_market_order(order, candle, slippage_result)
        elif order.order_type == OrderType.LIMIT:
            return self._fill_limit_order(order, candle, slippage_result)
        elif order.order_type == OrderType.STOP:
            return self._fill_stop_order(order, candle, slippage_result)
        else:
            return False, 0.0, 0.0

    def _fill_market_order(
        self,
        order: Order,
        candle: dict,
        slippage: SlippageResult,
    ) -> tuple[bool, float, float]:
        """Fill market order at slippage-adjusted price."""
        fill_price = slippage.execution_price
        fill_quantity = order.quantity

        # Apply partial fill based on model
        if self.config.partial_fills and self.config.fill_model == "realistic":
            # Simulate partial fills for large orders
            volume = candle.get("volume", 1_000_000)
            order_value = order.quantity * fill_price
            if order_value > volume * 0.1:  # > 10% of volume
                fill_ratio = 0.1 * volume / order_value
                fill_quantity = order.quantity * min(fill_ratio, 1.0)

        return True, fill_price, fill_quantity

    def _fill_limit_order(
        self,
        order: Order,
        candle: dict,
        slippage: SlippageResult,
    ) -> tuple[bool, float, float]:
        """Fill limit order if price touched."""
        if order.price is None:
            return False, 0.0, 0.0

        high = candle.get("high", 0)
        low = candle.get("low", 0)

        # Check if limit price was reached
        if order.side == OrderSide.BUY:
            if low <= order.price:
                fill_price = order.price  # Limit orders fill at limit price
                return True, fill_price, order.quantity
        else:  # SELL
            if high >= order.price:
                fill_price = order.price
                return True, fill_price, order.quantity

        return False, 0.0, 0.0

    def _fill_stop_order(
        self,
        order: Order,
        candle: dict,
        slippage: SlippageResult,
    ) -> tuple[bool, float, float]:
        """Fill stop order if stop price triggered."""
        if order.stop_price is None:
            return False, 0.0, 0.0

        high = candle.get("high", 0)
        low = candle.get("low", 0)

        # Check if stop was triggered
        if order.side == OrderSide.BUY:  # Buy stop (above current price)
            if high >= order.stop_price:
                # Fill at stop price + slippage
                fill_price = order.stop_price + slippage.slippage_amount
                return True, fill_price, order.quantity
        else:  # Sell stop (below current price)
            if low <= order.stop_price:
                fill_price = order.stop_price + slippage.slippage_amount
                return True, fill_price, order.quantity

        return False, 0.0, 0.0


@dataclass
class RealisticFillModel:
    """Realistic fill model with market microstructure."""

    config: BacktestConfig

    def estimate_fill_probability(
        self,
        order: Order,
        candle: dict,
        market_state: dict,
    ) -> float:
        """
        Estimate probability of fill.

        Considers:
        - Order size relative to volume
        - Price distance from current
        - Market volatility
        - Time remaining in candle
        """
        if order.order_type == OrderType.MARKET:
            return 1.0  # Market orders always fill

        volume = candle.get("volume", 1_000_000)
        order_value = order.quantity * (order.price or candle["close"])

        # Base probability
        prob = 0.8

        # Adjust for size (large orders less likely to fill completely)
        size_ratio = order_value / (volume * candle["close"])
        if size_ratio > 0.05:  # > 5% of volume
            prob *= 1 - size_ratio * 2

        # Adjust for price distance (limit orders)
        if order.price:
            current = candle["close"]
            distance = abs(order.price - current) / current
            if (order.side == OrderSide.BUY and order.price < current) or (order.side == OrderSide.SELL and order.price > current):
                prob *= max(0.1, 1 - distance * 10)

        return max(0.0, min(1.0, prob))


class AdvancedBacktestEngine:
    """
    Advanced Backtesting Engine.

    Features:
    - Realistic execution simulation
    - Multiple order types
    - Position management
    - Risk controls
    - Detailed analytics
    """

    def __init__(self, config: BacktestConfig | None = None):
        """
        Initialize backtest engine.

        Args:
            config: Backtest configuration
        """
        self.config = config or BacktestConfig()
        self.execution_sim = ExecutionSimulator(self.config)
        self.fill_model = RealisticFillModel(self.config)

        # State
        self.capital = self.config.initial_capital
        self.equity = self.config.initial_capital
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self.trades: list[Trade] = []

        # Tracking
        self.equity_curve: list[float] = []
        self.drawdown_curve: list[float] = []
        self.peak_equity = self.config.initial_capital
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0

        # Counters
        self._order_counter = 0
        self._trade_counter = 0
        self._funding_candle_counter = 0
        self._funding_minutes_accum = 0.0
        self._prev_candle_time: datetime | None = None
        self.total_funding_fees = 0.0
        self.liquidations = 0
        self.bars_in_market = 0
        self.events_log: list[dict[str, Any]] = []
        self.current_dd_duration = 0
        self.max_dd_duration = 0

        logger.info(
            f"AdvancedBacktestEngine initialized with capital=${self.config.initial_capital}"
        )

    def reset(self):
        """Reset engine state."""
        self.capital = self.config.initial_capital
        self.equity = self.config.initial_capital
        self.positions.clear()
        self.orders.clear()
        self.trades.clear()
        self.equity_curve.clear()
        self.drawdown_curve.clear()
        self.peak_equity = self.config.initial_capital
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0
        self._order_counter = 0
        self._trade_counter = 0
        self._funding_candle_counter = 0
        self._funding_minutes_accum = 0.0
        self._prev_candle_time = None
        self.total_funding_fees = 0.0
        self.liquidations = 0
        self.bars_in_market = 0
        self.events_log = []
        self.current_dd_duration = 0
        self.max_dd_duration = 0

    def run(
        self,
        data: list[dict],
        strategy_func: Callable[[dict, dict], dict | None],
        strategy_params: dict | None = None,
    ) -> dict[str, Any]:
        """
        Run backtest.

        Args:
            data: List of candle dictionaries
            strategy_func: Strategy function that returns signals
            strategy_params: Strategy parameters

        Returns:
            Backtest results dictionary
        """
        self.reset()
        strategy_params = strategy_params or {}

        start_time = datetime.now()
        logger.info(f"Starting backtest with {len(data)} candles")

        # Build market state
        market_state = {
            "position": None,
            "capital": self.capital,
            "equity": self.equity,
        }

        for i, candle in enumerate(data):
            # timestamp available in candle for debugging if needed
            open_time = candle.get("open_time")
            interval_minutes = self._infer_interval_minutes(candle, open_time)
            if open_time:
                self._prev_candle_time = open_time

            # Update positions PnL
            self._update_positions(candle)

            # Apply TP/SL/Trailing protections
            self._apply_position_protections(candle)

            # Apply funding when due
            self._maybe_apply_funding(candle, interval_minutes)

            # Liquidation check after funding impact
            self._check_liquidation(candle)

            # Process pending orders
            self._process_orders(candle)

            # Check risk limits
            if not self._check_risk_limits():
                logger.warning("Risk limit reached, stopping backtest")
                break

            # Get strategy signal
            market_state.update(
                {
                    "position": self._get_current_position(
                        candle.get("symbol", "UNKNOWN")
                    ),
                    "capital": self.capital,
                    "equity": self.equity,
                    "drawdown": self.current_drawdown,
                }
            )

            signal = strategy_func(candle, {**strategy_params, **market_state})

            # Process signal
            if signal:
                self._process_signal(signal, candle)

            # Time-in-market tracking
            if self.positions:
                self.bars_in_market += 1

            # Track equity
            self._update_equity_tracking()

        # Close any remaining positions
        if data:
            self._close_all_positions(data[-1])

        # Calculate results
        duration = (datetime.now() - start_time).total_seconds()
        results = self._calculate_results(data, duration)

        logger.info(f"Backtest completed in {duration:.2f}s")
        return results

    def _update_positions(self, candle: dict):
        """Update unrealized PnL and MAE/MFE for all positions."""
        current_price = candle.get("close", 0)
        high = candle.get("high", current_price)
        low = candle.get("low", current_price)
        symbol = candle.get("symbol", "UNKNOWN")

        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.update_pnl(current_price)
            pos.update_excursions(high, low)  # Track MAE/MFE

    def _apply_position_protections(self, candle: dict):
        """Apply SL/TP/Trailing to open positions using current candle high/low."""
        high = candle.get("high", candle.get("close", 0))
        low = candle.get("low", candle.get("close", 0))
        symbol = candle.get("symbol", "UNKNOWN")

        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        qty = pos.quantity
        if qty <= 0:
            return

        trigger_price = None
        trigger_reason = None

        # Update trailing anchor
        if pos.trailing_stop_pct:
            if pos.side == PositionSide.LONG:
                pos.trail_anchor = max(pos.trail_anchor or low, high)
            else:
                pos.trail_anchor = min(pos.trail_anchor or high, low)

        # Determine trailing stop price
        trailing_stop_price = None
        if pos.trailing_stop_pct and pos.trail_anchor:
            if pos.side == PositionSide.LONG:
                trailing_stop_price = pos.trail_anchor * (1 - pos.trailing_stop_pct)
            else:
                trailing_stop_price = pos.trail_anchor * (1 + pos.trailing_stop_pct)

        if pos.side == PositionSide.LONG:
            # SL first, then TP, then trailing
            if pos.stop_loss_price and low <= pos.stop_loss_price:
                trigger_price = pos.stop_loss_price
                trigger_reason = "stop_loss"
            elif pos.take_profit_price and high >= pos.take_profit_price:
                trigger_price = pos.take_profit_price
                trigger_reason = "take_profit"
            elif trailing_stop_price and low <= trailing_stop_price:
                trigger_price = trailing_stop_price
                trigger_reason = "trailing_stop"
        else:  # SHORT
            if pos.stop_loss_price and high >= pos.stop_loss_price:
                trigger_price = pos.stop_loss_price
                trigger_reason = "stop_loss"
            elif pos.take_profit_price and low <= pos.take_profit_price:
                trigger_price = pos.take_profit_price
                trigger_reason = "take_profit"
            elif trailing_stop_price and high >= trailing_stop_price:
                trigger_price = trailing_stop_price
                trigger_reason = "trailing_stop"

        if trigger_price is None:
            return

        # Build synthetic order to exit
        exit_side = OrderSide.SELL if pos.side == PositionSide.LONG else OrderSide.BUY
        order = Order(
            id=f"AUTO_EXIT_{symbol}_{trigger_reason}",
            symbol=symbol,
            side=exit_side,
            order_type=OrderType.MARKET,
            quantity=qty,
        )

        slippage = self.config.slippage_model.calculate(
            price=trigger_price,
            order_size=qty,
            side=exit_side.value,
            volume=candle.get("volume", 1_000_000),
            volatility=self._calculate_volatility(candle),
        )

        self._fill_order(order, slippage.execution_price, qty, candle, slippage)

        logger.info(
            f"Auto-exit {symbol} via {trigger_reason} at {trigger_price:.4f}, pos_side={pos.side.value}"
        )

    def _process_orders(self, candle: dict):
        """Process pending orders."""
        pending_orders = [o for o in self.orders if o.status == OrderStatus.OPEN]

        for order in pending_orders:
            # Calculate slippage
            slippage_result = self.config.slippage_model.calculate(
                price=candle.get("close", 0),
                order_size=order.quantity,
                side=order.side.value,
                volume=candle.get("volume", 1_000_000),
                volatility=self._calculate_volatility(candle),
            )

            # Try to fill
            filled, fill_price, fill_qty = self.execution_sim.simulate_fill(
                order, candle, slippage_result
            )

            if filled:
                self._fill_order(order, fill_price, fill_qty, candle, slippage_result)

    def _fill_order(
        self,
        order: Order,
        fill_price: float,
        fill_qty: float,
        candle: dict,
        slippage: SlippageResult,
        reason: str = "regular",
        extra_cost: float = 0.0,
    ):
        """Execute order fill."""
        # Calculate commission
        fill_value = fill_price * fill_qty
        fee_rate = (
            self.config.taker_fee
            if order.order_type == OrderType.MARKET
            else self.config.maker_fee
        )
        commission = fill_value * fee_rate

        # Update order
        order.filled_quantity = fill_qty
        order.average_fill_price = fill_price
        order.commission = commission
        order.slippage = slippage.slippage_amount * fill_qty
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now(UTC)

        # Update positions
        symbol = order.symbol
        existing = self.positions.get(symbol)

        if order.side == OrderSide.BUY:
            if existing and existing.side == PositionSide.SHORT:
                self._close_or_reduce_position(
                    symbol, fill_price, fill_qty, candle, order, reason, extra_cost
                )
            else:
                self._open_or_add_position(
                    symbol, PositionSide.LONG, fill_price, fill_qty, order
                )
        else:  # SELL
            if existing and existing.side == PositionSide.LONG:
                self._close_or_reduce_position(
                    symbol, fill_price, fill_qty, candle, order, reason, extra_cost
                )
            else:
                self._open_or_add_position(
                    symbol, PositionSide.SHORT, fill_price, fill_qty, order
                )

    def _open_or_add_position(
        self,
        symbol: str,
        side: PositionSide,
        price: float,
        quantity: float,
        order: Order,
    ):
        """Open new position or add to existing."""
        # Margin required for this fill
        required_margin = (price * quantity) / self.config.leverage

        # Deduct commission + margin from capital for entry
        self.capital -= required_margin + order.commission

        if symbol in self.positions:
            pos = self.positions[symbol]
            # Average into position
            total_qty = pos.quantity + quantity
            pos.entry_price = (
                pos.entry_price * pos.quantity + price * quantity
            ) / total_qty
            pos.quantity = total_qty
            pos.margin_used += required_margin
            pos.entry_commission_total += order.commission
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                side=side,
                entry_price=price,
                quantity=quantity,
                leverage=self.config.leverage,
                margin_used=(price * quantity) / self.config.leverage,
                entry_commission_total=order.commission,
                take_profit_price=order.take_profit,
                stop_loss_price=order.stop_loss,
                trailing_stop_pct=order.trailing_stop_pct,
                trail_anchor=price,
            )

    def _close_or_reduce_position(
        self,
        symbol: str,
        price: float,
        quantity: float,
        candle: dict,
        order: Order,
        reason: str = "regular",
        extra_cost: float = 0.0,
    ):
        """Close or reduce position."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        close_qty = min(quantity, pos.quantity)

        # Calculate PnL
        if pos.side == PositionSide.LONG:
            pnl = (price - pos.entry_price) * close_qty
        else:
            pnl = (pos.entry_price - price) * close_qty

        # Release proportional margin and entry commissions
        qty_ratio = close_qty / pos.quantity if pos.quantity else 0
        released_margin = pos.margin_used * qty_ratio
        released_entry_commission = pos.entry_commission_total * qty_ratio
        allocated_funding = pos.funding_paid * qty_ratio

        # Record trade
        self._trade_counter += 1
        trade = Trade(
            id=f"T{self._trade_counter:06d}",
            symbol=symbol,
            side=pos.side.value,
            entry_price=pos.entry_price,
            exit_price=price,
            quantity=close_qty,
            pnl=pnl
            - order.commission
            - released_entry_commission
            - allocated_funding
            - extra_cost,
            pnl_pct=(price / pos.entry_price - 1)
            if pos.side == PositionSide.LONG
            else (1 - price / pos.entry_price),
            entry_time=pos.entry_time,
            exit_time=datetime.now(UTC),
            commission=order.commission + released_entry_commission,
            slippage=order.slippage,
            funding_fees=allocated_funding,
            liquidation_penalty=extra_cost,
            reason=reason,
            # MAE/MFE from position tracking (TradingView compatible)
            max_favorable_excursion=pos.calculate_mfe(),
            max_adverse_excursion=pos.calculate_mae(),
        )
        trade.duration_seconds = int(
            (trade.exit_time - trade.entry_time).total_seconds()
        )
        self.trades.append(trade)

        # Capital update on exit: return margin + realized PnL - exit commission
        self.capital += released_margin + pnl - order.commission - extra_cost

        # Update or remove position
        pos.quantity -= close_qty
        pos.realized_pnl += (
            pnl - released_entry_commission - order.commission - extra_cost
        )
        pos.margin_used -= released_margin
        pos.entry_commission_total -= released_entry_commission
        pos.funding_paid -= allocated_funding

        if pos.quantity <= 0:
            del self.positions[symbol]

    def _close_all_positions(self, last_candle: dict):
        """Close all remaining positions at end of backtest."""
        close_price = last_candle.get("close", 0)
        symbols = list(self.positions.keys())

        for symbol in symbols:
            pos = self.positions[symbol]
            order = Order(
                id=f"CLOSE_{symbol}",
                symbol=symbol,
                side=OrderSide.SELL if pos.side == PositionSide.LONG else OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=pos.quantity,
            )

            slippage = self.config.slippage_model.calculate(
                price=close_price,
                order_size=pos.quantity,
                side=order.side.value,
            )

            self._fill_order(
                order, slippage.execution_price, pos.quantity, last_candle, slippage
            )

    def _process_signal(self, signal: dict, candle: dict):
        """Process strategy signal."""
        action = signal.get("action")
        symbol = signal.get("symbol", candle.get("symbol", "UNKNOWN"))
        price_for_margin = signal.get("price", candle.get("close", 0)) or candle.get(
            "close", 0
        )

        if action in ["buy", "long"]:
            if self._can_open_new_position():
                # Margin check
                proposed_qty = signal.get(
                    "quantity", self._calculate_position_size(candle)
                )
                required_margin = (
                    price_for_margin * proposed_qty
                ) / self.config.leverage
                if (
                    self.capital < required_margin + price_for_margin * 0 + 0
                ):  # commission handled later
                    logger.warning("Open blocked: insufficient margin (long)")
                    return
                self._create_order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType(signal.get("order_type", "market")),
                    quantity=signal.get(
                        "quantity", self._calculate_position_size(candle)
                    ),
                    price=signal.get("price"),
                    stop_price=signal.get("stop_price"),
                    take_profit=signal.get("take_profit"),
                    stop_loss=signal.get("stop_loss"),
                    trailing_stop_pct=signal.get("trailing_stop_pct"),
                )
            else:
                logger.warning("Open blocked by risk limits (long)")
        elif action in ["sell", "short"]:
            default_qty = self._calculate_position_size(candle)
            # If closing existing position and quantity not provided, use full position size
            existing_qty = self._get_position_size(symbol)
            inferred_qty = signal.get("quantity", existing_qty or default_qty)
            # Allow closing even if risk limit hit; opening new shorts blocked
            is_opening_short = existing_qty == 0 or (
                symbol in self.positions
                and self.positions[symbol].side == PositionSide.SHORT
                and inferred_qty > existing_qty
            )
            if is_opening_short and not self._can_open_new_position():
                logger.warning("Open blocked by risk limits (short)")
                return

            if is_opening_short:
                required_margin = (
                    price_for_margin * inferred_qty
                ) / self.config.leverage
                if self.capital < required_margin:
                    logger.warning("Open blocked: insufficient margin (short)")
                    return

            self._create_order(
                symbol=symbol,
                side=OrderSide.SELL,
                order_type=OrderType(signal.get("order_type", "market")),
                quantity=inferred_qty,
                price=signal.get("price"),
                stop_price=signal.get("stop_price"),
                take_profit=signal.get("take_profit"),
                stop_loss=signal.get("stop_loss"),
                trailing_stop_pct=signal.get("trailing_stop_pct"),
            )
        elif action == "close":
            pos = self._get_position(symbol)
            if not pos:
                return
            exit_side = (
                OrderSide.SELL if pos.side == PositionSide.LONG else OrderSide.BUY
            )
            qty = signal.get("quantity", pos.quantity)
            self._create_order(
                symbol=symbol,
                side=exit_side,
                order_type=OrderType(signal.get("order_type", "market")),
                quantity=qty,
                price=signal.get("price"),
                stop_price=signal.get("stop_price"),
                take_profit=signal.get("take_profit"),
                stop_loss=signal.get("stop_loss"),
                trailing_stop_pct=signal.get("trailing_stop_pct"),
            )

    def _create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
        take_profit: float | None = None,
        stop_loss: float | None = None,
        trailing_stop_pct: float | None = None,
    ):
        """Create and queue order."""
        self._order_counter += 1
        order = Order(
            id=f"O{self._order_counter:06d}",
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            trailing_stop_pct=trailing_stop_pct,
            status=OrderStatus.OPEN,
        )
        self.orders.append(order)

    def _check_risk_limits(self) -> bool:
        """Check if risk limits are breached."""
        # Max drawdown check
        if self.current_drawdown >= self.config.max_drawdown_limit:
            return False

        # Position limit check
        if len(self.positions) >= self.config.position_limit:
            return True  # Don't stop, just don't open new

        return True

    def _can_open_new_position(self) -> bool:
        """Gate for opening new positions (risk limits & position cap)."""
        if self.current_drawdown >= self.config.max_drawdown_limit:
            return False

        # Daily loss limit approximation: use equity vs initial
        if self.config.daily_loss_limit > 0:
            loss_frac = (
                max(0.0, (self.config.initial_capital - self.equity))
                / self.config.initial_capital
            )
            if loss_frac >= self.config.daily_loss_limit:
                return False

        if len(self.positions) >= self.config.position_limit:
            return False

        return True

    def _update_equity_tracking(self):
        """Update equity curve and drawdown."""
        # Calculate total equity
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        self.equity = self.capital + total_unrealized

        self.equity_curve.append(self.equity)

        # Update drawdown
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
            self.current_dd_duration = 0

        self.current_drawdown = (self.peak_equity - self.equity) / self.peak_equity
        self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
        self.drawdown_curve.append(self.current_drawdown)

        if self.equity < self.peak_equity:
            self.current_dd_duration += 1
            self.max_dd_duration = max(self.max_dd_duration, self.current_dd_duration)

    def _calculate_position_size(self, candle: dict) -> float:
        """Calculate position size based on config and leverage."""
        price = candle.get("close", 1)
        if price <= 0:
            return 0.0
        # Use a fraction of capital as margin, apply leverage to get notional
        available_margin = self.capital * self.config.max_position_size
        notional = available_margin * self.config.leverage
        return notional / price

    def _get_position_size(self, symbol: str) -> float:
        """Get current position size."""
        if symbol in self.positions:
            return self.positions[symbol].quantity
        return 0.0

    def _get_position(self, symbol: str) -> Position | None:
        return self.positions.get(symbol)

    def _get_current_position(self, symbol: str) -> dict | None:
        """Get current position as dict."""
        if symbol in self.positions:
            return self.positions[symbol].to_dict()
        return None

    def _get_maintenance_margin_rate(self, symbol: str, candle: dict) -> float:
        """Resolve maintenance margin rate with overrides and vol adjustment."""

        # Symbol-specific override
        if (
            self.config.maintenance_margin_by_symbol
            and symbol in self.config.maintenance_margin_by_symbol
        ):
            base = self.config.maintenance_margin_by_symbol[symbol]
        else:
            base = candle.get("maintenance_margin", self.config.maintenance_margin)

        vol = self._calculate_volatility(candle)
        adjusted = base + vol * self.config.maintenance_vol_multiplier
        return max(0.0, adjusted)

    def _get_funding_rate(self, candle: dict, symbol: str) -> float:
        """Resolve funding rate: candle field > symbol override > default."""

        if self.config.funding_rate_field and self.config.funding_rate_field in candle:
            return float(candle[self.config.funding_rate_field])

        if (
            self.config.funding_rate_by_symbol
            and symbol in self.config.funding_rate_by_symbol
        ):
            return self.config.funding_rate_by_symbol[symbol]

        return self.config.funding_rate

    def _infer_interval_minutes(
        self, candle: dict, open_time: datetime | None
    ) -> float | None:
        """Infer candle interval in minutes using provided metadata."""

        if candle.get("interval_minutes"):
            return float(candle.get("interval_minutes"))

        if open_time and self._prev_candle_time:
            delta = (open_time - self._prev_candle_time).total_seconds() / 60
            return max(delta, 0.0)

        close_time = candle.get("close_time")
        if open_time and close_time:
            delta = (close_time - open_time).total_seconds() / 60
            return max(delta, 0.0)

        return None

    def _maybe_apply_funding(
        self, candle: dict, interval_minutes: float | None
    ) -> None:
        """Apply funding payments/credits when due."""

        if not self.config.apply_funding or not self.positions:
            return

        # Candle-based scheduling (explicit override)
        if self.config.funding_interval_candles:
            self._funding_candle_counter += 1
            if self._funding_candle_counter >= self.config.funding_interval_candles:
                self._apply_funding(candle, 1.0)
                self._funding_candle_counter = 0
            return

        # Time-based scheduling (minutes)
        if interval_minutes is None or not self.config.funding_interval_minutes:
            return

        self._funding_minutes_accum += interval_minutes
        if self._funding_minutes_accum >= self.config.funding_interval_minutes:
            periods = self._funding_minutes_accum / self.config.funding_interval_minutes
            self._apply_funding(candle, periods)
            self._funding_minutes_accum = 0.0

    def _apply_funding(self, candle: dict, periods: float) -> None:
        """Apply funding based on open positions."""

        if periods <= 0:
            return

        price = candle.get("close", 0)
        for pos in list(self.positions.values()):
            notional = price * pos.quantity
            rate = self._get_funding_rate(candle, pos.symbol)
            effective_rate = rate * periods
            funding_fee = notional * effective_rate
            # Longs pay when rate positive; shorts receive. Reverse when rate negative.
            if pos.side == PositionSide.SHORT:
                funding_fee *= -1

            pos.funding_paid += funding_fee
            self.total_funding_fees += funding_fee
            self.capital -= funding_fee

            self.events_log.append(
                {
                    "type": "funding",
                    "symbol": pos.symbol,
                    "amount": funding_fee,
                    "rate": rate,
                    "periods": periods,
                    "timestamp": candle.get("open_time"),
                }
            )

    def _check_liquidation(self, candle: dict) -> None:
        """Trigger liquidation if equity falls below maintenance margin."""

        if not self.positions:
            return

        price = candle.get("close", 0)
        maintenance_req = 0.0
        for p in self.positions.values():
            rate = self._get_maintenance_margin_rate(p.symbol, candle)
            maintenance_req += price * p.quantity * rate

        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        equity = self.capital + total_unrealized

        if equity > maintenance_req:
            return

        # Liquidate all positions at current price with penalty
        penalty_rate = self.config.liquidation_penalty_pct

        for symbol, pos in list(self.positions.items()):
            opposite_side = (
                OrderSide.SELL if pos.side == PositionSide.LONG else OrderSide.BUY
            )
            order = Order(
                id=f"LIQ_{symbol}_{self._trade_counter:06d}",
                symbol=symbol,
                side=opposite_side,
                order_type=OrderType.MARKET,
                quantity=pos.quantity,
            )

            slippage = self.config.slippage_model.calculate(
                price=price,
                order_size=pos.quantity,
                side=opposite_side.value,
                volume=candle.get("volume", 1_000_000),
                volatility=self._calculate_volatility(candle),
            )

            penalty = price * pos.quantity * penalty_rate

            self._fill_order(
                order,
                slippage.execution_price,
                pos.quantity,
                candle,
                slippage,
                reason="liquidation",
                extra_cost=penalty,
            )

            self.events_log.append(
                {
                    "type": "liquidation",
                    "symbol": symbol,
                    "penalty": penalty,
                    "timestamp": candle.get("open_time"),
                }
            )

        self.liquidations += 1
        # Avoid negative balances after liquidation
        if self.capital < 0:
            self.capital = 0

    def _calculate_volatility(self, candle: dict) -> float:
        """Estimate volatility from candle."""
        high = candle.get("high", 0)
        low = candle.get("low", 0)
        close = candle.get("close", 1)
        return (high - low) / close if close > 0 else 0.02

    def _calculate_results(self, data: list[dict], duration: float) -> dict[str, Any]:
        """Calculate final backtest results."""
        if not self.trades:
            total_return = (
                self.equity - self.config.initial_capital
            ) / self.config.initial_capital
            time_in_market_pct = (
                (self.bars_in_market / len(self.equity_curve) * 100)
                if self.equity_curve
                else 0
            )
            return {
                "status": "no_trades",
                "config": {
                    "initial_capital": self.config.initial_capital,
                    "leverage": self.config.leverage,
                    "maker_fee": self.config.maker_fee,
                    "taker_fee": self.config.taker_fee,
                },
                "performance": {
                    "final_capital": round(self.equity, 2),
                    "total_return": round(total_return * 100, 2),
                    "sharpe_ratio": 0,
                    "sortino_ratio": 0,
                    "calmar_ratio": 0,
                    "max_drawdown": 0,
                    "max_drawdown_bars": self.max_dd_duration,
                    "time_in_market_pct": round(time_in_market_pct, 2),
                    "profit_factor": 0,
                },
                "events": {
                    "liquidations": self.liquidations,
                    "funding_events": len(
                        [e for e in self.events_log if e["type"] == "funding"]
                    ),
                    "log": self.events_log,
                },
                "trades": {
                    "total": 0,
                    "winning": 0,
                    "losing": 0,
                    "win_rate": 0,
                    "avg_trade": 0,
                    "avg_win": 0,
                    "avg_loss": 0,
                    "expectancy": 0,
                },
                "costs": {
                    "total_commission": 0,
                    "total_slippage": 0,
                    "total_funding": 0,
                    "cost_ratio": 0,
                },
                "equity_curve": self.equity_curve,
                "drawdown_curve": self.drawdown_curve,
                "all_trades": [],
                "duration_seconds": round(duration, 2),
            }

        # Basic metrics
        total_return = (
            self.equity - self.config.initial_capital
        ) / self.config.initial_capital
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0

        # Calculate Sharpe with strong guards against instability
        if len(self.equity_curve) > 1:
            returns = np.diff(self.equity_curve) / np.maximum(
                np.array(self.equity_curve[:-1]), 1e-12
            )
            returns = returns[np.isfinite(returns)]
            if returns.size > 1:
                std = np.std(returns)
                # TradingView Sortino: DD = sqrt(sum(min(0, Xi))^2 / N)
                downside_sq = np.minimum(0, returns) ** 2
                downside_dev = np.sqrt(downside_sq.sum() / len(returns))
                if std < 1e-9:
                    sharpe = 0
                else:
                    sharpe = np.mean(returns) / std * np.sqrt(365 * 24)
                if downside_dev < 1e-9:
                    sortino = 0
                else:
                    sortino = np.mean(returns) / downside_dev * np.sqrt(365 * 24)
            else:
                sharpe = 0
                sortino = 0
        else:
            sharpe = 0
            sortino = 0

        if not np.isfinite(sharpe):
            sharpe = 0
        sharpe = float(np.clip(sharpe, -25, 25))

        if not np.isfinite(sortino):
            sortino = 0
        sortino = float(np.clip(sortino, -25, 25))

        # Profit factor - use GROSS values (pnl + fees to exclude commissions)
        # TradingView calculates gross profit/loss BEFORE commissions
        gross_profit = sum(t.pnl + getattr(t, "fees", 0) for t in winning_trades)
        gross_loss = abs(sum(t.pnl + getattr(t, "fees", 0) for t in losing_trades))
        total_commission = sum(getattr(t, "fees", 0) for t in self.trades)
        net_profit = sum(t.pnl for t in self.trades)
        profit_factor_raw = (
            gross_profit / gross_loss if gross_loss > 0 else float("inf")
        )
        # Cap profit factor to avoid inf/overflow in reporting
        profit_factor = min(profit_factor_raw, 100.0)

        calmar = 0
        if self.max_drawdown > 1e-6:
            calmar = total_return / self.max_drawdown
        calmar = float(np.clip(calmar, -50, 50)) if np.isfinite(calmar) else 0

        # Average trade
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        avg_trade = np.mean([t.pnl for t in self.trades])

        # Expectancy
        expectancy = win_rate * avg_win - (1 - win_rate) * abs(avg_loss)

        time_in_market_pct = (
            (self.bars_in_market / len(self.equity_curve) * 100)
            if self.equity_curve
            else 0
        )

        # Total costs
        total_commission = sum(t.commission for t in self.trades)
        total_slippage = sum(t.slippage for t in self.trades)
        total_funding = (
            sum(t.funding_fees for t in self.trades) or self.total_funding_fees
        )

        return {
            "status": "completed",
            "config": {
                "initial_capital": self.config.initial_capital,
                "leverage": self.config.leverage,
                "maker_fee": self.config.maker_fee,
                "taker_fee": self.config.taker_fee,
            },
            "performance": {
                "final_capital": round(self.equity, 2),
                "total_return": round(total_return * 100, 2),
                "net_profit": round(net_profit, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
                "sharpe_ratio": round(sharpe, 3),
                "sortino_ratio": round(sortino, 3),
                "calmar_ratio": round(calmar, 3),
                "max_drawdown": round(self.max_drawdown * 100, 2),
                "max_drawdown_bars": self.max_dd_duration,
                "time_in_market_pct": round(time_in_market_pct, 2),
                "profit_factor": round(profit_factor, 2),
            },
            "events": {
                "liquidations": self.liquidations,
                "funding_events": len(
                    [e for e in self.events_log if e["type"] == "funding"]
                ),
                "log": self.events_log,
            },
            "trades": {
                "total": len(self.trades),
                "winning": len(winning_trades),
                "losing": len(losing_trades),
                "win_rate": round(win_rate * 100, 2),
                "avg_trade": round(avg_trade, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "expectancy": round(expectancy, 2),
            },
            "costs": {
                "total_commission": round(total_commission, 4),
                "total_slippage": round(total_slippage, 4),
                "total_funding": round(total_funding, 4),
                "cost_ratio": round(
                    (total_commission + total_slippage + abs(total_funding))
                    / self.config.initial_capital
                    * 100,
                    2,
                ),
            },
            "equity_curve": self.equity_curve,
            "drawdown_curve": self.drawdown_curve,
            "all_trades": [t.to_dict() for t in self.trades],
            "duration_seconds": round(duration, 2),
        }
