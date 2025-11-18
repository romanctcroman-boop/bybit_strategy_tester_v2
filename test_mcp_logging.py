"""
Тест логирования MCP tools с новым inline logging
"""
import asyncio
import sys
from pathlib import Path

# Добавить MCP server в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

from server import (
    perplexity_search,
    perplexity_analyze_crypto,
    quick_reasoning_analysis,
    chain_of_thought_analysis,
    perplexity_batch_analyze
)


async def test_quick_wins():
    """Тестирование топ-5 tools с логированием"""
    
    print("=" * 80)
    print("🧪 TESTING MCP TOOLS LOGGING (Quick Win)")
    print("=" * 80)
    
    # Test 1: perplexity_search
    print("\n1️⃣ Testing perplexity_search...")
    try:
        result = await perplexity_search("Latest Bitcoin price")
        print(f"   ✅ Success: {result.get('success', False)}")
        print(f"   📊 Tokens: {result.get('usage', {}).get('total_tokens', 'N/A')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: perplexity_analyze_crypto
    print("\n2️⃣ Testing perplexity_analyze_crypto...")
    try:
        result = await perplexity_analyze_crypto("BTCUSDT", "1d")
        print(f"   ✅ Success: {result.get('success', False)}")
        print(f"   📊 Tokens: {result.get('usage', {}).get('total_tokens', 'N/A')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: quick_reasoning_analysis
    print("\n3️⃣ Testing quick_reasoning_analysis...")
    try:
        result = await quick_reasoning_analysis("What is the trend of BTC?")
        print(f"   ✅ Success: {len(result) > 0}")
        print(f"   📝 Answer length: {len(result)} chars")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: perplexity_batch_analyze
    print("\n4️⃣ Testing perplexity_batch_analyze...")
    try:
        queries = [
            {"query": "Bitcoin analysis", "model": "sonar"},
            {"query": "Ethereum trends", "model": "sonar-pro"}
        ]
        result = await perplexity_batch_analyze(queries, parallel=True)
        print(f"   ✅ Success: {result.get('success', False)}")
        print(f"   📊 Total tokens: {result.get('metrics', {}).get('total_tokens', 'N/A')}")
        print(f"   💰 Total cost: ${result.get('metrics', {}).get('total_cost', 0):.6f}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("✅ TESTING COMPLETE")
    print("=" * 80)
    
    # Проверим файл логирования
    print("\n📂 Checking log file...")
    log_file = project_root / "logs" / "mcp_activity.jsonl"
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"   📝 Total log entries: {len(lines)}")
            if lines:
                print(f"   📌 Latest entry:")
                import json
                latest = json.loads(lines[-1])
                print(f"      - Tool: {latest.get('tool')}")
                print(f"      - Status: {latest.get('status')}")
                print(f"      - Duration: {latest.get('duration_ms')}ms")
                print(f"      - Tokens: {latest.get('tokens')}")
                print(f"      - Cost: ${latest.get('cost'):.6f}")
    else:
        print(f"   ⚠️ Log file not found: {log_file}")


if __name__ == "__main__":
    asyncio.run(test_quick_wins())
