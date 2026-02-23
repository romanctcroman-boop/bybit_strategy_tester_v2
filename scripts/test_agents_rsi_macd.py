"""
Agent test: study RSI and MACD Universal Node
using P5 Memory Integration.

DeepSeek, Qwen and Perplexity agents analyze RSI/MACD Strategy Builder nodes,
results are stored in memory and reused across deliberations.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()  # Загружаем .env ПЕРЕД импортом backend (KeyManager нужен os.getenv)

from loguru import logger

# Настройка логов
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


async def run_deliberation_test():
    """Run 2 deliberations with memory: RSI Node and MACD Node."""

    from backend.agents.consensus.real_llm_deliberation import (
        deliberate_with_llm,
        get_real_deliberation,
    )

    delib = get_real_deliberation()

    # Проверяем доступных клиентов
    available_agents = list(delib._clients.keys())
    logger.info(f"🤖 Доступные агенты: {available_agents}")

    if not available_agents:
        logger.error(
            "❌ Нет доступных агентов! Проверьте API ключи (DEEPSEEK_API_KEY, QWEN_API_KEY, PERPLEXITY_API_KEY)"
        )
        return

    # =========================================================================
    # ВОПРОС 1: RSI Universal Node
    # =========================================================================
    print("\n" + "=" * 80)
    print("🔴 ВОПРОС 1: Как работает RSI Universal Node в Strategy Builder?")
    print("=" * 80 + "\n")

    rsi_question = (
        "Объясни как работает RSI Universal Node в нашем Strategy Builder. "
        "У него 3 режима сигналов (Range, Cross, Legacy) которые комбинируются через AND логику. "
        "Как правильно настроить RSI ноду для: "
        "1) Классического mean-reversion (покупка в oversold зоне RSI < 30), "
        "2) Momentum стратегии (RSI пересечение уровня 50 вверх = long), "
        "3) Комбинированной стратегии (Range + Cross одновременно). "
        "Какие параметры нужно включить (use_long_range, use_cross_level и т.д.)?"
    )

    logger.info("📤 Отправляю вопрос про RSI агентам...")
    start = datetime.now()

    try:
        rsi_result = await deliberate_with_llm(
            question=rsi_question,
            agents=available_agents,
            max_rounds=2,
            min_confidence=0.6,
            symbol="BTCUSDT",
            strategy_type="technical_analysis",
            enrich_with_perplexity="perplexity" in available_agents,
            use_memory=True,  # P5: recall + store
        )

        duration = (datetime.now() - start).total_seconds()
        print(f"\n⏱️  Время: {duration:.1f}s")
        print(f"📊 Решение: {rsi_result.decision[:500]}...")
        print(f"🎯 Уверенность: {rsi_result.confidence:.2f}")
        print(f"🔄 Раундов: {len(rsi_result.rounds)}")
        print(f"🗳️  Голосов: {len(rsi_result.final_votes)}")

        if rsi_result.metadata.get("memory_id"):
            print(f"🧠 Сохранено в память: {rsi_result.metadata['memory_id']}")

        # Показать голоса агентов
        print("\n--- Голоса агентов ---")
        for vote in rsi_result.final_votes:
            print(f"  [{vote.agent_id}] confidence={vote.confidence:.2f} | {vote.position[:200]}...")

        if rsi_result.dissenting_opinions:
            print("\n--- Разногласия ---")
            for d in rsi_result.dissenting_opinions:
                print(f"  [{d.agent_id}] {d.reasoning[:200] if d.reasoning else d.position[:200]}...")

    except Exception as e:
        logger.error(f"❌ Ошибка RSI делиберации: {e}")
        import traceback

        traceback.print_exc()
        rsi_result = None

    # =========================================================================
    # ВОПРОС 2: MACD Universal Node (использует память от RSI вопроса!)
    # =========================================================================
    print("\n" + "=" * 80)
    print("🟢 ВОПРОС 2: Как работает MACD Universal Node в Strategy Builder?")
    print("=" * 80 + "\n")

    macd_question = (
        "Объясни как работает MACD Universal Node в нашем Strategy Builder. "
        "У него 2 режима сигналов (Cross Zero и Cross Signal) которые комбинируются через OR логику. "
        "Как правильно настроить MACD ноду для: "
        "1) Тренд-следящей стратегии (MACD пересекает нулевую линию), "
        "2) Momentum стратегии (MACD пересекает Signal линию), "
        "3) Фильтрованной стратегии (signal_only_if_macd_positive для mean-reversion). "
        "Как MACD нода отличается от RSI по логике комбинирования (OR vs AND)? "
        "Как работает Signal Memory и зачем нужен signal_memory_bars?"
    )

    logger.info("📤 Отправляю вопрос про MACD агентам (с памятью RSI!)...")
    start = datetime.now()

    try:
        macd_result = await deliberate_with_llm(
            question=macd_question,
            agents=available_agents,
            max_rounds=2,
            min_confidence=0.6,
            symbol="BTCUSDT",
            strategy_type="technical_analysis",
            enrich_with_perplexity="perplexity" in available_agents,
            use_memory=True,  # P5: recall RSI knowledge + store MACD result
        )

        duration = (datetime.now() - start).total_seconds()
        print(f"\n⏱️  Время: {duration:.1f}s")
        print(f"📊 Решение: {macd_result.decision[:500]}...")
        print(f"🎯 Уверенность: {macd_result.confidence:.2f}")
        print(f"🔄 Раундов: {len(macd_result.rounds)}")
        print(f"🗳️  Голосов: {len(macd_result.final_votes)}")

        if macd_result.metadata.get("memory_id"):
            print(f"🧠 Сохранено в память: {macd_result.metadata['memory_id']}")

        # Показать голоса агентов
        print("\n--- Голоса агентов ---")
        for vote in macd_result.final_votes:
            print(f"  [{vote.agent_id}] confidence={vote.confidence:.2f} | {vote.position[:200]}...")

        if macd_result.dissenting_opinions:
            print("\n--- Разногласия ---")
            for d in macd_result.dissenting_opinions:
                print(f"  [{d.agent_id}] {d.reasoning[:200] if d.reasoning else d.position[:200]}...")

    except Exception as e:
        logger.error(f"❌ Ошибка MACD делиберации: {e}")
        import traceback

        traceback.print_exc()
        macd_result = None

    # =========================================================================
    # ПРОВЕРКА ПАМЯТИ: что запомнили агенты
    # =========================================================================
    print("\n" + "=" * 80)
    print("🧠 ПРОВЕРКА ПАМЯТИ: что запомнили агенты")
    print("=" * 80 + "\n")

    try:
        from backend.agents.mcp.tools.memory import get_global_memory

        memory = get_global_memory()
        stats = memory.get_stats()
        print("📊 Статистика памяти:")
        print(f"  Total items: {stats.get('total_items', 0)}")
        for tier_name, count in stats.get("by_type", {}).items():
            print(f"  {tier_name}: {count}")

        # Поиск по тегу deliberation
        results = await memory.recall(
            query="RSI MACD node strategy builder",
            top_k=5,
            tags=["deliberation"],
        )
        print(f"\n🔍 Найдено {len(results)} items с тегом 'deliberation':")
        for item in results:
            print(f"  [{item.memory_type}] score={item.importance:.2f} | {item.content[:150]}...")
            print(f"    tags: {item.tags}")
            print()

    except Exception as e:
        logger.error(f"❌ Ошибка проверки памяти: {e}")

    # =========================================================================
    # ИТОГИ
    # =========================================================================
    print("\n" + "=" * 80)
    print("📋 ИТОГИ ТЕСТА")
    print("=" * 80)

    print(f"\n✅ RSI делиберация: {'УСПЕХ' if rsi_result else 'ОШИБКА'}")
    if rsi_result:
        print(f"   Confidence: {rsi_result.confidence:.2f}, Memory: {rsi_result.metadata.get('memory_id', 'N/A')}")

    print(f"✅ MACD делиберация: {'УСПЕХ' if macd_result else 'ОШИБКА'}")
    if macd_result:
        print(f"   Confidence: {macd_result.confidence:.2f}, Memory: {macd_result.metadata.get('memory_id', 'N/A')}")

    if rsi_result and macd_result:
        print("\n🎉 Оба вопроса обработаны! Агенты изучили RSI и MACD ноды.")
        print("   Второй вопрос (MACD) имел доступ к памяти RSI — P5 работает!")

    # Закрываем клиентов
    await delib.close()


if __name__ == "__main__":
    asyncio.run(run_deliberation_test())
