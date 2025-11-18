import asyncio
import httpx
import json

async def main():
    url = "http://127.0.0.1:8000/mcp"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        r = await client.post(url, json=payload)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
        if r.status_code == 200:
            try:
                data = r.json()
                print(json.dumps(data, indent=2))
            except Exception as e:
                print(f"JSON decode error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
