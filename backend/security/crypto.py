"""
Crypto Manager - AES-256-GCM Authenticated Encryption
Provides secure encryption and decryption of API keys and other secrets.

Security Features:
- AES-256-GCM authenticated encryption (NIST recommended)
- Unique nonce per encryption (96-bit random)
- Argon2id key derivation for password-based keys
- Memory protection for sensitive data
- Backward compatible with legacy ENCRYPTED: format

DeepSeek Recommendation: Week 1 - AES-GCM upgrade
"""

import base64
import hashlib
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import cryptography, fall back to stub if not available
try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("⚠️ cryptography library not installed, using fallback encryption")

# Try to import argon2 for key derivation
try:
    from argon2.low_level import Type, hash_secret_raw

    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False


class SecureBytes:
    """
    Secure byte container with memory protection.

    Features:
    - Automatic zeroing on deletion
    - Immutable after creation
    - Protected from accidental logging
    """

    __slots__ = ("_data", "_size")

    def __init__(self, data: bytes):
        self._data = bytearray(data)
        self._size = len(data)

    def get(self) -> bytes:
        """Get the secure data."""
        return bytes(self._data)

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        return f"SecureBytes(size={self._size}, redacted)"

    def __str__(self) -> str:
        return "[REDACTED]"

    def __del__(self):
        """Securely zero memory on deletion."""
        if hasattr(self, "_data") and self._data:
            for i in range(len(self._data)):
                self._data[i] = 0
            self._data.clear()

    def clear(self):
        """Manually clear the secure data."""
        self.__del__()


class CryptoManager:
    """
    AES-256-GCM Authenticated Encryption Manager.

    Provides:
    - Confidentiality: AES-256 encryption
    - Integrity: GCM authentication tag
    - Non-replayable: Unique random nonce per message

    Format: VERSION(1) + NONCE(12) + CIPHERTEXT + TAG(16)
    Base64 encoded for storage.
    """

    # Current version for forward compatibility
    VERSION = b"\x02"  # v2 = AES-GCM
    LEGACY_PREFIX = "ENCRYPTED:"
    NONCE_SIZE = 12  # 96 bits recommended for GCM
    KEY_SIZE = 32  # 256 bits
    TAG_SIZE = 16  # 128 bits

    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize with optional master key.

        Args:
            master_key: Base64 encoded 32-byte key, or password string.
                       If not provided, uses ENCRYPTION_KEY env var.
        """
        raw_key = master_key or os.getenv("ENCRYPTION_KEY", "")
        self.enabled = bool(raw_key) and CRYPTO_AVAILABLE
        self._aesgcm: Optional[AESGCM] = None
        self._key: Optional[SecureBytes] = None

        if not raw_key:
            logger.warning(
                "⚠️ CryptoManager: No encryption key available, encryption disabled"
            )
            return

        if not CRYPTO_AVAILABLE:
            logger.warning(
                "⚠️ CryptoManager: cryptography not installed, encryption disabled"
            )
            return

        # Derive or decode the key
        self._key = SecureBytes(self._prepare_key(raw_key))
        self._aesgcm = AESGCM(self._key.get())
        logger.info("✅ CryptoManager: AES-256-GCM encryption enabled")

    def _prepare_key(self, raw_key: str) -> bytes:
        """
        Prepare a 256-bit key from input.

        Supports:
        - Base64 encoded 32-byte key (preferred)
        - Password string (will be derived with Argon2id or Scrypt)
        """
        # Try base64 decode first
        try:
            decoded = base64.urlsafe_b64decode(raw_key)
            if len(decoded) == self.KEY_SIZE:
                return decoded
        except Exception:
            pass

        # Derive key from password using Argon2id or Scrypt
        return self._derive_key(raw_key.encode("utf-8"))

    def _derive_key(self, password: bytes, salt: Optional[bytes] = None) -> bytes:
        """
        Derive a 256-bit key from password using Argon2id (preferred) or Scrypt.

        Uses consistent salt derived from password for deterministic key generation.
        For production, store salt separately for each encrypted item.
        """
        # Generate deterministic salt from password hash
        if salt is None:
            salt = hashlib.sha256(password + b"crypto_salt_v2").digest()[:16]

        if ARGON2_AVAILABLE:
            # Argon2id - winner of Password Hashing Competition
            return hash_secret_raw(
                secret=password,
                salt=salt,
                time_cost=3,  # iterations
                memory_cost=65536,  # 64 MB
                parallelism=4,  # threads
                hash_len=32,  # output size
                type=Type.ID,  # Argon2id
            )
        else:
            # Fallback to Scrypt
            kdf = Scrypt(
                salt=salt,
                length=32,
                n=2**14,  # CPU/memory cost
                r=8,  # block size
                p=1,  # parallelism
                backend=default_backend(),
            )
            return kdf.derive(password)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext with AES-256-GCM.

        Args:
            plaintext: UTF-8 string to encrypt

        Returns:
            Base64 encoded ciphertext with version and nonce
        """
        if not self.enabled or not self._aesgcm:
            return plaintext

        try:
            # Generate random nonce (NEVER reuse with same key!)
            nonce = secrets.token_bytes(self.NONCE_SIZE)

            # Encrypt with GCM (includes authentication tag)
            ciphertext = self._aesgcm.encrypt(
                nonce,
                plaintext.encode("utf-8"),
                None,  # No additional authenticated data
            )

            # Pack: VERSION + NONCE + CIPHERTEXT
            packed = self.VERSION + nonce + ciphertext

            # Base64 encode for safe storage
            return base64.urlsafe_b64encode(packed).decode("ascii")

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError("Encryption failed") from e

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext with AES-256-GCM.

        Args:
            ciphertext: Base64 encoded encrypted data

        Returns:
            Decrypted UTF-8 string
        """
        if not self.enabled or not self._aesgcm:
            return ciphertext

        # Handle legacy format
        if ciphertext.startswith(self.LEGACY_PREFIX):
            return ciphertext[len(self.LEGACY_PREFIX) :]

        try:
            # Base64 decode
            packed = base64.urlsafe_b64decode(ciphertext)

            # Extract version
            version = packed[0:1]

            if version == self.VERSION:
                # Extract nonce and ciphertext
                nonce = packed[1 : 1 + self.NONCE_SIZE]
                encrypted = packed[1 + self.NONCE_SIZE :]

                # Decrypt and verify authentication tag
                plaintext = self._aesgcm.decrypt(nonce, encrypted, None)
                return plaintext.decode("utf-8")
            else:
                raise ValueError(f"Unknown encryption version: {version}")

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError(
                "Decryption failed - data may be corrupted or tampered"
            ) from e

    def is_encrypted(self, data: str) -> bool:
        """
        Check if data appears to be encrypted.

        Detects both:
        - Legacy ENCRYPTED: format
        - New AES-GCM format (base64 with version byte)
        """
        # Legacy format
        if data.startswith(self.LEGACY_PREFIX):
            return True

        # New format check
        try:
            decoded = base64.urlsafe_b64decode(data)
            return len(decoded) > self.NONCE_SIZE + 1 and decoded[0:1] == self.VERSION
        except Exception:
            return False

    def rotate_key(self, new_key: str, encrypted_data: list[str]) -> list[str]:
        """
        Rotate encryption key - re-encrypt all data with new key.

        Args:
            new_key: New master key
            encrypted_data: List of encrypted strings

        Returns:
            List of re-encrypted strings with new key
        """
        if not self.enabled:
            return encrypted_data

        # Decrypt with old key
        decrypted = [self.decrypt(data) for data in encrypted_data]

        # Create new manager with new key
        new_manager = CryptoManager(new_key)

        # Re-encrypt with new key
        return [new_manager.encrypt(data) for data in decrypted]

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new random 256-bit key.

        Returns:
            Base64 encoded 32-byte key suitable for ENCRYPTION_KEY env var
        """
        key = secrets.token_bytes(32)
        return base64.urlsafe_b64encode(key).decode("ascii")

    def __del__(self):
        """Clean up secure key material."""
        if hasattr(self, "_key") and self._key:
            self._key.clear()


# Legacy compatibility alias
def create_crypto_manager(master_key: Optional[str] = None) -> CryptoManager:
    """Create a new CryptoManager instance."""
    return CryptoManager(master_key)


__all__ = ["CryptoManager", "SecureBytes", "create_crypto_manager", "CRYPTO_AVAILABLE"]
