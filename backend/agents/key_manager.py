"""
Agent Key Management Module

Contains API key management, health tracking, and cooldown logic.
Extracted from unified_agent_interface.py for better modularity.
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger

from backend.agents.models import AgentType

# Lazy import for key decryption
_key_decryptor = None


def get_key_decryptor():
    """Lazily import key decryptor to avoid circular imports."""
    global _key_decryptor
    if _key_decryptor is None:
        try:
            from backend.services.key_decryptor import KeyDecryptor

            _key_decryptor = KeyDecryptor()
        except ImportError:
            logger.warning("KeyDecryptor not available")
            _key_decryptor = None
    return _key_decryptor


class APIKeyHealth(str, Enum):
    """Health tiers for API keys."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISABLED = "disabled"


@dataclass(init=False)
class APIKey:
    """
    API key with metadata and lazy decryption.

    Supports:
    - Lazy decryption of encrypted keys
    - Health tracking (healthy/degraded/disabled)
    - Cooldown management with exponential backoff
    - Usage statistics
    """

    agent_type: AgentType
    index: int  # 0-7 for DeepSeek, 0-3 for Perplexity
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
        agent_type: AgentType,
        index: int,
        value_override: str | None = None,
        key_manager: Any | None = None,
    ):
        """
        Initialize API key.

        Args:
            agent_type: DeepSeek or Perplexity
            index: Key index (0-7 for DeepSeek, 0-3 for Perplexity)
            value_override: Direct key value (bypasses decryption)
            key_manager: Reference to APIKeyManager for decryption
        """
        self.agent_type = agent_type
        self.index = index
        self.health = APIKeyHealth.HEALTHY
        self.last_used = None
        self.error_count = 0
        self.requests_count = 0
        self.cooldown_until = None
        self.cooldown_level = 0
        self.last_cooldown_reason = None
        self.last_cooldown_started = None
        self.cooling_events = 0
        self.last_error_time = None
        self._value_override = value_override
        self._key_manager = key_manager

        # Generate key name
        prefix = "DS" if agent_type == AgentType.DEEPSEEK else "PP"
        self.key_name = f"{prefix}-{index + 1}"

    @property
    def value(self) -> str | None:
        """Get decrypted key value (lazy)."""
        if self._value_override:
            return self._value_override

        # Try decryption via key manager
        if self._key_manager is not None:
            return self._key_manager._decrypt_key(self)

        # Fallback to env vars
        env_key = self._get_env_var_name()
        return os.getenv(env_key)

    def _get_env_var_name(self) -> str:
        """Get environment variable name for this key."""
        if self.agent_type == AgentType.DEEPSEEK:
            return f"DEEPSEEK_API_KEY_{self.index + 1}"
        else:
            return f"PERPLEXITY_API_KEY_{self.index + 1}"

    @property
    def is_available(self) -> bool:
        """Check if key is available for use."""
        if self.health == APIKeyHealth.DISABLED:
            return False
        if self.cooldown_until and time.time() < self.cooldown_until:
            return False
        if self.value is None:
            return False
        return True

    @property
    def remaining_cooldown(self) -> float:
        """Get remaining cooldown time in seconds."""
        if not self.cooldown_until:
            return 0
        remaining = self.cooldown_until - time.time()
        return max(0, remaining)

    def mark_used(self):
        """Mark key as used."""
        self.last_used = time.time()
        self.requests_count += 1

    def mark_error(self, reason: str = "Unknown error"):
        """
        Mark an error on this key.

        Implements exponential backoff cooldown.
        """
        self.error_count += 1
        self.last_error_time = time.time()
        self.last_cooldown_reason = reason

        # Cooldown levels: 30s, 60s, 120s, 300s, 600s
        cooldown_times = [30, 60, 120, 300, 600]
        level = min(self.cooldown_level, len(cooldown_times) - 1)
        cooldown = cooldown_times[level]

        self.cooldown_until = time.time() + cooldown
        self.last_cooldown_started = time.time()
        self.cooldown_level += 1
        self.cooling_events += 1

        # If too many errors, degrade health
        if self.error_count >= 5:
            self.health = APIKeyHealth.DEGRADED
        if self.error_count >= 10:
            self.health = APIKeyHealth.DISABLED

    def mark_success(self):
        """Mark successful use, reducing error penalties."""
        if self.error_count > 0:
            self.error_count = max(0, self.error_count - 1)

        if self.health == APIKeyHealth.DEGRADED and self.error_count < 3:
            self.health = APIKeyHealth.HEALTHY

        # Reset cooldown level on success
        if self.cooldown_level > 0:
            self.cooldown_level = max(0, self.cooldown_level - 1)

    def reset(self):
        """Reset key to initial state."""
        self.health = APIKeyHealth.HEALTHY
        self.error_count = 0
        self.cooldown_until = None
        self.cooldown_level = 0
        self.last_cooldown_reason = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "agent_type": self.agent_type.value,
            "index": self.index,
            "key_name": self.key_name,
            "health": self.health.value,
            "is_available": self.is_available,
            "error_count": self.error_count,
            "requests_count": self.requests_count,
            "remaining_cooldown": self.remaining_cooldown,
            "last_error": self.last_cooldown_reason,
        }


class APIKeyManager:
    """
    Manages API keys for agents with health tracking and rotation.

    Features:
    - Lazy key decryption
    - Health-aware key selection
    - Automatic cooldown management
    - Thread-safe operations
    - Metrics collection
    """

    # Key counts per agent type
    KEY_COUNTS = {
        AgentType.DEEPSEEK: 8,
        AgentType.PERPLEXITY: 4,
    }

    def __init__(self):
        self.keys: dict[AgentType, list[APIKey]] = {}
        self._initialized = False
        self._lock = asyncio.Lock()
        self._decryption_cache: dict[str, str] = {}

        self._initialize_keys()

    def _initialize_keys(self):
        """Initialize all API keys."""
        for agent_type in [AgentType.DEEPSEEK, AgentType.PERPLEXITY]:
            count = self.KEY_COUNTS.get(agent_type, 0)
            self.keys[agent_type] = [
                APIKey(
                    agent_type=agent_type,
                    index=i,
                    key_manager=self,
                )
                for i in range(count)
            ]
        self._initialized = True

    def _decrypt_key(self, key: APIKey) -> str | None:
        """
        Decrypt a key using KeyDecryptor.

        Uses caching to avoid repeated decryption.
        """
        cache_key = f"{key.agent_type.value}_{key.index}"

        if cache_key in self._decryption_cache:
            return self._decryption_cache[cache_key]

        decryptor = get_key_decryptor()
        if not decryptor:
            # Fallback to env var
            return key.value

        try:
            # Try encrypted first, then plaintext
            env_name = key._get_env_var_name()
            encrypted_name = f"{env_name}_ENCRYPTED"

            encrypted_value = os.getenv(encrypted_name)
            if encrypted_value:
                decrypted = decryptor.decrypt(encrypted_value)
                self._decryption_cache[cache_key] = decrypted
                return decrypted

            # Try plaintext
            value = os.getenv(env_name)
            if value:
                self._decryption_cache[cache_key] = value
                return value

        except Exception as e:
            logger.warning(f"Failed to decrypt key {key.key_name}: {e}")

        return None

    async def get_available_key(
        self,
        agent_type: AgentType,
        exclude: list[int] | None = None,
    ) -> APIKey | None:
        """
        Get the best available key for the agent type.

        Selection priority:
        1. Healthy keys with lowest usage
        2. Degraded keys if no healthy available
        3. None if all disabled/cooling
        """
        async with self._lock:
            exclude = exclude or []
            keys = self.keys.get(agent_type, [])

            # Filter available keys
            available = [k for k in keys if k.is_available and k.index not in exclude]

            if not available:
                return None

            # Sort by health (HEALTHY first) then by requests_count
            available.sort(
                key=lambda k: (
                    0 if k.health == APIKeyHealth.HEALTHY else 1,
                    k.requests_count,
                )
            )

            return available[0]

    def get_key_by_index(
        self,
        agent_type: AgentType,
        index: int,
    ) -> APIKey | None:
        """Get a specific key by index."""
        keys = self.keys.get(agent_type, [])
        for key in keys:
            if key.index == index:
                return key
        return None

    def get_all_keys(self, agent_type: AgentType) -> list[APIKey]:
        """Get all keys for an agent type."""
        return self.keys.get(agent_type, [])

    def get_status(self) -> dict:
        """Get status of all keys."""
        result = {}
        for agent_type, keys in self.keys.items():
            result[agent_type.value] = {
                "total": len(keys),
                "healthy": sum(1 for k in keys if k.health == APIKeyHealth.HEALTHY),
                "degraded": sum(1 for k in keys if k.health == APIKeyHealth.DEGRADED),
                "disabled": sum(1 for k in keys if k.health == APIKeyHealth.DISABLED),
                "available": sum(1 for k in keys if k.is_available),
                "keys": [k.to_dict() for k in keys],
            }
        return result

    def reset_all(self, agent_type: AgentType | None = None):
        """Reset all keys or keys for specific agent type."""
        types_to_reset = [agent_type] if agent_type else list(self.keys.keys())

        for at in types_to_reset:
            for key in self.keys.get(at, []):
                key.reset()

        self._decryption_cache.clear()


# Singleton instance
_key_manager: APIKeyManager | None = None


def get_key_manager() -> APIKeyManager:
    """Get the global APIKeyManager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = APIKeyManager()
    return _key_manager
