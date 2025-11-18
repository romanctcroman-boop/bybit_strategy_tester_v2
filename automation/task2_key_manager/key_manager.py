"""
KeyManager - Безопасное управление API ключами для MCP сервера

Singleton класс для:
- Шифрования/расшифровки API ключей
- Безопасного хранения в encrypted_secrets.json
- Предоставления доступа к ключам без логирования
"""

import os
import json
import logging
from typing import Optional, Dict
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)


class KeyManager:
    """
    Singleton класс для безопасного управления API ключами
    
    Использование:
        key_manager = KeyManager()
        key_manager.initialize_encryption(encryption_key)
        key_manager.load_keys("encrypted_secrets.json")
        api_key = key_manager.get_key("DEEPSEEK_API_KEY")
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KeyManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._keys: Dict[str, str] = {}
            self._fernet: Optional[Fernet] = None
            self._initialized = True
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Производный ключ из пароля с использованием PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def initialize_encryption(self, encryption_key: str) -> bool:
        """
        Инициализация шифрования с ключом из .env
        
        Args:
            encryption_key: Ключ шифрования (минимум 32 символа рекомендуется)
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            # Генерируем соль из ключа (первые 16 байт)
            # Для production используйте отдельную соль
            salt = encryption_key.encode()[:16].ljust(16, b'0')
            
            derived_key = self._derive_key(encryption_key, salt)
            self._fernet = Fernet(derived_key)
            
            logger.info("Шифрование успешно инициализировано")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации шифрования: {str(e)}")
            return False
    
    def load_keys(self, secrets_file: str = "encrypted_secrets.json") -> bool:
        """
        Загрузка и расшифровка ключей из файла
        
        Args:
            secrets_file: Путь к файлу с зашифрованными ключами
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            if not self._fernet:
                logger.error("Шифрование не инициализировано. Вызовите initialize_encryption() сначала.")
                return False
            
            secrets_path = Path(secrets_file)
            if not secrets_path.exists():
                logger.error(f"Файл секретов не найден: {secrets_file}")
                return False
            
            with open(secrets_path, 'r', encoding='utf-8') as f:
                encrypted_data = json.load(f)
            
            # Расшифровка каждого ключа
            successful_keys = 0
            for key_name, encrypted_value in encrypted_data.items():
                try:
                    decrypted_value = self._fernet.decrypt(encrypted_value.encode()).decode()
                    self._keys[key_name] = decrypted_value
                    successful_keys += 1
                    # НЕ логируем значение ключа!
                    logger.info(f"Ключ {key_name} успешно расшифрован")
                except Exception as e:
                    logger.error(f"Ошибка расшифровки ключа {key_name}: {str(e)}")
                    return False
            
            logger.info(f"Успешно загружено ключей: {successful_keys}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки ключей: {str(e)}")
            return False
    
    def get_key(self, key_name: str) -> Optional[str]:
        """
        Получение ключа по имени
        
        Args:
            key_name: Имя ключа (например: DEEPSEEK_API_KEY)
            
        Returns:
            Значение ключа или None если не найден
        """
        key_value = self._keys.get(key_name)
        if not key_value:
            logger.warning(f"Ключ {key_name} не найден в загруженных ключах")
        return key_value
    
    def get_all_keys(self, key_prefix: str) -> list[str]:
        """
        Получение всех ключей с определенным префиксом
        
        Полезно для получения нескольких API ключей одного сервиса.
        
        Args:
            key_prefix: Префикс ключа (например: DEEPSEEK_API_KEY)
            
        Returns:
            Список значений ключей (DEEPSEEK_API_KEY, DEEPSEEK_API_KEY_2, etc.)
            
        Examples:
            >>> # Получить все DeepSeek ключи
            >>> keys = key_manager.get_all_keys("DEEPSEEK_API_KEY")
            >>> # Вернет: ["sk-key1", "sk-key2", "sk-key3", "sk-key4"]
        """
        matching_keys = []
        
        # Добавляем основной ключ
        main_key = self._keys.get(key_prefix)
        if main_key:
            matching_keys.append(main_key)
        
        # Проверяем пронумерованные ключи (_1, _2, _3, _4)
        for i in range(1, 10):  # Поддерживаем до 10 ключей
            numbered_key = self._keys.get(f"{key_prefix}_{i}")
            if numbered_key:
                matching_keys.append(numbered_key)
        
        if not matching_keys:
            logger.warning(f"Ключи с префиксом {key_prefix} не найдены")
        else:
            logger.info(f"Найдено {len(matching_keys)} ключей с префиксом {key_prefix}")
        
        return matching_keys
    
    def encrypt_and_save(self, secrets: Dict[str, str], output_file: str = "encrypted_secrets.json") -> bool:
        """
        Шифрование и сохранение секретов в файл
        
        Args:
            secrets: Словарь с ключами для шифрования {имя: значение}
            output_file: Путь к выходному файлу
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            if not self._fernet:
                logger.error("Шифрование не инициализировано")
                return False
            
            encrypted_data = {}
            for key_name, value in secrets.items():
                encrypted_value = self._fernet.encrypt(value.encode())
                encrypted_data[key_name] = encrypted_value.decode()
                logger.info(f"Ключ {key_name} зашифрован")
            
            output_path = Path(output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(encrypted_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Секреты успешно сохранены в {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка шифрования секретов: {str(e)}")
            return False
    
    def has_keys(self) -> bool:
        """Проверка наличия загруженных ключей"""
        return len(self._keys) > 0
    
    def get_available_keys(self) -> list:
        """
        Получение списка доступных ключей (без значений!)
        
        Returns:
            Список имен ключей
        """
        return list(self._keys.keys())
    
    def clear(self):
        """Очистка всех загруженных ключей из памяти"""
        self._keys.clear()
        logger.info("Все ключи очищены из памяти")


def with_keys(func):
    """
    Декоратор для защиты MCP tools - проверяет наличие необходимых ключей
    
    Использование:
        @with_keys
        async def my_mcp_tool():
            key_manager = KeyManager()
            api_key = key_manager.get_key("API_KEY")
            # ... использование ключа
    """
    def wrapper(*args, **kwargs):
        key_manager = KeyManager()
        if not key_manager.has_keys():
            raise RuntimeError("API ключи не загружены. Проверьте инициализацию KeyManager.")
        return func(*args, **kwargs)
    return wrapper
