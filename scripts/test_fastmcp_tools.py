"""Test how to access registered tools from FastMCP instance"""
import asyncio
from fastmcp import FastMCP

m = FastMCP('test')

@m.tool()
def test_tool(x: str) -> str:
    """Test tool"""
    return x

async def test():
    # Try the FastMCP-level method
    if hasattr(m, 'get_tools'):
        tools = await m.get_tools()
        print(f"mcp.get_tools() type: {type(tools)}")
        print(f"mcp.get_tools() result: {tools}")
        if isinstance(tools, list) and len(tools) > 0:
            print(f"first tool type: {type(tools[0])}")
            print(f"first tool: {tools[0]}")
            if hasattr(tools[0], 'name'):
                print(f"tool names: {[t.name for t in tools]}")
            else:
                print(f"tools are strings: {tools}")

asyncio.run(test())
