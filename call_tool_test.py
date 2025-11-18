import httpx, asyncio

async def run():
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post('http://127.0.0.1:8000/mcp/bridge/tools/call', json={
            'name': 'mcp_read_project_file',
            'arguments': {'file_path': 'backend/mcp/mcp_integration.py'}
        })
        print('Status:', resp.status_code)
        print('JSON:', resp.json())

asyncio.run(run())
