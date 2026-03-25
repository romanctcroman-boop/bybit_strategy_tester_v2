"""
Agent Key Management Module (DEPRECATED)

.. deprecated:: 2026-02-12
    Use :class:`backend.agents.api_key_pool.APIKeyPoolManager` instead.
    This module is kept for backward compatibility only.

Contains legacy APIKeyManager for managing key pools with health tracking
and rotation. The canonical implementation is now in
``backend.agents.api_key_pool.APIKeyPoolManager`` which adds:
- Token-aware rate limiting
- Multi-level health scoring (not just enum states)
- Alert callback registration
- Pool-level metrics aggregation
"""

import asyncio
import os
import warnings

from loguru import logger

from backend.agents.key_models import APIKey, APIKeyHealth
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
        warnings.warn(
            "APIKeyManager in key_manager.py is deprecated. Use backend.agents.api_key_pool.APIKeyPoolManager instead.",
            DeprecationWarning,
            stacklevel=2,
        )
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
