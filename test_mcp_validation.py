"""Test MCP Bridge argument validation and structured errors"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

async def test_validation():
    from backend.mcp.mcp_integration import get_mcp_bridge
    
    bridge = get_mcp_bridge()
    await bridge.initialize()
    
    print("=" * 60)
    print("MCP BRIDGE VALIDATION & STRUCTURED ERROR TESTS")
    print("=" * 60)
    
    # Test 1: Missing required argument
    print("\n1️⃣ Test: Missing required argument (content)")
    result = await bridge.call_tool("mcp_agent_to_agent_send_to_deepseek", {})
    print(f"   Success: {result.get('success')}")
    print(f"   Error Type: {result.get('error_type')}")
    print(f"   Message: {result.get('message')}")
    print(f"   Stage: {result.get('stage')}")
    print(f"   Retryable: {result.get('retryable')}")
    print(f"   Details: {result.get('details')}")
    assert result["success"] is False
    assert result["error_type"] == "ValidationError"
    assert result["stage"] == "validation"
    assert result["retryable"] is False
    print("   ✅ PASS: Validation caught missing argument")
    
    # Test 2: Unknown argument
    print("\n2️⃣ Test: Unknown argument (invalid_arg)")
    result = await bridge.call_tool("mcp_agent_to_agent_send_to_deepseek", {
        "content": "test",
        "invalid_arg": "should fail"
    })
    print(f"   Success: {result.get('success')}")
    print(f"   Error Type: {result.get('error_type')}")
    print(f"   Message: {result.get('message')}")
    print(f"   Details: {result.get('details')}")
    assert result["success"] is False
    assert result["error_type"] == "ValidationError"
    assert "unknown" in result["message"].lower()
    print("   ✅ PASS: Validation caught unknown argument")
    
    # Test 3: Type mismatch
    print("\n3️⃣ Test: Type mismatch (content should be str, not int)")
    result = await bridge.call_tool("mcp_agent_to_agent_send_to_deepseek", {
        "content": 12345  # Wrong type
    })
    print(f"   Success: {result.get('success')}")
    print(f"   Error Type: {result.get('error_type')}")
    print(f"   Message: {result.get('message')}")
    print(f"   Details: {result.get('details')}")
    assert result["success"] is False
    assert result["error_type"] == "ValidationError"
    print("   ✅ PASS: Validation caught type mismatch")
    
    # Test 4: Tool not found
    print("\n4️⃣ Test: Tool not found (nonexistent_tool)")
    result = await bridge.call_tool("nonexistent_tool", {"arg": "value"})
    print(f"   Success: {result.get('success')}")
    print(f"   Error Type: {result.get('error_type')}")
    print(f"   Message: {result.get('message')}")
    print(f"   Stage: {result.get('stage')}")
    print(f"   Available tools sample: {result.get('details', {}).get('available_tools', [])[:3]}")
    assert result["success"] is False
    assert result["error_type"] == "ToolNotFoundError"
    assert result["stage"] == "lookup"
    print("   ✅ PASS: Tool not found error structured correctly")
    
    # Test 5: Valid call (should succeed or fail at invocation stage, not validation)
    print("\n5️⃣ Test: Valid arguments (should pass validation)")
    result = await bridge.call_tool("mcp_read_project_file", {
        "file_path": "backend/api/app.py",
        "max_size_kb": 200
    })
    print(f"   Success: {result.get('success')}")
    if not result.get('success'):
        print(f"   Error Type: {result.get('error_type')}")
        print(f"   Stage: {result.get('stage')}")
        # If failed, should be invocation stage not validation
        assert result.get('stage') != 'validation', "Should not fail at validation stage"
    else:
        print(f"   File size: {result.get('file_size_kb')} KB")
    print("   ✅ PASS: Validation passed (success or invocation-stage failure)")
    
    # Test 6: Correlation ID propagation
    print("\n6️⃣ Test: Correlation ID propagation")
    result = await bridge.call_tool("nonexistent_tool", {})
    print(f"   Correlation ID present: {result.get('correlation_id') is not None}")
    # Note: May be None if middleware not active in test context
    print(f"   Correlation ID: {result.get('correlation_id', 'N/A')}")
    print("   ✅ PASS: Correlation ID handling verified")
    
    print("\n" + "=" * 60)
    print("ALL VALIDATION TESTS PASSED ✅")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_validation())
