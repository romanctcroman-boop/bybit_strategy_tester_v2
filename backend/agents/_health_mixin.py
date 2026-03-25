"""
Health Monitoring Mixin for UnifiedAgentInterface

Extracted from unified_agent_interface.py to reduce file size.
Contains: health checks, circuit breaker registration, recovery actions,
           stats collection, autonomy score calculation.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx
from loguru import logger

from backend.agents.health_monitor import (
    HealthCheckResult,
    HealthStatus,
    RecoveryActionType,
)
from backend.agents.models import AgentType

if TYPE_CHECKING:
    from backend.agents.unified_agent_interface import APIKey, APIKeyHealth


class HealthMixin:
    """Mixin providing health monitoring, circuit breakers, and recovery logic."""

    # ------------------------------------------------------------------
    # Monitoring lifecycle
    # ------------------------------------------------------------------

    def ensure_monitoring_started(self) -> None:
        """Start health monitoring if not already running (lazy initialization)"""
        if self._monitoring_task is None or self._monitoring_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._monitoring_task = loop.create_task(self.health_monitor.start_monitoring(30))
                logger.info("🏥 Health monitoring started (30s interval)")
            except RuntimeError:
                logger.debug("⏳ No event loop yet, monitoring will start on first request")

    # ------------------------------------------------------------------
    # Circuit breaker & health check registration
    # ------------------------------------------------------------------

    def _register_circuit_breakers(self) -> None:
        """Register circuit breakers for all external dependencies"""
        self.circuit_manager.register_breaker(
            name="deepseek_api",
            fail_max=5,
            timeout_duration=60,
            expected_exception=Exception,
        )
        self.circuit_manager.register_breaker(
            name="perplexity_api",
            fail_max=5,
            timeout_duration=60,
            expected_exception=Exception,
        )
        self.circuit_manager.register_breaker(
            name="mcp_server",
            fail_max=3,
            timeout_duration=30,
            expected_exception=Exception,
        )

    def _register_health_checks(self) -> None:
        """Register health checks for all components"""
        self.health_monitor.register_health_check(
            component="deepseek_api",
            health_check_func=self._check_deepseek_health,
            recovery_func=self._recover_deepseek,
        )
        self.health_monitor.register_health_check(
            component="perplexity_api",
            health_check_func=self._check_perplexity_health,
            recovery_func=self._recover_perplexity,
        )
        self.health_monitor.register_health_check(
            component="mcp_server",
            health_check_func=self._check_mcp_health,
            recovery_func=self._recover_mcp,
        )

    # ------------------------------------------------------------------
    # Alerts / rate-limit tracking
    # ------------------------------------------------------------------

    def _handle_pool_alert(self, agent_type: AgentType, cooling: int, total: int) -> None:
        self.stats["key_pool_alerts"] += 1
        logger.error(f"🚨 Unified interface alert: {cooling}/{total} {agent_type.value} keys cooling simultaneously")

    def _record_rate_limit_event(self, agent_type: AgentType) -> None:
        self.stats["rate_limit_events"] += 1
        key = f"{agent_type.value}_rate_limits"
        self.stats[key] = self.stats.get(key, 0) + 1

    # ------------------------------------------------------------------
    # Health check implementations
    # ------------------------------------------------------------------

    async def _check_deepseek_health(self) -> HealthCheckResult:
        """Health check for DeepSeek API"""
        active_keys = sum(1 for k in self.key_manager.deepseek_keys if k.is_usable)
        total_keys = len(self.key_manager.deepseek_keys)

        if active_keys == 0:
            return HealthCheckResult(
                component="deepseek_api",
                status=HealthStatus.UNHEALTHY,
                message=f"No active DeepSeek keys (0/{total_keys})",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS,
            )
        elif active_keys < total_keys * 0.5:
            return HealthCheckResult(
                component="deepseek_api",
                status=HealthStatus.DEGRADED,
                message=f"Only {active_keys}/{total_keys} DeepSeek keys active",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS,
            )
        return HealthCheckResult(
            component="deepseek_api",
            status=HealthStatus.HEALTHY,
            message=f"DeepSeek API healthy ({active_keys}/{total_keys} keys active)",
            details={"active_keys": active_keys, "total_keys": total_keys},
        )

    async def _check_perplexity_health(self) -> HealthCheckResult:
        """Health check for Perplexity API"""
        active_keys = sum(1 for k in self.key_manager.perplexity_keys if k.is_usable)
        total_keys = len(self.key_manager.perplexity_keys)

        if active_keys == 0:
            return HealthCheckResult(
                component="perplexity_api",
                status=HealthStatus.UNHEALTHY,
                message=f"No active Perplexity keys (0/{total_keys})",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS,
            )
        elif active_keys < total_keys * 0.5:
            return HealthCheckResult(
                component="perplexity_api",
                status=HealthStatus.DEGRADED,
                message=f"Only {active_keys}/{total_keys} Perplexity keys active",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS,
            )
        return HealthCheckResult(
            component="perplexity_api",
            status=HealthStatus.HEALTHY,
            message=f"Perplexity API healthy ({active_keys}/{total_keys} keys active)",
            details={"active_keys": active_keys, "total_keys": total_keys},
        )

    async def _check_mcp_health(self) -> HealthCheckResult:
        """Health check for MCP Server"""
        if self.mcp_disabled:
            return HealthCheckResult(
                component="mcp_server",
                status=HealthStatus.DECOMMISSIONED,
                message="MCP disabled via MCP_DISABLED flag",
                details={"disabled": True},
            )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("http://127.0.0.1:8000/mcp/health")
                if resp.status_code == 200:
                    data = resp.json()
                    tool_count = data.get("tool_count", 0)
                    if tool_count >= 1:
                        return HealthCheckResult(
                            component="mcp_server",
                            status=HealthStatus.HEALTHY,
                            message=f"MCP Server healthy ({tool_count} tools)",
                            details=data,
                        )
                    return HealthCheckResult(
                        component="mcp_server",
                        status=HealthStatus.DEGRADED,
                        message="MCP Server running but no tools available",
                        details=data,
                        recovery_suggested=RecoveryActionType.FORCE_HEALTH_CHECK,
                    )
        except Exception as e:
            return HealthCheckResult(
                component="mcp_server",
                status=HealthStatus.UNHEALTHY,
                message=f"MCP Server unreachable: {e!s}",
                details={"error": str(e)},
                recovery_suggested=RecoveryActionType.FORCE_HEALTH_CHECK,
            )

    async def _test_key_health(self, agent_type: AgentType, key: APIKey) -> bool:
        """Minimal live request to verify that a key recovered."""
        url = self._get_api_url(agent_type)
        headers = self._get_headers(key)
        payload = {
            "model": "deepseek-chat" if agent_type == AgentType.DEEPSEEK else "sonar-pro",
            "messages": [
                {"role": "system", "content": "Health check ping"},
                {"role": "user", "content": "ping"},
            ],
            "max_tokens": 5,
            "temperature": 0.0,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                return True
            if response.status_code in (401, 403):
                self.key_manager.mark_auth_error(key)
            elif response.status_code == 429:
                retry_after = self._get_retry_after_seconds(response)
                self.key_manager.mark_rate_limit(key, retry_after=retry_after)
                self._record_rate_limit_event(agent_type)
            else:
                self.key_manager.mark_error(key)
        except TimeoutError:
            self.key_manager.mark_network_error(key)
        except httpx.HTTPError:
            self.key_manager.mark_network_error(key)
        except Exception:
            self.key_manager.mark_error(key)
        return False

    # ------------------------------------------------------------------
    # Recovery actions
    # ------------------------------------------------------------------

    async def _recover_deepseek(self, action_type: RecoveryActionType) -> None:
        """Recovery action for DeepSeek API"""
        if action_type == RecoveryActionType.RESET_ERRORS:
            recovered = 0
            for key in self.key_manager.deepseek_keys:
                if not key.is_usable:
                    is_healthy = await self._test_key_health(AgentType.DEEPSEEK, key)
                    if is_healthy:
                        key.error_count = 1
                        key.health = APIKeyHealth.DEGRADED
                        key.last_error_time = None
                        recovered += 1
                        logger.info(f"✅ Validated DeepSeek key #{key.index} (re-enabled in DEGRADED state)")
                    else:
                        logger.warning(f"❌ DeepSeek key #{key.index} failed validation, remains disabled")
            if recovered:
                self.stats["auto_recoveries"] += recovered
        elif action_type == RecoveryActionType.RESET_CIRCUIT_BREAKER:
            self.circuit_manager.reset_breaker("deepseek_api")
            self.stats["auto_recoveries"] += 1

    async def _recover_perplexity(self, action_type: RecoveryActionType) -> None:
        """Recovery action for Perplexity API"""
        if action_type == RecoveryActionType.RESET_ERRORS:
            recovered = 0
            for key in self.key_manager.perplexity_keys:
                if not key.is_usable:
                    is_healthy = await self._test_key_health(AgentType.PERPLEXITY, key)
                    if is_healthy:
                        key.error_count = 1
                        key.health = APIKeyHealth.DEGRADED
                        key.last_error_time = None
                        recovered += 1
                        logger.info(f"✅ Validated Perplexity key #{key.index} (re-enabled in DEGRADED state)")
                    else:
                        logger.warning(f"❌ Perplexity key #{key.index} failed validation, remains disabled")
            if recovered:
                self.stats["auto_recoveries"] += recovered
        elif action_type == RecoveryActionType.RESET_CIRCUIT_BREAKER:
            self.circuit_manager.reset_breaker("perplexity_api")
            self.stats["auto_recoveries"] += 1

    async def _recover_mcp(self, action_type: RecoveryActionType) -> None:
        """Recovery action for MCP Server"""
        if self.mcp_disabled:
            logger.debug("MCP recovery skipped because MCP_DISABLED flag is set")
            return
        if action_type == RecoveryActionType.FORCE_HEALTH_CHECK:
            await self._health_check()
            self.stats["auto_recoveries"] += 1
        elif action_type == RecoveryActionType.RESET_CIRCUIT_BREAKER:
            self.circuit_manager.reset_breaker("mcp_server")
            self.stats["auto_recoveries"] += 1

    # ------------------------------------------------------------------
    # Periodic health check
    # ------------------------------------------------------------------

    async def _health_check(self):
        """Периодическая проверка здоровья системы"""
        self.last_health_check = time.time()
        logger.debug("🏥 Running health check...")

        if self.mcp_disabled:
            self.mcp_available = False
        else:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get("http://127.0.0.1:8000/mcp/health")
                    if resp.status_code == 200:
                        data = resp.json()
                        self.mcp_available = bool(data.get("tool_count", 0) >= 1 and data.get("status") == "healthy")
                    else:
                        self.mcp_available = False
            except Exception as e:
                logger.debug(f"MCP health probe failed: {e}")
                self.mcp_available = False

        deepseek_active = sum(1 for k in self.key_manager.deepseek_keys if k.is_usable)
        perplexity_active = sum(1 for k in self.key_manager.perplexity_keys if k.is_usable)

        logger.info(
            f"🏥 Health: MCP={'✅' if self.mcp_available else '❌'} | "
            f"DeepSeek={deepseek_active}/8 | Perplexity={perplexity_active}/4"
        )

        adaptations = self.circuit_manager.maybe_adapt_breakers(force=True, min_interval_seconds=0)
        if adaptations:
            logger.info(f"⚙️ Adaptive circuit thresholds updated: {adaptations}")

    # ------------------------------------------------------------------
    # Stats & autonomy score
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику (включая Phase 1 metrics)"""
        cb_metrics = self.circuit_manager.get_metrics()
        health_metrics = self.health_monitor.get_metrics()

        return {
            **self.stats,
            "mcp_available": self.mcp_available,
            "mcp_disabled": self.mcp_disabled,
            "deepseek_keys_active": sum(1 for k in self.key_manager.deepseek_keys if k.is_usable),
            "perplexity_keys_active": sum(1 for k in self.key_manager.perplexity_keys if k.is_usable),
            "last_health_check": datetime.fromtimestamp(self.last_health_check).isoformat(),
            "circuit_breakers": cb_metrics.to_dict(),
            "health_monitoring": health_metrics,
            "autonomy_score": self._calculate_autonomy_score(cb_metrics, health_metrics),
        }

    def _calculate_autonomy_score(self, cb_metrics, health_metrics) -> float:
        """Calculate autonomy score (0-10) based on system health"""
        # Auto-recovery score (0-4.0 points)
        recovery_rate = health_metrics.get("recovery_success_rate", 0)
        auto_recovery_score = (recovery_rate / 100) * 4.0

        # Circuit breaker score (0-3.0 points)
        if hasattr(cb_metrics, "breakers") and cb_metrics.breakers:
            total_calls = sum(b.get("total_calls", 0) for b in cb_metrics.breakers.values())
            total_trips = sum(b.get("total_trips", 0) for b in cb_metrics.breakers.values())
            total_calls = total_calls or 1
            trip_rate = (total_trips / total_calls) * 100
        else:
            cb_data = cb_metrics.to_dict() if hasattr(cb_metrics, "to_dict") else {}
            total_calls = sum(b.get("success_count", 0) + b.get("failure_count", 0) for b in cb_data.values())
            total_calls = total_calls or 1
            trip_rate = 0

        circuit_score = max(0, 3.0 - (trip_rate / 10))

        # Component health score (0-3.0 points)
        total_components = health_metrics.get("total_components", 3)
        healthy_components = health_metrics.get("healthy_components", 0)
        health_score = (healthy_components / total_components) * 3.0 if total_components > 0 else 0

        return round(auto_recovery_score + circuit_score + health_score, 1)
