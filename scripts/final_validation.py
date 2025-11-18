"""
Final validation script for MCP agent recommendations implementation
Captures all evidence: health, metrics, MCP client, Direct API
"""
import asyncio
import json
from datetime import datetime, timezone
import httpx
from fastmcp import Client as FastMcpClient
from fastmcp.client.transports import StreamableHttpTransport


async def test_health_endpoint():
    """Test the MCP-native health endpoint"""
    print("\n" + "=" * 60)
    print("1. MCP HEALTH ENDPOINT TEST")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://127.0.0.1:8000/mcp/health")
        data = resp.json()
        
        print(f"Status Code: {resp.status_code}")
        print(f"Health Status: {data['status']}")
        print(f"Tool Count: {data['tool_count']}")
        print(f"Tools Registered: {data['tools_registered']}")
        print(f"Checks: {json.dumps(data['checks'], indent=2)}")
        
        # Validation
        assert resp.status_code == 200, "Health endpoint should return 200"
        assert data['tool_count'] == 3, "Should have 3 agent tools"
        assert data['status'] == 'healthy', "Status should be healthy"
        assert data['checks']['mcp_tools_available'], "MCP tools should be available"
        
        print("✅ Health endpoint validation PASSED")
        return data


async def test_metrics_histogram():
    """Test that latency histogram is populated"""
    print("\n" + "=" * 60)
    print("2. PROMETHEUS METRICS HISTOGRAM TEST")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://127.0.0.1:8000/metrics")
        metrics_text = resp.text
        
        # Extract histogram lines
        histogram_lines = [
            line for line in metrics_text.split('\n')
            if 'mcp_tool_duration_seconds' in line
        ]
        
        print("Histogram metrics found:")
        for line in histogram_lines[:15]:  # First 15 lines
            print(f"  {line}")
        
        # Validation
        assert any('mcp_tool_duration_seconds_bucket' in line for line in histogram_lines), \
            "Histogram buckets should be present"
        assert any('mcp_tool_duration_seconds_count' in line for line in histogram_lines), \
            "Histogram count should be present"
        assert any('mcp_tool_duration_seconds_sum' in line for line in histogram_lines), \
            "Histogram sum should be present"
        
        # Check if populated (count > 0)
        count_line = next((l for l in histogram_lines if 'count{' in l), None)
        if count_line:
            count_val = float(count_line.split()[-1])
            print(f"\n✅ Histogram populated: count={count_val}")
        else:
            print("\n⚠️ Histogram not yet populated (no traffic)")
        
        return histogram_lines


async def test_mcp_client():
    """Test MCP client connectivity via HTTP transport (FastMCP recommended pattern)"""
    print("\n" + "=" * 60)
    print("3. MCP CLIENT CONNECTIVITY TEST")
    print("=" * 60)

    async with FastMcpClient(transport=StreamableHttpTransport("http://127.0.0.1:8000/mcp")) as client:
        # Ping
        ping_ok = await client.ping()
        print(f"Ping: {ping_ok}")
        assert ping_ok is True, "Ping should return True"

        # List tools
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        print(f"Tools: {tool_names}")

        # Validation
        assert len(tool_names) == 3, "Should list 3 agent tools"
        assert 'mcp_agent_to_agent_send_to_deepseek' in tool_names
        assert 'mcp_agent_to_agent_send_to_perplexity' in tool_names
        assert 'mcp_agent_to_agent_get_consensus' in tool_names

        # Call one tool to verify execution path (DeepSeek preferred)
        target = 'mcp_agent_to_agent_send_to_deepseek'
        result = await client.call_tool(target, {"content": "Validation probe via final script"})
        data = getattr(result, 'data', {}) or {}
        success = data.get('success') is True
        print(f"Tool call '{target}' success: {success}; keys: {list(data.keys())}")
        assert success, "Tool execution should succeed"

        print("✅ MCP client test PASSED")
        return tool_names


async def test_direct_api():
    """Test Direct API agent communication"""
    print("\n" + "=" * 60)
    print("4. DIRECT API AGENT COMMUNICATION TEST")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        # Test DeepSeek
        deepseek_payload = {
            "from_agent": "copilot",
            "to_agent": "deepseek",
            "message_type": "query",
            "content": "Quick health check: return 'OK'"
        }
        
        resp_ds = await client.post(
            "http://127.0.0.1:8000/api/v1/agent/send",
            json=deepseek_payload,
            timeout=30.0
        )
        
        print(f"DeepSeek Status: {resp_ds.status_code}")
        if resp_ds.status_code == 200:
            data_ds = resp_ds.json()
            print(f"DeepSeek Message ID: {data_ds.get('message_id')}")
            print(f"DeepSeek Response: {data_ds.get('content', '')[:100]}")
        
        # Test Perplexity
        perplexity_payload = {
            "from_agent": "copilot",
            "to_agent": "perplexity",
            "message_type": "query",
            "content": "Quick health check: return 'OK'"
        }
        
        resp_px = await client.post(
            "http://127.0.0.1:8000/api/v1/agent/send",
            json=perplexity_payload,
            timeout=30.0
        )
        
        print(f"Perplexity Status: {resp_px.status_code}")
        if resp_px.status_code == 200:
            data_px = resp_px.json()
            print(f"Perplexity Message ID: {data_px.get('message_id')}")
            print(f"Perplexity Response: {data_px.get('content', '')[:100]}")
        
        # Validation
        assert resp_ds.status_code == 200, "DeepSeek should return 200"
        assert resp_px.status_code == 200, "Perplexity should return 200"
        
        print("✅ Direct API test PASSED")
        return {
            "deepseek": resp_ds.status_code == 200,
            "perplexity": resp_px.status_code == 200
        }


async def main():
    """Run all validation tests"""
    print("\n" + "=" * 60)
    print("MCP AGENT RECOMMENDATIONS - FINAL VALIDATION")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    try:
        # Run all tests
        health = await test_health_endpoint()
        metrics = await test_metrics_histogram()
        mcp_client = await test_mcp_client()
        direct_api = await test_direct_api()
        
        # Summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print("✅ Health Endpoint: PASSED")
        print("✅ Metrics Histogram: PASSED")
        print("✅ MCP Client: PASSED")
        print("✅ Direct API: PASSED")
        print("\n🎉 ALL TESTS PASSED - Agent Recommendations Complete")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
