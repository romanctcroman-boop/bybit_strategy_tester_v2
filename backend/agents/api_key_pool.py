"""
API Key Pool Manager

Manages API key rotation, health tracking, and cooldown for DeepSeek/Perplexity APIs.
Extracted from unified_agent_interface.py for better modularity (P1 fix 2026-01-28).

Features:
- Weighted key selection based on health/usage
- Exponential backoff cooldown
- Thread-safe async lock for multi-worker deployment
- Pool pressure alerting
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from typing import Any

from loguru import logger

# Import shared models
from backend.agents.key_models import APIKey, APIKeyHealth
from backend.agents.models import AgentType


class APIKeyPoolManager:
    """
    Manages API key pools with health tracking and weighted selection.

    Thread-safe key selection with async lock prevents race conditions
    in multi-worker FastAPI deployments.

    Example:
        manager = APIKeyPoolManager()
        key = await manager.get_active_key(AgentType.DEEPSEEK)
        if key:
            try:
                # Use key
                manager.mark_success(key)
            except RateLimitError:
                manager.mark_rate_limit(key, retry_after=30)
    """

    BASE_COOLDOWN_SECONDS = 5.0
    MAX_COOLDOWN_SECONDS = 300.0
    COOLDOWN_ALERT_THRESHOLD = 0.5
    COOLDOWN_ALERT_COOLDOWN = 60.0

    def __init__(self):
        self.deepseek_keys: list[APIKey] = []
        self.perplexity_keys: list[APIKey] = []
        self.qwen_keys: list[APIKey] = []

        # Async lock for thread-safe key selection
        self._key_selection_lock = asyncio.Lock()
        self._alert_callback: Callable[[AgentType, int, int], None] | None = None
        self.pool_telemetry: dict[str, Any] = {
            "cooldown_events": 0,
            "rate_limit_events": 0,
            "alerts_triggered": 0,
            "snapshots": {},
        }
        self._last_pool_alert_ts: dict[AgentType, float] = {}

        self._load_keys()

    def _load_keys(self):
        """Load API keys via KeyManager — 1 key per provider."""
        try:
            from backend.security.key_manager import KeyManager

            km = KeyManager()

            # DeepSeek (1 key)
            key_name = "DEEPSEEK_API_KEY"
            try:
                if km.has_key(key_name, require_decryptable=True):
                    self.deepseek_keys.append(
                        APIKey(
                            value=None,
                            agent_type=AgentType.DEEPSEEK,
                            index=0,
                            key_name=key_name,
                        )
                    )
                    logger.debug(f"DeepSeek key registered (pool size: {len(self.deepseek_keys)})")
            except Exception as e:
                logger.warning(f"DeepSeek key lookup failed: {e}")

            # Perplexity (1 key)
            key_name = "PERPLEXITY_API_KEY"
            try:
                if km.has_key(key_name, require_decryptable=True):
                    self.perplexity_keys.append(
                        APIKey(
                            value=None,
                            agent_type=AgentType.PERPLEXITY,
                            index=0,
                            key_name=key_name,
                        )
                    )
                    logger.debug(f"Perplexity key registered (pool size: {len(self.perplexity_keys)})")
            except Exception as e:
                logger.warning(f"Perplexity key lookup failed: {e}")

            # Qwen (1 key)
            key_name = "QWEN_API_KEY"
            try:
                if km.has_key(key_name, require_decryptable=True):
                    self.qwen_keys.append(
                        APIKey(
                            value=None,
                            agent_type=AgentType.QWEN,
                            index=0,
                            key_name=key_name,
                        )
                    )
                    logger.debug(f"Qwen key registered (pool size: {len(self.qwen_keys)})")
            except Exception as e:
                logger.warning(f"Qwen key lookup failed: {e}")

            logger.info(
                f"Loaded {len(self.deepseek_keys)} DeepSeek + "
                f"{len(self.perplexity_keys)} Perplexity + "
                f"{len(self.qwen_keys)} Qwen keys"
            )

        except ImportError:
            logger.error("Encryption system not available!")
            raise

    def _get_pool(self, agent_type: AgentType) -> list[APIKey]:
        """Get key pool by agent type"""
        if agent_type == AgentType.DEEPSEEK:
            return self.deepseek_keys
        elif agent_type == AgentType.QWEN:
            return self.qwen_keys
        return self.perplexity_keys

    def _refresh_cooldowns(self, agent_type: AgentType) -> None:
        """Restore keys that have finished cooling"""
        pool = self._get_pool(agent_type)
        recovered = 0
        for key in pool:
            if key.maybe_exit_cooldown():
                recovered += 1
        if recovered:
            logger.info(f"Restored {recovered} cooled {agent_type.value} keys")

    def _calculate_weight(self, key: APIKey) -> float:
        """Calculate selection weight for a key"""
        if not key.is_usable:
            return 0.0
        health_weight = {
            APIKeyHealth.HEALTHY: 3.0,
            APIKeyHealth.DEGRADED: 1.5,
            APIKeyHealth.DISABLED: 0.0,
        }.get(key.health, 1.0)
        request_penalty = 1.0 / (1 + max(0, key.requests_count) / 25)
        error_penalty = 1.0 / (1 + max(0, key.error_count))
        cooldown_penalty = 0.5**key.cooldown_level if key.cooldown_level else 1.0
        recency_bonus = 1.0
        if key.last_used:
            idle_time = max(0.0, time.time() - key.last_used)
            recency_bonus = min(1.2, 0.2 + idle_time / 30.0)
        weight = health_weight * request_penalty * error_penalty * cooldown_penalty * recency_bonus
        return max(0.001, weight)

    def _apply_cooldown(
        self,
        key: APIKey,
        reason: str,
        duration: float | None = None,
    ) -> float:
        """Apply cooldown to a key with exponential backoff"""
        exponent = max(0, key.cooldown_level)
        base_duration = self.BASE_COOLDOWN_SECONDS * (2**exponent)
        cooldown_duration = duration if duration is not None else base_duration
        cooldown_duration = min(cooldown_duration, self.MAX_COOLDOWN_SECONDS)
        actual = key.begin_cooldown(cooldown_duration, reason)
        self.pool_telemetry["cooldown_events"] += 1
        self.pool_telemetry.setdefault("cooldown_reasons", {}).setdefault(reason, 0)
        self.pool_telemetry["cooldown_reasons"][reason] += 1
        logger.warning(f"Cooling {key.agent_type.value} key #{key.index} for {cooldown_duration:.1f}s ({reason})")
        self._emit_pool_telemetry(key.agent_type)
        self._maybe_alert_pool_pressure(key.agent_type)
        return actual

    def _emit_pool_telemetry(self, agent_type: AgentType) -> None:
        """Emit telemetry snapshot for a key pool"""
        pool = self._get_pool(agent_type)
        total = len(pool)
        cooling = sum(1 for key in pool if key.is_cooling)
        usable = sum(1 for key in pool if key.is_usable)
        disabled = sum(1 for key in pool if key.health == APIKeyHealth.DISABLED)
        snapshot = {
            "total_keys": total,
            "usable": usable,
            "cooling": cooling,
            "disabled": disabled,
            "timestamp": time.time(),
        }
        self.pool_telemetry["snapshots"][agent_type.value] = snapshot
        logger.debug(f"KeyPool[{agent_type.value}] snapshot: {snapshot}")

    def _maybe_alert_pool_pressure(self, agent_type: AgentType) -> None:
        """Alert if too many keys are cooling"""
        pool = self._get_pool(agent_type)
        total = len(pool)
        if not total:
            return
        cooling = sum(1 for key in pool if key.is_cooling)
        ratio = cooling / total
        if ratio >= self.COOLDOWN_ALERT_THRESHOLD:
            now = time.time()
            last_alert = self._last_pool_alert_ts.get(agent_type, 0)
            if now - last_alert >= self.COOLDOWN_ALERT_COOLDOWN:
                self._last_pool_alert_ts[agent_type] = now
                self.pool_telemetry["alerts_triggered"] += 1
                logger.error(f"{agent_type.value} key pool under pressure: {cooling}/{total} keys cooling")
                if self._alert_callback:
                    self._alert_callback(agent_type, cooling, total)

    def get_pool_metrics(self, agent_type: AgentType) -> dict[str, Any]:
        """Get metrics for a key pool"""
        pool = self._get_pool(agent_type)
        total = len(pool)
        cooling = sum(1 for key in pool if key.is_cooling)
        healthy = sum(1 for key in pool if key.health == APIKeyHealth.HEALTHY and not key.is_cooling)
        degraded = sum(1 for key in pool if key.health == APIKeyHealth.DEGRADED and not key.is_cooling)
        cooling_keys = [key for key in pool if key.is_cooling]
        earliest_ready = min((key.cooldown_until or float("inf")) for key in cooling_keys) if cooling_keys else None
        return {
            "total": total,
            "cooling": cooling,
            "healthy": healthy,
            "degraded": degraded,
            "next_available_in": max(0.0, earliest_ready - time.time()) if earliest_ready else 0.0,
        }

    def register_alert_callback(self, callback: Callable[[AgentType, int, int], None]) -> None:
        """Register callback for pool pressure alerts"""
        self._alert_callback = callback

    def _health_sort_key(self, key: APIKey) -> tuple[int, int, int, float]:
        """Sort key for health-based ordering"""
        priority_map = {
            APIKeyHealth.HEALTHY: 0,
            APIKeyHealth.DEGRADED: 1,
            APIKeyHealth.DISABLED: 2,
        }
        last_used_sort = -(key.last_used or 0)
        return (
            priority_map.get(key.health, 1),
            key.error_count,
            key.requests_count,
            last_used_sort,
        )

    def _update_health_state(self, key: APIKey) -> None:
        """Update key health based on error count"""
        if not hasattr(key, "health"):
            return

        if key.health == APIKeyHealth.DISABLED and key.error_count < 5:
            key.health = APIKeyHealth.DEGRADED if key.error_count >= 2 else APIKeyHealth.HEALTHY

        if key.error_count >= 5:
            key.health = APIKeyHealth.DISABLED
        elif key.error_count >= 2:
            key.health = APIKeyHealth.DEGRADED
        else:
            key.health = APIKeyHealth.HEALTHY

    async def get_active_key(self, agent_type: AgentType) -> APIKey | None:
        """
        Get an active API key using weighted selection.

        Thread-safe with async lock to prevent race conditions.
        """
        async with self._key_selection_lock:
            self._refresh_cooldowns(agent_type)
            pool = self._get_pool(agent_type)
            if not pool:
                return None

            active_keys = [k for k in pool if k.is_usable]
            if not active_keys:
                self._emit_pool_telemetry(agent_type)
                self._maybe_alert_pool_pressure(agent_type)
                return None

            weights = [self._calculate_weight(k) for k in active_keys]
            if not any(weights):
                logger.warning(f"No positive weights for {agent_type.value} key pool")
                return None

            selected = random.choices(active_keys, weights=weights, k=1)[0]
            selected_weight = weights[active_keys.index(selected)]
            logger.debug(
                f"Weighted key selection for {agent_type.value}: key #{selected.index} (weight={selected_weight:.4f})"
            )
            self._emit_pool_telemetry(agent_type)
            return selected

    def mark_error(self, key: APIKey):
        """Mark a generic error for a key"""
        key.error_count += 1
        try:
            key.last_error_time = time.time()
        except Exception:
            key.last_error_time = time.time()
        self._update_health_state(key)
        if hasattr(key, "health") and key.health == APIKeyHealth.DISABLED:
            agent = getattr(key, "agent_type", "?")
            idx = getattr(key, "index", "?")
            logger.warning(f"Disabled {agent} key #{idx} (error_count={key.error_count})")

    def mark_success(self, key: APIKey):
        """Mark successful use of a key"""
        key.last_used = time.time()
        key.requests_count += 1
        key.error_count = max(0, key.error_count - 1)
        if hasattr(key, "last_error_time") and key.error_count == 0:
            try:
                key.last_error_time = None
            except Exception as _e:
                logger.debug("Operation failed (expected): {}", _e)
        if (
            hasattr(key, "cooldown_level")
            and hasattr(key, "is_cooling")
            and key.cooldown_level > 0
            and not key.is_cooling
        ):
            key.cooldown_level = max(0, key.cooldown_level - 1)
        self._update_health_state(key)

    def mark_network_error(self, key: APIKey):
        """Mark a network error without disabling the key"""
        key.error_count += 1
        key.last_error_time = time.time()
        self._update_health_state(key)

    def mark_rate_limit(self, key: APIKey, retry_after: float | None = None):
        """Mark rate limit and apply cooldown"""
        key.error_count += 1
        key.last_error_time = time.time()
        self.pool_telemetry["rate_limit_events"] += 1
        self._update_health_state(key)
        cooldown = retry_after if (retry_after is not None and retry_after > 0) else None
        self._apply_cooldown(key, reason="rate_limit", duration=cooldown)

    def mark_client_error(self, key: APIKey):
        """Mark client error (4xx except 401/403/429)"""
        key.error_count += 1
        key.last_error_time = time.time()
        self._update_health_state(key)

    def mark_auth_error(self, key: APIKey):
        """Immediately disable key on auth error"""
        key.error_count += 1
        key.last_error_time = time.time()
        key.health = APIKeyHealth.DISABLED
        logger.warning(f"Disabled {key.agent_type.value} key #{key.index} due to auth error")

    def count_active(self, agent_type: AgentType) -> int:
        """Count active (usable) keys for an agent type"""
        pool = self._get_pool(agent_type)
        return sum(1 for key in pool if key.is_usable)

    async def validate_keys_preflight(self) -> dict[str, Any]:
        """
        Pre-flight validation: verify each registered key is valid
        by sending a minimal API request.

        Disables keys that return 401/403 (invalid/revoked).
        Logs results for each provider.

        Returns:
            Dict with per-provider validation results:
            {"deepseek": {"valid": True, "status": 200}, ...}
        """
        import httpx

        results: dict[str, Any] = {}

        # Validation endpoints — minimal requests for each provider
        checks = [
            (
                "deepseek",
                self.deepseek_keys,
                "https://api.deepseek.com/models",
                "DEEPSEEK_API_KEY",
            ),
            (
                "qwen",
                self.qwen_keys,
                "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
                "QWEN_API_KEY",
            ),
            (
                "perplexity",
                self.perplexity_keys,
                "https://api.perplexity.ai/chat/completions",
                "PERPLEXITY_API_KEY",
            ),
        ]

        for provider, pool, url, key_name in checks:
            if not pool:
                results[provider] = {"valid": False, "reason": "no_key_registered"}
                logger.warning(f"⚠️ Pre-flight: {provider} has no keys registered")
                continue

            key_obj = pool[0]
            try:
                from backend.security.key_manager import KeyManager

                km = KeyManager()
                api_key = km.get_decrypted_key(key_name)
                if not api_key:
                    results[provider] = {"valid": False, "reason": "key_not_decryptable"}
                    key_obj.health = APIKeyHealth.DISABLED
                    logger.error(f"❌ Pre-flight: {provider} key not decryptable")
                    continue

                # Lightweight validation request
                headers = {"Authorization": f"Bearer {api_key}"}

                # Perplexity doesn't have a /models endpoint, use a different check
                if provider == "perplexity":
                    # Just check that auth header is accepted with a tiny request
                    headers["Content-Type"] = "application/json"
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(
                            url,
                            headers=headers,
                            json={
                                "model": "sonar",
                                "messages": [{"role": "user", "content": "ping"}],
                                "max_tokens": 1,
                            },
                        )
                else:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(url, headers=headers)

                if resp.status_code in (200, 201):
                    results[provider] = {"valid": True, "status": resp.status_code}
                    logger.info(f"✅ Pre-flight: {provider} key valid (HTTP {resp.status_code})")
                elif resp.status_code in (401, 403):
                    results[provider] = {"valid": False, "status": resp.status_code, "reason": "auth_failed"}
                    key_obj.health = APIKeyHealth.DISABLED
                    logger.error(f"❌ Pre-flight: {provider} key INVALID (HTTP {resp.status_code})")
                elif resp.status_code == 429:
                    # Rate limited but key is valid
                    results[provider] = {"valid": True, "status": 429, "note": "rate_limited_but_valid"}
                    logger.warning(f"⚠️ Pre-flight: {provider} key valid but rate-limited")
                else:
                    results[provider] = {"valid": True, "status": resp.status_code, "note": "unexpected_status"}
                    logger.warning(f"⚠️ Pre-flight: {provider} returned HTTP {resp.status_code}")

            except httpx.ConnectError as e:
                results[provider] = {"valid": None, "reason": "connection_failed", "error": str(e)[:100]}
                logger.warning(f"⚠️ Pre-flight: {provider} connection failed (DNS/network): {e}")
            except Exception as e:
                results[provider] = {"valid": None, "reason": "check_failed", "error": str(e)[:100]}
                logger.warning(f"⚠️ Pre-flight: {provider} check failed: {e}")

        # Summary
        valid_count = sum(1 for r in results.values() if r.get("valid") is True)
        total_count = len(results)
        logger.info(f"🔑 Pre-flight key validation: {valid_count}/{total_count} providers OK")

        return results


# Backward compatibility alias
APIKeyManager = APIKeyPoolManager


__all__ = [
    "APIKeyManager",  # Alias for backward compatibility
    "APIKeyPoolManager",
]
