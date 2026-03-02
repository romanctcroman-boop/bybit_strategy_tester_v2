"""
📈 Risk Limits

Risk management for live trading.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RiskLimitResult:
    """Risk limit check result"""

    allowed: bool
    reason: str | None = None
    current_value: float = 0.0
    limit_value: float = 0.0


class RiskLimits:
    """
    Risk limits for live trading.

    Limits:
    - Max loss per day
    - Max loss per trade
    - Max position size
    - Max drawdown
    - Circuit breakers
    """

    def __init__(
        self,
        max_daily_loss: float = 1000.0,
        max_trade_loss: float = 200.0,
        max_position_size: float = 10000.0,
        max_drawdown: float = 0.1,
        max_trades_per_day: int = 20,
        circuit_breaker_threshold: float = 500.0,
    ):
        """
        Args:
            max_daily_loss: Maximum loss per day ($)
            max_trade_loss: Maximum loss per trade ($)
            max_position_size: Maximum position size ($)
            max_drawdown: Maximum drawdown (fraction)
            max_trades_per_day: Maximum trades per day
            circuit_breaker_threshold: Circuit breaker threshold ($)
        """
        self.max_daily_loss = max_daily_loss
        self.max_trade_loss = max_trade_loss
        self.max_position_size = max_position_size
        self.max_drawdown = max_drawdown
        self.max_trades_per_day = max_trades_per_day
        self.circuit_breaker_threshold = circuit_breaker_threshold

        # State
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.peak_equity = 0.0
        self.current_equity = 0.0
        self.last_reset_date = datetime.now().date()

        # Circuit breaker
        self.circuit_breaker_active = False
        self.circuit_breaker_triggered_at: datetime | None = None

    def _reset_daily_if_needed(self):
        """Reset daily stats if new day"""
        today = datetime.now().date()

        if today != self.last_reset_date:
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_reset_date = today
            self.circuit_breaker_active = False

            logger.info("Daily stats reset")

    def check_daily_loss(self) -> RiskLimitResult:
        """Check daily loss limit"""
        self._reset_daily_if_needed()

        if self.daily_pnl < -self.max_daily_loss:
            return RiskLimitResult(
                allowed=False,
                reason=f"Daily loss limit reached: {self.daily_pnl:.2f}",
                current_value=self.daily_pnl,
                limit_value=-self.max_daily_loss,
            )

        return RiskLimitResult(allowed=True)

    def check_trade_loss(self, estimated_loss: float) -> RiskLimitResult:
        """Check per-trade loss limit"""
        if estimated_loss < -self.max_trade_loss:
            return RiskLimitResult(
                allowed=False,
                reason=f"Trade loss limit exceeded: {estimated_loss:.2f}",
                current_value=estimated_loss,
                limit_value=-self.max_trade_loss,
            )

        return RiskLimitResult(allowed=True)

    def check_position_size(self, position_size: float) -> RiskLimitResult:
        """Check position size limit"""
        if position_size > self.max_position_size:
            return RiskLimitResult(
                allowed=False,
                reason=f"Position size limit exceeded: {position_size:.2f}",
                current_value=position_size,
                limit_value=self.max_position_size,
            )

        return RiskLimitResult(allowed=True)

    def check_drawdown(self) -> RiskLimitResult:
        """Check drawdown limit"""
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

        if self.peak_equity > 0:
            drawdown = (self.peak_equity - self.current_equity) / self.peak_equity

            if drawdown > self.max_drawdown:
                return RiskLimitResult(
                    allowed=False,
                    reason=f"Max drawdown exceeded: {drawdown:.2%}",
                    current_value=drawdown,
                    limit_value=self.max_drawdown,
                )

        return RiskLimitResult(allowed=True)

    def check_trades_per_day(self) -> RiskLimitResult:
        """Check trades per day limit"""
        self._reset_daily_if_needed()

        if self.daily_trades >= self.max_trades_per_day:
            return RiskLimitResult(
                allowed=False,
                reason=f"Max trades per day reached: {self.daily_trades}",
                current_value=self.daily_trades,
                limit_value=self.max_trades_per_day,
            )

        return RiskLimitResult(allowed=True)

    def check_circuit_breaker(self) -> RiskLimitResult:
        """Check circuit breaker"""
        self._reset_daily_if_needed()

        if self.circuit_breaker_active and self.circuit_breaker_triggered_at:
            # Check if 1 hour has passed
            elapsed = datetime.now() - self.circuit_breaker_triggered_at

            if elapsed > timedelta(hours=1):
                self.circuit_breaker_active = False
                logger.info("Circuit breaker reset")
            else:
                return RiskLimitResult(
                    allowed=False,
                    reason=f"Circuit breaker active for {elapsed}",
                )

        if self.daily_pnl < -self.circuit_breaker_threshold:
            self.circuit_breaker_active = True
            self.circuit_breaker_triggered_at = datetime.now()

            logger.warning(f"Circuit breaker triggered: daily PnL = {self.daily_pnl:.2f}")

            return RiskLimitResult(
                allowed=False,
                reason="Circuit breaker triggered",
            )

        return RiskLimitResult(allowed=True)

    def check_all(self) -> RiskLimitResult:
        """Check all limits"""
        checks = [
            self.check_daily_loss(),
            self.check_drawdown(),
            self.check_trades_per_day(),
            self.check_circuit_breaker(),
        ]

        for check in checks:
            if not check.allowed:
                return check

        return RiskLimitResult(allowed=True)

    def update_pnl(self, pnl: float):
        """Update daily PnL"""
        self.daily_pnl += pnl
        self.current_equity += pnl

        logger.debug(f"Daily PnL updated: {pnl:.2f}, total: {self.daily_pnl:.2f}")

    def increment_trades(self):
        """Increment daily trade count"""
        self.daily_trades += 1
