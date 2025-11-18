"""
Tests for password hashing utilities

Coverage target: 0% → 100%
"""

import pytest

from backend.utils.password import hash_password, verify_password


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_creates_hash(self):
        """Test that hash_password creates a bcrypt hash."""
        password = "my_secure_password_123"
        hashed = hash_password(password)
        
        # Bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")
        # Bcrypt hashes are 60 characters
        assert len(hashed) == 60

    def test_hash_password_different_each_time(self):
        """Test that hashing same password twice produces different hashes (salt)."""
        password = "test123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Same password should produce different hashes due to different salts
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "correct_password"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_string(self):
        """Test verifying empty password."""
        password = "test"
        hashed = hash_password(password)
        
        assert verify_password("", hashed) is False

    def test_verify_password_with_special_chars(self):
        """Test password with special characters."""
        password = "P@ssw0rd!#$%^&*()"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
        assert verify_password("P@ssw0rd!", hashed) is False

    def test_verify_password_with_unicode(self):
        """Test password with unicode characters."""
        password = "пароль123"  # Russian characters
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "TestPassword"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
        assert verify_password("testpassword", hashed) is False
        assert verify_password("TESTPASSWORD", hashed) is False

    def test_verify_password_invalid_hash_format(self):
        """Test verification with invalid hash format."""
        password = "test"
        invalid_hash = "not_a_valid_bcrypt_hash"
        
        # Should return False, not raise exception
        assert verify_password(password, invalid_hash) is False

    def test_verify_password_empty_hash(self):
        """Test verification with empty hash."""
        password = "test"
        
        assert verify_password(password, "") is False

    def test_hash_password_long_password(self):
        """Test hashing password at bcrypt limit (72 bytes)."""
        # Bcrypt has 72-byte limit
        password = "a" * 72
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True

    def test_verify_password_whitespace_matters(self):
        """Test that whitespace in password matters."""
        password = "password"
        password_with_space = "password "
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
        assert verify_password(password_with_space, hashed) is False
