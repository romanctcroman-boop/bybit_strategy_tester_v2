"""
Simple Tool Calling Test

Проверка tool calling через /api/v1/agent/send
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_tool_calling():
    """Простой тест tool calling"""
    
    base_url = "http://127.0.0.1:8000"
    
    print("="*80)
    print("🧪 SIMPLE TOOL CALLING TEST")
    print("="*80)
    print()
    
    # Payload для агента (correct format)
    payload = {
        "from_agent": "copilot",
        "to_agent": "deepseek",
        "content": "Read the file backend/api/app.py and list all MCP tools you find",
        "message_type": "query",
        "context": {
            "use_file_access": True,  # Включаем file access tools
            "task_type": "code_analysis"
        }
    }
    
    print("📤 Sending request to /api/v1/agent/send")
    print(f"Target: deepseek")
    print(f"File access: enabled")
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
                print("✅ SUCCESS")
                print("="*80)
                print()
                print(f"Status: {result.get('status')}")
                print(f"Agent: {result.get('agent_used')}")
                print(f"Channel: {result.get('channel')}")
                print()
                print("Response:")
                print("-"*80)
                print(result.get('response', 'No response'))
                print("-"*80)
                print()
                
                # Сохранить в файл
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"TOOL_CALLING_TEST_{timestamp}.json"
                
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                
                print(f"📁 Results saved to: {filename}")
                print()
                
                # Анализ ответа
                response_text = result.get('response', '').lower()
                keywords = ['mcp_read_project_file', 'mcp_list_project_structure', 'app.py', 'file']
                found = [kw for kw in keywords if kw in response_text]
                
                if found:
                    print(f"✅ Response contains tool-related keywords: {', '.join(found)}")
                else:
                    print("⚠️  Response does not mention tools or file content")
                
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_tool_calling())
