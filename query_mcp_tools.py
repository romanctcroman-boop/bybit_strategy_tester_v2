"""
Query Perplexity AI for comprehensive list of MCP tools and capabilities
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Import secure key manager
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "backend"))
from security.key_manager import get_decrypted_key

import asyncio
import httpx

PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")

if not PERPLEXITY_API_KEY:
    raise ValueError(
        "⚠️ SECURITY: PERPLEXITY_API_KEY not configured. "
        "Please add PERPLEXITY_API_KEY to .env file"
    )
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

async def query_mcp_tools():
    """Query Perplexity AI about MCP (Model Context Protocol) tools"""
    
    query = """
# Model Context Protocol (MCP) Tools and Capabilities

What are the available tools and capabilities in Model Context Protocol (MCP) servers? Specifically:

1. **Core MCP Protocol Features:**
   - What tools are typically available in MCP servers?
   - How do MCP tools differ from regular API endpoints?
   - What are the standard MCP tool categories?

2. **MCP Tool Types:**
   - Search and information retrieval tools
   - Code analysis and generation tools
   - Project management tools
   - Database and data manipulation tools
   - Integration tools (API clients, webhooks, etc.)

3. **Popular MCP Implementations:**
   - What MCP servers are commonly used in VS Code?
   - What tools does GitHub Copilot expose via MCP?
   - What tools does Perplexity AI provide via MCP?

4. **Custom MCP Tools:**
   - How to define custom MCP tools in Python (FastMCP)?
   - What are the best practices for MCP tool design?
   - How to document MCP tools for AI agents?

5. **MCP Tool Discovery:**
   - How do AI assistants discover available MCP tools?
   - What metadata should MCP tools provide?
   - How to list all available tools in an MCP server?

Provide specific examples with code snippets and real-world MCP server implementations.
Focus on practical, actionable information for developers building MCP servers.
"""
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "sonar-pro",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert on Model Context Protocol (MCP) and AI agent tool integration. Provide comprehensive, technical information with code examples."
                        },
                        {
                            "role": "user",
                            "content": query
                        }
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "return_related_questions": True,
                    "search_recency_filter": "month"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                citations = data.get("citations", [])
                
                print("=" * 80)
                print("PERPLEXITY AI: MCP TOOLS AND CAPABILITIES")
                print("=" * 80)
                print(answer)
                print("\n" + "=" * 80)
                print("SOURCES:")
                print("=" * 80)
                for i, url in enumerate(citations, 1):
                    print(f"{i}. {url}")
                
                # Save to file
                with open("PERPLEXITY_MCP_TOOLS_RESPONSE.md", "w", encoding="utf-8") as f:
                    f.write("# Perplexity AI: MCP Tools and Capabilities\n\n")
                    f.write("**Query Date:** October 29, 2025\n")
                    f.write("**Model:** sonar-pro\n\n")
                    f.write("---\n\n")
                    f.write("## Response\n\n")
                    f.write(answer)
                    f.write("\n\n---\n\n")
                    f.write("## Sources\n\n")
                    for i, url in enumerate(citations, 1):
                        f.write(f"{i}. {url}\n")
                
                print("\n✅ Response saved to PERPLEXITY_MCP_TOOLS_RESPONSE.md")
                return data
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

async def main():
    print("🚀 Querying Perplexity AI about MCP tools and capabilities...")
    print("📡 Using sonar-pro model for comprehensive technical analysis\n")
    
    await query_mcp_tools()

if __name__ == "__main__":
    asyncio.run(main())
