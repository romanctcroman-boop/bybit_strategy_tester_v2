import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

URL = "http://127.0.0.1:8000/mcp"

async def main():
    async with Client(transport=StreamableHttpTransport(URL)) as client:
        ok = await client.ping()
        print("ping:", ok)
        tools = await client.list_tools()
        print("tools:", [t.name for t in tools])

        # Optionally call the first tool with no args (may fail if args required)
        if tools:
            name = tools[0].name
            try:
                result = await client.call_tool(name, {})
                print("call result:", getattr(result, 'data', None))
            except Exception as e:
                print(f"tool '{name}' call error (expected if args required):", e)

if __name__ == "__main__":
    asyncio.run(main())
