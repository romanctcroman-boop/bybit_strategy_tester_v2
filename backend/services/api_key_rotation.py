"""
API Key Rotation Service.

AI Agent Security Recommendation Implementation:
- Automatic key rotation every 90 days
- Secure key storage with encryption
- Key usage monitoring
- Rotation notifications
- Audit logging
"""

import hashlib
import json
import logging
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class KeyStatus(str, Enum):
    """Status of an API key."""

    ACTIVE = "active"
    PENDING_ROTATION = "pending_rotation"
    ROTATED = "rotated"
    EXPIRED = "expired"
    REVOKED = "revoked"


class KeyProvider(str, Enum):
    """Supported API key providers."""

    DEEPSEEK = "deepseek"
    PERPLEXITY = "perplexity"
    BYBIT = "bybit"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


@dataclass
class KeyMetadata:
    """Metadata for an API key."""

    key_id: str
    provider: KeyProvider
    created_at: datetime
    expires_at: datetime
    last_used: datetime | None = None
    usage_count: int = 0
    status: KeyStatus = KeyStatus.ACTIVE
    rotated_from: str | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class RotationEvent:
    """Event for key rotation."""

    event_id: str
    key_id: str
    provider: KeyProvider
    old_key_hash: str
    new_key_hash: str
    rotated_at: datetime
    reason: str
    success: bool
    error_message: str | None = None


@dataclass
class KeyUsageStats:
    """Usage statistics for a key."""

    key_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0


class SecureKeyStorage:
    """
    Secure storage for API keys with encryption.

    Uses Fernet symmetric encryption when available,
    falls back to obfuscation otherwise.
    """

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path("backend/config/key_vault.json")
        self._encryption_key: bytes | None = None
        self._init_encryption()

    def _init_encryption(self) -> None:
        """Initialize encryption using environment key."""
        env_key = os.environ.get("ENCRYPTION_KEY")
        if env_key:
            # Derive a proper key from the environment variable
            self._encryption_key = hashlib.sha256(env_key.encode()).digest()
            logger.info("SecureKeyStorage: Encryption enabled")
        else:
            logger.warning(
                "SecureKeyStorage: ENCRYPTION_KEY not set, using obfuscation"
            )

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a string."""
        if self._encryption_key:
            try:
                import base64

                from cryptography.fernet import Fernet

                # Use first 32 bytes as Fernet key
                key = base64.urlsafe_b64encode(self._encryption_key[:32])
                f = Fernet(key)
                return f.encrypt(plaintext.encode()).decode()
            except ImportError:
                pass

        # Fallback: Simple XOR obfuscation (not secure, but better than plaintext)
        return self._obfuscate(plaintext)

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a string."""
        if self._encryption_key:
            try:
                import base64

                from cryptography.fernet import Fernet

                key = base64.urlsafe_b64encode(self._encryption_key[:32])
                f = Fernet(key)
                return f.decrypt(ciphertext.encode()).decode()
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"Decryption failed, trying obfuscation: {e}")

        return self._deobfuscate(ciphertext)

    def _obfuscate(self, text: str) -> str:
        """Simple obfuscation (XOR with fixed key)."""
        import base64

        key = b"rotation_service_key_v1"
        result = bytes([ord(c) ^ key[i % len(key)] for i, c in enumerate(text)])
        return base64.b64encode(result).decode()

    def _deobfuscate(self, text: str) -> str:
        """Reverse obfuscation."""
        import base64

        key = b"rotation_service_key_v1"
        data = base64.b64decode(text)
        return "".join(chr(b ^ key[i % len(key)]) for i, b in enumerate(data))

    def store_key(self, key_id: str, key_value: str, metadata: KeyMetadata) -> bool:
        """Store an encrypted key with metadata."""
        try:
            vault = self._load_vault()

            encrypted_key = self._encrypt(key_value)
            key_hash = hashlib.sha256(key_value.encode()).hexdigest()[:16]

            vault["keys"][key_id] = {
                "encrypted_value": encrypted_key,
                "key_hash": key_hash,
                "metadata": {
                    "provider": metadata.provider.value,
                    "created_at": metadata.created_at.isoformat(),
                    "expires_at": metadata.expires_at.isoformat(),
                    "last_used": metadata.last_used.isoformat()
                    if metadata.last_used
                    else None,
                    "usage_count": metadata.usage_count,
                    "status": metadata.status.value,
                    "rotated_from": metadata.rotated_from,
                    "description": metadata.description,
                    "tags": metadata.tags,
                },
            }

            self._save_vault(vault)
            logger.info(f"Key stored: {key_id} (hash: {key_hash})")
            return True

        except Exception as e:
            logger.error(f"Failed to store key {key_id}: {e}")
            return False

    def retrieve_key(self, key_id: str) -> tuple[str, KeyMetadata] | None:
        """Retrieve a key and its metadata."""
        try:
            vault = self._load_vault()

            if key_id not in vault["keys"]:
                return None

            entry = vault["keys"][key_id]
            key_value = self._decrypt(entry["encrypted_value"])

            meta = entry["metadata"]
            metadata = KeyMetadata(
                key_id=key_id,
                provider=KeyProvider(meta["provider"]),
                created_at=datetime.fromisoformat(meta["created_at"]),
                expires_at=datetime.fromisoformat(meta["expires_at"]),
                last_used=datetime.fromisoformat(meta["last_used"])
                if meta["last_used"]
                else None,
                usage_count=meta["usage_count"],
                status=KeyStatus(meta["status"]),
                rotated_from=meta.get("rotated_from"),
                description=meta.get("description", ""),
                tags=meta.get("tags", []),
            )

            return key_value, metadata

        except Exception as e:
            logger.error(f"Failed to retrieve key {key_id}: {e}")
            return None

    def update_usage(self, key_id: str) -> bool:
        """Update key usage statistics."""
        try:
            vault = self._load_vault()

            if key_id not in vault["keys"]:
                return False

            vault["keys"][key_id]["metadata"]["last_used"] = datetime.now().isoformat()
            vault["keys"][key_id]["metadata"]["usage_count"] += 1

            self._save_vault(vault)
            return True

        except Exception as e:
            logger.error(f"Failed to update usage for {key_id}: {e}")
            return False

    def revoke_key(self, key_id: str) -> bool:
        """Mark a key as revoked."""
        try:
            vault = self._load_vault()

            if key_id not in vault["keys"]:
                return False

            vault["keys"][key_id]["metadata"]["status"] = KeyStatus.REVOKED.value
            self._save_vault(vault)

            logger.info(f"Key revoked: {key_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke key {key_id}: {e}")
            return False

    def list_keys(self, provider: KeyProvider | None = None) -> list[KeyMetadata]:
        """List all keys, optionally filtered by provider."""
        try:
            vault = self._load_vault()
            keys = []

            for key_id, entry in vault["keys"].items():
                meta = entry["metadata"]
                key_provider = KeyProvider(meta["provider"])

                if provider and key_provider != provider:
                    continue

                keys.append(
                    KeyMetadata(
                        key_id=key_id,
                        provider=key_provider,
                        created_at=datetime.fromisoformat(meta["created_at"]),
                        expires_at=datetime.fromisoformat(meta["expires_at"]),
                        last_used=datetime.fromisoformat(meta["last_used"])
                        if meta["last_used"]
                        else None,
                        usage_count=meta["usage_count"],
                        status=KeyStatus(meta["status"]),
                        rotated_from=meta.get("rotated_from"),
                        description=meta.get("description", ""),
                        tags=meta.get("tags", []),
                    )
                )

            return keys

        except Exception as e:
            logger.error(f"Failed to list keys: {e}")
            return []

    def _load_vault(self) -> dict[str, Any]:
        """Load the key vault from disk."""
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                return json.load(f)
        return {"version": 1, "keys": {}, "rotation_history": []}

    def _save_vault(self, vault: dict[str, Any]) -> None:
        """Save the key vault to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(vault, f, indent=2)


class APIKeyRotationService:
    """
    Service for automatic API key rotation.

    Features:
    - Automatic rotation based on age
    - Manual rotation support
    - Rotation notifications
    - Audit logging
    - Key usage monitoring
    """

    def __init__(
        self,
        rotation_days: int = 90,
        warning_days: int = 14,
        storage: SecureKeyStorage | None = None,
    ):
        self.rotation_days = rotation_days
        self.warning_days = warning_days
        self.storage = storage or SecureKeyStorage()

        # Rotation callbacks
        self._rotation_callbacks: list[Callable[[RotationEvent], None]] = []
        self._warning_callbacks: list[Callable[[KeyMetadata], None]] = []

        # Statistics
        self._rotation_history: list[RotationEvent] = []
        self._usage_stats: dict[str, KeyUsageStats] = {}

        # Key fetchers for automatic rotation
        self._key_fetchers: dict[KeyProvider, Callable[[], str | None]] = {}

        logger.info(
            f"APIKeyRotationService initialized: rotation={rotation_days}d, warning={warning_days}d"
        )

    def register_key(
        self,
        key_id: str,
        key_value: str,
        provider: KeyProvider,
        description: str = "",
        tags: list[str] | None = None,
    ) -> bool:
        """Register a new API key for rotation management."""
        now = datetime.now()
        metadata = KeyMetadata(
            key_id=key_id,
            provider=provider,
            created_at=now,
            expires_at=now + timedelta(days=self.rotation_days),
            description=description,
            tags=tags or [],
        )

        success = self.storage.store_key(key_id, key_value, metadata)
        if success:
            self._usage_stats[key_id] = KeyUsageStats(key_id=key_id)
            logger.info(f"Key registered: {key_id} ({provider.value})")

        return success

    def get_key(self, key_id: str) -> str | None:
        """Get a key value and update usage statistics."""
        result = self.storage.retrieve_key(key_id)
        if result:
            key_value, metadata = result

            # Check if key is expired
            if metadata.status == KeyStatus.EXPIRED:
                logger.warning(f"Attempted to use expired key: {key_id}")
                return None

            if metadata.status == KeyStatus.REVOKED:
                logger.warning(f"Attempted to use revoked key: {key_id}")
                return None

            # Update usage
            self.storage.update_usage(key_id)
            self._record_usage(key_id, success=True)

            return key_value

        return None

    def check_rotation_needed(self) -> list[KeyMetadata]:
        """Check which keys need rotation."""
        keys = self.storage.list_keys()
        now = datetime.now()
        needs_rotation = []

        for key in keys:
            if key.status not in [KeyStatus.ACTIVE, KeyStatus.PENDING_ROTATION]:
                continue

            days_until_expiry = (key.expires_at - now).days

            if days_until_expiry <= 0:
                # Key has expired
                key.status = KeyStatus.EXPIRED
                needs_rotation.append(key)
                logger.warning(f"Key expired: {key.key_id}")

            elif days_until_expiry <= self.warning_days:
                # Key approaching expiry
                key.status = KeyStatus.PENDING_ROTATION
                needs_rotation.append(key)
                self._notify_warning(key)
                logger.info(
                    f"Key needs rotation soon: {key.key_id} ({days_until_expiry}d left)"
                )

        return needs_rotation

    def rotate_key(
        self,
        key_id: str,
        new_key_value: str,
        reason: str = "scheduled_rotation",
    ) -> RotationEvent | None:
        """Rotate a key with a new value."""
        result = self.storage.retrieve_key(key_id)
        if not result:
            logger.error(f"Cannot rotate: key {key_id} not found")
            return None

        old_key_value, old_metadata = result

        # Generate new key ID
        new_key_id = f"{old_metadata.provider.value}_{secrets.token_hex(8)}"
        now = datetime.now()

        # Create new metadata
        new_metadata = KeyMetadata(
            key_id=new_key_id,
            provider=old_metadata.provider,
            created_at=now,
            expires_at=now + timedelta(days=self.rotation_days),
            rotated_from=key_id,
            description=old_metadata.description,
            tags=old_metadata.tags,
        )

        # Store new key
        success = self.storage.store_key(new_key_id, new_key_value, new_metadata)

        # Create rotation event
        event = RotationEvent(
            event_id=secrets.token_hex(16),
            key_id=key_id,
            provider=old_metadata.provider,
            old_key_hash=hashlib.sha256(old_key_value.encode()).hexdigest()[:16],
            new_key_hash=hashlib.sha256(new_key_value.encode()).hexdigest()[:16],
            rotated_at=now,
            reason=reason,
            success=success,
            error_message=None if success else "Failed to store new key",
        )

        if success:
            # Mark old key as rotated
            self.storage.revoke_key(key_id)
            self._rotation_history.append(event)
            self._notify_rotation(event)
            logger.info(f"Key rotated: {key_id} -> {new_key_id}")
        else:
            logger.error(f"Key rotation failed: {key_id}")

        return event

    def register_rotation_callback(
        self, callback: Callable[[RotationEvent], None]
    ) -> None:
        """Register callback for rotation events."""
        self._rotation_callbacks.append(callback)

    def register_warning_callback(
        self, callback: Callable[[KeyMetadata], None]
    ) -> None:
        """Register callback for expiry warnings."""
        self._warning_callbacks.append(callback)

    def register_key_fetcher(
        self, provider: KeyProvider, fetcher: Callable[[], str | None]
    ) -> None:
        """Register a function to fetch new keys for a provider."""
        self._key_fetchers[provider] = fetcher

    def auto_rotate(self, provider: KeyProvider) -> RotationEvent | None:
        """Automatically rotate keys for a provider using registered fetcher."""
        if provider not in self._key_fetchers:
            logger.error(f"No key fetcher registered for {provider}")
            return None

        keys = self.storage.list_keys(provider)
        active_keys = [k for k in keys if k.status == KeyStatus.PENDING_ROTATION]

        if not active_keys:
            logger.info(f"No keys need rotation for {provider}")
            return None

        # Get new key from fetcher
        new_key = self._key_fetchers[provider]()
        if not new_key:
            logger.error(f"Failed to fetch new key for {provider}")
            return None

        # Rotate the oldest pending key
        oldest_key = min(active_keys, key=lambda k: k.created_at)
        return self.rotate_key(oldest_key.key_id, new_key, "auto_rotation")

    def get_rotation_history(
        self, limit: int = 100, provider: KeyProvider | None = None
    ) -> list[RotationEvent]:
        """Get rotation history."""
        history = self._rotation_history

        if provider:
            history = [e for e in history if e.provider == provider]

        return history[-limit:]

    def get_usage_stats(self, key_id: str) -> KeyUsageStats | None:
        """Get usage statistics for a key."""
        return self._usage_stats.get(key_id)

    def get_all_usage_stats(self) -> dict[str, KeyUsageStats]:
        """Get usage statistics for all keys."""
        return self._usage_stats.copy()

    def get_status(self) -> dict[str, Any]:
        """Get service status."""
        keys = self.storage.list_keys()

        status_counts = {}
        for key in keys:
            status_counts[key.status.value] = status_counts.get(key.status.value, 0) + 1

        provider_counts = {}
        for key in keys:
            provider_counts[key.provider.value] = (
                provider_counts.get(key.provider.value, 0) + 1
            )

        return {
            "enabled": True,
            "rotation_days": self.rotation_days,
            "warning_days": self.warning_days,
            "total_keys": len(keys),
            "by_status": status_counts,
            "by_provider": provider_counts,
            "total_rotations": len(self._rotation_history),
            "registered_fetchers": list(self._key_fetchers.keys()),
        }

    def _record_usage(
        self, key_id: str, success: bool, latency_ms: float = 0.0
    ) -> None:
        """Record key usage."""
        if key_id not in self._usage_stats:
            self._usage_stats[key_id] = KeyUsageStats(key_id=key_id)

        stats = self._usage_stats[key_id]
        stats.total_requests += 1

        if success:
            stats.successful_requests += 1
            stats.last_success = datetime.now()
        else:
            stats.failed_requests += 1
            stats.last_failure = datetime.now()

        # Update error rate
        if stats.total_requests > 0:
            stats.error_rate = stats.failed_requests / stats.total_requests

        # Update average latency (exponential moving average)
        if latency_ms > 0:
            alpha = 0.1
            stats.avg_latency_ms = (
                alpha * latency_ms + (1 - alpha) * stats.avg_latency_ms
            )

    def _notify_rotation(self, event: RotationEvent) -> None:
        """Notify callbacks about rotation."""
        for callback in self._rotation_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Rotation callback error: {e}")

    def _notify_warning(self, key: KeyMetadata) -> None:
        """Notify callbacks about expiry warning."""
        for callback in self._warning_callbacks:
            try:
                callback(key)
            except Exception as e:
                logger.error(f"Warning callback error: {e}")


# Global service instance
_rotation_service: APIKeyRotationService | None = None


def get_rotation_service() -> APIKeyRotationService:
    """Get or create global rotation service."""
    global _rotation_service
    if _rotation_service is None:
        _rotation_service = APIKeyRotationService()
    return _rotation_service
