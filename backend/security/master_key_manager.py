"""
Master Key Manager - Manages encryption master keys
Provides centralized management of encryption keys for the system
"""

import logging
import os
from typing import Optional

from .crypto import CryptoManager

logger = logging.getLogger(__name__)


class MasterKeyManager:
    """Manager for encryption master keys"""

    _instance: Optional["MasterKeyManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MasterKeyManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.master_key = os.getenv("ENCRYPTION_KEY", "")
        self.crypto_manager: Optional[CryptoManager] = None

        if self.master_key:
            logger.info("✅ Master key loaded from environment")
            self.crypto_manager = CryptoManager(self.master_key)
        else:
            logger.warning("⚠️ ENCRYPTION_KEY not set - encryption disabled")

    def create_crypto_manager(self) -> CryptoManager:
        """Create a new CryptoManager instance"""
        if self.crypto_manager is not None:
            return self.crypto_manager

        return CryptoManager(self.master_key)

    def is_encryption_enabled(self) -> bool:
        """Check if encryption is enabled"""
        return bool(self.master_key)


# Global instance
_master_key_manager: Optional[MasterKeyManager] = None


def get_master_key_manager() -> MasterKeyManager:
    """Get or create the global master key manager"""
    global _master_key_manager
    if _master_key_manager is None:
        _master_key_manager = MasterKeyManager()
    return _master_key_manager


__all__ = ["MasterKeyManager", "get_master_key_manager"]
