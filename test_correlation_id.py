import httpx, asyncio

async def main():
    url = 'http://127.0.0.1:8000/mcp/bridge/health'
    headers = {'X-Request-ID': 'cid-test-001'}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=headers)
        print('STATUS', r.status_code)
        print('ECHO', r.headers.get('X-Request-ID'))
        print('BODY_START', r.text[:400])
    except Exception as e:
        print('ERROR', e)

if __name__ == '__main__':
    asyncio.run(main())
