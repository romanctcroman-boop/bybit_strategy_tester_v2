"""
Streaming WebSocket API for Real-time AI Responses

Provides WebSocket endpoint for streaming AI agent responses,
including real-time Chain-of-Thought reasoning from DeepSeek V3.2.

Features:
- Rate limiting: 60 messages/min per client, 10 connections/min per IP
- Graceful connection management
- Real-time Chain-of-Thought from DeepSeek V3.2
"""

import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger

router = APIRouter(prefix="/ws/v1/stream", tags=["Streaming AI"])


class WebSocketRateLimiter:
    """
    Rate limiter for WebSocket connections.

    Uses sliding window algorithm to limit:
    - Messages per minute per client
    - New connections per minute per IP
    """

    def __init__(
        self,
        max_messages_per_minute: int = 60,
        max_connections_per_minute: int = 10,
    ):
        self.max_messages_per_minute = max_messages_per_minute
        self.max_connections_per_minute = max_connections_per_minute
        # {client_id: [timestamps]}
        self._message_timestamps: dict[str, list[float]] = defaultdict(list)
        # {ip: [timestamps]}
        self._connection_timestamps: dict[str, list[float]] = defaultdict(list)

    def _clean_old_timestamps(self, timestamps: list[float], window_seconds: int = 60) -> list[float]:
        """Remove timestamps older than window."""
        cutoff = time.time() - window_seconds
        return [ts for ts in timestamps if ts > cutoff]

    def check_message_rate(self, client_id: str) -> tuple[bool, str | None]:
        """
        Check if client can send a message.

        Returns:
            (allowed, error_message)
        """
        now = time.time()
        self._message_timestamps[client_id] = self._clean_old_timestamps(self._message_timestamps[client_id])

        if len(self._message_timestamps[client_id]) >= self.max_messages_per_minute:
            return (
                False,
                f"Rate limit exceeded: max {self.max_messages_per_minute} messages/minute",
            )

        self._message_timestamps[client_id].append(now)
        return True, None

    def check_connection_rate(self, client_ip: str) -> tuple[bool, str | None]:
        """
        Check if IP can create a new connection.

        Returns:
            (allowed, error_message)
        """
        now = time.time()
        self._connection_timestamps[client_ip] = self._clean_old_timestamps(self._connection_timestamps[client_ip])

        if len(self._connection_timestamps[client_ip]) >= self.max_connections_per_minute:
            return (
                False,
                f"Too many connections: max {self.max_connections_per_minute}/minute",
            )

        self._connection_timestamps[client_ip].append(now)
        return True, None

    def cleanup_client(self, client_id: str):
        """Clean up rate limit data for disconnected client."""
        self._message_timestamps.pop(client_id, None)


# Global rate limiter instance
ws_rate_limiter = WebSocketRateLimiter()


class StreamingConnectionManager:
    """Manage WebSocket connections for streaming with rate limiting"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.client_ips: dict[str, str] = {}  # client_id -> IP
        self._shutting_down: bool = False

    async def connect(self, websocket: WebSocket, client_id: str) -> tuple[bool, str | None]:
        """
        Accept WebSocket connection with rate limiting.

        Returns:
            (success, error_message)
        """
        # Reject new connections during shutdown
        if self._shutting_down:
            return False, "Server is shutting down"

        # Get client IP for rate limiting
        client_ip = websocket.client.host if websocket.client else "unknown"

        # Check connection rate limit
        allowed, error = ws_rate_limiter.check_connection_rate(client_ip)
        if not allowed:
            logger.warning(f"🚫 Connection rate limit for IP {client_ip}: {error}")
            return False, error

        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.client_ips[client_id] = client_ip
        logger.info(f"🔌 Streaming client connected: {client_id} (IP: {client_ip})")
        return True, None

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            self.client_ips.pop(client_id, None)
            ws_rate_limiter.cleanup_client(client_id)
            logger.info(f"🔌 Streaming client disconnected: {client_id}")

    async def send_json(self, client_id: str, data: dict[str, Any]):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)

    def check_message_rate(self, client_id: str) -> tuple[bool, str | None]:
        """Check if client can send a message."""
        return ws_rate_limiter.check_message_rate(client_id)

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of WebSocket connections."""
        return {
            "active_connections": len(self.active_connections),
            "unique_ips": len(set(self.client_ips.values())),
            "shutting_down": self._shutting_down,
            "client_ids": list(self.active_connections.keys())[:10],  # First 10
        }

    async def graceful_shutdown(self, timeout_seconds: float = 5.0):
        """
        Gracefully close all WebSocket connections.

        Args:
            timeout_seconds: Max time to wait for connections to close
        """
        self._shutting_down = True
        logger.info(f"🔄 Graceful shutdown: closing {len(self.active_connections)} connections")

        # Notify all clients about shutdown
        close_tasks = []
        for client_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_json({"type": "shutdown", "message": "Server shutting down"})
                close_tasks.append(ws.close(code=1001, reason="Server shutdown"))
            except Exception as e:
                logger.warning(f"Error notifying client {client_id}: {e}")

        # Wait for connections to close with timeout
        if close_tasks:
            import asyncio

            try:
                await asyncio.wait_for(
                    asyncio.gather(*close_tasks, return_exceptions=True),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                logger.warning("Timeout waiting for WebSocket connections to close")

        # Clear all connections
        self.active_connections.clear()
        self.client_ips.clear()
        logger.info("✅ WebSocket graceful shutdown complete")


manager = StreamingConnectionManager()


@router.websocket("/agent/{client_id}")
async def streaming_agent_websocket(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for streaming AI agent responses.

    Connect: ws://localhost:8000/ws/v1/stream/agent/{client_id}

    Send message format:
    {
        "action": "query",
        "agent": "deepseek",  // or "perplexity"
        "task_type": "analyze",
        "prompt": "Your question here",
        "thinking_mode": true
    }

    Receive message formats:

    1. Reasoning chunk (DeepSeek Thinking Mode):
    {
        "type": "reasoning",
        "content": "Let me think about this step by step..."
    }

    2. Content chunk:
    {
        "type": "content",
        "content": "The answer is..."
    }

    3. Completion:
    {
        "type": "complete",
        "success": true,
        "latency_ms": 1234.56,
        "total_reasoning_length": 500,
        "total_content_length": 200
    }

    4. Error:
    {
        "type": "error",
        "error": "Error message"
    }

    5. Rate limit:
    {
        "type": "rate_limit",
        "error": "Rate limit exceeded: max 60 messages/minute"
    }
    """
    # Connect with rate limiting check
    success, error = await manager.connect(websocket, client_id)
    if not success:
        # Connection rejected due to rate limit - close immediately
        await websocket.close(code=1008, reason=error)  # 1008 = Policy Violation
        return

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            # Check message rate limit
            allowed, rate_error = manager.check_message_rate(client_id)
            if not allowed:
                await websocket.send_json({"type": "rate_limit", "error": rate_error})
                continue

            action = data.get("action")

            if action == "query":
                await handle_streaming_query(websocket, client_id, data)

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({"type": "error", "error": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"❌ WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)


async def handle_streaming_query(websocket: WebSocket, client_id: str, data: dict[str, Any]):
    """Handle a streaming query request"""
    from backend.agents.unified_agent_interface import (
        AgentRequest,
        AgentType,
        UnifiedAgentInterface,
    )

    agent_name = data.get("agent", "deepseek").lower()
    task_type = data.get("task_type", "analyze")
    prompt = data.get("prompt", "")
    thinking_mode = data.get("thinking_mode", True)

    if not prompt:
        await websocket.send_json({"type": "error", "error": "Empty prompt"})
        return

    # Map agent name to type
    agent_type = AgentType.DEEPSEEK if agent_name == "deepseek" else AgentType.PERPLEXITY

    # Create request
    request = AgentRequest(
        agent_type=agent_type,
        task_type=task_type,
        prompt=prompt,
        thinking_mode=thinking_mode,
        stream=True,
    )

    # Create callbacks for streaming
    async def on_reasoning_chunk(chunk: str):
        await websocket.send_json({"type": "reasoning", "content": chunk})

    async def on_content_chunk(chunk: str):
        await websocket.send_json({"type": "content", "content": chunk})

    # Execute streaming request
    agent = UnifiedAgentInterface()

    try:
        await websocket.send_json({"type": "start", "agent": agent_name})

        response = await agent.stream_request(
            request,
            on_reasoning_chunk=on_reasoning_chunk,
            on_content_chunk=on_content_chunk,
        )

        # Send completion message
        await websocket.send_json(
            {
                "type": "complete",
                "success": response.success,
                "latency_ms": response.latency_ms,
                "total_reasoning_length": len(response.reasoning_content or ""),
                "total_content_length": len(response.content),
                "error": response.error,
            }
        )

    except Exception as e:
        logger.error(f"❌ Streaming query failed: {e}")
        await websocket.send_json({"type": "error", "error": str(e)})


@router.get("/test")
async def test_streaming_endpoint():
    """Test endpoint to verify streaming router is registered"""
    return {
        "status": "ok",
        "message": "Streaming WebSocket endpoint available at /ws/v1/stream/agent/{client_id}",
        "features": [
            "Real-time Chain-of-Thought reasoning from DeepSeek V3.2",
            "Content streaming for both DeepSeek and Perplexity",
            "Session-based connections with unique client IDs",
            "Rate limiting: 60 messages/min, 10 connections/min per IP",
        ],
    }


@router.get("/health")
async def websocket_health():
    """
    Health check endpoint for WebSocket connections.

    Returns:
        Health status including active connections count.
    """
    status = manager.get_health_status()
    return {
        "status": "healthy" if not status["shutting_down"] else "shutting_down",
        "websocket": status,
        "rate_limiter": {
            "max_messages_per_minute": ws_rate_limiter.max_messages_per_minute,
            "max_connections_per_minute": ws_rate_limiter.max_connections_per_minute,
        },
    }


@router.get("/chat", response_class=HTMLResponse)
async def streaming_chat_ui():
    """Serve the streaming chat HTML UI"""
    html_path = Path(__file__).parent.parent.parent / "frontend" / "streaming-chat.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Chat UI not found</h1>", status_code=404)
