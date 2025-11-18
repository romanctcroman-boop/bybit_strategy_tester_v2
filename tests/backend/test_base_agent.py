"""
Unit tests для BaseAgent

Test coverage:
- execute() метод с retry logic
- Stats tracking (success_rate, avg_response_time)
- Error handling и custom exceptions
- Capability checks
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

import pytest

from backend.agents.base_agent import (
    AgentAPIError,
    AgentError,
    AgentTimeoutError,
    AgentValidationError,
    BaseAgent,
)
from backend.agents.base_config import (
    AgentCapability,
    AgentConfig,
    AgentType,
    DeepSeekConfig,
)


class MockSuccessAgent(BaseAgent):
    """Mock агент который всегда успешно отвечает"""
    
    async def send_request(self, prompt: str, context: Optional[dict] = None) -> str:
        await asyncio.sleep(0.01)  # Имитация API call
        return f"Response to: {prompt[:50]}"
    
    def validate_response(self, response: str) -> bool:
        return len(response) > 0


class MockFailingAgent(BaseAgent):
    """Mock агент который всегда падает"""
    
    def __init__(self, config: AgentConfig, error_type: type = Exception):
        super().__init__(config)
        self.error_type = error_type
        self.call_count = 0
    
    async def send_request(self, prompt: str, context: Optional[dict] = None) -> str:
        self.call_count += 1
        raise self.error_type("Mock error")
    
    def validate_response(self, response: str) -> bool:
        return True


class MockValidationFailAgent(BaseAgent):
    """Mock агент где валидация всегда падает"""
    
    async def send_request(self, prompt: str, context: Optional[dict] = None) -> str:
        return "invalid response"
    
    def validate_response(self, response: str) -> bool:
        return False


class MockEventualSuccessAgent(BaseAgent):
    """Mock агент который падает N раз, потом успех"""
    
    def __init__(self, config: AgentConfig, fail_times: int = 2):
        super().__init__(config)
        self.fail_times = fail_times
        self.call_count = 0
    
    async def send_request(self, prompt: str, context: Optional[dict] = None) -> str:
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise Exception(f"Attempt {self.call_count} failed")
        return "success"
    
    def validate_response(self, response: str) -> bool:
        return response == "success"


class TestBaseAgent:
    """Тесты для BaseAgent"""
    
    @pytest.fixture
    def base_config(self):
        """Базовая конфигурация"""
        return AgentConfig(
            agent_type=AgentType.DEEPSEEK,
            api_key="test-key-1234567890",
            model="test-model",
            timeout=120,
            max_retries=3,
            retry_delay=0.1  # Быстрый retry для тестов
        )
    
    @pytest.mark.asyncio
    async def test_successful_execution(self, base_config):
        """Успешное выполнение запроса"""
        agent = MockSuccessAgent(base_config)
        
        result = await agent.execute("test prompt")
        
        assert result["success"] is True
        assert "Response to: test prompt" in result["response"]
        assert result["attempts"] == 1
        assert result["agent_type"] == AgentType.DEEPSEEK.value
        assert result["response_time"] > 0
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, base_config):
        """Retry при ошибках"""
        base_config.max_retries = 3
        agent = MockFailingAgent(base_config)
        
        result = await agent.execute("test prompt")
        
        assert result["success"] is False
        assert "error" in result
        assert result["attempts"] == 3  # Все попытки использованы
        assert agent.call_count == 3
    
    @pytest.mark.asyncio
    async def test_eventual_success_after_retries(self, base_config):
        """Успех после нескольких попыток"""
        base_config.max_retries = 3
        agent = MockEventualSuccessAgent(base_config, fail_times=2)
        
        result = await agent.execute("test prompt")
        
        assert result["success"] is True
        assert result["response"] == "success"
        assert result["attempts"] == 3  # 2 неудачи + 1 успех
        assert agent.call_count == 3
    
    @pytest.mark.asyncio
    async def test_no_retry_when_disabled(self, base_config):
        """Без retry когда отключено"""
        base_config.max_retries = 3
        agent = MockFailingAgent(base_config)
        
        result = await agent.execute("test prompt", retry_on_failure=False)
        
        assert result["success"] is False
        assert result["attempts"] == 1  # Только одна попытка
        assert agent.call_count == 1
    
    @pytest.mark.asyncio
    async def test_validation_failure(self, base_config):
        """Ошибка валидации ответа"""
        agent = MockValidationFailAgent(base_config)
        
        result = await agent.execute("test prompt")
        
        assert result["success"] is False
        assert "validation" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_stats_tracking_success(self, base_config):
        """Отслеживание статистики успехов"""
        agent = MockSuccessAgent(base_config)
        
        # 5 успешных запросов
        for i in range(5):
            await agent.execute(f"prompt {i}")
        
        stats = agent.get_stats()
        
        assert stats["total_requests"] == 5
        assert stats["successful_requests"] == 5
        assert stats["failed_requests"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["average_response_time"] > 0
    
    @pytest.mark.asyncio
    async def test_stats_tracking_mixed(self, base_config):
        """Отслеживание статистики смешанных результатов"""
        success_agent = MockSuccessAgent(base_config)
        fail_agent = MockFailingAgent(base_config)
        
        # 3 успеха
        for i in range(3):
            await success_agent.execute(f"prompt {i}")
        
        # 2 неудачи
        for i in range(2):
            await fail_agent.execute(f"prompt {i}")
        
        success_stats = success_agent.get_stats()
        fail_stats = fail_agent.get_stats()
        
        assert success_stats["success_rate"] == 1.0
        assert fail_stats["success_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_reset_stats(self, base_config):
        """Сброс статистики"""
        agent = MockSuccessAgent(base_config)
        
        # Несколько запросов
        await agent.execute("prompt 1")
        await agent.execute("prompt 2")
        
        assert agent.get_stats()["total_requests"] == 2
        
        # Сброс
        agent.reset_stats()
        
        stats = agent.get_stats()
        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 0
    
    def test_has_capability(self, base_config):
        """Проверка capabilities"""
        base_config.capabilities = [
            AgentCapability.CODE_GENERATION,
            AgentCapability.ANALYSIS
        ]
        agent = MockSuccessAgent(base_config)
        
        assert agent.has_capability(AgentCapability.CODE_GENERATION)
        assert agent.has_capability(AgentCapability.ANALYSIS)
        assert not agent.has_capability(AgentCapability.RESEARCH)
    
    def test_agent_properties(self, base_config):
        """Свойства агента"""
        base_config.capabilities = [AgentCapability.CODE_GENERATION]
        agent = MockSuccessAgent(base_config)
        
        assert agent.agent_type == AgentType.DEEPSEEK
        assert agent.capabilities == [AgentCapability.CODE_GENERATION]
        assert agent.success_rate == 0.0  # Нет запросов
        assert agent.average_response_time == 0.0
    
    @pytest.mark.asyncio
    async def test_custom_exceptions(self, base_config):
        """Custom exceptions"""
        # AgentAPIError
        agent = MockFailingAgent(base_config, error_type=AgentAPIError)
        result = await agent.execute("test")
        assert "AgentAPIError" in result["error"]
        
        # AgentTimeoutError
        agent = MockFailingAgent(base_config, error_type=AgentTimeoutError)
        result = await agent.execute("test")
        assert "AgentTimeoutError" in result["error"]
        
        # AgentValidationError
        agent = MockFailingAgent(base_config, error_type=AgentValidationError)
        result = await agent.execute("test")
        assert "AgentValidationError" in result["error"]


class TestAgentExceptions:
    """Тесты для custom exceptions"""
    
    def test_agent_error_creation(self):
        """Создание AgentError"""
        error = AgentError(
            agent_type=AgentType.DEEPSEEK,
            message="Test error",
            details={"key": "value"}
        )
        
        assert error.agent_type == AgentType.DEEPSEEK
        assert error.message == "Test error"
        assert error.details == {"key": "value"}
        assert "DEEPSEEK" in str(error)
    
    def test_agent_timeout_error(self):
        """AgentTimeoutError"""
        error = AgentTimeoutError(
            agent_type=AgentType.PERPLEXITY,
            message="Timeout after 120s"
        )
        
        assert "Timeout" in str(error)
        assert "PERPLEXITY" in str(error)
    
    def test_agent_validation_error(self):
        """AgentValidationError"""
        error = AgentValidationError(
            agent_type=AgentType.DEEPSEEK,
            message="Response validation failed",
            details={"reason": "empty response"}
        )
        
        assert "validation" in str(error).lower()
        assert error.details["reason"] == "empty response"
    
    def test_agent_api_error(self):
        """AgentAPIError"""
        error = AgentAPIError(
            agent_type=AgentType.DEEPSEEK,
            message="API returned 500",
            details={"status_code": 500}
        )
        
        assert "API" in str(error)
        assert error.details["status_code"] == 500


class TestDeepSeekConfigIntegration:
    """Интеграционные тесты с DeepSeekConfig"""
    
    @pytest.mark.asyncio
    async def test_deepseek_config_with_agent(self):
        """DeepSeekConfig с BaseAgent"""
        config = DeepSeekConfig(
            api_key="sk-deepseek-1234567890",
            model="deepseek-chat",
            max_tokens=4000,
            enable_auto_fix=True,
            max_fix_iterations=3
        )
        
        agent = MockSuccessAgent(config)
        
        assert agent.agent_type == AgentType.DEEPSEEK
        assert agent.has_capability(AgentCapability.CODE_GENERATION)
        assert agent.has_capability(AgentCapability.ANALYSIS)
        
        result = await agent.execute("test prompt")
        assert result["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
