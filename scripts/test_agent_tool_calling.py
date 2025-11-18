"""
Test Agent Tool Calling - Full Integration

Тест tool calling функциональности агентов с MCP file access tools.
Агент должен:
1. Получить задачу с use_file_access=True
2. Автоматически использовать mcp_read_project_file и другие tools
3. Вернуть результат анализа
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_agent_tool_calling():
    """Тест tool calling с DeepSeek"""
    
    base_url = "http://127.0.0.1:8000"
    
    print("="*80)
    print("🧪 TESTING AGENT TOOL CALLING")
    print("="*80)
    print()
    print("Task: Agent uses mcp_read_project_file to analyze backend/api/app.py")
    print("Expected: Agent calls tool, receives file content, analyzes it")
    print()
    print("="*80)
    print()
    
    # Простая задача с file access
    task = """
Analyze the MCP tools defined in backend/api/app.py.

Please:
1. Use mcp_read_project_file to read "backend/api/app.py"
2. Find all @mcp.tool() decorators
3. List all MCP tools with their descriptions
4. Provide a brief summary of what each tool does

You have access to:
- mcp_read_project_file(file_path, max_size_kb)
- mcp_list_project_structure(directory, max_depth, include_hidden)
- mcp_analyze_code_quality(file_path, tools)

Use these tools to complete the task!
"""

    async with httpx.AsyncClient(timeout=180.0) as client:
        
        print("📤 Sending task to DeepSeek with use_file_access=True...")
        print()
        
        try:
            request = {
                "from_agent": "copilot",
                "to_agent": "deepseek",
                "content": task,
                "context": {
                    "task_type": "code_analysis",
                    "use_file_access": True,  # ← ENABLE TOOL CALLING
                    "priority": "high"
                }
            }
            
            response = await client.post(
                f"{base_url}/api/v1/agent/send",
                json=request
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Response received (HTTP {response.status_code})")
                print(f"   Message ID: {data.get('message_id', 'N/A')}")
                print(f"   Conversation ID: {data.get('conversation_id', 'N/A')}")
                print()
                print("="*80)
                print("AGENT RESPONSE:")
                print("="*80)
                print()
                
                content = data.get('content', '')
                print(content)
                print()
                
                # Save response
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"AGENT_TOOL_CALLING_TEST_{timestamp}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"📝 Full response saved to {filename}")
                print()
                
                # Check if tools were used
                print("="*80)
                print("TOOL USAGE ANALYSIS:")
                print("="*80)
                print()
                
                if "mcp_read_project_file" in content or "backend/api/app.py" in content:
                    print("✅ Agent appears to have used file access tools!")
                    print("   Evidence: Response mentions backend/api/app.py or tool usage")
                else:
                    print("⚠️  Cannot confirm tool usage from response content")
                    print("   Response may not explicitly mention tool calls")
                
                print()
                
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print("="*80)
    print("✅ Test completed!")
    print("="*80)
    print()
    print("Expected behavior:")
    print("1. DeepSeek receives task with use_file_access=True")
    print("2. DeepSeek API returns tool_calls in response")
    print("3. Our backend executes mcp_read_project_file")
    print("4. Result is sent back to DeepSeek")
    print("5. DeepSeek analyzes file content and returns final response")
    print()
    print("If tools were NOT used:")
    print("- Check backend logs for '🔧 Agent requested N tool calls'")
    print("- Verify DeepSeek API supports function calling")
    print("- Check that tools are included in API request")


if __name__ == "__main__":
    asyncio.run(test_agent_tool_calling())
