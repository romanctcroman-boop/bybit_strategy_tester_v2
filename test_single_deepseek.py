"""
Single DeepSeek test with debugging
"""

import asyncio
import os
from dotenv import load_dotenv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

# Import the MultiKeyDeepSeekAgent
from test_enhanced_cross_agent import MultiKeyDeepSeekAgent

async def main():
    print("\n" + "="*80)
    print("🔍 SINGLE DEEPSEEK TEST WITH DEBUG")
    print("="*80 + "\n")
    
    # Load keys
    deepseek_keys = []
    for i in range(1, 9):
        key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
        if key:
            deepseek_keys.append(key)
    
    print(f"✅ Loaded {len(deepseek_keys)} DeepSeek keys\n")
    
    # Create agent
    agent = MultiKeyDeepSeekAgent(api_keys=deepseek_keys)
    
    # Test query
    query = "Hello! Just say OK."
    
    print(f"📝 Query: {query}")
    print(f"⏱️  Starting request...\n")
    
    try:
        result = await asyncio.wait_for(
            agent.generate(query, timeout=10.0),
            timeout=15.0
        )
        
        print(f"\n✅ RESULT:")
        print(f"   Success: {result.get('success')}")
        print(f"   Content: {result.get('content', 'N/A')[:200]}")
        print(f"   Error: {result.get('error', 'N/A')}")
        print(f"   Key used: {result.get('key_used', 'N/A')}")
        
    except asyncio.TimeoutError:
        print(f"\n❌ TIMEOUT after 15s")
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")


if __name__ == "__main__":
    asyncio.run(main())
