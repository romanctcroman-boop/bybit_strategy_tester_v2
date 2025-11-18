"""
Unit-тесты для unified API providers.

Тесты:
- Базовый класс AIProvider
- PerplexityProvider
- DeepSeekProvider
- ProviderManager
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Добавляем mcp-server в path
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-server"))

from api import (
    AIProvider,
    PerplexityProvider,
    DeepSeekProvider,
    ProviderManager,
    RateLimitError,
    AuthenticationError,
    TimeoutError
)


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ PerplexityProvider
# ═══════════════════════════════════════════════════════════════════════════

class TestPerplexityProvider:
    """Тесты для PerplexityProvider"""
    
    @pytest.fixture
    def provider(self):
        """Fixture для создания провайдера"""
        return PerplexityProvider(api_key="test-key-123")
    
    def test_initialization(self, provider):
        """Тест инициализации провайдера"""
        assert provider.name == "Perplexity"
        assert provider.api_key == "test-key-123"
        assert provider.base_url == "https://api.perplexity.ai/chat/completions"  # base_url, не api_url
    
    def test_model_normalization(self, provider):
        """Тест нормализации старых моделей"""
        # Старые модели
        assert provider._normalize_model_name("llama-3.1-sonar-small-128k-online") == "sonar"
        assert provider._normalize_model_name("llama-3.1-sonar-large-128k-online") == "sonar-pro"
        assert provider._normalize_model_name("llama-3.1-sonar-huge-128k-online") == "sonar-pro"
        
        # Новые модели (без изменений)
        assert provider._normalize_model_name("sonar") == "sonar"
        assert provider._normalize_model_name("sonar-pro") == "sonar-pro"
    
    def test_build_request_payload(self, provider):
        """Тест построения payload"""
        payload = provider._build_request_payload(
            query="Test query",
            model="sonar",
            max_tokens=2000,
            temperature=0.2
        )
        
        assert payload["model"] == "sonar"
        assert len(payload["messages"]) == 2  # system + user
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == "Test query"
        assert payload["max_tokens"] == 2000
        assert payload["temperature"] == 0.2
    
    def test_parse_response(self, provider):
        """Тест парсинга ответа"""
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Test answer"
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            },
            "citations": ["source1.com", "source2.com"]
        }
        
        parsed = provider._parse_response(mock_response)
        
        # _parse_response не возвращает success/provider, только данные
        assert parsed["answer"] == "Test answer"
        assert parsed["usage"]["total_tokens"] == 30
        assert len(parsed["sources"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ DeepSeekProvider
# ═══════════════════════════════════════════════════════════════════════════

class TestDeepSeekProvider:
    """Тесты для DeepSeekProvider"""
    
    @pytest.fixture
    def provider(self):
        """Fixture для создания провайдера"""
        return DeepSeekProvider(api_key="test-key-456")
    
    def test_initialization(self, provider):
        """Тест инициализации провайдера"""
        assert provider.name == "DeepSeek"
        assert provider.api_key == "test-key-456"
        assert provider.base_url == "https://api.deepseek.com/chat/completions"  # base_url, не api_url
    
    def test_build_request_payload(self, provider):
        """Тест построения payload"""
        payload = provider._build_request_payload(
            query="Test query",
            model="deepseek-chat",
            max_tokens=4000
        )
        
        assert payload["model"] == "deepseek-chat"
        assert len(payload["messages"]) == 2  # system + user
        assert payload["messages"][1]["content"] == "Test query"
        assert payload["max_tokens"] == 4000
    
    def test_parse_response_with_reasoning(self, provider):
        """Тест парсинга ответа с reasoning"""
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Test answer",
                    "reasoning_content": "Detailed reasoning process"
                }
            }],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 25,
                "total_tokens": 40
            }
        }
        
        parsed = provider._parse_response(mock_response)
        
        # _parse_response не возвращает success/provider, только данные
        assert parsed["answer"] == "Test answer"
        assert "reasoning" in parsed  # reasoning может быть в ответе
        assert parsed["usage"]["total_tokens"] == 40
    
    def test_parse_response_without_reasoning(self, provider):
        """Тест парсинга ответа без reasoning"""
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Test answer"
                }
            }],
            "usage": {
                "total_tokens": 30
            }
        }
        
        parsed = provider._parse_response(mock_response)
        
        # _parse_response не возвращает success/provider, только данные
        assert parsed["answer"] == "Test answer"
        # reasoning может отсутствовать или быть None


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ ProviderManager
# ═══════════════════════════════════════════════════════════════════════════

class TestProviderManager:
    """Тесты для ProviderManager"""
    
    @pytest.fixture
    def manager(self):
        """Fixture для создания менеджера"""
        return ProviderManager()
    
    @pytest.fixture
    def mock_perplexity(self):
        """Mock для Perplexity провайдера"""
        provider = MagicMock(spec=PerplexityProvider)
        provider.name = "Perplexity"
        provider.generate_response = AsyncMock(return_value={
            "success": True,
            "answer": "Perplexity answer",
            "provider": "Perplexity"
        })
        return provider
    
    @pytest.fixture
    def mock_deepseek(self):
        """Mock для DeepSeek провайдера"""
        provider = MagicMock(spec=DeepSeekProvider)
        provider.name = "DeepSeek"
        provider.generate_response = AsyncMock(return_value={
            "success": True,
            "answer": "DeepSeek answer",
            "provider": "DeepSeek"
        })
        return provider
    
    def test_initialization(self, manager):
        """Тест инициализации менеджера"""
        assert len(manager.providers) == 0
        assert len(manager.weights) == 0
        assert len(manager.stats) == 0
    
    def test_register_provider(self, manager, mock_perplexity):
        """Тест регистрации провайдера"""
        manager.register_provider(mock_perplexity, weight=0.7, enabled=True)
        
        assert "perplexity" in manager.providers
        assert manager.weights["perplexity"] == 0.7
        assert "perplexity" in manager.stats
        assert manager.stats["perplexity"]["total_requests"] == 0
    
    def test_register_disabled_provider(self, manager, mock_perplexity):
        """Тест регистрации отключенного провайдера"""
        manager.register_provider(mock_perplexity, weight=0.5, enabled=False)
        
        assert "perplexity" not in manager.providers
    
    def test_get_provider_by_name(self, manager, mock_perplexity, mock_deepseek):
        """Тест получения провайдера по имени"""
        manager.register_provider(mock_perplexity, weight=0.7)
        manager.register_provider(mock_deepseek, weight=0.3)
        
        provider = manager.get_provider(preferred="perplexity")
        assert provider.name == "Perplexity"
        
        provider = manager.get_provider(preferred="deepseek")
        assert provider.name == "DeepSeek"
    
    def test_get_provider_weighted_random(self, manager, mock_perplexity, mock_deepseek):
        """Тест weighted random выбора"""
        manager.register_provider(mock_perplexity, weight=0.7)
        manager.register_provider(mock_deepseek, weight=0.3)
        
        # Выбираем провайдера несколько раз
        selected = []
        for _ in range(100):
            provider = manager.get_provider()
            selected.append(provider.name)
        
        # Проверяем, что оба провайдера используются
        assert "Perplexity" in selected
        assert "DeepSeek" in selected
        
        # Perplexity должен быть выбран чаще (примерно 70%)
        perplexity_count = selected.count("Perplexity")
        assert 60 <= perplexity_count <= 80  # Допуск ±10%
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self, manager, mock_perplexity):
        """Тест успешной генерации ответа"""
        manager.register_provider(mock_perplexity, weight=1.0)
        
        result = await manager.generate_response(
            query="test query",
            preferred_provider="perplexity"
        )
        
        assert result["success"] is True
        assert result["answer"] == "Perplexity answer"
        assert manager.stats["perplexity"]["total_requests"] == 1
        assert manager.stats["perplexity"]["successful"] == 1
    
    @pytest.mark.asyncio
    async def test_fallback_mechanism(self, manager, mock_perplexity, mock_deepseek):
        """Тест fallback механизма"""
        # Настраиваем Perplexity для возврата ошибки
        mock_perplexity.generate_response = AsyncMock(return_value={
            "success": False,
            "error": "API error"
        })
        
        manager.register_provider(mock_perplexity, weight=0.7)
        manager.register_provider(mock_deepseek, weight=0.3)
        
        result = await manager.generate_response(
            query="test query",
            preferred_provider="perplexity",
            fallback_enabled=True
        )
        
        # Должен успешно переключиться на DeepSeek
        assert result["success"] is True
        assert result["provider"] == "DeepSeek"
        assert manager.stats["perplexity"]["failed"] == 1
        assert manager.stats["deepseek"]["fallback_used"] == 1
    
    def test_update_weight(self, manager, mock_perplexity):
        """Тест обновления веса провайдера"""
        manager.register_provider(mock_perplexity, weight=0.5)
        
        manager.update_weight("perplexity", 0.9)
        assert manager.weights["perplexity"] == 0.9
        
        # Проверка ограничений (0.0-1.0)
        manager.update_weight("perplexity", 1.5)
        assert manager.weights["perplexity"] == 1.0
        
        manager.update_weight("perplexity", -0.5)
        assert manager.weights["perplexity"] == 0.0
    
    def test_get_stats(self, manager, mock_perplexity, mock_deepseek):
        """Тест получения статистики"""
        manager.register_provider(mock_perplexity, weight=0.7)
        manager.register_provider(mock_deepseek, weight=0.3)
        
        # Симулируем активность
        manager.stats["perplexity"]["total_requests"] = 10
        manager.stats["perplexity"]["successful"] = 7
        manager.stats["perplexity"]["failed"] = 3
        
        stats = manager.get_stats()
        
        assert "providers" in stats
        assert "perplexity" in stats["providers"]
        assert stats["providers"]["perplexity"]["success_rate"] == 70.0
        assert stats["total_requests"] == 10


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Тесты обработки ошибок"""
    
    @pytest.fixture
    def provider(self):
        return PerplexityProvider(api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, provider):
        """Тест обработки rate limit (429)"""
        with patch.object(provider, '_make_request') as mock_request:
            # Симулируем ошибку 429
            mock_request.side_effect = RateLimitError("Rate limit exceeded")
            
            # Провайдер должен вернуть error dict, а не raise исключение
            result = await provider.generate_response("test")
            assert result["success"] is False
            assert "Rate limit exceeded" in result["error"]
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, provider):
        """Тест обработки ошибки аутентификации (401)"""
        with patch.object(provider, '_make_request') as mock_request:
            mock_request.side_effect = AuthenticationError("Invalid API key")
            
            # Провайдер должен вернуть error dict, а не raise исключение
            result = await provider.generate_response("test")
            assert result["success"] is False
            assert "Invalid API key" in result["error"]
    
    @pytest.mark.asyncio
    async def test_timeout_error(self, provider):
        """Тест обработки таймаута"""
        with patch.object(provider, '_make_request') as mock_request:
            mock_request.side_effect = TimeoutError("Request timeout")
            
            # Провайдер должен вернуть error dict, а не raise исключение
            result = await provider.generate_response("test")
            assert result["success"] is False
            assert "Request timeout" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
