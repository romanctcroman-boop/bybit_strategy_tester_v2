#!/usr/bin/env python3
"""
Тестирование MCP инструментов напрямую
Обход STDIO транспорта для direct testing
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# DO NOT import mcp-server/server.py - it starts STDIO server immediately

async def test_deepseek_agent():
    """Test DeepSeek Agent initialization"""
    print("\n🧪 Testing DeepSeek Agent...")
    
    try:
        from backend.api.deepseek_pool import get_deepseek_agent
        
        agent = await get_deepseek_agent()
        print(f"✅ DeepSeek Agent initialized")
        print(f"   Client type: {type(agent.client).__name__}")
        
        # Test simple generation
        print("\n📝 Testing code generation...")
        result = await agent.generate_code(
            prompt="Create a simple Python function that calculates fibonacci numbers",
            max_tokens=200
        )
        
        print(f"✅ Generated {len(result)} characters")
        print(f"Preview: {result[:150]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_perplexity_search():
    """Test Perplexity API"""
    print("\n🧪 Testing Perplexity Search...")
    
    try:
        from backend.api.perplexity_client import PerplexityClient
        from backend.security.key_manager import KeyManager
        
        # Load keys
        key_manager = KeyManager()
        api_key = key_manager.get_key("PERPLEXITY_API_KEY")
        
        if not api_key:
            print("❌ No Perplexity API key found")
            return False
        
        client = PerplexityClient(api_key=api_key)
        
        # Test search
        print("\n🔍 Searching for latest Bitcoin price...")
        result = await client.search(
            query="What is the current Bitcoin price?",
            model="sonar"
        )
        
        print(f"✅ Search completed")
        print(f"Response: {result.get('content', '')[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_system_health():
    """Test system components"""
    print("\n🧪 Testing System Health...")
    
    try:
        from backend.security.key_manager import KeyManager
        
        # Test key manager
        km = KeyManager()
        keys = km.list_keys()
        print(f"✅ KeyManager loaded {len(keys)} keys")
        print(f"   Keys: {', '.join(keys)}")
        
        # Check DeepSeek keys
        deepseek_keys = [k for k in keys if 'DEEPSEEK' in k]
        print(f"✅ DeepSeek keys: {len(deepseek_keys)}")
        
        # Check Perplexity keys
        perplexity_keys = [k for k in keys if 'PERPLEXITY' in k]
        print(f"✅ Perplexity keys: {len(perplexity_keys)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("="*60)
    print("🚀 MCP Tools Testing Suite")
    print("="*60)
    
    results = {}
    
    # Test 1: System Health
    results['system_health'] = await test_system_health()
    
    # Test 2: DeepSeek Agent
    results['deepseek_agent'] = await test_deepseek_agent()
    
    # Test 3: Perplexity Search
    results['perplexity_search'] = await test_perplexity_search()
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Results:")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    print(f"\n🎯 Total: {total_passed}/{total_tests} tests passed")
    
    return total_passed == total_tests


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
