"""
📊 Production Performance Monitor
Real-time monitoring of Perplexity API performance metrics

Features:
- Live response time tracking
- Cache hit rate monitoring
- Success rate tracking
- Circuit breaker status
- Multi-key rotation stats
- Alert on performance degradation
"""

import asyncio
import time
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import statistics
from dotenv import load_dotenv

# Load environment
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from api.providers.perplexity import PerplexityProvider


class PerformanceMonitor:
    """Production performance monitoring"""
    
    def __init__(self, use_real_keys=True):
        # Load real API key
        if use_real_keys:
            real_api_key = os.getenv("PERPLEXITY_API_KEY")
            if real_api_key:
                api_keys = [real_api_key]
                print(f"✅ Monitoring real Perplexity API: {real_api_key[:10]}...")
            else:
                print("❌ PERPLEXITY_API_KEY not found in .env")
                sys.exit(1)
        else:
            api_keys = ["test_key"]
        
        self.provider = PerplexityProvider(
            api_keys=api_keys,
            enable_exponential_backoff=True
        )
        
        # Monitoring data
        self.metrics = {
            "response_times": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "successes": 0,
            "failures": 0,
            "start_time": time.time()
        }
        
        # Alert thresholds
        self.thresholds = {
            "max_response_time": 10.0,  # seconds
            "min_success_rate": 0.90,   # 90%
            "min_cache_hit_rate": 0.30  # 30%
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Formatted output"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "METRIC": "📊",
            "ALERT": "🚨"
        }.get(level, "•")
        
        print(f"[{timestamp}] {prefix} {message}")
    
    async def execute_test_query(self, query: str) -> Dict[str, Any]:
        """Execute single query and track metrics"""
        start_time = time.time()
        
        try:
            response = await self.provider.generate_response(
                query=query,
                model="sonar",
                temperature=0.7,
                max_tokens=1000,
                timeout=30.0
            )
            
            elapsed = time.time() - start_time
            cached = response.get("cached", False)
            
            # Track metrics
            self.metrics["response_times"].append(elapsed)
            if cached:
                self.metrics["cache_hits"] += 1
            else:
                self.metrics["cache_misses"] += 1
            self.metrics["successes"] += 1
            
            return {
                "success": True,
                "elapsed": elapsed,
                "cached": cached,
                "response_length": len(str(response))
            }
            
        except Exception as e:
            elapsed = time.time() - start_time
            self.metrics["response_times"].append(elapsed)
            self.metrics["failures"] += 1
            
            return {
                "success": False,
                "elapsed": elapsed,
                "error": str(e)
            }
    
    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate current statistics"""
        times = self.metrics["response_times"]
        total_requests = self.metrics["successes"] + self.metrics["failures"]
        total_cache = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        
        stats = {
            "total_requests": total_requests,
            "success_rate": self.metrics["successes"] / total_requests if total_requests > 0 else 0,
            "failure_rate": self.metrics["failures"] / total_requests if total_requests > 0 else 0,
            "cache_hit_rate": self.metrics["cache_hits"] / total_cache if total_cache > 0 else 0,
            "uptime": time.time() - self.metrics["start_time"]
        }
        
        if times:
            stats.update({
                "response_time_min": min(times),
                "response_time_max": max(times),
                "response_time_avg": statistics.mean(times),
                "response_time_median": statistics.median(times),
                "response_time_stdev": statistics.stdev(times) if len(times) > 1 else 0
            })
        
        return stats
    
    def check_alerts(self, stats: Dict[str, Any]) -> List[str]:
        """Check for alert conditions"""
        alerts = []
        
        # Check response time
        if "response_time_avg" in stats:
            if stats["response_time_avg"] > self.thresholds["max_response_time"]:
                alerts.append(f"High average response time: {stats['response_time_avg']:.2f}s (threshold: {self.thresholds['max_response_time']}s)")
        
        # Check success rate
        if stats["success_rate"] < self.thresholds["min_success_rate"]:
            alerts.append(f"Low success rate: {stats['success_rate']*100:.1f}% (threshold: {self.thresholds['min_success_rate']*100:.1f}%)")
        
        # Check cache hit rate (only after warm-up period)
        if stats["total_requests"] > 10:
            if stats["cache_hit_rate"] < self.thresholds["min_cache_hit_rate"]:
                alerts.append(f"Low cache hit rate: {stats['cache_hit_rate']*100:.1f}% (threshold: {self.thresholds['min_cache_hit_rate']*100:.1f}%)")
        
        return alerts
    
    def print_dashboard(self, stats: Dict[str, Any]):
        """Print monitoring dashboard"""
        print("\n" + "="*80)
        print("📊 PERFORMANCE DASHBOARD")
        print("="*80)
        
        # Uptime
        uptime_str = str(timedelta(seconds=int(stats["uptime"])))
        print(f"⏱️  Uptime: {uptime_str}")
        
        # Request stats
        print(f"\n📈 REQUEST STATISTICS:")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Success rate: {stats['success_rate']*100:.1f}% ({self.metrics['successes']}/{stats['total_requests']})")
        print(f"   Failure rate: {stats['failure_rate']*100:.1f}% ({self.metrics['failures']}/{stats['total_requests']})")
        
        # Cache stats
        print(f"\n💾 CACHE STATISTICS:")
        total_cache = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        print(f"   Cache hits: {self.metrics['cache_hits']}/{total_cache}")
        print(f"   Cache hit rate: {stats['cache_hit_rate']*100:.1f}%")
        
        # Response time stats
        if "response_time_avg" in stats:
            print(f"\n⚡ RESPONSE TIME STATISTICS:")
            print(f"   Min: {stats['response_time_min']:.2f}s")
            print(f"   Max: {stats['response_time_max']:.2f}s")
            print(f"   Avg: {stats['response_time_avg']:.2f}s")
            print(f"   Median: {stats['response_time_median']:.2f}s")
            print(f"   StdDev: {stats['response_time_stdev']:.2f}s")
        
        # Provider health
        cache_stats = self.provider.get_cache_stats()
        print(f"\n🏥 PROVIDER HEALTH:")
        print(f"   Circuit breaker: {self.provider.circuit_breaker.state}")
        print(f"   Cache size: {cache_stats['size']}/{cache_stats['max_size']}")
        
        # Key stats (if multi-key)
        if len(self.provider.api_keys) > 1:
            key_stats = self.provider.get_key_stats()
            print(f"\n🔑 MULTI-KEY STATISTICS:")
            for key_suffix, key_stat in key_stats.items():
                print(f"   Key {key_suffix}: {key_stat['requests']} requests, {key_stat['failures']} failures ({key_stat['success_rate']*100:.1f}% success)")
        
        print("="*80)
    
    async def continuous_monitoring(self, interval: int = 60, queries: List[str] = None):
        """Continuous monitoring loop"""
        if queries is None:
            queries = [
                "What is quantum computing?",
                "Explain blockchain technology",
                "How does machine learning work?",
                "What are neural networks?",
                "Describe cryptocurrency"
            ]
        
        self.log("Starting continuous monitoring...", "INFO")
        self.log(f"Query interval: {interval} seconds", "INFO")
        self.log(f"Test queries: {len(queries)}", "INFO")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                self.log(f"\n🔄 Iteration #{iteration}", "INFO")
                
                # Execute test query (cycle through queries)
                query = queries[iteration % len(queries)]
                self.log(f"Testing: {query[:50]}...", "INFO")
                
                result = await self.execute_test_query(query)
                
                if result["success"]:
                    self.log(
                        f"✅ Response: {result['elapsed']:.2f}s, "
                        f"cached={result['cached']}, "
                        f"len={result['response_length']}",
                        "SUCCESS"
                    )
                else:
                    self.log(f"❌ Failed: {result['error']}", "ERROR")
                
                # Calculate stats every 5 iterations or on failure
                if iteration % 5 == 0 or not result["success"]:
                    stats = self.calculate_statistics()
                    self.print_dashboard(stats)
                    
                    # Check alerts
                    alerts = self.check_alerts(stats)
                    if alerts:
                        self.log("\n🚨 ALERTS:", "ALERT")
                        for alert in alerts:
                            self.log(f"  - {alert}", "ALERT")
                
                # Wait before next iteration
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            self.log("\n\n⏹️  Monitoring stopped by user", "WARNING")
            
            # Print final stats
            stats = self.calculate_statistics()
            self.print_dashboard(stats)
            
            self.log("\n✅ Monitoring session complete", "SUCCESS")
    
    async def snapshot_test(self, iterations: int = 10):
        """Quick snapshot test"""
        self.log(f"Running snapshot test ({iterations} requests)...", "INFO")
        
        queries = [
            "What is quantum computing?",
            "Explain blockchain technology",
            "How does machine learning work?",
            "What are neural networks?",
            "Describe cryptocurrency"
        ]
        
        for i in range(iterations):
            query = queries[i % len(queries)]
            result = await self.execute_test_query(query)
            
            if result["success"]:
                self.log(
                    f"[{i+1}/{iterations}] {result['elapsed']:.2f}s, cached={result['cached']}",
                    "SUCCESS"
                )
            else:
                self.log(f"[{i+1}/{iterations}] Failed: {result['error']}", "ERROR")
            
            await asyncio.sleep(0.5)
        
        # Print results
        stats = self.calculate_statistics()
        self.print_dashboard(stats)
        
        # Check alerts
        alerts = self.check_alerts(stats)
        if alerts:
            self.log("\n🚨 ALERTS:", "ALERT")
            for alert in alerts:
                self.log(f"  - {alert}", "ALERT")
        else:
            self.log("\n✅ All metrics within normal range", "SUCCESS")


async def main():
    """Main monitoring function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Perplexity Performance Monitor')
    parser.add_argument('--mode', choices=['continuous', 'snapshot'], default='snapshot',
                       help='Monitoring mode (default: snapshot)')
    parser.add_argument('--interval', type=int, default=60,
                       help='Seconds between checks in continuous mode (default: 60)')
    parser.add_argument('--iterations', type=int, default=10,
                       help='Number of iterations for snapshot mode (default: 10)')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("📊 PERPLEXITY PERFORMANCE MONITOR")
    print("="*80)
    print(f"Mode: {args.mode}")
    if args.mode == 'continuous':
        print(f"Interval: {args.interval}s")
    else:
        print(f"Iterations: {args.iterations}")
    print("="*80 + "\n")
    
    monitor = PerformanceMonitor(use_real_keys=True)
    
    try:
        if args.mode == 'continuous':
            await monitor.continuous_monitoring(interval=args.interval)
        else:
            await monitor.snapshot_test(iterations=args.iterations)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
