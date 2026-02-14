"""
🤖 Unified Agent Interface — Autonomous system with auto-fallback

Architecture:
1. MCP Server (primary) → Direct API (fallback)
2. Automatic decryption of 8 DeepSeek + 8 Qwen + 8 Perplexity API keys
3. Health checks every 30s
4. Automatic API key rotation on errors
5. Unified request format (works via any channel)

Refactored: APIKey/APIKeyHealth extracted to key_models.py,
AgentRequest/TokenUsage/AgentResponse extracted to request_models.py
"""

import asyncio
import json
import time
import uuid
from typing import Any, cast

import httpx
from dotenv import load_dotenv
from loguru import logger

# APIKeyManager is now in api_key_pool.py (single source of truth).
# Imported here for backward compatibility — eliminates 330 LOC duplication.
from backend.agents.api_key_pool import APIKeyPoolManager as APIKeyManager
from backend.agents.base_config import FORCE_DIRECT_AGENT_API, MCP_DISABLED

# Phase 1: Circuit Breaker and Health Monitoring
from backend.agents.circuit_breaker_manager import (
    CircuitBreakerError,
    get_circuit_manager,
)
from backend.agents.health_monitor import (
    get_health_monitor,
)

# Canonical imports from extracted modules — re-exported for backward compat
from backend.agents.key_models import APIKey, APIKeyHealth  # noqa: F401
from backend.agents.models import AgentChannel, AgentType
from backend.agents.request_models import AgentRequest, AgentResponse, TokenUsage  # noqa: F401

# Metrics system (lazy import for graceful degradation)
try:
    from backend.monitoring.agent_metrics import metrics_enabled, record_agent_call
except ImportError:
    logger.warning("⚠️ Metrics system not available - recording disabled")
    metrics_enabled = False

    async def record_agent_call(  # type: ignore[misc]
        agent_name: str,
        response_time_ms: float,
        success: bool,
        error: str | None = None,
        tool_calls: int | None = None,
        iterations: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Stub for when metrics are unavailable."""


# Load environment variables from .env
load_dotenv()

# =============================================================================
# NOTE: APIKeyHealth, APIKey, AgentRequest, TokenUsage, AgentResponse
# are now defined in key_models.py and request_models.py respectively.
# They are imported above and re-exported for backward compatibility.
# =============================================================================


# =============================================================================
# UNIFIED AGENT INTERFACE
# =============================================================================

# Import mixins (extracted to reduce file size)
from backend.agents._api_mixin import APIMixin
from backend.agents._health_mixin import HealthMixin
from backend.agents._query_mixin import QueryMixin
from backend.agents._tool_mixin import ToolMixin


class UnifiedAgentInterface(HealthMixin, ToolMixin, APIMixin, QueryMixin):
    """
    Unified interface for AI agents

    Features:
    - Automatic MCP -> Direct API fallback
    - Automatic switching between API keys
    - Health checks every 30s
    - Unified request/response format
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

    # ensure_monitoring_started, _register_circuit_breakers, _register_health_checks,
    # _handle_pool_alert, _record_rate_limit_event,
    # _check_deepseek_health, _check_perplexity_health, _check_mcp_health,
    # _test_key_health, _recover_deepseek, _recover_perplexity, _recover_mcp
    # → moved to _health_mixin.py

    # _get_retry_after_seconds, get_key_pool_snapshot → moved to _api_mixin.py

    async def send_request(
        self,
        request: AgentRequest,
        preferred_channel: AgentChannel = AgentChannel.MCP_SERVER,
    ) -> AgentResponse:
        """
        Send request to agent (with automatic fallback)

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
            task = asyncio.create_task(self._health_check())
            task.add_done_callback(lambda t: t.result() if not t.cancelled() and not t.exception() else None)

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
        Attempt via MCP Server (internal bridge)

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
            result = cast(
                AgentResponse,
                await self.circuit_manager.call_with_breaker(
                    "mcp_server", self._execute_mcp_call, request, start_time
                ),
            )
            return result

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
        Attempt via Direct API (with tool calling and circuit breaker support)

        Phase 1: Wrapped with circuit breaker for automatic failure isolation

        Improvements (based on agent self-improvement analysis):
        - Exponential backoff for retry (3 attempts)
        - Increased timeout for complex tasks (300 sec)
        - Detailed logging of each attempt
        - Circuit breaker protection from cascading failures
        """
        start_time = time.time()

        # Determine circuit breaker name
        breaker_name = "deepseek_api" if request.agent_type == AgentType.DEEPSEEK else "perplexity_api"

        # Wrap API call with circuit breaker
        try:
            response = cast(
                AgentResponse,
                await self.circuit_manager.call_with_breaker(
                    breaker_name, self._execute_api_call, request, start_time
                ),
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
        last_exception: Exception | None = None
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
                            from backend.agents.cost_tracker import record_api_cost

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
        """Attempt with backup API key"""
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

    # _execute_tool_with_retry, _execute_mcp_tool, _execute_local_tool
    # → moved to _tool_mixin.py

    # _get_api_url, _get_headers, _get_retry_after_seconds,
    # get_key_pool_snapshot, stream_request,
    # _extract_content, _extract_reasoning_content, _save_reasoning_log,
    # _clear_reasoning_in_messages, _extract_citations, _extract_token_usage
    # → moved to _api_mixin.py

    # _health_check, get_stats, _calculate_autonomy_score → moved to _health_mixin.py

    # =========================================================================
    # HIGH-LEVEL API CONVENIENCE METHODS
    # =========================================================================
    # query_deepseek() and query_perplexity() → moved to _query_mixin.py
    # They are available via QueryMixin inheritance.


# =============================================================================
# CONVENIENCE METHODS
# =============================================================================

# Global instance
_agent_interface: UnifiedAgentInterface | None = None


def get_agent_interface() -> UnifiedAgentInterface:
    """Get global instance (singleton)"""
    global _agent_interface
    if _agent_interface is None:
        _agent_interface = UnifiedAgentInterface()
    return _agent_interface


async def analyze_with_deepseek(code: str, focus: str = "all") -> AgentResponse:
    """Quick method for code analysis via DeepSeek"""
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
    """Quick method for querying Perplexity"""
    interface = get_agent_interface()
    request = AgentRequest(agent_type=AgentType.PERPLEXITY, task_type="search", prompt=question)
    return await interface.send_request(request)
