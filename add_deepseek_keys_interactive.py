"""
Interactive script to add DeepSeek API keys to encrypted_secrets.json

This script:
1. Loads existing backend/config/encrypted_secrets.json
2. Asks user to paste DeepSeek API keys
3. Encrypts and saves them
4. Verifies with KeyManager

Usage:
    python add_deepseek_keys_interactive.py
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
    print("  ADDING DEEPSEEK API KEYS - INTERACTIVE MODE")
    print("=" * 80)
    print()
    
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
        print(f"\n📖 Current keys in {secrets_path}:")
        for key_name in encrypted_secrets.keys():
            print(f"   - {key_name}")
    else:
        encrypted_secrets = {}
        print("\n⚠️  No existing encrypted_secrets.json found, creating new")
    
    # Count existing DeepSeek keys
    existing_deepseek_keys = [k for k in encrypted_secrets.keys() if k.startswith("DEEPSEEK_API_KEY")]
    print(f"\n📊 Found {len(existing_deepseek_keys)} existing DeepSeek keys")
    
    # Ask user how many keys to add
    print("\n" + "=" * 80)
    print("How many DeepSeek API keys do you want to add?")
    print("(Recommended: 8 total keys for optimal parallel processing)")
    print(f"(You currently have: {len(existing_deepseek_keys)} keys)")
    print("=" * 80)
    
    try:
        num_keys = int(input("\nEnter number of keys to add (e.g., 7): ").strip())
    except ValueError:
        print("❌ Invalid number")
        return
    
    if num_keys <= 0:
        print("❌ Number must be positive")
        return
    
    # Collect keys from user
    keys_to_add = {}
    
    print(f"\n📝 Please paste {num_keys} DeepSeek API keys (format: sk-...)")
    print("   Press Enter after each key")
    print()
    
    for i in range(1, num_keys + 1):
        # Determine key name
        if i == 1 and "DEEPSEEK_API_KEY" not in encrypted_secrets:
            key_name = "DEEPSEEK_API_KEY"
        else:
            # Find next available index
            idx = 1
            while f"DEEPSEEK_API_KEY_{idx}" in encrypted_secrets:
                idx += 1
            key_name = f"DEEPSEEK_API_KEY_{idx}"
        
        key_value = input(f"Key {i}/{num_keys} ({key_name}): ").strip()
        
        if not key_value:
            print("   ⚠️  Empty key, skipping")
            continue
        
        if not key_value.startswith("sk-"):
            print(f"   ⚠️  Warning: Key doesn't start with 'sk-', but will be added")
        
        keys_to_add[key_name] = key_value
    
    if not keys_to_add:
        print("\n⚠️  No keys to add")
        return
    
    # Encrypt and add keys
    print(f"\n🔐 Encrypting {len(keys_to_add)} keys...")
    added_count = 0
    
    for key_name, key_value in keys_to_add.items():
        try:
            encrypted_value = crypto.encrypt(key_value)
            encrypted_secrets[key_name] = encrypted_value
            print(f"   ✅ {key_name}: {key_value[:10]}...{key_value[-6:]}")
            added_count += 1
        except Exception as e:
            print(f"   ❌ Failed to encrypt {key_name}: {e}")
    
    if added_count == 0:
        print("\n❌ No keys were added")
        return
    
    # Save updated secrets
    print(f"\n💾 Saving to {secrets_path}...")
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(secrets_path, 'w', encoding='utf-8') as f:
        json.dump(encrypted_secrets, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Successfully added {added_count} new keys!")
    print(f"   Total keys in storage: {len(encrypted_secrets)}")
    print(f"\n📋 All keys in encrypted storage:")
    for key_name in sorted(encrypted_secrets.keys()):
        print(f"   - {key_name}")
    
    # Count total DeepSeek keys
    total_deepseek_keys = [k for k in encrypted_secrets.keys() if k.startswith("DEEPSEEK_API_KEY")]
    print(f"\n📊 Total DeepSeek keys: {len(total_deepseek_keys)}")
    
    if len(total_deepseek_keys) >= 8:
        print("   🚀 Excellent! You have 8+ keys for optimal parallel processing!")
    elif len(total_deepseek_keys) >= 4:
        print("   ✅ Good! 4+ keys enable significant parallel speedup")
    else:
        print("   ⚠️  Consider adding more keys for better performance")
    
    # Verify by loading with KeyManager
    print("\n🔍 Verifying with KeyManager...")
    try:
        key_manager = KeyManager()
        key_manager.reload()  # Force reload
        
        # Try to get all DeepSeek keys
        deepseek_keys_found = 0
        for key_name in sorted(encrypted_secrets.keys()):
            if key_name.startswith("DEEPSEEK_API_KEY"):
                try:
                    key_value = key_manager.get_decrypted_key(key_name)
                    print(f"   ✅ {key_name}: ...{key_value[-6:]}")
                    deepseek_keys_found += 1
                except Exception as e:
                    print(f"   ❌ {key_name}: Failed to decrypt - {e}")
        
        print(f"\n✅ KeyManager successfully loaded {deepseek_keys_found} DeepSeek keys")
        
    except Exception as e:
        print(f"\n⚠️  KeyManager verification failed: {e}")
        print("   Keys are saved, but verification failed")
    
    print("\n" + "=" * 80)
    print("🎉 DONE! Now restart VS Code to activate all keys in MCP Server")
    print("=" * 80)


if __name__ == "__main__":
    main()
