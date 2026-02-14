"""
API Key Models — Single Source of Truth

Contains APIKeyHealth enum and APIKey dataclass used across the entire agent system.
Addresses audit finding: "APIKey duplicated in 3 files" (All 3 agents, P0)

Previously duplicated in:
- unified_agent_interface.py (authoritative, dataclass with full features)
- key_manager.py (different __init__ signature)
- models.py (Pydantic BaseModel, different interface)

This module is THE canonical implementation. All other files should import from here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger

from backend.agents.models import AgentType


class APIKeyHealth(str, Enum):
    """Health tiers for API keys.

    - HEALTHY: Key is fully operational
    - DEGRADED: Key has errors but still usable (error_count >= 2)
    - DISABLED: Key is disabled due to auth errors or too many failures
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISABLED = "disabled"


@dataclass(init=False)
class APIKey:
    """API key with metadata, lazy decryption, health tracking, and cooldown management.

    This is the canonical APIKey implementation. All imports across the codebase
    should reference this class.

    Features:
    - Lazy value resolution (env vars, KeyManager decryption, or direct override)
    - Health state machine (HEALTHY -> DEGRADED -> DISABLED)
    - Cooldown with exponential backoff
    - Usage statistics (requests_count, error_count)
    - Backward-compatible `is_active` property

    Example:
        key = APIKey(
            value="sk-xxx",
            agent_type=AgentType.DEEPSEEK,
            index=0,
        )
        assert key.is_usable
        key.begin_cooldown(30.0, "rate_limit")
        assert key.is_cooling
    """

    agent_type: AgentType
    index: int  # 0-7 for DeepSeek, 0-7 for Qwen, 0-7 for Perplexity
    health: APIKeyHealth = APIKeyHealth.HEALTHY
    last_used: float | None = None
    error_count: int = 0
    requests_count: int = 0
    cooldown_until: float | None = None
    cooldown_level: int = 0
    last_cooldown_reason: str | None = None
    last_cooldown_started: float | None = None
    cooling_events: int = 0
    key_name: str | None = None
    last_error_time: float | None = None
    _value_override: str | None = field(default=None, repr=False, compare=False)
    _key_manager: Any | None = field(default=None, repr=False, compare=False)

    def __init__(
        self,
        value: str | None = None,
        agent_type: AgentType = AgentType.DEEPSEEK,
        index: int = 0,
        *,
        key_name: str | None = None,
        health: APIKeyHealth = APIKeyHealth.HEALTHY,
        last_used: float | None = None,
        error_count: int = 0,
        requests_count: int = 0,
        last_error_time: float | None = None,
        cooldown_until: float | None = None,
        cooldown_level: int = 0,
        last_cooldown_reason: str | None = None,
        last_cooldown_started: float | None = None,
        cooling_events: int = 0,
        is_active: bool | None = None,
        # Legacy kwargs from key_manager.py interface
        value_override: str | None = None,
        key_manager: Any | None = None,
        **legacy_kwargs: Any,
    ) -> None:
        """Initialize API key.

        Supports two calling conventions for backward compatibility:
        1. Unified style: APIKey(value="sk-xxx", agent_type=..., index=...)
        2. key_manager style: APIKey(agent_type=..., index=..., value_override="sk-xxx")

        Args:
            value: Direct key value (primary)
            agent_type: Provider type (DeepSeek, Qwen, Perplexity)
            index: Key index in pool
            key_name: Secret name for KeyManager decryption
            health: Initial health state
            value_override: Alias for `value` (key_manager.py compatibility)
            key_manager: Reference to external key manager for decryption
        """
        if legacy_kwargs:
            logger.debug("APIKey received legacy kwargs: {}", list(legacy_kwargs.keys()))

        # Resolve value: prefer `value`, fallback to `value_override`
        self._value_override = value if value is not None else value_override
        self._key_manager = key_manager
        self.key_name = key_name
        self.agent_type = agent_type
        self.index = index
        self.health = health
        self.last_used = last_used
        self.error_count = error_count
        self.requests_count = requests_count
        self.last_error_time = last_error_time
        self.cooldown_until = cooldown_until
        self.cooldown_level = cooldown_level
        self.last_cooldown_reason = last_cooldown_reason
        self.last_cooldown_started = last_cooldown_started
        self.cooling_events = cooling_events

        # Auto-generate key_name if not provided
        if not self.key_name and self._value_override is None:
            prefix_map = {
                AgentType.DEEPSEEK: "DS",
                AgentType.QWEN: "QW",
                AgentType.PERPLEXITY: "PP",
            }
            prefix = prefix_map.get(agent_type, "UK")
            self.key_name = f"{prefix}-{index + 1}"

        if is_active is not None:
            self.is_active = is_active

    @property
    def value(self) -> str:
        """Get API key value, decrypting on demand.

        Resolution order:
        1. Direct value override
        2. KeyManager decryption via key_name
        3. Environment variable fallback

        Raises:
            ValueError: If no value source is available
        """
        if self._value_override is not None:
            return self._value_override

        # Try env var fallback (key_manager.py compatible)
        import os

        env_key = self._get_env_var_name()
        env_value = os.getenv(env_key)
        if env_value:
            return env_value

        if not self.key_name:
            raise ValueError("API key has no associated secret or key name")

        if self._key_manager is None:
            try:
                from backend.security.key_manager import get_key_manager

                self._key_manager = get_key_manager()
            except ImportError:
                raise ValueError(f"Cannot resolve key {self.key_name}: no KeyManager available")

        return self._key_manager.get_decrypted_key(self.key_name)

    def _get_env_var_name(self) -> str:
        """Get environment variable name for this key."""
        name_map = {
            AgentType.DEEPSEEK: "DEEPSEEK_API_KEY",
            AgentType.QWEN: "QWEN_API_KEY",
            AgentType.PERPLEXITY: "PERPLEXITY_API_KEY",
        }
        base = name_map.get(self.agent_type, "API_KEY")
        return f"{base}_{self.index + 1}" if self.index > 0 else base

    @property
    def is_usable(self) -> bool:
        """Check if key is available for use (not disabled, not cooling)."""
        if self.health == APIKeyHealth.DISABLED:
            return False
        return not self.is_cooling

    @property
    def is_available(self) -> bool:
        """Alias for is_usable (key_manager.py compatibility)."""
        return self.is_usable

    @property
    def is_cooling(self) -> bool:
        """Check if key is in cooldown period."""
        return bool(self.cooldown_until and self.cooldown_until > time.time())

    @property
    def cooldown_remaining(self) -> float:
        """Get remaining cooldown time in seconds."""
        if not self.cooldown_until:
            return 0.0
        remaining = self.cooldown_until - time.time()
        return max(0.0, remaining)

    @property
    def remaining_cooldown(self) -> float:
        """Alias for cooldown_remaining (key_manager.py compatibility)."""
        return self.cooldown_remaining

    @property
    def status(self) -> str:
        """Get human-readable status string."""
        if self.is_cooling:
            return "cooling"
        return self.health.value

    @property
    def is_active(self) -> bool:
        """Backward compatible alias for legacy code/tests."""
        return self.is_usable

    @is_active.setter
    def is_active(self, value: bool) -> None:
        """Set active state (legacy compatibility)."""
        self.health = APIKeyHealth.HEALTHY if value else APIKeyHealth.DISABLED
        if value:
            self.error_count = min(self.error_count, 1)
            self.last_error_time = None
        else:
            self.last_error_time = time.time()

    def begin_cooldown(self, duration: float, reason: str = "rate_limit") -> float:
        """Start cooldown period for this key.

        Args:
            duration: Cooldown duration in seconds
            reason: Why the key is being cooled down

        Returns:
            Actual cooldown duration applied
        """
        duration = max(0.0, duration)
        now = time.time()
        self.cooldown_until = now + duration if duration else now
        self.last_cooldown_started = now
        self.last_cooldown_reason = reason
        self.cooldown_level = min(self.cooldown_level + 1, 10)
        self.cooling_events += 1
        return duration

    def clear_cooldown(self) -> None:
        """Clear cooldown state."""
        if self.cooldown_level > 0:
            self.cooldown_level -= 1
        self.cooldown_until = None
        self.last_cooldown_started = None
        self.last_cooldown_reason = None

    def maybe_exit_cooldown(self) -> bool:
        """Check if cooldown has expired and clear it. Returns True if exited."""
        if self.cooldown_until and self.cooldown_until <= time.time():
            self.clear_cooldown()
            return True
        return False

    def mark_used(self) -> None:
        """Mark key as used (increment request count)."""
        self.last_used = time.time()
        self.requests_count += 1

    def mark_error(self, reason: str = "Unknown error") -> None:
        """Mark an error with exponential backoff cooldown.

        Implements automatic health degradation:
        - error_count >= 5: DEGRADED
        - error_count >= 10: DISABLED
        """
        self.error_count += 1
        self.last_error_time = time.time()
        self.last_cooldown_reason = reason

        # Exponential backoff: 30s, 60s, 120s, 300s, 600s
        cooldown_times = [30, 60, 120, 300, 600]
        level = min(self.cooldown_level, len(cooldown_times) - 1)
        cooldown = cooldown_times[level]

        self.cooldown_until = time.time() + cooldown
        self.last_cooldown_started = time.time()
        self.cooldown_level += 1
        self.cooling_events += 1

        if self.error_count >= 10:
            self.health = APIKeyHealth.DISABLED
        elif self.error_count >= 5:
            self.health = APIKeyHealth.DEGRADED

    def mark_success(self) -> None:
        """Mark successful use, reducing error penalties."""
        if self.error_count > 0:
            self.error_count = max(0, self.error_count - 1)

        if self.health == APIKeyHealth.DEGRADED and self.error_count < 3:
            self.health = APIKeyHealth.HEALTHY

        if self.cooldown_level > 0:
            self.cooldown_level = max(0, self.cooldown_level - 1)

    def reset(self) -> None:
        """Reset key to initial healthy state."""
        self.health = APIKeyHealth.HEALTHY
        self.error_count = 0
        self.cooldown_until = None
        self.cooldown_level = 0
        self.last_cooldown_reason = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization/API responses."""
        return {
            "agent_type": self.agent_type.value,
            "index": self.index,
            "key_name": self.key_name,
            "health": self.health.value,
            "is_available": self.is_usable,
            "error_count": self.error_count,
            "requests_count": self.requests_count,
            "remaining_cooldown": self.cooldown_remaining,
            "last_error": self.last_cooldown_reason,
            "status": self.status,
        }
