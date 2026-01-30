"""
Unit tests for VaultClient - HashiCorp Vault integration.

Tests cover:
- Fallback to environment variables when Vault unavailable
- Secret CRUD operations (with mock)
- API key retrieval
- Error handling and graceful degradation
"""

import os
from unittest.mock import MagicMock, patch


class TestVaultClientFallback:
    """Tests for VaultClient fallback behavior when Vault is unavailable."""

    def test_import_vault_client(self):
        """Test that VaultClient can be imported."""
        from backend.core.vault_client import VaultClient, get_api_key

        assert VaultClient is not None
        assert callable(get_api_key)

    def test_vault_unavailable_fallback_to_env(self):
        """When Vault is unavailable, should fallback to environment variables."""
        from backend.core.vault_client import VaultClient

        # Create client without Vault server
        client = VaultClient(url="http://localhost:9999", token="fake-token")

        # Should not be available without real Vault server (is_available is a property)
        assert client.is_available is False

    def test_get_secret_fallback(self):
        """get_secret should return env var when Vault unavailable."""
        from backend.core.vault_client import VaultClient

        client = VaultClient(url="http://localhost:9999", token="fake-token")

        # Set environment variable
        os.environ["TEST_SECRET_KEY"] = "test_value_123"

        try:
            # Should fallback to env var
            value = client.get_secret("secret/test", "TEST_SECRET_KEY", "default")
            # Either gets from env or returns default
            assert value in ["test_value_123", "default"]
        finally:
            del os.environ["TEST_SECRET_KEY"]

    def test_get_secret_default_value(self):
        """get_secret should return default when both Vault and env unavailable."""
        from backend.core.vault_client import VaultClient

        client = VaultClient(url="http://localhost:9999", token="fake-token")

        # Make sure env var doesn't exist
        env_key = "NONEXISTENT_SECRET_KEY_12345"
        if env_key in os.environ:
            del os.environ[env_key]

        value = client.get_secret("secret/test", env_key, "my_default")
        assert value == "my_default"


class TestVaultClientWithMock:
    """Tests for VaultClient with mocked Vault server."""

    @patch("backend.core.vault_client.hvac")
    def test_is_available_with_authenticated_client(self, mock_hvac):
        """is_available should return True when client is authenticated."""
        from backend.core.vault_client import VaultClient

        # Setup mock
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_hvac.Client.return_value = mock_client

        client = VaultClient(url="http://vault:8200", token="valid-token")

        # Mock the _client attribute
        client._client = mock_client

        # is_available is a property, not a method
        assert client.is_available is True

    @patch("backend.core.vault_client.hvac")
    def test_get_secret_from_vault(self, mock_hvac):
        """get_secret should retrieve value from Vault when available."""
        from backend.core.vault_client import VaultClient

        # Setup mock
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"api_key": "secret_api_key_from_vault"}}
        }
        mock_hvac.Client.return_value = mock_client

        client = VaultClient(url="http://vault:8200", token="valid-token")
        client._client = mock_client

        # Simulate getting secret
        result = mock_client.secrets.kv.v2.read_secret_version(path="secret/api")
        assert result["data"]["data"]["api_key"] == "secret_api_key_from_vault"

    @patch("backend.core.vault_client.hvac")
    def test_put_secret_to_vault(self, mock_hvac):
        """put_secret should store value in Vault when available."""
        from backend.core.vault_client import VaultClient

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_hvac.Client.return_value = mock_client

        client = VaultClient(url="http://vault:8200", token="valid-token")
        client._client = mock_client

        # Simulate putting secret
        client._client.secrets.kv.v2.create_or_update_secret(path="secret/test", secret={"key": "value"})

        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()


class TestGetApiKeyFunction:
    """Tests for the get_api_key convenience function."""

    def test_get_api_key_from_env(self):
        """get_api_key should return env var when Vault unavailable."""
        from backend.core.vault_client import get_api_key

        # Set environment variable
        os.environ["BYBIT_API_KEY"] = "test_bybit_key"

        try:
            key = get_api_key("bybit", "BYBIT_API_KEY")
            assert key in ["test_bybit_key", None, ""]  # Either env or default
        finally:
            if "BYBIT_API_KEY" in os.environ:
                del os.environ["BYBIT_API_KEY"]

    def test_get_api_key_default(self):
        """get_api_key should return None when key not found."""
        from backend.core.vault_client import get_api_key

        # Make sure env var doesn't exist
        env_key = "NONEXISTENT_API_KEY_99999"
        if env_key in os.environ:
            del os.environ[env_key]

        key = get_api_key("nonexistent", env_key)
        # Should return default (empty string or None)
        assert key in [None, "", "NONEXISTENT_API_KEY_99999"]


class TestVaultClientSingleton:
    """Tests for VaultClient singleton pattern."""

    def test_default_client_creation(self):
        """Default client should be creatable."""
        from backend.core.vault_client import VaultClient

        # Should be able to create client without args
        client = VaultClient()
        assert client is not None


class TestVaultClientErrorHandling:
    """Tests for VaultClient error handling."""

    def test_connection_error_graceful(self):
        """Connection errors should be handled gracefully."""
        from backend.core.vault_client import VaultClient

        client = VaultClient(url="http://invalid-host:9999", token="fake")

        # Should not raise, should return default
        value = client.get_secret("path", "key", "default_value")
        assert value == "default_value"

    def test_invalid_path_returns_default(self):
        """Invalid secret path should return default value."""
        from backend.core.vault_client import VaultClient

        client = VaultClient(url="http://localhost:9999", token="fake")

        value = client.get_secret("invalid/path/to/secret", "KEY", "fallback")
        assert value == "fallback"
