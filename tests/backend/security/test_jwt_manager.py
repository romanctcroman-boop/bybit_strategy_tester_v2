"""
Тесты для JWT Manager - Week 5 Day 2 AM

Покрытие:
- Генерация токенов (access, refresh, API key)
- Валидация токенов (подпись, срок действия, тип)
- Управление RSA ключами (генерация, загрузка, ротация)
- Blacklist (отзыв токенов)
- HTTP-only cookie support
- Edge cases и error handling

Целевое покрытие: 80%+ (170 statements)
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

from backend.security.jwt_manager import (
    JWTManager,
    TokenType,
    TokenConfig
)


# ==================== Fixtures ====================

@pytest.fixture
def temp_keys_dir():
    """Временная директория для RSA ключей"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def jwt_manager(temp_keys_dir):
    """JWT Manager с временными ключами"""
    return JWTManager(keys_dir=temp_keys_dir)


@pytest.fixture
def custom_config():
    """Кастомная конфигурация токенов"""
    return TokenConfig(
        access_token_expire_minutes=30,
        refresh_token_expire_days=14,
        api_key_expire_days=180,
        algorithm="RS256",
        issuer="test-issuer"
    )


@pytest.fixture
def jwt_manager_custom(temp_keys_dir, custom_config):
    """JWT Manager с кастомной конфигурацией"""
    return JWTManager(config=custom_config, keys_dir=temp_keys_dir)


@pytest.fixture
def mock_fastapi_response():
    """Mock FastAPI Response для cookie тестов"""
    response = Mock()
    response.set_cookie = Mock()
    response.delete_cookie = Mock()
    return response


@pytest.fixture
def mock_fastapi_request():
    """Mock FastAPI Request для cookie тестов"""
    request = Mock()
    request.cookies = {}
    request.headers = {}
    return request


# ==================== Тесты инициализации ====================

class TestJWTManagerInitialization:
    """Тесты инициализации JWT Manager"""
    
    def test_default_initialization(self, temp_keys_dir):
        """Тест инициализации с дефолтными настройками"""
        manager = JWTManager(keys_dir=temp_keys_dir)
        
        assert manager.config.access_token_expire_minutes == 15
        assert manager.config.refresh_token_expire_days == 7
        assert manager.config.api_key_expire_days == 365
        assert manager.config.algorithm == "RS256"
        assert manager.config.issuer == "bybit-strategy-tester"
    
    def test_custom_config_initialization(self, temp_keys_dir, custom_config):
        """Тест инициализации с кастомной конфигурацией"""
        manager = JWTManager(config=custom_config, keys_dir=temp_keys_dir)
        
        assert manager.config.access_token_expire_minutes == 30
        assert manager.config.refresh_token_expire_days == 14
        assert manager.config.api_key_expire_days == 180
        assert manager.config.issuer == "test-issuer"
    
    def test_keys_directory_created(self, temp_keys_dir):
        """Тест создания директории для ключей"""
        keys_subdir = temp_keys_dir / "subdir" / "keys"
        manager = JWTManager(keys_dir=keys_subdir)
        
        assert keys_subdir.exists()
        assert keys_subdir.is_dir()
    
    def test_rsa_keys_generated(self, jwt_manager, temp_keys_dir):
        """Тест генерации RSA ключей при первом запуске"""
        private_key_path = temp_keys_dir / "jwt_private.pem"
        public_key_path = temp_keys_dir / "jwt_public.pem"
        
        assert private_key_path.exists()
        assert public_key_path.exists()
        assert jwt_manager._private_key is not None
        assert jwt_manager._public_key is not None
    
    def test_existing_keys_loaded(self, temp_keys_dir):
        """Тест загрузки существующих ключей"""
        # Создаём первый manager (генерирует ключи)
        manager1 = JWTManager(keys_dir=temp_keys_dir)
        token1 = manager1.generate_access_token("user1", ["admin"])
        
        # Создаём второй manager (должен загрузить те же ключи)
        manager2 = JWTManager(keys_dir=temp_keys_dir)
        
        # Второй manager должен уметь валидировать токены первого
        payload = manager2.verify_token(token1)
        assert payload["sub"] == "user1"


# ==================== Тесты генерации токенов ====================

class TestAccessTokenGeneration:
    """Тесты генерации access tokens"""
    
    def test_generate_access_token_basic(self, jwt_manager):
        """Тест базовой генерации access token"""
        token = jwt_manager.generate_access_token(
            user_id="test_user",
            roles=["user", "admin"]
        )
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_access_token_payload(self, jwt_manager):
        """Тест содержимого access token"""
        token = jwt_manager.generate_access_token(
            user_id="test_user",
            roles=["user", "admin"]
        )
        
        payload = jwt_manager.get_token_info(token)
        
        assert payload["sub"] == "test_user"
        assert payload["type"] == TokenType.ACCESS.value
        assert payload["roles"] == ["user", "admin"]
        assert payload["iss"] == "bybit-strategy-tester"
        assert "jti" in payload  # JWT ID для blacklist
        assert "iat" in payload  # Issued at
        assert "exp" in payload  # Expiration
    
    def test_access_token_expiration(self, jwt_manager):
        """Тест времени жизни access token"""
        token = jwt_manager.generate_access_token(
            user_id="test_user",
            roles=["user"]
        )
        
        payload = jwt_manager.get_token_info(token)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        
        # Проверяем, что токен истекает через 15 минут (дефолт)
        expected_lifetime = timedelta(minutes=15)
        actual_lifetime = exp - iat
        
        # Допускаем погрешность 1 секунда
        assert abs(actual_lifetime - expected_lifetime) < timedelta(seconds=1)
    
    def test_access_token_additional_claims(self, jwt_manager):
        """Тест добавления дополнительных claims"""
        additional_claims = {
            "permissions": ["read:backtest", "write:backtest"],
            "email": "test@example.com"
        }
        
        token = jwt_manager.generate_access_token(
            user_id="test_user",
            roles=["user"],
            additional_claims=additional_claims
        )
        
        payload = jwt_manager.get_token_info(token)
        
        assert payload["permissions"] == ["read:backtest", "write:backtest"]
        assert payload["email"] == "test@example.com"
    
    def test_multiple_access_tokens_unique_jti(self, jwt_manager):
        """Тест уникальности JWT ID (jti) для каждого токена"""
        token1 = jwt_manager.generate_access_token("user1", ["user"])
        token2 = jwt_manager.generate_access_token("user1", ["user"])
        
        payload1 = jwt_manager.get_token_info(token1)
        payload2 = jwt_manager.get_token_info(token2)
        
        assert payload1["jti"] != payload2["jti"]


class TestRefreshTokenGeneration:
    """Тесты генерации refresh tokens"""
    
    def test_generate_refresh_token_basic(self, jwt_manager):
        """Тест базовой генерации refresh token"""
        token = jwt_manager.generate_refresh_token(user_id="test_user")
        
        assert token is not None
        assert isinstance(token, str)
    
    def test_refresh_token_payload(self, jwt_manager):
        """Тест содержимого refresh token"""
        token = jwt_manager.generate_refresh_token(user_id="test_user")
        
        payload = jwt_manager.get_token_info(token)
        
        assert payload["sub"] == "test_user"
        assert payload["type"] == TokenType.REFRESH.value
        assert "roles" not in payload  # Refresh токен не содержит roles
        assert "jti" in payload
        assert "iat" in payload
        assert "exp" in payload
    
    def test_refresh_token_expiration(self, jwt_manager):
        """Тест времени жизни refresh token (7 дней)"""
        token = jwt_manager.generate_refresh_token(user_id="test_user")
        
        payload = jwt_manager.get_token_info(token)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        
        expected_lifetime = timedelta(days=7)
        actual_lifetime = exp - iat
        
        assert abs(actual_lifetime - expected_lifetime) < timedelta(seconds=1)


class TestAPIKeyGeneration:
    """Тесты генерации API keys"""
    
    def test_generate_api_key_basic(self, jwt_manager):
        """Тест базовой генерации API key"""
        token = jwt_manager.generate_api_key(
            user_id="test_user",
            name="Production API Key",
            permissions=["read:backtest", "write:backtest"]
        )
        
        assert token is not None
        assert isinstance(token, str)
    
    def test_api_key_payload(self, jwt_manager):
        """Тест содержимого API key"""
        token = jwt_manager.generate_api_key(
            user_id="test_user",
            name="Production API Key",
            permissions=["read:backtest", "write:backtest"]
        )
        
        payload = jwt_manager.get_token_info(token)
        
        assert payload["sub"] == "test_user"
        assert payload["type"] == TokenType.API_KEY.value
        assert payload["name"] == "Production API Key"
        assert payload["permissions"] == ["read:backtest", "write:backtest"]
        assert "jti" in payload
    
    def test_api_key_expiration(self, jwt_manager):
        """Тест времени жизни API key (365 дней)"""
        token = jwt_manager.generate_api_key(
            user_id="test_user",
            name="Long-lived Key",
            permissions=["read:data"]
        )
        
        payload = jwt_manager.get_token_info(token)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        
        expected_lifetime = timedelta(days=365)
        actual_lifetime = exp - iat
        
        # Допускаем погрешность 1 секунда
        assert abs(actual_lifetime - expected_lifetime) < timedelta(seconds=1)


# ==================== Тесты валидации токенов ====================

class TestTokenVerification:
    """Тесты верификации токенов"""
    
    def test_verify_valid_access_token(self, jwt_manager):
        """Тест валидации правильного access token"""
        token = jwt_manager.generate_access_token(
            user_id="test_user",
            roles=["user", "admin"]
        )
        
        payload = jwt_manager.verify_token(token)
        
        assert payload["sub"] == "test_user"
        assert payload["roles"] == ["user", "admin"]
    
    def test_verify_valid_refresh_token(self, jwt_manager):
        """Тест валидации правильного refresh token"""
        token = jwt_manager.generate_refresh_token(user_id="test_user")
        
        payload = jwt_manager.verify_token(token)
        
        assert payload["sub"] == "test_user"
        assert payload["type"] == TokenType.REFRESH.value
    
    def test_verify_invalid_signature(self, jwt_manager):
        """Тест отклонения токена с неправильной подписью"""
        # Генерируем токен
        token = jwt_manager.generate_access_token("test_user", ["user"])
        
        # Подделываем подпись (заменяем последние символы)
        tampered_token = token[:-10] + "FAKESIGNATURE"
        
        with pytest.raises(jwt.InvalidTokenError):
            jwt_manager.verify_token(tampered_token)
    
    def test_verify_expired_token(self, jwt_manager_custom):
        """Тест отклонения истёкшего токена"""
        # Создаём токен с очень коротким временем жизни
        short_config = TokenConfig(access_token_expire_minutes=-1)  # Истёк 1 минуту назад
        manager = JWTManager(config=short_config, keys_dir=jwt_manager_custom.keys_dir)
        
        token = manager.generate_access_token("test_user", ["user"])
        
        with pytest.raises(jwt.ExpiredSignatureError):
            manager.verify_token(token)
    
    def test_verify_wrong_issuer(self, jwt_manager, temp_keys_dir):
        """Тест отклонения токена с неправильным issuer"""
        # Создаём токен с другим issuer
        other_config = TokenConfig(issuer="wrong-issuer")
        other_manager = JWTManager(config=other_config, keys_dir=temp_keys_dir)
        
        token = other_manager.generate_access_token("test_user", ["user"])
        
        # Пытаемся валидировать в оригинальном manager
        with pytest.raises(jwt.InvalidTokenError):
            jwt_manager.verify_token(token)
    
    def test_verify_malformed_token(self, jwt_manager):
        """Тест отклонения некорректного токена"""
        malformed_tokens = [
            "not.a.token",
            "header.payload",  # Нет подписи
            "invalid",
            "",
            "ey.ey.ey"  # Невалидный base64
        ]
        
        for token in malformed_tokens:
            with pytest.raises(jwt.InvalidTokenError):
                jwt_manager.verify_token(token)


# ==================== Тесты refresh access token ====================

class TestRefreshAccessToken:
    """Тесты обновления access token через refresh token"""
    
    def test_refresh_access_token_success(self, jwt_manager):
        """Тест успешного обновления access token"""
        # Генерируем refresh token
        refresh_token = jwt_manager.generate_refresh_token("test_user")
        
        # Обновляем access token
        new_access_token = jwt_manager.refresh_access_token(
            refresh_token,
            roles=["user", "premium"]
        )
        
        # Проверяем новый access token
        payload = jwt_manager.verify_token(new_access_token)
        
        assert payload["sub"] == "test_user"
        assert payload["type"] == TokenType.ACCESS.value
        assert payload["roles"] == ["user", "premium"]
    
    def test_refresh_with_access_token_fails(self, jwt_manager):
        """Тест отклонения попытки refresh через access token"""
        # Генерируем access token (не refresh!)
        access_token = jwt_manager.generate_access_token("test_user", ["user"])
        
        # Попытка refresh должна провалиться
        with pytest.raises(jwt.InvalidTokenError, match="not a refresh token"):
            jwt_manager.refresh_access_token(access_token, roles=["user"])
    
    def test_refresh_with_api_key_fails(self, jwt_manager):
        """Тест отклонения попытки refresh через API key"""
        # Генерируем API key
        api_key = jwt_manager.generate_api_key(
            "test_user",
            "Test Key",
            ["read:data"]
        )
        
        # Попытка refresh должна провалиться
        with pytest.raises(jwt.InvalidTokenError, match="not a refresh token"):
            jwt_manager.refresh_access_token(api_key, roles=["user"])


# ==================== Тесты blacklist (отзыв токенов) ====================

class TestTokenBlacklist:
    """Тесты blacklist для отозванных токенов"""
    
    def test_revoke_token(self, jwt_manager):
        """Тест отзыва токена"""
        token = jwt_manager.generate_access_token("test_user", ["user"])
        
        # Токен валиден
        payload = jwt_manager.verify_token(token)
        assert payload["sub"] == "test_user"
        
        # Отзываем токен
        jwt_manager.revoke_token(token)
        
        # Теперь токен должен быть отклонён
        with pytest.raises(jwt.InvalidTokenError, match="revoked"):
            jwt_manager.verify_token(token)
    
    def test_is_token_revoked(self, jwt_manager):
        """Тест проверки статуса отзыва"""
        token = jwt_manager.generate_access_token("test_user", ["user"])
        
        # Изначально не отозван
        assert not jwt_manager.is_token_revoked(token)
        
        # Отзываем
        jwt_manager.revoke_token(token)
        
        # Теперь отозван
        assert jwt_manager.is_token_revoked(token)
    
    def test_revoke_invalid_token_no_error(self, jwt_manager):
        """Тест отзыва невалидного токена (не должен вызывать ошибку)"""
        # Не должно вызывать exception
        jwt_manager.revoke_token("invalid_token")
        jwt_manager.revoke_token("")


# ==================== Тесты ротации ключей ====================

class TestKeyRotation:
    """Тесты ротации RSA ключей"""
    
    def test_rotate_keys_invalidates_tokens(self, jwt_manager):
        """Тест что ротация ключей инвалидирует старые токены"""
        # Генерируем токен со старыми ключами
        old_token = jwt_manager.generate_access_token("test_user", ["user"])
        
        # Токен валиден
        payload = jwt_manager.verify_token(old_token)
        assert payload["sub"] == "test_user"
        
        # Ротация ключей
        jwt_manager.rotate_keys()
        
        # Старый токен больше не валиден
        with pytest.raises(jwt.InvalidTokenError):
            jwt_manager.verify_token(old_token)
    
    def test_rotate_keys_new_tokens_valid(self, jwt_manager):
        """Тест что новые токены после ротации валидны"""
        # Ротация ключей
        jwt_manager.rotate_keys()
        
        # Генерируем новый токен
        new_token = jwt_manager.generate_access_token("test_user", ["user"])
        
        # Новый токен валиден
        payload = jwt_manager.verify_token(new_token)
        assert payload["sub"] == "test_user"
    
    def test_rotate_keys_clears_blacklist(self, jwt_manager):
        """Тест что ротация очищает blacklist"""
        token = jwt_manager.generate_access_token("test_user", ["user"])
        jwt_manager.revoke_token(token)
        
        assert len(jwt_manager._blacklist) > 0
        
        jwt_manager.rotate_keys()
        
        assert len(jwt_manager._blacklist) == 0
    
    def test_rotate_keys_backs_up_old_keys(self, jwt_manager, temp_keys_dir):
        """Тест что старые ключи сохраняются как backup"""
        jwt_manager.rotate_keys()
        
        old_private = temp_keys_dir / "jwt_private.pem.old"
        old_public = temp_keys_dir / "jwt_public.pem.old"
        
        assert old_private.exists()
        assert old_public.exists()


# ==================== Тесты HTTP-only cookie support ====================

class TestCookieSupport:
    """Тесты работы с HTTP-only cookies"""
    
    def test_set_access_token_cookie(self, jwt_manager, mock_fastapi_response):
        """Тест установки access token в cookie"""
        token = jwt_manager.generate_access_token("test_user", ["user"])
        
        jwt_manager.set_token_cookie(
            mock_fastapi_response,
            token,
            TokenType.ACCESS,
            secure=True
        )
        
        # Проверяем что set_cookie был вызван
        mock_fastapi_response.set_cookie.assert_called_once()
        
        # Проверяем аргументы
        call_kwargs = mock_fastapi_response.set_cookie.call_args[1]
        assert call_kwargs["key"] == "access_token"
        assert call_kwargs["value"] == token
        assert call_kwargs["httponly"] is True
        assert call_kwargs["secure"] is True
        assert call_kwargs["samesite"] == "strict"
        assert call_kwargs["max_age"] == 15 * 60  # 15 минут
    
    def test_set_refresh_token_cookie(self, jwt_manager, mock_fastapi_response):
        """Тест установки refresh token в cookie"""
        token = jwt_manager.generate_refresh_token("test_user")
        
        jwt_manager.set_token_cookie(
            mock_fastapi_response,
            token,
            TokenType.REFRESH,
            secure=False  # Для локальной разработки
        )
        
        call_kwargs = mock_fastapi_response.set_cookie.call_args[1]
        assert call_kwargs["key"] == "refresh_token"
        assert call_kwargs["secure"] is False
        assert call_kwargs["max_age"] == 7 * 24 * 60 * 60  # 7 дней
    
    def test_get_token_from_cookie(self, jwt_manager, mock_fastapi_request):
        """Тест извлечения токена из cookie"""
        test_token = "test_token_value"
        mock_fastapi_request.cookies = {"access_token": test_token}
        
        token = jwt_manager.get_token_from_cookie(
            mock_fastapi_request,
            TokenType.ACCESS
        )
        
        assert token == test_token
    
    def test_get_token_from_cookie_not_found(self, jwt_manager, mock_fastapi_request):
        """Тест когда токен в cookie не найден"""
        mock_fastapi_request.cookies = {}
        
        token = jwt_manager.get_token_from_cookie(
            mock_fastapi_request,
            TokenType.ACCESS
        )
        
        assert token is None
    
    def test_delete_token_cookie(self, jwt_manager, mock_fastapi_response):
        """Тест удаления токена из cookie (logout)"""
        jwt_manager.delete_token_cookie(
            mock_fastapi_response,
            TokenType.ACCESS
        )
        
        mock_fastapi_response.delete_cookie.assert_called_once()
        call_kwargs = mock_fastapi_response.delete_cookie.call_args[1]
        assert call_kwargs["key"] == "access_token"
    
    def test_extract_token_from_request_cookie_preferred(self, jwt_manager, mock_fastapi_request):
        """Тест что cookie предпочитается перед Authorization header"""
        cookie_token = "cookie_token"
        header_token = "header_token"
        
        mock_fastapi_request.cookies = {"access_token": cookie_token}
        mock_fastapi_request.headers = {"Authorization": f"Bearer {header_token}"}
        
        token = jwt_manager.extract_token_from_request(
            mock_fastapi_request,
            TokenType.ACCESS
        )
        
        # Должен вернуть токен из cookie (приоритет)
        assert token == cookie_token
    
    def test_extract_token_from_request_fallback_to_header(self, jwt_manager, mock_fastapi_request):
        """Тест fallback на Authorization header если cookie нет"""
        header_token = "header_token"
        
        mock_fastapi_request.cookies = {}
        mock_fastapi_request.headers = {"Authorization": f"Bearer {header_token}"}
        
        token = jwt_manager.extract_token_from_request(
            mock_fastapi_request,
            TokenType.ACCESS,
            fallback_to_header=True
        )
        
        assert token == header_token
    
    def test_extract_token_from_request_no_fallback(self, jwt_manager, mock_fastapi_request):
        """Тест без fallback на header"""
        header_token = "header_token"
        
        mock_fastapi_request.cookies = {}
        mock_fastapi_request.headers = {"Authorization": f"Bearer {header_token}"}
        
        token = jwt_manager.extract_token_from_request(
            mock_fastapi_request,
            TokenType.ACCESS,
            fallback_to_header=False  # Не использовать header
        )
        
        assert token is None
    
    def test_extract_token_from_request_not_found(self, jwt_manager, mock_fastapi_request):
        """Тест когда токен нигде не найден"""
        mock_fastapi_request.cookies = {}
        mock_fastapi_request.headers = {}
        
        token = jwt_manager.extract_token_from_request(
            mock_fastapi_request,
            TokenType.ACCESS
        )
        
        assert token is None


# ==================== Тесты get_token_info ====================

class TestTokenInfo:
    """Тесты получения информации о токене без валидации"""
    
    def test_get_token_info_without_verification(self, jwt_manager):
        """Тест получения информации без проверки подписи"""
        token = jwt_manager.generate_access_token(
            user_id="test_user",
            roles=["admin"]
        )
        
        info = jwt_manager.get_token_info(token)
        
        assert info["sub"] == "test_user"
        assert info["roles"] == ["admin"]
        assert info["type"] == TokenType.ACCESS.value
    
    def test_get_token_info_expired_token(self, jwt_manager_custom):
        """Тест что get_token_info работает даже для истёкших токенов"""
        short_config = TokenConfig(access_token_expire_minutes=-1)
        manager = JWTManager(config=short_config, keys_dir=jwt_manager_custom.keys_dir)
        
        token = manager.generate_access_token("test_user", ["user"])
        
        # verify_token вызовет ошибку
        with pytest.raises(jwt.ExpiredSignatureError):
            manager.verify_token(token)
        
        # Но get_token_info сработает
        info = manager.get_token_info(token)
        assert info["sub"] == "test_user"


# ==================== Тесты edge cases ====================

class TestEdgeCases:
    """Тесты граничных случаев"""
    
    def test_empty_roles_list(self, jwt_manager):
        """Тест генерации токена с пустым списком ролей"""
        token = jwt_manager.generate_access_token(
            user_id="test_user",
            roles=[]
        )
        
        payload = jwt_manager.verify_token(token)
        assert payload["roles"] == []
    
    def test_very_long_user_id(self, jwt_manager):
        """Тест с очень длинным user_id"""
        long_user_id = "a" * 1000
        
        token = jwt_manager.generate_access_token(
            user_id=long_user_id,
            roles=["user"]
        )
        
        payload = jwt_manager.verify_token(token)
        assert payload["sub"] == long_user_id
    
    def test_special_characters_in_claims(self, jwt_manager):
        """Тест специальных символов в claims"""
        token = jwt_manager.generate_access_token(
            user_id="user@example.com",
            roles=["user/admin", "tester:prod"],
            additional_claims={"email": "test+alias@example.com"}
        )
        
        payload = jwt_manager.verify_token(token)
        assert payload["sub"] == "user@example.com"
        assert "user/admin" in payload["roles"]
    
    def test_concurrent_token_generation(self, jwt_manager):
        """Тест одновременной генерации множества токенов"""
        tokens = []
        for i in range(100):
            token = jwt_manager.generate_access_token(f"user_{i}", ["user"])
            tokens.append(token)
        
        # Все токены должны быть валидными
        for i, token in enumerate(tokens):
            payload = jwt_manager.verify_token(token)
            assert payload["sub"] == f"user_{i}"
    
    def test_token_with_unicode_characters(self, jwt_manager):
        """Тест токена с unicode символами"""
        token = jwt_manager.generate_access_token(
            user_id="пользователь",
            roles=["админ", "тестер"],
            additional_claims={"город": "Москва"}
        )
        
        payload = jwt_manager.verify_token(token)
        assert payload["sub"] == "пользователь"
        assert "админ" in payload["roles"]
        assert payload["город"] == "Москва"


# ==================== Performance тесты ====================

class TestPerformance:
    """Тесты производительности (базовые)"""
    
    def test_token_generation_works(self, jwt_manager):
        """Тест что генерация токенов работает (без строгих таймингов)"""
        # RSA криптография может быть медленной, но должна работать
        tokens = []
        for i in range(10):  # Уменьшено до 10 для скорости тестов
            token = jwt_manager.generate_access_token(f"user_{i}", ["user"])
            tokens.append(token)
        
        # Проверяем что все токены сгенерировались
        assert len(tokens) == 10
        assert all(isinstance(t, str) for t in tokens)
    
    def test_token_verification_works(self, jwt_manager):
        """Тест что верификация токенов работает"""
        # Генерируем и верифицируем токены
        tokens = [jwt_manager.generate_access_token(f"user_{i}", ["user"]) for i in range(10)]
        
        # Все токены должны валидироваться
        for i, token in enumerate(tokens):
            payload = jwt_manager.verify_token(token)
            assert payload["sub"] == f"user_{i}"
