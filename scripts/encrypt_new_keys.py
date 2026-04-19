"""
Encrypt and save new API keys using backend's KeyManager.

Keys are loaded from environment variables (set in .env file).
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

    # PERPLEXITY KEY (loaded from environment)
    perplexity_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not perplexity_key:
        print("  ❌ PERPLEXITY_API_KEY not set in environment. Set it in .env file.")
        return

    perplexity_keys = {
        "PERPLEXITY_API_KEY": perplexity_key,
    }

    # DEEPSEEK KEY (loaded from environment)
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not deepseek_key:
        print("  ❌ DEEPSEEK_API_KEY not set in environment. Set it in .env file.")
        return

    deepseek_keys = {
        "DEEPSEEK_API_KEY": deepseek_key,
    }

    # Encrypt and store Perplexity keys
    print("\n📦 Encrypting Perplexity keys...")
    for key_name, key_value in perplexity_keys.items():
        try:
            km.store_encrypted_key(key_name, key_value)
            print(f"  ✅ {key_name}: {key_value[:15]}...")
        except Exception as e:
            print(f"  ❌ {key_name}: {e}")

    # Encrypt and store DeepSeek keys
    print("\n📦 Encrypting DeepSeek keys...")
    for key_name, key_value in deepseek_keys.items():
        try:
            km.store_encrypted_key(key_name, key_value)
            print(f"  ✅ {key_name}: {key_value[:15]}...")
        except Exception as e:
            print(f"  ❌ {key_name}: {e}")

    # Verify
    print("\n🔍 Verification...")

    # Test Perplexity
    try:
        test_key = km.get_decrypted_key("PERPLEXITY_API_KEY")
        if test_key and test_key.startswith("pplx-"):
            print(f"  ✅ PERPLEXITY_API_KEY works: {test_key[:15]}...")
        else:
            print("  ❌ PERPLEXITY_API_KEY verification failed")
    except Exception as e:
        print(f"  ❌ Verification error: {e}")

    # Test DeepSeek
    try:
        test_key = km.get_decrypted_key("DEEPSEEK_API_KEY")
        if test_key and test_key.startswith("sk-"):
            print(f"  ✅ DEEPSEEK_API_KEY works: {test_key[:15]}...")
        else:
            print("  ❌ DEEPSEEK_API_KEY verification failed")
    except Exception as e:
        print(f"  ❌ Verification error: {e}")

    print("\n" + "=" * 70)
    print("✅ DONE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
