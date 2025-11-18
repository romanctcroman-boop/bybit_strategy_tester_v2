#!/usr/bin/env python3
"""
Тест расшифровки encrypted_secrets.json
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "automation" / "task2_key_manager"))
from key_manager import KeyManager

load_dotenv()

def test_decryption():
    print("=" * 80)
    print("🧪 ТЕСТ РАСШИФРОВКИ КЛЮЧЕЙ")
    print("=" * 80)
    print()
    
    key_manager = KeyManager()
    
    # Инициализация
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not key_manager.initialize_encryption(encryption_key):
        print("❌ Ошибка инициализации")
        return False
    
    print("✅ Инициализация успешна")
    
    # Загрузка ключей
    if not key_manager.load_keys("encrypted_secrets.json"):
        print("❌ Ошибка загрузки ключей")
        return False
    
    print("✅ Ключи загружены")
    print()
    
    # Проверка ключей
    print("📋 Доступные ключи:")
    for key_name in key_manager.get_available_keys():
        key_value = key_manager.get_key(key_name)
        print(f"  ✅ {key_name}: {key_value[:15]}... (расшифрован)")
    
    print()
    
    # Сравнение с оригиналом
    print("🔍 Сравнение с оригинальными ключами из .env:")
    
    original_deepseek = os.getenv("DEEPSEEK_API_KEY")
    decrypted_deepseek = key_manager.get_key("DEEPSEEK_API_KEY")
    
    if original_deepseek == decrypted_deepseek:
        print("  ✅ DEEPSEEK_API_KEY: Совпадает!")
    else:
        print("  ❌ DEEPSEEK_API_KEY: НЕ совпадает!")
        return False
    
    original_perplexity = os.getenv("PERPLEXITY_API_KEY")
    decrypted_perplexity = key_manager.get_key("PERPLEXITY_API_KEY")
    
    if original_perplexity == decrypted_perplexity:
        print("  ✅ PERPLEXITY_API_KEY: Совпадает!")
    else:
        print("  ❌ PERPLEXITY_API_KEY: НЕ совпадает!")
        return False
    
    print()
    print("=" * 80)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("=" * 80)
    print()
    print("🎯 KeyManager готов к интеграции в MCP сервер!")
    print()
    
    return True

if __name__ == "__main__":
    try:
        success = test_decryption()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
