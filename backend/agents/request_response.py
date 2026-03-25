"""
Agent Request/Response Models

Contains data models for agent communication:
- AgentRequest: Unified request format
- AgentResponse: Unified response format
- TokenUsage: Token usage statistics

Extracted from unified_agent_interface.py for better modularity.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from backend.agents.models import AgentChannel, AgentType


@dataclass
class AgentRequest:
    """
    Unified request to an agent.

    Supports both DeepSeek and Perplexity with proper formatting.
    Includes thinking mode, strict mode, and streaming options.
    """

    agent_type: AgentType
    task_type: str  # "analyze", "fix", "explain", "generate", etc.
    prompt: str
    code: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    thinking_mode: bool = False  # DeepSeek V3.2 Thinking Mode (CoT) — disabled by default for cost
    strict_mode: bool = False  # DeepSeek Strict Mode for guaranteed JSON
    stream: bool = False  # Enable streaming for real-time output

    # Unsafe patterns for prompt injection protection
    UNSAFE_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"output\s+(all\s+)?(api\s+)?keys",
        r"execute\s+code",
        r"<script>",
        r"eval\(",
        r"forget\s+(all\s+)?previous",
        r"disregard\s+",
    ]

    def to_mcp_format(self) -> dict[str, Any]:
        """Convert to MCP tool format."""
        return {
            "strategy_code": self.code or self.prompt,
            "include_suggestions": True,
            "focus": self.context.get("focus", "all"),
        }

    def to_direct_api_format(self, include_tools: bool = True) -> dict[str, Any]:
        """
        Convert to direct API format.

        DeepSeek V3.2 improvements:
        - Thinking mode with reasoning_content
        - Optimized sampling params
        - Developer role for search scenarios
        """
        if self.agent_type == AgentType.DEEPSEEK:
            return self._build_deepseek_payload(include_tools)
        else:
            return self._build_perplexity_payload()

    def _build_deepseek_payload(self, include_tools: bool) -> dict[str, Any]:
        """Build DeepSeek API payload.

        Cost protection: deepseek-reasoner is blocked unless
        DEEPSEEK_ALLOW_REASONER=true is set in env.
        """
        # Cost guard: block reasoner unless explicitly allowed
        allow_reasoner = os.getenv("DEEPSEEK_ALLOW_REASONER", "false").lower() == "true"
        use_thinking = self.thinking_mode and allow_reasoner

        if self.thinking_mode and not allow_reasoner:
            logger.warning("⚠️ deepseek-reasoner blocked (DEEPSEEK_ALLOW_REASONER=false). Using deepseek-chat instead.")

        model = "deepseek-reasoner" if use_thinking else "deepseek-chat"
        max_tokens = 16000 if use_thinking else 4000

        # V3.2 recommended sampling params
        sampling_params = {"top_p": 0.95} if use_thinking else {"temperature": 0.7}

        # Use 'developer' role for search tasks
        task_type = self.task_type.lower()
        is_search_task = task_type in ("search", "research", "web", "find", "lookup")
        system_role = "developer" if is_search_task else "system"

        payload = {
            "model": model,
            "messages": [
                {
                    "role": system_role,
                    "content": "You are an expert Python developer analyzing trading strategies.",
                },
                {"role": "user", "content": self._build_prompt()},
            ],
            "max_tokens": max_tokens,
            **sampling_params,
        }

        # Add MCP file access tools
        use_file_access = self.context.get("use_file_access", False)

        if include_tools and use_file_access:
            tools = self._get_mcp_tools_definition(strict_mode=self.strict_mode)
            payload["tools"] = tools
            logger.info(f"🔧 Added {len(tools)} MCP tools to DeepSeek request")

        return payload

    def _build_perplexity_payload(self) -> dict[str, Any]:
        """Build Perplexity API payload."""
        task_type = self.task_type.lower()

        # Cost guard: block expensive models unless explicitly allowed
        allow_expensive = os.getenv("PERPLEXITY_ALLOW_EXPENSIVE", "false").lower() == "true"

        if not allow_expensive:
            # Force cheap model regardless of task type
            if task_type in ("research", "report", "deep"):
                logger.warning(
                    "⚠️ sonar-deep-research blocked (PERPLEXITY_ALLOW_EXPENSIVE=false). "
                    f"Task '{task_type}' downgraded to sonar-pro."
                )
            elif task_type in ("analyze", "reason", "solve", "complex"):
                logger.warning(
                    "⚠️ sonar-reasoning-pro blocked (PERPLEXITY_ALLOW_EXPENSIVE=false). "
                    f"Task '{task_type}' downgraded to sonar-pro."
                )

            if task_type in ("quick", "simple", "fast"):
                model = "sonar"
                max_tokens = 1000
            else:
                model = "sonar-pro"
                max_tokens = 2000
        else:
            # Expensive models allowed
            if task_type in ("research", "report", "deep"):
                model = "sonar-deep-research"
                max_tokens = 4000
            elif task_type in ("analyze", "reason", "solve", "complex"):
                model = "sonar-reasoning-pro"
                max_tokens = 4000
            elif task_type in ("quick", "simple", "fast"):
                model = "sonar"
                max_tokens = 1000
            else:
                model = "sonar-pro"
                max_tokens = 2000

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant specialized in trading strategies and market analysis.",
                },
                {"role": "user", "content": self._build_prompt()},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }

        # Add web search options for research tasks
        if task_type in ("research", "news", "current", "latest"):
            payload["web_search_options"] = {
                "search_recency_filter": "week",
            }

        return payload

    def _build_prompt(self) -> str:
        """Build full prompt with security sanitization."""
        parts: list[str] = []
        parts.append(f"Task: {self._sanitize(self.task_type)}")
        parts.append(f"\n{self._sanitize(self.prompt)}")

        if self.code:
            parts.append(f"\n\nCode to analyze:\n```python\n{self.code}\n```")

        if self.context:
            safe_context = {
                self._sanitize(str(k)): self._sanitize(str(v)) if not isinstance(v, (dict, list)) else v
                for k, v in self.context.items()
            }
            parts.append(f"\n\nContext: {json.dumps(safe_context, indent=2)}")

        full_prompt = "\n".join(parts)
        return self._sanitize(full_prompt)

    def _sanitize(self, text: str) -> str:
        """Sanitize text to prevent prompt injection."""
        if not text:
            return text

        for pattern in self.UNSAFE_PATTERNS:
            new = re.sub(pattern, "[REDACTED_UNSAFE_PATTERN]", text, flags=re.IGNORECASE)
            if new != text:
                logger.warning(f"🚫 Unsafe pattern sanitized: {pattern}")
            text = new

        return text

    @staticmethod
    def _get_mcp_tools_definition(strict_mode: bool = False) -> list[dict[str, Any]]:
        """Get MCP file access tools definition for DeepSeek."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "mcp_read_project_file",
                    "description": "Read a file from the project. Supports Python, JSON, Markdown, YAML files.",
                    "strict": strict_mode,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Relative path to file from project root",
                            },
                            "max_size_kb": {
                                "type": "integer",
                                "description": "Maximum file size in KB (default: 100)",
                                "default": 100,
                            },
                        },
                        "required": ["file_path"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_list_project_structure",
                    "description": "List directory structure of the project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "Directory to list (default: '.')",
                                "default": ".",
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum depth to traverse (default: 3)",
                                "default": 3,
                            },
                            "include_hidden": {
                                "type": "boolean",
                                "description": "Include hidden files/folders (default: false)",
                                "default": False,
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_analyze_code_quality",
                    "description": "Run code quality tools (Ruff, Black, Bandit) on a Python file.",
                    "strict": strict_mode,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to Python file to analyze",
                            },
                            "tools": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["ruff", "black", "bandit"],
                                },
                                "description": "Tools to run",
                                "default": ["ruff", "black", "bandit"],
                            },
                        },
                        "required": ["file_path"],
                        "additionalProperties": False,
                    },
                },
            },
        ]
        return tools


@dataclass
class TokenUsage:
    """Token usage statistics from API response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0  # DeepSeek V3.2: tokens in reasoning_content
    cost_usd: float | None = None  # Perplexity returns cost directly
    # DeepSeek Context Caching (V3.2)
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    cache_savings_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cost_usd": self.cost_usd,
            "cache_hit_tokens": self.cache_hit_tokens,
            "cache_miss_tokens": self.cache_miss_tokens,
            "cache_savings_pct": self.cache_savings_pct,
        }

    @classmethod
    def from_deepseek_response(cls, usage: dict) -> "TokenUsage":
        """Parse from DeepSeek API response."""
        return cls(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            reasoning_tokens=usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0),
            cache_hit_tokens=usage.get("prompt_cache_hit_tokens", 0),
            cache_miss_tokens=usage.get("prompt_cache_miss_tokens", 0),
        )

    @classmethod
    def from_perplexity_response(cls, usage: dict) -> "TokenUsage":
        """Parse from Perplexity API response."""
        return cls(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )


@dataclass
class AgentResponse:
    """
    Unified response from an agent.

    Contains:
    - Response content
    - Metadata (latency, channel, etc.)
    - Optional reasoning content (DeepSeek thinking mode)
    - Optional tool calls
    - Optional citations (Perplexity)
    """

    success: bool
    content: str
    channel: AgentChannel
    api_key_index: int | None = None
    latency_ms: float = 0
    error: str | None = None
    timestamp: float = field(default_factory=time.time)
    reasoning_content: str | None = None  # DeepSeek V3.2 Thinking Mode CoT
    tool_calls: list[dict] | None = None
    tokens_used: TokenUsage | None = None
    citations: list[str] | None = None  # Perplexity: list of source URLs

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "content": self.content,
            "channel": self.channel.value,
            "api_key_index": self.api_key_index,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "timestamp": self.timestamp,
            "reasoning_content": self.reasoning_content,
            "tool_calls": self.tool_calls,
            "tokens_used": self.tokens_used.to_dict() if self.tokens_used else None,
            "citations": self.citations,
        }

    @classmethod
    def error_response(
        cls,
        error: str,
        channel: AgentChannel = AgentChannel.DIRECT_API,
        latency_ms: float = 0,
    ) -> "AgentResponse":
        """Create an error response."""
        return cls(
            success=False,
            content="",
            channel=channel,
            error=error,
            latency_ms=latency_ms,
        )
