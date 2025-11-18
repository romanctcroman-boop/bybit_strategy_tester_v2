"""
Cryptographic functions for API key encryption/decryption
Uses AES-256-GCM with PBKDF2 key derivation
"""
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoManager:
    """
    Manages encryption and decryption of sensitive data using AES-256-GCM.
    
    Features:
    - AES-256-GCM authenticated encryption
    - PBKDF2 key derivation (100,000 iterations)
    - Random salt per encryption
    - Base64 encoding for storage
    """
    
    def __init__(self, master_key: str):
        """
        Initialize CryptoManager with master key.
        
        Args:
            master_key: Master encryption key (string)
        """
        if not master_key:
            raise ValueError("Master key cannot be empty")
        
        self.master_key = master_key.encode('utf-8')
    
    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive encryption key from master key using PBKDF2.
        
        Args:
            salt: Random salt (16 bytes)
            
        Returns:
            Derived key (32 bytes for AES-256)
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=salt,
            iterations=100000,  # OWASP recommendation
        )
        return kdf.derive(self.master_key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-256-GCM.
        
        Args:
            plaintext: Data to encrypt
            
        Returns:
            Base64-encoded string: salt(16) + nonce(12) + ciphertext + tag(16)
        """
        if not plaintext:
            raise ValueError("Plaintext cannot be empty")
        
        # Generate random salt and nonce
        salt = os.urandom(16)
        nonce = os.urandom(12)
        
        # Derive key from master key + salt
        key = self._derive_key(salt)
        
        # Encrypt with AES-GCM
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        # Combine: salt + nonce + ciphertext (includes auth tag)
        combined = salt + nonce + ciphertext
        
        # Encode as base64 for storage
        return base64.b64encode(combined).decode('ascii')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data encrypted with encrypt().
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            
        Returns:
            Decrypted plaintext
            
        Raises:
            ValueError: If decryption fails (wrong key or corrupted data)
        """
        if not encrypted_data:
            raise ValueError("Encrypted data cannot be empty")
        
        try:
            # Decode from base64
            data = base64.b64decode(encrypted_data)
            
            # Extract components
            salt = data[:16]
            nonce = data[16:28]
            ciphertext = data[28:]
            
            # Derive key
            key = self._derive_key(salt)
            
            # Decrypt with AES-GCM
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")


def test_crypto():
    """Test encryption/decryption"""
    crypto = CryptoManager("test_master_key_12345")
    
    # Test encryption
    plaintext = "pplx-test-api-key-12345"
    encrypted = crypto.encrypt(plaintext)
    print(f"Encrypted: {encrypted[:50]}...")
    
    # Test decryption
    decrypted = crypto.decrypt(encrypted)
    assert decrypted == plaintext
    print(f"Decrypted: {decrypted}")
    print("✓ Crypto test passed!")


if __name__ == "__main__":
    test_crypto()
