"""
Test with direct log monitoring
"""

import asyncio
import httpx
import json


async def test_with_monitoring():
    """Test and monitor logs"""
    
    base_url = "http://127.0.0.1:8000"
    
    print("Testing with log monitoring")
    print("="*80)
    
    # Check health first
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{base_url}/api/v1/health")
            print(f"Backend is running: {response.status_code}")
        except Exception as e:
            print(f"Backend not accessible: {e}")
            return
    
    # Send test request
    payload = {
        "from_agent": "copilot",
        "to_agent": "deepseek",
        "content": "Use mcp_read_project_file to read backend/api/app.py",
        "context": {
            "use_file_access": True
        }
    }
    
    print("\nSending agent request...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(
                f"{base_url}/api/v1/agent/send",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                print("="*80)
                print("RESPONSE RECEIVED")
                print("="*80)
                print(json.dumps(result, indent=2))
            else:
                print(f"Request failed: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_with_monitoring())
