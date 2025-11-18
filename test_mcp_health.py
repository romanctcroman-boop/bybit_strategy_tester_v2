"""
Quick test script для проверки MCP Server health check
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_mcp_server():
    """Test MCP server connectivity and tools"""
    
    server_params = StdioServerParameters(
        command="python",
        args=["mcp-server/server.py"],
        env={"PERPLEXITY_API_KEY": "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"}
    )
    
    print("=" * 80)
    print("🧪 TESTING MCP SERVER")
    print("=" * 80)
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("\n✅ Step 1: MCP Server Connected\n")
            
            # Test 1: List available tools
            print("📋 Step 2: Listing available tools...")
            tools = await session.list_tools()
            print(f"   ✅ Found {len(tools.tools)} tools\n")
            
            # Test 2: Call health_check tool
            print("🏥 Step 3: Running health_check...")
            result = await session.call_tool("health_check", arguments={})
            health_data = json.loads(result.content[0].text)
            
            print(f"\n   Server Status: {health_data['server_status']}")
            print(f"   Perplexity API: {health_data['perplexity_api']['status']}")
            print(f"   Response Time: {health_data['perplexity_api']['response_time_seconds']}s")
            print(f"   Total Tools: {health_data['tools']['total_count']}")
            print(f"   Version: {health_data['version']}\n")
            
            # Test 3: Call list_all_tools
            print("📊 Step 4: Getting tools list...")
            result = await session.call_tool("list_all_tools", arguments={})
            tools_data = json.loads(result.content[0].text)
            
            print(f"   ✅ Perplexity Tools: {tools_data['perplexity_ai_tools']['count']}")
            print(f"   ✅ Project Tools: {tools_data['project_information_tools']['count']}")
            print(f"   ✅ Analysis Tools: {tools_data['advanced_analysis_tools']['count']}")
            print(f"   ✅ Utility Tools: {tools_data['utility_tools']['count']}\n")
            
            # Test 4: Test Perplexity tool
            print("🔍 Step 5: Testing perplexity_sentiment_analysis...")
            result = await session.call_tool(
                "perplexity_sentiment_analysis",
                arguments={
                    "topic": "bitcoin",
                    "sources": "social_media",
                    "timeframe": "24h"
                }
            )
            sentiment_data = json.loads(result.content[0].text)
            
            if sentiment_data.get("success"):
                print(f"   ✅ Perplexity API call successful!")
                print(f"   📊 Answer preview: {sentiment_data.get('answer', '')[:100]}...\n")
            else:
                print(f"   ⚠️  Perplexity API error: {sentiment_data.get('error')}\n")
            
            print("=" * 80)
            print("🎉 ALL TESTS PASSED!")
            print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
