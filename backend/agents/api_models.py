"""
Pydantic модели для Agent-to-Agent API

Based on agent self-improvement recommendations:
- Стандартизация API через Pydantic schemas
- Валидация request/response на уровне API
- Type safety для всех endpoints
"""

from datetime import datetime
from backend.utils.time import utc_now
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class MessageType(str, Enum):
    """Типы сообщений"""
    QUERY = "query"
    RESPONSE = "response"
    ERROR = "error"
    SYSTEM = "system"


class AgentSendRequest(BaseModel):
    """
    Request для отправки сообщения агенту
    
    POST /api/v1/agent/send
    
    Example:
        {
            "from_agent": "copilot",
            "to_agent": "deepseek",
            "content": "Generate trading strategy",
            "message_type": "query",
            "context": {"symbol": "BTCUSDT"}
        }
    """
    
    from_agent: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Отправитель (copilot, deepseek, perplexity)"
    )
    
    to_agent: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Получатель (deepseek, perplexity)"
    )
    
    content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Содержимое сообщения (1-50000 символов)"
    )
    
    message_type: MessageType = Field(
        default=MessageType.QUERY,
        description="Тип сообщения"
    )
    
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительный контекст"
    )
    
    conversation_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="ID разговора (опционально)"
    )
    
    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Валидация содержимого"""
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")
        return v.strip()

    @field_validator("from_agent")
    @classmethod
    def validate_from_agent(cls, v: str) -> str:
        """Проверка, что from_agent не пустой/пробельный и без обрезки мусора"""
        if not isinstance(v, str):
            raise ValueError("from_agent must be a string")
        v2 = v.strip()
        if not v2:
            raise ValueError("from_agent cannot be empty or whitespace only")
        return v2

    @field_validator("to_agent")
    @classmethod
    def validate_to_agent(cls, v: str) -> str:
        """Проверка, что to_agent не пустой/пробельный и без обрезки мусора"""
        if not isinstance(v, str):
            raise ValueError("to_agent must be a string")
        v2 = v.strip()
        if not v2:
            raise ValueError("to_agent cannot be empty or whitespace only")
        return v2
    
    class Config:
        """Pydantic конфигурация"""
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "from_agent": "copilot",
                "to_agent": "deepseek",
                "content": "Generate a bollinger bands trading strategy for BTCUSDT",
                "message_type": "query",
                "context": {"symbol": "BTCUSDT", "timeframe": "1h"},
                "conversation_id": "conv-123"
            }
        }


class AgentSendResponse(BaseModel):
    """
    Response от агента
    
    Example:
        {
            "success": true,
            "message_id": "msg-abc123",
            "agent": "deepseek",
            "response": "Here is your strategy...",
            "response_time": 2.5,
            "timestamp": "2025-11-17T23:30:00"
        }
    """
    
    success: bool = Field(
        ...,
        description="Успешность запроса"
    )
    
    message_id: str = Field(
        ...,
        description="ID сообщения"
    )
    
    agent: str = Field(
        ...,
        description="Имя агента"
    )
    
    response: Optional[str] = Field(
        default=None,
        description="Ответ агента (если success=True)"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Ошибка (если success=False)"
    )
    
    response_time: float = Field(
        ...,
        ge=0.0,
        description="Время отклика в секундах"
    )
    
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="Временная метка"
    )
    
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительный контекст"
    )


class ConsensusRequest(BaseModel):
    """
    Request для получения консенсуса от нескольких агентов
    
    POST /api/v1/agent/consensus
    
    Example:
        {
            "question": "What is the best RSI period?",
            "agents": ["deepseek", "perplexity"],
            "context": {"symbol": "BTCUSDT"}
        }
    """
    
    question: str = Field(
        ...,
        min_length=5,
        max_length=10000,
        description="Вопрос для консенсуса"
    )
    
    agents: list[str] = Field(
        default=["deepseek", "perplexity"],
        # min_length handled by custom validator to provide clearer error message
        max_length=5,
        description="Список агентов (2-5 агентов)"
    )
    
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительный контекст"
    )
    
    require_consensus: bool = Field(
        default=True,
        description="Требовать консенсус или вернуть индивидуальные ответы"
    )
    
    @field_validator("agents")
    @classmethod
    def validate_agents(cls, v: list[str]) -> list[str]:
        """Валидация списка агентов"""
        if len(v) < 2:
            raise ValueError("At least 2 agents required for consensus")
        
        if len(set(v)) != len(v):
            raise ValueError("Duplicate agents not allowed")
        
        allowed_agents = {"deepseek", "perplexity", "copilot"}
        for agent in v:
            if agent not in allowed_agents:
                raise ValueError(f"Unknown agent: {agent}")
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the pros and cons of mean reversion strategies?",
                "agents": ["deepseek", "perplexity"],
                "context": {"market": "crypto"},
                "require_consensus": True
            }
        }


class ConsensusResponse(BaseModel):
    """
    Response с консенсусом
    
    Example:
        {
            "consensus": "Mean reversion works best in ranging markets...",
            "confidence": 0.85,
            "individual_responses": {
                "deepseek": "Mean reversion...",
                "perplexity": "These strategies..."
            },
            "agreement_level": 0.75
        }
    """
    
    consensus: Optional[str] = Field(
        default=None,
        description="Консенсус (если достигнут)"
    )
    
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Уровень уверенности (0.0-1.0)"
    )
    
    individual_responses: dict[str, str] = Field(
        ...,
        description="Индивидуальные ответы агентов"
    )
    
    agreement_level: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Уровень согласия (0.0-1.0)"
    )
    
    synthesis_failed: bool = Field(
        default=False,
        description="Не удалось синтезировать консенсус"
    )
    
    response_time: float = Field(
        ...,
        ge=0.0,
        description="Общее время обработки"
    )
    
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="Временная метка"
    )


class ConversationStartRequest(BaseModel):
    """
    Request для запуска multi-turn разговора между агентами
    
    POST /api/v1/agent/conversation
    
    Example:
        {
            "initial_message": "Let's discuss scalping strategies",
            "participants": ["deepseek", "perplexity"],
            "max_turns": 5
        }
    """
    
    initial_message: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Начальное сообщение"
    )
    
    participants: list[str] = Field(
        ...,
        # min_length handled by custom validator to provide clearer error message
        max_length=5,
        description="Участники разговора"
    )
    
    max_turns: int = Field(
        default=5,
        ge=2,
        le=20,
        description="Максимум раундов разговора"
    )
    
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Контекст разговора"
    )
    
    @field_validator("participants")
    @classmethod
    def validate_participants(cls, v: list[str]) -> list[str]:
        """Валидация участников"""
        # Нормализуем имена: обрезаем пробелы
        normalized: list[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("Participant names must be strings")
            s = item.strip()
            if not s:
                raise ValueError("Participant names cannot be empty or whitespace only")
            normalized.append(s)

        if len(normalized) < 2:
            raise ValueError("At least 2 participants required")
        
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate participants not allowed")
        
        return normalized


class ConversationResponse(BaseModel):
    """
    Response с результатами разговора
    
    Example:
        {
            "conversation_id": "conv-123",
            "messages": [...],
            "summary": "Agents discussed...",
            "total_turns": 5
        }
    """
    
    conversation_id: str = Field(
        ...,
        description="ID разговора"
    )
    
    messages: list[dict[str, Any]] = Field(
        ...,
        description="Список сообщений"
    )
    
    summary: Optional[str] = Field(
        default=None,
        description="Краткое резюме разговора"
    )
    
    total_turns: int = Field(
        ...,
        ge=0,
        description="Общее количество раундов"
    )
    
    completed: bool = Field(
        ...,
        description="Разговор завершён"
    )
    
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="Временная метка"
    )


class AgentHealthResponse(BaseModel):
    """
    Response для health check
    
    GET /api/v1/agent/health
    
    Example:
        {
            "healthy": true,
            "agents": {
                "deepseek": "healthy",
                "perplexity": "healthy"
            },
            "communicator_initialized": true
        }
    """
    
    healthy: bool = Field(
        ...,
        description="Общее состояние системы"
    )
    
    agents: dict[str, str] = Field(
        ...,
        description="Состояние каждого агента"
    )
    
    communicator_initialized: bool = Field(
        ...,
        description="Agent communicator инициализирован"
    )
    
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="Временная метка"
    )


class AgentMetricsResponse(BaseModel):
    """
    Response с метриками агента
    
    GET /api/v1/agent/metrics/{agent_name}
    
    Example:
        {
            "agent_name": "deepseek",
            "total_requests": 150,
            "success_rate": 0.95,
            "avg_response_time": 2.3
        }
    """
    
    agent_name: str = Field(
        ...,
        description="Имя агента"
    )
    
    total_requests: int = Field(
        ...,
        ge=0,
        description="Всего запросов"
    )
    
    successful_requests: int = Field(
        ...,
        ge=0,
        description="Успешных запросов"
    )
    
    failed_requests: int = Field(
        ...,
        ge=0,
        description="Неудачных запросов"
    )
    
    success_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Процент успешных запросов"
    )
    
    avg_response_time: float = Field(
        ...,
        ge=0.0,
        description="Среднее время отклика (секунды)"
    )
    
    error_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown ошибок по типам"
    )
    
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="Временная метка"
    )


__all__ = [
    "MessageType",
    "AgentSendRequest",
    "AgentSendResponse",
    "ConsensusRequest",
    "ConsensusResponse",
    "ConversationStartRequest",
    "ConversationResponse",
    "AgentHealthResponse",
    "AgentMetricsResponse",
]
