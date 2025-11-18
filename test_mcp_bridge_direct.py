#!/usr/bin/env python
"""Direct MCP bridge invocation test (no HTTP server required)."""
import asyncio
from loguru import logger

async def main():
    try:
        from backend.mcp.mcp_integration import ensure_mcp_bridge_initialized, get_mcp_bridge
    except Exception as e:
        logger.error(f"Failed to import bridge: {e}")
        return
    await ensure_mcp_bridge_initialized()
    bridge = get_mcp_bridge()
    tools = await bridge.list_tools()
    logger.info(f"Tools loaded: {[t['name'] for t in tools]}")
    if not tools:
        logger.error("No tools loaded; aborting")
        return
    result = await bridge.call_tool("mcp_read_project_file", {"file_path": "backend/mcp/mcp_integration.py"})
    logger.info(f"Call result: success={result.get('success')} keys={list(result.keys())}")
    if result.get("success"):
        content_preview = result.get("content", "")[:150]
        logger.info(f"Content preview: {content_preview}...")
    else:
        logger.error(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
