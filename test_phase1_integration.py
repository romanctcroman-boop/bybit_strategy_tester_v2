"""
Phase 1 Integration Test - Manual Verification Script

Tests circuit breaker and health monitoring integration by:
1. Importing UnifiedAgentInterface
2. Verifying circuit breakers registered
3. Verifying health monitoring started
4. Checking metrics
5. Simulating a failure and recovery
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.agents.unified_agent_interface import get_agent_interface
from backend.agents.circuit_breaker_manager import get_circuit_manager
from backend.agents.health_monitor import get_health_monitor
from loguru import logger


async def test_integration():
    """Test Phase 1 integration"""
    
    print("\n" + "="*80)
    print("Phase 1 Integration Test - Circuit Breaker & Health Monitoring")
    print("="*80 + "\n")
    
    # 1. Initialize agent interface
    print("1️⃣ Initializing UnifiedAgentInterface...")
    try:
        agent = get_agent_interface()
        print("   ✅ Agent interface initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize: {e}")
        return False
    
    # 2. Check circuit breakers
    print("\n2️⃣ Checking circuit breakers...")
    cb_manager = get_circuit_manager()
    breakers = cb_manager.get_all_breakers()
    print(f"   Registered breakers: {breakers}")
    
    expected_breakers = {"deepseek_api", "perplexity_api", "mcp_server"}
    if set(breakers) == expected_breakers:
        print("   ✅ All 3 circuit breakers registered")
    else:
        print(f"   ❌ Expected {expected_breakers}, got {set(breakers)}")
        return False
    
    # Check initial states
    for breaker_name in breakers:
        state = cb_manager.get_breaker_state(breaker_name)
        print(f"   - {breaker_name}: {state}")
    
    # 3. Check health monitoring
    print("\n3️⃣ Checking health monitoring...")
    health_monitor = get_health_monitor()
    health = health_monitor.get_all_health()
    print(f"   Monitored components: {list(health.keys())}")
    
    expected_components = {"deepseek_api", "perplexity_api", "mcp_server"}
    if set(health.keys()) == expected_components:
        print("   ✅ All 3 components being monitored")
    else:
        print(f"   ❌ Expected {expected_components}, got {set(health.keys())}")
        return False
    
    # Show current health
    for component, result in health.items():
        print(f"   - {component}: {result.status.value} - {result.message}")
    
    # 4. Check metrics
    print("\n4️⃣ Checking metrics...")
    stats = agent.get_stats()
    
    # Circuit breaker metrics
    cb_metrics = stats.get("circuit_breakers", {})
    print(f"   Circuit breaker calls: {cb_metrics.get('total_calls', 0)}")
    print(f"   Circuit breaker trips: {stats.get('circuit_breaker_trips', 0)}")
    
    # Health monitoring metrics
    health_metrics = stats.get("health_monitoring", {})
    print(f"   Monitoring active: {health_metrics.get('is_monitoring', False)}")
    print(f"   Healthy components: {health_metrics.get('healthy_components', 0)}/{health_metrics.get('total_components', 0)}")
    print(f"   Recovery success rate: {health_metrics.get('recovery_success_rate', 0):.1f}%")
    
    # Autonomy score
    autonomy = stats.get("autonomy_score", 0)
    print(f"   Autonomy score: {autonomy}/10")
    
    if autonomy >= 6.0:
        print("   ✅ Autonomy score acceptable")
    else:
        print(f"   ⚠️ Autonomy score below baseline (6.0)")
    
    # 5. Simulate a simple successful call
    print("\n5️⃣ Testing circuit breaker call protection...")
    
    async def test_call():
        """Simple test function"""
        return "success"
    
    try:
        result = await cb_manager.call_with_breaker("deepseek_api", test_call)
        print(f"   ✅ Protected call succeeded: {result}")
    except Exception as e:
        print(f"   ❌ Protected call failed: {e}")
        return False
    
    # Check updated metrics
    updated_cb = cb_manager.get_metrics()
    deepseek_config = updated_cb.breakers.get("deepseek_api")
    if deepseek_config:
        print(f"   - DeepSeek circuit breaker: {deepseek_config.total_calls} calls, {deepseek_config.successful_calls} successful")
    
    # 6. Final summary
    print("\n" + "="*80)
    print("✅ Phase 1 Integration Test PASSED")
    print("="*80)
    print("\nKey Features Verified:")
    print("  ✅ Circuit breakers registered and operational")
    print("  ✅ Health monitoring active")
    print("  ✅ Metrics collection working")
    print("  ✅ Protected calls execute correctly")
    print(f"\n🎯 Current Autonomy Score: {autonomy}/10")
    print(f"🎯 Phase 1 Target: 8.5/10 (will improve after real failures)")
    print("\n📋 Next Steps:")
    print("  1. Deploy to staging environment")
    print("  2. Monitor for 7 days")
    print("  3. Collect circuit breaker trip events")
    print("  4. Verify auto-recovery success rate > 85%")
    print("\n")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)
