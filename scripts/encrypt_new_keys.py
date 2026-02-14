"""
Encrypt and save new API keys using backend's KeyManager.

Keys are loaded from environment variables or .env file — never hardcoded.
Usage: set PERPLEXITY_API_KEY and DEEPSEEK_API_KEY env vars, then run this script.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.security.key_manager import get_key_manager


def main():
    print("=" * 70)
    print("🔐 ENCRYPTING NEW API KEYS")
    print("=" * 70)

    km = get_key_manager()

    # Load keys from environment variables (set in .env or shell)
    keys_to_encrypt = {}

    perplexity_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if perplexity_key:
        keys_to_encrypt["PERPLEXITY_API_KEY"] = perplexity_key
    else:
        print("  ⚠️  PERPLEXITY_API_KEY not set in environment — skipping")

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        keys_to_encrypt["DEEPSEEK_API_KEY"] = deepseek_key
    else:
        print("  ⚠️  DEEPSEEK_API_KEY not set in environment — skipping")

    if not keys_to_encrypt:
        print("\n❌ No API keys found in environment. Set them first:")
        print("   $env:PERPLEXITY_API_KEY = 'pplx-...'")
        print("   $env:DEEPSEEK_API_KEY = 'sk-...'")
        return

    # Encrypt and store keys
    print(f"\n📦 Encrypting {len(keys_to_encrypt)} key(s)...")
    for key_name, key_value in keys_to_encrypt.items():
        try:
            km.store_encrypted_key(key_name, key_value)
            print(f"  ✅ {key_name}: {key_value[:8]}***")
        except Exception as e:
            print(f"  ❌ {key_name}: {e}")

    # Verify stored keys
    print("\n🔍 Verification...")
    for key_name in keys_to_encrypt:
        try:
            test_key = km.get_decrypted_key(key_name)
            if test_key:
                print(f"  ✅ {key_name} works: {test_key[:8]}***")
            else:
                print(f"  ❌ {key_name} verification failed")
        except Exception as e:
            print(f"  ❌ Verification error: {e}")

    print("\n" + "=" * 70)
    print("✅ DONE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
