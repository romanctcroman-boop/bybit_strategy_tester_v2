#!/usr/bin/env python3
"""
Test DeepSeek MCP Server - verify connection and tools.

Usage:
    py -3 scripts/mcp/test_deepseek_mcp.py
"""

import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set API keys for test
os.environ["DEEPSEEK_API_KEY"] = "sk-1630fbba63c64f88952c16ad33337242"
os.environ["DEEPSEEK_API_KEY_2"] = "sk-0a584271e8104aea89c9f5d7502093dd"

from scripts.mcp.deepseek_mcp_server import DeepSeekMCPServer


def test_server():
    """Test DeepSeek server (synchronous)."""
    print("=" * 60)
    print("[TEST] DeepSeek MCP Server (Sync)")
    print("=" * 60)

    server = DeepSeekMCPServer()

    # Test 1: Check initialization
    print("\n[1] Server initialization...")
    init_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    init_response = server.handle_request(init_request)

    if "result" in init_response:
        print(f"   [OK] Server: {init_response['result']['serverInfo']['name']}")
        print(f"   [OK] Version: {init_response['result']['serverInfo']['version']}")
    else:
        print(f"   [FAIL] Error: {init_response}")
        return False

    # Test 2: List tools
    print("\n[2] List tools...")
    tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    tools_response = server.handle_request(tools_request)

    if "result" in tools_response:
        tools = tools_response['result']['tools']
        print(f"   [OK] Available tools: {len(tools)}")
        for tool in tools:
            print(f"      - {tool['name']}: {tool['description'][:50]}...")
    else:
        print(f"   [FAIL] Error: {tools_response}")
        return False

    # Test 3: Call deepseek_chat (real API request)
    print("\n[3] DeepSeek API call (deepseek_chat)...")
    print("   [..] Sending request...")

    chat_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "deepseek_chat",
            "arguments": {
                "message": "Say 'Hello, integration works!' in one line.",
                "temperature": 0.3
            }
        }
    }

    chat_response = server.handle_request(chat_request)

    if "result" in chat_response:
        import json
        content = chat_response['result']['content'][0]['text']
        result = json.loads(content)

        if result.get("success"):
            print("   [OK] Response received!")
            print(f"   [OK] Model: {result.get('model', 'unknown')}")
            print(f"   [OK] Response: {result.get('content', '')[:100]}")
            usage = result.get('usage', {})
            if usage:
                print(f"   [OK] Tokens: {usage.get('prompt_tokens', 0)} in / {usage.get('completion_tokens', 0)} out")
        else:
            print(f"   [FAIL] API error: {result.get('error', 'unknown')}")
            return False
    else:
        print(f"   [FAIL] Error: {chat_response}")
        return False

    print("\n" + "=" * 60)
    print("[SUCCESS] All tests passed! DeepSeek MCP is ready.")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = test_server()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[CRITICAL] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
