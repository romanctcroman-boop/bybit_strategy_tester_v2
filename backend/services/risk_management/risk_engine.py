"""
Risk Engine - Unified Risk Management System

Integrates all risk management components into a single cohesive system
for live trading risk control.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from backend.services.risk_management.exposure_controller import (
    ExposureController,
    ExposureLimits,
    Position,
)
from backend.services.risk_management.position_sizing import (
    PositionSizer,
    SizingMethod,
)
from backend.services.risk_management.stop_loss_manager import (
    StopLossConfig,
    StopLossManager,
    StopLossType,
)
from backend.services.risk_management.trade_validator import (
    AccountState,
    TradeRequest,
    TradeValidator,
    ValidationConfig,
)

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classification."""

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"
    CRITICAL = "critical"


@dataclass
class RiskEngineConfig:
    """Configuration for the Risk Engine."""

    # Initial equity
    initial_equity: float = 10000.0

    # Position sizing
    sizing_method: SizingMethod = SizingMethod.FIXED_PERCENTAGE
    risk_per_trade_pct: float = 1.0
    max_position_size_pct: float = 10.0

    # Stop loss defaults
    default_stop_type: StopLossType = StopLossType.TRAILING
    default_stop_pct: float = 2.0
    trailing_offset_pct: float = 0.5

    # Exposure limits
    max_total_exposure_pct: float = 100.0
    max_correlated_exposure_pct: float = 30.0
    max_leverage: float = 5.0
    max_drawdown_pct: float = 20.0
    daily_loss_limit_pct: float = 5.0

    # Validation
    min_balance: float = 100.0
    max_trades_per_day: int = 50
    min_risk_reward: float = 1.0

    # Behavior
    auto_stop_on_drawdown: bool = True
    auto_reduce_on_loss: bool = True
    enable_correlation_check: bool = True


@dataclass
class RiskAssessment:
    """Result of risk assessment for a potential trade."""

    approved: bool
    risk_level: RiskLevel
    position_size: float
    recommended_stop_loss: float | None
    recommended_take_profit: float | None
    max_allowed_size: float
    current_exposure_pct: float
    available_capacity_pct: float
    warnings: list[str]
    rejection_reasons: list[str]
    details: dict[str, Any]
    assessed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "approved": self.approved,
            "risk_level": self.risk_level.value,
            "position_size": self.position_size,
            "recommended_stop_loss": self.recommended_stop_loss,
            "recommended_take_profit": self.recommended_take_profit,
            "max_allowed_size": self.max_allowed_size,
            "current_exposure_pct": self.current_exposure_pct,
            "available_capacity_pct": self.available_capacity_pct,
            "warnings": self.warnings,
            "rejection_reasons": self.rejection_reasons,
            "details": self.details,
            "assessed_at": self.assessed_at.isoformat(),
        }


@dataclass
class PortfolioRiskSnapshot:
    """Snapshot of current portfolio risk state."""

    timestamp: datetime
    total_equity: float
    used_margin: float
    available_balance: float
    total_exposure_pct: float
    current_drawdown_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    open_positions: int
    active_stops: int
    risk_level: RiskLevel
    is_trading_allowed: bool
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_equity": self.total_equity,
            "used_margin": self.used_margin,
            "available_balance": self.available_balance,
            "total_exposure_pct": self.total_exposure_pct,
            "current_drawdown_pct": self.current_drawdown_pct,
            "daily_pnl": self.daily_pnl,
            "daily_pnl_pct": self.daily_pnl_pct,
            "open_positions": self.open_positions,
            "active_stops": self.active_stops,
            "risk_level": self.risk_level.value,
            "is_trading_allowed": self.is_trading_allowed,
            "warnings": self.warnings,
        }


class RiskEngine:
    """
    Unified Risk Management Engine.

    Integrates:
    - Position Sizing
    - Stop Loss Management
    - Exposure Control
    - Trade Validation

    Provides a single interface for all risk management operations.
    """

    def __init__(self, config: RiskEngineConfig | None = None):
        """Initialize the Risk Engine."""
        self.config = config or RiskEngineConfig()

        # Initialize components
        self._init_position_sizer()
        self._init_stop_loss_manager()
        self._init_exposure_controller()
        self._init_trade_validator()

        # State
        self._is_running = False
        self._trading_paused = False
        self._pause_reason: str | None = None
        self._risk_history: list[PortfolioRiskSnapshot] = []
        self._max_history_size = 1000

        # Callbacks
        self.on_risk_alert: Callable[[str, RiskLevel], None] | None = None
        self.on_trading_paused: Callable[[str], None] | None = None
        self.on_stop_triggered: Callable[[str, float, float], None] | None = None

        logger.info(
            f"RiskEngine initialized: equity=${self.config.initial_equity:.2f}, "
            f"max_drawdown={self.config.max_drawdown_pct}%"
        )

    def _init_position_sizer(self):
        """Initialize position sizing component."""
        self.position_sizer = PositionSizer(
            equity=self.config.initial_equity,
            default_risk_pct=self.config.risk_per_trade_pct,
            max_position_pct=self.config.max_position_size_pct,
            max_risk_pct=self.config.risk_per_trade_pct * 2,
        )

    def _init_stop_loss_manager(self):
        """Initialize stop loss management component."""
        stop_config = StopLossConfig(
            trail_percent=self.config.trailing_offset_pct,
            breakeven_trigger_pct=self.config.default_stop_pct,
        )
        self.stop_loss_manager = StopLossManager(stop_config)

        # Wire up stop triggered callback
        def on_stop_triggered(symbol: str, trigger_price: float, stop_price: float):
            if self.on_stop_triggered:
                self.on_stop_triggered(symbol, trigger_price, stop_price)

        self.stop_loss_manager.on_stop_triggered = on_stop_triggered

    def _init_exposure_controller(self):
        """Initialize exposure control component."""
        exposure_limits = ExposureLimits(
            max_position_size_pct=self.config.max_position_size_pct,
            max_total_exposure_pct=self.config.max_total_exposure_pct,
            max_leverage=self.config.max_leverage,
            max_drawdown_pct=self.config.max_drawdown_pct,
            max_daily_loss_pct=self.config.daily_loss_limit_pct,
        )
        self.exposure_controller = ExposureController(
            equity=self.config.initial_equity, limits=exposure_limits
        )

        # Wire up limit breach callback
        def on_limit_breach(violation_type, message):
            if self.config.auto_stop_on_drawdown:
                if "drawdown" in message.lower() or "loss" in message.lower():
                    self.pause_trading(f"Risk limit breach: {message}")

            if self.on_risk_alert:
                self.on_risk_alert(message, RiskLevel.HIGH)

        self.exposure_controller.on_limit_breach = on_limit_breach

    def _init_trade_validator(self):
        """Initialize trade validation component."""
        validation_config = ValidationConfig(
            min_balance_usd=self.config.min_balance,
            max_leverage=self.config.max_leverage,
            max_order_size_pct=self.config.max_position_size_pct,
            max_trades_per_day=self.config.max_trades_per_day,
            min_risk_reward_ratio=self.config.min_risk_reward,
        )
        self.trade_validator = TradeValidator(validation_config)

    # ==================== Core Operations ====================

    def assess_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        volatility: float | None = None,
        atr: float | None = None,
        win_rate: float = 0.5,
        avg_win: float = 1.0,
        avg_loss: float = 1.0,
    ) -> RiskAssessment:
        """
        Comprehensive risk assessment for a potential trade.

        Combines position sizing, exposure check, and validation.

        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            entry_price: Entry price
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price
            volatility: Optional volatility for sizing
            atr: Optional ATR for stop calculation
            win_rate: Historical win rate
            avg_win: Average winning trade
            avg_loss: Average losing trade

        Returns:
            RiskAssessment with sizing and validation result
        """
        warnings = []
        rejection_reasons = []
        details = {}

        # Get current state
        current_exposure_data = self.exposure_controller.get_current_exposure()
        current_exposure = current_exposure_data.get("total_exposure_pct", 0)
        available_exposure = 100 - current_exposure  # Simplified available calculation
        equity = self.exposure_controller.equity

        details["current_equity"] = equity
        details["current_exposure_pct"] = current_exposure
        details["available_exposure_pct"] = available_exposure

        # Check if trading is allowed
        if self._trading_paused:
            rejection_reasons.append(f"Trading paused: {self._pause_reason}")

        # Calculate optimal position size using the sizer
        sizing_result = self.position_sizer.calculate_size(
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            method=self.config.sizing_method,
        )
        position_size = sizing_result.position_size
        details["calculated_position_size"] = position_size
        details["sizing_details"] = sizing_result.details

        # Calculate max allowed size from exposure limits
        max_from_exposure = self.exposure_controller.get_max_position_size(
            symbol=symbol, current_price=entry_price
        )

        # Apply the more restrictive limit
        final_size = min(position_size, max_from_exposure)
        details["max_from_exposure"] = max_from_exposure

        if final_size < position_size:
            warnings.append(
                f"Position size reduced from {position_size:.4f} to {final_size:.4f} "
                "due to exposure limits"
            )

        # Calculate recommended stop loss if not provided
        recommended_stop = stop_loss
        if not recommended_stop:
            if atr:
                recommended_stop = entry_price - 2 * atr if side.lower() == "buy" else entry_price + 2 * atr
            else:
                stop_pct = self.config.default_stop_pct / 100
                if side.lower() == "buy":
                    recommended_stop = entry_price * (1 - stop_pct)
                else:
                    recommended_stop = entry_price * (1 + stop_pct)
        details["recommended_stop_loss"] = recommended_stop

        # Calculate take profit if not provided
        recommended_tp = take_profit
        if not recommended_tp and recommended_stop:
            risk = abs(entry_price - recommended_stop)
            rr_target = max(self.config.min_risk_reward, 2.0)  # Target 2:1 RR
            recommended_tp = entry_price + risk * rr_target if side.lower() == "buy" else entry_price - risk * rr_target
        details["recommended_take_profit"] = recommended_tp

        # Create trade request for validation
        trade_request = TradeRequest(
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=final_size,
            price=entry_price,
            stop_loss=recommended_stop,
            take_profit=recommended_tp,
        )

        # Build account state
        account_state = AccountState(
            total_equity=equity,
            available_balance=self.exposure_controller.equity
            - self.exposure_controller.used_margin,
            used_margin=self.exposure_controller.used_margin,
            total_pnl=self.exposure_controller.total_pnl,
            daily_pnl=self.exposure_controller.daily_pnl,
            open_positions_count=len(self.exposure_controller.positions),
            positions_by_symbol=dict.fromkeys(self.exposure_controller.positions, 1),
            trades_today=0,  # Would need external tracking
            trades_this_hour=0,
            last_trade_time=None,
            is_trading_paused=self._trading_paused,
            current_drawdown_pct=self.exposure_controller.current_drawdown_pct,
        )

        # Validate trade
        validation = self.trade_validator.validate(trade_request, account_state)
        details["validation_result"] = validation.result.value

        if not validation.approved:
            rejection_reasons.extend([r.value for r in validation.rejection_reasons])

        warnings.extend(validation.warnings)

        # Determine risk level
        risk_level = self._calculate_risk_level(
            position_size=final_size,
            entry_price=entry_price,
            stop_loss=recommended_stop,
            current_exposure=current_exposure,
            equity=equity,
        )

        # Check exposure constraint
        can_add = self.exposure_controller.can_add_position(
            symbol=symbol, side=side, size=final_size, entry_price=entry_price
        )
        if not can_add["allowed"]:
            rejection_reasons.append(can_add.get("reason", "Exposure limit exceeded"))

        approved = len(rejection_reasons) == 0 and final_size > 0

        return RiskAssessment(
            approved=approved,
            risk_level=risk_level,
            position_size=final_size if approved else 0,
            recommended_stop_loss=recommended_stop,
            recommended_take_profit=recommended_tp,
            max_allowed_size=max_from_exposure,
            current_exposure_pct=current_exposure,
            available_capacity_pct=available_exposure,
            warnings=warnings,
            rejection_reasons=rejection_reasons,
            details=details,
            assessed_at=datetime.now(),
        )

    def _calculate_risk_level(
        self,
        position_size: float,
        entry_price: float,
        stop_loss: float | None,
        current_exposure: float,
        equity: float,
    ) -> RiskLevel:
        """Calculate risk level for a potential trade."""
        risk_score = 0

        # Position size relative to equity
        notional = position_size * entry_price
        size_pct = (notional / equity) * 100 if equity > 0 else 100

        if size_pct > 20:
            risk_score += 3
        elif size_pct > 10:
            risk_score += 2
        elif size_pct > 5:
            risk_score += 1

        # Current exposure
        if current_exposure > 80:
            risk_score += 3
        elif current_exposure > 50:
            risk_score += 2
        elif current_exposure > 30:
            risk_score += 1

        # Stop loss distance
        if stop_loss and entry_price:
            stop_distance_pct = abs(entry_price - stop_loss) / entry_price * 100
            if stop_distance_pct > 10:
                risk_score += 2
            elif stop_distance_pct > 5:
                risk_score += 1
        else:
            # No stop loss = higher risk
            risk_score += 2

        # Current drawdown
        if self.exposure_controller.current_drawdown_pct > 15:
            risk_score += 3
        elif self.exposure_controller.current_drawdown_pct > 10:
            risk_score += 2
        elif self.exposure_controller.current_drawdown_pct > 5:
            risk_score += 1

        # Map score to level
        if risk_score >= 10:
            return RiskLevel.CRITICAL
        elif risk_score >= 8:
            return RiskLevel.EXTREME
        elif risk_score >= 6:
            return RiskLevel.HIGH
        elif risk_score >= 4:
            return RiskLevel.MEDIUM
        elif risk_score >= 2:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL

    def register_trade(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        leverage: float = 1.0,
        stop_loss: float | None = None,
    ):
        """
        Register an executed trade with the risk engine.

        Call this after a trade is successfully executed.
        """
        # Update exposure controller
        position = Position(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            leverage=leverage,
        )
        self.exposure_controller.update_position(position)

        # Register stop loss if provided
        if stop_loss:
            self.stop_loss_manager.add_stop(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=entry_price,
                stop_price=stop_loss,
            )

        logger.info(
            f"Trade registered: {symbol} {side} {size}@{entry_price}, "
            f"leverage={leverage}x, stop={stop_loss}"
        )

    def close_position(self, symbol: str, exit_price: float):
        """
        Register a closed position.

        Call this after a position is closed.
        """
        self.exposure_controller.remove_position(symbol)
        self.stop_loss_manager.remove_stop(symbol)

        logger.info(f"Position closed: {symbol} @ {exit_price}")

    def update_price(self, symbol: str, current_price: float):
        """
        Update current price for a symbol.

        This triggers stop loss checks and exposure recalculation.
        """
        # Update trade validator price cache
        self.trade_validator.update_price(symbol, current_price)

        # Check stop losses
        triggered = self.stop_loss_manager.check_stops(symbol, current_price)

        return triggered

    def update_equity(self, equity: float):
        """Update current account equity."""
        self.exposure_controller.update_equity(equity)

        # Record snapshot
        self._record_snapshot()

    # ==================== Control Operations ====================

    def pause_trading(self, reason: str):
        """Pause all trading."""
        self._trading_paused = True
        self._pause_reason = reason

        logger.warning(f"Trading paused: {reason}")

        if self.on_trading_paused:
            self.on_trading_paused(reason)

    def resume_trading(self):
        """Resume trading."""
        self._trading_paused = False
        self._pause_reason = None
        logger.info("Trading resumed")

    def is_trading_allowed(self) -> bool:
        """Check if trading is currently allowed."""
        if self._trading_paused:
            return False

        # Check exposure limits
        return not self.exposure_controller.current_drawdown_pct >= self.config.max_drawdown_pct

    def reset_daily(self):
        """Reset daily tracking (call at start of trading day)."""
        self.exposure_controller.reset_daily()
        self._risk_history = []
        logger.info("Daily risk tracking reset")

    # ==================== Status & Reporting ====================

    def get_risk_snapshot(self) -> PortfolioRiskSnapshot:
        """Get current portfolio risk snapshot."""
        exposure_data = self.exposure_controller.get_current_exposure()
        exposure_pct = exposure_data.get("total_exposure_pct", 0)
        equity = self.exposure_controller.equity
        daily_pnl = self.exposure_controller.daily_pnl

        warnings = []

        if exposure_pct > 80:
            warnings.append("High portfolio exposure")

        if self.exposure_controller.current_drawdown_pct > 10:
            warnings.append("Elevated drawdown level")

        if daily_pnl < 0 and abs(daily_pnl) > equity * 0.03:
            warnings.append("Significant daily loss")

        risk_level = self._get_portfolio_risk_level()

        return PortfolioRiskSnapshot(
            timestamp=datetime.now(),
            total_equity=equity,
            used_margin=self.exposure_controller.used_margin,
            available_balance=max(0, equity - self.exposure_controller.used_margin),
            total_exposure_pct=exposure_pct,
            current_drawdown_pct=self.exposure_controller.current_drawdown_pct,
            daily_pnl=daily_pnl,
            daily_pnl_pct=(daily_pnl / equity * 100) if equity > 0 else 0,
            open_positions=len(self.exposure_controller.positions),
            active_stops=len(self.stop_loss_manager.get_active_stops()),
            risk_level=risk_level,
            is_trading_allowed=self.is_trading_allowed(),
            warnings=warnings,
        )

    def _get_portfolio_risk_level(self) -> RiskLevel:
        """Calculate overall portfolio risk level."""
        risk_score = 0

        exposure_data = self.exposure_controller.get_current_exposure()
        exposure = exposure_data.get("total_exposure_pct", 0)
        drawdown = self.exposure_controller.current_drawdown_pct

        if exposure > 80:
            risk_score += 3
        elif exposure > 50:
            risk_score += 2
        elif exposure > 30:
            risk_score += 1

        if drawdown > 15:
            risk_score += 4
        elif drawdown > 10:
            risk_score += 3
        elif drawdown > 5:
            risk_score += 2
        elif drawdown > 2:
            risk_score += 1

        if self._trading_paused:
            risk_score += 2

        if risk_score >= 8:
            return RiskLevel.CRITICAL
        elif risk_score >= 6:
            return RiskLevel.EXTREME
        elif risk_score >= 4:
            return RiskLevel.HIGH
        elif risk_score >= 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _record_snapshot(self):
        """Record a risk snapshot for history."""
        snapshot = self.get_risk_snapshot()
        self._risk_history.append(snapshot)

        # Trim history
        if len(self._risk_history) > self._max_history_size:
            self._risk_history = self._risk_history[-self._max_history_size :]

    def get_risk_history(self, limit: int = 100) -> list[PortfolioRiskSnapshot]:
        """Get recent risk history."""
        return self._risk_history[-limit:]

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive risk engine status."""
        snapshot = self.get_risk_snapshot()

        return {
            "status": "active" if self._is_running else "inactive",
            "trading_allowed": self.is_trading_allowed(),
            "trading_paused": self._trading_paused,
            "pause_reason": self._pause_reason,
            "current_snapshot": snapshot.to_dict(),
            "config": {
                "sizing_method": self.config.sizing_method.value,
                "risk_per_trade_pct": self.config.risk_per_trade_pct,
                "max_position_size_pct": self.config.max_position_size_pct,
                "max_leverage": self.config.max_leverage,
                "max_drawdown_pct": self.config.max_drawdown_pct,
                "daily_loss_limit_pct": self.config.daily_loss_limit_pct,
            },
            "components": {
                "position_sizer": "active",
                "stop_loss_manager": {
                    "active_stops": len(self.stop_loss_manager.get_active_stops())
                },
                "exposure_controller": {
                    "positions": len(self.exposure_controller.positions),
                    "exposure_pct": self.exposure_controller.get_current_exposure().get(
                        "total_exposure_pct", 0
                    ),
                },
                "trade_validator": self.trade_validator.get_stats(),
            },
        }

    async def start(self):
        """Start the risk engine."""
        self._is_running = True
        logger.info("RiskEngine started")

    async def stop(self):
        """Stop the risk engine."""
        self._is_running = False
        logger.info("RiskEngine stopped")


# Factory functions for common configurations


def create_conservative_risk_engine(equity: float = 10000.0) -> RiskEngine:
    """Create a conservative risk engine."""
    config = RiskEngineConfig(
        initial_equity=equity,
        sizing_method=SizingMethod.FIXED_PERCENTAGE,
        risk_per_trade_pct=0.5,
        max_position_size_pct=5.0,
        default_stop_pct=1.5,
        max_total_exposure_pct=50.0,
        max_leverage=2.0,
        max_drawdown_pct=10.0,
        daily_loss_limit_pct=2.0,
        min_risk_reward=1.5,
    )
    return RiskEngine(config)


def create_moderate_risk_engine(equity: float = 10000.0) -> RiskEngine:
    """Create a moderate risk engine."""
    config = RiskEngineConfig(
        initial_equity=equity,
        sizing_method=SizingMethod.VOLATILITY_BASED,
        risk_per_trade_pct=1.0,
        max_position_size_pct=10.0,
        default_stop_pct=2.0,
        max_total_exposure_pct=80.0,
        max_leverage=5.0,
        max_drawdown_pct=15.0,
        daily_loss_limit_pct=5.0,
        min_risk_reward=1.0,
    )
    return RiskEngine(config)


def create_aggressive_risk_engine(equity: float = 10000.0) -> RiskEngine:
    """Create an aggressive risk engine."""
    config = RiskEngineConfig(
        initial_equity=equity,
        sizing_method=SizingMethod.KELLY_CRITERION,
        risk_per_trade_pct=2.0,
        max_position_size_pct=20.0,
        default_stop_pct=3.0,
        max_total_exposure_pct=100.0,
        max_leverage=10.0,
        max_drawdown_pct=25.0,
        daily_loss_limit_pct=10.0,
        min_risk_reward=0.5,
    )
    return RiskEngine(config)
