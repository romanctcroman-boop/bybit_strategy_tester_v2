#!/usr/bin/env python3
"""
Утилита для первоначального шифрования секретов

Использование:
    python encrypt_secrets.py
    
Следуйте инструкциям для ввода:
1. ENCRYPTION_KEY (будет скрыт)
2. Имена и значения API ключей
"""

import os
import sys
import getpass
from pathlib import Path

# Добавляем путь к key_manager
sys.path.insert(0, str(Path(__file__).parent))

from key_manager import KeyManager


def main():
    print("=" * 80)
    print("🔐 УТИЛИТА ШИФРОВАНИЯ СЕКРЕТОВ ДЛЯ MCP СЕРВЕРА")
    print("=" * 80)
    print()
    
    # Получение ключа шифрования
    print("Шаг 1: Ключ шифрования")
    print("-" * 40)
    encryption_key = getpass.getpass("Введите ENCRYPTION_KEY (минимум 16 символов): ")
    
    if not encryption_key:
        print("❌ Ошибка: ENCRYPTION_KEY не может быть пустым")
        return
    
    if len(encryption_key) < 16:
        print("⚠️  Предупреждение: Ключ слишком короткий (минимум 16 символов)")
        response = input("Продолжить? (y/n): ").lower()
        if response != 'y':
            return
    
    # Инициализация KeyManager
    key_manager = KeyManager()
    if not key_manager.initialize_encryption(encryption_key):
        print("❌ Ошибка инициализации шифрования")
        return
    
    print("✅ Шифрование инициализировано")
    print()
    
    # Ввод секретов
    print("Шаг 2: Ввод API ключей")
    print("-" * 40)
    print("Введите API ключи (оставьте имя пустым для завершения)")
    print()
    
    secrets = {}
    
    # Предлагаем стандартные ключи
    default_keys = ["DEEPSEEK_API_KEY", "PERPLEXITY_API_KEY"]
    
    for default_key in default_keys:
        response = input(f"Добавить {default_key}? (y/n): ").lower()
        if response == 'y':
            key_value = getpass.getpass(f"  Значение для {default_key}: ").strip()
            if key_value:
                secrets[default_key] = key_value
                print(f"  ✅ {default_key} добавлен")
            else:
                print(f"  ⏭️  Пропущен")
    
    print()
    print("Дополнительные ключи (или Enter для завершения):")
    
    while True:
        key_name = input("\nИмя ключа: ").strip()
        if not key_name:
            break
        
        key_value = getpass.getpass(f"Значение для {key_name}: ").strip()
        if not key_value:
            print("⏭️  Значение пустое, пропускаем...")
            continue
        
        secrets[key_name] = key_value
        print(f"✅ Ключ {key_name} добавлен")
    
    if not secrets:
        print("\n⚠️  Не добавлено ни одного ключа")
        return
    
    print()
    print(f"Всего добавлено ключей: {len(secrets)}")
    print()
    
    # Выбор файла для сохранения
    output_file = input("Файл для сохранения [encrypted_secrets.json]: ").strip()
    if not output_file:
        output_file = "encrypted_secrets.json"
    
    # Проверка существования файла
    if Path(output_file).exists():
        response = input(f"⚠️  Файл {output_file} уже существует. Перезаписать? (y/n): ").lower()
        if response != 'y':
            print("Отменено")
            return
    
    # Шифрование и сохранение
    print()
    print("Шифрование...")
    
    if key_manager.encrypt_and_save(secrets, output_file):
        print()
        print("=" * 80)
        print("✅ УСПЕШНО!")
        print("=" * 80)
        print(f"📁 Файл: {output_file}")
        print(f"🔑 Ключей: {len(secrets)}")
        print()
        print("📋 ВАЖНЫЕ ИНСТРУКЦИИ:")
        print("-" * 40)
        print("1. ✅ Добавьте ENCRYPTION_KEY в .env файл:")
        print(f"     ENCRYPTION_KEY={encryption_key[:10]}...  (полный ключ)")
        print()
        print("2. ✅ Добавьте в .gitignore:")
        print(f"     {output_file}")
        print("     .env")
        print()
        print("3. 🔒 Храните ENCRYPTION_KEY в безопасном месте!")
        print()
        print("4. 🚀 Теперь можно запускать MCP сервер")
        print("=" * 80)
    else:
        print("❌ Ошибка при шифровании секретов")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏸️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
