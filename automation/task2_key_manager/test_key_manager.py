"""
Тесты для KeyManager

Запуск:
    pytest test_key_manager.py -v
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from key_manager import KeyManager, with_keys


def test_singleton_pattern():
    """Тест: KeyManager должен быть singleton"""
    manager1 = KeyManager()
    manager2 = KeyManager()
    
    assert manager1 is manager2, "KeyManager должен быть singleton"
    print("✅ Singleton pattern работает")


def test_key_encryption_decryption():
    """Тест: Шифрование и расшифровка ключей"""
    manager = KeyManager()
    manager.clear()  # Очищаем предыдущие ключи
    
    test_encryption_key = "test_encryption_key_min_32_chars_long_12345"
    
    # Инициализация шифрования
    assert manager.initialize_encryption(test_encryption_key), "Инициализация шифрования должна пройти"
    
    # Тестовые данные
    test_secrets = {
        "TEST_API_KEY": "test_key_value_123",
        "ANOTHER_KEY": "another_value_456",
        "DEEPSEEK_API_KEY": "sk-deepseek-test-key-789"
    }
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name
    
    try:
        # Шифрование
        assert manager.encrypt_and_save(test_secrets, temp_file), "Шифрование должно пройти успешно"
        
        # Проверяем, что файл создан
        assert os.path.exists(temp_file), "Файл должен быть создан"
        
        # Проверяем, что данные зашифрованы (не в plain text)
        with open(temp_file, 'r') as f:
            encrypted_content = json.load(f)
        
        for key_name, encrypted_value in encrypted_content.items():
            assert encrypted_value != test_secrets[key_name], f"Ключ {key_name} должен быть зашифрован"
        
        # Очищаем manager для чистого теста загрузки
        manager.clear()
        assert not manager.has_keys(), "После clear() не должно быть ключей"
        
        # Загрузка и расшифровка
        assert manager.load_keys(temp_file), "Загрузка ключей должна пройти успешно"
        
        # Проверка значений
        for key_name, expected_value in test_secrets.items():
            actual_value = manager.get_key(key_name)
            assert actual_value == expected_value, f"Ключ {key_name} должен иметь правильное значение"
        
        # Проверка списка ключей
        available_keys = manager.get_available_keys()
        assert set(available_keys) == set(test_secrets.keys()), "Список ключей должен совпадать"
        
        print("✅ Шифрование и расшифровка работают корректно")
        
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_missing_key():
    """Тест: Несуществующий ключ должен возвращать None"""
    manager = KeyManager()
    
    result = manager.get_key("NON_EXISTENT_KEY_12345")
    assert result is None, "Несуществующий ключ должен возвращать None"
    
    print("✅ Обработка несуществующих ключей работает")


def test_has_keys():
    """Тест: has_keys() должен правильно определять наличие ключей"""
    manager = KeyManager()
    manager.clear()
    
    assert not manager.has_keys(), "После clear() не должно быть ключей"
    
    # Загружаем тестовые ключи
    test_encryption_key = "test_key_for_has_keys_test_min_32"
    manager.initialize_encryption(test_encryption_key)
    
    test_secrets = {"TEST_KEY": "test_value"}
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name
    
    try:
        manager.encrypt_and_save(test_secrets, temp_file)
        manager.clear()
        manager.load_keys(temp_file)
        
        assert manager.has_keys(), "После загрузки ключи должны быть доступны"
        
        print("✅ has_keys() работает корректно")
        
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_with_keys_decorator():
    """Тест: Декоратор @with_keys должен проверять наличие ключей"""
    manager = KeyManager()
    manager.clear()
    
    @with_keys
    def protected_function():
        return "success"
    
    # Без ключей должна быть ошибка
    with pytest.raises(RuntimeError):
        protected_function()
    
    # С ключами должно работать
    test_encryption_key = "test_decorator_key_min_32_chars"
    manager.initialize_encryption(test_encryption_key)
    
    test_secrets = {"TEST": "value"}
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name
    
    try:
        manager.encrypt_and_save(test_secrets, temp_file)
        manager.load_keys(temp_file)
        
        result = protected_function()
        assert result == "success", "С ключами функция должна работать"
        
        print("✅ Декоратор @with_keys работает корректно")
        
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_encryption_not_initialized():
    """Тест: Попытка загрузки без инициализации должна провалиться"""
    manager = KeyManager()
    manager._fernet = None  # Сброс инициализации
    
    result = manager.load_keys("nonexistent.json")
    assert not result, "Без инициализации шифрования load_keys должен провалиться"
    
    print("✅ Проверка инициализации работает")


if __name__ == "__main__":
    print("=" * 80)
    print("🧪 ЗАПУСК ТЕСТОВ KEY_MANAGER")
    print("=" * 80)
    print()
    
    # Запускаем тесты вручную
    try:
        test_singleton_pattern()
        test_key_encryption_decryption()
        test_missing_key()
        test_has_keys()
        test_with_keys_decorator()
        test_encryption_not_initialized()
        
        print()
        print("=" * 80)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n❌ ТЕСТ ПРОВАЛЕН: {e}")
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
