"""
Ultra-simple direct test bypassing agent API
"""

import asyncio
import httpx
import json


async def test_direct_tool_calling():
    """Test tool calling by directly calling DeepSeek API"""
    
    print("Testing DeepSeek tool calling DIRECTLY")
    print("="*80)
    
    # Load API key
    import sys
    sys.path.insert(0, ".")
    from backend.agents.unified_agent_interface import UnifiedAgentInterface
    
    interface = UnifiedAgentInterface()
    keys = interface.key_manager.deepseek_keys
    if not keys:
        print("No DeepSeek keys available!")
        return
    
    api_key = keys[0].value
    
    # Prepare request
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Define tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the project",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The file to read"
                        }
                    },
                    "required": ["filename"]
                }
            }
        }
    ]
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Please use the read_file tool to read 'test.txt'"}
        ],
        "tools": tools,
        "temperature": 0.0
    }
    
    print("\nSending request to DeepSeek API...")
    print(f"Tools defined: {len(tools)}")
    print()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            print("Response received:")
            print(json.dumps(data, indent=2))
            
            # Check for tool_calls
            message = data.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls")
            
            if tool_calls:
                print(f"\n✓ SUCCESS! DeepSeek called {len(tool_calls)} tools:")
                for tc in tool_calls:
                    print(f"  - {tc.get('function', {}).get('name')}")
            else:
                print("\n✗ FAILED! DeepSeek did NOT call any tools")
                print(f"Message content: {message.get('content')}")
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_direct_tool_calling())
