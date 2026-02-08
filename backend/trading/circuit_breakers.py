"""
Trading Circuit Breakers
=========================
Защита от катастрофических потерь в trading операциях

Features:
- Loss-based circuit breaker (стоп при достижении лимита убытков)
- Volume-based circuit breaker (ограничение объема торгов)
- Time-based circuit breaker (охлаждение после активации)
- Emergency halt mechanism (полная остановка торговли)
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Trading halted
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""

    # Loss limits
    max_loss_percent: float = 5.0  # Max 5% portfolio loss
    max_loss_absolute: float = 1000.0  # Max $1000 loss

    # Volume limits
    max_trades_per_minute: int = 10
    max_volume_per_hour: float = 10000.0  # $10k

    # Time limits
    cooldown_seconds: int = 300  # 5 minutes cooldown
    recovery_test_trades: int = 3  # Trades to test recovery

    # Emergency
    emergency_stop_loss_percent: float = 10.0  # Emergency at 10%


@dataclass
class TradingMetrics:
    """Current trading metrics"""

    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_profit_loss: float = 0.0
    current_position_value: float = 0.0
    initial_portfolio_value: float = 10000.0

    # Rolling windows
    trades_last_minute: int = 0
    volume_last_hour: float = 0.0

    # Timestamps
    last_trade_time: datetime | None = None
    circuit_opened_at: datetime | None = None


class TradingCircuitBreaker:
    """
    Circuit breaker для trading operations

    Monitors trading activity and halts operations if limits exceeded
    """

    def __init__(self, config: CircuitBreakerConfig = None):
        """Initialize circuit breaker"""
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.metrics = TradingMetrics()
        self.recovery_test_count = 0

        logger.info(f"Trading Circuit Breaker initialized: {self.config}")

    def _calculate_loss_percent(self) -> float:
        """Calculate current loss percentage"""
        current_value = (
            self.metrics.initial_portfolio_value + self.metrics.total_profit_loss
        )
        loss = self.metrics.initial_portfolio_value - current_value
        return (loss / self.metrics.initial_portfolio_value) * 100

    def _check_loss_limits(self) -> tuple[bool, str]:
        """Check if loss limits exceeded"""
        loss_percent = self._calculate_loss_percent()
        loss_absolute = abs(self.metrics.total_profit_loss)

        # Emergency stop
        if loss_percent >= self.config.emergency_stop_loss_percent:
            return False, f"EMERGENCY: Loss {loss_percent:.2f}% exceeds emergency limit"

        # Regular limits
        if loss_percent >= self.config.max_loss_percent:
            return (
                False,
                f"Loss {loss_percent:.2f}% exceeds limit {self.config.max_loss_percent}%",
            )

        if loss_absolute >= self.config.max_loss_absolute:
            return (
                False,
                f"Absolute loss ${loss_absolute:.2f} exceeds limit ${self.config.max_loss_absolute}",
            )

        return True, ""

    def _check_volume_limits(self) -> tuple[bool, str]:
        """Check if volume limits exceeded"""
        if self.metrics.trades_last_minute >= self.config.max_trades_per_minute:
            return (
                False,
                f"Trades/minute {self.metrics.trades_last_minute} exceeds limit",
            )

        if self.metrics.volume_last_hour >= self.config.max_volume_per_hour:
            return (
                False,
                f"Volume/hour ${self.metrics.volume_last_hour:.2f} exceeds limit",
            )

        return True, ""

    def _check_cooldown(self) -> bool:
        """Check if cooldown period has passed"""
        if self.metrics.circuit_opened_at is None:
            return True

        elapsed = (datetime.now() - self.metrics.circuit_opened_at).total_seconds()
        return elapsed >= self.config.cooldown_seconds

    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed

        Returns:
            (allowed, reason)
        """
        if self.state == CircuitBreakerState.OPEN:
            if not self._check_cooldown():
                remaining = (
                    self.config.cooldown_seconds
                    - (datetime.now() - self.metrics.circuit_opened_at).total_seconds()
                )
                return (
                    False,
                    f"Circuit breaker OPEN - cooldown {remaining:.0f}s remaining",
                )
            else:
                # Move to half-open for testing
                self.state = CircuitBreakerState.HALF_OPEN
                self.recovery_test_count = 0
                logger.info("Circuit breaker moved to HALF_OPEN for recovery testing")

        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.recovery_test_count >= self.config.recovery_test_trades:
                self.state = CircuitBreakerState.CLOSED
                logger.info("Circuit breaker CLOSED - recovery successful")
            else:
                logger.info(
                    f"Recovery test: {self.recovery_test_count}/{self.config.recovery_test_trades}"
                )

        # Check limits
        loss_ok, loss_reason = self._check_loss_limits()
        if not loss_ok:
            self._open_circuit(loss_reason)
            return False, loss_reason

        volume_ok, volume_reason = self._check_volume_limits()
        if not volume_ok:
            self._open_circuit(volume_reason)
            return False, volume_reason

        return True, "Trading allowed"

    def _open_circuit(self, reason: str):
        """Open circuit breaker"""
        if self.state != CircuitBreakerState.OPEN:
            self.state = CircuitBreakerState.OPEN
            self.metrics.circuit_opened_at = datetime.now()
            logger.warning(f"🔴 CIRCUIT BREAKER OPENED: {reason}")

            # Send alert notifications
            self._send_alert(reason, severity="warning")

    def _send_alert(self, reason: str, severity: str = "warning"):
        """Send alert notification via alerting service"""
        try:
            from backend.services.alerting import (
                Alert,
                AlertSeverity,
                get_alert_service,
            )

            alert_service = get_alert_service()
            severity_map = {
                "info": AlertSeverity.INFO,
                "warning": AlertSeverity.WARNING,
                "critical": AlertSeverity.CRITICAL,
            }

            alert = Alert(
                title=f"Trading Circuit Breaker {severity.upper()}",
                message=reason,
                severity=severity_map.get(severity, AlertSeverity.WARNING),
                source="trading_circuit_breaker",
                metadata={
                    "state": self.state.value,
                    "total_trades": self.metrics.total_trades,
                    "total_profit_loss": self.metrics.total_profit_loss,
                    "opened_at": self.metrics.circuit_opened_at.isoformat()
                    if self.metrics.circuit_opened_at
                    else None,
                },
            )

            # Fire and forget async alert
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(alert_service.send_alert(alert))
            except RuntimeError:
                # No event loop - log only
                logger.info(f"Alert would be sent: {alert.title} - {alert.message}")

        except ImportError:
            logger.debug("Alerting service not available")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    def record_trade(
        self,
        success: bool,
        profit_loss: float,
        volume: float,
        correlation_id: str | None = None,
    ):
        """
        Record trade execution

        Args:
            success: Whether trade was successful
            profit_loss: Profit/loss amount
            volume: Trade volume
            correlation_id: Request correlation ID
        """
        self.metrics.total_trades += 1

        if success:
            self.metrics.successful_trades += 1
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.recovery_test_count += 1
        else:
            self.metrics.failed_trades += 1

        self.metrics.total_profit_loss += profit_loss
        self.metrics.last_trade_time = datetime.now()

        # Update rolling windows (simplified)
        self.metrics.trades_last_minute += 1
        self.metrics.volume_last_hour += abs(volume)

        logger.info(
            f"Trade recorded: success={success}, P/L=${profit_loss:.2f}, "
            f"volume=${volume:.2f}, state={self.state}",
            extra={"correlation_id": correlation_id or "N/A"},
        )

    def emergency_halt(self, reason: str):
        """
        Emergency halt of all trading

        Args:
            reason: Reason for emergency halt
        """
        self.state = CircuitBreakerState.OPEN
        self.metrics.circuit_opened_at = datetime.now()

        logger.critical(f"🚨 EMERGENCY HALT: {reason}")

        # Send critical alerts
        self._send_alert(reason, severity="critical")

    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        loss_percent = self._calculate_loss_percent()

        return {
            "state": self.state.value,
            "metrics": {
                "total_trades": self.metrics.total_trades,
                "success_rate": (
                    self.metrics.successful_trades / self.metrics.total_trades * 100
                    if self.metrics.total_trades > 0
                    else 0
                ),
                "total_profit_loss": self.metrics.total_profit_loss,
                "loss_percent": loss_percent,
                "trades_last_minute": self.metrics.trades_last_minute,
                "volume_last_hour": self.metrics.volume_last_hour,
            },
            "limits": {
                "max_loss_percent": self.config.max_loss_percent,
                "max_loss_absolute": self.config.max_loss_absolute,
                "max_trades_per_minute": self.config.max_trades_per_minute,
                "max_volume_per_hour": self.config.max_volume_per_hour,
            },
            "can_trade": self.can_trade()[0],
        }


# Global circuit breaker instance
_circuit_breaker: TradingCircuitBreaker | None = None


def get_trading_circuit_breaker() -> TradingCircuitBreaker:
    """Get global trading circuit breaker"""
    global _circuit_breaker

    if _circuit_breaker is None:
        _circuit_breaker = TradingCircuitBreaker()

    return _circuit_breaker


# Decorator для защиты trading endpoints
def protected_trading_endpoint(func: Callable):
    """Decorator для автоматической проверки circuit breaker"""

    async def wrapper(*args, **kwargs):
        breaker = get_trading_circuit_breaker()
        allowed, reason = breaker.can_trade()

        if not allowed:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Trading halted by circuit breaker",
                    "reason": reason,
                    "status": breaker.get_status(),
                },
            )

        return await func(*args, **kwargs)

    return wrapper
