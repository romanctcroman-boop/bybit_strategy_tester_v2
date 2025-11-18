"""
Test Direct API Agent Communication
Validates internal agent requests through /api/v1/agent/send
"""
import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8000"

async def test_direct_api():
    """Test Direct API endpoints"""
    results = {
        "deepseek": {"success": False, "message_id": None, "error": None},
        "perplexity": {"success": False, "message_id": None, "error": None}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test DeepSeek
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/agent/send",
                json={
                    "from_agent": "copilot",
                    "to_agent": "deepseek",
                    "content": "Test message: MCP hardening implementation complete. Please confirm receipt.",
                    "message_type": "query"
                }
            )
            if response.status_code == 200:
                data = response.json()
                results["deepseek"]["success"] = True
                results["deepseek"]["message_id"] = data.get("message_id")
            else:
                results["deepseek"]["error"] = f"HTTP {response.status_code}: {response.text}"
        except Exception as e:
            results["deepseek"]["error"] = str(e)
        
        # Test Perplexity
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/agent/send",
                json={
                    "from_agent": "copilot",
                    "to_agent": "perplexity",
                    "content": "Test message: MCP hardening implementation complete. Please confirm receipt.",
                    "message_type": "query"
                }
            )
            if response.status_code == 200:
                data = response.json()
                results["perplexity"]["success"] = True
                results["perplexity"]["message_id"] = data.get("message_id")
            else:
                results["perplexity"]["error"] = f"HTTP {response.status_code}: {response.text}"
        except Exception as e:
            results["perplexity"]["error"] = str(e)
    
    # Print results
    print("\n=== Direct API Test Results ===")
    for agent, result in results.items():
        status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
        print(f"\n{agent.upper()}: {status}")
        if result["success"]:
            print(f"  Message ID: {result['message_id']}")
        else:
            print(f"  Error: {result['error']}")
    
    success_count = sum(1 for r in results.values() if r["success"])
    print(f"\n=== Summary: {success_count}/2 agents successful ===")
    
    return results

if __name__ == "__main__":
    asyncio.run(test_direct_api())
