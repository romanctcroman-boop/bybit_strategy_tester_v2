"""
Тест Perplexity Agent - Анализ Bitcoin
"""

import asyncio
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2/mcp-server')

from server import initialize_providers, _call_perplexity_api

print("=" * 80)
print("TESTING PERPLEXITY AGENT - BITCOIN ANALYSIS")
print("=" * 80)

# Единая async функция для всего процесса
async def main():
    # Инициализируем все провайдеры
    print("\n🔧 Initializing MCP providers...")
    await initialize_providers()
    
    print("\n✅ Perplexity API ready!")
    print("\n📝 Analyzing Bitcoin market...")
    
    # Тестируем Perplexity API
    result = await _call_perplexity_api(
        query="What is the current Bitcoin price and market sentiment? Provide brief analysis.",
        model="sonar",  # Быстрая модель
        use_cache=False  # Свежие данные
    )
    return result

# Запускаем в едином event loop
result = asyncio.run(main())

print("\n✅ Analysis complete!")
print(f"   Success: {result.get('success', False)}")
print(f"   Model: {result.get('model', 'unknown')}")
print(f"   Provider: {result.get('provider', 'unknown')}")
print(f"   Cached: {result.get('cached', False)}")

if result.get('success'):
    print(f"\n📄 Bitcoin Analysis:")
    print("=" * 80)
    print(result.get('answer', 'No answer'))
    print("=" * 80)
    
    sources = result.get('sources', [])
    if sources:
        print(f"\n📚 Sources ({len(sources)}):")
        for i, source in enumerate(sources[:3], 1):
            print(f"   {i}. {source.get('title', 'Unknown')}: {source.get('url', 'N/A')}")
    
    usage = result.get('usage', {})
    if usage:
        print(f"\n📊 Token Usage:")
        print(f"   Prompt: {usage.get('prompt_tokens', 0)}")
        print(f"   Completion: {usage.get('completion_tokens', 0)}")
        print(f"   Total: {usage.get('total_tokens', 0)}")
else:
    print(f"\n❌ Error: {result.get('error', 'Unknown error')}")

print("\n" + "=" * 80)
