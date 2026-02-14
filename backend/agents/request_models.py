"""
Agent Request/Response Models

Extracted from unified_agent_interface.py to reduce god-class complexity.
Contains: AgentRequest, TokenUsage, AgentResponse.

These are the data transfer objects for the agent system communication layer.
"""

from __future__ import annotations

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
    """Unified request to an AI agent.

    Supports DeepSeek, Qwen, and Perplexity with provider-specific formatting.

    Attributes:
        agent_type: Target provider (DeepSeek, Qwen, Perplexity)
        task_type: Task category ("analyze", "fix", "search", etc.)
        prompt: User prompt text
        code: Optional code to analyze
        context: Additional context dict
        thinking_mode: Enable CoT reasoning (DeepSeek V3.2)
        strict_mode: Guarantee JSON tool output (DeepSeek)
        stream: Enable streaming response
    """

    agent_type: AgentType
    task_type: str
    prompt: str
    code: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    thinking_mode: bool = False
    strict_mode: bool = False
    stream: bool = False

    # Prompt injection protection patterns
    _UNSAFE_PATTERNS: list[str] = field(
        default_factory=lambda: [
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"output\s+(all\s+)?(api\s+)?keys",
            r"execute\s+code",
            r"<script>",
            r"eval\(",
            r"forget\s+(all\s+)?previous",
            r"disregard\s+",
        ],
        repr=False,
        compare=False,
    )

    def to_mcp_format(self) -> dict[str, Any]:
        """Convert to MCP tool format."""
        return {
            "strategy_code": self.code or self.prompt,
            "include_suggestions": True,
            "focus": self.context.get("focus", "all"),
        }

    def to_direct_api_format(self, include_tools: bool = True) -> dict[str, Any]:
        """Convert to direct API format with provider-specific settings.

        Args:
            include_tools: Whether to include tool definitions (DeepSeek only)

        Returns:
            API payload dict ready for HTTP POST
        """
        if self.agent_type == AgentType.DEEPSEEK:
            return self._build_deepseek_payload(include_tools)
        elif self.agent_type == AgentType.QWEN:
            return self._build_qwen_payload()
        else:
            return self._build_perplexity_payload()

    def _build_deepseek_payload(self, include_tools: bool) -> dict[str, Any]:
        """Build DeepSeek V3.2 API payload.

        Cost protection: deepseek-reasoner is blocked unless
        DEEPSEEK_ALLOW_REASONER=true is set in env.
        """
        # Cost guard: block reasoner unless explicitly allowed
        allow_reasoner = os.getenv("DEEPSEEK_ALLOW_REASONER", "false").lower() == "true"
        use_thinking = self.thinking_mode and allow_reasoner

        if self.thinking_mode and not allow_reasoner:
            logger.warning(
                "⚠️ deepseek-reasoner blocked (DEEPSEEK_ALLOW_REASONER=false). "
                "Using deepseek-chat instead. Set DEEPSEEK_ALLOW_REASONER=true to allow."
            )

        model = "deepseek-reasoner" if use_thinking else "deepseek-chat"
        max_tokens = 16000 if use_thinking else 4000

        sampling_params = {"top_p": 0.95} if use_thinking else {"temperature": 0.7}

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

        use_file_access = self.context.get("use_file_access", False)
        if include_tools and use_file_access:
            tools = self._get_mcp_tools_definition(strict_mode=self.strict_mode)
            payload["tools"] = tools

        return payload

    def _build_qwen_payload(self) -> dict[str, Any]:
        """Build Qwen API payload."""
        model = os.getenv("QWEN_MODEL", "qwen-plus")
        temperature = float(os.getenv("QWEN_TEMPERATURE", "0.4"))

        # Cost guard: block thinking mode unless explicitly allowed via env var
        allow_thinking = os.getenv("QWEN_ENABLE_THINKING", "false").lower() == "true"

        if not allow_thinking:
            enable_thinking = False
            if self.task_type.lower() in (
                "analyze",
                "optimize",
                "compare",
                "deliberation",
                "strategy_evolution",
            ):
                logger.warning(
                    "⚠️ Qwen thinking mode blocked (QWEN_ENABLE_THINKING=false). "
                    f"Task '{self.task_type}' would have triggered thinking. Using standard mode."
                )
        else:
            # Dynamic thinking mode — only when explicitly allowed
            try:
                from backend.agents.llm.prompt_optimizer import get_prompt_optimizer

                optimizer = get_prompt_optimizer()
                task_desc = f"{self.task_type} {self.prompt[:200]}"
                enable_thinking = optimizer.should_enable_thinking("qwen", task_desc)
            except ImportError:
                enable_thinking = self.task_type.lower() in (
                    "analyze",
                    "optimize",
                    "compare",
                    "deliberation",
                    "strategy_evolution",
                )

        if not enable_thinking and os.getenv("QWEN_MODEL_FAST"):
            model = os.getenv("QWEN_MODEL_FAST", model)

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert quantitative analyst and algorithmic trader.",
                },
                {"role": "user", "content": self._build_prompt()},
            ],
            "temperature": temperature,
            "max_tokens": 8192 if enable_thinking else 4096,
        }

        if enable_thinking:
            payload["enable_thinking"] = True

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

        if task_type in ("research", "news", "current", "latest"):
            payload["web_search_options"] = {"search_recency_filter": "week"}

        return payload

    def _build_prompt(self) -> str:
        """Build full prompt with injection protection."""

        def sanitize(text: str) -> str:
            if not text:
                return text
            for pattern in self._UNSAFE_PATTERNS:
                new = re.sub(pattern, "[REDACTED_UNSAFE_PATTERN]", text, flags=re.IGNORECASE)
                if new != text:
                    logger.warning(f"🚫 Unsafe pattern sanitized: {pattern}")
                text = new
            return text

        parts: list[str] = []
        parts.append(f"Task: {sanitize(self.task_type)}")
        parts.append(f"\n{sanitize(self.prompt)}")

        if self.code:
            parts.append(f"\n\nCode to analyze:\n```python\n{self.code}\n```")

        if self.context:
            safe_context = {
                sanitize(str(k)): sanitize(str(v)) if not isinstance(v, (dict, list)) else v
                for k, v in self.context.items()
            }
            parts.append(f"\n\nContext: {json.dumps(safe_context, indent=2)}")

        full_prompt = "\n".join(parts)
        full_prompt = sanitize(full_prompt)
        return full_prompt

    @staticmethod
    def _get_mcp_tools_definition(strict_mode: bool = False) -> list[dict[str, Any]]:
        """Get MCP file access tool definitions for DeepSeek."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "mcp_read_project_file",
                    "description": (
                        "Read a file from the project. Supports Python, JSON, Markdown, "
                        "YAML files. Has security restrictions (cannot read .env, .git, secrets)."
                    ),
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
                    "description": (
                        "List directory structure of the project. Returns nested tree. "
                        "Auto-blocks .git, __pycache__, node_modules."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "Directory to list (relative to project root)",
                                "default": ".",
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum depth to traverse (default: 3)",
                                "default": 3,
                            },
                            "include_hidden": {
                                "type": "boolean",
                                "description": "Include hidden files/folders",
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
                    "description": ("Run code quality tools (Ruff, Black, Bandit) on a Python file."),
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
    """Token usage statistics from API response.

    Tracks prompt, completion, reasoning tokens and cost.
    Supports DeepSeek V3.2 context caching metrics.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float | None = None
    # DeepSeek Context Caching (V3.2)
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    cache_savings_pct: float = 0.0


@dataclass
class AgentResponse:
    """Unified response from an AI agent.

    Contains the response content, metadata about the channel used,
    timing information, and optional reasoning/citations.
    """

    success: bool
    content: str
    channel: AgentChannel
    api_key_index: int | None = None
    latency_ms: float = 0
    error: str | None = None
    timestamp: float = field(default_factory=time.time)
    reasoning_content: str | None = None
    tool_calls: list[dict] | None = None
    tokens_used: TokenUsage | None = None
    citations: list[str] | None = None
    metadata: dict[str, Any] | None = None
