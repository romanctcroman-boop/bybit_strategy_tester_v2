"""Master key provider utilities for SecretsManager.

This module abstracts how the master encryption key is retrieved so we can
store it outside of the application environment (OS keyring, secure files,
cloud KMS, etc.). It still falls back to environment variables for
backwards compatibility, but encourages operators to move secrets into a
more secure store.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # Optional dependency - only used when installed
    import keyring  # type: ignore
except ImportError:  # pragma: no cover - optional
    keyring = None  # type: ignore


class MasterKeyProvider:
    """Fetches and persists the master encryption key from secure stores.

    Priority order:
    1. OS keyring (if the `keyring` package is available)
    2. Local secure file (default: ``~/.config/bybit/master_key``)
    3. Environment variable fallback (legacy mode)
    """

    def __init__(
        self,
        env_var: str = "MASTER_ENCRYPTION_KEY",
        keyring_service: str = "BybitStrategyTester",
        key_file: str | Path | None = None,
    ) -> None:
        self.env_var = env_var
        self.keyring_service = keyring_service
        default_file = Path("~/.config/bybit_strategy_tester/master_key").expanduser()
        self.key_file = Path(key_file).expanduser() if key_file else default_file

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_key(self) -> tuple[str | None, str | None]:
        """Return the master key string and the source it was loaded from."""
        key = self._get_from_keyring()
        if key:
            return key, "keyring"

        key = self._get_from_file()
        if key:
            return key, str(self.key_file)

        key = os.getenv(self.env_var)
        if key:
            return key, f"env:{self.env_var}"

        return None, None

    def store_in_keyring(self, key: str) -> bool:
        if not keyring:  # pragma: no cover - optional path
            return False
        keyring.set_password(self.keyring_service, self.env_var, key.strip())
        return True

    def store_in_file(self, key: str) -> Path:
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self.key_file.write_text(key.strip())
        return self.key_file

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_from_keyring(self) -> str | None:
        if not keyring:
            return None
        try:
            return keyring.get_password(self.keyring_service, self.env_var)
        except Exception:
            return None

    def _get_from_file(self) -> str | None:
        if not self.key_file.exists():
            return None
        try:
            data = self.key_file.read_text().strip()
            return data or None
        except OSError:
            return None