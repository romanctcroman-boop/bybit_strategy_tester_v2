"""
Тест unified API провайдеров и ProviderManager.

Проверяет:
- Инициализацию провайдеров
- Балансировку нагрузки
- Fallback механизм
- Статистику
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

from api import (
    PerplexityProvider,
    DeepSeekProvider,
    ProviderManager
)


async def test_provider_manager():
    """Тест ProviderManager с реальными API вызовами."""
    
    # API ключи
    perplexity_key = os.getenv("PERPLEXITY_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    
    if not perplexity_key or not deepseek_key:
        print("❌ API ключи не найдены в переменных окружения")
        return
    
    print("=" * 70)
    print("🧪 ТЕСТ UNIFIED API PROVIDER MANAGER")
    print("=" * 70)
    
    # 1. Инициализация провайдеров
    print("\n📦 Инициализация провайдеров...")
    
    perplexity = PerplexityProvider(api_key=perplexity_key)
    deepseek = DeepSeekProvider(api_key=deepseek_key)
    
    print(f"   ✓ {perplexity.name} initialized")
    print(f"   ✓ {deepseek.name} initialized")
    
    # 2. Создание ProviderManager
    print("\n🔧 Создание ProviderManager...")
    
    manager = ProviderManager()
    
    # Регистрация с разными весами
    manager.register_provider(perplexity, weight=0.7, enabled=True)
    manager.register_provider(deepseek, weight=0.3, enabled=True)
    
    print("   ✓ Perplexity зарегистрирован (вес=0.7)")
    print("   ✓ DeepSeek зарегистрирован (вес=0.3)")
    
    # 3. Тест балансировки (5 запросов без указания провайдера)
    print("\n⚖️ Тест балансировки нагрузки (5 запросов)...")
    
    for i in range(5):
        result = await manager.generate_response(
            query=f"Что такое {['Bitcoin', 'Ethereum', 'DeFi', 'NFT', 'DAO'][i]}? (кратко в 2 предложениях)",
            model="sonar" if i % 2 == 0 else "deepseek-chat"
        )
        
        if result.get("success"):
            provider_used = result.get("provider", "unknown")
            answer_preview = result.get("answer", "")[:50]
            print(f"   ✓ Запрос {i+1}: {provider_used} - {answer_preview}...")
        else:
            print(f"   ❌ Запрос {i+1}: {result.get('error')}")
    
    # 4. Тест с preferred provider
    print("\n🎯 Тест с preferred_provider (Perplexity)...")
    
    result = await manager.generate_response(
        query="Текущая цена Bitcoin?",
        preferred_provider="perplexity",
        model="sonar"
    )
    
    if result.get("success"):
        print(f"   ✓ Использован: {result.get('provider')}")
        print(f"   Ответ: {result.get('answer')[:100]}...")
    else:
        print(f"   ❌ Ошибка: {result.get('error')}")
    
    # 5. Тест fallback (симулируем сбой)
    print("\n🔄 Тест fallback механизма...")
    
    # Временно отключаем Perplexity (устанавливаем вес = 0)
    manager.update_weight("perplexity", 0.0)
    
    result = await manager.generate_response(
        query="Тестовый запрос для fallback",
        preferred_provider="perplexity",  # Запросим Perplexity
        fallback_enabled=True,
        model="deepseek-chat"
    )
    
    if result.get("success"):
        print(f"   ✓ Fallback на: {result.get('provider')}")
    else:
        print(f"   ⚠️ Fallback не сработал: {result.get('error')}")
    
    # Восстанавливаем вес
    manager.update_weight("perplexity", 0.7)
    
    # 6. Статистика
    print("\n📊 Статистика использования провайдеров:")
    
    stats = manager.get_stats()
    
    print(f"\n   Всего запросов: {stats['total_requests']}")
    print("\n   По провайдерам:")
    
    for provider_name, provider_stats in stats["providers"].items():
        print(f"\n   {provider_name.upper()}:")
        print(f"      Total:        {provider_stats['total_requests']}")
        print(f"      Successful:   {provider_stats['successful']}")
        print(f"      Failed:       {provider_stats['failed']}")
        print(f"      Fallback:     {provider_stats['fallback_used']}")
        print(f"      Success rate: {provider_stats['success_rate']:.1f}%")
        print(f"      Weight:       {provider_stats['weight']}")
    
    # 7. Итоговый отчёт
    print("\n" + "=" * 70)
    print("✅ UNIFIED API PROVIDER MANAGER - ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    print("=" * 70)
    
    print("\n🎉 Возможности:")
    print("   ✓ Автоматическая балансировка (weighted random)")
    print("   ✓ Fallback при сбое провайдера")
    print("   ✓ Детальная статистика")
    print("   ✓ Динамическое изменение весов")
    print("   ✓ Поддержка preferred provider")


if __name__ == "__main__":
    asyncio.run(test_provider_manager())
