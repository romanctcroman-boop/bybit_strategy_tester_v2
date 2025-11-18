"""
Migrate Secrets to Encrypted Storage
=====================================

Migrates API keys from environment variables to encrypted storage.

Usage:
    1. Generate master encryption key:
       python backend/core/secrets_manager.py generate-key
    
    2. Set master key as environment variable:
       export MASTER_ENCRYPTION_KEY='<generated_key>'
    
    3. Run migration:
       python migrate_secrets_to_encrypted.py
    
    4. Verify:
       python migrate_secrets_to_encrypted.py --verify

Security:
    - Original .env file is backed up
    - Secrets are encrypted with AES-256-GCM + audit metadata
    - Audit log created in logs/secrets_audit.log
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.core.secrets_manager import SecretsManager, get_secret
from loguru import logger


# API keys to migrate
API_KEYS_TO_MIGRATE = [
    # DeepSeek
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_API_KEY_1",
    "DEEPSEEK_API_KEY_2",
    "DEEPSEEK_API_KEY_3",
    "DEEPSEEK_API_KEY_4",
    "DEEPSEEK_API_KEY_5",
    "DEEPSEEK_API_KEY_6",
    "DEEPSEEK_API_KEY_7",
    
    # Perplexity
    "PERPLEXITY_API_KEY",
    "PERPLEXITY_API_KEY_1",
    "PERPLEXITY_API_KEY_2",
    "PERPLEXITY_API_KEY_3",
    "PERPLEXITY_API_KEY_4",
    "PERPLEXITY_API_KEY_5",
    "PERPLEXITY_API_KEY_6",
    "PERPLEXITY_API_KEY_7",
    
    # Bybit
    "BYBIT_API_KEY",
    "BYBIT_API_SECRET",
    "BYBIT_TESTNET_API_KEY",
    "BYBIT_TESTNET_API_SECRET",
    
    # Database
    "DATABASE_URL",
    "POSTGRES_PASSWORD",
    
    # Redis
    "REDIS_URL",
    "REDIS_PASSWORD",
    
    # JWT
    "SECRET_KEY",
    "JWT_SECRET_KEY",
]


def migrate_secrets(dry_run: bool = False):
    """Migrate secrets from .env to encrypted storage"""
    
    logger.info("="*80)
    logger.info("🔐 Secrets Migration Tool")
    logger.info("="*80)
    
    # Load .env file
    env_path = Path(".env")
    if not env_path.exists():
        logger.error("❌ .env file not found!")
        return False
    
    load_dotenv()
    
    # Check master encryption key
    master_key = os.getenv("MASTER_ENCRYPTION_KEY")
    if not master_key:
        logger.error("❌ MASTER_ENCRYPTION_KEY not set!")
        logger.info("\n📝 Generate key with:")
        logger.info("   python backend/core/secrets_manager.py generate-key")
        return False
    
    logger.info(f"✅ Master encryption key loaded ({len(master_key)} chars)")
    
    # Initialize SecretsManager
    try:
        sm = SecretsManager()
    except Exception as e:
        logger.error(f"❌ Failed to initialize SecretsManager: {e}")
        return False
    
    # Backup .env file
    if not dry_run:
        backup_path = env_path.with_suffix(f".env.backup.{int(datetime.now().timestamp())}")
        try:
            import shutil
            shutil.copy2(env_path, backup_path)
            logger.info(f"💾 Backup created: {backup_path}")
        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return False
    
    # Migrate secrets
    logger.info(f"\n📦 Migrating {len(API_KEYS_TO_MIGRATE)} secrets...")
    
    migrated = 0
    skipped = 0
    failed = 0
    
    for key_name in API_KEYS_TO_MIGRATE:
        try:
            secret = os.getenv(key_name)
            if secret:
                if dry_run:
                    logger.info(f"   [DRY RUN] Would migrate: {key_name}")
                else:
                    sm.set_secret(key_name, secret)
                    logger.info(f"   ✅ Migrated: {key_name} ({len(secret)} chars)")
                migrated += 1
            else:
                logger.debug(f"   ⏭️  Skipped (not found): {key_name}")
                skipped += 1
        except Exception as e:
            logger.error(f"   ❌ Failed: {key_name} - {e}")
            failed += 1
    
    logger.info("\n" + "="*80)
    logger.info("📊 Migration Summary")
    logger.info("="*80)
    logger.info(f"   ✅ Migrated: {migrated}")
    logger.info(f"   ⏭️  Skipped: {skipped}")
    logger.info(f"   ❌ Failed: {failed}")
    
    if not dry_run:
        logger.info(f"\n📄 Secrets stored in: .secrets.enc")
        logger.info(f"📝 Audit log: logs/secrets_audit.log")
    
    return failed == 0


def verify_migration():
    """Verify migrated secrets can be decrypted"""
    
    logger.info("="*80)
    logger.info("🔍 Verifying Encrypted Secrets")
    logger.info("="*80)
    
    sm = SecretsManager()
    
    secrets_list = sm.list_secrets()
    if not secrets_list:
        logger.warning("⚠️ No secrets found in encrypted storage")
        return False
    
    logger.info(f"\n📦 Found {len(secrets_list)} secrets in encrypted storage")
    
    success = 0
    failed = 0
    
    for key_name in secrets_list:
        try:
            secret = sm.get_secret(key_name, fallback_env=False)
            if secret:
                logger.info(f"   ✅ {key_name}: OK ({len(secret)} chars)")
                success += 1
            else:
                logger.error(f"   ❌ {key_name}: EMPTY")
                failed += 1
        except Exception as e:
            logger.error(f"   ❌ {key_name}: {e}")
            failed += 1
    
    logger.info("\n" + "="*80)
    logger.info("📊 Verification Summary")
    logger.info("="*80)
    logger.info(f"   ✅ Success: {success}")
    logger.info(f"   ❌ Failed: {failed}")
    
    return failed == 0


def test_encryption_performance():
    """Test encryption/decryption performance"""
    
    logger.info("="*80)
    logger.info("⚡ Performance Test")
    logger.info("="*80)
    
    import time
    
    sm = SecretsManager()
    test_secret = "test-api-key-" + "x" * 64
    
    # Encryption test
    start = time.time()
    iterations = 1000
    
    for i in range(iterations):
        encrypted = sm.encrypt_secret(test_secret, key_name="PERF_TEST")
    
    encrypt_time = time.time() - start
    logger.info(f"\n🔐 Encryption: {iterations} ops in {encrypt_time:.2f}s")
    logger.info(f"   Rate: {iterations/encrypt_time:.0f} ops/sec")
    
    # Decryption test
    encrypted = sm.encrypt_secret(test_secret, key_name="PERF_TEST")
    start = time.time()
    
    for i in range(iterations):
        decrypted = sm.decrypt_secret(encrypted, key_name="PERF_TEST")
    
    decrypt_time = time.time() - start
    logger.info(f"\n🔓 Decryption: {iterations} ops in {decrypt_time:.2f}s")
    logger.info(f"   Rate: {iterations/decrypt_time:.0f} ops/sec")
    
    # Get secret test (with file I/O)
    sm.set_secret("PERF_TEST_KEY", test_secret)
    start = time.time()
    
    for i in range(100):
        secret = sm.get_secret("PERF_TEST_KEY")
    
    get_time = time.time() - start
    logger.info(f"\n📖 Get Secret (with I/O): 100 ops in {get_time:.2f}s")
    logger.info(f"   Rate: {100/get_time:.0f} ops/sec")
    
    sm.delete_secret("PERF_TEST_KEY")


def main():
    parser = argparse.ArgumentParser(description="Migrate secrets to encrypted storage")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without writing")
    parser.add_argument("--verify", action="store_true", help="Verify encrypted secrets")
    parser.add_argument("--test-performance", action="store_true", help="Test encryption performance")
    
    args = parser.parse_args()
    
    if args.test_performance:
        test_encryption_performance()
    elif args.verify:
        success = verify_migration()
        sys.exit(0 if success else 1)
    else:
        success = migrate_secrets(dry_run=args.dry_run)
        
        if success and not args.dry_run:
            logger.info("\n✅ Migration completed successfully!")
            logger.info("\n📝 Next steps:")
            logger.info("   1. Run verification: python migrate_secrets_to_encrypted.py --verify")
            logger.info("   2. Update code to use SecretsManager:")
            logger.info("      from backend.core.secrets_manager import get_secret")
            logger.info("      api_key = get_secret('DEEPSEEK_API_KEY')")
            logger.info("   3. Consider removing secrets from .env file")
            logger.info("      (Keep MASTER_ENCRYPTION_KEY in .env)")
        
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
