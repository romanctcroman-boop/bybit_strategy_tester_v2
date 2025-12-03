"""
Key Manager - Central service for encrypted API keys management
Provides automatic decryption and caching of API keys
"""
import os
import json
from pathlib import Path
from typing import Dict, Optional
from .crypto import CryptoManager
from .master_key_manager import get_master_key_manager


class KeyManager:
    """
    Singleton KeyManager for managing encrypted API keys.
    
    Features:
    - Automatic loading of encrypted secrets from file
    - In-memory caching for performance
    - Fallback to environment variables
    - Thread-safe singleton pattern
    """
    
    _instance: Optional['KeyManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KeyManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not KeyManager._initialized:
            # Store encrypted secrets only; decrypt lazily per request
            self._encrypted_secrets: Dict[str, str] = {}
            self._crypto: Optional[CryptoManager] = None
            self._load_crypto_manager()
            self._load_encrypted_secrets()
            KeyManager._initialized = True
    
    def _load_crypto_manager(self):
        """Initialize CryptoManager with master key"""
        try:
            master_manager = get_master_key_manager()
            self._crypto = master_manager.create_crypto_manager()
        except Exception as e:
            print(f"Warning: Failed to initialize CryptoManager: {e}")
            print("API keys will only be available from environment variables")
    
    def _get_encrypted_secrets_path(self) -> Path:
        """Get path to encrypted secrets file"""
        # Try multiple locations
        possible_paths = [
            Path("backend/config/encrypted_secrets.json"),
            Path("config/encrypted_secrets.json"),
            Path("encrypted_secrets.json"),
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        # Return default path (may not exist yet)
        return Path("backend/config/encrypted_secrets.json")
    
    def _load_encrypted_secrets(self):
        """Load and decrypt secrets from encrypted_secrets.json"""
        encrypted_path = self._get_encrypted_secrets_path()
        
        if not encrypted_path.exists():
            print(f"Note: {encrypted_path} not found. Using environment variables only.")
            return

        try:
            with open(encrypted_path, 'r', encoding='utf-8') as f:
                encrypted_secrets = json.load(f)

            # Keep encrypted payloads in memory; decrypt lazily on demand
            self._encrypted_secrets = encrypted_secrets
            print(f"✓ Registered {len(self._encrypted_secrets)} encrypted API keys")

        except Exception as e:
            print(f"Warning: Failed to load encrypted secrets: {e}")
    
    def get_decrypted_key(self, key_name: str) -> str:
        """
        Get decrypted API key by name.
        
        Priority:
        1. Environment variables (highest priority)
        2. Encrypted secrets file
        
        Args:
            key_name: Name of the key (e.g., "PERPLEXITY_API_KEY")
            
        Returns:
            Decrypted key value
            
        Raises:
            ValueError: If key not found
        """
        # Priority 1: Environment variable (allows runtime override)
        env_value = os.getenv(key_name)
        if env_value:
            return env_value
        
        # Priority 2: Encrypted secrets cache (decrypt lazily per request)
        encrypted_value = self._encrypted_secrets.get(key_name)
        if encrypted_value:
            if not self._crypto:
                raise ValueError("CryptoManager not available to decrypt secrets")
            return self._crypto.decrypt(encrypted_value)
        
        # Not found
        raise ValueError(
            f"API key '{key_name}' not found.\n"
            f"Please add it to:\n"
            f"  1. Environment variables: export {key_name}=your-key\n"
            f"  2. Or encrypted_secrets.json via Settings UI"
        )
    
    def list_keys_masked(self) -> Dict[str, str]:
        """
        List all available keys with masked values.
        
        Returns:
            Dict of key names to masked values (e.g., "pplx-...1234")
        """
        masked = {}
        
        # From encrypted cache (decrypt lazily just for masking)
        for key_name in self._encrypted_secrets.keys():
            try:
                value = self.get_decrypted_key(key_name)
            except ValueError:
                continue
            if len(value) > 12:
                masked[key_name] = f"{value[:8]}...{value[-4:]}"
            else:
                masked[key_name] = "***"
        
        # From environment (only if not already in cache)
        known_keys = [
            "PERPLEXITY_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
        ]
        
        for key_name in known_keys:
            if key_name not in masked:
                env_value = os.getenv(key_name)
                if env_value:
                    if len(env_value) > 12:
                        masked[key_name] = f"{env_value[:8]}...{env_value[-4:]}"
                    else:
                        masked[key_name] = "***"
        
        return masked
    
    def save_encrypted_keys(self, keys: Dict[str, str]):
        """
        Encrypt and save API keys to file.
        
        Args:
            keys: Dict of key names to plaintext values
            
        Raises:
            ValueError: If CryptoManager not available
        """
        if not self._crypto:
            raise ValueError("CryptoManager not available")
        
        # Encrypt all keys
        encrypted = {}
        for key_name, plaintext_value in keys.items():
            encrypted[key_name] = self._crypto.encrypt(plaintext_value)
        
        # Save to file
        encrypted_path = self._get_encrypted_secrets_path()
        encrypted_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(encrypted_path, 'w', encoding='utf-8') as f:
            json.dump(encrypted, f, indent=2)
        
        # Update encrypted cache
        for key_name, encrypted_value in encrypted.items():
            self._encrypted_secrets[key_name] = encrypted_value
        
        print(f"✓ Saved {len(keys)} encrypted keys to {encrypted_path}")
    
    def reload(self):
        """Reload encrypted secrets from file"""
        self._encrypted_secrets.clear()
        self._load_encrypted_secrets()
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (useful for testing)"""
        cls._instance = None
        cls._initialized = False

    def has_key(self, key_name: str, require_decryptable: bool = False) -> bool:
        """Check whether a key exists and (optionally) can be decrypted."""
        if os.getenv(key_name):
            return True
        if key_name in self._encrypted_secrets:
            if require_decryptable and not self._crypto:
                return False
            return True
        return False


# Global singleton instance
_key_manager: Optional[KeyManager] = None


def get_key_manager() -> KeyManager:
    """Get singleton KeyManager instance"""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager


def get_decrypted_key(key_name: str) -> str:
    """
    Convenience function to get decrypted API key.
    
    Usage:
        from backend.security.key_manager import get_decrypted_key
        
        PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")
    
    Args:
        key_name: Name of the key
        
    Returns:
        Decrypted key value
    """
    manager = get_key_manager()
    return manager.get_decrypted_key(key_name)
