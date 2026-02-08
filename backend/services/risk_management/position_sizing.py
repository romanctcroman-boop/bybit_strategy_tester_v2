"""
Position Sizing Module.

Provides various position sizing methods for risk management:
- Fixed Percentage: Risk a fixed % of equity per trade
- Kelly Criterion: Optimal sizing based on win rate and payoff ratio
- Volatility-Based: Size based on asset volatility (ATR)
- Fixed Fractional: Fixed fraction of equity
- Optimal f: Maximize geometric growth
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SizingMethod(str, Enum):
    """Position sizing methods."""

    FIXED_PERCENTAGE = "fixed_percentage"
    KELLY_CRITERION = "kelly_criterion"
    VOLATILITY_BASED = "volatility_based"
    FIXED_FRACTIONAL = "fixed_fractional"
    OPTIMAL_F = "optimal_f"
    HALF_KELLY = "half_kelly"
    QUARTER_KELLY = "quarter_kelly"


@dataclass
class SizingResult:
    """Result of position sizing calculation."""

    position_size: float  # In base currency (e.g., BTC)
    position_value: float  # In quote currency (e.g., USDT)
    risk_amount: float  # Amount at risk
    risk_percentage: float  # % of equity at risk
    stop_loss_price: float | None
    method_used: SizingMethod
    details: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "position_size": self.position_size,
            "position_value": self.position_value,
            "risk_amount": self.risk_amount,
            "risk_percentage": self.risk_percentage,
            "stop_loss_price": self.stop_loss_price,
            "method_used": self.method_used.value,
            "details": self.details,
        }


@dataclass
class TradingStats:
    """Historical trading statistics for Kelly calculation."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_rate: float = 0.0
    payoff_ratio: float = 1.0
    expectancy: float = 0.0

    @classmethod
    def from_trades(cls, trades: list[dict]) -> "TradingStats":
        """Calculate stats from trade history."""
        if not trades:
            return cls()

        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) < 0]

        total_profit = sum(t["pnl"] for t in wins)
        total_loss = abs(sum(t["pnl"] for t in losses))

        avg_win = total_profit / len(wins) if wins else 0
        avg_loss = total_loss / len(losses) if losses else 1

        win_rate = len(wins) / len(trades) if trades else 0
        payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 1

        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        return cls(
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            total_profit=total_profit,
            total_loss=total_loss,
            avg_win=avg_win,
            avg_loss=avg_loss,
            win_rate=win_rate,
            payoff_ratio=payoff_ratio,
            expectancy=expectancy,
        )


class PositionSizer:
    """
    Position sizing calculator with multiple methods.

    Usage:
        sizer = PositionSizer(
            equity=10000,
            default_risk_pct=2.0,
            max_position_pct=25.0
        )

        result = sizer.calculate_size(
            entry_price=50000,
            stop_loss_price=48000,
            method=SizingMethod.FIXED_PERCENTAGE
        )
    """

    def __init__(
        self,
        equity: float,
        default_risk_pct: float = 2.0,
        max_position_pct: float = 25.0,
        max_risk_pct: float = 5.0,
        min_position_size: float = 0.001,
    ):
        """
        Initialize position sizer.

        Args:
            equity: Current account equity
            default_risk_pct: Default risk per trade (%)
            max_position_pct: Maximum position size as % of equity
            max_risk_pct: Maximum risk per trade (%)
            min_position_size: Minimum position size (contracts/units)
        """
        self.equity = equity
        self.default_risk_pct = default_risk_pct
        self.max_position_pct = max_position_pct
        self.max_risk_pct = max_risk_pct
        self.min_position_size = min_position_size

        # Trading stats for Kelly
        self.stats: TradingStats | None = None

        # Volatility data for ATR sizing
        self.atr_values: dict[str, float] = {}

        logger.info(
            f"PositionSizer initialized: equity=${equity:.2f}, "
            f"risk={default_risk_pct}%, max_position={max_position_pct}%"
        )

    def update_equity(self, equity: float):
        """Update current equity."""
        self.equity = equity

    def update_stats(self, trades: list[dict]):
        """Update trading statistics from trade history."""
        self.stats = TradingStats.from_trades(trades)
        logger.debug(
            f"Stats updated: {self.stats.total_trades} trades, "
            f"win_rate={self.stats.win_rate:.2%}"
        )

    def update_atr(self, symbol: str, atr: float):
        """Update ATR value for a symbol."""
        self.atr_values[symbol] = atr

    def calculate_size(
        self,
        entry_price: float,
        stop_loss_price: float | None = None,
        method: SizingMethod = SizingMethod.FIXED_PERCENTAGE,
        risk_pct: float | None = None,
        symbol: str | None = None,
        leverage: float = 1.0,
    ) -> SizingResult:
        """
        Calculate position size using specified method.

        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price (required for most methods)
            method: Sizing method to use
            risk_pct: Override default risk percentage
            symbol: Trading symbol (for ATR lookup)
            leverage: Leverage to use

        Returns:
            SizingResult with calculated position size
        """
        risk_pct = risk_pct or self.default_risk_pct

        # Calculate based on method
        if method == SizingMethod.FIXED_PERCENTAGE:
            result = self._fixed_percentage(
                entry_price, stop_loss_price, risk_pct, leverage
            )
        elif method == SizingMethod.KELLY_CRITERION:
            result = self._kelly_criterion(entry_price, stop_loss_price, leverage)
        elif method == SizingMethod.HALF_KELLY:
            result = self._kelly_criterion(
                entry_price, stop_loss_price, leverage, fraction=0.5
            )
        elif method == SizingMethod.QUARTER_KELLY:
            result = self._kelly_criterion(
                entry_price, stop_loss_price, leverage, fraction=0.25
            )
        elif method == SizingMethod.VOLATILITY_BASED:
            result = self._volatility_based(entry_price, symbol, risk_pct, leverage)
        elif method == SizingMethod.FIXED_FRACTIONAL:
            result = self._fixed_fractional(entry_price, risk_pct, leverage)
        elif method == SizingMethod.OPTIMAL_F:
            result = self._optimal_f(entry_price, stop_loss_price, leverage)
        else:
            result = self._fixed_percentage(
                entry_price, stop_loss_price, risk_pct, leverage
            )

        # Apply constraints
        result = self._apply_constraints(result, entry_price, leverage)

        logger.info(
            f"Position sized: {result.position_size:.6f} @ ${entry_price:.2f}, "
            f"risk={result.risk_percentage:.2f}%, method={method.value}"
        )

        return result

    def _fixed_percentage(
        self,
        entry_price: float,
        stop_loss_price: float | None,
        risk_pct: float,
        leverage: float,
    ) -> SizingResult:
        """
        Fixed percentage risk method.

        Risk a fixed percentage of equity per trade.
        Position size = (Equity * Risk%) / (Entry - StopLoss)
        """
        risk_amount = self.equity * (risk_pct / 100)

        if stop_loss_price and stop_loss_price != entry_price:
            stop_distance = abs(entry_price - stop_loss_price)
            stop_pct = stop_distance / entry_price

            # Position size in base currency
            position_size = risk_amount / stop_distance
            position_value = position_size * entry_price
        else:
            # No stop loss - use risk % as position %
            position_value = risk_amount
            position_size = position_value / entry_price
            stop_pct = risk_pct / 100

        return SizingResult(
            position_size=position_size,
            position_value=position_value,
            risk_amount=risk_amount,
            risk_percentage=risk_pct,
            stop_loss_price=stop_loss_price,
            method_used=SizingMethod.FIXED_PERCENTAGE,
            details={
                "equity": self.equity,
                "risk_pct": risk_pct,
                "stop_distance_pct": stop_pct * 100 if stop_loss_price else 0,
            },
        )

    def _kelly_criterion(
        self,
        entry_price: float,
        stop_loss_price: float | None,
        leverage: float,
        fraction: float = 1.0,
    ) -> SizingResult:
        """
        Kelly Criterion position sizing.

        Kelly % = W - [(1-W) / R]
        Where:
            W = Win rate
            R = Payoff ratio (avg win / avg loss)
        """
        if not self.stats or self.stats.total_trades < 10:
            # Not enough data - use conservative 1%
            logger.warning("Insufficient trade history for Kelly - using 1% risk")
            return self._fixed_percentage(entry_price, stop_loss_price, 1.0, leverage)

        win_rate = self.stats.win_rate
        payoff_ratio = self.stats.payoff_ratio

        # Kelly formula: W - [(1-W) / R]
        kelly_pct = win_rate - ((1 - win_rate) / payoff_ratio)

        # Apply fraction (half-Kelly, quarter-Kelly)
        kelly_pct = kelly_pct * fraction

        # Clamp to reasonable range
        kelly_pct = max(0, min(kelly_pct * 100, self.max_risk_pct))

        if kelly_pct <= 0:
            # Negative Kelly = don't trade
            logger.warning(f"Negative Kelly: {kelly_pct:.2f}% - reducing to minimum")
            kelly_pct = 0.5

        result = self._fixed_percentage(
            entry_price, stop_loss_price, kelly_pct, leverage
        )
        result.method_used = (
            SizingMethod.HALF_KELLY
            if fraction == 0.5
            else SizingMethod.QUARTER_KELLY
            if fraction == 0.25
            else SizingMethod.KELLY_CRITERION
        )
        result.details.update(
            {
                "kelly_pct": kelly_pct / fraction,  # Raw Kelly
                "fraction": fraction,
                "win_rate": win_rate,
                "payoff_ratio": payoff_ratio,
                "expectancy": self.stats.expectancy,
            }
        )

        return result

    def _volatility_based(
        self,
        entry_price: float,
        symbol: str | None,
        risk_pct: float,
        leverage: float,
    ) -> SizingResult:
        """
        Volatility-based position sizing using ATR.

        Stop distance = N * ATR
        Position size = Risk Amount / (N * ATR)

        This automatically adjusts for market volatility.
        """
        # Get ATR for symbol
        atr = self.atr_values.get(symbol, 0) if symbol else 0

        if atr <= 0:
            logger.warning(f"No ATR for {symbol} - using 2% of price")
            atr = entry_price * 0.02  # Default 2% ATR

        # Use 2x ATR as stop distance (common practice)
        atr_multiplier = 2.0
        stop_distance = atr * atr_multiplier
        stop_loss_price = entry_price - stop_distance

        risk_amount = self.equity * (risk_pct / 100)
        position_size = risk_amount / stop_distance
        position_value = position_size * entry_price

        return SizingResult(
            position_size=position_size,
            position_value=position_value,
            risk_amount=risk_amount,
            risk_percentage=risk_pct,
            stop_loss_price=stop_loss_price,
            method_used=SizingMethod.VOLATILITY_BASED,
            details={
                "atr": atr,
                "atr_multiplier": atr_multiplier,
                "stop_distance": stop_distance,
                "stop_distance_pct": (stop_distance / entry_price) * 100,
            },
        )

    def _fixed_fractional(
        self,
        entry_price: float,
        risk_pct: float,
        leverage: float,
    ) -> SizingResult:
        """
        Fixed fractional position sizing.

        Simple: Position = Equity * (risk% / 100)
        No stop loss considered.
        """
        position_value = self.equity * (risk_pct / 100)
        position_size = position_value / entry_price

        return SizingResult(
            position_size=position_size,
            position_value=position_value,
            risk_amount=position_value,  # Entire position is "at risk"
            risk_percentage=risk_pct,
            stop_loss_price=None,
            method_used=SizingMethod.FIXED_FRACTIONAL,
            details={
                "equity": self.equity,
                "fraction": risk_pct / 100,
            },
        )

    def _optimal_f(
        self,
        entry_price: float,
        stop_loss_price: float | None,
        leverage: float,
    ) -> SizingResult:
        """
        Optimal f position sizing.

        Maximizes geometric growth rate.
        f = ((B+1) * W - 1) / B
        Where:
            B = Average win / Average loss ratio
            W = Win rate
        """
        if not self.stats or self.stats.total_trades < 20:
            logger.warning("Insufficient data for Optimal f - using 1%")
            return self._fixed_percentage(entry_price, stop_loss_price, 1.0, leverage)

        b = self.stats.payoff_ratio
        w = self.stats.win_rate

        # Optimal f formula
        optimal_f = ((b + 1) * w - 1) / b

        # Convert to percentage and clamp
        optimal_f_pct = max(0, min(optimal_f * 100, self.max_risk_pct))

        if optimal_f_pct <= 0:
            optimal_f_pct = 0.5

        result = self._fixed_percentage(
            entry_price, stop_loss_price, optimal_f_pct, leverage
        )
        result.method_used = SizingMethod.OPTIMAL_F
        result.details.update(
            {
                "optimal_f": optimal_f,
                "win_rate": w,
                "payoff_ratio": b,
            }
        )

        return result

    def _apply_constraints(
        self,
        result: SizingResult,
        entry_price: float,
        leverage: float,
    ) -> SizingResult:
        """Apply position size constraints."""
        # Max position constraint
        max_position_value = self.equity * (self.max_position_pct / 100) * leverage
        if result.position_value > max_position_value:
            scale = max_position_value / result.position_value
            result.position_value = max_position_value
            result.position_size = result.position_value / entry_price
            result.risk_amount *= scale
            result.details["constrained_by"] = "max_position"
            logger.debug(f"Position constrained to max {self.max_position_pct}%")

        # Max risk constraint
        max_risk_amount = self.equity * (self.max_risk_pct / 100)
        if result.risk_amount > max_risk_amount:
            scale = max_risk_amount / result.risk_amount
            result.position_size *= scale
            result.position_value *= scale
            result.risk_amount = max_risk_amount
            result.risk_percentage = self.max_risk_pct
            result.details["constrained_by"] = "max_risk"
            logger.debug(f"Risk constrained to max {self.max_risk_pct}%")

        # Min position constraint
        if result.position_size < self.min_position_size:
            result.position_size = self.min_position_size
            result.position_value = result.position_size * entry_price
            result.details["constrained_by"] = "min_size"

        return result

    def get_optimal_method(self) -> SizingMethod:
        """
        Suggest optimal sizing method based on available data.

        Returns:
            Recommended SizingMethod
        """
        if self.stats and self.stats.total_trades >= 30:
            if self.stats.expectancy > 0:
                # Positive expectancy - use half-Kelly
                return SizingMethod.HALF_KELLY
            else:
                # Negative expectancy - use minimum
                return SizingMethod.FIXED_PERCENTAGE

        if self.atr_values:
            # Have volatility data - use ATR-based
            return SizingMethod.VOLATILITY_BASED

        # Default to fixed percentage
        return SizingMethod.FIXED_PERCENTAGE

    def calculate_all_methods(
        self,
        entry_price: float,
        stop_loss_price: float | None = None,
        symbol: str | None = None,
        leverage: float = 1.0,
    ) -> dict[SizingMethod, SizingResult]:
        """
        Calculate position size using all methods for comparison.

        Returns:
            Dictionary of results by method
        """
        results = {}

        for method in SizingMethod:
            try:
                results[method] = self.calculate_size(
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    method=method,
                    symbol=symbol,
                    leverage=leverage,
                )
            except Exception as e:
                logger.error(f"Error calculating {method}: {e}")

        return results
