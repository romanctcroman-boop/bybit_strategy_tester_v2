"""
Margin Call Simulation Module

TradingView margin call simulation for leveraged positions.
Simulates position liquidation when margin requirements are not met.

TradingView 10-step margin call logic:
1. Calculate Available Funds
2. Calculate Open Profit/Loss
3. Calculate Margin Ratio
4. Calculate Used Margin Percentage
5. If Used% >= threshold → Margin Call
6. Calculate Loss and Cover Amount
7. Execute Margin Call
"""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    pass


class MarginCallType(str, Enum):
    """Type of margin call event."""

    NONE = "none"
    WARNING = "warning"  # Approaching threshold
    LIQUIDATION = "liquidation"  # Position liquidated


@dataclass
class MarginStatus:
    """Current margin status for a position."""

    equity: float  # Current equity
    used_margin: float  # Margin used by positions
    available_margin: float  # Free margin
    margin_level: float  # equity / used_margin * 100 (%)
    unrealized_pnl: float  # Unrealized P&L
    margin_call_type: MarginCallType
    cover_amount: float  # Amount to liquidate if margin call
    message: str


class MarginCallSimulator:
    """
    Simulates margin calls for leveraged trading.

    TradingView behavior:
    - Tracks used margin as percentage of position value
    - Triggers margin call when used margin % >= threshold
    - Calculates cover amount = loss × 4 (TradingView formula)
    """

    def __init__(
        self,
        margin_call_enabled: bool = False,
        margin_call_threshold: float = 100.0,
        maintenance_margin: float = 50.0,
        margin_long: float = 100.0,
        margin_short: float = 100.0,
    ):
        """
        Initialize Margin Call Simulator.

        Args:
            margin_call_enabled: Enable margin call simulation
            margin_call_threshold: % at which margin call triggers (100 = full)
            maintenance_margin: Maintenance margin % (liquidation below this)
            margin_long: Margin requirement for longs (%, 100 = no leverage)
            margin_short: Margin requirement for shorts (%, 100 = no leverage)
        """
        self.enabled = margin_call_enabled
        self.threshold = margin_call_threshold
        self.maintenance = maintenance_margin
        self.margin_long = margin_long
        self.margin_short = margin_short

        if self.enabled:
            logger.info(
                f"Margin Call Simulator: threshold={self.threshold}%, "
                f"maintenance={self.maintenance}%, "
                f"long_margin={self.margin_long}%, short_margin={self.margin_short}%"
            )

    def calculate_margin_required(self, position_value: float, is_long: bool) -> float:
        """
        Calculate margin required for a position.

        Args:
            position_value: Absolute value of position
            is_long: True for long, False for short

        Returns:
            Required margin amount
        """
        margin_pct = self.margin_long if is_long else self.margin_short
        return position_value * (margin_pct / 100.0)

    def calculate_leverage(self, is_long: bool) -> float:
        """
        Calculate effective leverage.

        Args:
            is_long: True for long, False for short

        Returns:
            Leverage multiplier (e.g., 4.0 for 25% margin)
        """
        margin_pct = self.margin_long if is_long else self.margin_short
        return 100.0 / margin_pct

    def check_margin_status(
        self,
        initial_capital: float,
        position_value: float,
        entry_price: float,
        current_price: float,
        is_long: bool,
        realized_pnl: float = 0.0,
    ) -> MarginStatus:
        """
        Check current margin status and determine if margin call needed.

        TradingView 10-step logic:
        1. Available Funds = Initial Capital + Realized P&L
        2. Open Profit = Position Size × (Current Price - Entry Price)
        3. Margin Ratio = Entry Price × Qty × Margin%
        4. Used Margin % = Margin Ratio / (Available + Open Profit) × 100
        5. If Used% >= 100% → Margin Call

        Args:
            initial_capital: Starting capital
            position_value: Notional value at entry
            entry_price: Position entry price
            current_price: Current market price
            is_long: True for long
            realized_pnl: Realized P&L from closed trades

        Returns:
            MarginStatus with current state
        """
        if not self.enabled or position_value == 0:
            return MarginStatus(
                equity=initial_capital + realized_pnl,
                used_margin=0.0,
                available_margin=initial_capital + realized_pnl,
                margin_level=float("inf"),
                unrealized_pnl=0.0,
                margin_call_type=MarginCallType.NONE,
                cover_amount=0.0,
                message="No position or margin calls disabled",
            )

        # Step 1: Available Funds
        available_funds = initial_capital + realized_pnl

        # Step 2: Open Profit/Loss
        position_size = position_value / entry_price
        if is_long:
            unrealized_pnl = (current_price - entry_price) * position_size
        else:
            unrealized_pnl = (entry_price - current_price) * position_size

        # Step 3: Margin Ratio (required margin)
        margin_pct = self.margin_long if is_long else self.margin_short
        margin_required = entry_price * position_size * (margin_pct / 100.0)

        # Step 4: Current equity and used margin %
        current_equity = available_funds + unrealized_pnl

        if current_equity <= 0:
            # Complete loss
            return MarginStatus(
                equity=current_equity,
                used_margin=margin_required,
                available_margin=0.0,
                margin_level=0.0,
                unrealized_pnl=unrealized_pnl,
                margin_call_type=MarginCallType.LIQUIDATION,
                cover_amount=position_value,
                message="Equity depleted - full liquidation",
            )

        # Margin level = equity / used_margin × 100
        margin_level = (
            (current_equity / margin_required) * 100
            if margin_required > 0
            else float("inf")
        )
        # used_margin_pct for logging/debugging
        _ = (margin_required / current_equity) * 100
        available_margin = current_equity - margin_required

        # Step 5: Check for margin call
        margin_call_type = MarginCallType.NONE
        cover_amount = 0.0
        message = "Margin OK"

        if margin_level <= self.maintenance:
            # Below maintenance margin - liquidation
            margin_call_type = MarginCallType.LIQUIDATION
            loss = abs(min(0, unrealized_pnl))
            cover_amount = loss * 4  # TradingView formula
            cover_amount = min(
                cover_amount, position_value
            )  # Can't cover more than position
            message = f"Margin call: level {margin_level:.1f}% <= maintenance {self.maintenance}%"
            logger.warning(f"MARGIN CALL: {message}, cover={cover_amount:.2f}")

        elif margin_level <= self.threshold:
            # Approaching threshold - warning
            margin_call_type = MarginCallType.WARNING
            message = f"Margin warning: level {margin_level:.1f}% approaching threshold"

        return MarginStatus(
            equity=current_equity,
            used_margin=margin_required,
            available_margin=available_margin,
            margin_level=margin_level,
            unrealized_pnl=unrealized_pnl,
            margin_call_type=margin_call_type,
            cover_amount=cover_amount,
            message=message,
        )

    def calculate_liquidation_price(
        self,
        entry_price: float,
        is_long: bool,
        initial_margin: float,
        position_size: float,
    ) -> float:
        """
        Calculate the price at which position would be liquidated.

        Args:
            entry_price: Position entry price
            is_long: True for long
            initial_margin: Initial margin deposited
            position_size: Position size in base currency

        Returns:
            Liquidation price
        """
        # margin_pct used to determine leverage context
        _ = self.margin_long if is_long else self.margin_short
        maintenance_ratio = self.maintenance / 100.0

        # At liquidation: equity = maintenance_margin × position_value
        # For long: (current_price - entry) × size + initial_margin = maintenance_ratio × current_price × size
        # Solving for current_price:

        if position_size == 0:
            return 0.0

        if is_long:
            # liq_price = (entry × size - initial_margin) / (size × (1 - maintenance_ratio))
            denominator = position_size * (1 - maintenance_ratio)
            if denominator == 0:
                return 0.0
            liq_price = (entry_price * position_size - initial_margin) / denominator
            return max(0.0, liq_price)
        else:
            # For short: liq_price = (entry × size + initial_margin) / (size × (1 + maintenance_ratio))
            denominator = position_size * (1 + maintenance_ratio)
            if denominator == 0:
                return float("inf")
            liq_price = (entry_price * position_size + initial_margin) / denominator
            return liq_price


def create_margin_simulator(config) -> MarginCallSimulator:
    """
    Create MarginCallSimulator from BacktestConfig.

    Args:
        config: BacktestConfig object

    Returns:
        Configured MarginCallSimulator
    """
    return MarginCallSimulator(
        margin_call_enabled=getattr(config, "margin_call_enabled", False),
        margin_call_threshold=getattr(config, "margin_call_threshold", 100.0),
        maintenance_margin=getattr(config, "maintenance_margin", 50.0),
        margin_long=getattr(config, "margin_long", 100.0),
        margin_short=getattr(config, "margin_short", 100.0),
    )
