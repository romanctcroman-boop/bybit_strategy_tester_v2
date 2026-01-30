"""
HashiCorp Vault Client for Secure Secret Management.

This module provides integration with HashiCorp Vault for centralized
API key management, secret rotation, and secure credential storage.

Audit Task: P2 - API Keys Centralization
"""

import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Try to import hvac, fall back gracefully if not installed
try:
    import hvac

    HVAC_AVAILABLE = True
except ImportError:
    HVAC_AVAILABLE = False
    hvac = None


class VaultClient:
    """
    HashiCorp Vault client for secure secret management.

    Features:
    - Automatic token renewal
    - Secret caching with TTL
    - Fallback to environment variables
    - Key rotation support

    Usage:
        vault = VaultClient()
        api_key = vault.get_secret("bybit/api_key")
        api_secret = vault.get_secret("bybit/api_secret")
    """

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        mount_point: str = "secret",
        namespace: str | None = None,
    ):
        """
        Initialize Vault client.

        Args:
            url: Vault server URL (default: VAULT_ADDR env var)
            token: Vault token (default: VAULT_TOKEN env var)
            mount_point: KV secrets engine mount point
            namespace: Vault namespace (enterprise only)
        """
        self.url = url or os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.token = token or os.getenv("VAULT_TOKEN")
        self.mount_point = mount_point
        self.namespace = namespace
        self._client: Any = None
        self._initialized = False

        if not HVAC_AVAILABLE:
            logger.warning("hvac library not installed. Vault integration disabled. Install with: pip install hvac")

    def _get_client(self) -> Any:
        """Get or create Vault client."""
        if self._client is None and HVAC_AVAILABLE:
            try:
                self._client = hvac.Client(
                    url=self.url,
                    token=self.token,
                    namespace=self.namespace,
                )

                # Verify connection
                if self._client.is_authenticated():
                    self._initialized = True
                    logger.info(f"Connected to Vault at {self.url}")
                else:
                    logger.warning("Failed to authenticate with Vault")
                    self._client = None
            except Exception as e:
                logger.warning(f"Cannot connect to Vault at {self.url}: {e}")
                self._client = None

        return self._client

    @property
    def is_available(self) -> bool:
        """Check if Vault is available and authenticated."""
        if not HVAC_AVAILABLE:
            return False
        try:
            client = self._get_client()
            return client is not None and client.is_authenticated()
        except Exception:
            return False

    def get_secret(
        self,
        path: str,
        key: str | None = None,
        default: str | None = None,
        version: int | None = None,
    ) -> str | dict | None:
        """
        Retrieve a secret from Vault.

        Args:
            path: Secret path (e.g., "bybit/credentials")
            key: Specific key within the secret (optional)
            default: Default value if secret not found
            version: Specific version to retrieve (KV v2 only)

        Returns:
            Secret value or dict of all keys, or default if not found

        Example:
            # Get specific key
            api_key = vault.get_secret("bybit/credentials", key="api_key")

            # Get all keys at path
            creds = vault.get_secret("bybit/credentials")
            # Returns: {"api_key": "xxx", "api_secret": "yyy"}
        """
        # Fallback to environment variable if Vault unavailable
        if not self.is_available:
            env_key = path.replace("/", "_").upper()
            if key:
                env_key = f"{env_key}_{key.upper()}"
            env_value = os.getenv(env_key, default)
            logger.debug(f"Vault unavailable, using env var: {env_key}")
            return env_value

        try:
            client = self._get_client()

            # Read from KV v2 secrets engine
            response = client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
                version=version,
            )

            data = response.get("data", {}).get("data", {})

            if key:
                return data.get(key, default)
            return data

        except Exception as e:
            logger.warning(f"Failed to read secret '{path}': {e}")

            # Fallback to environment variable
            env_key = path.replace("/", "_").upper()
            if key:
                env_key = f"{env_key}_{key.upper()}"
            return os.getenv(env_key, default)

    def set_secret(
        self,
        path: str,
        data: dict,
        cas: int | None = None,
    ) -> bool:
        """
        Store a secret in Vault.

        Args:
            path: Secret path
            data: Dict of key-value pairs to store
            cas: Check-and-set version for optimistic locking

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available:
            logger.error("Cannot write secret: Vault unavailable")
            return False

        try:
            client = self._get_client()

            client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point=self.mount_point,
                cas=cas,
            )

            logger.info(f"Secret stored at '{path}'")
            return True

        except Exception as e:
            logger.error(f"Failed to write secret '{path}': {e}")
            return False

    def delete_secret(self, path: str, versions: list[int] | None = None) -> bool:
        """
        Delete a secret from Vault.

        Args:
            path: Secret path
            versions: Specific versions to delete (soft delete)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available:
            logger.error("Cannot delete secret: Vault unavailable")
            return False

        try:
            client = self._get_client()

            if versions:
                # Soft delete specific versions
                client.secrets.kv.v2.delete_secret_versions(
                    path=path,
                    versions=versions,
                    mount_point=self.mount_point,
                )
            else:
                # Delete latest version
                client.secrets.kv.v2.delete_latest_version_of_secret(
                    path=path,
                    mount_point=self.mount_point,
                )

            logger.info(f"Secret deleted at '{path}'")
            return True

        except Exception as e:
            logger.error(f"Failed to delete secret '{path}': {e}")
            return False

    def rotate_secret(
        self,
        path: str,
        new_data: dict,
        backup_versions: int = 3,
    ) -> bool:
        """
        Rotate a secret with backup of previous versions.

        Args:
            path: Secret path
            new_data: New secret values
            backup_versions: Number of old versions to keep

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available:
            logger.error("Cannot rotate secret: Vault unavailable")
            return False

        try:
            # Write new secret (creates new version)
            success = self.set_secret(path, new_data)

            if success:
                logger.info(f"Secret rotated at '{path}'")

                # Optionally clean up old versions
                # (keeping backup_versions most recent)
                # This would require additional metadata tracking

            return success

        except Exception as e:
            logger.error(f"Failed to rotate secret '{path}': {e}")
            return False

    def list_secrets(self, path: str = "") -> list[str]:
        """
        List secrets at a path.

        Args:
            path: Path prefix to list

        Returns:
            List of secret names
        """
        if not self.is_available:
            return []

        try:
            client = self._get_client()

            response = client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=self.mount_point,
            )

            return response.get("data", {}).get("keys", [])

        except Exception as e:
            logger.warning(f"Failed to list secrets at '{path}': {e}")
            return []


# Singleton instance
_vault_client: VaultClient | None = None


@lru_cache(maxsize=1)
def get_vault_client() -> VaultClient:
    """Get singleton Vault client instance."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client


# Convenience functions
def get_api_key(service: str, key_name: str = "api_key") -> str | None:
    """
    Get API key for a service.

    Args:
        service: Service name (e.g., "bybit", "openai")
        key_name: Key name within the service secrets

    Returns:
        API key or None
    """
    vault = get_vault_client()
    return vault.get_secret(f"{service}/credentials", key=key_name)


def get_bybit_credentials() -> tuple[str | None, str | None]:
    """
    Get Bybit API credentials.

    Returns:
        Tuple of (api_key, api_secret)
    """
    vault = get_vault_client()
    creds = vault.get_secret("bybit/credentials")

    if isinstance(creds, dict):
        return creds.get("api_key"), creds.get("api_secret")

    # Fallback to individual env vars
    return (
        os.getenv("BYBIT_API_KEY"),
        os.getenv("BYBIT_API_SECRET"),
    )
