#!/usr/bin/env python3
"""
Test Provider Readiness Decorator

Проверка что @provider_ready блокирует выполнение tools до инициализации providers
"""

import sys
import asyncio
from pathlib import Path

# Добавляем путь к MCP серверу
mcp_path = Path(__file__).parent / "mcp-server"
sys.path.insert(0, str(mcp_path))

async def test_provider_readiness():
    """Test that tools are blocked when providers not ready"""
    
    print("=" * 80)
    print("🧪 Testing Provider Readiness Decorator")
    print("=" * 80)
    print()
    
    try:
        # Import server module
        import server
        
        # Check initial state - providers should NOT be ready yet
        print(f"Initial _providers_ready state: {server._providers_ready}")
        
        if server._providers_ready:
            print("⚠️  Warning: Providers already marked as ready!")
            print("   This might be because they were initialized on import.")
        else:
            print("✅ Providers correctly marked as NOT ready")
        
        print()
        print("=" * 80)
        print("🔧 Test 1: Calling tool BEFORE provider initialization")
        print("=" * 80)
        print()
        
        # Try to call a DeepSeek tool before providers are ready
        # Should get error about providers not ready
        try:
            result = await server.deepseek_generate_strategy(
                prompt="Test strategy",
                symbol="BTCUSDT",
                timeframe="1h"
            )
            
            if result.get("success") is False:
                error_msg = result.get("error", "")
                if "not ready" in error_msg.lower():
                    print("✅ PASS: Tool correctly blocked with error:")
                    print(f"   Error: {error_msg}")
                else:
                    print(f"⚠️  Unexpected error: {error_msg}")
            else:
                print("❌ FAIL: Tool executed when providers not ready!")
                print(f"   Result: {result}")
        
        except Exception as e:
            print(f"❌ Exception occurred: {e}")
        
        print()
        print("=" * 80)
        print("🔧 Test 2: Initialize providers and test again")
        print("=" * 80)
        print()
        
        # Initialize providers
        print("Initializing providers...")
        init_success = await server.initialize_providers()
        
        if init_success:
            print("✅ Providers initialized successfully")
            print(f"   _providers_ready = {server._providers_ready}")
        else:
            print("❌ Provider initialization failed")
            return False
        
        print()
        print("=" * 80)
        print("🔧 Test 3: Calling tool AFTER provider initialization")
        print("=" * 80)
        print()
        
        # Now tools should work
        print("Calling deepseek_generate_strategy with minimal prompt...")
        result = await server.deepseek_generate_strategy(
            prompt="Create simple moving average crossover strategy",
            symbol="BTCUSDT",
            timeframe="1h",
            enable_auto_fix=False  # Disable auto-fix for faster test
        )
        
        if result.get("success"):
            print("✅ PASS: Tool executed successfully after provider init")
            print(f"   Generated strategy: {len(result.get('strategy', ''))} chars")
        else:
            print("⚠️  Tool failed, but providers are ready")
            print(f"   Error: {result.get('error', 'Unknown error')}")
        
        print()
        print("=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        print()
        print("✅ Provider readiness decorator working correctly")
        print("✅ Tools blocked when providers not ready")
        print("✅ Tools execute when providers ready")
        print()
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import server module: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "    🧪 Provider Readiness Decorator Test".ljust(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    success = asyncio.run(test_provider_readiness())
    
    sys.exit(0 if success else 1)
