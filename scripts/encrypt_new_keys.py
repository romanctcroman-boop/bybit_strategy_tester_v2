"""
Encrypt and save new API keys using backend's KeyManager
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.security.key_manager import get_key_manager

def main():
    print("=" * 70)
    print("🔐 ENCRYPTING NEW API KEYS")
    print("=" * 70)
    
    km = get_key_manager()
    
    # NEW PERPLEXITY KEYS
    perplexity_keys = {
        "PERPLEXITY_API_KEY": "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",
        "PERPLEXITY_API_KEY_2": "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",
        "PERPLEXITY_API_KEY_3": "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",
        "PERPLEXITY_API_KEY_4": "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",
        "PERPLEXITY_API_KEY_5": "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",
        "PERPLEXITY_API_KEY_6": "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",
        "PERPLEXITY_API_KEY_7": "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",
        "PERPLEXITY_API_KEY_8": "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",
    }
    
    # NEW DEEPSEEK KEYS
    deepseek_keys = {
        "DEEPSEEK_API_KEY": "sk-1630fbba63c64f88952c16ad33337242",
        "DEEPSEEK_API_KEY_2": "sk-0a584271e8104aea89c9f5d7502093dd",
        "DEEPSEEK_API_KEY_3": "sk-d2b206a09da4413685613d637b9b8463",
        "DEEPSEEK_API_KEY_4": "sk-1428e58c87d74e90a063f6f5f5d8fbb3",
        "DEEPSEEK_API_KEY_5": "sk-8d66d1927a2044f7a368cc020173069b",
        "DEEPSEEK_API_KEY_6": "sk-0382ccd139814a5fb5ec7b65dd96afc0",
        "DEEPSEEK_API_KEY_7": "sk-abd04bc463a249cebbca748024d19bde",
        "DEEPSEEK_API_KEY_8": "sk-1fa47abaeb854e058aa9ee42fdedc811",
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
            print(f"  ❌ PERPLEXITY_API_KEY verification failed")
    except Exception as e:
        print(f"  ❌ Verification error: {e}")
    
    # Test DeepSeek
    try:
        test_key = km.get_decrypted_key("DEEPSEEK_API_KEY")
        if test_key and test_key.startswith("sk-"):
            print(f"  ✅ DEEPSEEK_API_KEY works: {test_key[:15]}...")
        else:
            print(f"  ❌ DEEPSEEK_API_KEY verification failed")
    except Exception as e:
        print(f"  ❌ Verification error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ DONE!")
    print("=" * 70)

if __name__ == "__main__":
    main()
