import asyncio
import httpx
import json

async def test_mcp_jsonrpc():
    async with httpx.AsyncClient(timeout=10) as client:
        # Test MCP JSON-RPC protocol
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        url = "http://127.0.0.1:8000/mcp"
        print(f"Testing MCP JSON-RPC at {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            r = await client.post(url, json=payload, follow_redirects=True)
            print(f"\nStatus: {r.status_code}")
            print(f"Headers: {dict(r.headers)}")
            print(f"Response: {r.text[:500]}")
            
            if r.status_code == 200:
                data = r.json()
                print(f"\nParsed response:")
                print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_jsonrpc())
