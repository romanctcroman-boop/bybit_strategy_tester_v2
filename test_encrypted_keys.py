"""
Test Encrypted Key Loading
===========================

Проверяет что все 12 ключей загружаются из encrypted_secrets.json
"""

import sys
from pathlib import Path
import os

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from automation.task2_key_manager.key_manager import KeyManager
from dotenv import load_dotenv

# Load .env
load_dotenv()

def test_key_loading():
    """Test loading encrypted keys"""
    print("=" * 80)
    print("🔐 Testing Encrypted Key Loading")
    print("=" * 80)
    
    # Initialize KeyManager
    key_manager = KeyManager()
    
    # Get encryption key
    encryption_key = os.getenv('ENCRYPTION_KEY')
    if not encryption_key:
        print("❌ ENCRYPTION_KEY not found in .env!")
        print("\n💡 To fix:")
        print("1. Add to .env: ENCRYPTION_KEY=your_32_char_key")
        print("2. Or generate: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        return False
    
    print(f"✅ ENCRYPTION_KEY found: {encryption_key[:10]}...")
    
    # Initialize encryption
    if not key_manager.initialize_encryption(encryption_key):
        print("❌ Failed to initialize encryption")
        return False
    
    print("✅ Encryption initialized")
    
    # Load keys
    if not key_manager.load_keys("encrypted_secrets.json"):
        print("❌ Failed to load encrypted_secrets.json")
        print("\n💡 To fix:")
        print("1. Check that encrypted_secrets.json exists")
        print("2. Run: python automation/task2_key_manager/encrypt_secrets.py")
        return False
    
    print("✅ Keys loaded from encrypted_secrets.json")
    
    # Check available keys
    available_keys = key_manager.get_available_keys()
    print(f"\n📊 Available keys: {len(available_keys)}")
    for key_name in sorted(available_keys):
        print(f"   - {key_name}")
    
    # Test Perplexity keys
    print("\n" + "=" * 80)
    print("🔵 Perplexity API Keys")
    print("=" * 80)
    
    perplexity_keys = key_manager.get_all_keys('PERPLEXITY_API_KEY')
    print(f"Found: {len(perplexity_keys)} keys")
    
    for i, key in enumerate(perplexity_keys, 1):
        print(f"   Key #{i}: {key[:10]}... (length: {len(key)})")
    
    if len(perplexity_keys) != 4:
        print(f"⚠️ Expected 4 Perplexity keys, got {len(perplexity_keys)}")
        print("\n💡 To add more keys:")
        print("1. Add to encrypted_secrets.json:")
        print("   PERPLEXITY_API_KEY_1, PERPLEXITY_API_KEY_2, etc.")
    else:
        print("✅ All 4 Perplexity keys loaded!")
    
    # Test DeepSeek keys
    print("\n" + "=" * 80)
    print("🟣 DeepSeek API Keys")
    print("=" * 80)
    
    deepseek_keys = key_manager.get_all_keys('DEEPSEEK_API_KEY')
    print(f"Found: {len(deepseek_keys)} keys")
    
    for i, key in enumerate(deepseek_keys, 1):
        print(f"   Key #{i}: {key[:10]}... (length: {len(key)})")
    
    if len(deepseek_keys) != 8:
        print(f"⚠️ Expected 8 DeepSeek keys, got {len(deepseek_keys)}")
        print("\n💡 To add more keys:")
        print("1. Add to encrypted_secrets.json:")
        print("   DEEPSEEK_API_KEY_1, DEEPSEEK_API_KEY_2, etc.")
    else:
        print("✅ All 8 DeepSeek keys loaded!")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 Summary")
    print("=" * 80)
    print(f"Total encrypted keys: {len(available_keys)}")
    print(f"Perplexity keys: {len(perplexity_keys)} (expected: 4)")
    print(f"DeepSeek keys: {len(deepseek_keys)} (expected: 8)")
    print(f"Total API keys: {len(perplexity_keys) + len(deepseek_keys)} (expected: 12)")
    
    if len(perplexity_keys) == 4 and len(deepseek_keys) == 8:
        print("\n🎉 SUCCESS! All 12 API keys loaded correctly!")
        return True
    else:
        print("\n⚠️ WARNING: Not all keys loaded. Check encrypted_secrets.json")
        return False


if __name__ == "__main__":
    success = test_key_loading()
    
    if success:
        print("\n✅ Ready to use SimplifiedReliableMCP with encrypted keys!")
    else:
        print("\n❌ Fix the issues above before using SimplifiedReliableMCP")
    
    sys.exit(0 if success else 1)
