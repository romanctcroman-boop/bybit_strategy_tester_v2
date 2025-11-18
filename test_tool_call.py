import httpx, asyncio, json

async def main():
    url = 'http://127.0.0.1:8000/mcp/bridge/tools/call'
    payload = {"name": "mcp_read_project_file", "arguments": {"file_path": "backend/mcp/mcp_integration.py"}}
    headers = {"X-Request-ID": "cid-tool-002"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=payload, headers=headers)
    print('STATUS', r.status_code)
    print('ECHO', r.headers.get('X-Request-ID'))
    print('BODY', json.dumps(r.json(), indent=2)[:500])

if __name__ == '__main__':
    asyncio.run(main())
