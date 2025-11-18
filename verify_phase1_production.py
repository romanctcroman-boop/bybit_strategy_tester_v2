"""
🎯 Phase 1 Production Verification Script
Проверяет, что все Phase 1 features работают на запущенном бэкенде
"""
import asyncio
import httpx
import json
from datetime import datetime


async def verify_phase1():
    """Проверка Phase 1 features через API"""
    
    print("=" * 60)
    print("🎯 Phase 1 Production Verification")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    base_url = "http://127.0.0.1:8000"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 1. Basic health check
            print("1️⃣ Testing basic health endpoint...")
            response = await client.get(f"{base_url}/api/v1/health")
            if response.status_code == 200:
                print("   ✅ Backend is running")
            else:
                print(f"   ❌ Backend returned {response.status_code}")
                return
            print()
            
            # 2. Agent stats (Phase 1 metrics)
            print("2️⃣ Fetching Phase 1 metrics...")
            response = await client.get(f"{base_url}/api/v1/agent/stats")
            if response.status_code != 200:
                print(f"   ❌ Failed to fetch stats: {response.status_code}")
                return
            
            stats = response.json()
            print(f"   ✅ Agent stats retrieved")
            print()
            
            # 3. Circuit Breakers
            print("3️⃣ Circuit Breaker Status:")
            if "circuit_breakers" in stats:
                breakers = stats["circuit_breakers"]
                print(f"   📊 Total breakers: {len(breakers)}")
                for name, metrics in breakers.items():
                    state = metrics.get("current_state", "UNKNOWN")
                    calls = metrics.get("total_calls", 0)
                    failures = metrics.get("failure_count", 0)
                    trips = metrics.get("trips", 0)
                    
                    state_icon = "🟢" if state == "CLOSED" else "🔴" if state == "OPEN" else "🟡"
                    print(f"   {state_icon} {name}:")
                    print(f"      State: {state}")
                    print(f"      Calls: {calls} | Failures: {failures} | Trips: {trips}")
            else:
                print("   ⚠️ No circuit breaker data found")
            print()
            
            # 4. Health Monitoring
            print("4️⃣ Health Monitoring Status:")
            if "health_monitoring" in stats:
                health = stats["health_monitoring"]
                monitoring_active = health.get("monitoring_active", False)
                components = health.get("components_monitored", [])
                recovery_count = health.get("recovery_attempts", 0)
                recovery_rate = health.get("recovery_success_rate", 0.0)
                
                print(f"   🏥 Monitoring active: {'✅ Yes' if monitoring_active else '❌ No'}")
                print(f"   📦 Components monitored: {len(components)}")
                for comp in components:
                    print(f"      • {comp}")
                print(f"   🔄 Recovery attempts: {recovery_count}")
                print(f"   📈 Recovery success rate: {recovery_rate:.1f}%")
            else:
                print("   ⚠️ No health monitoring data found")
            print()
            
            # 5. Autonomy Score
            print("5️⃣ Autonomy Score:")
            if "autonomy_score" in stats:
                score = stats["autonomy_score"]
                print(f"   🎯 Current score: {score:.2f}/10")
                
                # Оценка
                if score >= 8.5:
                    print(f"   🌟 EXCELLENT - Target achieved!")
                elif score >= 8.0:
                    print(f"   ✅ GOOD - Close to target (8.5)")
                elif score >= 7.0:
                    print(f"   ⚠️ FAIR - Below target but operational")
                else:
                    print(f"   ❌ POOR - Needs attention")
            else:
                print("   ⚠️ No autonomy score found")
            print()
            
            # 6. API Keys Status
            print("6️⃣ API Keys Status:")
            deepseek_keys = stats.get("deepseek_keys_active", 0)
            perplexity_keys = stats.get("perplexity_keys_active", 0)
            print(f"   🔑 DeepSeek: {deepseek_keys}/8 active")
            print(f"   🔑 Perplexity: {perplexity_keys}/8 active")
            print()
            
            # 7. MCP Server
            print("7️⃣ MCP Server Status:")
            mcp_available = stats.get("mcp_available", False)
            mcp_tool_count = stats.get("mcp_tool_count", 0)
            print(f"   🛠️ MCP available: {'✅ Yes' if mcp_available else '❌ No'}")
            print(f"   🧰 Tools registered: {mcp_tool_count}")
            print()
            
            # Summary
            print("=" * 60)
            print("📋 Phase 1 Verification Summary")
            print("=" * 60)
            
            checks = []
            checks.append(("Backend running", response.status_code == 200))
            checks.append(("Circuit breakers registered", "circuit_breakers" in stats and len(stats["circuit_breakers"]) == 3))
            checks.append(("Health monitoring active", stats.get("health_monitoring", {}).get("monitoring_active", False)))
            checks.append(("Autonomy score calculated", "autonomy_score" in stats))
            checks.append(("All DeepSeek keys active", deepseek_keys == 8))
            checks.append(("All Perplexity keys active", perplexity_keys == 8))
            checks.append(("MCP Server available", mcp_available))
            
            passed = sum(1 for _, result in checks if result)
            total = len(checks)
            
            for name, result in checks:
                icon = "✅" if result else "❌"
                print(f"{icon} {name}")
            
            print()
            print(f"Overall: {passed}/{total} checks passed ({passed/total*100:.1f}%)")
            print()
            
            if passed == total:
                print("🎉 Phase 1 FULLY OPERATIONAL - Ready for staging!")
            elif passed >= total * 0.8:
                print("✅ Phase 1 MOSTLY OPERATIONAL - Minor issues")
            else:
                print("⚠️ Phase 1 NEEDS ATTENTION - Review failures")
            
            print("=" * 60)
            
            # Save full stats to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"phase1_verification_{timestamp}.json"
            with open(filename, "w") as f:
                json.dump(stats, f, indent=2)
            print(f"💾 Full stats saved to: {filename}")
            
        except httpx.ConnectError:
            print("❌ Cannot connect to backend at http://127.0.0.1:8000")
            print("   Make sure the backend is running:")
            print("   .\\venv\\Scripts\\python.exe -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(verify_phase1())
