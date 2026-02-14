"""
Consultation with DeepSeek AI about VectorBT limitations and possible solutions.
Uses the project's UnifiedAgentInterface with encrypted API keys.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.agents.unified_agent_interface import (
    AgentRequest,
    AgentType,
    UnifiedAgentInterface,
)

PROMPT = """
# VectorBT vs Fallback Engine: Консультация

## Контекст

Мы используем VectorBT в проекте для оптимизации торговых стратегий.
VectorBT используется ТОЛЬКО для быстрого скрининга параметров (Two-Stage Optimization).
Финальные метрики рассчитываются Fallback движком (наш собственный bar-by-bar симулятор).

## Архитектура

```
STAGE 1: VectorBT (векторизованный)
  - Тестирует 10,000+ комбинаций параметров
  - Скорость: 5,000-80,000 комб/сек
  - Точность: ~85%
  
STAGE 2: Fallback (последовательный)
  - Валидирует TOP-50 кандидатов
  - Скорость: ~1 комб/сек
  - Точность: 100%
```

## Проблемы VectorBT (которые мы не можем обойти)

| # | Ограничение | Объяснение |
|---|-------------|------------|
| 1 | **❌ Intrabar SL/TP** | Проверяет стопы только по CLOSE, не по High/Low внутри бара. Пример: бар O=100, H=105, L=96, C=104 со SL=97. VectorBT: позиция ОТКРЫТА (C > SL). Fallback: позиция ЗАКРЫТА (L < SL). |
| 2 | **❌ MAE/MFE** | Не отслеживает максимальную прибыль/убыток внутри сделки |
| 3 | **❌ Equity-Based Sizing** | Использует фиксированный order_value, не пересчитывает по текущему капиталу |
| 4 | **❌ Quick Reversals** | Может открыть позицию на том же баре, где закрыл предыдущую. Результат: VectorBT генерирует +25% больше сделок |
| 5 | **❌ Bar Magnifier** | Не может использовать 1-минутные данные для симуляции внутрибаровых движений |
| 6 | **❌ Trailing Stop** | Не поддерживает |
| 7 | **❌ Sequential Processing** | Обрабатывает все сигналы параллельно (векторно) |

## Результаты тестов (расхождения)

| Направление | VectorBT сделок | Fallback сделок | Разница |
|-------------|-----------------|-----------------|---------|
| LONG only   | 5               | 4               | +25%    |
| BOTH        | 10              | 8               | +25%    |

| Метрика      | VectorBT | Fallback | Разница |
|--------------|----------|----------|---------|
| Net Profit   | -8,500   | -9,200   | ~8%     |
| Sharpe       | -1.2     | -1.4     | ~15%    |

## Вопросы для DeepSeek

1. **Есть ли способы реализовать intrabar SL/TP в VectorBT?**
   - Может быть через vectorbt.signals или кастомные функции?
   - Или это фундаментальное ограничение архитектуры?

2. **Можно ли в VectorBT реализовать Equity-Based Position Sizing?**
   - `order_value` vs `order_pct` ?
   - Как учитывать изменение капитала между сделками?

3. **Есть ли способ предотвратить Quick Reversals?**
   - Может быть через `min_duration` или `delay` параметры?

4. **Что вы думаете о нашей Two-Stage архитектуре?**
   - VectorBT для скрининга → Fallback для валидации
   - Это оптимальный подход или есть альтернативы?

5. **Какие альтернативы VectorBT существуют для быстрой оптимизации?**
   - Numba-based backtesters?
   - GPU-accelerated?
   - Другие векторизованные библиотеки?

6. **Наш Fallback движок работает ~1 комб/сек. Как его ускорить без потери точности?**
   - Профилирование показывает, что основное время уходит на bar-by-bar loop
   - Можно ли сохранить точность intrabar SL/TP при ускорении?

## Ожидаемый ответ

Пожалуйста, дай детальные рекомендации:
1. Возможные решения для каждой проблемы (если они существуют)
2. Код-примеры где возможно
3. Оценка реалистичности каждого решения
4. Приоритетность: какие проблемы стоит решать в первую очередь
"""


async def main():
    print("=" * 70)
    print("DEEPSEEK CONSULTATION: VectorBT Limitations")
    print("=" * 70)

    # Initialize
    try:
        agent = UnifiedAgentInterface(force_direct_api=True)  # Direct API (no MCP)
        print("✅ UnifiedAgentInterface initialized")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        return

    # Check available keys
    deepseek_count = agent.key_manager.count_active(AgentType.DEEPSEEK)
    print(f"🔑 DeepSeek keys available: {deepseek_count}")

    if deepseek_count == 0:
        print("❌ No DeepSeek keys available!")
        return

    # Create request
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="analyze",
        prompt=PROMPT,
        thinking_mode=False,  # Disabled: deepseek-reasoner is 6-8x more expensive
        context={
            "project": "Bybit Strategy Tester",
            "focus": "VectorBT optimization limitations",
        },
    )

    print("\n📤 Sending request to DeepSeek...")
    print("   Model: deepseek-chat (cost-optimized)")
    print(f"   Prompt length: {len(PROMPT)} chars")

    # Send request
    try:
        response = await agent.send_request(request)

        print("\n" + "=" * 70)
        print("DEEPSEEK RESPONSE")
        print("=" * 70)

        if response.success:
            print(f"\n✅ Success! Latency: {response.latency_ms:.0f}ms")
            print(f"   Channel: {response.channel.value}")

            if response.reasoning_content:
                print("\n--- REASONING (Chain-of-Thought) ---")
                print(response.reasoning_content[:2000])
                if len(response.reasoning_content) > 2000:
                    print(f"\n... (truncated, {len(response.reasoning_content)} chars total)")

            print("\n--- FINAL ANSWER ---")
            print(response.content)

            # Save to file
            with open("deepseek_vectorbt_consultation.md", "w", encoding="utf-8") as f:
                f.write("# DeepSeek VectorBT Consultation\n\n")
                if response.reasoning_content:
                    f.write("## Reasoning (Chain-of-Thought)\n\n")
                    f.write(response.reasoning_content)
                    f.write("\n\n")
                f.write("## Final Answer\n\n")
                f.write(response.content)

            print("\n📄 Full response saved to: deepseek_vectorbt_consultation.md")

        else:
            print(f"\n❌ Failed: {response.error}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
