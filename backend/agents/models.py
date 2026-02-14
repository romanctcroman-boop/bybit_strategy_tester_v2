"""
🎯 Pydantic Models for Agent System

Standardized models for data validation and serialization
in the inter-agent communication system.

Benefits:
- Automatic data validation
- Type hints and IDE autocompletion
- JSON Schema generation
- FastAPI integration
- Built-in serialization/deserialization
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.utils.time import utc_now

# =============================================================================
# ENUMS
# =============================================================================


class AgentType(str, Enum):
    """AI agent types in the system"""

    DEEPSEEK = "deepseek"
    PERPLEXITY = "perplexity"
    QWEN = "qwen"
    COPILOT = "copilot"
    ORCHESTRATOR = "orchestrator"


class AgentChannel(str, Enum):
    """Agent communication channels"""

    MCP_SERVER = "mcp_server"
    DIRECT_API = "direct_api"
    BACKUP_API = "backup_api"


class MessageType(str, Enum):
    """Message types between agents"""

    QUERY = "query"
    RESPONSE = "response"
    VALIDATION = "validation"
    CONSENSUS_REQUEST = "consensus_request"
    ERROR = "error"
    COMPLETION = "completion"


class CommunicationPattern(str, Enum):
    """Communication patterns between agents"""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ITERATIVE = "iterative"
    COLLABORATIVE = "collaborative"
    HIERARCHICAL = "hierarchical"


class TaskType(str, Enum):
    """Task types for AI agents"""

    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    CODE_FIX = "code_fix"
    ANALYSIS = "analysis"
    EXPLANATION = "explanation"
    STRATEGY = "strategy"
    BACKTEST = "backtest"
    OPTIMIZATION = "optimization"


# =============================================================================
# TASK MODELS
# =============================================================================


class AgentTask(BaseModel):
    """
    Task for an AI agent

    Examples:
        >>> task = AgentTask(
        ...     task_type=TaskType.CODE_GENERATION,
        ...     instruction="Generate RSI strategy",
        ...     context={"pattern": "trend_following"}
        ... )
    """

    model_config = ConfigDict(use_enum_values=False)

    task_type: TaskType = Field(..., description="Task type")
    instruction: str = Field(
        ...,
        description="Instruction for task execution",
        min_length=1,
        max_length=5000,
    )
    context: dict[str, Any] = Field(default_factory=dict, description="Task context")
    priority: int = Field(default=5, ge=1, le=10, description="Task priority (1-10)")
    timeout: float = Field(default=120.0, gt=0, description="Timeout in seconds")


# =============================================================================
# REQUEST MODELS
# =============================================================================


class AgentRequest(BaseModel):
    """
    Unified request to an agent

    Examples:
        >>> request = AgentRequest(
        ...     agent_type=AgentType.DEEPSEEK,
        ...     task_type="analyze",
        ...     prompt="Analyze this trading strategy",
        ...     code="def my_strategy(): pass"
        ... )
    """

    model_config = ConfigDict(use_enum_values=False)

    agent_type: AgentType = Field(..., description="Target agent type")
    task_type: str = Field(
        ...,
        description="Task type: analyze, fix, explain, generate, etc.",
        min_length=1,
        max_length=50,
    )
    prompt: str = Field(..., description="Request text for the agent", min_length=1, max_length=10000)
    code: str | None = Field(None, description="Code for analysis (optional)", max_length=50000)
    context: dict[str, Any] = Field(default_factory=dict, description="Additional request context")

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v: str) -> str:
        """Validate allowed task types"""
        allowed = {
            "analyze",
            "fix",
            "explain",
            "generate",
            "optimize",
            "review",
            "test",
            "refactor",
            "document",
            "research",
        }
        if v.lower() not in allowed:
            raise ValueError(f"task_type must be one of {allowed}, got '{v}'")
        return v.lower()

    def to_mcp_format(self) -> dict[str, Any]:
        """Convert to MCP tool format"""
        return {
            "strategy_code": self.code or self.prompt,
            "include_suggestions": True,
            "focus": self.context.get("focus", "all"),
        }

    def to_direct_api_format(self, include_tools: bool = True) -> dict[str, Any]:
        """Convert to direct API format"""
        if self.agent_type == AgentType.DEEPSEEK:
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": ("You are an expert Python developer analyzing trading strategies."),
                    },
                    {"role": "user", "content": self._build_prompt()},
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
                    {
                        "role": "system",
                        "content": "You are a helpful assistant specialized in trading strategies.",
                    },
                    {"role": "user", "content": self._build_prompt()},
                ],
                "temperature": 0.2,
                "max_tokens": 2000,
            }

    def _build_prompt(self) -> str:
        """Build complete prompt with prompt injection protection.

        SECURITY: Implements Phase 1 MEDIUM vulnerability fix (prompt injection sanitization).
        Phase 2: Applies external config limits from agents.yaml if present.
        """
        import json
        import re

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
        """MCP file access tools for DeepSeek"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "mcp_read_project_file",
                    "description": "Read a file from the project",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Relative path to file",
                            },
                            "max_size_kb": {
                                "type": "integer",
                                "description": "Maximum file size",
                                "default": 100,
                            },
                        },
                        "required": ["file_path"],
                    },
                },
            }
        ]


class AgentMessage(BaseModel):
    """
    Message between agents

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

    message_id: str = Field(..., description="Unique message ID")
    from_agent: AgentType = Field(..., description="Sender")
    to_agent: AgentType = Field(..., description="Recipient")
    message_type: MessageType = Field(..., description="Message type")
    content: str = Field(..., min_length=1, max_length=50000, description="Message content")
    context: dict[str, Any] = Field(default_factory=dict, description="Communication context")
    conversation_id: str = Field(..., description="Conversation ID")
    iteration: int = Field(default=1, ge=1, le=100, description="Iteration number")
    max_iterations: int = Field(default=5, ge=1, le=100, description="Maximum iterations")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Agent confidence")
    timestamp: datetime = Field(default_factory=utc_now, description="Creation time")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class AgentResponse(BaseModel):
    """
    Unified response from an agent

    Examples:
        >>> response = AgentResponse(
        ...     success=True,
        ...     content="Analysis result",
        ...     channel=AgentChannel.DIRECT_API,
        ...     latency_ms=1250.5
        ... )
    """

    model_config = ConfigDict(use_enum_values=False)

    success: bool = Field(..., description="Execution success")
    content: str = Field(..., description="Agent response")
    channel: AgentChannel = Field(..., description="Communication channel")
    api_key_index: int | None = Field(None, ge=0, le=11, description="Index of used API key")
    latency_ms: float = Field(default=0, ge=0, description="Latency in milliseconds")
    error: str | None = Field(None, description="Error description (if any)")
    timestamp: datetime = Field(default_factory=utc_now, description="Response time")

    @field_validator("latency_ms")
    @classmethod
    def validate_latency(cls, v: float) -> float:
        """Validate latency (cannot be negative or too large)"""
        if v < 0:
            raise ValueError("latency_ms cannot be negative")
        if v > 300000:  # 5 minutes
            raise ValueError("latency_ms too large (>5 minutes), possible error")
        return v


class ConsensusRequest(BaseModel):
    """
    Request for consensus from multiple agents

    Examples:
        >>> req = ConsensusRequest(
        ...     question="What are the best indicators for crypto?",
        ...     agents=[AgentType.DEEPSEEK, AgentType.PERPLEXITY],
        ...     context={"domain": "crypto_trading"}
        ... )
    """

    model_config = ConfigDict(use_enum_values=False)

    question: str = Field(..., min_length=10, max_length=5000, description="Question for consensus")
    agents: list[AgentType] = Field(..., min_length=2, max_length=4, description="List of agents to query")
    context: dict[str, Any] = Field(default_factory=dict, description="Request context")
    require_full_consensus: bool = Field(default=False, description="Require full agreement of all agents")

    @field_validator("agents")
    @classmethod
    def validate_unique_agents(cls, v: list[AgentType]) -> list[AgentType]:
        """Check agent uniqueness"""
        if len(v) != len(set(v)):
            raise ValueError("agents must be unique")
        return v


class ConsensusResponse(BaseModel):
    """
    Consensus response from agents

    Examples:
        >>> resp = ConsensusResponse(
        ...     question="Original question",
        ...     consensus="Agreed answer",
        ...     individual_responses={"deepseek": "...", "perplexity": "..."},
        ...     agreement_level=0.85
        ... )
    """

    question: str = Field(..., description="Original question")
    consensus: str = Field(..., description="Consensus answer")
    individual_responses: dict[str, str] = Field(..., description="Individual agent responses")
    agreement_level: float = Field(..., ge=0.0, le=1.0, description="Agreement level (0-1)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Consensus metadata")
    timestamp: datetime = Field(default_factory=utc_now, description="Consensus formation time")


# =============================================================================
# API KEY MODELS
# =============================================================================


class APIKey(BaseModel):
    """
    API key with metadata

    Examples:
        >>> key = APIKey(
        ...     value="sk-xxx",
        ...     agent_type=AgentType.DEEPSEEK,
        ...     index=0
        ... )
    """

    model_config = ConfigDict(use_enum_values=False)

    value: str = Field(..., min_length=10, description="API key value")
    agent_type: AgentType = Field(..., description="Agent type")
    index: int = Field(..., ge=0, le=11, description="Key index")
    is_active: bool = Field(default=True, description="Whether key is active")
    last_used: float | None = Field(None, description="Last usage timestamp")
    error_count: int = Field(default=0, ge=0, description="Error counter")
    requests_count: int = Field(default=0, ge=0, description="Request counter")
    last_error_time: float | None = Field(None, description="Last error timestamp")

    @field_validator("value")
    @classmethod
    def validate_key_format(cls, v: str) -> str:
        """Basic API key format validation"""
        if not v.startswith(("sk-", "pplx-")):
            raise ValueError("API key must start with 'sk-' or 'pplx-'")
        return v


# =============================================================================
# HELPER MODELS
# =============================================================================


class AgentStats(BaseModel):
    """Agent operation statistics"""

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
        """Percentage of successful requests"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def mcp_preference(self) -> float:
        """Percentage of MCP vs Direct API usage"""
        mcp_total = self.mcp_success + self.mcp_failed
        total = mcp_total + self.direct_api_success + self.direct_api_failed
        if total == 0:
            return 0.0
        return mcp_total / total


class HealthStatus(BaseModel):
    """Agent health status"""

    is_healthy: bool = Field(..., description="Whether agent is healthy")
    mcp_available: bool = Field(..., description="Whether MCP is available")
    api_keys_available: int = Field(..., ge=0, description="Number of available API keys")
    last_check: datetime = Field(default_factory=utc_now, description="Last check time")
    errors: list[str] = Field(default_factory=list, description="Error list")
