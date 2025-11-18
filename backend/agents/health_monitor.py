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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from loguru import logger


class HealthStatus(str, Enum):
    """Health check statuses"""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"  # Partial functionality
    UNHEALTHY = "UNHEALTHY"  # Complete failure
    UNKNOWN = "UNKNOWN"  # Not yet checked


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
    
    def __init__(self):
        self._health_checks: Dict[str, Callable] = {}
        self._recovery_actions: Dict[str, Callable] = {}
        self._health_status: Dict[str, HealthCheckResult] = {}
        self._recovery_history: List[RecoveryAction] = []
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        logger.info("🏥 Health Monitor initialized")
    
    def register_health_check(
        self,
        component: str,
        health_check_func: Callable,
        recovery_func: Optional[Callable] = None
    ) -> None:
        """
        Register a health check for a component.
        
        Args:
            component: Unique component name (e.g., "deepseek_api")
            health_check_func: Async function that returns HealthCheckResult
            recovery_func: Optional async function to execute for recovery
        """
        if component in self._health_checks:
            logger.warning(f"Health check for '{component}' already registered, replacing")
        
        self._health_checks[component] = health_check_func
        if recovery_func:
            self._recovery_actions[component] = recovery_func
        
        # Initialize status
        self._health_status[component] = HealthCheckResult(
            component=component,
            status=HealthStatus.UNKNOWN,
            message="Not yet checked"
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
                message="No health check registered"
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
                message=f"Health check error: {str(e)}"
            )
            self._health_status[component] = result
            return result
    
    async def execute_recovery(self, component: str, action_type: RecoveryActionType) -> RecoveryAction:
        """
        Execute recovery action for a component.
        
        Args:
            component: Component name
            action_type: Type of recovery action
        
        Returns:
            RecoveryAction with execution results
        """
        recovery_action = RecoveryAction(
            action_type=action_type,
            component=component,
            reason=f"Automated recovery triggered by health monitor",
            executed_at=datetime.now(timezone.utc)
        )
        
        if component not in self._recovery_actions:
            logger.error(f"No recovery action registered for '{component}'")
            recovery_action.error = "No recovery action registered"
            return recovery_action
        
        try:
            recovery_func = self._recovery_actions[component]
            await recovery_func(action_type)
            
            recovery_action.success = True
            logger.info(f"✅ Recovery action '{action_type.value}' completed for '{component}'")
            
            # Recheck health after recovery
            await asyncio.sleep(5)  # Wait 5s for recovery to take effect
            health_result = await self.check_component_health(component)
            
            if health_result.status == HealthStatus.HEALTHY:
                logger.info(f"🎉 Component '{component}' recovered successfully!")
            else:
                logger.warning(f"⚠️ Component '{component}' still unhealthy after recovery")
        
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
                    if result.status == HealthStatus.UNHEALTHY and result.recovery_suggested:
                        logger.warning(
                            f"🚨 Component '{component}' unhealthy, "
                            f"triggering recovery: {result.recovery_suggested.value}"
                        )
                        await self.execute_recovery(component, result.recovery_suggested)
                
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
            1 for status in self._health_status.values()
            if status.status == HealthStatus.HEALTHY
        )
        degraded = sum(
            1 for status in self._health_status.values()
            if status.status == HealthStatus.DEGRADED
        )
        unhealthy = sum(
            1 for status in self._health_status.values()
            if status.status == HealthStatus.UNHEALTHY
        )
        
        total_recoveries = len(self._recovery_history)
        successful_recoveries = sum(1 for r in self._recovery_history if r.success)
        
        return {
            "is_monitoring": self._is_monitoring,
            "total_components": total_checks,
            "healthy_components": healthy,
            "degraded_components": degraded,
            "unhealthy_components": unhealthy,
            "total_recovery_attempts": total_recoveries,
            "successful_recoveries": successful_recoveries,
            "recovery_success_rate": (
                successful_recoveries / total_recoveries * 100
                if total_recoveries > 0 else 0.0
            ),
            "components": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "checked_at": result.checked_at.isoformat()
                }
                for name, result in self._health_status.items()
            }
        }


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
        _health_monitor = HealthMonitor()
    return _health_monitor
