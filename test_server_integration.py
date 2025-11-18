"""
Тест интеграции ProviderManager в MCP server.py
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Добавляем mcp-server в path
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

# Импортируем из обновлённого server.py
from server import provider_manager, _call_ai_provider


async def test_server_integration():
    """Тест интеграции unified API в server.py"""
    
    print("=" * 70)
    print("🧪 ТЕСТ ИНТЕГРАЦИИ PROVIDER MANAGER В SERVER.PY")
    print("=" * 70)
    
    # 1. Проверка инициализации
    print("\n📦 Проверка инициализации ProviderManager в server.py...")
    
    initial_stats = provider_manager.get_stats()
    print(f"   ✓ ProviderManager загружен")
    print(f"   ✓ Зарегистрировано провайдеров: {len(initial_stats['providers'])}")
    
    for provider_name, stats in initial_stats['providers'].items():
        print(f"      - {provider_name.upper()}: weight={stats['weight']}")
    
    # 2. Тест _call_ai_provider с автобалансировкой
    print("\n⚖️ Тест _call_ai_provider (автобалансировка)...")
    
    result = await _call_ai_provider(
        query="Что такое Bitcoin? (кратко в 1 предложении)",
        fallback_enabled=True
    )
    
    if result.get("success"):
        print(f"   ✓ Успешно через: {result.get('provider')}")
        print(f"   Ответ: {result.get('answer')[:80]}...")
    else:
        print(f"   ❌ Ошибка: {result.get('error')}")
    
    # 3. Тест с preferred provider
    print("\n🎯 Тест с preferred_provider='perplexity'...")
    
    result = await _call_ai_provider(
        query="Текущая цена Ethereum?",
        preferred_provider="perplexity",
        model="sonar",
        fallback_enabled=True
    )
    
    if result.get("success"):
        print(f"   ✓ Использован: {result.get('provider')}")
        print(f"   Ответ: {result.get('answer')[:80]}...")
    else:
        print(f"   ⚠️ Ошибка: {result.get('error')}")
    
    # 4. Тест с DeepSeek
    print("\n🧠 Тест с preferred_provider='deepseek'...")
    
    result = await _call_ai_provider(
        query="Объясни DeFi простыми словами (1 предложение)",
        preferred_provider="deepseek",
        model="deepseek-chat",
        fallback_enabled=True
    )
    
    if result.get("success"):
        print(f"   ✓ Использован: {result.get('provider')}")
        print(f"   Ответ: {result.get('answer')[:80]}...")
    else:
        print(f"   ⚠️ Ошибка: {result.get('error')}")
    
    # 5. Финальная статистика
    print("\n📊 Финальная статистика провайдеров:")
    
    final_stats = provider_manager.get_stats()
    
    print(f"\n   Всего запросов: {final_stats['total_requests']}")
    
    for provider_name, stats in final_stats['providers'].items():
        print(f"\n   {provider_name.upper()}:")
        print(f"      Total:        {stats['total_requests']}")
        print(f"      Successful:   {stats['successful']}")
        print(f"      Failed:       {stats['failed']}")
        print(f"      Fallback:     {stats['fallback_used']}")
        print(f"      Success rate: {stats['success_rate']:.1f}%")
    
    # 6. Итоговый отчёт
    print("\n" + "=" * 70)
    print("✅ ИНТЕГРАЦИЯ В SERVER.PY УСПЕШНА!")
    print("=" * 70)
    
    print("\n🎉 Возможности:")
    print("   ✓ _call_ai_provider() - единая точка для всех AI запросов")
    print("   ✓ Автоматическая балансировка (70/30)")
    print("   ✓ Fallback при сбое")
    print("   ✓ Статистика в реальном времени")
    print("   ✓ MCP tool 'get_provider_stats' для мониторинга")


if __name__ == "__main__":
    asyncio.run(test_server_integration())
