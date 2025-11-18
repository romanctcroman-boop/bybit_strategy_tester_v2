"""
Pytest тесты для Key Rotation и Secure Storage
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.security.crypto import CryptoManager
from backend.security.key_rotation import KeyRotationManager, KeyVersion
from backend.security.secure_storage import SecureStorageManager


class TestKeyRotation:
    """Тесты для KeyRotationManager"""
    
    @pytest.fixture
    def temp_config(self):
        """Создаёт временный config файл"""
        temp_dir = Path(tempfile.mkdtemp())
        config_path = temp_dir / "key_rotation.json"
        yield config_path
        shutil.rmtree(temp_dir)
    
    def test_initialization(self, temp_config):
        """Тест инициализации"""
        manager = KeyRotationManager(temp_config, rotation_days=30)
        
        assert manager.current_version == 0
        assert len(manager.versions) == 0
        assert manager.rotation_days == 30
    
    def test_create_first_version(self, temp_config):
        """Тест создания первой версии ключа"""
        manager = KeyRotationManager(temp_config, rotation_days=30)
        
        version = manager.create_new_version("test_master_key_1")
        
        assert version.version == 1
        assert version.is_active
        assert manager.current_version == 1
        assert len(manager.versions) == 1
    
    def test_create_second_version_deactivates_first(self, temp_config):
        """Тест что вторая версия деактивирует первую"""
        manager = KeyRotationManager(temp_config, rotation_days=30)
        
        v1 = manager.create_new_version("master_key_v1")
        v2 = manager.create_new_version("master_key_v2")
        
        assert v2.version == 2
        assert v2.is_active
        assert not v1.is_active  # Первая версия деактивирована
        assert manager.current_version == 2
    
    def test_needs_rotation_fresh_key(self, temp_config):
        """Тест что свежий ключ не требует ротации"""
        manager = KeyRotationManager(temp_config, rotation_days=30)
        manager.create_new_version("test_key")
        
        assert not manager.needs_rotation()
    
    def test_get_current_version(self, temp_config):
        """Тест получения текущей версии"""
        manager = KeyRotationManager(temp_config, rotation_days=30)
        
        # До создания версий
        assert manager.get_current_version() is None
        
        # После создания
        v1 = manager.create_new_version("test_key")
        current = manager.get_current_version()
        
        assert current is not None
        assert current.version == v1.version
        assert current.is_active
    
    def test_rotate_secrets(self, temp_config):
        """Тест ротации секретов"""
        manager = KeyRotationManager(temp_config, rotation_days=30)
        
        # Создаём две версии ключей
        old_crypto = CryptoManager("old_master_key")
        new_crypto = CryptoManager("new_master_key")
        
        # Шифруем секреты старым ключом
        secrets = {
            "API_KEY_1": old_crypto.encrypt("secret_value_1"),
            "API_KEY_2": old_crypto.encrypt("secret_value_2"),
            "API_KEY_3": old_crypto.encrypt("secret_value_3")
        }
        
        # Ротация
        rotated = manager.rotate_secrets(old_crypto, new_crypto, secrets)
        
        # Проверяем что все секреты ротированы
        assert len(rotated) == 3
        
        for key_name in secrets:
            # Расшифровываем новым ключом
            decrypted_new = new_crypto.decrypt(rotated[key_name])
            
            # Расшифровываем старым ключом для сравнения
            decrypted_old = old_crypto.decrypt(secrets[key_name])
            
            # Должны быть равны
            assert decrypted_new == decrypted_old
    
    def test_get_rotation_status(self, temp_config):
        """Тест получения статуса ротации"""
        manager = KeyRotationManager(temp_config, rotation_days=30)
        
        # До создания версий
        status = manager.get_rotation_status()
        assert status["status"] == "no_active_key"
        assert status["needs_rotation"] == True
        
        # После создания версии
        manager.create_new_version("test_key")
        status = manager.get_rotation_status()
        
        assert status["status"] == "ok"
        assert status["current_version"] == 1
        assert status["needs_rotation"] == False
        assert "days_until_expiry" in status
    
    def test_cleanup_expired_versions(self, temp_config):
        """Тест очистки истёкших версий"""
        manager = KeyRotationManager(temp_config, rotation_days=1)
        
        # Создаём версию с коротким сроком действия
        v1 = manager.create_new_version("key_v1")
        
        # Модифицируем expiry date чтобы сделать её истёкшей
        v1.expires_at = (datetime.now() - timedelta(days=10)).isoformat()
        manager._save_config()
        
        # Создаём новую активную версию
        v2 = manager.create_new_version("key_v2")
        
        assert len(manager.versions) == 2
        
        # Очищаем истёкшие (grace period = 7 дней)
        manager.cleanup_expired_versions(grace_period_days=7)
        
        # Истёкшая версия должна быть удалена
        assert len(manager.versions) == 1
        assert manager.versions[0].version == v2.version
    
    def test_persistence(self, temp_config):
        """Тест сохранения и загрузки конфигурации"""
        # Создаём manager и версию
        manager1 = KeyRotationManager(temp_config, rotation_days=30)
        v1 = manager1.create_new_version("test_key")
        
        # Создаём новый manager с тем же файлом
        manager2 = KeyRotationManager(temp_config, rotation_days=30)
        
        # Должен загрузить существующую конфигурацию
        assert manager2.current_version == 1
        assert len(manager2.versions) == 1
        assert manager2.versions[0].version == v1.version


class TestSecureStorage:
    """Тесты для SecureStorageManager"""
    
    @pytest.fixture
    def storage_manager(self):
        """Создаёт SecureStorageManager"""
        manager = SecureStorageManager(app_name="TestApp")
        yield manager
        # Cleanup после теста
        try:
            manager.delete_master_key()
        except:
            pass
    
    def test_initialization(self, storage_manager):
        """Тест инициализации"""
        assert storage_manager.app_name == "TestApp"
        assert storage_manager.key_name == "master_encryption_key"
        assert storage_manager.system in ["Windows", "Linux", "Darwin"]
    
    def test_store_and_retrieve(self, storage_manager):
        """Тест сохранения и получения ключа"""
        test_key = "test_master_key_12345"
        
        # Сохраняем
        success = storage_manager.store_master_key(test_key)
        assert success
        
        # Получаем
        retrieved = storage_manager.retrieve_master_key()
        assert retrieved == test_key
    
    def test_delete(self, storage_manager):
        """Тест удаления ключа"""
        test_key = "test_key_to_delete"
        
        # Сохраняем
        storage_manager.store_master_key(test_key)
        
        # Проверяем что существует
        assert storage_manager.retrieve_master_key() == test_key
        
        # Удаляем
        deleted = storage_manager.delete_master_key()
        assert deleted
        
        # Проверяем что удалён
        assert storage_manager.retrieve_master_key() is None
    
    def test_retrieve_nonexistent(self, storage_manager):
        """Тест получения несуществующего ключа"""
        # Убедимся что ключа нет
        storage_manager.delete_master_key()
        
        # Попытка получить
        retrieved = storage_manager.retrieve_master_key()
        assert retrieved is None
    
    def test_get_storage_info(self, storage_manager):
        """Тест получения информации о хранилище"""
        info = storage_manager.get_storage_info()
        
        assert "platform" in info
        assert "app_name" in info
        assert "storage_type" in info
        assert "key_exists" in info
        
        assert info["app_name"] == "TestApp"
        assert info["platform"] == storage_manager.system
    
    def test_multiple_stores_overwrite(self, storage_manager):
        """Тест что повторное сохранение перезаписывает ключ"""
        key1 = "first_key"
        key2 = "second_key"
        
        # Сохраняем первый ключ
        storage_manager.store_master_key(key1)
        assert storage_manager.retrieve_master_key() == key1
        
        # Сохраняем второй ключ
        storage_manager.store_master_key(key2)
        assert storage_manager.retrieve_master_key() == key2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
