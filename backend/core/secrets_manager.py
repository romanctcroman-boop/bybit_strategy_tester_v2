"""
Secrets Manager
===============

Centralized secrets management with encryption at rest.

Features:
- AES-256-GCM encryption with authenticated data
- Audit logging for secrets access
- Key rotation support
- Environment-based configuration

Security:
- Master key stored in environment variable (rotate monthly)
- Secrets encrypted at rest in .secrets.enc file
- Audit trail for compliance

Usage:
    secrets = SecretsManager()
    api_key = secrets.get_secret("DEEPSEEK_API_KEY")
    secrets.rotate_master_key()  # Rotate encryption key
"""

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger

from backend.core.master_key_provider import MasterKeyProvider

CURRENT_ENCRYPTION_VERSION = "AES256_GCM_V1"
LEGACY_ENCRYPTION_VERSION = "FERNET_V1"


@dataclass
class SecretRecord:
    """Structured representation of an encrypted secret."""

    version: str
    key_name: str
    nonce: str
    ciphertext: str
    created_at: str
    updated_at: str
    algorithm: str = "AES-256-GCM"
    rotation_id: str | None = None


class SecretsManager:
    """Centralized secrets management with encryption"""
    
    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------
    def _normalize_master_key(self, master_key: str) -> bytes:
        key = master_key.strip()
        decoders = (
            base64.urlsafe_b64decode,
            base64.b64decode,
            lambda v: bytes.fromhex(v),
        )

        for decoder in decoders:
            try:
                raw = decoder(key)
                if len(raw) in (16, 24, 32):
                    return raw
            except Exception:
                continue

        raw = key.encode()
        if len(raw) in (16, 24, 32):
            return raw

        raise ValueError(
            "Master key must decode to 16/24/32 bytes for AES-GCM. "
            "Ensure you are using a base64/hex encoded 256-bit key."
        )

    @staticmethod
    def _looks_like_fernet_key(key: str) -> bool:
        key = key.strip()
        return len(key) == 44 and key.endswith("=")

    def _build_aad(self, key_name: str, rotation_id: str | None = None) -> bytes:
        rid = rotation_id or self.rotation_id
        return f"{key_name}|{rid}".encode()

    def _encrypt_secret_record(
        self,
        key_name: str,
        secret: str,
        *,
        cipher: AESGCM | None = None,
        rotation_id: str | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        cipher = cipher or self.aead_cipher
        rotation_id = rotation_id or self.rotation_id
        nonce = secrets.token_bytes(12)
        aad = self._build_aad(key_name, rotation_id)
        ciphertext = cipher.encrypt(nonce, secret.encode(), aad)
        timestamp = created_at or datetime.now(UTC).isoformat()
        return {
            "version": CURRENT_ENCRYPTION_VERSION,
            "key_name": key_name,
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "created_at": timestamp,
            "updated_at": datetime.now(UTC).isoformat(),
            "algorithm": "AES-256-GCM",
            "rotation_id": rotation_id,
        }

    def _decrypt_secret_entry(
        self,
        key_name: str,
        entry: Any,
    ) -> tuple[str, dict[str, Any] | None]:
        """Return plaintext and optional upgraded record."""

        if isinstance(entry, dict):
            version = entry.get("version")
            if version == CURRENT_ENCRYPTION_VERSION:
                nonce = base64.b64decode(entry["nonce"])
                ciphertext = base64.b64decode(entry["ciphertext"])
                aad = self._build_aad(entry.get("key_name", key_name), entry.get("rotation_id"))
                plaintext = self.aead_cipher.decrypt(nonce, ciphertext, aad).decode()
                return plaintext, None
            if version == LEGACY_ENCRYPTION_VERSION and "payload" in entry:
                plaintext = self._decrypt_legacy_cipher(entry["payload"])
                upgraded = self._encrypt_secret_record(key_name, plaintext)
                return plaintext, upgraded

        if isinstance(entry, str):
            # Legacy string (Fernet) or JSON serialized record
            try:
                parsed = json.loads(entry)
                if isinstance(parsed, dict) and parsed.get("version"):
                    return self._decrypt_secret_entry(key_name, parsed)
            except json.JSONDecodeError:
                pass

            plaintext = self._decrypt_legacy_cipher(entry)
            upgraded = self._encrypt_secret_record(key_name, plaintext)
            return plaintext, upgraded

        raise ValueError("Unsupported secret record format")

    def _decrypt_legacy_cipher(self, payload: str) -> str:
        if not self.legacy_cipher:
            raise ValueError("Legacy secret detected but legacy cipher is disabled")
        decrypted = self.legacy_cipher.decrypt(payload.encode())
        return decrypted.decode()

    def __init__(
        self,
        secrets_file: str = ".secrets.enc",
        master_key_env: str = "MASTER_ENCRYPTION_KEY",
        audit_log_path: str = "logs/secrets_audit.log",
        enable_legacy_decrypt: bool = True,
    ):
        """
        Initialize secrets manager
        
        Args:
            secrets_file: Path to encrypted secrets file
            master_key_env: Environment variable for master encryption key
            audit_log_path: Path to audit log file
        """
        self.secrets_file = Path(secrets_file)
        self.master_key_env = master_key_env
        self.audit_log_path = Path(audit_log_path)
        self.enable_legacy_decrypt = enable_legacy_decrypt

        self.master_key_provider = MasterKeyProvider(env_var=master_key_env)
        master_key, source = self.master_key_provider.get_key()
        if not master_key:
            logger.warning(
                "⚠️ Master encryption key not found in keyring/file/env. "
                "Generating temporary key (NOT for production!)."
            )
            master_key = Fernet.generate_key().decode()
            logger.warning("🔑 Temporary key generated. Store it securely via keyring or config file!")
            source = "generated"

        self.master_key_source = source or "unknown"
        self.master_key_bytes = self._normalize_master_key(master_key)
        self.rotation_id = hashlib.sha256(self.master_key_bytes).hexdigest()[:16]
        self.aead_cipher = AESGCM(self.master_key_bytes)

        self.legacy_cipher: Fernet | None = None
        if enable_legacy_decrypt and self._looks_like_fernet_key(master_key):
            try:
                self.legacy_cipher = Fernet(master_key.encode() if isinstance(master_key, str) else master_key)
            except Exception:
                self.legacy_cipher = None
        
        # Create audit log directory
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ SecretsManager initialized (file: {self.secrets_file})")
    
    def encrypt_secret(self, secret: str, *, key_name: str = "ANONYMOUS") -> dict[str, Any]:
        """Encrypt a secret using AES-256-GCM and return a structured record."""
        try:
            return self._encrypt_secret_record(key_name, secret)
        except Exception as e:
            logger.error(f"❌ Failed to encrypt secret: {e}")
            raise
    
    def decrypt_secret(self, encrypted_secret: Any, *, key_name: str | None = None) -> str:
        """
        Decrypt an encrypted secret record or legacy string."""

        try:
            plaintext, _ = self._decrypt_secret_entry(key_name or "ANONYMOUS", encrypted_secret)
            return plaintext
        except InvalidToken:
            logger.error("❌ Invalid encryption token - master key may have changed")
            raise ValueError("Failed to decrypt secret - invalid master key")
        except Exception as e:
            logger.error(f"❌ Failed to decrypt secret: {e}")
            raise
    
    def get_secret(self, key_name: str, fallback_env: bool = True) -> str | None:
        """
        Get a secret by name
        
        Args:
            key_name: Name of the secret (e.g., "DEEPSEEK_API_KEY")
            fallback_env: If True, fallback to environment variable if not in encrypted storage
        
        Returns:
            Decrypted secret or None if not found
        """
        start_time = time.time()
        
        try:
            # Try to read from encrypted storage
            if self.secrets_file.exists():
                encrypted_data = self._read_encrypted_storage()
                if key_name in encrypted_data:
                    secret, upgraded = self._decrypt_secret_entry(key_name, encrypted_data[key_name])
                    if upgraded:
                        encrypted_data[key_name] = upgraded
                        self._write_encrypted_storage(encrypted_data)
                        logger.info(f"🔁 Auto-migrated secret '{key_name}' to AES-256-GCM format")
                    self._audit_log("GET_SECRET", key_name, success=True, elapsed=time.time() - start_time)
                    return secret
            
            # Fallback to environment variable
            if fallback_env:
                secret = os.getenv(key_name)
                if secret:
                    logger.debug(f"📝 Secret '{key_name}' loaded from environment variable")
                    self._audit_log("GET_SECRET_ENV", key_name, success=True, elapsed=time.time() - start_time)
                    return secret
            
            logger.warning(f"⚠️ Secret '{key_name}' not found")
            self._audit_log("GET_SECRET", key_name, success=False, elapsed=time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get secret '{key_name}': {e}")
            self._audit_log("GET_SECRET_ERROR", key_name, success=False, error=str(e))
            raise
    
    def set_secret(self, key_name: str, secret: str) -> None:
        """
        Store a secret in encrypted storage
        
        Args:
            key_name: Name of the secret
            secret: Plain text secret to encrypt and store
        """
        start_time = time.time()
        
        try:
            # Read existing secrets
            encrypted_data = {}
            if self.secrets_file.exists():
                encrypted_data = self._read_encrypted_storage()
            
            # Encrypt and store new secret
            encrypted_data[key_name] = self.encrypt_secret(secret, key_name=key_name)
            
            # Write to file
            self._write_encrypted_storage(encrypted_data)
            
            logger.info(f"✅ Secret '{key_name}' stored successfully")
            self._audit_log("SET_SECRET", key_name, success=True, elapsed=time.time() - start_time)
            
        except Exception as e:
            logger.error(f"❌ Failed to set secret '{key_name}': {e}")
            self._audit_log("SET_SECRET_ERROR", key_name, success=False, error=str(e))
            raise
    
    def delete_secret(self, key_name: str) -> bool:
        """
        Delete a secret from encrypted storage
        
        Args:
            key_name: Name of the secret to delete
        
        Returns:
            True if deleted, False if not found
        """
        try:
            if not self.secrets_file.exists():
                return False
            
            encrypted_data = self._read_encrypted_storage()
            if key_name in encrypted_data:
                del encrypted_data[key_name]
                self._write_encrypted_storage(encrypted_data)
                logger.info(f"✅ Secret '{key_name}' deleted")
                self._audit_log("DELETE_SECRET", key_name, success=True)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to delete secret '{key_name}': {e}")
            self._audit_log("DELETE_SECRET_ERROR", key_name, success=False, error=str(e))
            raise
    
    def list_secrets(self) -> list[str]:
        """
        List all secret names in encrypted storage
        
        Returns:
            List of secret names (keys only, not values)
        """
        try:
            if not self.secrets_file.exists():
                return []
            
            encrypted_data = self._read_encrypted_storage()
            return list(encrypted_data.keys())
            
        except Exception as e:
            logger.error(f"❌ Failed to list secrets: {e}")
            return []
    
    def rotate_master_key(self, new_master_key: str) -> None:
        """Rotate master encryption key and re-encrypt all secrets."""

        start_time = time.time()

        try:
            logger.info("🔄 Starting master key rotation...")

            if not self.secrets_file.exists():
                logger.warning("⚠️ No secrets file found - nothing to rotate")
                return

            encrypted_data = self._read_encrypted_storage()
            decrypted_secrets: dict[str, str] = {}

            for key_name, encrypted_value in encrypted_data.items():
                plaintext, _ = self._decrypt_secret_entry(key_name, encrypted_value)
                decrypted_secrets[key_name] = plaintext

            logger.info(f"📝 Decrypted {len(decrypted_secrets)} secrets with old key")

            new_key_bytes = self._normalize_master_key(new_master_key)
            new_cipher = AESGCM(new_key_bytes)
            new_rotation_id = hashlib.sha256(new_key_bytes).hexdigest()[:16]

            new_encrypted_data = {}
            for key_name, secret in decrypted_secrets.items():
                record = self._encrypt_secret_record(
                    key_name,
                    secret,
                    cipher=new_cipher,
                    rotation_id=new_rotation_id,
                )
                new_encrypted_data[key_name] = record

            backup_path = self.secrets_file.with_suffix(f".enc.backup.{int(time.time())}")
            if self.secrets_file.exists():
                self.secrets_file.rename(backup_path)
                logger.info(f"💾 Backup created: {backup_path}")

            with open(self.secrets_file, "w", encoding="utf-8") as f:
                json.dump(new_encrypted_data, f, indent=2)

            self.master_key_bytes = new_key_bytes
            self.aead_cipher = new_cipher
            self.rotation_id = new_rotation_id
            if self.enable_legacy_decrypt:
                try:
                    self.legacy_cipher = Fernet(new_master_key)
                except Exception:
                    self.legacy_cipher = None

            logger.info(f"✅ Master key rotation completed in {time.time() - start_time:.2f}s")
            logger.warning(f"⚠️ Update secure store/{self.master_key_env} with the new key!")
            self._audit_log("ROTATE_MASTER_KEY", "ALL_SECRETS", success=True, elapsed=time.time() - start_time)

        except Exception as e:
            logger.error(f"❌ Master key rotation failed: {e}")
            self._audit_log("ROTATE_MASTER_KEY_ERROR", "ALL_SECRETS", success=False, error=str(e))
            raise
    
    def migrate_from_env(self, key_names: list[str]) -> int:
        """
        Migrate secrets from environment variables to encrypted storage
        
        Args:
            key_names: List of environment variable names to migrate
        
        Returns:
            Number of secrets migrated
        """
        migrated = 0
        
        for key_name in key_names:
            try:
                secret = os.getenv(key_name)
                if secret:
                    self.set_secret(key_name, secret)
                    migrated += 1
                    logger.info(f"✅ Migrated '{key_name}' from environment")
                else:
                    logger.warning(f"⚠️ Environment variable '{key_name}' not found")
            except Exception as e:
                logger.error(f"❌ Failed to migrate '{key_name}': {e}")
        
        logger.info(f"✅ Migration complete: {migrated}/{len(key_names)} secrets migrated")
        return migrated
    
    def _read_encrypted_storage(self) -> dict[str, Any]:
        """Read encrypted secrets from file"""
        try:
            with open(self.secrets_file) as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"❌ Corrupted secrets file: {e}")
            raise ValueError(f"Corrupted secrets file: {e}")
    
    def _write_encrypted_storage(self, data: dict[str, Any]) -> None:
        """Write encrypted secrets to file"""
        try:
            with open(self.secrets_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to write secrets file: {e}")
            raise
    
    def _audit_log(
        self,
        action: str,
        key_name: str,
        success: bool,
        elapsed: float = 0.0,
        error: str | None = None
    ) -> None:
        """Write audit log entry"""
        try:
            log_entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "action": action,
                "key_name": key_name,
                "success": success,
                "elapsed_ms": round(elapsed * 1000, 2),
                "error": error
            }
            
            with open(self.audit_log_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            logger.error(f"❌ Failed to write audit log: {e}")


# Singleton instance
_secrets_manager_instance = None


def get_secrets_manager() -> SecretsManager:
    """Get singleton SecretsManager instance"""
    global _secrets_manager_instance
    if _secrets_manager_instance is None:
        _secrets_manager_instance = SecretsManager()
    return _secrets_manager_instance


# Convenience functions
def get_secret(key_name: str, fallback_env: bool = True) -> str | None:
    """Get a secret by name"""
    return get_secrets_manager().get_secret(key_name, fallback_env)


def set_secret(key_name: str, secret: str) -> None:
    """Store a secret"""
    return get_secrets_manager().set_secret(key_name, secret)


if __name__ == "__main__":
    # Example usage
    import sys
    
    # Generate master key
    if len(sys.argv) > 1 and sys.argv[1] == "generate-key":
        master_key = Fernet.generate_key().decode()
        print("\n🔑 Generated Master Encryption Key:\n")
        print(f"   {master_key}\n")
        print("⚠️  Set this as environment variable:")
        print(f"   export MASTER_ENCRYPTION_KEY='{master_key}'")
        print(f"   (Windows: set MASTER_ENCRYPTION_KEY={master_key})\n")
        sys.exit(0)
    
    # Test encryption/decryption
    print("🔐 Testing SecretsManager...\n")
    
    sm = SecretsManager()
    
    # Store test secret
    sm.set_secret("TEST_SECRET", "my-secure-api-key-123")
    print("✅ Stored test secret")
    
    # Retrieve test secret
    retrieved = sm.get_secret("TEST_SECRET")
    print(f"✅ Retrieved: {retrieved}")
    
    # List secrets
    secrets = sm.list_secrets()
    print(f"✅ Secrets in storage: {secrets}")
    
    # Delete test secret
    sm.delete_secret("TEST_SECRET")
    print("✅ Deleted test secret")
    
    print("\n✅ All tests passed!")
