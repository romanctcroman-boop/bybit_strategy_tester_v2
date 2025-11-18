"""
MCP Load Test Script - Verify semaphore behavior under concurrent load
Tests circuit breaker, concurrency limits, and timeout handling per DeepSeek feedback
"""
import asyncio
import time
from typing import List, Dict
import httpx
from datetime import datetime, timezone


class McpLoadTester:
    """Load tester for MCP tools with semaphore + circuit breaker validation"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.results: List[Dict] = []
    
    async def call_mcp_tool(
        self, 
        tool_name: str, 
        content: str, 
        client: httpx.AsyncClient,
        task_id: int
    ) -> Dict:
        """Single MCP tool call with timing"""
        start = time.perf_counter()
        try:
            response = await client.post(
                f"{self.base_url}/api/v1/agent/send",
                json={
                    "from_agent": "load_tester",
                    "to_agent": tool_name.split("_")[-1],  # deepseek or perplexity
                    "message_type": "query",
                    "content": content,
                    "context": {
                        "load_test": True,
                        "task_id": task_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                },
                timeout=180.0  # Allow long AI responses
            )
            
            latency = time.perf_counter() - start
            
            return {
                "task_id": task_id,
                "tool": tool_name,
                "status": response.status_code,
                "latency_sec": latency,
                "success": response.status_code == 200,
                "error": None if response.status_code == 200 else response.text[:200]
            }
            
        except asyncio.TimeoutError:
            return {
                "task_id": task_id,
                "tool": tool_name,
                "status": 0,
                "latency_sec": time.perf_counter() - start,
                "success": False,
                "error": "TimeoutError (>180s)"
            }
        except Exception as e:
            return {
                "task_id": task_id,
                "tool": tool_name,
                "status": 0,
                "latency_sec": time.perf_counter() - start,
                "success": False,
                "error": str(e)[:200]
            }
    
    async def run_concurrent_load(
        self, 
        tool_name: str, 
        num_requests: int = 15,  # Exceeds default semaphore limit (10)
        message: str = "Quick test"
    ):
        """Run concurrent requests to test semaphore queueing"""
        print(f"\n{'='*60}")
        print(f"CONCURRENT LOAD TEST: {tool_name}")
        print(f"Requests: {num_requests} (exceeds semaphore limit)")
        print(f"{'='*60}\n")
        
        async with httpx.AsyncClient() as client:
            tasks = [
                self.call_mcp_tool(tool_name, f"{message} #{i}", client, i)
                for i in range(num_requests)
            ]
            
            start_time = time.perf_counter()
            results = await asyncio.gather(*tasks, return_exceptions=False)
            total_time = time.perf_counter() - start_time
            
            self.results.extend(results)
            
            # Analyze results
            successes = sum(1 for r in results if r["success"])
            failures = num_requests - successes
            avg_latency = sum(r["latency_sec"] for r in results) / num_requests
            max_latency = max(r["latency_sec"] for r in results)
            min_latency = min(r["latency_sec"] for r in results)
            
            print(f"✅ Completed in {total_time:.2f}s")
            print(f"   Success: {successes}/{num_requests}")
            print(f"   Failures: {failures}/{num_requests}")
            print(f"   Avg Latency: {avg_latency:.2f}s")
            print(f"   Min Latency: {min_latency:.2f}s")
            print(f"   Max Latency: {max_latency:.2f}s")
            
            if failures > 0:
                print(f"\n⚠️ FAILURES DETECTED:")
                for r in results:
                    if not r["success"]:
                        print(f"   Task {r['task_id']}: {r['error']}")
    
    async def test_circuit_breaker(self, tool_name: str):
        """Test circuit breaker by sending invalid requests"""
        print(f"\n{'='*60}")
        print(f"CIRCUIT BREAKER TEST: {tool_name}")
        print(f"Sending requests that should trigger breaker")
        print(f"{'='*60}\n")
        
        # Send rapid-fire requests with potentially failing content
        num_requests = 8  # Should exceed CB threshold (default 5)
        
        async with httpx.AsyncClient() as client:
            tasks = [
                self.call_mcp_tool(
                    tool_name, 
                    "Invalid request to test circuit breaker" * 100,  # Very long content
                    client, 
                    i
                )
                for i in range(num_requests)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=False)
            
            failures = sum(1 for r in results if not r["success"])
            
            print(f"Results: {failures}/{num_requests} failures")
            print(f"Circuit breaker should open after {failures} consecutive failures")
            
            if failures >= 5:
                print(f"✅ Circuit breaker likely activated (threshold met)")
            else:
                print(f"⚠️ Circuit breaker may not have activated")
    
    def print_summary(self):
        """Print overall test summary"""
        if not self.results:
            print("\nNo test results available")
            return
        
        print(f"\n{'='*60}")
        print("LOAD TEST SUMMARY")
        print(f"{'='*60}")
        
        total = len(self.results)
        successes = sum(1 for r in self.results if r["success"])
        failures = total - successes
        
        print(f"Total Requests: {total}")
        print(f"Successes: {successes} ({successes/total*100:.1f}%)")
        print(f"Failures: {failures} ({failures/total*100:.1f}%)")
        
        if self.results:
            latencies = [r["latency_sec"] for r in self.results]
            latencies.sort()
            
            p50 = latencies[len(latencies)//2]
            p95_idx = int(len(latencies) * 0.95)
            p95 = latencies[p95_idx] if p95_idx < len(latencies) else latencies[-1]
            p99_idx = int(len(latencies) * 0.99)
            p99 = latencies[p99_idx] if p99_idx < len(latencies) else latencies[-1]
            
            print(f"\nLatency Percentiles:")
            print(f"  P50: {p50:.2f}s")
            print(f"  P95: {p95:.2f}s")
            print(f"  P99: {p99:.2f}s")
            print(f"  Max: {max(latencies):.2f}s")
            
            # Check if P95/P99 exceed alerting thresholds
            if p95 > 60:
                print(f"⚠️ P95 exceeds 60s threshold (alert should fire)")
            if p99 > 120:
                print(f"⚠️ P99 exceeds 120s threshold (critical alert should fire)")
            
            if failures / total > 0.1:
                print(f"⚠️ Error rate >10% (alert should fire)")


async def main():
    """Run comprehensive load tests"""
    tester = McpLoadTester()
    
    print("🚀 MCP LOAD TEST STARTING")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("\nObjective: Verify semaphore queueing, circuit breaker, and timeout handling")
    print("Per DeepSeek feedback: Check for deadlock scenarios and head-of-line blocking")
    
    # Test 1: Concurrent load on DeepSeek
    await tester.run_concurrent_load(
        tool_name="deepseek",
        num_requests=12,  # Exceeds semaphore limit (10)
        message="Analyze this simple Python function: def add(a, b): return a + b"
    )
    
    # Wait for circuit breaker cooldown
    print("\n⏳ Waiting 65s for potential circuit breaker cooldown...")
    await asyncio.sleep(65)
    
    # Test 2: Concurrent load on Perplexity
    await tester.run_concurrent_load(
        tool_name="perplexity",
        num_requests=8,
        message="What is the best practice for async Python error handling?"
    )
    
    # Test 3: Circuit breaker test (commented out by default to avoid API abuse)
    # await tester.test_circuit_breaker("deepseek")
    
    # Print summary
    tester.print_summary()
    
    print(f"\n{'='*60}")
    print("LOAD TEST COMPLETE")
    print(f"{'='*60}")
    print("\nRecommendations:")
    print("1. Check Prometheus /metrics for mcp_tool_duration_seconds histogram")
    print("2. Verify no deadlocks occurred (all requests completed)")
    print("3. Confirm semaphore prevented >10 concurrent executions")
    print("4. Review circuit breaker activation in logs if failures occurred")


if __name__ == "__main__":
    asyncio.run(main())
