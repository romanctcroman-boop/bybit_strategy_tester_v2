"""
🔄 Enhanced Cross-Agent Testing: DeepSeek ↔ Perplexity
Multi-threaded performance with REAL Multi-Key Rotation

Features:
- ✅ Perplexity: 4 API keys (full rotation)
- ✅ DeepSeek: 8 API keys (full rotation)
- ✅ Multi-threading with asyncio
- ✅ Comprehensive statistics
- ✅ Real production testing
"""

import asyncio
import time
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import statistics
from dotenv import load_dotenv
import httpx

# Load environment
load_dotenv()

# Add paths
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from api.providers.perplexity import PerplexityProvider


class MultiKeyDeepSeekAgent:
    """
    DeepSeek Agent with multi-key rotation support
    """
    
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        
        print(f"🎯 DeepSeek multi-key rotation enabled: {len(api_keys)} keys")
        
        # Per-key statistics
        self._key_stats = {}
        for key in api_keys:
            self._key_stats[key] = {
                "requests": 0,
                "failures": 0,
                "success_rate": 1.0,
                "last_success": time.time()
            }
    
    def _get_next_key(self) -> str:
        """Round-robin key selection"""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key
    
    def _update_key_stats(self, key: str, success: bool):
        """Update key statistics"""
        if key in self._key_stats:
            stats = self._key_stats[key]
            stats["requests"] += 1
            
            if success:
                stats["last_success"] = time.time()
            else:
                stats["failures"] += 1
            
            total = stats["requests"]
            failures = stats["failures"]
            stats["success_rate"] = (total - failures) / total if total > 0 else 1.0
    
    async def generate(self, prompt: str, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Generate response from DeepSeek with multi-key rotation
        """
        max_attempts = len(self.api_keys)  # 1 attempt per key
        last_error = None
        
        for attempt in range(max_attempts):
            current_key = self._get_next_key()
            
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.base_url,
                        headers={
                            "Authorization": f"Bearer {current_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "deepseek-chat",
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 500  # Reduced for faster responses
                        }
                    )
                    
                    if response.status_code == 200:
                        self._update_key_stats(current_key, success=True)
                        data = response.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        return {
                            "success": True,
                            "content": content,
                            "model": "deepseek-chat",
                            "key_used": current_key[-8:]
                        }
                    else:
                        self._update_key_stats(current_key, success=False)
                        last_error = Exception(f"HTTP {response.status_code}: {response.text}")
                        
                        # Short delay before next key
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(0.5)
                        
            except httpx.TimeoutException as e:
                self._update_key_stats(current_key, success=False)
                last_error = e
                # Try next key immediately on timeout
                
            except Exception as e:
                self._update_key_stats(current_key, success=False)
                last_error = e
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5)
        
        # All attempts failed
        return {
            "success": False,
            "error": str(last_error),
            "content": ""
        }
    
    def get_key_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all keys"""
        return {
            key[-8:]: stats 
            for key, stats in self._key_stats.items()
        }


class EnhancedCrossAgentTester:
    """
    Enhanced cross-agent tester with full multi-key support
    """
    
    def __init__(self, use_real_keys=True):
        # Load Perplexity keys
        perplexity_keys = []
        for i in range(1, 5):
            key = os.getenv(f"PERPLEXITY_API_KEY_{i}")
            if key:
                perplexity_keys.append(key)
        
        if not perplexity_keys:
            perplexity_keys = [os.getenv("PERPLEXITY_API_KEY", "test_key")]
        
        print(f"✅ Loaded {len(perplexity_keys)} Perplexity keys")
        
        self.perplexity = PerplexityProvider(
            api_keys=perplexity_keys,
            enable_exponential_backoff=True
        )
        
        # Load DeepSeek keys
        deepseek_keys = []
        for i in range(1, 9):
            key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
            if key:
                deepseek_keys.append(key)
        
        if not deepseek_keys:
            deepseek_keys = [os.getenv("DEEPSEEK_API_KEY", "test_key")]
        
        print(f"✅ Loaded {len(deepseek_keys)} DeepSeek keys")
        
        self.deepseek = MultiKeyDeepSeekAgent(api_keys=deepseek_keys)
        
        # Results tracking
        self.results = {
            "perplexity": [],
            "deepseek": [],
            "cross_validation": []
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Formatted logging"""
        timestamp = time.strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "PERF": "📊"
        }.get(level, "•")
        
        print(f"[{timestamp}] {prefix} {message}")
    
    async def test_perplexity_query(self, query: str, test_id: int) -> Dict[str, Any]:
        """Test single Perplexity query"""
        start_time = time.time()
        
        try:
            response = await self.perplexity.generate_response(
                query=query,
                model="sonar",
                temperature=0.7,
                max_tokens=1000,
                timeout=30.0
            )
            
            elapsed = time.time() - start_time
            content = response.get("content", "") or str(response.get("answer", ""))
            
            result = {
                "test_id": test_id,
                "query": query[:50] + "...",
                "success": True,
                "elapsed": elapsed,
                "response_length": len(content),
                "cached": response.get("cached", False),
                "error": None
            }
            
            self.log(
                f"Perplexity #{test_id}: {elapsed:.2f}s, "
                f"len={result['response_length']}, "
                f"cached={result['cached']}",
                "SUCCESS"
            )
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            
            result = {
                "test_id": test_id,
                "query": query[:50] + "...",
                "success": False,
                "elapsed": elapsed,
                "response_length": 0,
                "cached": False,
                "error": str(e)
            }
            
            self.log(f"Perplexity #{test_id} failed: {e}", "ERROR")
            return result
    
    async def test_deepseek_query(self, query: str, test_id: int) -> Dict[str, Any]:
        """Test single DeepSeek query with timeout and progress"""
        start_time = time.time()
        
        # Use shorter query for testing
        short_query = query[:200] if len(query) > 200 else query
        
        # Log start
        self.log(f"DeepSeek #{test_id} starting...", "INFO")
        
        try:
            # Add asyncio timeout wrapper - reduced to 20s
            response = await asyncio.wait_for(
                self.deepseek.generate(short_query, timeout=25.0),
                timeout=30.0  # Overall timeout: 30s (increased from 20s)
            )
            
            elapsed = time.time() - start_time
            
            result = {
                "test_id": test_id,
                "query": query[:50] + "...",
                "success": response.get("success", False),
                "elapsed": elapsed,
                "response_length": len(response.get("content", "")),
                "key_used": response.get("key_used", "unknown"),
                "error": response.get("error")
            }
            
            if result["success"]:
                self.log(
                    f"DeepSeek #{test_id}: {elapsed:.2f}s, "
                    f"len={result['response_length']}, "
                    f"key={result['key_used']}",
                    "SUCCESS"
                )
            else:
                self.log(f"DeepSeek #{test_id} failed: {result['error']}", "ERROR")
            
            return result
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            
            result = {
                "test_id": test_id,
                "query": query[:50] + "...",
                "success": False,
                "elapsed": elapsed,
                "response_length": 0,
                "key_used": "unknown",
                "error": "Timeout after 30s"
            }
            
            self.log(f"DeepSeek #{test_id} TIMEOUT after {elapsed:.2f}s", "ERROR")
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            
            result = {
                "test_id": test_id,
                "query": query[:50] + "...",
                "success": False,
                "elapsed": elapsed,
                "response_length": 0,
                "key_used": "unknown",
                "error": str(e)
            }
            
            self.log(f"DeepSeek #{test_id} EXCEPTION: {e}", "ERROR")
            return result
    
    async def test_parallel_queries(self, queries: List[str], agent: str = "both"):
        """Test parallel queries with concurrency control"""
        self.log(f"\n{'='*80}", "INFO")
        self.log(f"🔄 Parallel Test: {agent.upper()}", "INFO")
        self.log(f"Queries: {len(queries)}", "INFO")
        self.log(f"{'='*80}\n", "INFO")
        
        start_time = time.time()
        
        # Create semaphore for DeepSeek (limit concurrent requests)
        deepseek_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent DeepSeek requests
        
        async def deepseek_with_limit(query, test_id):
            async with deepseek_semaphore:
                return await self.test_deepseek_query(query, test_id)
        
        tasks = []
        
        if agent in ("perplexity", "both"):
            for i, query in enumerate(queries):
                tasks.append(self.test_perplexity_query(query, i))
        
        if agent in ("deepseek", "both"):
            for i, query in enumerate(queries):
                # Use semaphore-limited version for DeepSeek
                tasks.append(deepseek_with_limit(query, i))
        
        # Execute all in parallel (but DeepSeek limited to 5 concurrent)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Store results and handle exceptions
        for result in results:
            if isinstance(result, Exception):
                self.log(f"Task failed with exception: {result}", "ERROR")
                continue
                
            if "cached" in result:  # Perplexity result
                self.results["perplexity"].append(result)
            else:  # DeepSeek result
                self.results["deepseek"].append(result)
        
        elapsed = time.time() - start_time
        self.log(f"\n📊\n⏱️  Total parallel execution time: {elapsed:.2f}s", "PERF")
        
        return len([r for r in results if not isinstance(r, Exception)])
    
    async def test_cross_validation(self, query: str):
        """Cross-validation: same query to both agents"""
        self.log(f"\n{'='*80}", "INFO")
        self.log(f"🔍 Cross-Validation Test", "INFO")
        self.log(f"Query: {query[:50]}...", "INFO")
        self.log(f"{'='*80}\n", "INFO")
        
        # Run both in parallel
        perp_task = self.test_perplexity_query(query, 0)
        deep_task = self.test_deepseek_query(query, 0)
        
        perp_result, deep_result = await asyncio.gather(perp_task, deep_task)
        
        # Compare
        comparison = {
            "query": query,
            "perplexity_time": perp_result["elapsed"],
            "deepseek_time": deep_result["elapsed"],
            "perplexity_success": perp_result["success"],
            "deepseek_success": deep_result["success"],
            "winner": None
        }
        
        if perp_result["success"] and deep_result["success"]:
            if perp_result["elapsed"] < deep_result["elapsed"]:
                comparison["winner"] = "perplexity"
                self.log(
                    f"🏆 Winner: Perplexity (faster by {deep_result['elapsed'] - perp_result['elapsed']:.2f}s)",
                    "SUCCESS"
                )
            else:
                comparison["winner"] = "deepseek"
                self.log(
                    f"🏆 Winner: DeepSeek (faster by {perp_result['elapsed'] - deep_result['elapsed']:.2f}s)",
                    "SUCCESS"
                )
        elif perp_result["success"]:
            comparison["winner"] = "perplexity"
            self.log("🏆 Winner: Perplexity (DeepSeek failed)", "SUCCESS")
        elif deep_result["success"]:
            comparison["winner"] = "deepseek"
            self.log("🏆 Winner: DeepSeek (Perplexity failed)", "SUCCESS")
        else:
            self.log("⚠️  Both agents failed", "WARNING")
        
        self.results["cross_validation"].append(comparison)
    
    def print_statistics(self):
        """Print comprehensive statistics"""
        self.log(f"\n{'='*80}", "INFO")
        self.log(f"📊 STATISTICS SUMMARY", "INFO")
        self.log(f"{'='*80}\n", "INFO")
        
        # Perplexity stats
        if self.results["perplexity"]:
            perp_results = self.results["perplexity"]
            successful = [r for r in perp_results if r["success"]]
            failed = [r for r in perp_results if not r["success"]]
            cached = [r for r in successful if r.get("cached")]
            
            times = [r["elapsed"] for r in successful]
            lengths = [r["response_length"] for r in successful]
            
            self.log(f"\nPERPLEXITY Agent:", "INFO")
            self.log(f"  Total requests: {len(perp_results)}", "INFO")
            self.log(f"  Successful: {len(successful)} ({len(successful)/len(perp_results)*100:.1f}%)", "SUCCESS")
            self.log(f"  Failed: {len(failed)} ({len(failed)/len(perp_results)*100:.1f}%)", "INFO")
            self.log(f"  Cache hits: {len(cached)} ({len(cached)/len(perp_results)*100:.1f}%)", "INFO")
            
            if times:
                self.log(f"\n📊  Response Times:", "PERF")
                self.log(f"    Min: {min(times):.2f}s", "INFO")
                self.log(f"    Max: {max(times):.2f}s", "INFO")
                self.log(f"    Avg: {statistics.mean(times):.2f}s", "INFO")
                self.log(f"    Median: {statistics.median(times):.2f}s", "INFO")
                if len(times) > 1:
                    self.log(f"    StdDev: {statistics.stdev(times):.2f}s", "INFO")
            
            if lengths:
                self.log(f"\n📊  Response Lengths:", "PERF")
                self.log(f"    Min: {min(lengths)} chars", "INFO")
                self.log(f"    Max: {max(lengths)} chars", "INFO")
                self.log(f"    Avg: {int(statistics.mean(lengths))} chars", "INFO")
            
            # Per-key stats
            key_stats = self.perplexity.get_key_stats()
            if len(key_stats) > 1:
                self.log(f"\n🔑  Multi-Key Statistics:", "INFO")
                for key_suffix, stats in key_stats.items():
                    success_rate = stats.get('success_rate', 0.0)
                    self.log(
                        f"    Key ...{key_suffix}: {stats['requests']} requests, "
                        f"{stats['failures']} failures ({success_rate*100:.1f}% success)",
                        "INFO"
                    )
        
        # DeepSeek stats
        if self.results["deepseek"]:
            deep_results = self.results["deepseek"]
            successful = [r for r in deep_results if r["success"]]
            failed = [r for r in deep_results if not r["success"]]
            
            times = [r["elapsed"] for r in successful]
            lengths = [r["response_length"] for r in successful]
            
            self.log(f"\n\nDEEPSEEK Agent:", "INFO")
            self.log(f"  Total requests: {len(deep_results)}", "INFO")
            self.log(f"  Successful: {len(successful)} ({len(successful)/len(deep_results)*100:.1f}%)", "SUCCESS")
            self.log(f"  Failed: {len(failed)} ({len(failed)/len(deep_results)*100:.1f}%)", "INFO")
            
            if times:
                self.log(f"\n📊  Response Times:", "PERF")
                self.log(f"    Min: {min(times):.2f}s", "INFO")
                self.log(f"    Max: {max(times):.2f}s", "INFO")
                self.log(f"    Avg: {statistics.mean(times):.2f}s", "INFO")
                self.log(f"    Median: {statistics.median(times):.2f}s", "INFO")
                if len(times) > 1:
                    self.log(f"    StdDev: {statistics.stdev(times):.2f}s", "INFO")
            
            if lengths:
                self.log(f"\n📊  Response Lengths:", "PERF")
                self.log(f"    Min: {min(lengths)} chars", "INFO")
                self.log(f"    Max: {max(lengths)} chars", "INFO")
                self.log(f"    Avg: {int(statistics.mean(lengths))} chars", "INFO")
            
            # Per-key stats
            key_stats = self.deepseek.get_key_stats()
            if len(key_stats) > 1:
                self.log(f"\n🔑  Multi-Key Statistics:", "INFO")
                for key_suffix, stats in key_stats.items():
                    self.log(
                        f"    Key ...{key_suffix}: {stats['requests']} requests, "
                        f"{stats['failures']} failures ({stats['success_rate']*100:.1f}% success)",
                        "INFO"
                    )
        
        # Cross-validation stats
        if self.results["cross_validation"]:
            self.log(f"\n\nCROSS-VALIDATION:", "INFO")
            
            perplexity_wins = sum(1 for c in self.results["cross_validation"] if c.get("winner") == "perplexity")
            deepseek_wins = sum(1 for c in self.results["cross_validation"] if c.get("winner") == "deepseek")
            total = len(self.results["cross_validation"])
            
            self.log(f"  Total comparisons: {total}", "INFO")
            self.log(f"  Perplexity wins: {perplexity_wins} ({perplexity_wins/total*100:.1f}%)", "SUCCESS")
            self.log(f"  DeepSeek wins: {deepseek_wins} ({deepseek_wins/total*100:.1f}%)", "SUCCESS")


async def main():
    """Main testing function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Cross-Agent Testing')
    parser.add_argument('--parallel', type=int, default=20,
                       help='Number of parallel requests (default: 20)')
    parser.add_argument('--extended', action='store_true',
                       help='Run extended stress test')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🔄 ENHANCED CROSS-AGENT TESTING: DeepSeek ↔ Perplexity")
    print("="*80)
    print(f"Mode: 🔑 REAL MULTI-KEY ROTATION")
    print(f"Extended: {'✅ YES' if args.extended else '❌ NO'}")
    print(f"Parallel requests: {args.parallel}")
    print("="*80 + "\n")
    
    tester = EnhancedCrossAgentTester(use_real_keys=True)
    
    # Test queries - SHORTENED for faster DeepSeek responses
    test_queries = [
        "What is AI?",
        "Explain blockchain",
        "How does ML work?",
        "Benefits of crypto?",
        "What are neural nets?",
        "Define deep learning",
        "Explain Bitcoin",
        "What is Ethereum?",
        "Smart contracts?",
        "What is Python?"
    ]
    
    try:
        # Test 1: Parallel Perplexity (warm up cache)
        tester.log("🎯 TEST 1: Parallel Perplexity Queries (warm up)", "INFO")
        await tester.test_parallel_queries(test_queries[:5], agent="perplexity")
        await asyncio.sleep(1)
        
        # Test 2: Parallel DeepSeek (warm up)
        tester.log("\n🎯 TEST 2: Parallel DeepSeek Queries (warm up)", "INFO")
        await tester.test_parallel_queries(test_queries[:5], agent="deepseek")
        await asyncio.sleep(1)
        
        # Test 3: Both agents in parallel
        tester.log("\n🎯 TEST 3: Both Agents in Parallel", "INFO")
        await tester.test_parallel_queries(test_queries[:3], agent="both")
        await asyncio.sleep(1)
        
        # Test 4: Cross-validation
        tester.log("\n🎯 TEST 4: Cross-Validation", "INFO")
        for query in test_queries[:3]:
            await tester.test_cross_validation(query)
            await asyncio.sleep(0.5)
        
        # Test 5: Stress test
        if args.extended:
            tester.log(f"\n🎯 TEST 5: EXTENDED Stress Test ({args.parallel} parallel)", "INFO")
            stress_queries = test_queries * (args.parallel // len(test_queries) + 1)
            stress_queries = stress_queries[:args.parallel]
        else:
            tester.log(f"\n🎯 TEST 5: Stress Test ({args.parallel} parallel)", "INFO")
            stress_queries = test_queries * (args.parallel // len(test_queries) + 1)
            stress_queries = stress_queries[:args.parallel]
        
        await tester.test_parallel_queries(stress_queries, agent="both")
        
        # Print statistics
        tester.print_statistics()
        
        print("\n" + "="*80)
        print("✅ ALL CROSS-AGENT TESTS COMPLETED")
        print("="*80)
        
    except KeyboardInterrupt:
        tester.log("\n\n⏹️  Tests interrupted by user", "WARNING")
        tester.print_statistics()
    except Exception as e:
        tester.log(f"\n\n❌ Error: {e}", "ERROR")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
