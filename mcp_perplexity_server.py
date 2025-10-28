#!/usr/bin/env python3
"""
MCP Server for Perplexity AI Integration
Implements Model Context Protocol for VS Code GitHub Copilot
"""
import os
import sys
import json
import asyncio
from typing import Any
import httpx

# Перplexity API endpoint
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


async def call_perplexity(query: str, api_key: str) -> dict[str, Any]:
    """Call Perplexity AI API with a query."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful research assistant. Provide accurate, concise answers with sources when possible."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.2,
        "top_p": 0.9,
        "return_citations": True,
        "search_domain_filter": ["github.com", "stackoverflow.com", "docs.python.org"],
        "return_images": False,
        "return_related_questions": False,
        "search_recency_filter": "month",
        "top_k": 0,
        "stream": False,
        "presence_penalty": 0,
        "frequency_penalty": 1
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            PERPLEXITY_API_URL,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()


async def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Handle MCP protocol requests."""
    method = request.get("method")
    params = request.get("params", {})
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "tools": {
                        "search": {
                            "description": "Search and research using Perplexity AI",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Search query or research question"
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    }
                },
                "serverInfo": {
                    "name": "perplexity-mcp-server",
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name == "search":
            api_key = os.getenv("PERPLEXITY_API_KEY")
            if not api_key:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": "PERPLEXITY_API_KEY environment variable not set"
                    }
                }
            
            query = arguments.get("query", "")
            try:
                result = await call_perplexity(query, api_key)
                
                # Extract answer and citations
                answer = result["choices"][0]["message"]["content"]
                citations = result.get("citations", [])
                
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"{answer}\n\n**Sources:**\n" + "\n".join(f"- {cite}" for cite in citations) if citations else answer
                            }
                        ]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Perplexity API error: {str(e)}"
                    }
                }
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "tools": [
                    {
                        "name": "search",
                        "description": "Search and research using Perplexity AI",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query or research question"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
            }
        }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


async def main():
    """Main MCP server loop - reads from stdin, writes to stdout."""
    # Read requests from stdin
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = await handle_request(request)
            # Write response to stdout
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error: Invalid JSON"
                }
            }
            print(json.dumps(error_response), flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    # Check for API key
    if not os.getenv("PERPLEXITY_API_KEY"):
        print(json.dumps({
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": "PERPLEXITY_API_KEY environment variable not set"
            }
        }), flush=True)
        sys.exit(1)
    
    # Run async main loop
    asyncio.run(main())
