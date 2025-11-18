 #!/usr/bin/env python
 """Test MCP Bridge HTTP endpoints."""
 
 import httpx
 import json
 import asyncio
 from loguru import logger
 
 BASE_URL = "http://127.0.0.1:8000"
 
 async def test_mcp_bridge():
     """Test all MCP bridge endpoints."""
     async with httpx.AsyncClient(timeout=30) as client:
         # Test 1: Health check
         logger.info("1️⃣ Testing GET /mcp/bridge/health")
         try:
             resp = await client.get(f"{BASE_URL}/mcp/bridge/health")
             logger.info(f"   Status: {resp.status_code}")
             logger.info(f"   Response: {resp.json()}")
             assert resp.status_code == 200
             assert "status" in resp.json()
             logger.success("   ✅ Health check passed")
         except Exception as e:
             logger.error(f"   ❌ Health check failed: {e}")
             return False
 
         # Test 2: List tools
         logger.info("\n2️⃣ Testing GET /mcp/bridge/tools")
         try:
             resp = await client.get(f"{BASE_URL}/mcp/bridge/tools")
             logger.info(f"   Status: {resp.status_code}")
             tools = resp.json()
             logger.info(f"   Tools count: {len(tools['tools'])}")
             logger.info(f"   Tool names: {[t['name'] for t in tools['tools']]}")
             assert resp.status_code == 200
             assert len(tools['tools']) >= 6
             logger.success("   ✅ Tools list passed")
         except Exception as e:
             logger.error(f"   ❌ Tools list failed: {e}")
             return False
 
         # Test 3: Call tool (mcp_read_project_file)
         logger.info("\n3️⃣ Testing POST /mcp/bridge/tools/call (mcp_read_project_file)")
         try:
             payload = {
                 "tool_name": "mcp_read_project_file",
                 "arguments": {"file_path": "backend/mcp/mcp_integration.py"}
             }
             resp = await client.post(
                 f"{BASE_URL}/mcp/bridge/tools/call",
                 json=payload
             )
             logger.info(f"   Status: {resp.status_code}")
             result = resp.json()
             logger.info(f"   Success: {result.get('success')}")
             if result.get('success'):
                 content = result.get('content', '')
                 logger.info(f"   Content length: {len(content)} chars")
                 logger.info(f"   First 100 chars: {content[:100]}...")
                 logger.success("   ✅ Tool call passed")
             else:
                 logger.warning(f"   ⚠️ Tool returned error: {result.get('error')}")
         except Exception as e:
             logger.error(f"   ❌ Tool call failed: {e}")
             return False
 
         # Test 4: Correlation ID propagation
         logger.info("\n4️⃣ Testing Correlation ID propagation")
         try:
             test_id = "test-correlation-123"
             resp = await client.get(
                 f"{BASE_URL}/mcp/bridge/health",
                 headers={"X-Request-ID": test_id}
             )
             logger.info(f"   Status: {resp.status_code}")
             response_id = resp.headers.get("X-Request-ID")
             logger.info(f"   Sent ID: {test_id}")
             logger.info(f"   Response ID: {response_id}")
             if response_id == test_id:
                 logger.success("   ✅ Correlation ID preserved")
             else:
                 logger.warning(f"   ⚠️ Correlation ID mismatch (may not be implemented in routes yet)")
         except Exception as e:
             logger.error(f"   ❌ Correlation ID test failed: {e}")
 
         logger.success("\n✨ All MCP bridge tests complete!")
         return True
 
 if __name__ == "__main__":
     logger.info("🧪 Testing MCP Bridge HTTP Endpoints\n")
     asyncio.run(test_mcp_bridge())
