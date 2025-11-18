"""
🧪 Тесты для Pydantic моделей Agent System

Проверяет валидацию, сериализацию и бизнес-логику моделей.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.agents.models import (
    AgentType,
    AgentChannel,
    MessageType,
    AgentRequest,
    AgentResponse,
    AgentMessage,
    ConsensusRequest,
    ConsensusResponse,
    APIKey,
    AgentStats,
    HealthStatus,
)


# =============================================================================
# AGENT REQUEST TESTS
# =============================================================================

def test_agent_request_valid():
    """Тест валидного AgentRequest"""
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="analyze",
        prompt="Analyze this strategy",
        code="def strategy(): pass",
        context={"focus": "performance"}
    )
    
    assert request.agent_type == AgentType.DEEPSEEK
    assert request.task_type == "analyze"
    assert "strategy" in request.prompt
    assert request.code is not None


def test_agent_request_invalid_task_type():
    """Тест невалидного task_type"""
    with pytest.raises(ValidationError) as exc:
        AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="invalid_task",
            prompt="Test"
        )
    
    assert "task_type must be one of" in str(exc.value)


def test_agent_request_empty_prompt():
    """Тест пустого prompt"""
    with pytest.raises(ValidationError):
        AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="analyze",
            prompt=""
        )


def test_agent_request_to_mcp_format():
    """Тест конвертации в MCP формат"""
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="analyze",
        prompt="Test prompt",
        code="def test(): pass",
        context={"focus": "security"}
    )
    
    mcp_format = request.to_mcp_format()
    
    assert "strategy_code" in mcp_format
    assert mcp_format["strategy_code"] == "def test(): pass"
    assert mcp_format["focus"] == "security"


def test_agent_request_to_direct_api_format():
    """Тест конвертации в Direct API формат"""
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="explain",
        prompt="Explain this code",
        code="import sys"
    )
    
    api_format = request.to_direct_api_format(include_tools=False)
    
    assert api_format["model"] == "deepseek-chat"
    assert "messages" in api_format
    assert len(api_format["messages"]) == 2
    assert "tools" not in api_format  # include_tools=False


# =============================================================================
# AGENT RESPONSE TESTS
# =============================================================================

def test_agent_response_success():
    """Тест успешного AgentResponse"""
    response = AgentResponse(
        success=True,
        content="Analysis complete",
        channel=AgentChannel.DIRECT_API,
        latency_ms=1250.5,
        api_key_index=3
    )
    
    assert response.success is True
    assert response.error is None
    assert response.latency_ms == 1250.5
    assert isinstance(response.timestamp, datetime)


def test_agent_response_negative_latency():
    """Тест отрицательной latency (невалидно)"""
    with pytest.raises(ValidationError) as exc:
        AgentResponse(
            success=True,
            content="Test",
            channel=AgentChannel.DIRECT_API,
            latency_ms=-100
        )
    
    # Pydantic использует "greater than or equal to" в сообщении
    assert "greater than or equal to 0" in str(exc.value)


def test_agent_response_excessive_latency():
    """Тест слишком большой latency"""
    with pytest.raises(ValidationError) as exc:
        AgentResponse(
            success=True,
            content="Test",
            channel=AgentChannel.DIRECT_API,
            latency_ms=400000  # >5 минут
        )
    
    assert "too large" in str(exc.value)


# =============================================================================
# AGENT MESSAGE TESTS
# =============================================================================

def test_agent_message_valid():
    """Тест валидного AgentMessage"""
    msg = AgentMessage(
        message_id="msg-123",
        from_agent=AgentType.DEEPSEEK,
        to_agent=AgentType.COPILOT,
        message_type=MessageType.RESPONSE,
        content="Analysis result",
        context={"task": "review"},
        conversation_id="conv-456",
        iteration=2,
        confidence_score=0.95
    )
    
    assert msg.message_id == "msg-123"
    assert msg.iteration == 2
    assert msg.confidence_score == 0.95
    assert isinstance(msg.timestamp, datetime)


def test_agent_message_invalid_iteration():
    """Тест невалидной итерации (>100)"""
    with pytest.raises(ValidationError):
        AgentMessage(
            message_id="msg-123",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.COPILOT,
            message_type=MessageType.RESPONSE,
            content="Test",
            context={},
            conversation_id="conv-456",
            iteration=150  # >100
        )


def test_agent_message_invalid_confidence():
    """Тест невалидной confidence_score (>1.0)"""
    with pytest.raises(ValidationError):
        AgentMessage(
            message_id="msg-123",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.COPILOT,
            message_type=MessageType.RESPONSE,
            content="Test",
            context={},
            conversation_id="conv-456",
            confidence_score=1.5  # >1.0
        )


# =============================================================================
# CONSENSUS TESTS
# =============================================================================

def test_consensus_request_valid():
    """Тест валидного ConsensusRequest"""
    req = ConsensusRequest(
        question="What is the best crypto indicator?",
        agents=[AgentType.DEEPSEEK, AgentType.PERPLEXITY],
        context={"domain": "crypto"},
        require_full_consensus=True
    )
    
    assert len(req.agents) == 2
    assert req.require_full_consensus is True


def test_consensus_request_duplicate_agents():
    """Тест дублирующихся агентов (невалидно)"""
    with pytest.raises(ValidationError) as exc:
        ConsensusRequest(
            question="Test question",
            agents=[AgentType.DEEPSEEK, AgentType.DEEPSEEK],  # Duplicate
            context={}
        )
    
    assert "must be unique" in str(exc.value)


def test_consensus_request_too_few_agents():
    """Тест слишком малого количества агентов"""
    with pytest.raises(ValidationError):
        ConsensusRequest(
            question="Test question",
            agents=[AgentType.DEEPSEEK],  # Только 1 агент, нужно >=2
            context={}
        )


def test_consensus_response_valid():
    """Тест валидного ConsensusResponse"""
    resp = ConsensusResponse(
        question="Original question",
        consensus="Agreed answer",
        individual_responses={
            "deepseek": "DeepSeek response",
            "perplexity": "Perplexity response"
        },
        agreement_level=0.87,
        metadata={"method": "weighted_average"}
    )
    
    assert resp.agreement_level == 0.87
    assert len(resp.individual_responses) == 2
    assert isinstance(resp.timestamp, datetime)


# =============================================================================
# API KEY TESTS
# =============================================================================

def test_api_key_valid():
    """Тест валидного APIKey"""
    key = APIKey(
        value="sk-test123456789",
        agent_type=AgentType.DEEPSEEK,
        index=0,
        is_active=True,
        requests_count=10,
        error_count=1
    )
    
    assert key.is_active is True
    assert key.requests_count == 10
    assert key.error_count == 1


def test_api_key_invalid_format():
    """Тест невалидного формата API ключа"""
    with pytest.raises(ValidationError) as exc:
        APIKey(
            value="invalid-key-format",
            agent_type=AgentType.DEEPSEEK,
            index=0
        )
    
    assert "must start with 'sk-' or 'pplx-'" in str(exc.value)


def test_api_key_perplexity():
    """Тест Perplexity API ключа"""
    key = APIKey(
        value="pplx-abc123",
        agent_type=AgentType.PERPLEXITY,
        index=2
    )
    
    assert key.agent_type == AgentType.PERPLEXITY
    assert key.value.startswith("pplx-")


# =============================================================================
# AGENT STATS TESTS
# =============================================================================

def test_agent_stats_success_rate():
    """Тест расчета success_rate"""
    stats = AgentStats(
        total_requests=100,
        successful_requests=85,
        failed_requests=15
    )
    
    assert stats.success_rate == 0.85


def test_agent_stats_success_rate_zero_requests():
    """Тест success_rate при нулевом количестве запросов"""
    stats = AgentStats(
        total_requests=0,
        successful_requests=0
    )
    
    assert stats.success_rate == 0.0


def test_agent_stats_mcp_preference():
    """Тест расчета MCP preference"""
    stats = AgentStats(
        mcp_success=70,
        mcp_failed=10,
        direct_api_success=15,
        direct_api_failed=5
    )
    
    # (70+10) / (70+10+15+5) = 80/100 = 0.8
    assert stats.mcp_preference == 0.8


# =============================================================================
# HEALTH STATUS TESTS
# =============================================================================

def test_health_status_healthy():
    """Тест здорового статуса"""
    health = HealthStatus(
        is_healthy=True,
        mcp_available=True,
        api_keys_available=8,
        errors=[]
    )
    
    assert health.is_healthy is True
    assert len(health.errors) == 0


def test_health_status_unhealthy():
    """Тест нездорового статуса"""
    health = HealthStatus(
        is_healthy=False,
        mcp_available=False,
        api_keys_available=0,
        errors=["MCP server unreachable", "All API keys exhausted"]
    )
    
    assert health.is_healthy is False
    assert len(health.errors) == 2


# =============================================================================
# JSON SERIALIZATION TESTS
# =============================================================================

def test_agent_request_json_serialization():
    """Тест JSON сериализации AgentRequest"""
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="analyze",
        prompt="Test"
    )
    
    json_str = request.model_dump_json()
    assert "deepseek" in json_str
    assert "analyze" in json_str


def test_agent_response_json_deserialization():
    """Тест JSON десериализации AgentResponse"""
    json_data = {
        "success": True,
        "content": "Result",
        "channel": "direct_api",
        "latency_ms": 1000
    }
    
    response = AgentResponse.model_validate(json_data)
    assert response.success is True
    assert response.channel == AgentChannel.DIRECT_API


# =============================================================================
# ENUM VALIDATION TESTS
# =============================================================================

def test_enum_string_values():
    """Тест что Enums используют string values"""
    assert AgentType.DEEPSEEK.value == "deepseek"
    assert AgentChannel.MCP_SERVER.value == "mcp_server"
    assert MessageType.CONSENSUS_REQUEST.value == "consensus_request"


def test_invalid_enum_value():
    """Тест невалидного enum значения"""
    with pytest.raises(ValidationError):
        AgentRequest(
            agent_type="invalid_agent",  # Не AgentType
            task_type="analyze",
            prompt="Test"
        )
