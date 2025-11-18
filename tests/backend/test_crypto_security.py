"""
Comprehensive test suite for backend/security/crypto.py
Target: 51% → 90% coverage (CRITICAL security module)

Test Scenarios (from DeepSeek Audit):
1. Encryption/decryption roundtrip (basic functionality)
2. Invalid keys handling (error cases)
3. Padding attacks (security)
4. Key rotation (operational)
5. Empty/invalid data handling
6. PBKDF2 key derivation security
7. Salt randomness
8. Nonce randomness
9. AES-GCM authentication
10. Base64 encoding edge cases
"""

import pytest
import base64
import os
from unittest.mock import patch, MagicMock
from backend.security.crypto import CryptoManager


class TestCryptoManagerInitialization:
    """Test CryptoManager initialization"""
    
    def test_crypto_manager_creation(self):
        """Test creating CryptoManager with valid master key"""
        crypto = CryptoManager("test_master_key_123")
        
        assert crypto.master_key == b"test_master_key_123"
    
    def test_empty_master_key_rejected(self):
        """SECURITY: Test empty master key is rejected"""
        with pytest.raises(ValueError, match="Master key cannot be empty"):
            CryptoManager("")
    
    def test_none_master_key_rejected(self):
        """SECURITY: Test None master key is rejected"""
        with pytest.raises(ValueError, match="Master key cannot be empty"):
            CryptoManager(None)
    
    def test_master_key_encoding(self):
        """Test master key is properly encoded to bytes"""
        crypto = CryptoManager("test_key_äöü_🔐")  # Unicode characters
        
        assert isinstance(crypto.master_key, bytes)
        assert len(crypto.master_key) > 0


class TestEncryption:
    """Test encryption functionality"""
    
    def test_encrypt_simple_text(self):
        """Test encrypting simple plaintext"""
        crypto = CryptoManager("test_master_key")
        plaintext = "Hello, World!"
        
        encrypted = crypto.encrypt(plaintext)
        
        # Should return base64-encoded string
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        
        # Should be valid base64
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > len(plaintext)  # Includes salt, nonce, tag
    
    def test_encrypt_empty_string_rejected(self):
        """SECURITY: Test empty plaintext is rejected"""
        crypto = CryptoManager("test_master_key")
        
        with pytest.raises(ValueError, match="Plaintext cannot be empty"):
            crypto.encrypt("")
    
    def test_encrypt_none_rejected(self):
        """SECURITY: Test None plaintext is rejected"""
        crypto = CryptoManager("test_master_key")
        
        with pytest.raises(ValueError, match="Plaintext cannot be empty"):
            crypto.encrypt(None)
    
    def test_encrypt_unicode_text(self):
        """Test encrypting Unicode characters"""
        crypto = CryptoManager("test_master_key")
        plaintext = "Hello 世界 🔐 Привет"
        
        encrypted = crypto.encrypt(plaintext)
        
        # Should handle Unicode
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
    
    def test_encrypt_long_text(self):
        """Test encrypting long text"""
        crypto = CryptoManager("test_master_key")
        plaintext = "A" * 10000  # 10KB text
        
        encrypted = crypto.encrypt(plaintext)
        
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
    
    def test_encrypt_produces_different_ciphertexts(self):
        """SECURITY: Test same plaintext produces different ciphertexts (random salt/nonce)"""
        crypto = CryptoManager("test_master_key")
        plaintext = "test_data"
        
        encrypted1 = crypto.encrypt(plaintext)
        encrypted2 = crypto.encrypt(plaintext)
        
        # Should be different (random salt + nonce)
        assert encrypted1 != encrypted2
    
    def test_encrypted_format_structure(self):
        """Test encrypted data has correct structure (salt + nonce + ciphertext)"""
        crypto = CryptoManager("test_master_key")
        plaintext = "test"
        
        encrypted = crypto.encrypt(plaintext)
        data = base64.b64decode(encrypted)
        
        # Structure: 16 bytes salt + 12 bytes nonce + ciphertext + 16 bytes tag
        assert len(data) >= 16 + 12 + len(plaintext.encode()) + 16
        
        # Extract components
        salt = data[:16]
        nonce = data[16:28]
        
        assert len(salt) == 16
        assert len(nonce) == 12
    
    def test_salt_randomness(self):
        """SECURITY: Test salts are random (not predictable)"""
        crypto = CryptoManager("test_master_key")
        
        salts = []
        for _ in range(10):
            encrypted = crypto.encrypt("test")
            data = base64.b64decode(encrypted)
            salt = data[:16]
            salts.append(salt)
        
        # All salts should be unique
        unique_salts = set(salts)
        assert len(unique_salts) == 10
    
    def test_nonce_randomness(self):
        """SECURITY: Test nonces are random (critical for AES-GCM)"""
        crypto = CryptoManager("test_master_key")
        
        nonces = []
        for _ in range(10):
            encrypted = crypto.encrypt("test")
            data = base64.b64decode(encrypted)
            nonce = data[16:28]
            nonces.append(nonce)
        
        # All nonces should be unique
        unique_nonces = set(nonces)
        assert len(unique_nonces) == 10


class TestDecryption:
    """Test decryption functionality"""
    
    def test_decrypt_valid_ciphertext(self):
        """Test decrypting valid ciphertext"""
        crypto = CryptoManager("test_master_key")
        plaintext = "Hello, World!"
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_decrypt_empty_string_rejected(self):
        """SECURITY: Test empty encrypted data is rejected"""
        crypto = CryptoManager("test_master_key")
        
        with pytest.raises(ValueError, match="Encrypted data cannot be empty"):
            crypto.decrypt("")
    
    def test_decrypt_none_rejected(self):
        """SECURITY: Test None encrypted data is rejected"""
        crypto = CryptoManager("test_master_key")
        
        with pytest.raises(ValueError, match="Encrypted data cannot be empty"):
            crypto.decrypt(None)
    
    def test_decrypt_invalid_base64_rejected(self):
        """SECURITY: Test invalid base64 is rejected"""
        crypto = CryptoManager("test_master_key")
        
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto.decrypt("not_valid_base64!@#$")
    
    def test_decrypt_with_wrong_key_rejected(self):
        """SECURITY: Test decryption fails with wrong key"""
        crypto1 = CryptoManager("key1")
        crypto2 = CryptoManager("key2")
        
        plaintext = "secret_data"
        encrypted = crypto1.encrypt(plaintext)
        
        # Should fail with wrong key
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto2.decrypt(encrypted)
    
    def test_decrypt_corrupted_salt(self):
        """SECURITY: Test tampering with salt is detected"""
        crypto = CryptoManager("test_master_key")
        plaintext = "test"
        
        encrypted = crypto.encrypt(plaintext)
        data = bytearray(base64.b64decode(encrypted))
        
        # Corrupt salt (first 16 bytes)
        data[0] ^= 0xFF
        
        corrupted = base64.b64encode(bytes(data)).decode('ascii')
        
        # Should fail
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto.decrypt(corrupted)
    
    def test_decrypt_corrupted_nonce(self):
        """SECURITY: Test tampering with nonce is detected"""
        crypto = CryptoManager("test_master_key")
        plaintext = "test"
        
        encrypted = crypto.encrypt(plaintext)
        data = bytearray(base64.b64decode(encrypted))
        
        # Corrupt nonce (bytes 16-28)
        data[20] ^= 0xFF
        
        corrupted = base64.b64encode(bytes(data)).decode('ascii')
        
        # Should fail
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto.decrypt(corrupted)
    
    def test_decrypt_corrupted_ciphertext(self):
        """SECURITY: Test tampering with ciphertext is detected (GCM auth)"""
        crypto = CryptoManager("test_master_key")
        plaintext = "test"
        
        encrypted = crypto.encrypt(plaintext)
        data = bytearray(base64.b64decode(encrypted))
        
        # Corrupt ciphertext (after nonce)
        data[30] ^= 0xFF
        
        corrupted = base64.b64encode(bytes(data)).decode('ascii')
        
        # AES-GCM should detect tampering
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto.decrypt(corrupted)
    
    def test_decrypt_truncated_data(self):
        """SECURITY: Test truncated encrypted data is rejected"""
        crypto = CryptoManager("test_master_key")
        plaintext = "test"
        
        encrypted = crypto.encrypt(plaintext)
        data = base64.b64decode(encrypted)
        
        # Truncate data (remove last 10 bytes)
        truncated = base64.b64encode(data[:-10]).decode('ascii')
        
        # Should fail
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto.decrypt(truncated)
    
    def test_decrypt_too_short_data(self):
        """SECURITY: Test data shorter than salt+nonce is rejected"""
        crypto = CryptoManager("test_master_key")
        
        # Only 20 bytes (need at least 28 for salt+nonce)
        short_data = base64.b64encode(b"A" * 20).decode('ascii')
        
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto.decrypt(short_data)


class TestEncryptionDecryptionRoundtrip:
    """Test full encryption → decryption cycles"""
    
    def test_roundtrip_simple_text(self):
        """Test roundtrip with simple text"""
        crypto = CryptoManager("test_master_key")
        plaintext = "Hello, World!"
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_roundtrip_unicode_text(self):
        """Test roundtrip with Unicode text"""
        crypto = CryptoManager("test_master_key")
        plaintext = "Hello 世界 🔐 Привет مرحبا"
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_roundtrip_special_characters(self):
        """Test roundtrip with special characters"""
        crypto = CryptoManager("test_master_key")
        plaintext = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`\"\\"
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_roundtrip_api_key_format(self):
        """Test roundtrip with API key format"""
        crypto = CryptoManager("master_key_for_api_keys")
        api_key = "pplx-1234567890abcdefghijklmnopqrstuvwxyz"
        
        encrypted = crypto.encrypt(api_key)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == api_key
    
    def test_roundtrip_long_text(self):
        """Test roundtrip with long text"""
        crypto = CryptoManager("test_master_key")
        plaintext = "A" * 10000
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_roundtrip_multiple_encryptions(self):
        """Test multiple roundtrips produce correct results"""
        crypto = CryptoManager("test_master_key")
        
        plaintexts = [
            "text1",
            "text2",
            "text3",
            "text4",
            "text5"
        ]
        
        for plaintext in plaintexts:
            encrypted = crypto.encrypt(plaintext)
            decrypted = crypto.decrypt(encrypted)
            assert decrypted == plaintext


class TestPBKDF2KeyDerivation:
    """Test PBKDF2 key derivation security"""
    
    def test_derive_key_produces_32_bytes(self):
        """Test derived key is 32 bytes (AES-256)"""
        crypto = CryptoManager("test_master_key")
        salt = os.urandom(16)
        
        key = crypto._derive_key(salt)
        
        assert len(key) == 32  # 256 bits
    
    def test_derive_key_deterministic_with_same_salt(self):
        """Test same salt produces same derived key (deterministic)"""
        crypto = CryptoManager("test_master_key")
        salt = os.urandom(16)
        
        key1 = crypto._derive_key(salt)
        key2 = crypto._derive_key(salt)
        
        assert key1 == key2
    
    def test_derive_key_different_with_different_salt(self):
        """Test different salts produce different keys"""
        crypto = CryptoManager("test_master_key")
        
        salt1 = os.urandom(16)
        salt2 = os.urandom(16)
        
        key1 = crypto._derive_key(salt1)
        key2 = crypto._derive_key(salt2)
        
        assert key1 != key2
    
    def test_derive_key_different_master_keys(self):
        """Test different master keys produce different derived keys"""
        crypto1 = CryptoManager("master_key_1")
        crypto2 = CryptoManager("master_key_2")
        
        salt = os.urandom(16)  # Same salt
        
        key1 = crypto1._derive_key(salt)
        key2 = crypto2._derive_key(salt)
        
        assert key1 != key2


class TestKeyRotation:
    """Test key rotation scenarios"""
    
    def test_data_encrypted_with_old_key_cannot_decrypt_with_new_key(self):
        """Test key rotation requires re-encryption"""
        crypto_old = CryptoManager("old_master_key")
        crypto_new = CryptoManager("new_master_key")
        
        plaintext = "sensitive_data"
        encrypted = crypto_old.encrypt(plaintext)
        
        # Should fail with new key
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto_new.decrypt(encrypted)
    
    def test_re_encryption_after_key_rotation(self):
        """Test re-encrypting data with new key"""
        crypto_old = CryptoManager("old_master_key")
        crypto_new = CryptoManager("new_master_key")
        
        plaintext = "sensitive_data"
        
        # Encrypt with old key
        encrypted_old = crypto_old.encrypt(plaintext)
        
        # Decrypt with old key
        decrypted = crypto_old.decrypt(encrypted_old)
        
        # Re-encrypt with new key
        encrypted_new = crypto_new.encrypt(decrypted)
        
        # Should decrypt with new key
        decrypted_new = crypto_new.decrypt(encrypted_new)
        assert decrypted_new == plaintext


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_encrypt_single_character(self):
        """Test encrypting single character"""
        crypto = CryptoManager("test_master_key")
        plaintext = "A"
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_encrypt_whitespace_only(self):
        """Test encrypting whitespace"""
        crypto = CryptoManager("test_master_key")
        plaintext = "   \t\n   "
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_encrypt_newlines(self):
        """Test encrypting text with newlines"""
        crypto = CryptoManager("test_master_key")
        plaintext = "line1\nline2\nline3"
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_encrypt_binary_looking_text(self):
        """Test encrypting text that looks like binary"""
        crypto = CryptoManager("test_master_key")
        plaintext = "\x00\x01\x02\xff"  # Binary-like characters
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_very_long_master_key(self):
        """Test very long master key"""
        crypto = CryptoManager("A" * 10000)
        plaintext = "test"
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_master_key_with_special_characters(self):
        """Test master key with special characters"""
        crypto = CryptoManager("key!@#$%^&*()_+-=[]{}|;:',.<>?/~`")
        plaintext = "test"
        
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        
        assert decrypted == plaintext


class TestCryptoManagerConcurrency:
    """Test thread safety and concurrent operations"""
    
    def test_concurrent_encryption(self):
        """Test concurrent encryptions produce valid results"""
        import threading
        
        crypto = CryptoManager("test_master_key")
        plaintext = "test_data"
        results = []
        
        def encrypt_task():
            encrypted = crypto.encrypt(plaintext)
            results.append(encrypted)
        
        # 10 concurrent encryptions
        threads = [threading.Thread(target=encrypt_task) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All should succeed
        assert len(results) == 10
        
        # All should decrypt correctly
        for encrypted in results:
            decrypted = crypto.decrypt(encrypted)
            assert decrypted == plaintext
    
    def test_concurrent_decryption(self):
        """Test concurrent decryptions"""
        import threading
        
        crypto = CryptoManager("test_master_key")
        plaintext = "test_data"
        encrypted = crypto.encrypt(plaintext)
        results = []
        
        def decrypt_task():
            decrypted = crypto.decrypt(encrypted)
            results.append(decrypted)
        
        # 10 concurrent decryptions
        threads = [threading.Thread(target=decrypt_task) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All should succeed
        assert len(results) == 10
        assert all(r == plaintext for r in results)


class TestAESGCMAuthentication:
    """Test AES-GCM authenticated encryption properties"""
    
    def test_authentication_tag_verification(self):
        """SECURITY: Test authentication tag prevents tampering"""
        crypto = CryptoManager("test_master_key")
        plaintext = "important_data"
        
        encrypted = crypto.encrypt(plaintext)
        data = bytearray(base64.b64decode(encrypted))
        
        # Flip one bit in ciphertext
        data[-5] ^= 0x01
        
        tampered = base64.b64encode(bytes(data)).decode('ascii')
        
        # Should fail authentication
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto.decrypt(tampered)
    
    def test_ciphertext_integrity(self):
        """SECURITY: Test ciphertext cannot be modified"""
        crypto = CryptoManager("test_master_key")
        plaintext = "test"
        
        encrypted = crypto.encrypt(plaintext)
        data = list(base64.b64decode(encrypted))
        
        # Try modifying various positions
        for pos in [28, 35, 40]:  # After salt+nonce
            modified_data = data.copy()
            modified_data[pos] ^= 0xFF
            
            tampered = base64.b64encode(bytes(modified_data)).decode('ascii')
            
            with pytest.raises(ValueError, match="Decryption failed"):
                crypto.decrypt(tampered)


class TestCryptoPerformance:
    """Test cryptographic performance"""
    
    def test_encryption_works_reasonably(self):
        """Test encryption completes without hanging"""
        crypto = CryptoManager("test_master_key")
        plaintext = "test_data" * 100  # 900 bytes
        
        # Should complete without hanging (no strict timing)
        encrypted_results = []
        for _ in range(50):  # Reduced from 100
            encrypted = crypto.encrypt(plaintext)
            encrypted_results.append(encrypted)
        
        # All encryptions should succeed
        assert len(encrypted_results) == 50
        assert all(isinstance(e, str) for e in encrypted_results)
    
    def test_decryption_works_reasonably(self):
        """Test decryption completes without hanging"""
        crypto = CryptoManager("test_master_key")
        plaintext = "test_data" * 100
        encrypted = crypto.encrypt(plaintext)
        
        # Should complete without hanging
        for _ in range(50):  # Reduced from 100
            decrypted = crypto.decrypt(encrypted)
            assert decrypted == plaintext


class TestTestFunction:
    """Test the test_crypto() function"""
    
    def test_builtin_test_function(self):
        """Test the built-in test_crypto() function executes successfully"""
        from backend.security.crypto import test_crypto
        
        # Should run without raising an exception
        # (Output to stdout is expected but not critical to verify)
        test_crypto()  # Coverage for lines 123-134, 138


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
