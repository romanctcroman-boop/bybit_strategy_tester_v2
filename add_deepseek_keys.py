"""
Add additional DeepSeek API keys to encrypted_secrets.json using backend KeyManager

This script:
1. Reads existing backend/config/encrypted_secrets.json
2. Adds 3 new DeepSeek keys from API.txt
3. Saves updated file

After execution, KeyManager can retrieve all keys via get_all_keys("DEEPSEEK_API_KEY")
"""

import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file FIRST
load_dotenv()

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.security.crypto import CryptoManager
from backend.security.master_key_manager import get_master_key_manager
from backend.security.key_manager import KeyManager


def main():
    print("=" * 80)
    print("  ADDING ADDITIONAL DEEPSEEK API KEYS")
    print("=" * 80)
    print()
    
    # Keys from d:\PERP\Demo\API.txt
    keys_to_add = {
        "DEEPSEEK_API_KEY_2": "sk-0a584271e8104aea89c9f5d7502093dd",
        "DEEPSEEK_API_KEY_3": "sk-d2b206a09da4413685613d637b9b8463",
        "DEEPSEEK_API_KEY_4": "sk-1428e58c87d74e90a063f6f5f5d8fbb3",
    }
    
    # Get crypto manager
    try:
        master_manager = get_master_key_manager()
        crypto = master_manager.create_crypto_manager()
        print("✅ Encryption initialized")
    except Exception as e:
        print(f"❌ Failed to initialize encryption: {e}")
        return
    
    # Path to encrypted secrets
    secrets_path = Path("backend/config/encrypted_secrets.json")
    
    # Load existing encrypted secrets
    if secrets_path.exists():
        with open(secrets_path, 'r', encoding='utf-8') as f:
            encrypted_secrets = json.load(f)
        print(f"\n📖 Current keys: {list(encrypted_secrets.keys())}")
    else:
        encrypted_secrets = {}
        print("\n⚠️  No existing encrypted_secrets.json found, creating new")
    
    # Add new keys
    print(f"\n➕ Adding new DeepSeek keys...")
    added_count = 0
    
    for key_name, key_value in keys_to_add.items():
        if key_name in encrypted_secrets:
            print(f"   ⚠️  {key_name} already exists, skipping")
            continue
        
        # Encrypt and add
        encrypted_value = crypto.encrypt(key_value)
        encrypted_secrets[key_name] = encrypted_value
        print(f"   ✅ {key_name}: {key_value[:10]}...{key_value[-6:]}")
        added_count += 1
    
    if added_count == 0:
        print("\n⚠️  No new keys added (all already exist)")
        return
    
    # Save updated secrets
    print(f"\n💾 Saving updated {secrets_path}...")
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(secrets_path, 'w', encoding='utf-8') as f:
        json.dump(encrypted_secrets, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Successfully added {added_count} new keys!")
    print(f"   Total keys in storage: {len(encrypted_secrets)}")
    print(f"   Keys: {list(encrypted_secrets.keys())}")
    
    # Verify by loading with KeyManager
    print("\n🔍 Verifying with KeyManager...")
    key_manager = KeyManager()
    deepseek_keys = key_manager.get_all_keys("DEEPSEEK_API_KEY")
    print(f"   ✅ KeyManager loaded {len(deepseek_keys)} DeepSeek keys")
    
    # Show last 6 chars of each key for verification
    for i, key in enumerate(deepseek_keys, 1):
        print(f"      Key {i}: ...{key[-6:]}")
    
    print("\n🚀 ParallelDeepSeekClient can now use all keys for parallel processing!")


if __name__ == "__main__":
    main()
