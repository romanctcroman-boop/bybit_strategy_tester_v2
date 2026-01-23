"""
Security Module - Comprehensive Security Infrastructure.

This module provides enterprise-grade security features:

== Week 1 (Immediate) ==
- AES-256-GCM authenticated encryption (crypto.py)
- Memory protection with secure zeroing (memory_protection.py)
- Argon2id key derivation (crypto.py)

== Month 1 (Short-term) ==
- HSM abstraction layer (hsm_provider.py)
- Enhanced secret scanner with 30+ patterns (git_secrets_scanner.py)
- API key rotation with 90-day policy (api_key_rotation.py)

== Quarter 1 (Medium-term) ==
- Shamir's Secret Sharing for key sharding (shamir_sharing.py)
- Master key management (master_key_manager.py)
- Key storage with encryption (key_manager.py)

Usage:
    from backend.security import (
        CryptoManager,
        SecureString,
        ShamirSecretSharing,
        get_hsm,
    )

    # Encrypt sensitive data
    crypto = CryptoManager("my-encryption-key")
    encrypted = crypto.encrypt("secret-data")

    # Protect secrets in memory
    with secure_operation() as guard:
        secret = guard.protect(api_key)
        use_key(secret.get())

    # Split master key for distributed custody
    sss = ShamirSecretSharing()
    shares = sss.split(master_key, threshold=3, num_shares=5)
"""

# Core Crypto
from backend.security.api_key_rotation import (
    APIKeyRotationManager,
    get_rotation_manager,
)
from backend.security.crypto import (
    CRYPTO_AVAILABLE,
    CryptoManager,
    SecureBytes,
    create_crypto_manager,
)

# HSM Integration
from backend.security.hsm_provider import (
    HSMConfig,
    HSMFactory,
    HSMProvider,
    LocalHSM,
    get_hsm,
    set_hsm,
)
from backend.security.key_manager import (
    KeyManager,
    get_decrypted_key,
    get_key_manager,
)

# Key Management
from backend.security.master_key_manager import (
    MasterKeyManager,
    get_master_key_manager,
)

# Memory Protection
from backend.security.memory_protection import (
    MLOCK_AVAILABLE,
    MemoryGuard,
    SecureString,
    secure_compare,
    secure_operation,
    secure_random_string,
)

# Key Sharding
from backend.security.shamir_sharing import (
    SecretShare,
    ShamirSecretSharing,
    combine_key,
    split_key,
)

__all__ = [
    # Crypto
    "CryptoManager",
    "SecureBytes",
    "create_crypto_manager",
    "CRYPTO_AVAILABLE",
    # Memory
    "SecureString",
    "MemoryGuard",
    "secure_operation",
    "secure_compare",
    "secure_random_string",
    "MLOCK_AVAILABLE",
    # Key Management
    "MasterKeyManager",
    "get_master_key_manager",
    "KeyManager",
    "get_key_manager",
    "get_decrypted_key",
    "APIKeyRotationManager",
    "get_rotation_manager",
    # HSM
    "HSMProvider",
    "HSMConfig",
    "HSMFactory",
    "LocalHSM",
    "get_hsm",
    "set_hsm",
    # Shamir
    "ShamirSecretSharing",
    "SecretShare",
    "split_key",
    "combine_key",
]
