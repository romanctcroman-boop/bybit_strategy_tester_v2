"""
Test Agent File Access Capabilities - Real World Task

Task: Find and fix Plugin Manager shutdown error
Error: "WARNING: ⚠️ Plugin Manager shutdown error: 'PluginManager' object has no attribute 'unload_all_plugins'"

Let agents use new MCP file access tools to:
1. Navigate project structure
2. Find Plugin Manager code
3. Read and analyze the code
4. Identify the bug
5. Propose fix
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_agent_autonomous_debugging():
    """Test agents' ability to autonomously find and fix bugs using file access"""
    
    base_url = "http://127.0.0.1:8000"
    
    print("="*80)
    print("🤖 TESTING AGENT AUTONOMOUS DEBUGGING")
    print("="*80)
    print()
    print("Task: Find and fix Plugin Manager shutdown error")
    print("Error: 'PluginManager' object has no attribute 'unload_all_plugins'")
    print()
    print("Agents will use new MCP file access tools to:")
    print("  1. Navigate project structure")
    print("  2. Find Plugin Manager code")
    print("  3. Read and analyze implementation")
    print("  4. Identify the bug")
    print("  5. Propose fix")
    print()
    print("="*80)
    print()
    
    # Create detailed investigation request
    investigation_request = """
🔍 DEBUGGING TASK: Plugin Manager Shutdown Error

**Error Message:**
```
WARNING: ⚠️ Plugin Manager shutdown error: 'PluginManager' object has no attribute 'unload_all_plugins'
```

**Context:**
This error appears during backend shutdown in `backend/api/app.py` lifespan context manager.

**Your Task:**
1. Use `mcp_list_project_structure` to find where Plugin Manager is implemented
2. Use `mcp_read_project_file` to read the Plugin Manager code
3. Use `mcp_read_project_file` to read the backend/api/app.py lifespan shutdown code
4. Analyze both files and identify why 'unload_all_plugins' method doesn't exist
5. Propose a fix

**Available MCP Tools:**
- `mcp_list_project_structure(directory, max_depth, include_hidden)` - Navigate project
- `mcp_read_project_file(file_path, max_size_kb)` - Read files
- `mcp_analyze_code_quality(file_path, tools)` - Check code quality

**Instructions:**
Please use these tools step-by-step to investigate and solve this issue.
Start with listing the project structure to find Plugin Manager files.
"""

    async with httpx.AsyncClient(timeout=120.0) as client:
        
        # =======================================================================
        # Send investigation task to DeepSeek (Code Analysis Expert)
        # =======================================================================
        print("📤 Sending investigation task to DeepSeek...")
        print()
        
        try:
            deepseek_request = {
                "from_agent": "copilot",
                "to_agent": "deepseek",
                "content": investigation_request,
                "context": {
                    "task_type": "autonomous_debugging",
                    "error_message": "PluginManager' object has no attribute 'unload_all_plugins'",
                    "available_tools": [
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
                print("DEEPSEEK ANALYSIS:")
                print("="*80)
                print()
                
                content = data.get('content', '')
                print(content)
                print()
                
                # Save full response
                with open("DEEPSEEK_PLUGIN_MANAGER_DEBUG.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print("📝 Full response saved to DEEPSEEK_PLUGIN_MANAGER_DEBUG.json")
                print()
            else:
                print(f"❌ DeepSeek Error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return
                
        except Exception as e:
            print(f"❌ DeepSeek Exception: {e}")
            return
        
        # =======================================================================
        # Also send to Perplexity for research-based approach
        # =======================================================================
        print("="*80)
        print("📤 Sending investigation task to Perplexity...")
        print()
        
        perplexity_request_content = """
🔍 RESEARCH TASK: Python Plugin Manager Best Practices

**Problem:**
Backend shutdown fails with:
```
'PluginManager' object has no attribute 'unload_all_plugins'
```

**Research Questions:**
1. What are common patterns for Python plugin manager shutdown/cleanup?
2. What should the method be called (unload_all_plugins vs unload_all vs cleanup)?
3. Are there standard lifecycle methods for plugin managers?
4. What are best practices for graceful plugin unloading?

**Context:**
We have a custom PluginManager that loads plugins dynamically.
The lifespan shutdown tries to call `plugin_manager.unload_all_plugins()` but this method doesn't exist.

**Your Task:**
Research Python plugin architecture patterns and recommend:
1. Correct method naming convention
2. Proper cleanup implementation
3. Best practices for plugin lifecycle management
"""
        
        try:
            perplexity_request = {
                "from_agent": "copilot",
                "to_agent": "perplexity",
                "content": perplexity_request_content,
                "context": {
                    "task_type": "research_debugging",
                    "error_message": "PluginManager' object has no attribute 'unload_all_plugins'",
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
                
                # Save full response
                with open("PERPLEXITY_PLUGIN_MANAGER_RESEARCH.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print("📝 Full response saved to PERPLEXITY_PLUGIN_MANAGER_RESEARCH.json")
                print()
            else:
                print(f"❌ Perplexity Error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Perplexity Exception: {e}")
    
    print("="*80)
    print("✅ Agent autonomous debugging test completed!")
    print("="*80)
    print()
    print("📊 Results:")
    print("   - DeepSeek: Code analysis and bug identification")
    print("   - Perplexity: Research best practices and recommendations")
    print()
    print("📝 Check saved files:")
    print("   - DEEPSEEK_PLUGIN_MANAGER_DEBUG.json")
    print("   - PERPLEXITY_PLUGIN_MANAGER_RESEARCH.json")
    print()
    print("🎯 Next: Review agent responses and apply their fixes!")


if __name__ == "__main__":
    asyncio.run(test_agent_autonomous_debugging())
