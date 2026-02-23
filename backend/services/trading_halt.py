"""
Trading Halt Service.

Provides emergency trading halt mechanisms with:
- Emergency stop functionality
- Position limit enforcement
- Loss threshold monitoring
- Automated halt triggers
- Manual override capabilities
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HaltReason(str, Enum):
    """Reasons for trading halt."""

    MANUAL = "manual"
    LOSS_THRESHOLD = "loss_threshold"
    POSITION_LIMIT = "position_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    VOLATILITY = "volatility"
    API_ERROR = "api_error"
    SYSTEM_ERROR = "system_error"
    MAINTENANCE = "maintenance"
    CIRCUIT_BREAKER = "circuit_breaker"
    RISK_LIMIT = "risk_limit"


class HaltLevel(str, Enum):
    """Severity level of trading halt."""

    SOFT = "soft"  # Warning, allows manual override
    HARD = "hard"  # Blocks new positions, allows closing
    EMERGENCY = "emergency"  # Blocks all trading, force close positions


class TradingStatus(str, Enum):
    """Current trading status."""

    ACTIVE = "active"
    HALTED = "halted"
    LIMITED = "limited"
    CLOSING_ONLY = "closing_only"


@dataclass
class HaltConfig:
    """Configuration for trading halt triggers."""

    # Loss thresholds
    max_daily_loss_pct: float = 5.0  # Max daily loss as % of equity
    max_weekly_loss_pct: float = 10.0  # Max weekly loss as % of equity
    max_trade_loss_pct: float = 2.0  # Max loss per trade as % of equity

    # Drawdown limits
    max_drawdown_pct: float = 15.0  # Max drawdown from peak

    # Position limits
    max_open_positions: int = 10
    max_position_size_pct: float = 20.0  # Max position as % of equity
    max_total_exposure_pct: float = 100.0  # Max total exposure

    # Volatility triggers
    volatility_threshold: float = 3.0  # Std deviations for volatility halt

    # Recovery settings
    auto_recovery_enabled: bool = True
    recovery_cooldown_minutes: int = 30


@dataclass
class HaltEvent:
    """Record of a halt event."""

    id: str
    reason: HaltReason
    level: HaltLevel
    timestamp: datetime
    triggered_by: str  # System, user, or automatic
    details: dict = field(default_factory=dict)
    resolved_at: datetime | None = None
    resolved_by: str | None = None


@dataclass
class TradingState:
    """Current trading state."""

    status: TradingStatus
    halt_level: HaltLevel | None
    halt_reason: HaltReason | None
    halted_at: datetime | None
    halted_by: str | None
    resume_at: datetime | None
    message: str = ""


@dataclass
class RiskMetrics:
    """Current risk metrics for halt decisions."""

    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    weekly_pnl: float = 0.0
    weekly_pnl_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    open_positions: int = 0
    total_exposure: float = 0.0
    total_exposure_pct: float = 0.0
    largest_position_pct: float = 0.0


class TradingHaltService:
    """
    Trading Halt Service for emergency stop functionality.

    Features:
    - Manual emergency stop
    - Automated halt triggers (loss, drawdown, position limits)
    - Gradual halt levels (soft, hard, emergency)
    - Recovery mechanisms with cooldown
    - Audit trail of all halt events
    """

    def __init__(self, config: HaltConfig | None = None):
        self._config = config or HaltConfig()
        self._state = TradingState(
            status=TradingStatus.ACTIVE,
            halt_level=None,
            halt_reason=None,
            halted_at=None,
            halted_by=None,
            resume_at=None,
        )
        self._events: list[HaltEvent] = []
        self._risk_metrics = RiskMetrics()
        self._event_counter = 0
        self._initialized = False
        self._lock = asyncio.Lock()
        self._halt_callbacks: list[Callable[[HaltEvent], None]] = []
        self._resume_callbacks: list[Callable[[str], None]] = []
        self._initialized = True
        logger.info("✅ Trading Halt Service initialized")

    # ============================================================
    # Emergency Stop Controls
    # ============================================================

    async def emergency_stop(
        self,
        reason: str = "Manual emergency stop",
        triggered_by: str = "system",
    ) -> HaltEvent:
        """
        Immediately halt all trading (EMERGENCY level).

        This is the most severe halt - blocks all trading activity.
        """
        async with self._lock:
            event = self._create_halt_event(
                reason=HaltReason.MANUAL,
                level=HaltLevel.EMERGENCY,
                triggered_by=triggered_by,
                details={"message": reason},
            )

            self._state = TradingState(
                status=TradingStatus.HALTED,
                halt_level=HaltLevel.EMERGENCY,
                halt_reason=HaltReason.MANUAL,
                halted_at=event.timestamp,
                halted_by=triggered_by,
                resume_at=None,
                message=reason,
            )

            self._events.append(event)
            await self._notify_halt(event)

            logger.warning(f"🚨 EMERGENCY STOP activated by {triggered_by}: {reason}")

            return event

    async def halt_trading(
        self,
        reason: HaltReason,
        level: HaltLevel = HaltLevel.HARD,
        triggered_by: str = "system",
        duration_minutes: int | None = None,
        details: dict | None = None,
    ) -> HaltEvent:
        """
        Halt trading with specified level and reason.

        Args:
            reason: Reason for the halt
            level: Severity level
            triggered_by: Who/what triggered the halt
            duration_minutes: Optional auto-resume after duration
            details: Additional details about the halt

        Returns:
            HaltEvent record
        """
        async with self._lock:
            resume_at = None
            if duration_minutes and self._config.auto_recovery_enabled:
                resume_at = datetime.now(UTC) + timedelta(
                    minutes=duration_minutes
                )

            event = self._create_halt_event(
                reason=reason,
                level=level,
                triggered_by=triggered_by,
                details=details or {},
            )

            # Determine status based on level
            status = TradingStatus.HALTED
            if level == HaltLevel.SOFT:
                status = TradingStatus.LIMITED
            elif level == HaltLevel.HARD:
                status = TradingStatus.CLOSING_ONLY

            self._state = TradingState(
                status=status,
                halt_level=level,
                halt_reason=reason,
                halted_at=event.timestamp,
                halted_by=triggered_by,
                resume_at=resume_at,
                message=f"{reason.value}: {details.get('message', '')}"
                if details
                else reason.value,
            )

            self._events.append(event)
            await self._notify_halt(event)

            logger.warning(
                f"⚠️ Trading halted [{level.value}]: {reason.value} by {triggered_by}"
            )

            return event

    async def resume_trading(
        self,
        resumed_by: str = "system",
        force: bool = False,
    ) -> bool:
        """
        Resume trading after a halt.

        Args:
            resumed_by: Who is resuming trading
            force: Force resume even during cooldown

        Returns:
            True if resumed successfully
        """
        async with self._lock:
            if self._state.status == TradingStatus.ACTIVE:
                return True  # Already active

            # Check cooldown
            if not force and self._state.halted_at:
                cooldown_end = self._state.halted_at + timedelta(
                    minutes=self._config.recovery_cooldown_minutes
                )
                if datetime.now(UTC) < cooldown_end:
                    logger.warning(
                        f"⏳ Resume blocked - cooldown active until {cooldown_end}"
                    )
                    return False

            # Mark last event as resolved
            if self._events:
                self._events[-1].resolved_at = datetime.now(UTC)
                self._events[-1].resolved_by = resumed_by

            self._state = TradingState(
                status=TradingStatus.ACTIVE,
                halt_level=None,
                halt_reason=None,
                halted_at=None,
                halted_by=None,
                resume_at=None,
                message="Trading resumed",
            )

            await self._notify_resume(resumed_by)

            logger.info(f"✅ Trading resumed by {resumed_by}")
            return True

    # ============================================================
    # Trade Validation
    # ============================================================

    def can_open_position(self) -> tuple[bool, str]:
        """Check if new positions can be opened."""
        if self._state.status == TradingStatus.HALTED:
            return False, f"Trading halted: {self._state.message}"

        if self._state.status == TradingStatus.CLOSING_ONLY:
            return False, "Only closing positions allowed"

        if self._state.status == TradingStatus.LIMITED:
            # Soft halt - check additional conditions
            if self._risk_metrics.open_positions >= self._config.max_open_positions:
                return (
                    False,
                    f"Position limit reached ({self._config.max_open_positions})",
                )

        return True, "OK"

    def can_close_position(self) -> tuple[bool, str]:
        """Check if positions can be closed."""
        if self._state.status == TradingStatus.HALTED and self._state.halt_level == HaltLevel.EMERGENCY:
            return False, "Emergency halt - all trading blocked"
        return True, "OK"

    def validate_trade(
        self,
        trade_type: str,  # "open" or "close"
        position_size: float,
        current_equity: float,
    ) -> tuple[bool, str]:
        """
        Validate if a trade is allowed.

        Args:
            trade_type: "open" or "close"
            position_size: Size of the position
            current_equity: Current account equity

        Returns:
            Tuple of (allowed, reason)
        """
        if trade_type == "close":
            return self.can_close_position()

        can_open, reason = self.can_open_position()
        if not can_open:
            return False, reason

        # Check position size limit
        if current_equity > 0:
            position_pct = (position_size / current_equity) * 100
            if position_pct > self._config.max_position_size_pct:
                return (
                    False,
                    f"Position size {position_pct:.1f}% exceeds limit {self._config.max_position_size_pct}%",
                )

        return True, "OK"

    # ============================================================
    # Risk Monitoring & Auto-Halt
    # ============================================================

    async def update_risk_metrics(self, metrics: RiskMetrics) -> HaltEvent | None:
        """
        Update risk metrics and check for auto-halt triggers.

        Args:
            metrics: Current risk metrics

        Returns:
            HaltEvent if halt was triggered, None otherwise
        """
        self._risk_metrics = metrics

        # Check daily loss threshold
        if abs(metrics.daily_pnl_pct) >= self._config.max_daily_loss_pct:
            return await self.halt_trading(
                reason=HaltReason.LOSS_THRESHOLD,
                level=HaltLevel.HARD,
                triggered_by="risk_monitor",
                duration_minutes=self._config.recovery_cooldown_minutes,
                details={
                    "message": f"Daily loss {metrics.daily_pnl_pct:.2f}% exceeded limit",
                    "daily_pnl_pct": metrics.daily_pnl_pct,
                    "limit": self._config.max_daily_loss_pct,
                },
            )

        # Check drawdown threshold
        if metrics.current_drawdown_pct >= self._config.max_drawdown_pct:
            return await self.halt_trading(
                reason=HaltReason.DRAWDOWN_LIMIT,
                level=HaltLevel.HARD,
                triggered_by="risk_monitor",
                details={
                    "message": f"Drawdown {metrics.current_drawdown_pct:.2f}% exceeded limit",
                    "drawdown_pct": metrics.current_drawdown_pct,
                    "limit": self._config.max_drawdown_pct,
                },
            )

        # Check position limit
        if metrics.open_positions > self._config.max_open_positions:
            return await self.halt_trading(
                reason=HaltReason.POSITION_LIMIT,
                level=HaltLevel.SOFT,
                triggered_by="risk_monitor",
                details={
                    "message": f"Open positions {metrics.open_positions} exceeded limit",
                    "positions": metrics.open_positions,
                    "limit": self._config.max_open_positions,
                },
            )

        # Check total exposure
        if metrics.total_exposure_pct > self._config.max_total_exposure_pct:
            return await self.halt_trading(
                reason=HaltReason.RISK_LIMIT,
                level=HaltLevel.SOFT,
                triggered_by="risk_monitor",
                details={
                    "message": f"Total exposure {metrics.total_exposure_pct:.2f}% exceeded limit",
                    "exposure_pct": metrics.total_exposure_pct,
                    "limit": self._config.max_total_exposure_pct,
                },
            )

        return None

    # ============================================================
    # Event Management
    # ============================================================

    def _create_halt_event(
        self,
        reason: HaltReason,
        level: HaltLevel,
        triggered_by: str,
        details: dict,
    ) -> HaltEvent:
        """Create a new halt event."""
        self._event_counter += 1
        return HaltEvent(
            id=f"HALT-{self._event_counter:06d}",
            reason=reason,
            level=level,
            timestamp=datetime.now(UTC),
            triggered_by=triggered_by,
            details=details,
        )

    async def _notify_halt(self, event: HaltEvent) -> None:
        """Notify registered callbacks about halt."""
        for callback in self._halt_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Halt callback error: {e}")

    async def _notify_resume(self, resumed_by: str) -> None:
        """Notify registered callbacks about resume."""
        for callback in self._resume_callbacks:
            try:
                callback(resumed_by)
            except Exception as e:
                logger.error(f"Resume callback error: {e}")

    def register_halt_callback(self, callback: Callable[[HaltEvent], None]) -> None:
        """Register a callback for halt events."""
        self._halt_callbacks.append(callback)

    def register_resume_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback for resume events."""
        self._resume_callbacks.append(callback)

    # ============================================================
    # Status & Reporting
    # ============================================================

    def get_status(self) -> dict:
        """Get current trading halt status."""
        return {
            "trading_status": self._state.status.value,
            "halt_level": self._state.halt_level.value
            if self._state.halt_level
            else None,
            "halt_reason": self._state.halt_reason.value
            if self._state.halt_reason
            else None,
            "halted_at": self._state.halted_at.isoformat()
            if self._state.halted_at
            else None,
            "halted_by": self._state.halted_by,
            "resume_at": self._state.resume_at.isoformat()
            if self._state.resume_at
            else None,
            "message": self._state.message,
            "can_open_positions": self.can_open_position()[0],
            "can_close_positions": self.can_close_position()[0],
        }

    def get_config(self) -> dict:
        """Get current halt configuration."""
        return {
            "max_daily_loss_pct": self._config.max_daily_loss_pct,
            "max_weekly_loss_pct": self._config.max_weekly_loss_pct,
            "max_trade_loss_pct": self._config.max_trade_loss_pct,
            "max_drawdown_pct": self._config.max_drawdown_pct,
            "max_open_positions": self._config.max_open_positions,
            "max_position_size_pct": self._config.max_position_size_pct,
            "max_total_exposure_pct": self._config.max_total_exposure_pct,
            "volatility_threshold": self._config.volatility_threshold,
            "auto_recovery_enabled": self._config.auto_recovery_enabled,
            "recovery_cooldown_minutes": self._config.recovery_cooldown_minutes,
        }

    def update_config(self, **kwargs: Any) -> dict:
        """Update halt configuration."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
                logger.info(f"📝 Updated halt config: {key} = {value}")
        return self.get_config()

    def get_events(
        self,
        limit: int = 50,
        include_resolved: bool = True,
    ) -> list[dict]:
        """Get halt event history."""
        events = self._events
        if not include_resolved:
            events = [e for e in events if e.resolved_at is None]

        return [
            {
                "id": e.id,
                "reason": e.reason.value,
                "level": e.level.value,
                "timestamp": e.timestamp.isoformat(),
                "triggered_by": e.triggered_by,
                "details": e.details,
                "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
                "resolved_by": e.resolved_by,
            }
            for e in events[-limit:]
        ]

    def get_risk_metrics(self) -> dict:
        """Get current risk metrics."""
        return {
            "daily_pnl": self._risk_metrics.daily_pnl,
            "daily_pnl_pct": self._risk_metrics.daily_pnl_pct,
            "weekly_pnl": self._risk_metrics.weekly_pnl,
            "weekly_pnl_pct": self._risk_metrics.weekly_pnl_pct,
            "current_drawdown_pct": self._risk_metrics.current_drawdown_pct,
            "peak_equity": self._risk_metrics.peak_equity,
            "current_equity": self._risk_metrics.current_equity,
            "open_positions": self._risk_metrics.open_positions,
            "total_exposure": self._risk_metrics.total_exposure,
            "total_exposure_pct": self._risk_metrics.total_exposure_pct,
            "largest_position_pct": self._risk_metrics.largest_position_pct,
        }


# Singleton instance
_trading_halt_service: TradingHaltService | None = None


def get_trading_halt_service() -> TradingHaltService:
    """Get or create trading halt service instance."""
    global _trading_halt_service
    if _trading_halt_service is None:
        _trading_halt_service = TradingHaltService()
        logger.info("🛑 Trading Halt Service initialized")
    return _trading_halt_service
