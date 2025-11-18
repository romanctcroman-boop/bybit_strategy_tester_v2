import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

URL = "http://127.0.0.1:8000/mcp"

async def main():
    async with Client(transport=StreamableHttpTransport(URL)) as client:
        print("ping:", await client.ping())
        tools = await client.list_tools()
        names = [t.name for t in tools]
        print("tools:", names)

        # Choose a tool that accepts 'content'
        target = None
        for n in names:
            if "send_to_deepseek" in n:
                target = n
                break
        target = target or names[0]
        print("calling:", target)

        # Call with valid arguments to record latency
        result = await client.call_tool(target, {"content": "Latency probe from test_mcp_latency"})
        print("result keys:", list(getattr(result, 'data', {}) or {}))

if __name__ == "__main__":
    asyncio.run(main())
