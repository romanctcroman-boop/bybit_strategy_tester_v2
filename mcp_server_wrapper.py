#!/usr/bin/env python3
"""
MCP Server Wrapper for Agent-to-Agent Backend

This script wraps the existing FastAPI backend to work as an MCP (Model Context Protocol) server.
GitHub Copilot will see this as a standard MCP server and can communicate with it.

Usage:
    python mcp_server_wrapper.py

Environment:
    - Backend must be running on http://localhost:8000
    - MCP server will expose agent tools to GitHub Copilot
"""

import asyncio
import json
import sys
from typing import Any, Dict, List
import httpx
from loguru import logger

# MCP Server Protocol (simplified implementation)
class MCPServer:
    """
    Model Context Protocol (MCP) Server
    
    Exposes Agent-to-Agent backend as MCP-compatible server
    that GitHub Copilot can discover and use.
    """
    
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url
        self.tools = self._register_tools()
        logger.info(f"🚀 MCP Server initialized with {len(self.tools)} tools")
    
    def _register_tools(self) -> List[Dict[str, Any]]:
        """Register available tools from Agent-to-Agent backend"""
        return [
            {
                "name": "send_to_deepseek",
                "description": "Send a message to DeepSeek AI agent for analysis, code review, or general queries",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The message/question to send to DeepSeek"
                        }
                    },
                    "required": ["content"]
                }
            },
            {
                "name": "send_to_perplexity",
                "description": "Send a message to Perplexity AI agent for web research and factual queries",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The search query or question for Perplexity"
                        }
                    },
                    "required": ["content"]
                }
            },
            {
                "name": "get_consensus",
                "description": "Get consensus opinion from multiple AI agents (DeepSeek + Perplexity)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The question to ask multiple agents"
                        }
                    },
                    "required": ["question"]
                }
            },
            {
                "name": "start_conversation",
                "description": "Start a multi-turn conversation between AI agents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "initial_message": {
                            "type": "string",
                            "description": "Initial message to start the conversation"
                        },
                        "participants": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of agents: deepseek, perplexity"
                        },
                        "max_turns": {
                            "type": "integer",
                            "description": "Maximum conversation turns",
                            "default": 5
                        }
                    },
                    "required": ["initial_message", "participants"]
                }
            }
        ]
    
    async def handle_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP method calls"""
        
        if method == "initialize":
            return await self._handle_initialize(params)
        
        elif method == "tools/list":
            return await self._handle_list_tools()
        
        elif method == "tools/call":
            return await self._handle_tool_call(params)
        
        else:
            return {"error": f"Unknown method: {method}"}
    
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request"""
        return {
            "protocolVersion": "0.1.0",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "agent-to-agent-bridge",
                "version": "1.0.0"
            }
        }
    
    async def _handle_list_tools(self) -> Dict[str, Any]:
        """Return list of available tools"""
        return {"tools": self.tools}
    
    async def _handle_tool_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool call by forwarding to backend"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"🔧 Tool call: {tool_name} with args: {arguments}")
        
        try:
            if tool_name == "send_to_deepseek":
                result = await self._send_message("deepseek", arguments["content"])
            
            elif tool_name == "send_to_perplexity":
                result = await self._send_message("perplexity", arguments["content"])
            
            elif tool_name == "get_consensus":
                result = await self._get_consensus(arguments["question"])
            
            elif tool_name == "start_conversation":
                result = await self._start_conversation(
                    arguments["initial_message"],
                    arguments["participants"],
                    arguments.get("max_turns", 5)
                )
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
            
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
        
        except Exception as e:
            logger.error(f"❌ Tool call error: {e}")
            return {"error": str(e)}
    
    async def _send_message(self, agent: str, content: str) -> Dict[str, Any]:
        """Send message to specific agent via backend API"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.backend_url}/api/v1/agent/message",
                json={
                    "from_agent": "copilot",
                    "to_agent": agent,
                    "content": content
                }
            )
            return response.json()
    
    async def _get_consensus(self, question: str) -> Dict[str, Any]:
        """Get consensus from multiple agents"""
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{self.backend_url}/api/v1/agent/consensus",
                json={
                    "question": question,
                    "agents": ["deepseek", "perplexity"]
                }
            )
            return response.json()
    
    async def _start_conversation(self, initial_message: str, participants: List[str], max_turns: int) -> Dict[str, Any]:
        """Start multi-turn conversation"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.backend_url}/api/v1/agent/conversation",
                json={
                    "initiator": "copilot",
                    "participants": participants,
                    "initial_message": initial_message,
                    "max_turns": max_turns,
                    "pattern": "collaborative"
                }
            )
            return response.json()
    
    async def run(self):
        """Run MCP server using stdio transport"""
        logger.info("🎯 MCP Server started (stdio transport)")
        logger.info(f"📡 Backend URL: {self.backend_url}")
        logger.info(f"🔧 Available tools: {len(self.tools)}")
        
        while True:
            try:
                # Read JSON-RPC request from stdin
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                
                if not line:
                    break
                
                request = json.loads(line.strip())
                logger.debug(f"📥 Request: {request}")
                
                # Handle request
                method = request.get("method")
                params = request.get("params", {})
                request_id = request.get("id")
                
                result = await self.handle_request(method, params)
                
                # Send response
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
                
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                logger.debug(f"📤 Response: {response}")
            
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON: {e}")
                continue
            
            except Exception as e:
                logger.error(f"❌ Server error: {e}")
                
                if 'request_id' in locals():
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32603, "message": str(e)}
                    }
                    sys.stdout.write(json.dumps(error_response) + "\n")
                    sys.stdout.flush()

async def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("🚀 Agent-to-Agent MCP Server")
    logger.info("=" * 80)
    
    # Check if backend is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/v1/agent/health")
            health = response.json()
            logger.success(f"✅ Backend healthy: {health}")
    except Exception as e:
        logger.error(f"❌ Backend not running: {e}")
        logger.info("💡 Start backend: py run_backend.py")
        sys.exit(1)
    
    # Start MCP server
    server = MCPServer()
    await server.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 MCP Server stopped")
