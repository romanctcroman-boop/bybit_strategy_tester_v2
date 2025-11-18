#!/usr/bin/env python3
"""
Автоматическое шифрование API ключей из .env файла

Этот скрипт:
1. Читает ENCRYPTION_KEY из .env
2. Читает API ключи из .env (DEEPSEEK_API_KEY, PERPLEXITY_API_KEY)
3. Шифрует их через KeyManager
4. Сохраняет в encrypted_secrets.json
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Добавляем путь к key_manager
sys.path.insert(0, str(Path(__file__).parent / "automation" / "task2_key_manager"))

from key_manager import KeyManager

# Загружаем .env
load_dotenv()


def main():
    print("=" * 80)
    print("🔐 АВТОМАТИЧЕСКОЕ ШИФРОВАНИЕ API КЛЮЧЕЙ")
    print("=" * 80)
    print()
    
    # Получение ключа шифрования из .env
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        print("❌ ENCRYPTION_KEY не найден в .env файле")
        return False
    
    print(f"✅ ENCRYPTION_KEY загружен: {encryption_key[:10]}...")
    
    # Получение API ключей из .env
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    perplexity_key = os.getenv("PERPLEXITY_API_KEY")
    
    if not deepseek_key and not perplexity_key:
        print("❌ Не найдены API ключи в .env файле")
        return False
    
    secrets = {}
    
    if deepseek_key:
        secrets["DEEPSEEK_API_KEY"] = deepseek_key
        print(f"✅ DEEPSEEK_API_KEY найден: {deepseek_key[:10]}...")
    
    if perplexity_key:
        secrets["PERPLEXITY_API_KEY"] = perplexity_key
        print(f"✅ PERPLEXITY_API_KEY найден: {perplexity_key[:10]}...")
    
    print(f"\nВсего ключей для шифрования: {len(secrets)}")
    print()
    
    # Инициализация KeyManager
    key_manager = KeyManager()
    
    if not key_manager.initialize_encryption(encryption_key):
        print("❌ Ошибка инициализации шифрования")
        return False
    
    print("✅ Шифрование инициализировано")
    
    # Шифрование и сохранение
    output_file = "encrypted_secrets.json"
    
    print(f"\n📝 Шифрование ключей в {output_file}...")
    
    if key_manager.encrypt_and_save(secrets, output_file):
        print()
        print("=" * 80)
        print("✅ УСПЕШНО!")
        print("=" * 80)
        print(f"📁 Файл: {output_file}")
        print(f"🔑 Зашифровано ключей: {len(secrets)}")
        print()
        print("📋 СЛЕДУЮЩИЕ ШАГИ:")
        print("-" * 40)
        print("1. ✅ encrypted_secrets.json создан")
        print("2. ✅ Ключи в .gitignore")
        print("3. 🔄 Интегрируйте KeyManager в MCP сервер")
        print()
        print("⚠️  ВАЖНО: НЕ удаляйте ключи из .env до тестирования!")
        print("=" * 80)
        return True
    else:
        print("❌ Ошибка при шифровании")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏸️  Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
