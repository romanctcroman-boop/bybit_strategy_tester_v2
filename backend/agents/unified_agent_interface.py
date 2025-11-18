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
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from loguru import logger

# ✅ FIX: Import AgentType from models.py instead of redefining
from backend.agents.models import AgentType, AgentChannel

# Phase 1: Circuit Breaker and Health Monitoring
from backend.agents.circuit_breaker_manager import (
    get_circuit_manager,
    CircuitBreakerError,
)
from backend.agents.health_monitor import (
    get_health_monitor,
    HealthStatus,
    HealthCheckResult,
    RecoveryActionType,
)

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


@dataclass
class APIKey:
    """API ключ с метаданными"""
    value: str
    agent_type: AgentType
    index: int  # 0-7 для DeepSeek, 0-3 для Perplexity
    is_active: bool = True
    last_used: float | None = None
    error_count: int = 0
    requests_count: int = 0


@dataclass
class AgentRequest:
    """Унифицированный запрос к агенту"""
    agent_type: AgentType
    task_type: str  # "analyze", "fix", "explain", "generate", etc.
    prompt: str
    code: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    
    def to_mcp_format(self) -> dict[str, Any]:
        """Преобразовать в формат MCP tool"""
        return {
            "strategy_code": self.code or self.prompt,
            "include_suggestions": True,
            "focus": self.context.get("focus", "all"),
        }
    
    def to_direct_api_format(self, include_tools: bool = True) -> dict[str, Any]:
        """Преобразовать в формат прямого API (с опциональными tools)"""
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
            
            # Add MCP file access tools for DeepSeek
            use_file_access = self.context.get("use_file_access", False)
            logger.debug(f"🔍 use_file_access={use_file_access}, include_tools={include_tools}")
            
            if include_tools and use_file_access:
                tools = self._get_mcp_tools_definition()
                payload["tools"] = tools
                logger.info(f"🔧 Added {len(tools)} MCP tools to DeepSeek request")
            else:
                logger.debug(f"⚠️  Tools not included (include_tools={include_tools}, use_file_access={use_file_access})")
            
            return payload
            
        else:  # Perplexity
            # Perplexity doesn't support function calling yet
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
        """Построить полный prompt"""
        parts = [f"Task: {self.task_type}", f"\n{self.prompt}"]
        if self.code:
            parts.append(f"\n\nCode to analyze:\n```python\n{self.code}\n```")
        if self.context:
            parts.append(f"\n\nContext: {json.dumps(self.context, indent=2)}")
        return "\n".join(parts)
    
    @staticmethod
    def _get_mcp_tools_definition() -> list[dict[str, Any]]:
        """Получить определения MCP file access tools для DeepSeek"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "mcp_read_project_file",
                    "description": "Read a file from the project. Supports Python, JSON, Markdown, YAML files. Has security restrictions (cannot read .env, .git, secrets).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Relative path to file from project root (e.g., 'backend/api/app.py')"
                            },
                            "max_size_kb": {
                                "type": "integer",
                                "description": "Maximum file size in KB (default: 100)",
                                "default": 100
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_list_project_structure",
                    "description": "List directory structure of the project. Returns nested tree. Auto-blocks .git, __pycache__, node_modules.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "Directory to list (relative to project root, default: '.')",
                                "default": "."
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum depth to traverse (default: 3)",
                                "default": 3
                            },
                            "include_hidden": {
                                "type": "boolean",
                                "description": "Include hidden files/folders (default: false)",
                                "default": False
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_analyze_code_quality",
                    "description": "Run code quality tools (Ruff, Black, Bandit) on a Python file. Returns linting issues, formatting problems, security vulnerabilities.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to Python file to analyze"
                            },
                            "tools": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["ruff", "black", "bandit"]},
                                "description": "Tools to run (default: ['ruff', 'black', 'bandit'])",
                                "default": ["ruff", "black", "bandit"]
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            }
        ]


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


# =============================================================================
# ENCRYPTION SYSTEM INTEGRATION
# =============================================================================

class APIKeyManager:
    """Менеджер API ключей с расшифровкой
    
    Quick Win #2: Thread-safe key selection with async lock
    Prevents race condition in multi-worker FastAPI deployment
    """
    
    def __init__(self):
        self.deepseek_keys: list[APIKey] = []
        self.perplexity_keys: list[APIKey] = []
        
        # ✅ QUICK WIN #2: Async lock for thread-safe key selection
        self._key_selection_lock = asyncio.Lock()
        
        self._load_keys()
    
    def _load_keys(self):
        """Загрузить и расшифровать все API ключи"""
        try:
            # Импорт системы шифрования
            from backend.security.key_manager import KeyManager
            
            km = KeyManager()
            
            # DeepSeek (8 keys)
            for i in range(8):
                try:
                    key_name = f"DEEPSEEK_API_KEY_{i+1}" if i > 0 else "DEEPSEEK_API_KEY"
                    decrypted = km.get_decrypted_key(key_name)
                    if decrypted:
                        self.deepseek_keys.append(APIKey(
                            value=decrypted,
                            agent_type=AgentType.DEEPSEEK,
                            index=i
                        ))
                        logger.debug(f"✅ DeepSeek key {i+1}/8 loaded")
                except Exception as e:
                    logger.warning(f"⚠️ DeepSeek key {i+1}/8 failed: {e}")
            
            # Perplexity (8 keys - расширено с 4 до 8)
            for i in range(8):
                try:
                    key_name = f"PERPLEXITY_API_KEY_{i+1}" if i > 0 else "PERPLEXITY_API_KEY"
                    decrypted = km.get_decrypted_key(key_name)
                    if decrypted:
                        self.perplexity_keys.append(APIKey(
                            value=decrypted,
                            agent_type=AgentType.PERPLEXITY,
                            index=i
                        ))
                        logger.debug(f"✅ Perplexity key {i+1}/8 loaded")
                except Exception as e:
                    logger.warning(f"⚠️ Perplexity key {i+1}/8 failed: {e}")
            
            logger.info(f"🔑 Loaded {len(self.deepseek_keys)} DeepSeek + {len(self.perplexity_keys)} Perplexity keys")
            
        except ImportError:
            logger.error("❌ Encryption system not available!")
            raise
    
    async def get_active_key(self, agent_type: AgentType) -> APIKey | None:
        """
        Получить активный API ключ (с наименьшим количеством ошибок)
        
        ✅ QUICK WIN #2: Thread-safe with async lock
        Prevents race condition when multiple concurrent requests select the same key
        """
        async with self._key_selection_lock:
            keys = self.deepseek_keys if agent_type == AgentType.DEEPSEEK else self.perplexity_keys
            active_keys = [k for k in keys if k.is_active]
            
            if not active_keys:
                return None
            
            # Сортировка: меньше ошибок → меньше использований → давно не использовался
            return sorted(
                active_keys,
                key=lambda k: (k.error_count, k.requests_count, -(k.last_used or 0))
            )[0]
    
    def mark_error(self, key: APIKey):
        """Отметить ошибку для ключа"""
        key.error_count += 1
        if key.error_count >= 3:
            key.is_active = False
            logger.warning(f"⚠️ Disabled {key.agent_type.value} key #{key.index} (3 errors)")
    
    def mark_success(self, key: APIKey):
        """Отметить успешное использование"""
        key.last_used = time.time()
        key.requests_count += 1
        key.error_count = max(0, key.error_count - 1)  # Уменьшить счетчик ошибок

    # The following helpers avoid disabling keys on transient network issues
    def mark_network_error(self, key: APIKey):
        """Учесть сетевую/временную ошибку без деактивации ключа"""
        key.error_count += 1

    def mark_client_error(self, key: APIKey):
        """Учесть ошибку клиента (4xx, кроме 401/403/429) без деактивации ключа"""
        key.error_count += 1

    def mark_auth_error(self, key: APIKey):
        """Немедленно деактивировать ключ при ошибке аутентификации"""
        key.error_count += 1
        key.is_active = False
        logger.warning(f"⚠️ Disabled {key.agent_type.value} key #{key.index} due to auth error")


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
    
    def __init__(self):
        self.key_manager = APIKeyManager()
        self.mcp_available = False
        self.last_health_check = 0
        self.health_check_interval = 30  # seconds
        
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
        }
        
        logger.info("🚀 Unified Agent Interface initialized")
        logger.info("🛡️ Circuit breakers registered: deepseek_api, perplexity_api, mcp_server")
        logger.info("🏥 Health monitoring ready (will start with event loop)")
        
        # Start background health monitoring - lazy initialization
        # Will be started when first request is made (in ensure_monitoring_started)
        self._monitoring_task: Optional[asyncio.Task] = None
    
    def ensure_monitoring_started(self) -> None:
        """Start health monitoring if not already running (lazy initialization)"""
        if self._monitoring_task is None or self._monitoring_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._monitoring_task = loop.create_task(
                    self.health_monitor.start_monitoring(30)
                )
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
            expected_exception=Exception
        )
        
        # Perplexity API
        self.circuit_manager.register_breaker(
            name="perplexity_api",
            fail_max=5,
            timeout_duration=60,
            expected_exception=Exception
        )
        
        # MCP Server
        self.circuit_manager.register_breaker(
            name="mcp_server",
            fail_max=3,  # More sensitive for internal service
            timeout_duration=30,  # Faster recovery attempt
            expected_exception=Exception
        )
    
    def _register_health_checks(self) -> None:
        """Register health checks for all components"""
        # DeepSeek API
        self.health_monitor.register_health_check(
            component="deepseek_api",
            health_check_func=self._check_deepseek_health,
            recovery_func=self._recover_deepseek
        )
        
        # Perplexity API
        self.health_monitor.register_health_check(
            component="perplexity_api",
            health_check_func=self._check_perplexity_health,
            recovery_func=self._recover_perplexity
        )
        
        # MCP Server
        self.health_monitor.register_health_check(
            component="mcp_server",
            health_check_func=self._check_mcp_health,
            recovery_func=self._recover_mcp
        )
    
    async def _check_deepseek_health(self) -> HealthCheckResult:
        """Health check for DeepSeek API"""
        active_keys = sum(1 for k in self.key_manager.deepseek_keys if k.is_active)
        total_keys = len(self.key_manager.deepseek_keys)
        
        if active_keys == 0:
            return HealthCheckResult(
                component="deepseek_api",
                status=HealthStatus.UNHEALTHY,
                message=f"No active DeepSeek keys (0/{total_keys})",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS
            )
        elif active_keys < total_keys * 0.5:
            return HealthCheckResult(
                component="deepseek_api",
                status=HealthStatus.DEGRADED,
                message=f"Only {active_keys}/{total_keys} DeepSeek keys active",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS
            )
        else:
            return HealthCheckResult(
                component="deepseek_api",
                status=HealthStatus.HEALTHY,
                message=f"DeepSeek API healthy ({active_keys}/{total_keys} keys active)",
                details={"active_keys": active_keys, "total_keys": total_keys}
            )
    
    async def _check_perplexity_health(self) -> HealthCheckResult:
        """Health check for Perplexity API"""
        active_keys = sum(1 for k in self.key_manager.perplexity_keys if k.is_active)
        total_keys = len(self.key_manager.perplexity_keys)
        
        if active_keys == 0:
            return HealthCheckResult(
                component="perplexity_api",
                status=HealthStatus.UNHEALTHY,
                message=f"No active Perplexity keys (0/{total_keys})",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS
            )
        elif active_keys < total_keys * 0.5:
            return HealthCheckResult(
                component="perplexity_api",
                status=HealthStatus.DEGRADED,
                message=f"Only {active_keys}/{total_keys} Perplexity keys active",
                details={"active_keys": active_keys, "total_keys": total_keys},
                recovery_suggested=RecoveryActionType.RESET_ERRORS
            )
        else:
            return HealthCheckResult(
                component="perplexity_api",
                status=HealthStatus.HEALTHY,
                message=f"Perplexity API healthy ({active_keys}/{total_keys} keys active)",
                details={"active_keys": active_keys, "total_keys": total_keys}
            )
    
    async def _check_mcp_health(self) -> HealthCheckResult:
        """Health check for MCP Server"""
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
                            details=data
                        )
                    else:
                        return HealthCheckResult(
                            component="mcp_server",
                            status=HealthStatus.DEGRADED,
                            message="MCP Server running but no tools available",
                            details=data,
                            recovery_suggested=RecoveryActionType.FORCE_HEALTH_CHECK
                        )
        except Exception as e:
            return HealthCheckResult(
                component="mcp_server",
                status=HealthStatus.UNHEALTHY,
                message=f"MCP Server unreachable: {str(e)}",
                details={"error": str(e)},
                recovery_suggested=RecoveryActionType.FORCE_HEALTH_CHECK
            )
    
    async def _recover_deepseek(self, action_type: RecoveryActionType) -> None:
        """Recovery action for DeepSeek API"""
        if action_type == RecoveryActionType.RESET_ERRORS:
            # Reset error counts for all DeepSeek keys
            for key in self.key_manager.deepseek_keys:
                if not key.is_active and key.error_count >= 3:
                    key.error_count = 0
                    key.is_active = True
                    logger.info(f"✅ Recovered DeepSeek key #{key.index}")
            self.stats["auto_recoveries"] += 1
        elif action_type == RecoveryActionType.RESET_CIRCUIT_BREAKER:
            self.circuit_manager.reset_breaker("deepseek_api")
            self.stats["auto_recoveries"] += 1
    
    async def _recover_perplexity(self, action_type: RecoveryActionType) -> None:
        """Recovery action for Perplexity API"""
        if action_type == RecoveryActionType.RESET_ERRORS:
            # Reset error counts for all Perplexity keys
            for key in self.key_manager.perplexity_keys:
                if not key.is_active and key.error_count >= 3:
                    key.error_count = 0
                    key.is_active = True
                    logger.info(f"✅ Recovered Perplexity key #{key.index}")
            self.stats["auto_recoveries"] += 1
        elif action_type == RecoveryActionType.RESET_CIRCUIT_BREAKER:
            self.circuit_manager.reset_breaker("perplexity_api")
            self.stats["auto_recoveries"] += 1
    
    async def _recover_mcp(self, action_type: RecoveryActionType) -> None:
        """Recovery action for MCP Server"""
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
        preferred_channel: AgentChannel = AgentChannel.MCP_SERVER
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
                    context=request.context
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to record metrics: {e}")
        
        # Task 12: Enqueue to DLQ for retry
        try:
            from backend.agents.dead_letter_queue import DLQMessage, DLQPriority, get_dlq
            from backend.middleware.correlation_id import get_correlation_id
            
            dlq = get_dlq()
            dlq_message = DLQMessage(
                message_id=str(uuid.uuid4()),
                agent_type=request.agent_type.value,
                content=request.prompt,
                context=request.context,
                error="All communication channels failed",
                priority=DLQPriority.HIGH if request.context.get("critical", False) else DLQPriority.NORMAL,
                correlation_id=get_correlation_id()
            )
            
            enqueued = await dlq.enqueue(dlq_message)
            if enqueued:
                logger.info(f"📬 Message enqueued to DLQ: {dlq_message.message_id}")
        except Exception as e:
            logger.error(f"❌ Failed to enqueue to DLQ: {e}")
        
        return AgentResponse(
            success=False,
            content="",
            channel=AgentChannel.DIRECT_API,
            latency_ms=latency,
            error="All communication channels failed"
        )
    
    async def _try_mcp(self, request: AgentRequest) -> AgentResponse:
        """
        Попытка через MCP Server (internal bridge)
        
        Phase 1: Wrapped with circuit breaker for automatic failure isolation
        """
        start_time = time.time()
        
        # Wrap MCP call with circuit breaker
        try:
            return await self.circuit_manager.call_with_breaker(
                "mcp_server",
                self._execute_mcp_call,
                request,
                start_time
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
                error=f"MCP circuit breaker open: {str(e)}"
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
                arguments={
                    "content": request.prompt,
                    "context": request.context
                }
            )
            
            if result.get("success"):
                return AgentResponse(
                    success=True,
                    content=result.get("content", ""),
                    channel=AgentChannel.MCP_SERVER,
                    latency_ms=(time.time() - start_time) * 1000
                )
            else:
                return AgentResponse(
                    success=False,
                    content="",
                    channel=AgentChannel.MCP_SERVER,
                    latency_ms=(time.time() - start_time) * 1000,
                    error=result.get("error", "MCP tool execution failed")
                )
                    
        except Exception as e:
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.MCP_SERVER,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"MCP bridge error: {str(e)}"
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
        breaker_name = (
            "deepseek_api" if request.agent_type == AgentType.DEEPSEEK
            else "perplexity_api"
        )
        
        # Wrap API call with circuit breaker
        try:
            response = await self.circuit_manager.call_with_breaker(
                breaker_name,
                self._execute_api_call,
                request,
                start_time
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
                error=f"Circuit breaker open: {str(e)}"
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
                error=f"No active {request.agent_type.value} API keys"
            )
        
        # Determine timeout based on task complexity
        is_complex_task = (
            request.context.get("use_file_access", False) or
            request.context.get("complex_task", False) or
            request.context.get("self_improvement_analysis", False)
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
                logger.warning(
                    f"🔄 Retry attempt {retry_attempt}/{MAX_RETRIES} "
                    f"after {backoff_delay}s backoff"
                )
                await asyncio.sleep(backoff_delay)
            
            # Make API request with tool calling loop
            try:
                url = self._get_api_url(request.agent_type)
                logger.debug(f"🌐 URL for {request.agent_type.value}: {url}")
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
                                logger.warning(
                                    f"⚠️ Tool call budget exceeded: {total_tool_calls + len(tool_calls)} > {tool_call_budget}"
                                )
                                # Graceful degradation: ask agent to provide final analysis without tools
                                messages.append({
                                    "role": "system",
                                    "content": f"Tool call budget exceeded ({tool_call_budget} calls). Please provide final analysis without additional tool calls."
                                })
                                # Continue to get final response without executing tools
                                continue
                            
                            # Add assistant message with tool calls
                            messages.append(message)
                            
                            # Execute each tool call
                            for tool_call in tool_calls:
                                tool_result = await self._execute_mcp_tool(tool_call)
                                
                                # ✅ QUICK WIN #1: Track total tool calls
                                total_tool_calls += 1
                                tool_name = tool_call.get("function", {}).get("name", "unknown")
                                logger.debug(f"   Tool call #{total_tool_calls}/{tool_call_budget} completed: {tool_name}")
                                
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
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.get("id"),
                                    "name": tool_name,
                                    "content": result_content
                                })
                            
                            # Continue loop to get agent's final response
                            continue
                    
                    # No more tool calls - extract final content
                    content = self._extract_content(data, request.agent_type)
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
                                context=request.context
                            )
                        except Exception as e:
                            logger.error(f"❌ Failed to record success metrics: {e}", exc_info=True)
                    else:
                        logger.warning("⚠️ Metrics disabled - skipping recording")
                    
                    return AgentResponse(
                        success=True,
                        content=content,
                            channel=AgentChannel.DIRECT_API,
                            api_key_index=key.index,
                            latency_ms=latency
                        )
                
                # Max iterations reached
                logger.warning(f"⚠️ Max iterations ({max_iterations}) reached for tool calling")
                logger.info(f"   Total tool calls executed: {total_tool_calls}/{tool_call_budget}")
                return AgentResponse(
                    success=False,
                    content="",
                    channel=AgentChannel.DIRECT_API,
                    latency_ms=(time.time() - start_time) * 1000,
                    error=f"Max tool calling iterations ({max_iterations}) reached"
                )
        
            except httpx.TimeoutException as e:
                last_exception = e
                if not first_error:
                    first_error = f"Timeout ({timeout}s) on {request.agent_type.value}"
                # Timeouts are typically transient; do not disable key
                self.key_manager.mark_network_error(key)
                logger.error(
                    f"❌ Timeout on attempt {retry_attempt}/{MAX_RETRIES}: "
                    f"{timeout}s exceeded"
                )
                # Continue to next retry iteration
                continue
            
            except httpx.HTTPStatusError as e:
                last_exception = e
                if not first_error:
                    first_error = f"HTTP {e.response.status_code} on {request.agent_type.value}: {e.response.text[:100]}"
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
                elif status == 429 or 500 <= status < 600:
                    # Rate limit or server errors: transient
                    self.key_manager.mark_network_error(key)
                    # Continue to next retry iteration for 5xx and 429
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
                error=f"No backup {request.agent_type.value} keys available"  # ✅ FIX: Specific error message
            )
        
        # ✅ FIX: Validate key type matches request
        if key.agent_type != request.agent_type:
            logger.error(
                f"❌ KEY TYPE MISMATCH: {key.agent_type.value} key for {request.agent_type.value} request"
            )
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.BACKUP_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"Key type mismatch: {key.agent_type.value} != {request.agent_type.value}"
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
                    latency_ms=(time.time() - start_time) * 1000
                )
        except Exception as e:
            self.key_manager.mark_error(key)
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.BACKUP_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"Backup API also failed: {str(e)}"
            )
    
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
                        "error": f"Invalid tool arguments JSON: {str(e)}"
                    }
            else:
                arguments = arguments_str
            
            logger.debug(f"   Arguments (parsed): {arguments}")
            
            # Import MCP tools from app.py
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
                    "error": f"Failed to import MCP tools: {str(e)}"
                }
            
            # Map tool names to functions - use functions directly
            # Note: If tools are wrapped with @mcp.tool(), they might be FunctionTool objects
            # Try to call them directly first, if that fails, try .fn attribute
            tool_map = {
                "mcp_read_project_file": mcp_read_project_file,
                "mcp_list_project_structure": mcp_list_project_structure,
                "mcp_analyze_code_quality": mcp_analyze_code_quality,
            }
            
            if function_name not in tool_map:
                logger.error(f"❌ Unknown tool: {function_name}")
                logger.error(f"   Available tools: {list(tool_map.keys())}")
                return {
                    "success": False,
                    "error": f"Unknown tool: {function_name}"
                }
            
            # Execute tool
            tool_func = tool_map[function_name]
            logger.debug(f"   Calling {function_name} with arguments: {arguments}")
            logger.debug(f"   Tool function type: {type(tool_func)}")
            
            # Try to call the tool - if it's a FunctionTool object, try .fn attribute
            try:
                result = await tool_func(**arguments)
            except TypeError as e:
                if "'FunctionTool' object is not callable" in str(e) or "not callable" in str(e):
                    logger.warning("   Tool is wrapped, trying .fn attribute")
                    actual_func = getattr(tool_func, 'fn', None)
                    if actual_func:
                        result = await actual_func(**arguments)
                    else:
                        raise
                else:
                    raise
            
            logger.info(f"✅ Tool executed: {function_name} -> success={result.get('success')}")
            if not result.get('success'):
                logger.warning(f"   Tool returned error: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Tool execution failed for {function_name}: {e}")
            logger.error(f"   Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": f"Tool execution error: {str(e)}"
            }
    
    def _get_api_url(self, agent_type: AgentType) -> str:
        """Получить URL для API"""
        # ✅ QUICK WIN #4: Removed debug logging from Bug #4 fix (no longer needed)
        if agent_type == AgentType.DEEPSEEK:
            return "https://api.deepseek.com/v1/chat/completions"
        else:
            return "https://api.perplexity.ai/chat/completions"
    
    def _get_headers(self, key: APIKey) -> dict[str, str]:
        """Получить headers для API запроса"""
        return {
            "Authorization": f"Bearer {key.value}",
            "Content-Type": "application/json"
        }
    
    def _extract_content(self, data: dict, agent_type: AgentType) -> str:
        """Извлечь содержимое из ответа API"""
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error(f"❌ Failed to extract content: {e}")
            return json.dumps(data, indent=2)
    
    async def _health_check(self):
        """Периодическая проверка здоровья системы"""
        self.last_health_check = time.time()
        
        logger.debug("🏥 Running health check...")
        
        # Check MCP Server via native health endpoint
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
        deepseek_active = sum(1 for k in self.key_manager.deepseek_keys if k.is_active)
        perplexity_active = sum(1 for k in self.key_manager.perplexity_keys if k.is_active)
        
        logger.info(f"🏥 Health: MCP={'✅' if self.mcp_available else '❌'} | "
                   f"DeepSeek={deepseek_active}/8 | Perplexity={perplexity_active}/4")
    
    def get_stats(self) -> dict[str, Any]:
        """Получить статистику (включая Phase 1 metrics)"""
        # Get circuit breaker metrics
        cb_metrics = self.circuit_manager.get_metrics()
        
        # Get health monitoring metrics
        health_metrics = self.health_monitor.get_metrics()
        
        return {
            **self.stats,
            "mcp_available": self.mcp_available,
            "deepseek_keys_active": sum(1 for k in self.key_manager.deepseek_keys if k.is_active),
            "perplexity_keys_active": sum(1 for k in self.key_manager.perplexity_keys if k.is_active),
            "last_health_check": datetime.fromtimestamp(self.last_health_check).isoformat(),
            # Phase 1 additions:
            "circuit_breakers": cb_metrics.to_dict(),
            "health_monitoring": health_metrics,
            "autonomy_score": self._calculate_autonomy_score(cb_metrics, health_metrics)
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
        total_calls = cb_metrics.total_calls or 1
        trip_rate = (cb_metrics.total_trips / total_calls) * 100
        circuit_score = max(0, 3.0 - (trip_rate / 10))  # Penalty for high trip rate
        
        # Component health score (0-3.0 points)
        total_components = health_metrics.get("total_components", 3)
        healthy_components = health_metrics.get("healthy_components", 0)
        health_score = (healthy_components / total_components) * 3.0 if total_components > 0 else 0
        
        # Total score (0-10)
        total_score = auto_recovery_score + circuit_score + health_score
        
        return round(total_score, 1)


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
        context={"focus": focus}
    )
    return await interface.send_request(request)


async def ask_perplexity(question: str) -> AgentResponse:
    """Быстрый метод для вопроса к Perplexity"""
    interface = get_agent_interface()
    request = AgentRequest(
        agent_type=AgentType.PERPLEXITY,
        task_type="search",
        prompt=question
    )
    return await interface.send_request(request)
