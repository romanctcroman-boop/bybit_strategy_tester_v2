"""
🎯 Pydantic Models для Agent System

Стандартизированные модели для валидации и сериализации данных
в системе межагентной коммуникации.

Benefits:
- Автоматическая валидация данных
- Type hints и автокомплиты в IDE
- JSON Schema generation
- FastAPI integration
- Серализация/десериализация из коробки
"""

from datetime import datetime
from backend.utils.time import utc_now
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# ENUMS
# =============================================================================

class AgentType(str, Enum):
    """Типы AI агентов в системе"""
    DEEPSEEK = "deepseek"
    PERPLEXITY = "perplexity"
    COPILOT = "copilot"
    ORCHESTRATOR = "orchestrator"


class AgentChannel(str, Enum):
    """Каналы связи с агентами"""
    MCP_SERVER = "mcp_server"
    DIRECT_API = "direct_api"
    BACKUP_API = "backup_api"


class MessageType(str, Enum):
    """Типы сообщений между агентами"""
    QUERY = "query"
    RESPONSE = "response"
    VALIDATION = "validation"
    CONSENSUS_REQUEST = "consensus_request"
    ERROR = "error"
    COMPLETION = "completion"


class CommunicationPattern(str, Enum):
    """Паттерны коммуникации между агентами"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ITERATIVE = "iterative"
    COLLABORATIVE = "collaborative"
    HIERARCHICAL = "hierarchical"


# =============================================================================
# REQUEST MODELS
# =============================================================================

class AgentRequest(BaseModel):
    """
    Унифицированный запрос к агенту
    
    Examples:
        >>> request = AgentRequest(
        ...     agent_type=AgentType.DEEPSEEK,
        ...     task_type="analyze",
        ...     prompt="Analyze this trading strategy",
        ...     code="def my_strategy(): pass"
        ... )
    """
    model_config = ConfigDict(use_enum_values=False)
    
    agent_type: AgentType = Field(
        ...,
        description="Тип целевого агента"
    )
    task_type: str = Field(
        ...,
        description="Тип задачи: analyze, fix, explain, generate, etc.",
        min_length=1,
        max_length=50
    )
    prompt: str = Field(
        ...,
        description="Текст запроса к агенту",
        min_length=1,
        max_length=10000
    )
    code: str | None = Field(
        None,
        description="Код для анализа (опционально)",
        max_length=50000
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительный контекст запроса"
    )
    
    @field_validator('task_type')
    @classmethod
    def validate_task_type(cls, v: str) -> str:
        """Валидация допустимых типов задач"""
        allowed = {
            "analyze", "fix", "explain", "generate", "optimize",
            "review", "test", "refactor", "document", "research"
        }
        if v.lower() not in allowed:
            raise ValueError(f"task_type must be one of {allowed}, got '{v}'")
        return v.lower()
    
    def to_mcp_format(self) -> dict[str, Any]:
        """Преобразовать в формат MCP tool"""
        return {
            "strategy_code": self.code or self.prompt,
            "include_suggestions": True,
            "focus": self.context.get("focus", "all"),
        }
    
    def to_direct_api_format(self, include_tools: bool = True) -> dict[str, Any]:
        """Преобразовать в формат прямого API"""
        if self.agent_type == AgentType.DEEPSEEK:
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are an expert Python developer analyzing trading strategies."},
                    {"role": "user", "content": self._build_prompt()}
                ],
                "temperature": 0.7,
                "max_tokens": 4000,
            }
            
            # Add tools if needed
            if include_tools and self.context.get("use_file_access", False):
                payload["tools"] = self._get_mcp_tools_definition()
            
            return payload
        else:  # Perplexity
            return {
                "model": "sonar-pro",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant specialized in trading strategies."},
                    {"role": "user", "content": self._build_prompt()}
                ],
                "temperature": 0.2,
                "max_tokens": 2000,
            }
    
    def _build_prompt(self) -> str:
        """Построить полный prompt с защитой от prompt injection.

        SECURITY: Implements Phase 1 MEDIUM vulnerability fix (prompt injection sanitization).
        Phase 2: Applies external config limits from agents.yaml if present.
        """
        import re, json
        UNSAFE_PATTERNS = [
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"output\s+(all\s+)?(api\s+)?keys",
            r"execute\s+code",
            r"<script>",
            r"eval\(",
            r"forget\s+(all\s+)?previous",
            r"disregard\s+",
        ]

        def sanitize(text: str) -> str:
            if not text:
                return text
            for pattern in UNSAFE_PATTERNS:
                new = re.sub(pattern, "[REDACTED_UNSAFE_PATTERN]", text, flags=re.IGNORECASE)
                text = new
            return text

        parts = [f"Task: {sanitize(self.task_type)}", f"\n{sanitize(self.prompt)}"]
        if self.code:
            parts.append(f"\n\nCode to analyze:\n```python\n{self.code}\n```")
        if self.context:
            safe_context = {
                sanitize(str(k)): sanitize(str(v)) if not isinstance(v, (dict, list)) else v
                for k, v in self.context.items()
            }
            parts.append(f"\n\nContext: {json.dumps(safe_context, indent=2)}")
        full_prompt = "\n".join(parts)
        # Final pass across complete prompt
        full_prompt = sanitize(full_prompt)
        
        # Phase 2: Apply config-based length limit
        try:
            from backend.agents.agent_config import get_agent_config
            cfg = get_agent_config()
            max_len = cfg.prompt.max_length
            truncate_notice = cfg.prompt.truncate_notice
        except Exception:  # pragma: no cover
            max_len = 16000
            truncate_notice = "[TRUNCATED]"
        
        if len(full_prompt) > max_len:
            full_prompt = full_prompt[:max_len] + f"\n{truncate_notice}"
        
        return full_prompt
    
    @staticmethod
    def _get_mcp_tools_definition() -> list[dict[str, Any]]:
        """MCP file access tools для DeepSeek"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "mcp_read_project_file",
                    "description": "Read a file from the project",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Relative path to file"},
                            "max_size_kb": {"type": "integer", "description": "Maximum file size", "default": 100}
                        },
                        "required": ["file_path"]
                    }
                }
            }
        ]


class AgentMessage(BaseModel):
    """
    Сообщение между агентами
    
    Examples:
        >>> msg = AgentMessage(
        ...     message_id="msg-123",
        ...     from_agent=AgentType.DEEPSEEK,
        ...     to_agent=AgentType.COPILOT,
        ...     message_type=MessageType.RESPONSE,
        ...     content="Analysis complete",
        ...     context={},
        ...     conversation_id="conv-456"
        ... )
    """
    model_config = ConfigDict(use_enum_values=False)
    
    message_id: str = Field(..., description="Уникальный ID сообщения")
    from_agent: AgentType = Field(..., description="Отправитель")
    to_agent: AgentType = Field(..., description="Получатель")
    message_type: MessageType = Field(..., description="Тип сообщения")
    content: str = Field(..., min_length=1, max_length=50000, description="Содержимое сообщения")
    context: dict[str, Any] = Field(default_factory=dict, description="Контекст коммуникации")
    conversation_id: str = Field(..., description="ID беседы")
    iteration: int = Field(default=1, ge=1, le=100, description="Номер итерации")
    max_iterations: int = Field(default=5, ge=1, le=100, description="Максимум итераций")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Уверенность агента")
    timestamp: datetime = Field(default_factory=utc_now, description="Время создания")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные")


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class AgentResponse(BaseModel):
    """
    Унифицированный ответ от агента
    
    Examples:
        >>> response = AgentResponse(
        ...     success=True,
        ...     content="Analysis result",
        ...     channel=AgentChannel.DIRECT_API,
        ...     latency_ms=1250.5
        ... )
    """
    model_config = ConfigDict(use_enum_values=False)
    
    success: bool = Field(..., description="Успешность выполнения")
    content: str = Field(..., description="Ответ агента")
    channel: AgentChannel = Field(..., description="Канал коммуникации")
    api_key_index: int | None = Field(None, ge=0, le=11, description="Индекс использованного API ключа")
    latency_ms: float = Field(default=0, ge=0, description="Задержка в миллисекундах")
    error: str | None = Field(None, description="Описание ошибки (если есть)")
    timestamp: datetime = Field(default_factory=utc_now, description="Время ответа")
    
    @field_validator('latency_ms')
    @classmethod
    def validate_latency(cls, v: float) -> float:
        """Валидация задержки (не может быть отрицательной или слишком большой)"""
        if v < 0:
            raise ValueError("latency_ms cannot be negative")
        if v > 300000:  # 5 минут
            raise ValueError("latency_ms too large (>5 minutes), possible error")
        return v


class ConsensusRequest(BaseModel):
    """
    Запрос на получение консенсуса от нескольких агентов
    
    Examples:
        >>> req = ConsensusRequest(
        ...     question="What are the best indicators for crypto?",
        ...     agents=[AgentType.DEEPSEEK, AgentType.PERPLEXITY],
        ...     context={"domain": "crypto_trading"}
        ... )
    """
    model_config = ConfigDict(use_enum_values=False)
    
    question: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Вопрос для консенсуса"
    )
    agents: list[AgentType] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="Список агентов для опроса"
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Контекст запроса"
    )
    require_full_consensus: bool = Field(
        default=False,
        description="Требовать полного согласия всех агентов"
    )
    
    @field_validator('agents')
    @classmethod
    def validate_unique_agents(cls, v: list[AgentType]) -> list[AgentType]:
        """Проверка уникальности агентов"""
        if len(v) != len(set(v)):
            raise ValueError("agents must be unique")
        return v


class ConsensusResponse(BaseModel):
    """
    Ответ с консенсусом от агентов
    
    Examples:
        >>> resp = ConsensusResponse(
        ...     question="Original question",
        ...     consensus="Agreed answer",
        ...     individual_responses={"deepseek": "...", "perplexity": "..."},
        ...     agreement_level=0.85
        ... )
    """
    question: str = Field(..., description="Исходный вопрос")
    consensus: str = Field(..., description="Консенсусный ответ")
    individual_responses: dict[str, str] = Field(..., description="Индивидуальные ответы агентов")
    agreement_level: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Уровень согласованности (0-1)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Метаданные консенсуса"
    )
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="Время формирования консенсуса"
    )


# =============================================================================
# API KEY MODELS
# =============================================================================

class APIKey(BaseModel):
    """
    API ключ с метаданными
    
    Examples:
        >>> key = APIKey(
        ...     value="sk-xxx",
        ...     agent_type=AgentType.DEEPSEEK,
        ...     index=0
        ... )
    """
    model_config = ConfigDict(use_enum_values=False)
    
    value: str = Field(..., min_length=10, description="Значение API ключа")
    agent_type: AgentType = Field(..., description="Тип агента")
    index: int = Field(..., ge=0, le=11, description="Индекс ключа")
    is_active: bool = Field(default=True, description="Активен ли ключ")
    last_used: float | None = Field(None, description="Timestamp последнего использования")
    error_count: int = Field(default=0, ge=0, description="Счетчик ошибок")
    requests_count: int = Field(default=0, ge=0, description="Счетчик запросов")
    last_error_time: float | None = Field(None, description="Timestamp последней ошибки")
    
    @field_validator('value')
    @classmethod
    def validate_key_format(cls, v: str) -> str:
        """Базовая валидация формата API ключа"""
        if not v.startswith(('sk-', 'pplx-')):
            raise ValueError("API key must start with 'sk-' or 'pplx-'")
        return v


# =============================================================================
# HELPER MODELS
# =============================================================================

class AgentStats(BaseModel):
    """Статистика работы агента"""
    total_requests: int = Field(default=0, ge=0)
    successful_requests: int = Field(default=0, ge=0)
    failed_requests: int = Field(default=0, ge=0)
    mcp_success: int = Field(default=0, ge=0)
    mcp_failed: int = Field(default=0, ge=0)
    direct_api_success: int = Field(default=0, ge=0)
    direct_api_failed: int = Field(default=0, ge=0)
    avg_latency_ms: float = Field(default=0, ge=0)
    uptime_seconds: float = Field(default=0, ge=0)
    
    @property
    def success_rate(self) -> float:
        """Процент успешных запросов"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def mcp_preference(self) -> float:
        """Процент использования MCP vs Direct API"""
        mcp_total = self.mcp_success + self.mcp_failed
        total = mcp_total + self.direct_api_success + self.direct_api_failed
        if total == 0:
            return 0.0
        return mcp_total / total


class HealthStatus(BaseModel):
    """Статус здоровья агента"""
    is_healthy: bool = Field(..., description="Здоров ли агент")
    mcp_available: bool = Field(..., description="Доступен ли MCP")
    api_keys_available: int = Field(..., ge=0, description="Количество доступных API ключей")
    last_check: datetime = Field(default_factory=utc_now, description="Время последней проверки")
    errors: list[str] = Field(default_factory=list, description="Список ошибок")
