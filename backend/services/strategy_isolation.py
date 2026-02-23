"""
Strategy Isolation Framework

DeepSeek Recommendation: Deploy strategy isolation framework
- Separate execution environments per strategy
- Independent risk limits per strategy
- Fault containment to prevent cascade failures
- Resource quotas and monitoring

Created: 2025-12-21
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class IsolationLevel(str, Enum):
    """Strategy isolation levels"""

    NONE = "none"  # No isolation (legacy mode)
    SOFT = "soft"  # Logical isolation (shared resources, separate accounting)
    HARD = "hard"  # Strong isolation (separate resource pools)
    CONTAINER = "container"  # Full container isolation (future)


class StrategyState(str, Enum):
    """Strategy execution state"""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    COOLDOWN = "cooldown"


@dataclass
class ResourceQuota:
    """Resource limits for a strategy"""

    max_memory_mb: float = 512.0  # Maximum memory usage
    max_cpu_percent: float = 25.0  # Maximum CPU usage
    max_concurrent_trades: int = 10  # Maximum simultaneous open trades
    max_position_size_usdt: float = 10000.0  # Maximum position size
    max_daily_trades: int = 100  # Maximum trades per day
    max_daily_loss_usdt: float = 500.0  # Maximum daily loss (circuit breaker)
    max_drawdown_percent: float = 20.0  # Maximum drawdown before pause
    api_rate_limit_per_minute: int = 60  # API calls per minute

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "max_concurrent_trades": self.max_concurrent_trades,
            "max_position_size_usdt": self.max_position_size_usdt,
            "max_daily_trades": self.max_daily_trades,
            "max_daily_loss_usdt": self.max_daily_loss_usdt,
            "max_drawdown_percent": self.max_drawdown_percent,
            "api_rate_limit_per_minute": self.api_rate_limit_per_minute,
        }


@dataclass
class ResourceUsage:
    """Current resource usage for a strategy"""

    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    open_trades: int = 0
    current_position_usdt: float = 0.0
    daily_trade_count: int = 0
    daily_pnl_usdt: float = 0.0
    current_drawdown_percent: float = 0.0
    api_calls_last_minute: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_mb": self.memory_mb,
            "cpu_percent": self.cpu_percent,
            "open_trades": self.open_trades,
            "current_position_usdt": self.current_position_usdt,
            "daily_trade_count": self.daily_trade_count,
            "daily_pnl_usdt": self.daily_pnl_usdt,
            "current_drawdown_percent": self.current_drawdown_percent,
            "api_calls_last_minute": self.api_calls_last_minute,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class StrategyContext:
    """Isolated execution context for a strategy"""

    strategy_id: str
    strategy_name: str
    isolation_level: IsolationLevel
    state: StrategyState
    quota: ResourceQuota
    usage: ResourceUsage

    # Execution tracking
    started_at: datetime | None = None
    last_trade_at: datetime | None = None
    last_error: str | None = None
    error_count: int = 0
    trade_count_total: int = 0
    total_pnl_usdt: float = 0.0
    peak_equity_usdt: float = 0.0

    # Circuit breaker state
    circuit_breaker_triggered: bool = False
    circuit_breaker_reason: str | None = None
    circuit_breaker_triggered_at: datetime | None = None
    cooldown_until: datetime | None = None

    # Callbacks
    on_limit_breach: Callable | None = field(default=None, repr=False)
    on_state_change: Callable | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "isolation_level": self.isolation_level.value,
            "state": self.state.value,
            "quota": self.quota.to_dict(),
            "usage": self.usage.to_dict(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_trade_at": self.last_trade_at.isoformat()
            if self.last_trade_at
            else None,
            "last_error": self.last_error,
            "error_count": self.error_count,
            "trade_count_total": self.trade_count_total,
            "total_pnl_usdt": self.total_pnl_usdt,
            "peak_equity_usdt": self.peak_equity_usdt,
            "circuit_breaker": {
                "triggered": self.circuit_breaker_triggered,
                "reason": self.circuit_breaker_reason,
                "triggered_at": self.circuit_breaker_triggered_at.isoformat()
                if self.circuit_breaker_triggered_at
                else None,
                "cooldown_until": self.cooldown_until.isoformat()
                if self.cooldown_until
                else None,
            },
        }


class QuotaViolation(Exception):
    """Raised when a strategy exceeds its quota"""

    def __init__(self, strategy_id: str, quota_type: str, current: float, limit: float):
        self.strategy_id = strategy_id
        self.quota_type = quota_type
        self.current = current
        self.limit = limit
        super().__init__(
            f"Strategy {strategy_id} exceeded {quota_type}: {current} > {limit}"
        )


class StrategyIsolationManager:
    """
    Manages isolated execution environments for trading strategies.

    Features:
    - Resource quota enforcement
    - Fault isolation
    - Circuit breaker per strategy
    - Independent risk limits
    - Monitoring and alerting
    """

    def __init__(
        self,
        default_quota: ResourceQuota | None = None,
        default_isolation_level: IsolationLevel = IsolationLevel.SOFT,
        enable_monitoring: bool = True,
        monitoring_interval_seconds: float = 5.0,
    ):
        self.default_quota = default_quota or ResourceQuota()
        self.default_isolation_level = default_isolation_level
        self.enable_monitoring = enable_monitoring
        self.monitoring_interval = monitoring_interval_seconds

        self._contexts: dict[str, StrategyContext] = {}
        self._lock = asyncio.Lock()
        self._monitoring_task: asyncio.Task | None = None
        self._running = False

        # Event handlers
        self._on_quota_violation: list[Callable] = []
        self._on_circuit_breaker: list[Callable] = []
        self._on_state_change: list[Callable] = []

        logger.info(
            f"StrategyIsolationManager initialized with "
            f"isolation_level={default_isolation_level.value}"
        )

    async def start(self) -> None:
        """Start the isolation manager"""
        self._running = True
        if self.enable_monitoring:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("StrategyIsolationManager started")

    async def stop(self) -> None:
        """Stop the isolation manager"""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._monitoring_task
        logger.info("StrategyIsolationManager stopped")

    async def register_strategy(
        self,
        strategy_name: str,
        strategy_id: str | None = None,
        quota: ResourceQuota | None = None,
        isolation_level: IsolationLevel | None = None,
    ) -> StrategyContext:
        """
        Register a new strategy with isolated execution context.

        Args:
            strategy_name: Human-readable strategy name
            strategy_id: Unique ID (auto-generated if not provided)
            quota: Resource quota (uses default if not provided)
            isolation_level: Isolation level (uses default if not provided)

        Returns:
            StrategyContext for the registered strategy
        """
        async with self._lock:
            sid = strategy_id or f"strategy_{uuid.uuid4().hex[:8]}"

            if sid in self._contexts:
                logger.warning(f"Strategy {sid} already registered, returning existing")
                return self._contexts[sid]

            context = StrategyContext(
                strategy_id=sid,
                strategy_name=strategy_name,
                isolation_level=isolation_level or self.default_isolation_level,
                state=StrategyState.IDLE,
                quota=quota or ResourceQuota(**self.default_quota.__dict__),
                usage=ResourceUsage(),
            )

            self._contexts[sid] = context
            logger.info(f"Registered strategy: {sid} ({strategy_name})")

            return context

    async def unregister_strategy(self, strategy_id: str) -> bool:
        """Unregister a strategy and release its resources"""
        async with self._lock:
            if strategy_id not in self._contexts:
                return False

            context = self._contexts[strategy_id]

            # Ensure strategy is stopped
            if context.state == StrategyState.RUNNING:
                context.state = StrategyState.STOPPED
                await self._notify_state_change(context, StrategyState.RUNNING)

            del self._contexts[strategy_id]
            logger.info(f"Unregistered strategy: {strategy_id}")

            return True

    def get_context(self, strategy_id: str) -> StrategyContext | None:
        """Get strategy context by ID"""
        return self._contexts.get(strategy_id)

    def list_strategies(self) -> list[StrategyContext]:
        """List all registered strategies"""
        return list(self._contexts.values())

    async def start_strategy(self, strategy_id: str) -> bool:
        """Start strategy execution"""
        context = self._contexts.get(strategy_id)
        if not context:
            return False

        if context.state == StrategyState.RUNNING:
            return True

        # Check cooldown
        if (
            context.cooldown_until
            and datetime.now(UTC) < context.cooldown_until
        ):
            logger.warning(
                f"Strategy {strategy_id} is in cooldown until {context.cooldown_until}"
            )
            return False

        # Reset circuit breaker if was triggered
        if context.circuit_breaker_triggered:
            context.circuit_breaker_triggered = False
            context.circuit_breaker_reason = None
            context.circuit_breaker_triggered_at = None

        old_state = context.state
        context.state = StrategyState.RUNNING
        context.started_at = datetime.now(UTC)

        await self._notify_state_change(context, old_state)
        logger.info(f"Started strategy: {strategy_id}")

        return True

    async def stop_strategy(self, strategy_id: str, reason: str = "manual") -> bool:
        """Stop strategy execution"""
        context = self._contexts.get(strategy_id)
        if not context:
            return False

        old_state = context.state
        context.state = StrategyState.STOPPED

        await self._notify_state_change(context, old_state)
        logger.info(f"Stopped strategy: {strategy_id} (reason: {reason})")

        return True

    async def pause_strategy(self, strategy_id: str, reason: str = "manual") -> bool:
        """Pause strategy execution"""
        context = self._contexts.get(strategy_id)
        if not context:
            return False

        old_state = context.state
        context.state = StrategyState.PAUSED

        await self._notify_state_change(context, old_state)
        logger.info(f"Paused strategy: {strategy_id} (reason: {reason})")

        return True

    async def check_quota(
        self,
        strategy_id: str,
        trade_size_usdt: float | None = None,
    ) -> tuple[bool, str | None]:
        """
        Check if strategy is within quota limits.

        Returns:
            Tuple of (is_allowed, violation_reason)
        """
        context = self._contexts.get(strategy_id)
        if not context:
            return False, "Strategy not found"

        quota = context.quota
        usage = context.usage

        # Check daily trade count
        if usage.daily_trade_count >= quota.max_daily_trades:
            return False, f"Daily trade limit reached ({quota.max_daily_trades})"

        # Check daily loss limit
        if usage.daily_pnl_usdt <= -quota.max_daily_loss_usdt:
            return False, f"Daily loss limit reached (${quota.max_daily_loss_usdt})"

        # Check drawdown
        if usage.current_drawdown_percent >= quota.max_drawdown_percent:
            return False, f"Max drawdown reached ({quota.max_drawdown_percent}%)"

        # Check concurrent trades
        if usage.open_trades >= quota.max_concurrent_trades:
            return (
                False,
                f"Max concurrent trades reached ({quota.max_concurrent_trades})",
            )

        # Check position size
        if trade_size_usdt:
            total_position = usage.current_position_usdt + trade_size_usdt
            if total_position > quota.max_position_size_usdt:
                return (
                    False,
                    f"Position size would exceed limit (${quota.max_position_size_usdt})",
                )

        # Check API rate limit
        if usage.api_calls_last_minute >= quota.api_rate_limit_per_minute:
            return (
                False,
                f"API rate limit reached ({quota.api_rate_limit_per_minute}/min)",
            )

        return True, None

    @asynccontextmanager
    async def trade_context(
        self,
        strategy_id: str,
        trade_size_usdt: float,
    ):
        """
        Context manager for executing a trade with quota checks.

        Usage:
            async with manager.trade_context("strategy_1", 1000) as ctx:
                # Execute trade
                result = await execute_trade(...)
                ctx.record_trade(result)
        """
        context = self._contexts.get(strategy_id)
        if not context:
            raise ValueError(f"Strategy {strategy_id} not found")

        if context.state != StrategyState.RUNNING:
            raise RuntimeError(
                f"Strategy {strategy_id} is not running (state: {context.state})"
            )

        # Check quota before trade
        allowed, reason = await self.check_quota(strategy_id, trade_size_usdt)
        if not allowed:
            await self._trigger_circuit_breaker(context, reason)
            raise QuotaViolation(strategy_id, "pre_trade_check", 0, 0)

        # Update usage
        context.usage.open_trades += 1
        context.usage.current_position_usdt += trade_size_usdt
        context.usage.api_calls_last_minute += 1

        class TradeContextHelper:
            def __init__(self, ctx: StrategyContext, size: float):
                self.context = ctx
                self.size = size
                self.pnl: float = 0.0

            def record_trade(self, pnl: float) -> None:
                self.pnl = pnl
                self.context.usage.daily_trade_count += 1
                self.context.usage.daily_pnl_usdt += pnl
                self.context.trade_count_total += 1
                self.context.total_pnl_usdt += pnl
                self.context.last_trade_at = datetime.now(UTC)

                # Update peak equity and drawdown
                current_equity = self.context.peak_equity_usdt + pnl
                if current_equity > self.context.peak_equity_usdt:
                    self.context.peak_equity_usdt = current_equity

                if self.context.peak_equity_usdt > 0:
                    drawdown = (
                        (self.context.peak_equity_usdt - current_equity)
                        / self.context.peak_equity_usdt
                        * 100
                    )
                    self.context.usage.current_drawdown_percent = max(0, drawdown)

        helper = TradeContextHelper(context, trade_size_usdt)

        try:
            yield helper
        finally:
            # Cleanup
            context.usage.open_trades = max(0, context.usage.open_trades - 1)
            context.usage.current_position_usdt = max(
                0, context.usage.current_position_usdt - trade_size_usdt
            )
            context.usage.last_updated = datetime.now(UTC)

    async def record_error(self, strategy_id: str, error: str) -> None:
        """Record an error for a strategy"""
        context = self._contexts.get(strategy_id)
        if not context:
            return

        context.error_count += 1
        context.last_error = error

        # Auto-pause on too many errors
        if context.error_count >= 5:
            await self._trigger_circuit_breaker(
                context, f"Too many errors ({context.error_count})"
            )

    async def reset_daily_counters(self) -> None:
        """Reset daily counters for all strategies"""
        async with self._lock:
            for context in self._contexts.values():
                context.usage.daily_trade_count = 0
                context.usage.daily_pnl_usdt = 0.0
                context.error_count = 0
                context.last_error = None

        logger.info("Reset daily counters for all strategies")

    async def update_resource_usage(
        self,
        strategy_id: str,
        memory_mb: float | None = None,
        cpu_percent: float | None = None,
    ) -> None:
        """Update resource usage metrics for a strategy"""
        context = self._contexts.get(strategy_id)
        if not context:
            return

        if memory_mb is not None:
            context.usage.memory_mb = memory_mb

            # Check memory limit
            if memory_mb > context.quota.max_memory_mb:
                await self._trigger_circuit_breaker(
                    context,
                    f"Memory limit exceeded ({memory_mb}MB > {context.quota.max_memory_mb}MB)",
                )

        if cpu_percent is not None:
            context.usage.cpu_percent = cpu_percent

        context.usage.last_updated = datetime.now(UTC)

    async def _trigger_circuit_breaker(
        self,
        context: StrategyContext,
        reason: str,
        cooldown_seconds: float = 300.0,  # 5 minutes default
    ) -> None:
        """Trigger circuit breaker for a strategy"""
        context.circuit_breaker_triggered = True
        context.circuit_breaker_reason = reason
        context.circuit_breaker_triggered_at = datetime.now(UTC)
        context.cooldown_until = datetime.now(UTC).replace(tzinfo=UTC)

        # Calculate cooldown end time
        from datetime import timedelta

        context.cooldown_until = datetime.now(UTC) + timedelta(
            seconds=cooldown_seconds
        )

        old_state = context.state
        context.state = StrategyState.COOLDOWN

        logger.warning(
            f"Circuit breaker triggered for {context.strategy_id}: {reason}. "
            f"Cooldown until {context.cooldown_until}"
        )

        # Notify handlers
        for handler in self._on_circuit_breaker:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(context, reason)
                else:
                    handler(context, reason)
            except Exception as e:
                logger.error(f"Error in circuit breaker handler: {e}")

        await self._notify_state_change(context, old_state)

    async def _notify_state_change(
        self,
        context: StrategyContext,
        old_state: StrategyState,
    ) -> None:
        """Notify state change handlers"""
        for handler in self._on_state_change:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(context, old_state, context.state)
                else:
                    handler(context, old_state, context.state)
            except Exception as e:
                logger.error(f"Error in state change handler: {e}")

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop"""
        while self._running:
            try:
                await asyncio.sleep(self.monitoring_interval)

                for context in self._contexts.values():
                    # Decay API call counter
                    context.usage.api_calls_last_minute = max(
                        0, context.usage.api_calls_last_minute - 1
                    )

                    # Check if cooldown has expired
                    if (
                        context.state == StrategyState.COOLDOWN
                        and context.cooldown_until
                        and datetime.now(UTC) >= context.cooldown_until
                    ):
                        old_state = context.state
                        context.state = StrategyState.IDLE
                        context.cooldown_until = None
                        await self._notify_state_change(context, old_state)
                        logger.info(f"Strategy {context.strategy_id} cooldown expired")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

    def on_quota_violation(self, handler: Callable) -> None:
        """Register quota violation handler"""
        self._on_quota_violation.append(handler)

    def on_circuit_breaker(self, handler: Callable) -> None:
        """Register circuit breaker handler"""
        self._on_circuit_breaker.append(handler)

    def on_state_change(self, handler: Callable) -> None:
        """Register state change handler"""
        self._on_state_change.append(handler)

    def get_status(self) -> dict[str, Any]:
        """Get overall status of the isolation manager"""
        strategies_by_state = {}
        for state in StrategyState:
            strategies_by_state[state.value] = [
                ctx.strategy_id for ctx in self._contexts.values() if ctx.state == state
            ]

        return {
            "running": self._running,
            "total_strategies": len(self._contexts),
            "strategies_by_state": strategies_by_state,
            "default_isolation_level": self.default_isolation_level.value,
            "monitoring_enabled": self.enable_monitoring,
            "monitoring_interval_seconds": self.monitoring_interval,
        }


# Singleton instance
_isolation_manager: StrategyIsolationManager | None = None


def get_isolation_manager() -> StrategyIsolationManager:
    """Get or create the strategy isolation manager singleton"""
    global _isolation_manager

    if _isolation_manager is None:
        _isolation_manager = StrategyIsolationManager()

    return _isolation_manager


async def init_isolation_manager() -> StrategyIsolationManager:
    """Initialize and start the isolation manager"""
    manager = get_isolation_manager()
    await manager.start()
    return manager
