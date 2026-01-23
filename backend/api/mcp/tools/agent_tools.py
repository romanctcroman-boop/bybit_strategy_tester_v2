"""
MCP Agent-to-Agent Communication Tools

Provides MCP tools for inter-agent communication via DeepSeek and Perplexity.
Extracted from app.py for better modularity.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List

from backend.agents.agent_to_agent_communicator import (
    AgentMessage,
    AgentType,
    MessageType,
    get_communicator,
)
from backend.api.mcp.circuit_breaker import (
    CircuitBreaker,
    mcp_semaphore,
    CB_THRESHOLD,
    CB_TIMEOUT,
)
from backend.api.mcp_errors import (
    AgentUnavailableError,
    exception_to_mcp_error,
)

# Try to import metrics (may not be available)
try:
    from backend.monitoring.phase5_collector import (
        MCP_TOOL_CALLS,
        MCP_TOOL_DURATION,
        MCP_TOOL_ERRORS,
    )

    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False
    MCP_TOOL_CALLS = None
    MCP_TOOL_DURATION = None
    MCP_TOOL_ERRORS = None

logger = logging.getLogger(__name__)

# Per-tool circuit breakers
_circuit_breakers: Dict[str, CircuitBreaker] = {
    "send_to_deepseek": CircuitBreaker(CB_THRESHOLD, CB_TIMEOUT),
    "send_to_perplexity": CircuitBreaker(CB_THRESHOLD, CB_TIMEOUT),
    "get_consensus": CircuitBreaker(CB_THRESHOLD, CB_TIMEOUT),
}


def _update_metrics(tool: str, success: bool, duration: float, error_type: str = None):
    """Update Prometheus metrics if available."""
    if not _METRICS_AVAILABLE:
        return
    try:
        MCP_TOOL_CALLS.labels(tool=tool, success=str(success).lower()).inc()
        MCP_TOOL_DURATION.labels(tool=tool).observe(duration)
        if error_type:
            MCP_TOOL_ERRORS.labels(tool=tool, error_type=error_type).inc()
    except Exception as e:
        logger.warning(f"Failed to update metrics: {e}")


async def send_to_deepseek(
    content: str, conversation_id: str = None, context: dict = None
) -> dict:
    """
    Send message to DeepSeek agent via MCP.

    Args:
        content: Message content to send
        conversation_id: Optional conversation ID for context
        context: Optional context dictionary

    Returns:
        dict with success, message_id, content, conversation_id, iteration
    """
    start_time = time.perf_counter()
    cb = _circuit_breakers["send_to_deepseek"]

    # Circuit breaker guard
    if cb.is_open():
        _update_metrics("send_to_deepseek", False, 0, "CircuitOpen")
        return AgentUnavailableError(
            "Circuit breaker open for send_to_deepseek"
        ).to_dict()

    try:
        communicator = get_communicator()

        # Mark context as MCP tool call to prevent recursion
        if context is None:
            context = {}
        context["from_mcp_tool"] = True

        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType.COPILOT,
            to_agent=AgentType.DEEPSEEK,
            message_type=MessageType.QUERY,
            content=content,
            context=context,
            conversation_id=conversation_id or str(uuid.uuid4()),
        )

        # Semaphore + timeout for deadlock prevention
        async with mcp_semaphore:
            async with asyncio.timeout(120):
                response = await communicator.route_message(message)

        result = {
            "success": True,
            "message_id": response.message_id,
            "content": response.content,
            "conversation_id": response.conversation_id,
            "iteration": response.iteration,
        }

        duration = time.perf_counter() - start_time
        _update_metrics("send_to_deepseek", True, duration)
        cb.reset()
        return result

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"MCP DeepSeek tool error: {e}")

        mcp_error = exception_to_mcp_error(e)
        cb.record_failure()
        _update_metrics("send_to_deepseek", False, duration, mcp_error.error_type)
        return mcp_error.to_dict()


async def send_to_perplexity(
    content: str, conversation_id: str = None, context: dict = None
) -> dict:
    """
    Send message to Perplexity agent via MCP.

    Args:
        content: Message content to send
        conversation_id: Optional conversation ID for context
        context: Optional context dictionary

    Returns:
        dict with success, message_id, content, conversation_id, iteration
    """
    start_time = time.perf_counter()
    cb = _circuit_breakers["send_to_perplexity"]

    # Circuit breaker guard
    if cb.is_open():
        _update_metrics("send_to_perplexity", False, 0, "CircuitOpen")
        return AgentUnavailableError(
            "Circuit breaker open for send_to_perplexity"
        ).to_dict()

    try:
        communicator = get_communicator()

        # Mark context as MCP tool call to prevent recursion
        if context is None:
            context = {}
        context["from_mcp_tool"] = True

        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType.COPILOT,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content=content,
            context=context,
            conversation_id=conversation_id or str(uuid.uuid4()),
        )

        # Semaphore + timeout for deadlock prevention
        async with mcp_semaphore:
            async with asyncio.timeout(120):
                response = await communicator.route_message(message)

        result = {
            "success": True,
            "message_id": response.message_id,
            "content": response.content,
            "conversation_id": response.conversation_id,
            "iteration": response.iteration,
        }

        duration = time.perf_counter() - start_time
        _update_metrics("send_to_perplexity", True, duration)
        cb.reset()
        return result

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"MCP Perplexity tool error: {e}")

        mcp_error = exception_to_mcp_error(e)
        cb.record_failure()
        _update_metrics("send_to_perplexity", False, duration, mcp_error.error_type)
        return mcp_error.to_dict()


async def get_consensus(question: str, agents: List[str] = None) -> dict:
    """
    Get consensus from multiple agents.

    Args:
        question: The question to ask all agents
        agents: List of agent names (default: ["deepseek", "perplexity"])

    Returns:
        dict with success, consensus, confidence_score, conversation_id, individual_responses
    """
    start_time = time.perf_counter()
    cb = _circuit_breakers["get_consensus"]

    # Circuit breaker guard
    if cb.is_open():
        _update_metrics("get_consensus", False, 0, "CircuitOpen")
        return AgentUnavailableError("Circuit breaker open for get_consensus").to_dict()

    try:
        if agents is None:
            agents = ["deepseek", "perplexity"]

        communicator = get_communicator()
        agent_types = [AgentType(a) for a in agents]

        # Semaphore + extended timeout for multi-agent consensus
        async with mcp_semaphore:
            async with asyncio.timeout(180):
                result = await communicator.parallel_consensus(
                    question=question, agents=agent_types
                )

        response = {
            "success": True,
            "consensus": result["consensus"],
            "confidence_score": result["confidence_score"],
            "conversation_id": result["conversation_id"],
            "individual_responses": result["individual_responses"],
        }

        duration = time.perf_counter() - start_time
        _update_metrics("get_consensus", True, duration)
        cb.reset()
        return response

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"MCP Consensus tool error: {e}")

        mcp_error = exception_to_mcp_error(e)
        cb.record_failure()
        _update_metrics("get_consensus", False, duration, mcp_error.error_type)
        return mcp_error.to_dict()


def register_agent_tools(mcp):
    """
    Register all agent tools with the MCP server.

    Args:
        mcp: The MCP server instance (FastMCP or _DummyMCP)
    """

    @mcp.tool()
    async def mcp_agent_to_agent_send_to_deepseek(
        content: str, conversation_id: str = None, context: dict = None
    ) -> dict:
        """Send message to DeepSeek agent via MCP"""
        return await send_to_deepseek(content, conversation_id, context)

    @mcp.tool()
    async def mcp_agent_to_agent_send_to_perplexity(
        content: str, conversation_id: str = None, context: dict = None
    ) -> dict:
        """Send message to Perplexity agent via MCP"""
        return await send_to_perplexity(content, conversation_id, context)

    @mcp.tool()
    async def mcp_agent_to_agent_get_consensus(
        question: str, agents: list = None
    ) -> dict:
        """Get consensus from multiple agents"""
        return await get_consensus(question, agents)

    logger.info("✅ MCP Agent tools registered")


__all__ = [
    "send_to_deepseek",
    "send_to_perplexity",
    "get_consensus",
    "register_agent_tools",
]
