"""
🎯 Phase 1 Direct Python Verification
Проверяет Phase 1 features напрямую через UnifiedAgentInterface (без HTTP)
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.agents.unified_agent_interface import get_agent_interface


async def verify_phase1_direct():
    """Прямая проверка Phase 1 через Python"""
    
    print("=" * 70)
    print("🎯 Phase 1 Direct Python Verification (No HTTP)")
    print("=" * 70)
    print()
    
    # Get agent interface
    print("1️⃣ Initializing UnifiedAgentInterface...")
    agent = get_agent_interface()
    print("   ✅ Agent interface initialized")
    print()
    
    # Get stats
    print("2️⃣ Fetching Phase 1 stats...")
    stats = agent.get_stats()
    print("   ✅ Stats retrieved")
    print()
    
    # Circuit Breakers
    print("3️⃣ Circuit Breaker Status:")
    if "circuit_breakers" in stats:
        cb_data = stats["circuit_breakers"]
        # Handle nested structure: circuit_breakers.breakers.{name}
        breakers = cb_data.get("breakers", {}) if isinstance(cb_data, dict) else {}
        print(f"   📊 Total breakers: {len(breakers)}")
        for name, metrics in breakers.items():
            state = metrics.get("state", "UNKNOWN") if isinstance(metrics, dict) else "UNKNOWN"
            calls = metrics.get("total_calls", 0) if isinstance(metrics, dict) else 0
            failures = metrics.get("failed_calls", 0) if isinstance(metrics, dict) else 0
            trips = metrics.get("total_trips", 0) if isinstance(metrics, dict) else 0
            
            state_icon = "🟢" if state == "CLOSED" else "🔴" if state == "OPEN" else "🟡"
            print(f"   {state_icon} {name}:")
            print(f"      State: {state}")
            print(f"      Calls: {calls} | Failures: {failures} | Trips: {trips}")
    else:
        print("   ❌ No circuit breaker data!")
    print()
    
    # Health Monitoring
    print("4️⃣ Health Monitoring Status:")
    if "health_monitoring" in stats:
        health = stats["health_monitoring"]
        monitoring_active = health.get("monitoring_active", False)
        components = health.get("components_monitored", [])
        recovery_count = health.get("recovery_attempts", 0)
        recovery_rate = health.get("recovery_success_rate", 0.0)
        
        print(f"   🏥 Monitoring active: {'✅ Yes' if monitoring_active else '⚠️ No (will start after asyncio event loop)'}")
        print(f"   📦 Components monitored: {len(components)}")
        for comp in components:
            print(f"      • {comp}")
        print(f"   🔄 Recovery attempts: {recovery_count}")
        print(f"   📈 Recovery success rate: {recovery_rate:.1f}%")
    else:
        print("   ❌ No health monitoring data!")
    print()
    
    # Autonomy Score
    print("5️⃣ Autonomy Score:")
    if "autonomy_score" in stats:
        score = stats["autonomy_score"]
        print(f"   🎯 Current score: {score:.2f}/10")
        
        if score >= 8.5:
            print(f"   🌟 EXCELLENT - Target achieved!")
        elif score >= 8.0:
            print(f"   ✅ GOOD - Close to target (8.5)")
        elif score >= 7.0:
            print(f"   ⚠️ FAIR - Below target but operational")
        elif score >= 3.0:
            print(f"   ℹ️ BASELINE - No failures yet (expected)")
        else:
            print(f"   ❌ POOR - Needs attention")
    else:
        print("   ❌ No autonomy score!")
    print()
    
    # API Keys
    print("6️⃣ API Keys Status:")
    deepseek_keys = stats.get("deepseek_keys_active", 0)
    perplexity_keys = stats.get("perplexity_keys_active", 0)
    print(f"   🔑 DeepSeek: {deepseek_keys}/8 active")
    print(f"   🔑 Perplexity: {perplexity_keys}/8 active")
    print()
    
    # MCP Server
    print("7️⃣ MCP Server Status:")
    mcp_available = stats.get("mcp_available", False)
    mcp_tool_count = stats.get("mcp_tool_count", 0)
    print(f"   🛠️ MCP available: {'✅ Yes' if mcp_available else '⚠️ No (standalone mode)'}")
    print(f"   🧰 Tools registered: {mcp_tool_count}")
    print()
    
    # Summary
    print("=" * 70)
    print("📋 Phase 1 Verification Summary")
    print("=" * 70)
    
    checks = []
    cb_data = stats.get("circuit_breakers", {})
    breakers = cb_data.get("breakers", {}) if isinstance(cb_data, dict) else {}
    checks.append(("Circuit breakers registered", len(breakers) == 3))
    checks.append(("All breakers CLOSED", all(m.get("state") == "CLOSED" for m in breakers.values() if isinstance(m, dict))))
    checks.append(("Health monitoring configured", "health_monitoring" in stats))
    checks.append(("Health checks registered", len(stats.get("health_monitoring", {}).get("components_monitored", [])) == 3))
    checks.append(("Autonomy score calculated", "autonomy_score" in stats))
    checks.append(("All DeepSeek keys loaded", deepseek_keys == 8))
    checks.append(("All Perplexity keys loaded", perplexity_keys == 8))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        icon = "✅" if result else "❌"
        print(f"{icon} {name}")
    
    print()
    print(f"Overall: {passed}/{total} checks passed ({passed/total*100:.1f}%)")
    print()
    
    if passed == total:
        print("🎉 Phase 1 FULLY OPERATIONAL!")
        print("   ✅ Circuit Breakers: Working")
        print("   ✅ Health Monitoring: Ready (will activate on first event loop)")
        print("   ✅ Autonomy Scoring: Functional")
        print()
        print("📝 Next Steps:")
        print("   1. Start backend: uvicorn backend.api.app:app")
        print("   2. Monitor logs for health checks every 30s")
        print("   3. Watch autonomy score improve with real failures")
        print("   4. Deploy to staging when ready")
    elif passed >= total * 0.8:
        print("✅ Phase 1 MOSTLY OPERATIONAL - Review minor issues")
    else:
        print("⚠️ Phase 1 NEEDS ATTENTION - Check implementation")
    
    print("=" * 70)
    
    # Pretty-print all stats
    print()
    print("📄 Full Stats JSON:")
    print("-" * 70)
    import json
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    asyncio.run(verify_phase1_direct())
