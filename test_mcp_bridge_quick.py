"""Quick test for MCP bridge integration (Tasks 6-9)

Run: python test_mcp_bridge_quick.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_mcp_bridge():
    print("🧪 Testing MCP Bridge Integration...")
    
    # Test 1: Import bridge
    print("\n1️⃣ Testing bridge import...")
    try:
        from backend.mcp.mcp_integration import get_mcp_bridge, ensure_mcp_bridge_initialized
        print("   ✅ Bridge module imported")
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False
    
    # Test 2: Initialize bridge
    print("\n2️⃣ Testing bridge initialization...")
    try:
        bridge = get_mcp_bridge()
        await ensure_mcp_bridge_initialized()
        print("   ✅ Bridge initialized")
    except Exception as e:
        print(f"   ❌ Initialization failed: {e}")
        return False
    
    # Test 3: List tools
    print("\n3️⃣ Testing tool listing...")
    try:
        tools = await bridge.list_tools()
        print(f"   ✅ Found {len(tools)} tools")
        if len(tools) > 0:
            print(f"   📋 Sample tools: {[t['name'] for t in tools[:3]]}")
        else:
            print("   ⚠️ No tools registered (FastMCP may need app context)")
    except Exception as e:
        print(f"   ❌ Tool listing failed: {e}")
        return False
    
    # Test 4: Test routes import
    print("\n4️⃣ Testing routes import...")
    try:
        from backend.api.mcp_routes import router
        print(f"   ✅ Routes imported ({len(router.routes)} endpoints)")
    except Exception as e:
        print(f"   ❌ Routes import failed: {e}")
        return False
    
    # Test 5: Check unified agent interface patch
    print("\n5️⃣ Testing unified agent interface patch...")
    try:
        from backend.agents.unified_agent_interface import UnifiedAgentInterface
        import inspect
        source = inspect.getsource(UnifiedAgentInterface._try_mcp)
        if "get_mcp_bridge" in source:
            print("   ✅ _try_mcp patched to use internal bridge")
        else:
            print("   ⚠️ _try_mcp may still use HTTP (check manually)")
    except Exception as e:
        print(f"   ❌ Source inspection failed: {e}")
    
    print("\n✨ MCP Bridge Integration Tests Complete!")
    print("\n📝 Next Steps:")
    print("   - Start backend: python -m uvicorn backend.api.app:app --reload")
    print("   - Check logs for '✅ MCP Bridge initialized'")
    print("   - Test endpoints: GET http://127.0.0.1:8000/mcp/bridge/health")
    print("   - Test tool call: POST http://127.0.0.1:8000/mcp/bridge/tools/call")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_mcp_bridge())
    sys.exit(0 if success else 1)
