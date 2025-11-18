"""
Unit tests для Pydantic моделей агентов

Test coverage:
- AgentConfig валидация
- DeepSeekConfig валидация
- PerplexityConfig валидация
- API models валидация
"""

import pytest
from pydantic import ValidationError

from backend.agents.api_models import (
    AgentSendRequest,
    ConsensusRequest,
    MessageType,
)
from backend.agents.base_config import (
    AgentCapability,
    AgentConfig,
    AgentType,
    DeepSeekConfig,
    MultiKeyConfig,
    PerplexityConfig,
)


class TestAgentConfig:
    """Тесты для AgentConfig"""
    
    def test_valid_config(self):
        """Валидная конфигурация"""
        config = AgentConfig(
            agent_type=AgentType.DEEPSEEK,
            api_key="valid-key-1234567890",
            model="deepseek-chat",
            timeout=120,
            max_retries=3
        )
        
        assert config.agent_type == AgentType.DEEPSEEK
        assert config.timeout == 120
        assert config.max_retries == 3
    
    def test_invalid_api_key_too_short(self):
        """API ключ слишком короткий"""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(
                agent_type=AgentType.DEEPSEEK,
                api_key="short",  # < 10 символов
                model="deepseek-chat"
            )
        
        assert "at least 10 characters" in str(exc_info.value).lower()
    
    def test_invalid_api_key_placeholder(self):
        """Placeholder API ключ"""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(
                agent_type=AgentType.DEEPSEEK,
                api_key="your-api-key-here",
                model="deepseek-chat"
            )
        
        assert "invalid api key placeholder" in str(exc_info.value).lower()
    
    def test_invalid_timeout_too_short(self):
        """Timeout слишком короткий"""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(
                agent_type=AgentType.DEEPSEEK,
                api_key="valid-key-1234567890",
                model="deepseek-chat",
                timeout=5  # < 10
            )
        
        assert "timeout" in str(exc_info.value).lower()
    
    def test_invalid_timeout_too_long(self):
        """Timeout слишком длинный"""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(
                agent_type=AgentType.DEEPSEEK,
                api_key="valid-key-1234567890",
                model="deepseek-chat",
                timeout=700  # > 600
            )
        
        assert "timeout" in str(exc_info.value).lower()
    
    def test_default_values(self):
        """Значения по умолчанию"""
        config = AgentConfig(
            agent_type=AgentType.DEEPSEEK,
            api_key="valid-key-1234567890",
            model="deepseek-chat"
        )
        
        assert config.timeout == 120
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.temperature == 0.7
        assert config.capabilities == []
        assert config.metadata == {}
    
    def test_extra_fields_forbidden(self):
        """Дополнительные поля запрещены"""
        with pytest.raises(ValidationError):
            AgentConfig(
                agent_type=AgentType.DEEPSEEK,
                api_key="valid-key-1234567890",
                model="deepseek-chat",
                unknown_field="value"  # Extra field
            )


class TestDeepSeekConfig:
    """Тесты для DeepSeekConfig"""
    
    def test_valid_deepseek_config(self):
        """Валидная DeepSeek конфигурация"""
        config = DeepSeekConfig(
            api_key="sk-deepseek-1234567890",
            model="deepseek-chat",
            max_tokens=4000
        )
        
        assert config.agent_type == AgentType.DEEPSEEK
        assert config.model == "deepseek-chat"
        assert config.max_tokens == 4000
        assert config.enable_auto_fix is True
        assert AgentCapability.CODE_GENERATION in config.capabilities
    
    def test_invalid_model_pattern(self):
        """Модель не соответствует паттерну"""
        with pytest.raises(ValidationError) as exc_info:
            DeepSeekConfig(
                api_key="sk-deepseek-1234567890",
                model="gpt-4"  # Не начинается с 'deepseek-'
            )
        
        assert "pattern" in str(exc_info.value).lower() or "match" in str(exc_info.value).lower()
    
    def test_frozen_agent_type(self):
        """agent_type нельзя изменить после создания"""
        config = DeepSeekConfig(
            api_key="sk-deepseek-1234567890",
            model="deepseek-chat"
        )
        
        with pytest.raises(ValidationError):
            config.agent_type = AgentType.PERPLEXITY
    
    def test_auto_fix_iterations(self):
        """Валидация max_fix_iterations"""
        config = DeepSeekConfig(
            api_key="sk-deepseek-1234567890",
            model="deepseek-chat",
            max_fix_iterations=5
        )
        
        assert config.max_fix_iterations == 5
    
    def test_max_tokens_bounds(self):
        """Boundaries для max_tokens"""
        # Минимум
        with pytest.raises(ValidationError):
            DeepSeekConfig(
                api_key="sk-deepseek-1234567890",
                model="deepseek-chat",
                max_tokens=50  # < 100
            )
        
        # Максимум
        with pytest.raises(ValidationError):
            DeepSeekConfig(
                api_key="sk-deepseek-1234567890",
                model="deepseek-chat",
                max_tokens=15000  # > 10000
            )


class TestPerplexityConfig:
    """Тесты для PerplexityConfig"""
    
    def test_valid_perplexity_config(self):
        """Валидная Perplexity конфигурация"""
        config = PerplexityConfig(
            api_key="pplx-1234567890",
            model="sonar",
            enable_search=True
        )
        
        assert config.agent_type == AgentType.PERPLEXITY
        assert config.model == "sonar"
        assert config.enable_search is True
        assert AgentCapability.RESEARCH in config.capabilities
    
    def test_sonar_pro_model(self):
        """Sonar Pro модель"""
        config = PerplexityConfig(
            api_key="pplx-1234567890",
            model="sonar-pro"
        )
        
        assert config.model == "sonar-pro"
    
    def test_invalid_model_pattern(self):
        """Модель не соответствует паттерну"""
        with pytest.raises(ValidationError):
            PerplexityConfig(
                api_key="pplx-1234567890",
                model="gpt-4"  # Не 'sonar' или 'sonar-pro'
            )
    
    def test_search_domain_filter(self):
        """Фильтр доменов"""
        config = PerplexityConfig(
            api_key="pplx-1234567890",
            model="sonar",
            search_domain_filter=["arxiv.org", "github.com"]
        )
        
        assert "arxiv.org" in config.search_domain_filter
        assert "github.com" in config.search_domain_filter


class TestMultiKeyConfig:
    """Тесты для MultiKeyConfig"""
    
    def test_valid_multi_key_config(self):
        """Валидная multi-key конфигурация"""
        base_config = DeepSeekConfig(
            api_key="primary-key-1234567890",
            model="deepseek-chat"
        )
        
        multi_config = MultiKeyConfig(
            base_config=base_config,
            backup_keys=["backup-key-1234567890", "backup-key-0987654321"],
            rotation_strategy="round-robin"
        )
        
        assert len(multi_config.backup_keys) == 2
        assert multi_config.rotation_strategy == "round-robin"
    
    def test_invalid_backup_key_too_short(self):
        """Backup ключ слишком короткий"""
        base_config = DeepSeekConfig(
            api_key="primary-key-1234567890",
            model="deepseek-chat"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            MultiKeyConfig(
                base_config=base_config,
                backup_keys=["short"]  # < 10 символов
            )
        
        assert "backup key too short" in str(exc_info.value).lower()
    
    def test_rotation_strategies(self):
        """Различные стратегии ротации"""
        base_config = DeepSeekConfig(
            api_key="primary-key-1234567890",
            model="deepseek-chat"
        )
        
        for strategy in ["round-robin", "random", "least-used"]:
            config = MultiKeyConfig(
                base_config=base_config,
                backup_keys=["backup-key-1234567890"],
                rotation_strategy=strategy
            )
            assert config.rotation_strategy == strategy
    
    def test_invalid_rotation_strategy(self):
        """Невалидная стратегия ротации"""
        base_config = DeepSeekConfig(
            api_key="primary-key-1234567890",
            model="deepseek-chat"
        )
        
        with pytest.raises(ValidationError):
            MultiKeyConfig(
                base_config=base_config,
                backup_keys=["backup-key-1234567890"],
                rotation_strategy="invalid-strategy"
            )


class TestAPIModels:
    """Тесты для API models"""
    
    def test_agent_send_request_valid(self):
        """Валидный AgentSendRequest"""
        request = AgentSendRequest(
            from_agent="copilot",
            to_agent="deepseek",
            content="Generate trading strategy",
            message_type=MessageType.QUERY
        )
        
        assert request.from_agent == "copilot"
        assert request.to_agent == "deepseek"
        assert request.content == "Generate trading strategy"
    
    def test_agent_send_request_empty_content(self):
        """Пустое содержимое"""
        with pytest.raises(ValidationError) as exc_info:
            AgentSendRequest(
                from_agent="copilot",
                to_agent="deepseek",
                content="   ",  # Только пробелы
                message_type=MessageType.QUERY
            )
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_agent_send_request_content_too_long(self):
        """Содержимое слишком длинное"""
        with pytest.raises(ValidationError):
            AgentSendRequest(
                from_agent="copilot",
                to_agent="deepseek",
                content="x" * 60000,  # > 50000
                message_type=MessageType.QUERY
            )
    
    def test_consensus_request_valid(self):
        """Валидный ConsensusRequest"""
        request = ConsensusRequest(
            question="What is the best trading strategy?",
            agents=["deepseek", "perplexity"]
        )
        
        assert len(request.agents) == 2
        assert "deepseek" in request.agents
    
    def test_consensus_request_duplicate_agents(self):
        """Дублирующиеся агенты"""
        with pytest.raises(ValidationError) as exc_info:
            ConsensusRequest(
                question="What is the best trading strategy?",
                agents=["deepseek", "deepseek"]  # Дубликат
            )
        
        assert "duplicate" in str(exc_info.value).lower()
    
    def test_consensus_request_unknown_agent(self):
        """Неизвестный агент"""
        with pytest.raises(ValidationError) as exc_info:
            ConsensusRequest(
                question="What is the best trading strategy?",
                agents=["deepseek", "unknown-agent"]
            )
        
        assert "unknown agent" in str(exc_info.value).lower()
    
    def test_consensus_request_too_few_agents(self):
        """Слишком мало агентов"""
        with pytest.raises(ValidationError) as exc_info:
            ConsensusRequest(
                question="What is the best trading strategy?",
                agents=["deepseek"]  # < 2
            )
        
        assert "at least 2 agents" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
