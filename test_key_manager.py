"""
Test KeyManager - проверка работы зашифрованных ключей
"""
from dotenv import load_dotenv
load_dotenv()

import sys
sys.path.insert(0, 'backend')

from security.key_manager import get_key_manager

def test_key_manager():
    print("\n" + "="*70)
    print("  🔐 ТЕСТ: KeyManager - Безопасное получение ключей")
    print("="*70 + "\n")
    
    # Получаем менеджер ключей
    km = get_key_manager()
    
    # Список ключей (замаскированные)
    keys = km.list_keys_masked()
    
    print(f"📊 Найдено ключей: {len(keys)}\n")
    
    for key_name, masked_value in keys.items():
        print(f"  ✅ {key_name}: {masked_value}")
    
    # Проверяем что можем получить незамаскированные ключи
    print("\n" + "="*70)
    print("  🔓 ТЕСТ: Расшифровка ключей")
    print("="*70 + "\n")
    
    try:
        perplexity_key = km.get_decrypted_key("PERPLEXITY_API_KEY")
        print(f"  ✅ PERPLEXITY_API_KEY: {perplexity_key[:10]}...{perplexity_key[-10:]}")
        print(f"     Длина: {len(perplexity_key)} символов")
        
        deepseek_key = km.get_decrypted_key("DEEPSEEK_API_KEY")
        print(f"  ✅ DEEPSEEK_API_KEY: {deepseek_key[:10]}...{deepseek_key[-10:]}")
        print(f"     Длина: {len(deepseek_key)} символов")
        
        print("\n" + "="*70)
        print("  ✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n  ❌ ОШИБКА: {e}\n")
        return False
    
    return True

if __name__ == "__main__":
    success = test_key_manager()
    exit(0 if success else 1)
