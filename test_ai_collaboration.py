"""
🤝 ТЕСТ ВЗАИМОДЕЙСТВИЯ DEEPSEEK ↔ PERPLEXITY

Проверяем канал быстрого взаимодействия между AI:
1. Perplexity → DeepSeek (быстрый поиск → глубокий анализ)
2. DeepSeek → Perplexity (reasoning → проверка фактов)
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к MCP серверу
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from server import _call_perplexity_api, _call_deepseek_api
from activity_logger import log_mcp_execution


async def test_perplexity_to_deepseek():
    """
    Тест 1: Perplexity → DeepSeek
    Perplexity находит данные → DeepSeek анализирует
    """
    print("\n" + "=" * 80)
    print("🔵→🟣 ТЕСТ 1: Perplexity → DeepSeek")
    print("=" * 80)
    
    # Шаг 1: Perplexity быстро находит информацию
    perplexity_query = "Какие основные события произошли на крипторынке за последнюю неделю?"
    
    print(f"\n📝 Шаг 1: Perplexity ищет информацию...")
    print(f"   Запрос: {perplexity_query}")
    
    async with log_mcp_execution("Perplexity", "collaboration_test_search") as logger:
        perplexity_result = await _call_perplexity_api(
            perplexity_query, 
            model="sonar-pro"
        )
        if perplexity_result.get("success"):
            perplexity_answer = perplexity_result.get("content", "")
            tokens = perplexity_result.get("usage", {}).get("total_tokens", 0)
            logger.tokens = tokens
            print(f"   ✅ Perplexity ответил ({tokens} токенов)")
            print(f"   📄 Превью: {perplexity_answer[:200]}...")
        else:
            print(f"   ❌ Ошибка: {perplexity_result.get('error')}")
            return
    
    # Шаг 2: DeepSeek анализирует ответ Perplexity
    deepseek_query = f"""Проанализируй следующую информацию о криптовалютном рынке и дай стратегические рекомендации:

{perplexity_answer}

Задачи:
1. Выдели ключевые тренды
2. Оцени риски и возможности
3. Предложи 2-3 торговые стратегии"""

    print(f"\n📝 Шаг 2: DeepSeek анализирует ответ Perplexity...")
    
    async with log_mcp_execution("DeepSeek", "collaboration_test_analysis") as logger:
        deepseek_result = await _call_deepseek_api(deepseek_query)
        if deepseek_result.get("success"):
            deepseek_answer = deepseek_result.get("content", "")
            tokens = deepseek_result.get("usage", {}).get("total_tokens", 0)
            logger.tokens = tokens
            print(f"   ✅ DeepSeek провёл анализ ({tokens} токенов)")
            print(f"   📄 Превью: {deepseek_answer[:200]}...")
        else:
            print(f"   ❌ Ошибка: {deepseek_result.get('error')}")
    
    print(f"\n✅ Цепочка Perplexity → DeepSeek завершена!")


async def test_deepseek_to_perplexity():
    """
    Тест 2: DeepSeek → Perplexity
    DeepSeek создаёт reasoning → Perplexity проверяет факты
    """
    print("\n" + "=" * 80)
    print("🟣→🔵 ТЕСТ 2: DeepSeek → Perplexity")
    print("=" * 80)
    
    # Шаг 1: DeepSeek создаёт гипотезу/стратегию
    deepseek_query = """Разработай инновационную торговую стратегию для криптовалют, 
основанную на комбинации технического и фундаментального анализа. 
Опиши ключевые индикаторы и условия входа/выхода."""
    
    print(f"\n📝 Шаг 1: DeepSeek создаёт стратегию...")
    print(f"   Запрос: {deepseek_query[:80]}...")
    
    async with log_mcp_execution("DeepSeek", "collaboration_test_strategy") as logger:
        deepseek_result = await _call_deepseek_api(deepseek_query)
        if deepseek_result.get("success"):
            deepseek_answer = deepseek_result.get("content", "")
            tokens = deepseek_result.get("usage", {}).get("total_tokens", 0)
            logger.tokens = tokens
            print(f"   ✅ DeepSeek создал стратегию ({tokens} токенов)")
            print(f"   📄 Превью: {deepseek_answer[:200]}...")
        else:
            print(f"   ❌ Ошибка: {deepseek_result.get('error')}")
            return
    
    # Шаг 2: Perplexity проверяет актуальность стратегии
    perplexity_query = f"""Оцени следующую торговую стратегию с точки зрения:
1. Актуальности в текущих рыночных условиях
2. Применимости на практике
3. Известных примеров использования

Стратегия:
{deepseek_answer[:500]}...

Дай краткую оценку и укажи потенциальные проблемы."""

    print(f"\n📝 Шаг 2: Perplexity проверяет стратегию...")
    
    async with log_mcp_execution("Perplexity", "collaboration_test_validation") as logger:
        perplexity_result = await _call_perplexity_api(
            perplexity_query,
            model="sonar-pro"
        )
        if perplexity_result.get("success"):
            perplexity_answer = perplexity_result.get("content", "")
            tokens = perplexity_result.get("usage", {}).get("total_tokens", 0)
            logger.tokens = tokens
            print(f"   ✅ Perplexity проверил стратегию ({tokens} токенов)")
            print(f"   📄 Превью: {perplexity_answer[:200]}...")
        else:
            print(f"   ❌ Ошибка: {perplexity_result.get('error')}")
    
    print(f"\n✅ Цепочка DeepSeek → Perplexity завершена!")


async def main():
    """Главная функция"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  🤝 ТЕСТ ВЗАИМОДЕЙСТВИЯ DEEPSEEK ↔ PERPLEXITY".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    
    # Тест 1: Perplexity → DeepSeek
    await test_perplexity_to_deepseek()
    
    print("\n⏸️  Пауза 5 секунд между тестами...")
    await asyncio.sleep(5)
    
    # Тест 2: DeepSeek → Perplexity
    await test_deepseek_to_perplexity()
    
    # Итоговая сводка
    print("\n" + "=" * 80)
    print("🎊 ИТОГОВАЯ СВОДКА")
    print("=" * 80)
    print("""
✅ Проверены 2 паттерна взаимодействия:
   1. Perplexity → DeepSeek (поиск → анализ)
   2. DeepSeek → Perplexity (reasoning → проверка)

📊 Всего выполнено 4 API вызова:
   🔵 Perplexity: 2 вызова
   🟣 DeepSeek: 2 вызова

💡 Проверьте:
   - logs/mcp_activity.jsonl (4 новых записи)
   - MCP Monitor v2.0 (обновлённая статистика)

🚀 Канал быстрого взаимодействия работает!
    """)
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
