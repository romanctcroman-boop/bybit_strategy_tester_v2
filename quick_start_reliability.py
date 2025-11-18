"""
Quick Start: MCP Reliability System
Быстрый запуск для проверки работоспособности системы
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


async def quick_start_demo():
    """Quick demonstration of MCP reliability system"""
    
    print("=" * 80)
    print("🚀 MCP RELIABILITY SYSTEM - QUICK START DEMO")
    print("=" * 80)
    print()
    
    # Import reliability system
    from reliability_auto_system import (
        on_ide_startup,
        on_ide_shutdown,
        send_ai_request,
        get_system_status,
        reliability_system
    )
    
    # Step 1: System Startup
    print("📦 Step 1/5: Starting MCP Reliability System...")
    success = await on_ide_startup()
    
    if not success:
        print("❌ Failed to start system")
        return
    
    print("✅ System started successfully\n")
    await asyncio.sleep(2)
    
    # Step 2: Add Demo API Keys
    print("📦 Step 2/5: Adding demo API keys...")
    
    # NOTE: Replace with real API keys for production
    demo_keys = {
        "deepseek": [
            "sk-demo-deepseek-key-1",
            "sk-demo-deepseek-key-2"
        ],
        "perplexity": [
            "pplx-demo-perplexity-key-1",
            "pplx-demo-perplexity-key-2"
        ]
    }
    
    for service, keys in demo_keys.items():
        for key in keys:
            reliability_system.add_api_key(service, key)
    
    print(f"✅ Added {len(demo_keys['deepseek'])} DeepSeek keys")
    print(f"✅ Added {len(demo_keys['perplexity'])} Perplexity keys\n")
    await asyncio.sleep(1)
    
    # Step 3: Check System Status
    print("📦 Step 3/5: Checking system status...")
    status = get_system_status()
    
    print(f"   System Running: {'✅' if status['system_running'] else '❌'}")
    print(f"   MCP Running: {'✅' if status['mcp_running'] else '⚠️ (will use Direct API)'}")
    print(f"   Monitor Active: {'✅' if status['monitor_active'] else '❌'}")
    print(f"   Connection Mode: {status['current_mode'].upper()}")
    print(f"   DeepSeek Keys: {status['key_status']['deepseek_keys']}")
    print(f"   Perplexity Keys: {status['key_status']['perplexity_keys']}")
    print()
    await asyncio.sleep(2)
    
    # Step 4: Demonstrate Request Flow
    print("📦 Step 4/5: Testing request flow...")
    print("   NOTE: This will fail without real API keys, but demonstrates routing\n")
    
    try:
        test_request = {
            "service": "deepseek",
            "query": "Quick test: What is 2+2?",
            "max_tokens": 50
        }
        
        print(f"   📤 Sending: {test_request['query']}")
        print(f"   🔄 Route: {status['current_mode'].upper()}")
        
        result = await send_ai_request(test_request)
        
        print(f"   📥 Success! Source: {result.get('source', 'unknown')}")
        print(f"   📝 Response: {result.get('content', '')[:100]}...\n")
    
    except Exception as e:
        print(f"   ⚠️ Expected failure (demo keys): {type(e).__name__}")
        print(f"   ℹ️ Replace demo keys with real keys in Step 2 to test properly\n")
    
    await asyncio.sleep(2)
    
    # Step 5: Monitor Health (short cycle)
    print("📦 Step 5/5: Monitoring health (10 seconds)...")
    print("   Self-healing monitor is running in background...")
    
    await asyncio.sleep(10)
    
    # Final status
    final_status = get_system_status()
    monitor_metrics = final_status['monitor_metrics']
    
    print(f"\n   📊 Health Check Cycles: {monitor_metrics['total_checks']}")
    print(f"   ✅ Checks Passed: {monitor_metrics['health_checks_passed']}")
    print(f"   ❌ Checks Failed: {monitor_metrics['health_checks_failed']}")
    
    # Shutdown
    print("\n📦 Shutting down system...")
    await on_ide_shutdown()
    
    print("\n" + "=" * 80)
    print("✅ DEMO COMPLETE")
    print("=" * 80)
    print()
    print("📚 Next Steps:")
    print("   1. Run full test suite: python test_reliability_system.py")
    print("   2. Add real API keys: See MCP_RELIABILITY_CRISIS_COMPLETE.md")
    print("   3. Integrate with IDE: Follow deployment guide")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(quick_start_demo())
    except KeyboardInterrupt:
        print("\n\n⏹️ Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
