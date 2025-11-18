"""Custom MCP bridge HTTP routes

Provides simplified endpoints decoupled from FastMCP's internal HTTP schema.
Path namespace: /mcp/bridge/* (leaves existing /mcp/* untouched)

Endpoints:
GET  /mcp/bridge/health -> {status, tool_count}
GET  /mcp/bridge/tools  -> list of tools
POST /mcp/bridge/tools/call {name, arguments} -> tool execution result

Will be included in app in a later task (Task 9). Safe to import even if
bridge not yet initialized; lazy init performed per request.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

from backend.mcp.mcp_integration import get_mcp_bridge

router = APIRouter(prefix="/mcp/bridge", tags=["mcp-bridge"])


class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] | None = None


@router.get("/health")
async def bridge_health():
    bridge = get_mcp_bridge()
    await bridge.initialize()
    tool_list = await bridge.list_tools()
    # Correlation ID injection
    try:
        from backend.middleware.correlation_id import get_correlation_id
        corr_id = get_correlation_id()
    except Exception:
        corr_id = None
    resp = {
        "status": "ready" if len(tool_list) > 0 else "initializing",
        "tool_count": len(tool_list),
        "tools": [t["name"] for t in tool_list],
    }
    if corr_id:
        resp["correlation_id"] = corr_id
    return resp


@router.get("/tools")
async def list_tools():
    bridge = get_mcp_bridge()
    tools = await bridge.list_tools()
    try:
        from backend.middleware.correlation_id import get_correlation_id
        corr_id = get_correlation_id()
    except Exception:
        corr_id = None
    resp = {"success": True, "tools": tools, "count": len(tools)}
    if corr_id:
        resp["correlation_id"] = corr_id
    return resp


@router.post("/tools/call")
async def call_tool(payload: ToolCallRequest):
    bridge = get_mcp_bridge()
    result = await bridge.call_tool(payload.name, payload.arguments)
    if not result.get("success"):
        # Provide HTTP error semantics while returning structured body
        raise HTTPException(status_code=400, detail=result)
    # result already includes correlation_id if available
    return result
