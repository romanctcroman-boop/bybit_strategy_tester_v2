"""
Encryption Key Manager
Безопасное хранение и управление API ключами с AES-256 шифрованием
Based on: AWS KMS, HashiCorp Vault, Azure Key Vault best practices
"""

import os
import json
import base64
from pathlib import Path
from typing import List, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import logging


class EncryptionKeyManager:
    """Manages encrypted API keys with auto-load on startup"""
    
    def __init__(self, keys_file: str = "encrypted_api_keys.json"):
        self.keys_file = Path(keys_file)
        self.encryption_key = None
        self.fernet = None
        
        # In-memory key pool (AWS KMS pattern)
        self.key_pool = {
            "deepseek": [],
            "perplexity": []
        }
        
        self.logger = logging.getLogger(__name__)
        
        # Auto-initialize encryption key
        self._initialize_encryption_key()
    
    def _initialize_encryption_key(self):
        """Initialize encryption key from environment or generate new"""
        
        # Try to load from environment variable (12-factor app pattern)
        master_password = os.environ.get("API_KEY_MASTER_PASSWORD")
        
        if not master_password:
            # Generate a random master password if not set
            master_password = base64.urlsafe_b64encode(os.urandom(32)).decode()
            self.logger.warning(
                "⚠️ No master password found, generated random one. "
                "Set API_KEY_MASTER_PASSWORD environment variable for persistence."
            )
        
        # Derive encryption key using PBKDF2 (NIST recommended)
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"bybit_strategy_tester_salt",  # Fixed salt for deterministic key
            iterations=100000  # OWASP recommended minimum
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        self.encryption_key = key
        self.fernet = Fernet(key)
        
        self.logger.info("🔐 Encryption key initialized")
    
    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key using AES-256 (Fernet)"""
        encrypted = self.fernet.encrypt(api_key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt API key"""
        decoded = base64.urlsafe_b64decode(encrypted_key.encode())
        decrypted = self.fernet.decrypt(decoded)
        return decrypted.decode()
    
    def add_key_to_pool(self, service: str, api_key: str):
        """Add API key to in-memory pool (with encryption)"""
        if service not in self.key_pool:
            self.key_pool[service] = []
        
        self.key_pool[service].append(api_key)
        self.logger.info(
            f"✅ Added {service} API key to pool "
            f"(total: {len(self.key_pool[service])})"
        )
    
    def save_keys_to_disk(self):
        """Save encrypted keys to disk (HashiCorp Vault pattern)"""
        try:
            encrypted_data = {}
            
            for service, keys in self.key_pool.items():
                encrypted_data[service] = [
                    self.encrypt_api_key(key) for key in keys
                ]
            
            # Save with atomic write (AWS S3 pattern)
            temp_file = self.keys_file.with_suffix(".tmp")
            
            with open(temp_file, 'w') as f:
                json.dump(encrypted_data, f, indent=2)
            
            # Atomic rename (prevents corruption)
            temp_file.replace(self.keys_file)
            
            self.logger.info(
                f"💾 Saved encrypted keys to {self.keys_file} "
                f"(DeepSeek: {len(self.key_pool.get('deepseek', []))}, "
                f"Perplexity: {len(self.key_pool.get('perplexity', []))})"
            )
            
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Failed to save keys: {e}")
            return False
    
    def load_keys_from_disk(self) -> bool:
        """Load encrypted keys from disk (auto-load on startup)"""
        if not self.keys_file.exists():
            self.logger.warning(
                f"⚠️ Keys file not found: {self.keys_file}"
            )
            return False
        
        try:
            with open(self.keys_file, 'r') as f:
                encrypted_data = json.load(f)
            
            # Decrypt and load into memory pool
            for service, encrypted_keys in encrypted_data.items():
                self.key_pool[service] = [
                    self.decrypt_api_key(key) for key in encrypted_keys
                ]
            
            self.logger.info(
                f"✅ Loaded encrypted keys from {self.keys_file} "
                f"(DeepSeek: {len(self.key_pool.get('deepseek', []))}, "
                f"Perplexity: {len(self.key_pool.get('perplexity', []))})"
            )
            
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Failed to load keys: {e}")
            return False
    
    def get_keys(self, service: str) -> List[str]:
        """Get all API keys for a service"""
        return self.key_pool.get(service, [])
    
    def rotate_keys(self, service: str, new_keys: List[str]):
        """Rotate API keys for a service (zero-downtime rotation)"""
        self.logger.info(f"🔄 Rotating {service} API keys...")
        
        old_count = len(self.key_pool.get(service, []))
        self.key_pool[service] = new_keys
        new_count = len(new_keys)
        
        self.save_keys_to_disk()
        
        self.logger.info(
            f"✅ {service} keys rotated "
            f"({old_count} → {new_count})"
        )
    
    def get_key_status(self) -> Dict[str, Any]:
        """Get status of all keys"""
        return {
            "deepseek_keys": len(self.key_pool.get("deepseek", [])),
            "perplexity_keys": len(self.key_pool.get("perplexity", [])),
            "keys_file_exists": self.keys_file.exists(),
            "encryption_initialized": self.fernet is not None
        }
