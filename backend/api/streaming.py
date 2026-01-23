# -*- coding: utf-8 -*-
"""
Streaming WebSocket API for Real-time AI Responses

Provides WebSocket endpoint for streaming AI agent responses,
including real-time Chain-of-Thought reasoning from DeepSeek V3.2.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger

router = APIRouter(prefix="/ws/v1/stream", tags=["Streaming AI"])


class StreamingConnectionManager:
    """Manage WebSocket connections for streaming"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"🔌 Streaming client connected: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"🔌 Streaming client disconnected: {client_id}")

    async def send_json(self, client_id: str, data: dict[str, Any]):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)


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
    """
    await manager.connect(websocket, client_id)

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "query":
                await handle_streaming_query(websocket, client_id, data)

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json(
                    {"type": "error", "error": f"Unknown action: {action}"}
                )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"❌ WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)


async def handle_streaming_query(
    websocket: WebSocket, client_id: str, data: dict[str, Any]
):
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
    agent_type = (
        AgentType.DEEPSEEK if agent_name == "deepseek" else AgentType.PERPLEXITY
    )

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
        ],
    }


@router.get("/chat", response_class=HTMLResponse)
async def streaming_chat_ui():
    """Serve the streaming chat HTML UI"""
    html_path = Path(__file__).parent.parent.parent / "frontend" / "streaming-chat.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Chat UI not found</h1>", status_code=404)
