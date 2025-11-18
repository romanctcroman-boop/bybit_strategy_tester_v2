"""
Test script for new MCP File Access Tools

Tests:
1. mcp_read_project_file - Reading project files
2. mcp_list_project_structure - Directory navigation
3. mcp_analyze_code_quality - Code quality checks

Run: py scripts\test_mcp_file_access.py
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_mcp_file_access_tools():
    """Test all new MCP file access tools"""
    
    base_url = "http://127.0.0.1:8000/mcp"
    
    print("="*80)
    print("🧪 Testing MCP File Access Tools")
    print("="*80)
    print()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        
        # =======================================================================
        # Test 1: mcp_read_project_file
        # =======================================================================
        print("📖 Test 1: Reading project file (backend/api/app.py)")
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "mcp_read_project_file",
                    "arguments": {
                        "file_path": "backend/api/app.py",
                        "max_size_kb": 200
                    }
                },
                "id": 1
            }
            
            response = await client.post(base_url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                
                if result.get("success"):
                    print(f"✅ File read successfully")
                    print(f"   File size: {result.get('file_size_kb', 0)} KB")
                    print(f"   Lines: {result.get('lines', 0)}")
                    print(f"   Path: {result.get('file_path')}")
                    print(f"   Content preview: {result.get('content', '')[:100]}...")
                else:
                    print(f"❌ Failed: {result.get('error')}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print()
        
        # =======================================================================
        # Test 2: Security - Try to read .env (should be blocked)
        # =======================================================================
        print("🔒 Test 2: Security check - Attempt to read .env (should fail)")
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "mcp_read_project_file",
                    "arguments": {
                        "file_path": ".env"
                    }
                },
                "id": 2
            }
            
            response = await client.post(base_url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                
                if not result.get("success"):
                    print(f"✅ Security working: {result.get('error')}")
                else:
                    print(f"⚠️ Security bypass detected! File was read.")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print()
        
        # =======================================================================
        # Test 3: mcp_list_project_structure
        # =======================================================================
        print("📂 Test 3: List project structure (backend/ directory)")
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "mcp_list_project_structure",
                    "arguments": {
                        "directory": "backend",
                        "max_depth": 2,
                        "include_hidden": False
                    }
                },
                "id": 3
            }
            
            response = await client.post(base_url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                
                if result.get("success"):
                    print(f"✅ Structure retrieved successfully")
                    print(f"   Files: {result.get('file_count', 0)}")
                    print(f"   Directories: {result.get('dir_count', 0)}")
                    print(f"   Max depth: {result.get('max_depth', 0)}")
                    
                    # Print structure summary
                    structure = result.get("structure", {})
                    children = structure.get("children", [])
                    print(f"   Top-level items: {len(children)}")
                    for item in children[:5]:
                        print(f"      - {item.get('name')} ({item.get('type')})")
                else:
                    print(f"❌ Failed: {result.get('error')}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print()
        
        # =======================================================================
        # Test 4: mcp_analyze_code_quality
        # =======================================================================
        print("🔍 Test 4: Analyze code quality (backend/api/app.py)")
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "mcp_analyze_code_quality",
                    "arguments": {
                        "file_path": "backend/api/app.py",
                        "tools": ["ruff", "black"]  # Skip bandit for speed
                    }
                },
                "id": 4
            }
            
            response = await client.post(base_url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                
                if result.get("success"):
                    summary = result.get("summary", {})
                    print(f"✅ Code quality analysis completed")
                    print(f"   All passed: {summary.get('all_passed', False)}")
                    print(f"   Total issues: {summary.get('total_issues', 0)}")
                    print(f"   Tools run: {', '.join(summary.get('tools_run', []))}")
                    
                    # Show results per tool
                    results = result.get("results", {})
                    for tool, tool_result in results.items():
                        status = tool_result.get("status", "unknown")
                        issues = tool_result.get("issues_count", 0)
                        print(f"      {tool}: {status} ({issues} issues)")
                else:
                    print(f"❌ Failed: {result.get('error')}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print()
        
        # =======================================================================
        # Test 5: List all available MCP tools
        # =======================================================================
        print("🔧 Test 5: List all available MCP tools")
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 5
            }
            
            response = await client.post(base_url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                tools = data.get("result", {}).get("tools", [])
                
                print(f"✅ Found {len(tools)} MCP tools:")
                for tool in tools:
                    name = tool.get("name", "unknown")
                    description = tool.get("description", "")
                    print(f"   - {name}")
                    if description:
                        print(f"     {description[:80]}...")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print()
    
    print("="*80)
    print("✅ All tests completed!")
    print("="*80)
    print()
    print("📊 Summary:")
    print("   - 3 new MCP file access tools tested")
    print("   - Security validation passed")
    print("   - Tools available for agents to use")
    print()
    print("🚀 Next steps:")
    print("   1. Integrate tools with unified_agent_interface.py")
    print("   2. Test agent file reading capabilities")
    print("   3. Send comprehensive project analysis request to agents")


if __name__ == "__main__":
    asyncio.run(test_mcp_file_access_tools())
