import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=30) as client:
        print('1. Testing /mcp/bridge/health')
        r = await client.get('http://127.0.0.1:8000/mcp/bridge/health')
        print(f'  Status: {r.status_code}')
        print(f'  Response: {r.json()}')
        
        print('\n2. Testing /mcp/bridge/tools')
        r = await client.get('http://127.0.0.1:8000/mcp/bridge/tools')
        print(f'  Status: {r.status_code}')
        data = r.json()
        print(f'  Tools: {len(data["tools"])} tools')
        print(f'  Names: {[t["name"] for t in data["tools"]]}')
        
        print('\n3. Testing /mcp/bridge/tools/call')
        r = await client.post('http://127.0.0.1:8000/mcp/bridge/tools/call', json={
            'tool_name': 'mcp_read_project_file',
            'arguments': {'file_path': 'backend/mcp/mcp_integration.py'}
        })
        print(f'  Status: {r.status_code}')
        data = r.json()
        if data.get('success'):
            print(f'  Success! Content length: {len(data["content"])} chars')
        else:
            print(f'  Error: {data.get("error")}')

asyncio.run(test())
