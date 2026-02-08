"""
🤖 Unified Agent Interface - Автономная система с автофоллбэком

Архитектура:
1. MCP Server (primary) → Direct API (fallback)
2. Автоматическая расшифровка 8 DeepSeek + 4 Perplexity API keys
3. Health checks каждые 30s
4. Автоматическое переключение между API ключами при ошибках
5. Унифицированный формат запросов (работает через любой канал)

Quick Wins (from autonomous self-improvement):
- Quick Win #1: Tool call budget counter (защита от runaway loops)
- Quick Win #2: Async lock for key selection (thread-safe multi-worker)
- Quick Win #4: Removed debug logging (cleaner logs)
"""

import asyncio
import json
import random
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any

import httpx
from dotenv import load_dotenv
from loguru import logger

from backend.agents.base_config import FORCE_DIRECT_AGENT_API, MCP_DISABLED

# Phase 1: Circuit Breaker and Health Monitoring
from backend.agents.circuit_breaker_manager import (
    CircuitBreakerError,
    get_circuit_manager,
)
from backend.agents.health_monitor import (
    HealthCheckResult,
    HealthStatus,
    RecoveryActionType,
    get_health_monitor,
)

# ✅ FIX: Import AgentType from models.py instead of redefining
from backend.agents.models import AgentChannel, AgentType

# Metrics system (lazy import for graceful degradation)
try:
    from backend.monitoring.agent_metrics import metrics_enabled, record_agent_call
except ImportError:
    logger.warning("⚠️ Metrics system not available - recording disabled")
    metrics_enabled = False

    async def record_agent_call(*args, **kwargs):
        """Stub for when metrics are unavailable"""
        pass


# Load environment variables from .env
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

# ✅ FIX: AgentChannel also redefined - should import from models.py
# Removing duplicate definitions, will use from models.py


class APIKeyHealth(str, Enum):
    """Health tiers for API keys"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISABLED = "disabled"


@dataclass(init=False)
class APIKey:
    """API ключ с метаданными и ленивой расшифровкой"""

    agent_type: AgentType
    index: int  # 0-7 для DeepSeek, 0-3 для Perplexity
    health: APIKeyHealth = APIKeyHealth.HEALTHY
    last_used: float | None = None
    error_count: int = 0
    requests_count: int = 0
    cooldown_until: float | None = None
    cooldown_level: int = 0
    last_cooldown_reason: str | None = None
    last_cooldown_started: float | None = None
    cooling_events: int = 0
    key_name: str | None = None
    last_error_time: float | None = None
    _value_override: str | None = field(default=None, repr=False, compare=False)
    _key_manager: Any | None = field(default=None, repr=False, compare=False)

    def __init__(
        self,
        value: str | None,
        agent_type: AgentType,
        index: int,
        *,
        key_name: str | None = None,
        health: APIKeyHealth = APIKeyHealth.HEALTHY,
        last_used: float | None = None,
        error_count: int = 0,
        requests_count: int = 0,
        last_error_time: float | None = None,
        cooldown_until: float | None = None,
        cooldown_level: int = 0,
        last_cooldown_reason: str | None = None,
        last_cooldown_started: float | None = None,
        cooling_events: int = 0,
        is_active: bool | None = None,
        **legacy_kwargs: Any,
    ) -> None:
        if legacy_kwargs:
            logger.debug("APIKey received legacy kwargs: {}", list(legacy_kwargs.keys()))
        self._value_override = value
        self.key_name = key_name
        self.agent_type = agent_type
        self.index = index
        self.health = health
        self.last_used = last_used
        self.error_count = error_count
        self.requests_count = requests_count
        self.last_error_time = last_error_time
        self.cooldown_until = cooldown_until
        self.cooldown_level = cooldown_level
        self.last_cooldown_reason = last_cooldown_reason
        self.last_cooldown_started = last_cooldown_started
        self.cooling_events = cooling_events
        self._key_manager = None
        if is_active is not None:
            self.is_active = is_active

    @property
    def value(self) -> str:
        """Получить значение API ключа, расшифровывая по требованию."""
        if self._value_override is not None:
            return self._value_override
        if not self.key_name:
            raise ValueError("API key has no associated secret or key name")
        if self._key_manager is None:
            from backend.security.key_manager import get_key_manager

            self._key_manager = get_key_manager()
        return self._key_manager.get_decrypted_key(self.key_name)

    @property
    def is_usable(self) -> bool:
        if self.health == APIKeyHealth.DISABLED:
            return False
        return not self.is_cooling

    @property
    def is_cooling(self) -> bool:
        return bool(self.cooldown_until and self.cooldown_until > time.time())

    @property
    def cooldown_remaining(self) -> float:
        if not self.cooldown_until:
            return 0.0
        remaining = self.cooldown_until - time.time()
        return max(0.0, remaining)

    @property
    def status(self) -> str:
        if self.is_cooling:
            return "cooling"
        return self.health.value

    @property
    def is_active(self) -> bool:
        """Backward compatible alias for legacy code/tests."""
        return self.is_usable

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.health = APIKeyHealth.HEALTHY if value else APIKeyHealth.DISABLED
        if value:
            self.error_count = min(self.error_count, 1)
            self.last_error_time = None
        else:
            self.last_error_time = time.time()

    def begin_cooldown(self, duration: float, reason: str = "rate_limit") -> float:
        duration = max(0.0, duration)
        now = time.time()
        self.cooldown_until = now + duration if duration else now
        self.last_cooldown_started = now
        self.last_cooldown_reason = reason
        self.cooldown_level = min(self.cooldown_level + 1, 10)
        self.cooling_events += 1
        return duration

    def clear_cooldown(self) -> None:
        if self.cooldown_level > 0:
            self.cooldown_level -= 1
        self.cooldown_until = None
        self.last_cooldown_started = None
        self.last_cooldown_reason = None

    def maybe_exit_cooldown(self) -> bool:
        if self.cooldown_until and self.cooldown_until <= time.time():
            self.clear_cooldown()
            return True
        return False


@dataclass
class AgentRequest:
    """Унифицированный запрос к агенту"""

    agent_type: AgentType
    task_type: str  # "analyze", "fix", "explain", "generate", etc.
    prompt: str
    code: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    thinking_mode: bool = True  # DeepSeek V3.2 Thinking Mode (CoT) - enabled by default
    strict_mode: bool = False  # DeepSeek Strict Mode for guaranteed JSON tool output
    stream: bool = False  # Enable streaming for real-time output

    def to_mcp_format(self) -> dict[str, Any]:
        """Преобразовать в формат MCP tool"""
        return {
            "strategy_code": self.code or self.prompt,
            "include_suggestions": True,
            "focus": self.context.get("focus", "all"),
        }

    def to_direct_api_format(self, include_tools: bool = True) -> dict[str, Any]:
        """Преобразовать в формат прямого API (с опциональными tools)

        DeepSeek V3.2 improvements:
        - Thinking mode with reasoning_content
        - Optimized sampling params (temperature=1.0, top_p=0.95 for thinking)
        - Developer role for search agent scenarios
        """
        if self.agent_type == AgentType.DEEPSEEK:
            # DeepSeek V3.2: Use thinking mode if enabled
            model = "deepseek-reasoner" if self.thinking_mode else "deepseek-chat"
            max_tokens = 16000 if self.thinking_mode else 4000  # Thinking needs more tokens

            # V3.2 recommended sampling params
            if self.thinking_mode:
                # Thinking mode: recommended temperature=1.0, top_p=0.95
                # But API ignores temperature for thinking, so we set top_p only
                sampling_params = {"top_p": 0.95}
            else:
                sampling_params = {"temperature": 0.7}

            # Build system message - use 'developer' role for search/research tasks
            task_type = self.task_type.lower()
            is_search_task = task_type in (
                "search",
                "research",
                "web",
                "find",
                "lookup",
            )
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

            # Add MCP file access tools for DeepSeek
            use_file_access = self.context.get("use_file_access", False)
            logger.debug(
                f"🔍 use_file_access={use_file_access}, include_tools={include_tools}, "
                f"thinking_mode={self.thinking_mode}, strict_mode={self.strict_mode}"
            )

            if include_tools and use_file_access:
                tools = self._get_mcp_tools_definition(strict_mode=self.strict_mode)
                payload["tools"] = tools
                logger.info(f"🔧 Added {len(tools)} MCP tools to DeepSeek request (strict={self.strict_mode})")
            else:
                logger.debug(
                    f"⚠️  Tools not included (include_tools={include_tools}, use_file_access={use_file_access})"
                )

            return payload

        else:  # Perplexity
            # Perplexity 2025 models:
            # - sonar: Quick search
            # - sonar-pro: Complex queries (default)
            # - sonar-reasoning: Step-by-step thinking
            # - sonar-reasoning-pro: DeepSeek-R1 + CoT (best for analysis)
            # - sonar-deep-research: Exhaustive research

            task_type = self.task_type.lower()

            # Select model based on task type
            if task_type in ("research", "report", "deep"):
                model = "sonar-deep-research"
                max_tokens = 4000
            elif task_type in ("analyze", "reason", "solve", "complex"):
                model = "sonar-reasoning-pro"  # DeepSeek-R1 with CoT!
                max_tokens = 4000
            elif task_type in ("quick", "simple", "fast"):
                model = "sonar"
                max_tokens = 1000
            else:
                model = "sonar-pro"  # Default for general queries
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
                    "search_recency_filter": "week",  # Recent results
                }

            return payload

    def _build_prompt(self) -> str:
        """Построить полный prompt

        🔐 SECURITY: Implements prompt injection protection per consensus proposal (99% approval).
        """
        import re

        # 🔐 SECURITY PATCH #3: Prompt injection protection (MEDIUM)
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
        # Final sweep across entire assembled prompt (covers multi-line patterns)
        full_prompt = sanitize(full_prompt)
        return full_prompt

    @staticmethod
    def _get_mcp_tools_definition(strict_mode: bool = False) -> list[dict[str, Any]]:
        """Получить определения MCP file access tools для DeepSeek

        Args:
            strict_mode: If True, adds 'strict: true' to tools for guaranteed JSON output
                        Requires using beta URL: https://api.deepseek.com/beta
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "mcp_read_project_file",
                    "description": (
                        "Read a file from the project. Supports Python, JSON, Markdown, "
                        "YAML files. Has security restrictions (cannot read .env, .git, secrets)."
                    ),
                    "strict": strict_mode,  # DeepSeek Strict Mode
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Relative path to file from project root (e.g., 'backend/api/app.py')",
                            },
                            "max_size_kb": {
                                "type": "integer",
                                "description": "Maximum file size in KB (default: 100)",
                                "default": 100,
                            },
                        },
                        "required": ["file_path"],
                        "additionalProperties": False,  # Required for strict mode
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
                                "description": "Directory to list (relative to project root, default: '.')",
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
                    "description": (
                        "Run code quality tools (Ruff, Black, Bandit) on a Python file. "
                        "Returns linting issues, formatting problems, security vulnerabilities."
                    ),
                    "strict": strict_mode,  # DeepSeek Strict Mode
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
                                "description": "Tools to run (default: ['ruff', 'black', 'bandit'])",
                                "default": ["ruff", "black", "bandit"],
                            },
                        },
                        "required": ["file_path"],
                        "additionalProperties": False,  # Required for strict mode
                    },
                },
            },
        ]
        return tools


@dataclass
class TokenUsage:
    """Token usage statistics from API response"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0  # DeepSeek V3.2: tokens in reasoning_content
    cost_usd: float | None = None  # Perplexity returns cost directly
    # DeepSeek Context Caching (V3.2)
    cache_hit_tokens: int = 0  # prompt_cache_hit_tokens - tokens from cache
    cache_miss_tokens: int = 0  # prompt_cache_miss_tokens - tokens not cached
    cache_savings_pct: float = 0.0  # Percentage of tokens saved from cache


@dataclass
class AgentResponse:
    """Унифицированный ответ от агента"""

    success: bool
    content: str
    channel: AgentChannel
    api_key_index: int | None = None
    latency_ms: float = 0
    error: str | None = None
    timestamp: float = field(default_factory=time.time)
    reasoning_content: str | None = None  # DeepSeek V3.2 Thinking Mode CoT
    tool_calls: list[dict] | None = None  # Tool calls from response
    tokens_used: "TokenUsage | None" = None  # Token usage tracking
    citations: list[str] | None = None  # Perplexity: list of source URLs


# =============================================================================
# ENCRYPTION SYSTEM INTEGRATION
# =============================================================================


class APIKeyManager:
    """Менеджер API ключей с расшифровкой

    Quick Win #2: Thread-safe key selection with async lock
    Prevents race condition in multi-worker FastAPI deployment
    """

    BASE_COOLDOWN_SECONDS = 5.0
    MAX_COOLDOWN_SECONDS = 300.0
    COOLDOWN_ALERT_THRESHOLD = 0.5
    COOLDOWN_ALERT_COOLDOWN = 60.0

    def __init__(self):
        self.deepseek_keys: list[APIKey] = []
        self.perplexity_keys: list[APIKey] = []

        # ✅ QUICK WIN #2: Async lock for thread-safe key selection
        self._key_selection_lock = asyncio.Lock()
        self._alert_callback: Callable[[AgentType, int, int], None] | None = None
        self.pool_telemetry: dict[str, Any] = {
            "cooldown_events": 0,
            "rate_limit_events": 0,
            "alerts_triggered": 0,
            "snapshots": {},
        }
        self._last_pool_alert_ts: dict[AgentType, float] = {}

        self._load_keys()

    def _load_keys(self):
        """Загрузить и расшифровать все API ключи"""
        try:
            # Импорт системы шифрования
            from backend.security.key_manager import KeyManager

            km = KeyManager()

            # DeepSeek (8 keys)
            for i in range(8):
                key_name = f"DEEPSEEK_API_KEY_{i + 1}" if i > 0 else "DEEPSEEK_API_KEY"
                try:
                    if km.has_key(key_name, require_decryptable=True):
                        self.deepseek_keys.append(
                            APIKey(
                                value=None,
                                agent_type=AgentType.DEEPSEEK,
                                index=i,
                                key_name=key_name,
                            )
                        )
                        # 🔐 SECURITY PATCH #5: Logging security (LOW) - don't expose key indices
                        logger.debug(f"✅ DeepSeek key registered (pool size: {len(self.deepseek_keys)})")
                except Exception as e:
                    logger.warning(f"⚠️ DeepSeek key lookup failed: {e}")

            # Perplexity (8 keys - расширено с 4 до 8)
            for i in range(8):
                key_name = f"PERPLEXITY_API_KEY_{i + 1}" if i > 0 else "PERPLEXITY_API_KEY"
                try:
                    if km.has_key(key_name, require_decryptable=True):
                        self.perplexity_keys.append(
                            APIKey(
                                value=None,
                                agent_type=AgentType.PERPLEXITY,
                                index=i,
                                key_name=key_name,
                            )
                        )
                        # 🔐 SECURITY PATCH #5: Logging security (LOW) - don't expose key indices
                        logger.debug(f"✅ Perplexity key registered (pool size: {len(self.perplexity_keys)})")
                except Exception as e:
                    logger.warning(f"⚠️ Perplexity key lookup failed: {e}")

            logger.info(f"🔑 Loaded {len(self.deepseek_keys)} DeepSeek + {len(self.perplexity_keys)} Perplexity keys")

        except ImportError:
            logger.error("❌ Encryption system not available!")
            raise

    def _get_pool(self, agent_type: AgentType) -> list[APIKey]:
        return self.deepseek_keys if agent_type == AgentType.DEEPSEEK else self.perplexity_keys

    def _refresh_cooldowns(self, agent_type: AgentType) -> None:
        pool = self._get_pool(agent_type)
        recovered = 0
        for key in pool:
            if key.maybe_exit_cooldown():
                recovered += 1
        if recovered:
            logger.info(f"🔥 Restored {recovered} cooled {agent_type.value} keys")

    def _calculate_weight(self, key: APIKey) -> float:
        if not key.is_usable:
            return 0.0
        health_weight = {
            APIKeyHealth.HEALTHY: 3.0,
            APIKeyHealth.DEGRADED: 1.5,
            APIKeyHealth.DISABLED: 0.0,
        }.get(key.health, 1.0)
        request_penalty = 1.0 / (1 + max(0, key.requests_count) / 25)
        error_penalty = 1.0 / (1 + max(0, key.error_count))
        cooldown_penalty = 0.5**key.cooldown_level if key.cooldown_level else 1.0
        recency_bonus = 1.0
        if key.last_used:
            idle_time = max(0.0, time.time() - key.last_used)
            recency_bonus = min(1.2, 0.2 + idle_time / 30.0)
        weight = health_weight * request_penalty * error_penalty * cooldown_penalty * recency_bonus
        return max(0.001, weight)

    def _apply_cooldown(
        self,
        key: APIKey,
        reason: str,
        duration: float | None = None,
    ) -> float:
        exponent = max(0, key.cooldown_level)
        base_duration = self.BASE_COOLDOWN_SECONDS * (2**exponent)
        cooldown_duration = duration if duration is not None else base_duration
        cooldown_duration = min(cooldown_duration, self.MAX_COOLDOWN_SECONDS)
        actual = key.begin_cooldown(cooldown_duration, reason)
        self.pool_telemetry["cooldown_events"] += 1
        self.pool_telemetry.setdefault("cooldown_reasons", {}).setdefault(reason, 0)
        self.pool_telemetry["cooldown_reasons"][reason] += 1
        logger.warning(f"⏳ Cooling {key.agent_type.value} key #{key.index} for {cooldown_duration:.1f}s ({reason})")
        self._emit_pool_telemetry(key.agent_type)
        self._maybe_alert_pool_pressure(key.agent_type)
        return actual

    def _emit_pool_telemetry(self, agent_type: AgentType) -> None:
        pool = self._get_pool(agent_type)
        total = len(pool)
        cooling = sum(1 for key in pool if key.is_cooling)
        usable = sum(1 for key in pool if key.is_usable)
        disabled = sum(1 for key in pool if key.health == APIKeyHealth.DISABLED)
        snapshot = {
            "total_keys": total,
            "usable": usable,
            "cooling": cooling,
            "disabled": disabled,
            "timestamp": time.time(),
        }
        self.pool_telemetry["snapshots"][agent_type.value] = snapshot
        logger.debug(f"📊 KeyPool[{agent_type.value}] snapshot: {snapshot}")

    def _maybe_alert_pool_pressure(self, agent_type: AgentType) -> None:
        pool = self._get_pool(agent_type)
        total = len(pool)
        if not total:
            return
        cooling = sum(1 for key in pool if key.is_cooling)
        ratio = cooling / total
        if ratio >= self.COOLDOWN_ALERT_THRESHOLD:
            now = time.time()
            last_alert = self._last_pool_alert_ts.get(agent_type, 0)
            if now - last_alert >= self.COOLDOWN_ALERT_COOLDOWN:
                self._last_pool_alert_ts[agent_type] = now
                self.pool_telemetry["alerts_triggered"] += 1
                logger.error(f"🚨 {agent_type.value} key pool under pressure: {cooling}/{total} keys cooling")
                if self._alert_callback:
                    self._alert_callback(agent_type, cooling, total)

    def get_pool_metrics(self, agent_type: AgentType) -> dict[str, Any]:
        pool = self._get_pool(agent_type)
        total = len(pool)
        cooling = sum(1 for key in pool if key.is_cooling)
        healthy = sum(1 for key in pool if key.health == APIKeyHealth.HEALTHY and not key.is_cooling)
        degraded = sum(1 for key in pool if key.health == APIKeyHealth.DEGRADED and not key.is_cooling)
        cooling_keys = [key for key in pool if key.is_cooling]
        earliest_ready = min((key.cooldown_until or float("inf")) for key in cooling_keys) if cooling_keys else None
        return {
            "total": total,
            "cooling": cooling,
            "healthy": healthy,
            "degraded": degraded,
            "next_available_in": max(0.0, earliest_ready - time.time()) if earliest_ready else 0.0,
        }

    def register_alert_callback(self, callback: Callable[[AgentType, int, int], None]) -> None:
        self._alert_callback = callback

    def _health_sort_key(self, key: APIKey) -> tuple[int, int, int, float]:
        priority_map = {
            APIKeyHealth.HEALTHY: 0,
            APIKeyHealth.DEGRADED: 1,
            APIKeyHealth.DISABLED: 2,
        }
        last_used_sort = -(key.last_used or 0)
        return (
            priority_map.get(key.health, 1),
            key.error_count,
            key.requests_count,
            last_used_sort,
        )

    def _update_health_state(self, key: APIKey) -> None:
        # Graceful degradation if APIKey object doesn't expose health attribute (legacy model)
        if not hasattr(key, "health"):
            return  # Skip health management for simplified key model

        if key.health == APIKeyHealth.DISABLED and key.error_count < 5:
            key.health = APIKeyHealth.DEGRADED if key.error_count >= 2 else APIKeyHealth.HEALTHY

        if key.error_count >= 5:
            key.health = APIKeyHealth.DISABLED
        elif key.error_count >= 2:
            key.health = APIKeyHealth.DEGRADED
        else:
            key.health = APIKeyHealth.HEALTHY

    async def get_active_key(self, agent_type: AgentType) -> APIKey | None:
        """
        Получить активный API ключ (с наименьшим количеством ошибок)

        ✅ QUICK WIN #2: Thread-safe with async lock
        Prevents race condition when multiple concurrent requests select the same key
        """
        async with self._key_selection_lock:
            self._refresh_cooldowns(agent_type)
            pool = self._get_pool(agent_type)
            if not pool:
                return None

            active_keys = [k for k in pool if k.is_usable]
            if not active_keys:
                self._emit_pool_telemetry(agent_type)
                self._maybe_alert_pool_pressure(agent_type)
                return None

            weights = [self._calculate_weight(k) for k in active_keys]
            if not any(weights):
                logger.warning(f"⚠️ No positive weights for {agent_type.value} key pool")
                return None

            selected = random.choices(active_keys, weights=weights, k=1)[0]
            selected_weight = weights[active_keys.index(selected)]
            logger.debug(
                f"🎯 Weighted key selection for {agent_type.value}: "
                f"key #{selected.index} (weight={selected_weight:.4f})"
            )
            self._emit_pool_telemetry(agent_type)
            return selected

    def mark_error(self, key: APIKey):
        """Отметить ошибку для ключа"""
        key.error_count += 1
        try:
            key.last_error_time = time.time()
        except Exception:
            # Graceful fallback if underlying key object doesn't define field
            key.last_error_time = time.time()
        self._update_health_state(key)
        if hasattr(key, "health") and key.health == APIKeyHealth.DISABLED:
            agent = getattr(key, "agent_type", "?")
            idx = getattr(key, "index", "?")
            logger.warning(f"⚠️ Disabled {agent} key #{idx} (error_count={key.error_count})")

    def mark_success(self, key: APIKey):
        """Отметить успешное использование"""
        key.last_used = time.time()
        key.requests_count += 1
        key.error_count = max(0, key.error_count - 1)
        if hasattr(key, "last_error_time") and key.error_count == 0:
            try:
                key.last_error_time = None
            except Exception as _e:
                logger.debug("Operation failed (expected): {}", _e)
        if hasattr(key, "cooldown_level") and hasattr(key, "is_cooling"):
            if key.cooldown_level > 0 and not key.is_cooling:
                key.cooldown_level = max(0, key.cooldown_level - 1)
        self._update_health_state(key)

    # The following helpers avoid disabling keys on transient network issues
    def mark_network_error(self, key: APIKey):
        """Учесть сетевую/временную ошибку без деактивации ключа"""
        key.error_count += 1
        key.last_error_time = time.time()
        self._update_health_state(key)

    def mark_rate_limit(self, key: APIKey, retry_after: float | None = None):
        """Учесть ограничение governor и отправить ключ на охлаждение"""
        key.error_count += 1
        key.last_error_time = time.time()
        self.pool_telemetry["rate_limit_events"] += 1
        self._update_health_state(key)
        cooldown = retry_after if (retry_after is not None and retry_after > 0) else None
        self._apply_cooldown(key, reason="rate_limit", duration=cooldown)

    def mark_client_error(self, key: APIKey):
        """Учесть ошибку клиента (4xx, кроме 401/403/429) без деактивации ключа"""
        key.error_count += 1
        key.last_error_time = time.time()
        self._update_health_state(key)

    def mark_auth_error(self, key: APIKey):
        """Немедленно деактивировать ключ при ошибке аутентификации"""
        key.error_count += 1
        key.last_error_time = time.time()
        key.health = APIKeyHealth.DISABLED
        logger.warning(f"⚠️ Disabled {key.agent_type.value} key #{key.index} due to auth error")

    def count_active(self, agent_type: AgentType) -> int:
        keys = self.deepseek_keys if agent_type == AgentType.DEEPSEEK else self.perplexity_keys
        return sum(1 for key in keys if key.is_usable)


# =============================================================================
# UNIFIED AGENT INTERFACE
# =============================================================================


class UnifiedAgentInterface:
    """
    Унифицированный интерфейс для AI агентов

    Features:
    - Автоматический fallback MCP → Direct API
    - Автоматическое переключение между API ключами
    - Health checks каждые 30s
    - Унифицированный формат запросов/ответов
    """

    def __init__(self, *, force_direct_api: bool | None = None):
        self.key_manager = APIKeyManager()
        self.key_manager.register_alert_callback(self._handle_pool_alert)
        self.mcp_disabled = MCP_DISABLED
        self.mcp_available = False
        self.last_health_check = 0
        self.health_check_interval = 30  # seconds
        base_force_direct = FORCE_DIRECT_AGENT_API or self.mcp_disabled
        self.force_direct_api = base_force_direct if force_direct_api is None else force_direct_api
        if self.mcp_disabled:
            self.force_direct_api = True
            logger.info("MCP bridge disabled via MCP_DISABLED flag; using direct API mode")

        # Phase 1: Circuit Breaker and Health Monitoring
        self.circuit_manager = get_circuit_manager()
        self.health_monitor = get_health_monitor()

        # Register circuit breakers for each component
        self._register_circuit_breakers()

        # Register health checks for each component
        self._register_health_checks()

        # Statistics
        self.stats = {
            "total_requests": 0,
            "mcp_success": 0,
            "mcp_failed": 0,
            "direct_api_success": 0,
            "direct_api_failed": 0,
            "circuit_breaker_trips": 0,  # Phase 1: Track circuit breaker opens
            "auto_recoveries": 0,  # Phase 1: Track successful auto-recoveries
            "mcp_breaker_rejections": 0,
            "rate_limit_events": 0,
            "deepseek_rate_limits": 0,
            "perplexity_rate_limits": 0,
            "key_pool_alerts": 0,
        }

        logger.info("🚀 Unified Agent Interface initialized")
        logger.info("🛡️ Circuit breakers registered: deepseek_api, perplexity_api, mcp_server")
        logger.info("🏥 Health monitoring ready (will start with event loop)")

        # Start background health monitoring - lazy initialization
        # Will be started when first request is made (in ensure_monitoring_started)
        self._monitoring_task: asyncio.Task | None = None

    def ensure_monitoring_started(self) -> None:
        """Start health monitoring if not already running (lazy initialization)"""
        if self._monitoring_task is None or self._monitoring_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._monitoring_task = loop.create_task(self.health_monitor.start_monitoring(30))
                logger.info("🏥 Health monitoring started (30s interval)")
            except RuntimeError:
                # No event loop running - will start on first request
                logger.debug("⏳ No event loop yet, monitoring will start on first request")

    def _register_circuit_breakers(self) -> None:
        """Register circuit breakers for all external dependencies"""
        # DeepSeek API
        self.circuit_manager.register_breaker(
            name="deepseek_api",
            fail_max=5,  # Open after 5 consecutive failures
            timeout_duration=60,  # Try recovery after 60 seconds
            expected_exception=Exception,
        )

        # Perplexity API
        self.circuit_manager.register_breaker(
            name="perplexity_api",
            fail_max=5,
            timeout_duration=60,
            expected_exception=Exception,
        )

        # MCP Server
        self.circuit_manager.register_breaker(
            name="mcp_server",
            fail_max=3,  # More sensitive for internal service
            timeout_duration=30,  # Faster recovery attempt
            expected_exception=Exception,
        )

    def _register_health_checks(self) -> None:
        """Register health checks for all components"""
        # DeepSeek API
        self.health_monitor.register_health_check(
            component="deepseek_api",
            health_check_func=self._check_deepseek_health,
            recovery_func=self._recover_deepseek,
        )

        # Perplexity API
        self.health_monitor.register_health_check(
            component="perplexity_api",
            health_check_func=self._check_perplexity_health,
            recovery_func=self._recover_perplexity,
        )

        # MCP Server
        self.health_monitor.register_health_check(
            component="mcp_server",
            health_check_func=self._check_mcp_health,
            recovery_func=self._recover_mcp,
        )

    def _handle_pool_alert(self, agent_type: AgentType, cooling: int, total: int) -> None:
        self.stats["key_pool_alerts"] += 1
        logger.error(f"🚨 Unified interface alert: {cooling}/{total} {agent_type.value} keys cooling simultaneously")

    def _record_rate_limit_event(self, agent_type: AgentType) -> None:
        self.stats["rate_limit_events"] += 1
        key = f"{agent_type.value}_rate_limits"
        self.stats[key] = self.stats.get(key, 0) + 1

    @staticmethod
    def _get_retry_after_seconds(response: httpx.Response) -> float | None:
        header = response.headers.get("Retry-After") if response else None
        if not header:
            return None
        try:
            return float(header)
        except ValueError:
            try:
                retry_dt = parsedate_to_datetime(header)
                if retry_dt.tzinfo is None:
                    retry_dt = retry_dt.replace(tzinfo=UTC)
                delta = retry_dt - datetime.now(UTC)
                return max(0.0, delta.total_seconds())
            except Exception:
                return None

    def get_key_pool_snapshot(self) -> dict[str, Any]:
        """Экспортировать текущие метрики пула ключей для мониторинга"""
        return {
            "deepseek": self.key_manager.get_pool_metrics(AgentType.DEEPSEEK),
            "perplexity": self.key_manager.get_pool_metrics(AgentType.PERPLEXITY),
            "telemetry": self.key_manager.pool_telemetry.copy(),
        }

    async def _check_deepseek_health(self) -> HealthCheckResult:
        """Health check for DeepSeek API"""
        active_keys = sum(1 for k in self.key_manager.deepseek_keys if k.is_usable)
        total_keys = len(self.key_manager.deepseek_keys)

        if active_keys == 0:
            return HealthCheckResult(
                component="deepseek_api",
                status=HealthStatus.UNHEALTHY,
                message=f"No active DeepSeek keys (0/{total_keys})",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS,
            )
        elif active_keys < total_keys * 0.5:
            return HealthCheckResult(
                component="deepseek_api",
                status=HealthStatus.DEGRADED,
                message=f"Only {active_keys}/{total_keys} DeepSeek keys active",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS,
            )
        else:
            return HealthCheckResult(
                component="deepseek_api",
                status=HealthStatus.HEALTHY,
                message=f"DeepSeek API healthy ({active_keys}/{total_keys} keys active)",
                details={"active_keys": active_keys, "total_keys": total_keys},
            )

    async def _check_perplexity_health(self) -> HealthCheckResult:
        """Health check for Perplexity API"""
        active_keys = sum(1 for k in self.key_manager.perplexity_keys if k.is_usable)
        total_keys = len(self.key_manager.perplexity_keys)

        if active_keys == 0:
            return HealthCheckResult(
                component="perplexity_api",
                status=HealthStatus.UNHEALTHY,
                message=f"No active Perplexity keys (0/{total_keys})",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS,
            )
        elif active_keys < total_keys * 0.5:
            return HealthCheckResult(
                component="perplexity_api",
                status=HealthStatus.DEGRADED,
                message=f"Only {active_keys}/{total_keys} Perplexity keys active",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS,
            )
        else:
            return HealthCheckResult(
                component="perplexity_api",
                status=HealthStatus.HEALTHY,
                message=f"Perplexity API healthy ({active_keys}/{total_keys} keys active)",
                details={"active_keys": active_keys, "total_keys": total_keys},
            )

    async def _check_mcp_health(self) -> HealthCheckResult:
        """Health check for MCP Server"""
        if self.mcp_disabled:
            return HealthCheckResult(
                component="mcp_server",
                status=HealthStatus.DECOMMISSIONED,
                message="MCP disabled via MCP_DISABLED flag",
                details={"disabled": True},
            )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("http://127.0.0.1:8000/mcp/health")
                if resp.status_code == 200:
                    data = resp.json()
                    tool_count = data.get("tool_count", 0)
                    if tool_count >= 1:
                        return HealthCheckResult(
                            component="mcp_server",
                            status=HealthStatus.HEALTHY,
                            message=f"MCP Server healthy ({tool_count} tools)",
                            details=data,
                        )
                    else:
                        return HealthCheckResult(
                            component="mcp_server",
                            status=HealthStatus.DEGRADED,
                            message="MCP Server running but no tools available",
                            details=data,
                            recovery_suggested=RecoveryActionType.FORCE_HEALTH_CHECK,
                        )
        except Exception as e:
            return HealthCheckResult(
                component="mcp_server",
                status=HealthStatus.UNHEALTHY,
                message=f"MCP Server unreachable: {e!s}",
                details={"error": str(e)},
                recovery_suggested=RecoveryActionType.FORCE_HEALTH_CHECK,
            )

    async def _test_key_health(self, agent_type: AgentType, key: APIKey) -> bool:
        """Minimal live request to verify that a key recovered."""
        url = self._get_api_url(agent_type)
        headers = self._get_headers(key)
        payload = {
            "model": "deepseek-chat" if agent_type == AgentType.DEEPSEEK else "sonar-pro",
            "messages": [
                {"role": "system", "content": "Health check ping"},
                {"role": "user", "content": "ping"},
            ],
            "max_tokens": 5,
            "temperature": 0.0,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                return True
            if response.status_code in (401, 403):
                self.key_manager.mark_auth_error(key)
            elif response.status_code == 429:
                retry_after = self._get_retry_after_seconds(response)
                self.key_manager.mark_rate_limit(key, retry_after=retry_after)
                self._record_rate_limit_event(agent_type)
            else:
                self.key_manager.mark_error(key)
        except TimeoutError:
            self.key_manager.mark_network_error(key)
        except httpx.HTTPError:
            self.key_manager.mark_network_error(key)
        except Exception:
            self.key_manager.mark_error(key)
        return False

    async def _recover_deepseek(self, action_type: RecoveryActionType) -> None:
        """Recovery action for DeepSeek API"""
        if action_type == RecoveryActionType.RESET_ERRORS:
            recovered = 0
            for key in self.key_manager.deepseek_keys:
                if not key.is_usable:
                    is_healthy = await self._test_key_health(AgentType.DEEPSEEK, key)
                    if is_healthy:
                        key.error_count = 1
                        key.health = APIKeyHealth.DEGRADED
                        key.last_error_time = None
                        recovered += 1
                        logger.info(f"✅ Validated DeepSeek key #{key.index} (re-enabled in DEGRADED state)")
                    else:
                        logger.warning(f"❌ DeepSeek key #{key.index} failed validation, remains disabled")
            if recovered:
                self.stats["auto_recoveries"] += recovered
        elif action_type == RecoveryActionType.RESET_CIRCUIT_BREAKER:
            self.circuit_manager.reset_breaker("deepseek_api")
            self.stats["auto_recoveries"] += 1

    async def _recover_perplexity(self, action_type: RecoveryActionType) -> None:
        """Recovery action for Perplexity API"""
        if action_type == RecoveryActionType.RESET_ERRORS:
            recovered = 0
            for key in self.key_manager.perplexity_keys:
                if not key.is_usable:
                    is_healthy = await self._test_key_health(AgentType.PERPLEXITY, key)
                    if is_healthy:
                        key.error_count = 1
                        key.health = APIKeyHealth.DEGRADED
                        key.last_error_time = None
                        recovered += 1
                        logger.info(f"✅ Validated Perplexity key #{key.index} (re-enabled in DEGRADED state)")
                    else:
                        logger.warning(f"❌ Perplexity key #{key.index} failed validation, remains disabled")
            if recovered:
                self.stats["auto_recoveries"] += recovered
        elif action_type == RecoveryActionType.RESET_CIRCUIT_BREAKER:
            self.circuit_manager.reset_breaker("perplexity_api")
            self.stats["auto_recoveries"] += 1

    async def _recover_mcp(self, action_type: RecoveryActionType) -> None:
        """Recovery action for MCP Server"""
        if self.mcp_disabled:
            logger.debug("MCP recovery skipped because MCP_DISABLED flag is set")
            return
        if action_type == RecoveryActionType.FORCE_HEALTH_CHECK:
            # Force a health check to update mcp_available status
            await self._health_check()
            self.stats["auto_recoveries"] += 1
        elif action_type == RecoveryActionType.RESET_CIRCUIT_BREAKER:
            self.circuit_manager.reset_breaker("mcp_server")
            self.stats["auto_recoveries"] += 1

    async def send_request(
        self,
        request: AgentRequest,
        preferred_channel: AgentChannel = AgentChannel.MCP_SERVER,
    ) -> AgentResponse:
        """
        Отправить запрос к агенту (с автоматическим fallback)

        Flow:
        1. Try MCP Server (if preferred and available)
        2. Fallback to Direct API (if MCP fails)
        3. Try backup API keys (if primary fails)
        4. Return error (if all channels fail)

        New: Records metrics for monitoring (response time, success rate, tool calling)
        """
        # Ensure health monitoring is started (lazy initialization)
        self.ensure_monitoring_started()

        start_time = time.time()
        self.stats["total_requests"] += 1

        # Import metrics collector (lazy import to avoid circular dependency)
        try:
            from backend.monitoring.agent_metrics import record_agent_call

            metrics_enabled = True
        except ImportError:
            metrics_enabled = False
            logger.warning("⚠️ Metrics module not available")

        # Health check if needed
        if time.time() - self.last_health_check > self.health_check_interval:
            asyncio.create_task(self._health_check())

        if (self.force_direct_api or self.mcp_disabled) and preferred_channel == AgentChannel.MCP_SERVER:
            reason = "MCP_DISABLED flag" if self.mcp_disabled else "FORCE_DIRECT_AGENT_API flag"
            logger.info(f"🚫 MCP channel bypassed ({reason}); using direct API")
            preferred_channel = AgentChannel.DIRECT_API

        # Try MCP Server first
        if preferred_channel == AgentChannel.MCP_SERVER and self.mcp_available:
            try:
                response = await self._try_mcp(request)
                if response.success:
                    self.stats["mcp_success"] += 1
                    return response
                else:
                    self.stats["mcp_failed"] += 1
                    logger.warning(f"⚠️ MCP failed, falling back to Direct API: {response.error}")
            except Exception as e:
                self.stats["mcp_failed"] += 1
                logger.warning(f"⚠️ MCP exception, falling back: {e}")

        # Fallback to Direct API
        try:
            response = await self._try_direct_api(request)
            if response.success:
                self.stats["direct_api_success"] += 1
                return response
            else:
                self.stats["direct_api_failed"] += 1
        except Exception as e:
            self.stats["direct_api_failed"] += 1
            logger.error(f"❌ Direct API failed: {e}")

        # All channels failed
        latency = (time.time() - start_time) * 1000

        # Record failed metrics
        if metrics_enabled:
            try:
                await record_agent_call(
                    agent_name=request.agent_type.value,
                    response_time_ms=latency,
                    success=False,
                    error="All communication channels failed",
                    context=request.context,
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to record metrics: {e}")

        # Task 12: Enqueue to DLQ for retry
        try:
            from backend.agents.dead_letter_queue import (
                DLQMessage,
                DLQPriority,
                get_dlq,
            )
            from backend.middleware.correlation_id import get_correlation_id

            dlq = get_dlq()
            dlq_message = DLQMessage(
                message_id=str(uuid.uuid4()),
                agent_type=request.agent_type.value,
                content=request.prompt,
                context=request.context,
                error="All communication channels failed",
                priority=DLQPriority.HIGH if request.context.get("critical", False) else DLQPriority.NORMAL,
                correlation_id=get_correlation_id(),
            )

            enqueued = await dlq.enqueue(dlq_message)
            if enqueued:
                logger.info(f"📬 Message enqueued to DLQ: {dlq_message.message_id}")
        except Exception as e:
            logger.error(f"❌ Failed to enqueue to DLQ: {e}")

        # Phase 5: Try FallbackService for graceful degradation
        try:
            from backend.services.fallback_service import (
                FallbackType,
                get_fallback_service,
            )

            fallback_service = get_fallback_service()
            fallback_response = fallback_service.get_fallback(
                prompt=request.prompt,
                agent_type=request.agent_type.value,
                task_type=request.context.get("task_type"),
            )

            if fallback_response:
                logger.info(f"🔄 FallbackService provided response: {fallback_response.fallback_type.value}")
                return AgentResponse(
                    success=True,
                    content=fallback_response.content,
                    channel=AgentChannel.DIRECT_API,
                    latency_ms=latency,
                    metadata={
                        "fallback": True,
                        "fallback_type": fallback_response.fallback_type.value,
                        "is_cached": fallback_response.fallback_type == FallbackType.CACHED,
                        "degraded_mode": fallback_response.fallback_type == FallbackType.DEGRADED,
                        **fallback_response.metadata,
                    },
                )
        except Exception as e:
            logger.debug(f"⚠️ FallbackService unavailable: {e}")

        return AgentResponse(
            success=False,
            content="",
            channel=AgentChannel.DIRECT_API,
            latency_ms=latency,
            error="All communication channels failed",
        )

    async def _try_mcp(self, request: AgentRequest) -> AgentResponse:
        """
        Попытка через MCP Server (internal bridge)

        Phase 1: Wrapped with circuit breaker for automatic failure isolation
        """
        start_time = time.time()
        if self.mcp_disabled:
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.MCP_SERVER,
                latency_ms=(time.time() - start_time) * 1000,
                error="MCP disabled via MCP_DISABLED flag",
            )

        # Wrap MCP call with circuit breaker
        try:
            return await self.circuit_manager.call_with_breaker(
                "mcp_server", self._execute_mcp_call, request, start_time
            )

        except CircuitBreakerError as e:
            # Circuit breaker is open
            self.stats["circuit_breaker_trips"] += 1
            logger.warning(f"⚠️ MCP circuit breaker OPEN: {e}")

            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.MCP_SERVER,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"MCP circuit breaker open: {e!s}",
            )

    async def _execute_mcp_call(self, request: AgentRequest, start_time: float) -> AgentResponse:
        """
        Internal method for actual MCP call execution (called by circuit breaker)
        """

        try:
            # Task 8: Use internal MCP bridge instead of HTTP loopback
            from backend.mcp.mcp_integration import get_mcp_bridge

            # Task 10: Propagate correlation ID
            try:
                from backend.middleware.correlation_id import get_correlation_id

                correlation_id = get_correlation_id()
                if correlation_id:
                    request.context["correlation_id"] = correlation_id
                    logger.debug(f"Propagating correlation_id={correlation_id} to MCP tool")
            except ImportError:
                pass  # Middleware not available

            bridge = get_mcp_bridge()
            await bridge.initialize()

            # Determine which MCP tool to call based on agent type
            if request.agent_type == AgentType.DEEPSEEK:
                tool_name = "mcp_agent_to_agent_send_to_deepseek"
            else:  # PERPLEXITY
                tool_name = "mcp_agent_to_agent_send_to_perplexity"

            # Call tool via bridge (no network hop)
            result = await bridge.call_tool(
                name=tool_name,
                arguments={"content": request.prompt, "context": request.context},
            )

            if result.get("success"):
                return AgentResponse(
                    success=True,
                    content=result.get("content", ""),
                    channel=AgentChannel.MCP_SERVER,
                    latency_ms=(time.time() - start_time) * 1000,
                )
            else:
                return AgentResponse(
                    success=False,
                    content="",
                    channel=AgentChannel.MCP_SERVER,
                    latency_ms=(time.time() - start_time) * 1000,
                    error=result.get("error", "MCP tool execution failed"),
                )

        except Exception as e:
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.MCP_SERVER,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"MCP bridge error: {e!s}",
            )

    async def _try_direct_api(self, request: AgentRequest) -> AgentResponse:
        """
        Попытка через Direct API (с поддержкой tool calling и circuit breaker)

        Phase 1: Wrapped with circuit breaker for automatic failure isolation

        Improvements (based on agent self-improvement analysis):
        - Exponential backoff для retry (3 попытки)
        - Увеличенный timeout для complex tasks (300 сек)
        - Детальное логирование каждой попытки
        - Circuit breaker защита от cascading failures
        """
        start_time = time.time()

        # Determine circuit breaker name
        breaker_name = "deepseek_api" if request.agent_type == AgentType.DEEPSEEK else "perplexity_api"

        # Wrap API call with circuit breaker
        try:
            response = await self.circuit_manager.call_with_breaker(
                breaker_name, self._execute_api_call, request, start_time
            )
            return response

        except CircuitBreakerError as e:
            # Circuit breaker is open, track and return error
            self.stats["circuit_breaker_trips"] += 1
            logger.error(f"⚠️ Circuit breaker '{breaker_name}' is OPEN: {e}")

            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.DIRECT_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"Circuit breaker open: {e!s}",
            )

    async def _execute_api_call(self, request: AgentRequest, start_time: float) -> AgentResponse:
        """
        Internal method for actual API call execution (called by circuit breaker)

        This is the actual implementation that was in _try_direct_api before.
        Now wrapped by circuit breaker for automatic failure isolation.
        """

        # Task 10: Propagate correlation ID for distributed tracing
        try:
            from backend.middleware.correlation_id import get_correlation_id

            correlation_id = get_correlation_id()
            if correlation_id:
                request.context["correlation_id"] = correlation_id
                logger.debug(f"Direct API call with correlation_id={correlation_id}")
        except ImportError:
            pass  # Middleware not available

        # Get active API key
        key = await self.key_manager.get_active_key(request.agent_type)
        if not key:
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.DIRECT_API,
                error=f"No active {request.agent_type.value} API keys",
            )

        # Determine timeout based on task complexity
        is_complex_task = (
            request.context.get("use_file_access", False)
            or request.context.get("complex_task", False)
            or request.context.get("self_improvement_analysis", False)
        )
        timeout = 600.0 if is_complex_task else 120.0  # 10 min for complex, 2 min for standard

        logger.info(f"⏱️ Using timeout: {timeout}s ({'complex' if is_complex_task else 'standard'} task)")

        # Retry configuration
        MAX_RETRIES = 3
        retry_attempt = 0
        last_exception = None
        first_error = None  # ✅ FIX: Track first error to avoid misleading logs

        while retry_attempt < MAX_RETRIES:
            retry_attempt += 1

            if retry_attempt > 1:
                # Exponential backoff: 2^(attempt-1) seconds
                backoff_delay = 2 ** (retry_attempt - 1)
                logger.warning(f"🔄 Retry attempt {retry_attempt}/{MAX_RETRIES} after {backoff_delay}s backoff")
                await asyncio.sleep(backoff_delay)

            # Make API request with tool calling loop
            try:
                url = self._get_api_url(request.agent_type, strict_mode=request.strict_mode)
                logger.debug(f"🌐 URL for {request.agent_type.value}: {url} (strict={request.strict_mode})")
                headers = self._get_headers(key)

                # Store the original payload with tools - IMPORTANT: Keep tools in all iterations
                original_payload = request.to_direct_api_format(include_tools=True)
                messages = original_payload["messages"].copy()
                max_iterations = 5  # Prevent infinite loops

                # ✅ QUICK WIN #1: Tool Call Budget Counter
                # Import from base_config (configured via env var TOOL_CALL_BUDGET)
                from backend.agents.base_config import TOOL_CALL_BUDGET

                tool_call_budget = TOOL_CALL_BUDGET
                total_tool_calls = 0

                iteration = 0

                async with httpx.AsyncClient(timeout=timeout) as client:
                    while iteration < max_iterations:
                        iteration += 1

                        # Create payload for this iteration - ALWAYS include tools from original
                        payload = original_payload.copy()
                        payload["messages"] = messages

                        response = await client.post(url, json=payload, headers=headers)
                        response.raise_for_status()

                    data = response.json()
                    logger.debug(f"   API response keys: {list(data.keys())}")
                    logger.debug(f"   Response data: {json.dumps(data, indent=2)[:500]}...")

                    # Check if agent wants to call tools (DeepSeek only)
                    if request.agent_type == AgentType.DEEPSEEK:
                        message = data.get("choices", [{}])[0].get("message", {})
                        logger.debug(f"   Message keys: {list(message.keys())}")
                        tool_calls = message.get("tool_calls")
                        logger.debug(f"   Tool calls: {tool_calls}")

                        if tool_calls:
                            logger.info(f"🔧 Agent requested {len(tool_calls)} tool calls (iteration {iteration})")

                            # ✅ QUICK WIN #1: Check tool call budget
                            # Protection against runaway loops and cascading timeouts
                            if total_tool_calls + len(tool_calls) > tool_call_budget:
                                budget_used = total_tool_calls + len(tool_calls)
                                logger.warning(f"⚠️ Tool call budget exceeded: {budget_used} > {tool_call_budget}")
                                # Graceful degradation: ask agent to provide final analysis without tools
                                messages.append(
                                    {
                                        "role": "system",
                                        "content": (
                                            f"Tool call budget exceeded ({tool_call_budget} calls). "
                                            "Please provide final analysis without additional tool calls."
                                        ),
                                    }
                                )
                                # Continue to get final response without executing tools
                                continue

                            # Add assistant message with tool calls
                            # V3.2: Clear reasoning_content from previous messages to save bandwidth
                            self._clear_reasoning_in_messages(messages)
                            messages.append(message)

                            # Execute each tool call with retry
                            for tool_call in tool_calls:
                                tool_result = await self._execute_tool_with_retry(tool_call, max_retries=3)

                                # ✅ QUICK WIN #1: Track total tool calls
                                total_tool_calls += 1
                                tool_name = tool_call.get("function", {}).get("name", "unknown")
                                logger.debug(
                                    f"   Tool call #{total_tool_calls}/{tool_call_budget} completed: {tool_name}"
                                )

                                # Format tool result for DeepSeek
                                # If successful, return the actual content/data
                                # If failed, return error message
                                if tool_result.get("success"):
                                    # Extract the actual data from the result
                                    if "content" in tool_result:
                                        result_content = str(tool_result["content"])
                                    elif "structure" in tool_result:
                                        result_content = json.dumps(tool_result["structure"], indent=2)
                                    elif "report" in tool_result:
                                        result_content = tool_result["report"]
                                    else:
                                        result_content = json.dumps(tool_result, indent=2)
                                else:
                                    result_content = f"Error: {tool_result.get('error', 'Unknown error')}"

                                logger.debug(f"   Tool result length: {len(result_content)} chars")

                                # Add tool result to messages
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_call.get("id"),
                                        "name": tool_name,
                                        "content": result_content,
                                    }
                                )

                            # Continue loop to get agent's final response
                            continue

                    # No more tool calls - extract final content
                    logger.debug(f"🔍 Extracting content from API response. Keys: {list(data.keys())}")
                    content = self._extract_content(data, request.agent_type)

                    # Extract reasoning_content for DeepSeek Thinking Mode
                    reasoning_content = None
                    if request.agent_type == AgentType.DEEPSEEK and request.thinking_mode:
                        reasoning_content = self._extract_reasoning_content(data)
                        if reasoning_content:
                            logger.info(f"🧠 Thinking Mode CoT extracted: {len(reasoning_content)} chars")

                    # Extract token usage from response
                    token_usage = self._extract_token_usage(data, request.agent_type)

                    if not content or not content.strip():
                        logger.warning(f"⚠️ Empty content extracted from {request.agent_type.value} response!")
                        logger.debug(f"🔍 Raw response data: {json.dumps(data, indent=2)[:1000]}")
                    else:
                        logger.debug(f"✅ Content extracted: {content[:100]}...")

                    self.key_manager.mark_success(key)

                    latency = (time.time() - start_time) * 1000
                    logger.info(f"✅ Agent completed in {iteration} iterations ({latency:.0f}ms)")
                    logger.info(f"   Tool calls used: {total_tool_calls}/{tool_call_budget}")
                    logger.info(f"🔍 DEBUG: metrics_enabled={metrics_enabled}")

                    # Record success metrics
                    if metrics_enabled:
                        logger.info(f"📊 About to record metrics for {request.agent_type.value}")
                        try:
                            await record_agent_call(
                                agent_name=request.agent_type.value,
                                response_time_ms=latency,
                                success=True,
                                tool_calls=total_tool_calls,  # ✅ QUICK WIN #1: Use actual tool call count
                                iterations=iteration,
                                context=request.context,
                            )
                        except Exception as e:
                            logger.error(
                                f"❌ Failed to record success metrics: {e}",
                                exc_info=True,
                            )
                    else:
                        logger.warning("⚠️ Metrics disabled - skipping recording")

                    # Record cost for dashboard tracking
                    if token_usage and token_usage.cost_usd:
                        try:
                            from backend.monitoring.cost_tracker import record_api_cost

                            record_api_cost(
                                agent=request.agent_type.value,
                                model=payload.get("model", "unknown"),
                                prompt_tokens=token_usage.prompt_tokens,
                                completion_tokens=token_usage.completion_tokens,
                                total_tokens=token_usage.total_tokens,
                                reasoning_tokens=token_usage.reasoning_tokens,
                                cost_usd=token_usage.cost_usd,
                                session_id=request.context.get("session_id"),
                                task_type=request.task_type,
                            )
                        except Exception as e:
                            logger.debug(f"Cost tracking failed: {e}")

                    return AgentResponse(
                        success=True,
                        content=content,
                        channel=AgentChannel.DIRECT_API,
                        api_key_index=key.index,
                        latency_ms=latency,
                        reasoning_content=reasoning_content,  # DeepSeek V3.2 Thinking Mode
                        tokens_used=token_usage,  # Token usage tracking
                        citations=self._extract_citations(data, request.agent_type),  # Perplexity sources
                    )

                # Max iterations reached
                logger.warning(f"⚠️ Max iterations ({max_iterations}) reached for tool calling")
                logger.info(f"   Total tool calls executed: {total_tool_calls}/{tool_call_budget}")
                return AgentResponse(
                    success=False,
                    content="",
                    channel=AgentChannel.DIRECT_API,
                    latency_ms=(time.time() - start_time) * 1000,
                    error=f"Max tool calling iterations ({max_iterations}) reached",
                )

            except httpx.TimeoutException as e:
                last_exception = e
                if not first_error:
                    first_error = f"Timeout ({timeout}s) on {request.agent_type.value}"
                # Timeouts are typically transient; do not disable key
                self.key_manager.mark_network_error(key)
                logger.error(f"❌ Timeout on attempt {retry_attempt}/{MAX_RETRIES}: {timeout}s exceeded")
                # Continue to next retry iteration
                continue

            except httpx.HTTPStatusError as e:
                last_exception = e
                if not first_error:
                    status = e.response.status_code
                    text = e.response.text[:100]
                    first_error = f"HTTP {status} on {request.agent_type.value}: {text}"
                logger.error(
                    f"❌ HTTP error {e.response.status_code} on attempt {retry_attempt}/{MAX_RETRIES}: "
                    f"{e.response.text[:200]}"
                )

                status = e.response.status_code
                if status in (401, 403):
                    # Auth error: disable this key immediately
                    self.key_manager.mark_auth_error(key)
                    logger.error("❌ Auth error, disabling key and not retrying")
                    break
                elif status == 429:
                    retry_after = self._get_retry_after_seconds(e.response)
                    self.key_manager.mark_rate_limit(key, retry_after=retry_after)
                    self._record_rate_limit_event(request.agent_type)
                    continue
                elif 500 <= status < 600:
                    # Server errors: transient
                    self.key_manager.mark_network_error(key)
                    # Continue to next retry iteration for 5xx
                    continue
                elif 400 <= status < 500:
                    # Other client errors: don't disable key
                    self.key_manager.mark_client_error(key)
                    logger.error(f"❌ Client error {status}, not retrying")
                    break

            except Exception as e:
                last_exception = e
                if not first_error:
                    first_error = f"{type(e).__name__} on {request.agent_type.value}: {str(e)[:100]}"
                # Generic connectivity errors (e.g., DNS getaddrinfo) should not disable keys
                self.key_manager.mark_network_error(key)
                logger.error(f"❌ Request failed on attempt {retry_attempt}/{MAX_RETRIES}: {e}")
                # Continue to next retry iteration
                continue

        # All retries exhausted - try backup key
        logger.error(
            f"❌ All {MAX_RETRIES} retry attempts failed. "
            f"FIRST error: {first_error or 'Unknown'} | LAST error: {last_exception}"
        )
        return await self._try_backup_key(request, start_time)

    async def _try_backup_key(self, request: AgentRequest, start_time: float) -> AgentResponse:
        """Попытка с backup API ключом"""
        key = await self.key_manager.get_active_key(request.agent_type)
        if not key:
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.BACKUP_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"No backup {request.agent_type.value} keys available",  # ✅ FIX: Specific error message
            )

        # ✅ FIX: Validate key type matches request
        if key.agent_type != request.agent_type:
            logger.error(f"❌ KEY TYPE MISMATCH: {key.agent_type.value} key for {request.agent_type.value} request")
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.BACKUP_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"Key type mismatch: {key.agent_type.value} != {request.agent_type.value}",
            )

        logger.info(f"🔄 Trying backup {request.agent_type.value} key #{key.index}")

        try:
            url = self._get_api_url(request.agent_type)
            headers = self._get_headers(key)
            payload = request.to_direct_api_format(include_tools=False)  # No tools for backup

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

                data = response.json()
                content = self._extract_content(data, request.agent_type)

                self.key_manager.mark_success(key)

                return AgentResponse(
                    success=True,
                    content=content,
                    channel=AgentChannel.BACKUP_API,
                    api_key_index=key.index,
                    latency_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            self.key_manager.mark_error(key)
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.BACKUP_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"Backup API also failed: {e!s}",
            )

    async def _execute_tool_with_retry(self, tool_call: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
        """
        Execute MCP tool call with exponential backoff retry.

        Args:
            tool_call: Tool call from DeepSeek API
            max_retries: Maximum number of retry attempts

        Returns:
            Tool result dict with success/error
        """
        import asyncio

        function_name = tool_call.get("function", {}).get("name", "unknown")
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = await self._execute_mcp_tool(tool_call)

                # Check if result is successful or is a known/expected error
                if result.get("success"):
                    if attempt > 0:
                        logger.info(f"🔄 Tool {function_name} succeeded on attempt {attempt + 1}")
                    return result

                # Check if error is retryable
                error_msg = result.get("error", "")
                retryable_errors = [
                    "timeout",
                    "connection",
                    "rate limit",
                    "temporary",
                    "503",
                    "502",
                    "500",
                ]
                is_retryable = any(err.lower() in error_msg.lower() for err in retryable_errors)

                if not is_retryable or attempt >= max_retries:
                    # Non-retryable error or max retries reached
                    return result

                last_error = error_msg

            except Exception as e:
                last_error = str(e)
                if attempt >= max_retries:
                    logger.error(f"❌ Tool {function_name} failed after {max_retries + 1} attempts: {e}")
                    return {
                        "success": False,
                        "error": f"Tool failed after {max_retries + 1} attempts: {last_error}",
                    }

            # Exponential backoff: 1s, 2s, 4s
            delay = 2**attempt
            logger.warning(
                f"⏳ Tool {function_name} failed (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay}s... Error: {last_error}"
            )
            await asyncio.sleep(delay)

        return {
            "success": False,
            "error": f"Tool failed after {max_retries + 1} attempts: {last_error}",
        }

    async def _execute_mcp_tool(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """
        Выполнить MCP tool call

        Args:
            tool_call: Tool call от DeepSeek API
                {
                    "id": "call_xyz",
                    "type": "function",
                    "function": {
                        "name": "mcp_read_project_file",
                        "arguments": "{\"file_path\": \"backend/api/app.py\"}"
                    }
                }

        Returns:
            Tool result dict
        """
        function_name = None
        try:
            function_name = tool_call.get("function", {}).get("name")
            arguments_str = tool_call.get("function", {}).get("arguments", "{}")

            logger.info(f"🔧 Executing tool: {function_name}")
            logger.debug(f"   Arguments (raw): {arguments_str}")

            # Parse arguments
            if isinstance(arguments_str, str):
                try:
                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to parse tool arguments: {e}")
                    logger.error(f"   Raw arguments: {arguments_str}")
                    return {
                        "success": False,
                        "error": f"Invalid tool arguments JSON: {e!s}",
                    }
            else:
                arguments = arguments_str

            logger.debug(f"   Arguments (parsed): {arguments}")

            # ------------------------------------------------------------------
            # AUTONOMOUS MODE: If MCP is disabled, emulate critical tools locally
            # ------------------------------------------------------------------
            if self.mcp_disabled:
                logger.debug("🧩 MCP disabled: executing tool via local emulation layer")
                return await self._execute_local_tool(function_name, arguments)

            # Normal path: import real MCP tool implementations
            try:
                from backend.api.app import (
                    mcp_analyze_code_quality,
                    mcp_list_project_structure,
                    mcp_read_project_file,
                )

                logger.debug("✅ MCP tools imported successfully")
            except ImportError as e:
                logger.error(f"❌ Failed to import MCP tools: {e}")
                return {
                    "success": False,
                    "error": f"Failed to import MCP tools: {e!s}",
                }

            tool_map = {
                "mcp_read_project_file": mcp_read_project_file,
                "mcp_list_project_structure": mcp_list_project_structure,
                "mcp_analyze_code_quality": mcp_analyze_code_quality,
            }

            if function_name not in tool_map:
                logger.error(f"❌ Unknown tool: {function_name}")
                logger.error(f"   Available tools: {list(tool_map.keys())}")
                return {"success": False, "error": f"Unknown tool: {function_name}"}

            tool_func = tool_map[function_name]
            logger.debug(f"   Calling {function_name} with arguments: {arguments}")
            logger.debug(f"   Tool function type: {type(tool_func)}")

            try:
                result = await tool_func(**arguments)
            except TypeError as e:
                if "'FunctionTool' object is not callable" in str(e) or "not callable" in str(e):
                    logger.warning("   Tool is wrapped, trying .fn attribute")
                    actual_func = getattr(tool_func, "fn", None)
                    if actual_func:
                        result = await actual_func(**arguments)
                    else:
                        raise
                else:
                    raise

            logger.info(f"✅ Tool executed: {function_name} -> success={result.get('success')}")
            if not result.get("success"):
                logger.warning(f"   Tool returned error: {result.get('error')}")
            return result

        except Exception as e:
            logger.error(f"❌ Tool execution failed for {function_name}: {e}")
            logger.error(f"   Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            return {"success": False, "error": f"Tool execution error: {e!s}"}

    async def _execute_local_tool(self, function_name: str | None, arguments: dict[str, Any]) -> dict[str, Any]:
        """Local emulation for MCP tools when autonomy mode disables MCP bridge.

        🔐 SECURITY: Implements path traversal protection per consensus proposal (99% approval).
        """
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent.parent  # points to project root

        if not function_name:
            return {"success": False, "error": "No tool name provided"}

        if function_name == "mcp_read_project_file":
            rel_path = arguments.get("file_path", "")
            max_size_kb = int(arguments.get("max_size_kb", 100))
            if not rel_path:
                return {"success": False, "error": "file_path required"}

            # 🔐 SECURITY PATCH #1: Path traversal protection (CRITICAL)
            # Normalize path separators
            rel_path = Path(rel_path).as_posix()

            # Block parent directory references and absolute paths
            if ".." in rel_path or rel_path.startswith("/"):
                logger.warning(f"🚫 Path traversal attempt blocked: {rel_path}")
                return {
                    "success": False,
                    "error": "Path traversal blocked: '..' and absolute paths not allowed",
                }

            # Resolve full path and validate it's within project
            target = (project_root / rel_path).resolve()
            if not target.is_relative_to(project_root):
                logger.warning(f"🚫 Access outside project blocked: {target}")
                return {
                    "success": False,
                    "error": "Access outside project directory denied",
                }

            # Block sensitive files
            blocked_patterns = [
                ".env",
                ".git",
                "secrets",
                "*.key",
                "*.pem",
                "id_rsa",
                "*.crt",
            ]
            if any(target.match(pattern) for pattern in blocked_patterns):
                logger.warning(f"🚫 Access to sensitive file blocked: {target.name}")
                return {
                    "success": False,
                    "error": f"Access to sensitive file '{target.name}' denied",
                }

            if not target.exists() or not target.is_file():
                return {"success": False, "error": f"File not found: {rel_path}"}
            try:
                size_kb = target.stat().st_size / 1024.0
                if size_kb > max_size_kb:
                    return {
                        "success": False,
                        "error": f"File too large ({size_kb:.1f}KB > {max_size_kb}KB)",
                    }
                text = target.read_text(encoding="utf-8", errors="ignore")
                return {
                    "success": True,
                    "file_path": rel_path,
                    "content": text,
                    "size_kb": round(size_kb, 2),
                    "source": "local_emulation",
                }
            except Exception as e:
                return {"success": False, "error": f"Read error: {e}"}

        if function_name == "mcp_list_project_structure":
            directory = arguments.get("directory", ".")
            max_depth = int(arguments.get("max_depth", 3))
            include_hidden = bool(arguments.get("include_hidden", False))
            base = (project_root / directory).resolve()
            if not base.exists() or not base.is_dir():
                return {"success": False, "error": f"Directory not found: {directory}"}

            # 🔐 SECURITY PATCH #2: Resource exhaustion protection (MEDIUM)
            MAX_ENTRIES_PER_DIR = 1000
            MAX_TOTAL_FILES = 10000
            file_count = [0]  # Mutable counter for recursive tracking
            truncation_markers = []  # Track truncation events for result

            tree = {}

            def walk(path: Path, depth: int):
                if depth > max_depth or file_count[0] > MAX_TOTAL_FILES:
                    return None
                entries = []
                for idx, child in enumerate(sorted(path.iterdir())):
                    # Cap entries per directory to prevent DoS
                    if idx >= MAX_ENTRIES_PER_DIR:
                        entries.append(
                            {
                                "type": "truncated",
                                "message": f"Truncated (>{MAX_ENTRIES_PER_DIR} entries)",
                            }
                        )
                        logger.warning(f"⚠️ Directory {path} truncated at {MAX_ENTRIES_PER_DIR} entries")
                        truncation_markers.append(
                            f"Directory '{path.relative_to(base)}' truncated at {MAX_ENTRIES_PER_DIR} entries"
                        )
                        break

                    name = child.name
                    if not include_hidden and name.startswith("."):
                        continue
                    if name in {".git", "__pycache__", "node_modules"}:
                        continue

                    file_count[0] += 1
                    if file_count[0] > MAX_TOTAL_FILES:
                        entries.append(
                            {
                                "type": "truncated",
                                "message": f"Max total files reached ({MAX_TOTAL_FILES})",
                            }
                        )
                        logger.warning(f"⚠️ Total file count exceeded {MAX_TOTAL_FILES}")
                        truncation_markers.append(f"Max total files reached ({MAX_TOTAL_FILES})")
                        break

                    if child.is_dir():
                        entries.append(
                            {
                                "type": "dir",
                                "name": name,
                                "children": walk(child, depth + 1),
                            }
                        )
                    else:
                        entries.append({"type": "file", "name": name, "size": child.stat().st_size})
                return entries

            tree[directory] = walk(base, 0)
            result = {
                "success": True,
                "structure": tree,
                "source": "local_emulation",
                "files_scanned": file_count[0],
            }
            if truncation_markers:
                result["truncation_info"] = truncation_markers
            return result

        if function_name == "mcp_analyze_code_quality":
            fp = arguments.get("file_path")
            if not fp:
                return {"success": False, "error": "file_path required"}
            target = project_root / fp
            if not target.exists():
                return {"success": False, "error": f"File not found: {fp}"}
            # Minimal heuristic analysis (no external tools to keep autonomy)
            code = target.read_text(encoding="utf-8", errors="ignore")
            lines = code.splitlines()
            todo_count = sum(1 for line in lines if "TODO" in line or "FIXME" in line)
            long_lines = sum(1 for line in lines if len(line) > 120)
            score = max(0, 100 - (todo_count * 2 + long_lines))
            report = (
                f"Code Quality (local heuristic)\n"
                f"Lines: {len(lines)}\n"
                f"TODO/FIXME: {todo_count}\n"
                f"Long lines (>120c): {long_lines}\n"
                f"Heuristic score: {score}/100"
            )
            return {"success": True, "report": report, "source": "local_emulation"}

        return {
            "success": False,
            "error": f"Unknown tool (local mode): {function_name}",
        }

    def _get_api_url(self, agent_type: AgentType, strict_mode: bool = False) -> str:
        """Получить URL для API

        Args:
            agent_type: Type of agent (DeepSeek or Perplexity)
            strict_mode: If True, use beta URL for DeepSeek strict mode
        """
        # ✅ QUICK WIN #4: Removed debug logging from Bug #4 fix (no longer needed)
        if agent_type == AgentType.DEEPSEEK:
            if strict_mode:
                return "https://api.deepseek.com/beta/chat/completions"
            return "https://api.deepseek.com/v1/chat/completions"
        else:
            return "https://api.perplexity.ai/chat/completions"

    def _get_headers(self, key: APIKey) -> dict[str, str]:
        """Получить headers для API запроса"""
        return {
            "Authorization": f"Bearer {key.value}",
            "Content-Type": "application/json",
        }

    async def stream_request(
        self,
        request: AgentRequest,
        on_reasoning_chunk: Callable | None = None,
        on_content_chunk: Callable | None = None,
    ) -> AgentResponse:
        """
        Stream a request with real-time output.

        DeepSeek V3.2 streaming returns:
        - reasoning_content chunks (Chain-of-Thought)
        - content chunks (Final answer)

        Args:
            request: AgentRequest with stream=True
            on_reasoning_chunk: Callback for reasoning chunks (reasoning: str)
            on_content_chunk: Callback for content chunks (content: str)

        Returns:
            AgentResponse with complete content
        """
        import httpx

        start_time = time.time()

        # Get API key
        key = await self.key_manager.get_active_key(request.agent_type)
        if not key:
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.DIRECT_API,
                error=f"No active {request.agent_type.value} API keys",
            )

        url = self._get_api_url(request.agent_type, strict_mode=request.strict_mode)
        headers = self._get_headers(key)

        # Build payload with stream=True
        payload = request.to_direct_api_format(include_tools=False)
        payload["stream"] = True

        logger.info(f"🌊 Starting streaming request to {request.agent_type.value}")

        full_reasoning = ""
        full_content = ""

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})

                            # Extract reasoning_content chunk (DeepSeek Thinking Mode)
                            reasoning_chunk = delta.get("reasoning_content", "")
                            if reasoning_chunk:
                                full_reasoning += reasoning_chunk
                                if on_reasoning_chunk:
                                    await on_reasoning_chunk(reasoning_chunk)

                            # Extract content chunk
                            content_chunk = delta.get("content", "")
                            if content_chunk:
                                full_content += content_chunk
                                if on_content_chunk:
                                    await on_content_chunk(content_chunk)

                        except json.JSONDecodeError:
                            continue

            latency = (time.time() - start_time) * 1000
            self.key_manager.mark_success(key)

            logger.success(
                f"✅ Streaming completed in {latency:.0f}ms "
                f"(reasoning: {len(full_reasoning)}, content: {len(full_content)})"
            )

            # Save reasoning log if available
            if full_reasoning:
                self._save_reasoning_log(full_reasoning)

            return AgentResponse(
                success=True,
                content=full_content,
                channel=AgentChannel.DIRECT_API,
                api_key_index=key.index,
                latency_ms=latency,
                reasoning_content=full_reasoning if full_reasoning else None,
            )

        except httpx.HTTPStatusError as e:
            self.key_manager.mark_rate_limit(key)
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.DIRECT_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )

        except Exception as e:
            self.key_manager.mark_network_error(key)
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.DIRECT_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    def _extract_content(self, data: dict, agent_type: AgentType) -> str:
        """
        Извлечь содержимое из ответа API с fallback стратегией

        Пробует несколько путей для извлечения контента:
        1. data["choices"][0]["message"]["content"] - стандартный OpenAI формат
        2. data["message"]["content"] - альтернативный формат
        3. data["content"] - прямой доступ
        4. data["text"] - текстовое поле
        5. data["response"] - поле ответа
        """
        # List of possible paths to extract content
        extraction_paths = [
            # Standard OpenAI format
            lambda d: d["choices"][0]["message"]["content"],
            # Alternative formats
            lambda d: d["message"]["content"],
            lambda d: d["content"],
            lambda d: d["text"],
            lambda d: d["response"],
            # DeepSeek specific
            lambda d: d["choices"][0]["text"],
            # Perplexity specific
            lambda d: d["output"]["text"],
        ]

        for path_func in extraction_paths:
            try:
                content = path_func(data)
                if content and isinstance(content, str) and content.strip():
                    logger.debug(f"✅ Content extracted successfully via {path_func.__name__}")
                    return content.strip()
            except (KeyError, IndexError, TypeError):
                continue

        # If all paths failed, log the full response for debugging
        logger.error(f"❌ Failed to extract content from response. Full data: {json.dumps(data, indent=2)[:500]}...")
        logger.warning(f"⚠️ Available keys in response: {list(data.keys())}")

        # Last resort: try to find any text-like value
        for key in ["choices", "message", "content", "text", "response", "output"]:
            if key in data:
                value = data[key]
                if isinstance(value, str) and value.strip():
                    logger.info(f"🔍 Found content in fallback key '{key}'")
                    return value.strip()
                elif isinstance(value, list) and value:
                    logger.info(f"🔍 Found list in '{key}', extracting first item")
                    return str(value[0])

        # Complete fallback: return JSON dump
        logger.error("❌ No content found in any known field, returning JSON dump")
        return json.dumps(data, indent=2)

    def _extract_reasoning_content(self, data: dict) -> str | None:
        """
        Extract reasoning_content from DeepSeek V3.2 Thinking Mode response.

        DeepSeek Thinking Mode returns:
        - reasoning_content: Chain-of-Thought reasoning process
        - content: Final answer

        Reference: https://api-docs.deepseek.com/guides/thinking_mode
        """
        try:
            message = data.get("choices", [{}])[0].get("message", {})
            reasoning = message.get("reasoning_content")
            if reasoning and isinstance(reasoning, str) and reasoning.strip():
                # Save reasoning to log file for analysis
                self._save_reasoning_log(reasoning.strip())
                return reasoning.strip()
        except (KeyError, IndexError, TypeError) as e:
            logger.debug(f"No reasoning_content found: {e}")
        return None

    def _save_reasoning_log(self, reasoning: str) -> None:
        """Save reasoning content to log file for analysis and debugging.

        DeepSeek V3.2 Thinking Mode produces valuable Chain-of-Thought
        that can be analyzed to improve agent quality.
        """
        try:
            from datetime import datetime
            from pathlib import Path

            log_dir = Path("logs/reasoning")
            log_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"reasoning_{timestamp}.md"

            content = f"""# DeepSeek V3.2 Reasoning Log
**Timestamp:** {datetime.now().isoformat()}
**Length:** {len(reasoning)} chars

## Chain-of-Thought

{reasoning}
"""
            log_file.write_text(content, encoding="utf-8")
            logger.debug(f"💾 Reasoning saved to {log_file}")
        except Exception as e:
            logger.warning(f"Failed to save reasoning log: {e}")

    def _clear_reasoning_in_messages(self, messages: list[dict]) -> None:
        """Clear reasoning_content from messages to save bandwidth.

        DeepSeek V3.2 documentation recommends:
        - Keep reasoning_content within a single turn (for tool calling loops)
        - Clear reasoning_content when starting a new turn

        Reference: https://api-docs.deepseek.com/guides/thinking_mode
        """
        for msg in messages:
            if isinstance(msg, dict) and "reasoning_content" in msg:
                msg["reasoning_content"] = None
            elif hasattr(msg, "reasoning_content"):
                msg.reasoning_content = None

    def _extract_citations(self, data: dict, agent_type: AgentType) -> list[str] | None:
        """
        Extract citations from Perplexity API response.

        Perplexity response format:
        {
            "citations": [
                "https://example.com/source1",
                "https://example.com/source2",
                ...
            ]
        }

        Args:
            data: API response data
            agent_type: Agent type (only Perplexity has citations)

        Returns:
            List of source URLs or None if not available
        """
        if agent_type != AgentType.PERPLEXITY:
            return None

        try:
            citations = data.get("citations", [])
            if citations and isinstance(citations, list):
                # Filter valid URLs
                valid_citations = [
                    url for url in citations if isinstance(url, str) and url.startswith(("http://", "https://"))
                ]
                if valid_citations:
                    logger.info(f"📚 Extracted {len(valid_citations)} citations from Perplexity")
                    return valid_citations
        except Exception as e:
            logger.debug(f"Failed to extract citations: {e}")

        return None

    def _extract_token_usage(self, data: dict, agent_type: AgentType) -> TokenUsage | None:
        """
        Extract token usage from API response.

        DeepSeek format:
        {
            "usage": {
                "prompt_tokens": 123,
                "completion_tokens": 456,
                "total_tokens": 579,
                "completion_tokens_details": {
                    "reasoning_tokens": 200  # V3.2 Thinking Mode
                }
            }
        }

        Perplexity format:
        {
            "usage": {
                "prompt_tokens": 123,
                "completion_tokens": 456,
                "total_tokens": 579,
                "cost": {
                    "total_cost": 0.018
                }
            }
        }
        """
        try:
            usage = data.get("usage", {})
            if not usage:
                return None

            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)

            # DeepSeek V3.2: reasoning tokens in completion_tokens_details
            reasoning_tokens = 0
            if agent_type == AgentType.DEEPSEEK:
                details = usage.get("completion_tokens_details", {})
                reasoning_tokens = details.get("reasoning_tokens", 0)

            # DeepSeek Context Caching: extract cache hit/miss tokens
            cache_hit_tokens = 0
            cache_miss_tokens = 0
            cache_savings_pct = 0.0
            if agent_type == AgentType.DEEPSEEK:
                prompt_details = usage.get("prompt_tokens_details", {})
                cache_hit_tokens = prompt_details.get("cached_tokens", 0)
                # Also check for prompt_cache_hit_tokens (alternative format)
                if cache_hit_tokens == 0:
                    cache_hit_tokens = usage.get("prompt_cache_hit_tokens", 0)
                    cache_miss_tokens = usage.get("prompt_cache_miss_tokens", 0)
                else:
                    # Calculate miss tokens if only hit is provided
                    cache_miss_tokens = prompt_tokens - cache_hit_tokens

                # Calculate cache savings percentage
                if prompt_tokens > 0:
                    cache_savings_pct = round((cache_hit_tokens / prompt_tokens) * 100, 2)

            # Perplexity: cost in usage.cost
            cost_usd = None
            if agent_type == AgentType.PERPLEXITY:
                cost_info = usage.get("cost", {})
                cost_usd = cost_info.get("total_cost")

            # Calculate cost for DeepSeek if not provided
            # DeepSeek pricing: $0.14/M input, $0.28/M output (standard)
            # Thinking Mode: $0.55/M input, $2.19/M output
            if agent_type == AgentType.DEEPSEEK and cost_usd is None:
                # Check if it's thinking mode (has reasoning tokens)
                if reasoning_tokens > 0:
                    input_cost = prompt_tokens * 0.55 / 1_000_000
                    output_cost = completion_tokens * 2.19 / 1_000_000
                else:
                    input_cost = prompt_tokens * 0.14 / 1_000_000
                    output_cost = completion_tokens * 0.28 / 1_000_000
                cost_usd = round(input_cost + output_cost, 6)

            token_usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                reasoning_tokens=reasoning_tokens,
                cost_usd=cost_usd,
                cache_hit_tokens=cache_hit_tokens,
                cache_miss_tokens=cache_miss_tokens,
                cache_savings_pct=cache_savings_pct,
            )

            # Log with cache info if available
            cache_info = ""
            if cache_hit_tokens > 0:
                cache_info = f" | Cache: {cache_savings_pct:.1f}% ({cache_hit_tokens} tokens)"

            logger.debug(
                f"📊 Token usage: {total_tokens} total "
                f"({prompt_tokens} in, {completion_tokens} out"
                f"{f', {reasoning_tokens} reasoning' if reasoning_tokens else ''})"
                f"{cache_info}"
                f" | Cost: ${cost_usd:.4f}"
                if cost_usd
                else ""
            )

            return token_usage

        except Exception as e:
            logger.debug(f"Failed to extract token usage: {e}")
            return None

    async def _health_check(self):
        """Периодическая проверка здоровья системы"""
        self.last_health_check = time.time()

        logger.debug("🏥 Running health check...")

        # Check MCP Server via native health endpoint
        if self.mcp_disabled:
            self.mcp_available = False
        else:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get("http://127.0.0.1:8000/mcp/health")
                    if resp.status_code == 200:
                        data = resp.json()
                        self.mcp_available = bool(data.get("tool_count", 0) >= 1 and data.get("status") == "healthy")
                    else:
                        self.mcp_available = False
            except Exception as e:
                logger.debug(f"MCP health probe failed: {e}")
                self.mcp_available = False

        # Check API keys
        deepseek_active = sum(1 for k in self.key_manager.deepseek_keys if k.is_usable)
        perplexity_active = sum(1 for k in self.key_manager.perplexity_keys if k.is_usable)

        logger.info(
            f"🏥 Health: MCP={'✅' if self.mcp_available else '❌'} | "
            f"DeepSeek={deepseek_active}/8 | Perplexity={perplexity_active}/4"
        )

        adaptations = self.circuit_manager.maybe_adapt_breakers(force=True, min_interval_seconds=0)
        if adaptations:
            logger.info(f"⚙️ Adaptive circuit thresholds updated: {adaptations}")

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику (включая Phase 1 metrics)"""
        # Get circuit breaker metrics
        cb_metrics = self.circuit_manager.get_metrics()

        # Get health monitoring metrics
        health_metrics = self.health_monitor.get_metrics()

        return {
            **self.stats,
            "mcp_available": self.mcp_available,
            "mcp_disabled": self.mcp_disabled,
            "deepseek_keys_active": sum(1 for k in self.key_manager.deepseek_keys if k.is_usable),
            "perplexity_keys_active": sum(1 for k in self.key_manager.perplexity_keys if k.is_usable),
            "last_health_check": datetime.fromtimestamp(self.last_health_check).isoformat(),
            # Phase 1 additions:
            "circuit_breakers": cb_metrics.to_dict(),
            "health_monitoring": health_metrics,
            "autonomy_score": self._calculate_autonomy_score(cb_metrics, health_metrics),
        }

    def _calculate_autonomy_score(self, cb_metrics, health_metrics) -> float:
        """
        Calculate autonomy score (0-10) based on system health

        Phase 1 Target: 7.5 → 8.5
        Factors:
        - Auto-recovery success rate (40%)
        - Circuit breaker health (30%)
        - Component health (30%)
        """
        # Auto-recovery score (0-4.0 points)
        recovery_rate = health_metrics.get("recovery_success_rate", 0)
        auto_recovery_score = (recovery_rate / 100) * 4.0

        # Circuit breaker score (0-3.0 points)
        # Lower trip rate = better score
        # Calculate from all breakers if metrics has breakers dict
        if hasattr(cb_metrics, "breakers") and cb_metrics.breakers:
            total_calls = sum(b.get("total_calls", 0) for b in cb_metrics.breakers.values())
            total_trips = sum(b.get("total_trips", 0) for b in cb_metrics.breakers.values())
            total_calls = total_calls or 1
            trip_rate = (total_trips / total_calls) * 100
        else:
            # Fallback: use data from cb_metrics.to_dict() if available
            cb_data = cb_metrics.to_dict() if hasattr(cb_metrics, "to_dict") else {}
            total_calls = sum(b.get("success_count", 0) + b.get("failure_count", 0) for b in cb_data.values())
            total_calls = total_calls or 1
            trip_rate = 0  # No trip data available

        circuit_score = max(0, 3.0 - (trip_rate / 10))  # Penalty for high trip rate

        # Component health score (0-3.0 points)
        total_components = health_metrics.get("total_components", 3)
        healthy_components = health_metrics.get("healthy_components", 0)
        health_score = (healthy_components / total_components) * 3.0 if total_components > 0 else 0

        # Total score (0-10)
        total_score = auto_recovery_score + circuit_score + health_score

        return round(total_score, 1)

    # =========================================================================
    # HIGH-LEVEL API CONVENIENCE METHODS
    # =========================================================================

    async def query_deepseek(
        self,
        prompt: str,
        *,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        use_cache: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Convenient method to query DeepSeek AI with caching support

        Args:
            prompt: The question or prompt
            model: DeepSeek model name
            temperature: Response randomness (0.0-2.0)
            max_tokens: Maximum response length
            use_cache: Enable/disable caching for this request (default: True)
            **kwargs: Additional parameters

        Returns:
            dict with keys: response, model, tokens_used, latency_ms, api_key_id, from_cache
        """
        # Try cache first
        if use_cache:
            try:
                from backend.core.ai_cache import get_cache_manager

                cache_manager = get_cache_manager()
                cached_response = cache_manager.get(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                if cached_response:
                    logger.info("⚡ Cache HIT for DeepSeek query (latency: ~0ms)")
                    return cached_response

            except Exception as e:
                logger.debug(f"Cache check failed: {e}, proceeding without cache")

        # Build request with simplified approach
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="chat",
            prompt=prompt,
        )

        start_time = time.time()
        response = await self.send_request(request)
        latency_ms = (time.time() - start_time) * 1000

        # Extract token usage from response
        tokens_used = None
        if response.tokens_used:
            tokens_used = {
                "prompt_tokens": response.tokens_used.prompt_tokens,
                "completion_tokens": response.tokens_used.completion_tokens,
                "total_tokens": response.tokens_used.total_tokens,
                "reasoning_tokens": response.tokens_used.reasoning_tokens,
                "cost_usd": response.tokens_used.cost_usd,
            }

        result = {
            "response": response.content,
            "model": model,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "api_key_id": str(response.api_key_index) if response.api_key_index is not None else None,
            "success": response.success,
            "error": response.error,
            "from_cache": False,
        }

        # Cache successful responses
        if use_cache and response.success and response.content:
            try:
                from backend.core.ai_cache import get_cache_manager

                cache_manager = get_cache_manager()
                cache_manager.set(
                    prompt=prompt,
                    model=model,
                    response=result,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                logger.debug("💾 Cached DeepSeek response")

            except Exception as e:
                logger.debug(f"Cache save failed: {e}")

        return result

    async def query_perplexity(
        self,
        prompt: str,
        *,
        model: str = "llama-3.1-sonar-small-128k-online",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        use_cache: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Convenient method to query Perplexity AI with caching support

        Args:
            prompt: The question or prompt
            model: Perplexity model name
            temperature: Response randomness (0.0-2.0)
            max_tokens: Maximum response length
            use_cache: Enable/disable caching for this request (default: True)
            **kwargs: Additional parameters

        Returns:
            dict with keys: response, model, tokens_used, latency_ms, api_key_id, from_cache
        """
        # Try cache first
        if use_cache:
            try:
                from backend.core.ai_cache import get_cache_manager

                cache_manager = get_cache_manager()
                cached_response = cache_manager.get(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                if cached_response:
                    logger.info("⚡ Cache HIT for Perplexity query (latency: ~0ms)")
                    return cached_response

            except Exception as e:
                logger.debug(f"Cache check failed: {e}, proceeding without cache")

        # Build request with simplified approach
        request = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="search",
            prompt=prompt,
        )

        start_time = time.time()
        response = await self.send_request(request)
        latency_ms = (time.time() - start_time) * 1000

        # Extract token usage from response
        tokens_used = None
        if response.tokens_used:
            tokens_used = {
                "prompt_tokens": response.tokens_used.prompt_tokens,
                "completion_tokens": response.tokens_used.completion_tokens,
                "total_tokens": response.tokens_used.total_tokens,
                "cost_usd": response.tokens_used.cost_usd,
            }

        result = {
            "response": response.content,
            "model": model,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "api_key_id": str(response.api_key_index) if response.api_key_index is not None else None,
            "success": response.success,
            "error": response.error,
            "from_cache": False,
        }

        # Cache successful responses
        if use_cache and response.success and response.content:
            try:
                from backend.core.ai_cache import get_cache_manager

                cache_manager = get_cache_manager()
                cache_manager.set(
                    prompt=prompt,
                    model=model,
                    response=result,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                logger.debug("💾 Cached Perplexity response")

            except Exception as e:
                logger.debug(f"Cache save failed: {e}")

        return result


# =============================================================================
# CONVENIENCE METHODS
# =============================================================================

# Global instance
_agent_interface: UnifiedAgentInterface | None = None


def get_agent_interface() -> UnifiedAgentInterface:
    """Получить глобальный инстанс (singleton)"""
    global _agent_interface
    if _agent_interface is None:
        _agent_interface = UnifiedAgentInterface()
    return _agent_interface


async def analyze_with_deepseek(code: str, focus: str = "all") -> AgentResponse:
    """Быстрый метод для анализа кода через DeepSeek"""
    interface = get_agent_interface()
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="analyze",
        prompt="Analyze this code for issues, bugs, and improvements",
        code=code,
        context={"focus": focus},
    )
    return await interface.send_request(request)


async def ask_perplexity(question: str) -> AgentResponse:
    """Быстрый метод для вопроса к Perplexity"""
    interface = get_agent_interface()
    request = AgentRequest(agent_type=AgentType.PERPLEXITY, task_type="search", prompt=question)
    return await interface.send_request(request)
