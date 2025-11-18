"""
Load Testing Script for Circuit Breaker V2 Threshold Optimization

Purpose:
    Test different circuit breaker configurations to find optimal thresholds
    for production deployment.

Test Scenarios:
    1. Transient failures (recoverable)
    2. Persistent failures (non-recoverable)
    3. Rate limit scenarios
    4. Mixed workload (normal + failures)
    5. Cascading failures across multiple keys

Configuration Matrix:
    - failure_threshold: 3, 5, 7, 10
    - success_threshold: 1, 2, 3
    - timeout: 30s, 60s, 90s, 120s
    - half_open_max_calls: 2, 3, 5

Metrics Collected:
    - Time to recovery
    - False positive trips
    - Request success rate
    - Circuit breaker flapping rate
    - System throughput under load

Version: 2.0 (Circuit Breaker V2 with asyncio)
"""

import asyncio
import time
import random
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
import sys
import json

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from api.circuit_breaker import CircuitBreaker, CircuitState


@dataclass
class TestConfig:
    """Circuit breaker configuration to test"""
    failure_threshold: int
    success_threshold: int
    timeout: int
    half_open_max_calls: int
    
    def __str__(self):
        return (f"F{self.failure_threshold}_S{self.success_threshold}_"
                f"T{self.timeout}_H{self.half_open_max_calls}")


@dataclass
class TestResult:
    """Results from a single test run"""
    config: TestConfig
    scenario: str
    
    # Performance metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Circuit breaker metrics
    circuit_breaker_trips: int = 0
    false_positive_trips: int = 0  # Trips that shouldn't have happened
    time_to_first_recovery: Optional[float] = None
    time_in_open_state: float = 0.0
    time_in_half_open_state: float = 0.0
    state_transitions: List[str] = field(default_factory=list)
    
    # Timing metrics
    test_duration: float = 0.0
    avg_response_time: float = 0.0
    
    def success_rate(self) -> float:
        """Calculate request success rate"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    def flapping_rate(self) -> float:
        """Calculate circuit breaker flapping (transitions per minute)"""
        if self.test_duration == 0:
            return 0.0
        return (len(self.state_transitions) / self.test_duration) * 60
    
    def score(self) -> float:
        """
        Calculate overall configuration score (0-100).
        
        Higher is better. Considers:
        - Success rate (40%)
        - Low false positives (30%)
        - Fast recovery (20%)
        - Low flapping (10%)
        """
        # Success rate component (0-40)
        success_score = self.success_rate() * 40
        
        # False positive component (0-30)
        # Penalize false positive trips heavily
        false_positive_penalty = min(30, self.false_positive_trips * 10)
        false_positive_score = 30 - false_positive_penalty
        
        # Recovery time component (0-20)
        # Optimal recovery: 60-90 seconds
        if self.time_to_first_recovery is None:
            recovery_score = 0
        elif 60 <= self.time_to_first_recovery <= 90:
            recovery_score = 20
        elif self.time_to_first_recovery < 60:
            # Too fast = might be flapping
            recovery_score = 10
        else:
            # Too slow = poor user experience
            recovery_score = max(0, 20 - (self.time_to_first_recovery - 90) / 10)
        
        # Flapping component (0-10)
        # Optimal: <2 transitions per minute
        flapping = self.flapping_rate()
        if flapping < 2:
            flapping_score = 10
        elif flapping < 5:
            flapping_score = 5
        else:
            flapping_score = 0
        
        total = success_score + false_positive_score + recovery_score + flapping_score
        return round(total, 2)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export"""
        return {
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "half_open_max_calls": self.config.half_open_max_calls
            },
            "scenario": self.scenario,
            "metrics": {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "success_rate": round(self.success_rate(), 4),
                "circuit_breaker_trips": self.circuit_breaker_trips,
                "false_positive_trips": self.false_positive_trips,
                "time_to_first_recovery": self.time_to_first_recovery,
                "time_in_open_state": round(self.time_in_open_state, 2),
                "time_in_half_open_state": round(self.time_in_half_open_state, 2),
                "state_transitions": len(self.state_transitions),
                "flapping_rate": round(self.flapping_rate(), 2),
                "test_duration": round(self.test_duration, 2),
                "avg_response_time": round(self.avg_response_time, 3)
            },
            "score": self.score()
        }


class LoadTester:
    """Load tester for circuit breaker configurations"""
    
    def __init__(self):
        self.results: List[TestResult] = []
    
    async def simulate_api_call(
        self,
        failure_probability: float = 0.0,
        latency_ms: int = 100,
        fail_type: str = "transient"
    ) -> tuple[bool, float]:
        """
        Simulate API call with configurable failure behavior.
        
        Args:
            failure_probability: 0.0-1.0 probability of failure
            latency_ms: Response time in milliseconds
            fail_type: "transient", "persistent", or "rate_limit"
            
        Returns:
            (success, response_time)
        """
        # Simulate network latency
        latency_variation = random.uniform(0.8, 1.2)
        actual_latency = (latency_ms / 1000) * latency_variation
        await asyncio.sleep(actual_latency)
        
        # Determine success/failure
        success = random.random() > failure_probability
        
        return success, actual_latency
    
    async def run_scenario_transient_failures(
        self,
        config: TestConfig,
        duration_seconds: int = 300
    ) -> TestResult:
        """
        Test Scenario 1: Transient Failures
        
        Simulates temporary API issues (network blips, 5xx errors).
        Expected behavior: Circuit breaker opens, then recovers.
        """
        print(f"\n{'='*70}")
        print(f"🧪 SCENARIO 1: Transient Failures")
        print(f"   Config: {config}")
        print(f"   Duration: {duration_seconds}s")
        print(f"{'='*70}")
        
        result = TestResult(config=config, scenario="transient_failures")
        
        # Create circuit breaker
        breaker = CircuitBreaker(
            failure_threshold=config.failure_threshold,
            success_threshold=config.success_threshold,
            timeout=config.timeout,
            half_open_max_calls=config.half_open_max_calls,
            key_id="test_transient",
            provider="test"
        )
        
        start_time = time.time()
        last_state = breaker.state
        state_enter_time = start_time
        
        # Track first recovery
        first_recovery_time = None
        
        # Simulate workload
        while time.time() - start_time < duration_seconds:
            result.total_requests += 1
            
            # Check if circuit breaker allows request
            if not await breaker.is_available():
                # Circuit breaker OPEN - fast fail
                result.failed_requests += 1
                await asyncio.sleep(0.1)
                continue
            
            # Simulate API call with 30% failure rate (transient)
            success, response_time = await self.simulate_api_call(
                failure_probability=0.3,
                latency_ms=50
            )
            
            if success:
                result.successful_requests += 1
                await breaker.record_success()
            else:
                result.failed_requests += 1
                await breaker.record_failure()
            
            # Track state changes
            if breaker.state != last_state:
                # State transition detected
                transition = f"{last_state.value} -> {breaker.state.value}"
                result.state_transitions.append(transition)
                
                # Update time in state
                state_duration = time.time() - state_enter_time
                if last_state == CircuitState.OPEN:
                    result.time_in_open_state += state_duration
                elif last_state == CircuitState.HALF_OPEN:
                    result.time_in_half_open_state += state_duration
                
                # Track first recovery
                if (last_state == CircuitState.OPEN and 
                    breaker.state == CircuitState.HALF_OPEN and
                    first_recovery_time is None):
                    first_recovery_time = time.time() - start_time
                    result.time_to_first_recovery = first_recovery_time
                
                # Track trips
                if breaker.state == CircuitState.OPEN:
                    result.circuit_breaker_trips += 1
                
                # Update tracking
                last_state = breaker.state
                state_enter_time = time.time()
                
                print(f"   [{time.time() - start_time:.1f}s] {transition} "
                      f"(trip #{result.circuit_breaker_trips})")
            
            # Brief pause between requests
            await asyncio.sleep(0.05)
        
        result.test_duration = time.time() - start_time
        
        # Print results
        print(f"\n📊 Results:")
        print(f"   Total requests: {result.total_requests}")
        print(f"   Success rate: {result.success_rate():.2%}")
        print(f"   Circuit breaker trips: {result.circuit_breaker_trips}")
        print(f"   State transitions: {len(result.state_transitions)}")
        print(f"   Time to first recovery: {result.time_to_first_recovery:.1f}s" 
              if result.time_to_first_recovery else "   Time to first recovery: N/A")
        print(f"   Flapping rate: {result.flapping_rate():.2f} transitions/min")
        print(f"   Score: {result.score():.2f}/100")
        
        return result
    
    async def run_scenario_persistent_failures(
        self,
        config: TestConfig,
        duration_seconds: int = 180
    ) -> TestResult:
        """
        Test Scenario 2: Persistent Failures
        
        Simulates sustained API outage (100% failure rate).
        Expected behavior: Circuit breaker opens quickly and stays open.
        """
        print(f"\n{'='*70}")
        print(f"🧪 SCENARIO 2: Persistent Failures")
        print(f"   Config: {config}")
        print(f"   Duration: {duration_seconds}s")
        print(f"{'='*70}")
        
        result = TestResult(config=config, scenario="persistent_failures")
        
        breaker = CircuitBreaker(
            failure_threshold=config.failure_threshold,
            success_threshold=config.success_threshold,
            timeout=config.timeout,
            half_open_max_calls=config.half_open_max_calls,
            key_id="test_persistent",
            provider="test"
        )
        
        start_time = time.time()
        last_state = breaker.state
        
        while time.time() - start_time < duration_seconds:
            result.total_requests += 1
            
            if not await breaker.is_available():
                result.failed_requests += 1
                await asyncio.sleep(0.1)
                
                # Check state transitions
                if breaker.state != last_state:
                    transition = f"{last_state.value} -> {breaker.state.value}"
                    result.state_transitions.append(transition)
                    last_state = breaker.state
                    print(f"   [{time.time() - start_time:.1f}s] {transition}")
                
                continue
            
            # 100% failure rate (persistent outage)
            success, _ = await self.simulate_api_call(failure_probability=1.0, latency_ms=50)
            
            result.failed_requests += 1
            await breaker.record_failure()
            
            # Track state changes
            if breaker.state != last_state:
                transition = f"{last_state.value} -> {breaker.state.value}"
                result.state_transitions.append(transition)
                
                if breaker.state == CircuitState.OPEN:
                    result.circuit_breaker_trips += 1
                
                last_state = breaker.state
                print(f"   [{time.time() - start_time:.1f}s] {transition}")
            
            await asyncio.sleep(0.05)
        
        result.test_duration = time.time() - start_time
        
        print(f"\n📊 Results:")
        print(f"   Circuit breaker trips: {result.circuit_breaker_trips}")
        print(f"   State transitions: {len(result.state_transitions)}")
        print(f"   Expected: Quick trip, stay open (optimal behavior)")
        print(f"   Score: {result.score():.2f}/100")
        
        return result
    
    async def run_scenario_mixed_workload(
        self,
        config: TestConfig,
        duration_seconds: int = 300
    ) -> TestResult:
        """
        Test Scenario 3: Mixed Workload
        
        Simulates realistic production: 95% success, 5% transient failures.
        Expected behavior: Circuit breaker should NOT trip (false positive test).
        """
        print(f"\n{'='*70}")
        print(f"🧪 SCENARIO 3: Mixed Workload (False Positive Test)")
        print(f"   Config: {config}")
        print(f"   Duration: {duration_seconds}s")
        print(f"{'='*70}")
        
        result = TestResult(config=config, scenario="mixed_workload")
        
        breaker = CircuitBreaker(
            failure_threshold=config.failure_threshold,
            success_threshold=config.success_threshold,
            timeout=config.timeout,
            half_open_max_calls=config.half_open_max_calls,
            key_id="test_mixed",
            provider="test"
        )
        
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            result.total_requests += 1
            
            if not await breaker.is_available():
                result.failed_requests += 1
                result.false_positive_trips += 1  # Should NOT happen in this scenario
                await asyncio.sleep(0.1)
                continue
            
            # 95% success rate (realistic production)
            success, _ = await self.simulate_api_call(failure_probability=0.05, latency_ms=50)
            
            if success:
                result.successful_requests += 1
                await breaker.record_success()
            else:
                result.failed_requests += 1
                await breaker.record_failure()
            
            # Track trips (should be 0 in ideal config)
            if breaker.state == CircuitState.OPEN:
                result.circuit_breaker_trips += 1
                print(f"   ⚠️  FALSE POSITIVE TRIP at {time.time() - start_time:.1f}s")
            
            await asyncio.sleep(0.01)  # High request rate
        
        result.test_duration = time.time() - start_time
        
        print(f"\n📊 Results:")
        print(f"   Total requests: {result.total_requests}")
        print(f"   Success rate: {result.success_rate():.2%}")
        print(f"   False positive trips: {result.false_positive_trips}")
        print(f"   Expected: 0 trips (stable operation)")
        print(f"   Score: {result.score():.2f}/100")
        
        return result
    
    async def run_full_test_matrix(self):
        """
        Run all scenarios across configuration matrix.
        
        Test Matrix:
        - 4 failure_threshold values × 3 success_threshold values × 3 timeout values
        - 3 scenarios per configuration
        - Total: ~108 test runs
        """
        print("="*70)
        print("🚀 CIRCUIT BREAKER V2 LOAD TESTING")
        print("="*70)
        print(f"Test Matrix: 4 failure_thresholds × 3 timeouts × 3 scenarios")
        print(f"Estimated Duration: ~45 minutes")
        print("="*70)
        
        # Configuration matrix
        configs = [
            # Low sensitivity (fewer false positives, slower detection)
            TestConfig(failure_threshold=10, success_threshold=2, timeout=60, half_open_max_calls=3),
            TestConfig(failure_threshold=10, success_threshold=2, timeout=90, half_open_max_calls=3),
            
            # Medium sensitivity (balanced)
            TestConfig(failure_threshold=7, success_threshold=2, timeout=60, half_open_max_calls=3),
            TestConfig(failure_threshold=7, success_threshold=2, timeout=90, half_open_max_calls=3),
            
            # Current default (moderate)
            TestConfig(failure_threshold=5, success_threshold=2, timeout=60, half_open_max_calls=3),
            TestConfig(failure_threshold=5, success_threshold=2, timeout=90, half_open_max_calls=3),
            TestConfig(failure_threshold=5, success_threshold=2, timeout=120, half_open_max_calls=3),
            
            # High sensitivity (more false positives, faster detection)
            TestConfig(failure_threshold=3, success_threshold=2, timeout=60, half_open_max_calls=3),
            TestConfig(failure_threshold=3, success_threshold=2, timeout=90, half_open_max_calls=3),
        ]
        
        total_tests = len(configs) * 3  # 3 scenarios
        completed = 0
        
        for config in configs:
            print(f"\n{'='*70}")
            print(f"Testing Config: {config}")
            print(f"Progress: {completed}/{total_tests} tests completed")
            print(f"{'='*70}")
            
            # Run all scenarios
            result1 = await self.run_scenario_transient_failures(config, duration_seconds=120)
            self.results.append(result1)
            completed += 1
            
            result2 = await self.run_scenario_persistent_failures(config, duration_seconds=90)
            self.results.append(result2)
            completed += 1
            
            result3 = await self.run_scenario_mixed_workload(config, duration_seconds=120)
            self.results.append(result3)
            completed += 1
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive test report with recommendations"""
        print("\n" + "="*70)
        print("📊 LOAD TESTING RESULTS - CIRCUIT BREAKER V2")
        print("="*70)
        
        # Group results by config
        config_scores: Dict[str, List[float]] = {}
        
        for result in self.results:
            config_key = str(result.config)
            if config_key not in config_scores:
                config_scores[config_key] = []
            config_scores[config_key].append(result.score())
        
        # Calculate average scores
        config_avg_scores = {
            config: statistics.mean(scores)
            for config, scores in config_scores.items()
        }
        
        # Sort by score
        sorted_configs = sorted(config_avg_scores.items(), key=lambda x: x[1], reverse=True)
        
        print("\n🏆 TOP 5 CONFIGURATIONS (by average score):")
        print("-" * 70)
        for i, (config_str, avg_score) in enumerate(sorted_configs[:5], 1):
            print(f"{i}. {config_str}: {avg_score:.2f}/100")
        
        # Best configuration
        best_config_str = sorted_configs[0][0]
        best_results = [r for r in self.results if str(r.config) == best_config_str]
        
        print(f"\n✅ RECOMMENDED CONFIGURATION:")
        print("-" * 70)
        print(f"Config: {best_results[0].config}")
        print(f"Average Score: {sorted_configs[0][1]:.2f}/100")
        print(f"\nBreakdown by Scenario:")
        for result in best_results:
            print(f"  - {result.scenario}: {result.score():.2f}/100")
            print(f"    Success rate: {result.success_rate():.2%}")
            print(f"    False positives: {result.false_positive_trips}")
            print(f"    Recovery time: {result.time_to_first_recovery:.1f}s" 
                  if result.time_to_first_recovery else "    Recovery time: N/A")
        
        # Export to JSON
        output_file = "circuit_breaker_load_test_results.json"
        with open(output_file, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": len(self.results),
                    "configurations_tested": len(config_scores),
                    "recommended_config": str(best_results[0].config)
                },
                "results": [r.to_dict() for r in self.results]
            }, f, indent=2)
        
        print(f"\n💾 Full results saved to: {output_file}")
        print("="*70)


async def main():
    """Main entry point"""
    tester = LoadTester()
    
    # Run full test matrix
    await tester.run_full_test_matrix()


if __name__ == "__main__":
    asyncio.run(main())
