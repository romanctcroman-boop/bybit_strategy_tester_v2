"""
Agent Self-Analysis Test

Задача: Агенты самостоятельно анализируют свои возможности
используя новые MCP file access tools.

Что должны сделать агенты:
1. Прочитать backend/api/app.py и найти все MCP tools
2. Проанализировать свои собственные capabilities
3. Предложить улучшения если нужно
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_agent_self_analysis():
    """Агенты анализируют свои собственные возможности"""
    
    base_url = "http://127.0.0.1:8000"
    
    print("="*80)
    print("🤖 AGENT SELF-ANALYSIS TEST")
    print("="*80)
    print()
    print("Задача для агентов:")
    print("1. Использовать mcp_list_project_structure для навигации")
    print("2. Использовать mcp_read_project_file для чтения backend/api/app.py")
    print("3. Найти все зарегистрированные MCP tools")
    print("4. Проанализировать свои capabilities")
    print("5. Предложить улучшения если требуются")
    print()
    print("="*80)
    print()
    
    # Задача для DeepSeek
    deepseek_task = """
🔍 TASK: Self-Analysis of Agent Capabilities

**Your Mission:**
Analyze your own capabilities by examining the code that defines you.

**Step-by-step instructions:**

1. **Use `mcp_list_project_structure`** to navigate the project:
   - Start with directory="backend/api", max_depth=2
   - Find where MCP tools are defined

2. **Use `mcp_read_project_file`** to read the main API file:
   - Read "backend/api/app.py"
   - Search for all @mcp.tool() decorators
   - List all available MCP tools

3. **Analyze your capabilities:**
   - What can you do with these tools?
   - What are the security restrictions?
   - What file types can you read?
   - What directories are blocked?

4. **Self-evaluation:**
   - Are you truly "полнофункциональный агент" now?
   - What limitations still exist?
   - What improvements would you suggest?

5. **Code quality check:**
   - Use `mcp_analyze_code_quality` on "backend/api/app.py"
   - Report any issues found

**Expected output:**
- Complete list of your MCP tools
- Analysis of what each tool allows you to do
- Self-assessment of your capabilities
- Suggestions for improvements
- Code quality report

**Remember:** You are analyzing YOURSELF. Be honest about limitations!
"""

    # Задача для Perplexity
    perplexity_task = """
🔍 RESEARCH TASK: Agent Capabilities Best Practices

**Context:**
We have implemented file access tools for AI agents. Now we need to evaluate
if our implementation follows best practices.

**Research Questions:**

1. **Industry Standards:**
   - What are common file access patterns for AI agents?
   - What security features should be mandatory?
   - What are standard naming conventions for agent tools?

2. **Security Best Practices:**
   - Is path traversal protection sufficient?
   - Are our blocked file patterns comprehensive?
   - Should we implement additional sandboxing?

3. **Tool Design:**
   - Are our tool names (mcp_read_project_file, mcp_list_project_structure, mcp_analyze_code_quality) optimal?
   - Should we split or merge any tools?
   - What additional tools would make agents more capable?

4. **Limitations Analysis:**
   - What can agents NOT do that they should be able to?
   - Are read-only permissions sufficient or should we add write capabilities?
   - How do our agents compare to GitHub Copilot Workspace or Cursor AI?

5. **Improvement Recommendations:**
   - What 3-5 improvements would have the highest impact?
   - Are there any critical missing features?
   - Should we implement MCP protocol extensions?

**Expected output:**
- Comparison with industry standards
- Security audit results
- Tool design recommendations
- Feature gap analysis
- Prioritized improvement roadmap
"""

    async with httpx.AsyncClient(timeout=120.0) as client:
        
        # =======================================================================
        # Send to DeepSeek (Code Analysis)
        # =======================================================================
        print("📤 Sending self-analysis task to DeepSeek...")
        print()
        
        try:
            deepseek_request = {
                "from_agent": "copilot",
                "to_agent": "deepseek",
                "content": deepseek_task,
                "context": {
                    "task_type": "self_analysis",
                    "use_file_access": True,
                    "expected_tools": [
                        "mcp_list_project_structure",
                        "mcp_read_project_file",
                        "mcp_analyze_code_quality"
                    ],
                    "priority": "high"
                }
            }
            
            response = await client.post(
                f"{base_url}/api/v1/agent/send",
                json=deepseek_request
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ DeepSeek Response (HTTP {response.status_code}):")
                print(f"   Message ID: {data.get('message_id', 'N/A')}")
                print(f"   Conversation ID: {data.get('conversation_id', 'N/A')}")
                print()
                print("="*80)
                print("DEEPSEEK SELF-ANALYSIS:")
                print("="*80)
                print()
                
                content = data.get('content', '')
                print(content)
                print()
                
                # Save response
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"DEEPSEEK_SELF_ANALYSIS_{timestamp}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"📝 Full response saved to {filename}")
                print()
            else:
                print(f"❌ DeepSeek Error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"❌ DeepSeek Exception: {e}")
        
        print("="*80)
        print()
        
        # =======================================================================
        # Send to Perplexity (Research)
        # =======================================================================
        print("📤 Sending research task to Perplexity...")
        print()
        
        try:
            perplexity_request = {
                "from_agent": "copilot",
                "to_agent": "perplexity",
                "content": perplexity_task,
                "context": {
                    "task_type": "capabilities_research",
                    "priority": "high"
                }
            }
            
            response = await client.post(
                f"{base_url}/api/v1/agent/send",
                json=perplexity_request
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Perplexity Response (HTTP {response.status_code}):")
                print(f"   Message ID: {data.get('message_id', 'N/A')}")
                print(f"   Conversation ID: {data.get('conversation_id', 'N/A')}")
                print()
                print("="*80)
                print("PERPLEXITY RESEARCH:")
                print("="*80)
                print()
                
                content = data.get('content', '')
                print(content)
                print()
                
                # Save response
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"PERPLEXITY_CAPABILITIES_RESEARCH_{timestamp}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"📝 Full response saved to {filename}")
                print()
            else:
                print(f"❌ Perplexity Error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Perplexity Exception: {e}")
    
    print("="*80)
    print("✅ Agent self-analysis test completed!")
    print("="*80)
    print()
    print("📊 Expected Results:")
    print("   - DeepSeek: List of MCP tools, capabilities analysis, self-assessment")
    print("   - Perplexity: Industry best practices, security audit, improvement roadmap")
    print()
    print("📝 Check saved JSON files for full responses")
    print()
    print("🎯 Next: Review agent feedback and implement suggested improvements!")


if __name__ == "__main__":
    asyncio.run(test_agent_self_analysis())
