"""
Health Monitor for AI Agent System

Continuously monitors the health of all AI agent components and automatically
triggers recovery actions when issues are detected. Works alongside circuit breakers
to provide comprehensive resilience.

Monitored Components:
- DeepSeek API: Key rotation health, error rates, response times
- Perplexity API: Key rotation health, error rates, response times
- MCP Server: Process health, connectivity, tool availability

Phase 1 Implementation - Week 1
Part of autonomous multi-agent self-improvement initiative.
"""

import asyncio
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
from loguru import logger

from backend.agents.base_config import MCP_DISABLED

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MCP_TRANSPORT_URL = "http://127.0.0.1:8000/mcp"
DEFAULT_MCP_HEALTH_URL = f"{DEFAULT_MCP_TRANSPORT_URL}/health"
FILE_STRATEGY_PROBE_TTL_SECONDS = 30
CONTROLLED_RESTART_COOLDOWN_SECONDS = 60

try:  # Optional dependency used for lightweight MCP probes
    from fastmcp import Client as FastMcpClient
    from fastmcp.client.transports import StreamableHttpTransport
except Exception:  # pragma: no cover - optional
    FastMcpClient = None
    StreamableHttpTransport = None


class HealthStatus(str, Enum):
    """Health check statuses"""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"  # Partial functionality
    UNHEALTHY = "UNHEALTHY"  # Complete failure
    UNKNOWN = "UNKNOWN"  # Not yet checked
    DECOMMISSIONED = "DECOMMISSIONED"  # Intentionally offline


class RecoveryActionType(str, Enum):
    """Types of recovery actions"""

    ROTATE_KEYS = "ROTATE_KEYS"
    RESET_ERRORS = "RESET_ERRORS"
    RESTART_SERVICE = "RESTART_SERVICE"
    FORCE_HEALTH_CHECK = "FORCE_HEALTH_CHECK"
    RESET_CIRCUIT_BREAKER = "RESET_CIRCUIT_BREAKER"
    NO_ACTION = "NO_ACTION"


@dataclass
class HealthCheckResult:
    """Result of a health check"""

    component: str
    status: HealthStatus
    message: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)
    recovery_suggested: Optional[RecoveryActionType] = None


@dataclass
class RecoveryAction:
    """A recovery action to execute"""

    action_type: RecoveryActionType
    component: str
    reason: str
    executed_at: Optional[datetime] = None
    success: bool = False
    error: Optional[str] = None


class FileOperationStrategy(str, Enum):
    """Strategies for applying code changes."""

    MCP_PRIMARY = "mcp_primary"
    MCP_DEGRADED = "mcp_degraded"
    DIRECT_FALLBACK = "direct_fallback"


@dataclass
class FileOperationDecision:
    """Decision record returned by get_file_operation_strategy."""

    strategy: FileOperationStrategy
    reason: str
    mcp_available: bool
    health_status: str
    fallback_mode: bool
    timestamp: str
    degraded: bool = False
    context: Optional[str] = None


class HealthMonitor:
    """
    Monitors health of AI agent components and triggers automatic recovery.

    Runs continuous health checks in the background (default: every 30 seconds)
    and executes recovery actions when issues are detected.

    Usage:
        monitor = get_health_monitor()

        # Register a health check
        monitor.register_health_check(
            "deepseek_api",
            check_deepseek_health,
            recovery_action=recover_deepseek
        )

        # Start background monitoring
        await monitor.start_monitoring(interval_seconds=30)

        # Get current health status
        status = monitor.get_component_health("deepseek_api")
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        mcp_base_url: Optional[str] = None,
        mcp_disabled: Optional[bool] = None,
    ):
        self._health_checks: Dict[str, Callable] = {}
        self._recovery_actions: Dict[str, Callable] = {}
        self._health_status: Dict[str, HealthCheckResult] = {}
        self._recovery_history: List[RecoveryAction] = []
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        self.project_root = Path(project_root) if project_root else PROJECT_ROOT
        base_url = (mcp_base_url or DEFAULT_MCP_TRANSPORT_URL).rstrip("/")
        if base_url.endswith("/health"):
            self._mcp_transport_url = base_url.rsplit("/health", 1)[0]
            self._mcp_health_url = base_url
        else:
            self._mcp_transport_url = base_url
            self._mcp_health_url = f"{base_url}/health"
        self._mcp_probe_timeout = 5.0
        self._probe_ttl_seconds = FILE_STRATEGY_PROBE_TTL_SECONDS
        self._last_probe_result: Optional[HealthCheckResult] = None
        self._fallback_mode = False
        self._degraded_periods: List[Dict[str, Any]] = []
        self._restart_lock = asyncio.Lock()
        self._last_restart_attempt: Optional[datetime] = None
        self._mcp_disabled = MCP_DISABLED if mcp_disabled is None else mcp_disabled
        self._auto_restart_enabled = not self._mcp_disabled
        self._mcp_entrypoint = "mcp-server/server.py"
        if self._mcp_disabled:
            logger.debug("MCP health monitoring disabled via MCP_DISABLED flag")
            self._build_decommissioned_result()
        logger.info("🏥 Health Monitor initialized")

    def register_health_check(
        self,
        component: str,
        health_check_func: Callable,
        recovery_func: Optional[Callable] = None,
    ) -> None:
        """
        Register a health check for a component.

        Args:
            component: Unique component name (e.g., "deepseek_api")
            health_check_func: Async function that returns HealthCheckResult
            recovery_func: Optional async function to execute for recovery
        """
        if component in self._health_checks:
            logger.warning(f"Health check for '{component}' already registered")

        self._health_checks[component] = health_check_func
        if recovery_func:
            self._recovery_actions[component] = recovery_func

        # Initialize status
        self._health_status[component] = HealthCheckResult(
            component=component, status=HealthStatus.UNKNOWN, message="Not yet checked"
        )

        logger.info(
            f"✅ Health check registered for '{component}' "
            f"(recovery: {'yes' if recovery_func else 'no'})"
        )

    async def check_component_health(self, component: str) -> HealthCheckResult:
        """
        Execute health check for a specific component.

        Args:
            component: Component name

        Returns:
            HealthCheckResult
        """
        if component not in self._health_checks:
            logger.error(f"No health check registered for '{component}'")
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNKNOWN,
                message="No health check registered",
            )

        try:
            health_check = self._health_checks[component]
            result = await health_check()

            # Update cached status
            self._health_status[component] = result

            # Log status changes
            if result.status == HealthStatus.UNHEALTHY:
                logger.error(f"❌ {component}: {result.message}")
            elif result.status == HealthStatus.DEGRADED:
                logger.warning(f"⚠️ {component}: {result.message}")
            else:
                logger.debug(f"✅ {component}: {result.message}")

            return result

        except Exception as e:
            logger.error(f"Health check failed for '{component}': {e}")
            result = HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
            )
            self._health_status[component] = result
            return result

    async def execute_recovery(
        self, component: str, action_type: RecoveryActionType
    ) -> RecoveryAction:
        """Execute recovery action for a component.

        Args:
            component: Component name
            action_type: Type of recovery action

        Returns:
            RecoveryAction with execution results
        """
        recovery_action = RecoveryAction(
            action_type=action_type,
            component=component,
            reason="Automated recovery triggered by health monitor",
            executed_at=datetime.now(timezone.utc),
        )

        if component not in self._recovery_actions:
            logger.error(f"No recovery action registered for '{component}'")
            recovery_action.error = "No recovery action registered"
            return recovery_action

        try:
            recovery_func = self._recovery_actions[component]
            await recovery_func(action_type)

            recovery_action.success = True
            logger.info(
                f"✅ Recovery action '{action_type.value}' completed for '{component}'"
            )

            # Recheck health after recovery
            await asyncio.sleep(5)  # Wait 5s for recovery to take effect
            health_result = await self.check_component_health(component)

            if health_result.status == HealthStatus.HEALTHY:
                logger.info(f"🎉 Component '{component}' recovered successfully!")
            else:
                logger.warning(
                    f"⚠️ Component '{component}' still unhealthy after recovery"
                )

        except Exception as e:
            recovery_action.error = str(e)
            logger.error(f"❌ Recovery action failed for '{component}': {e}")

        # Track recovery history
        self._recovery_history.append(recovery_action)
        if len(self._recovery_history) > 100:
            self._recovery_history = self._recovery_history[-100:]  # Keep last 100

        return recovery_action

    async def _monitoring_loop(self, interval_seconds: int) -> None:
        """Background monitoring loop"""
        logger.info(f"🔄 Starting health monitoring (interval: {interval_seconds}s)")
        self._is_monitoring = True

        while self._is_monitoring:
            try:
                # Check all registered components
                for component in list(self._health_checks.keys()):
                    result = await self.check_component_health(component)

                    # Trigger recovery if needed
                    if (
                        result.status == HealthStatus.UNHEALTHY
                        and result.recovery_suggested
                    ):
                        logger.warning(
                            f"🚨 Component '{component}' unhealthy, "
                            f"triggering recovery: {result.recovery_suggested.value}"
                        )
                        await self.execute_recovery(
                            component, result.recovery_suggested
                        )

                # Wait for next cycle
                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                logger.info("Health monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)

        logger.info("Health monitoring stopped")

    async def start_monitoring(self, interval_seconds: int = 30) -> None:
        """
        Start background health monitoring.

        Args:
            interval_seconds: Seconds between health checks (default: 30)
        """
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Health monitoring already running")
            return

        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )

    async def stop_monitoring(self) -> None:
        """Stop background health monitoring"""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitoring stopped")

    def get_component_health(self, component: str) -> Optional[HealthCheckResult]:
        """Get current health status for a component"""
        return self._health_status.get(component)

    def get_all_health(self) -> Dict[str, HealthCheckResult]:
        """Get health status for all components"""
        return self._health_status.copy()

    def get_recovery_history(self, limit: int = 10) -> List[RecoveryAction]:
        """Get recent recovery actions"""
        return self._recovery_history[-limit:]

    def get_metrics(self) -> dict:
        """Get health monitoring metrics"""
        total_checks = len(self._health_checks)
        healthy = sum(
            1
            for status in self._health_status.values()
            if status.status == HealthStatus.HEALTHY
        )
        degraded = sum(
            1
            for status in self._health_status.values()
            if status.status == HealthStatus.DEGRADED
        )
        unhealthy = sum(
            1
            for status in self._health_status.values()
            if status.status == HealthStatus.UNHEALTHY
        )
        decommissioned = sum(
            1
            for status in self._health_status.values()
            if status.status == HealthStatus.DECOMMISSIONED
        )

        total_recoveries = len(self._recovery_history)
        successful_recoveries = sum(1 for r in self._recovery_history if r.success)

        return {
            "is_monitoring": self._is_monitoring,
            "total_components": total_checks,
            "healthy_components": healthy,
            "degraded_components": degraded,
            "unhealthy_components": unhealthy,
            "decommissioned_components": decommissioned,
            "total_recovery_attempts": total_recoveries,
            "successful_recoveries": successful_recoveries,
            "recovery_success_rate": (
                successful_recoveries / total_recoveries * 100
                if total_recoveries > 0
                else 0.0
            ),
            "components": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "checked_at": result.checked_at.isoformat(),
                }
                for name, result in self._health_status.items()
            },
        }

    # ------------------------------------------------------------------
    # MCP-specific monitoring helpers
    # ------------------------------------------------------------------
    async def _http_probe(self) -> tuple[bool, Dict[str, Any]]:
        details: Dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=self._mcp_probe_timeout) as client:
                response = await client.get(self._mcp_health_url)
            details["status_code"] = response.status_code
            if response.headers.get("content-type", "").startswith("application/json"):
                payload = response.json()
                details["payload"] = payload
                healthy = (
                    response.status_code == 200 and payload.get("status") == "healthy"
                )
            else:
                healthy = response.status_code == 200
            return healthy, details
        except Exception as exc:  # pragma: no cover - network failures
            details["error"] = str(exc)
            return False, details

    async def _client_ping(self) -> tuple[bool, Optional[str]]:
        if not FastMcpClient or not StreamableHttpTransport:
            return False, "fastmcp_unavailable"
        try:
            transport = StreamableHttpTransport(self._mcp_transport_url)
            async with FastMcpClient(transport=transport) as client:
                ok = await asyncio.wait_for(
                    client.ping(), timeout=self._mcp_probe_timeout
                )
            return bool(ok), None
        except Exception as exc:  # pragma: no cover - optional
            return False, str(exc)

    def _build_decommissioned_result(
        self, context: Optional[str] = None
    ) -> HealthCheckResult:
        details: Dict[str, Any] = {"disabled": True}
        if context:
            details["context"] = context
        result = HealthCheckResult(
            component="mcp_server",
            status=HealthStatus.DECOMMISSIONED,
            message="MCP disabled via MCP_DISABLED flag",
            details=details,
        )
        self._health_status["mcp_server"] = result
        self._last_probe_result = result
        self._fallback_mode = False
        return result

    def _update_fallback_state(
        self, status: HealthStatus, reason: str, context: Optional[str] = None
    ) -> None:
        degraded = status in {HealthStatus.DEGRADED, HealthStatus.UNHEALTHY}
        if degraded and not self._fallback_mode:
            self._fallback_mode = True
            self._start_degraded_period(reason, context)
        elif not degraded and self._fallback_mode:
            self._fallback_mode = False
            self._end_degraded_period(reason)

    def _start_degraded_period(
        self, reason: str, context: Optional[str] = None
    ) -> None:
        entry = {
            "start": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        if context:
            entry["context"] = context
        logger.warning(
            f"📉 Entering MCP fallback mode: {reason} ({context or 'no-context'})"
        )
        self._degraded_periods.append(entry)

    def _end_degraded_period(self, resolution: str) -> None:
        if not self._degraded_periods:
            return
        entry = self._degraded_periods[-1]
        if "end" in entry:
            return
        entry["end"] = datetime.now(timezone.utc).isoformat()
        entry["resolution"] = resolution
        logger.info(f"📈 MCP returned to healthy mode: {resolution}")

    async def probe_mcp_server(
        self, context: Optional[str] = None
    ) -> HealthCheckResult:
        if self._mcp_disabled:
            return self._build_decommissioned_result(context)
        http_ok, http_details = await self._http_probe()
        client_ok = False
        client_error: Optional[str] = None
        if http_ok:
            client_ok, client_error = await self._client_ping()
        else:
            client_ok, client_error = await self._client_ping()

        if http_ok and client_ok:
            status = HealthStatus.HEALTHY
            message = "MCP health endpoint and ping succeeded"
        elif http_ok or client_ok:
            status = HealthStatus.DEGRADED
            message = "MCP partially responsive"
        else:
            status = HealthStatus.UNHEALTHY
            message = "MCP unreachable"

        details = {
            "http": http_details,
            "client_error": client_error,
        }
        result = HealthCheckResult(
            component="mcp_server",
            status=status,
            message=message,
            details=details,
        )
        self._health_status["mcp_server"] = result
        self._last_probe_result = result
        self._update_fallback_state(status, message, context)
        return result

    async def _maybe_restart_mcp(self) -> None:
        if self._mcp_disabled or not self._auto_restart_enabled:
            return
        now = datetime.now(timezone.utc)
        if (
            self._last_restart_attempt
            and (now - self._last_restart_attempt).total_seconds()
            < CONTROLLED_RESTART_COOLDOWN_SECONDS
        ):
            return
        self._last_restart_attempt = now
        if not (self.project_root / self._mcp_entrypoint).exists():
            logger.error("MCP entrypoint missing; cannot restart")
            return
        async with self._restart_lock:
            try:
                subprocess.Popen(
                    [sys.executable, self._mcp_entrypoint],
                    cwd=str(self.project_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                logger.warning("🔄 Triggered controlled MCP restart")
                await asyncio.sleep(5)
                await self.execute_recovery(
                    "mcp_server", RecoveryActionType.FORCE_HEALTH_CHECK
                )
            except Exception as exc:  # pragma: no cover - best effort
                logger.error(f"Failed to restart MCP server: {exc}")

    async def get_file_operation_strategy(
        self,
        mcp_available: bool,
        context: Optional[str] = None,
    ) -> FileOperationDecision:
        now = datetime.now(timezone.utc)
        status = self._health_status.get("mcp_server")

        if self._mcp_disabled:
            if not status or status.status != HealthStatus.DECOMMISSIONED:
                status = self._build_decommissioned_result(context)
            return FileOperationDecision(
                strategy=FileOperationStrategy.DIRECT_FALLBACK,
                reason="MCP disabled via MCP_DISABLED flag",
                mcp_available=False,
                health_status=status.status.value,
                fallback_mode=False,
                timestamp=now.isoformat(),
                degraded=False,
                context=context,
            )

        if (
            not status
            or (now - status.checked_at).total_seconds() > self._probe_ttl_seconds
        ):
            status = await self.probe_mcp_server(context)

        if mcp_available and status.status == HealthStatus.HEALTHY:
            strategy = FileOperationStrategy.MCP_PRIMARY
            reason = "MCP healthy"
        elif mcp_available and status.status == HealthStatus.DEGRADED:
            strategy = FileOperationStrategy.MCP_DEGRADED
            reason = "MCP degraded"
        else:
            strategy = FileOperationStrategy.DIRECT_FALLBACK
            reason = "MCP unavailable"
            await self._maybe_restart_mcp()

        self._update_fallback_state(status.status, reason, context)
        decision = FileOperationDecision(
            strategy=strategy,
            reason=reason,
            mcp_available=mcp_available,
            health_status=status.status.value,
            fallback_mode=self._fallback_mode,
            timestamp=now.isoformat(),
            degraded=(strategy != FileOperationStrategy.MCP_PRIMARY),
            context=context,
        )
        if status.status == HealthStatus.DECOMMISSIONED:
            decision.degraded = False
        return decision

    def get_degraded_periods(self) -> List[Dict[str, Any]]:
        return list(self._degraded_periods)

    def get_fallback_mode(self) -> bool:
        return self._fallback_mode


# Global singleton instance
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """
    Get the global health monitor singleton.

    Returns:
        HealthMonitor instance
    """
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor(mcp_disabled=MCP_DISABLED)
    return _health_monitor
