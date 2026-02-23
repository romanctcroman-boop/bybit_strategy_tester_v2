"""
FULL DeepSeek API call for VectorBT consultation with complete context
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import httpx

from backend.security.key_manager import get_key_manager

FULL_PROMPT = """
# VectorBT vs Fallback Engine: Консультация

## Контекст

Мы используем VectorBT в проекте Bybit Strategy Tester для оптимизации торговых стратегий криптовалют.
VectorBT используется ТОЛЬКО для быстрого скрининга параметров (Two-Stage Optimization).
Финальные метрики рассчитываются Fallback движком (наш собственный bar-by-bar симулятор).

## Текущая архитектура

```
STAGE 1: VectorBT (векторизованный)
  - Тестирует 10,000+ комбинаций параметров
  - Скорость: 5,000-80,000 комб/сек
  - Точность: ~85%
  - Использует: vectorbt.Portfolio.from_signals()

STAGE 2: Fallback (последовательный)
  - Валидирует TOP-50 кандидатов из Stage 1
  - Скорость: ~1 комб/сек
  - Точность: 100%
  - Полный bar-by-bar симулятор с intrabar обработкой
```

## Проблемы VectorBT (которые мы обнаружили в production)

| # | Ограничение | Подробное объяснение |
|---|-------------|----------------------|
| 1 | **❌ Intrabar SL/TP** | VectorBT.Portfolio проверяет стопы только по CLOSE цене бара, не по High/Low внутри бара. Пример: бар Open=100, High=105, Low=96, Close=104 со StopLoss=97 (3%). VectorBT: позиция ОСТАЁТСЯ ОТКРЫТОЙ (Close=104 > SL=97). Fallback: позиция ЗАКРЫТА (Low=96 < SL=97, стоп сработал внутри бара). Это приводит к 10-15% расхождению в метриках. |
| 2 | **❌ MAE/MFE** | Maximum Adverse Excursion и Maximum Favorable Excursion не отслеживаются. Эти метрики критичны для оценки качества входов и правильности стоп-лоссов. |
| 3 | **❌ Equity-Based Sizing** | VectorBT использует фиксированный `order_value` или `size`. Не пересчитывает размер позиции по текущему капиталу (equity). После +20% прибыли размер позиции должен увеличиться, но VectorBT использует начальный размер. |
| 4 | **❌ Quick Reversals** | VectorBT может открыть новую позицию на том же баре, где закрыл предыдущую. Результат: VectorBT генерирует +25% больше сделок чем Fallback. Тест: VectorBT=10 сделок, Fallback=8 сделок при direction="both". |
| 5 | **❌ Bar Magnifier** | Наш Fallback может использовать 1-минутные свечи для симуляции движений внутри 30-минутного бара. VectorBT работает только с основным таймфреймом. |
| 6 | **❌ Trailing Stop** | VectorBT не поддерживает trailing stop loss. |
| 7 | **❌ Sequential Processing** | VectorBT обрабатывает все сигналы параллельно (векторно), а реальный трейдинг последователен. Это влияет на расчёт equity curve. |

## Эмпирические результаты тестов (реальные данные)

### Расхождение по количеству сделок:
| Направление | VectorBT сделок | Fallback сделок | Разница |
|-------------|-----------------|-----------------|---------|
| LONG only   | 5               | 4               | +25%    |
| SHORT only  | 6               | 6               | 0%      |
| BOTH        | 10              | 8               | +25%    |

### Расхождение по метрикам:
| Метрика        | VectorBT | Fallback | Разница |
|----------------|----------|----------|---------|
| Net Profit     | -$8,500  | -$9,200  | ~8%     |
| Sharpe Ratio   | -1.2     | -1.4     | ~15%    |
| Win Rate       | 28%      | 25%      | ~12%    |
| Max Drawdown   | 45%      | 52%      | ~15%    |

## Вопросы к DeepSeek

### 1. Intrabar SL/TP в VectorBT
Есть ли способы реализовать проверку stop loss и take profit по HIGH/LOW внутри бара?
- Может быть через `sl_trail`, `sl_stop` с кастомными функциями?
- Или через `order_func_nb` с доступом к OHLC?
- Это фундаментальное ограничение архитектуры VectorBT?

### 2. Equity-Based Position Sizing
Можно ли в VectorBT реализовать динамический расчёт размера позиции?
- `order_value` vs `size` vs `size_type`?
- Как учитывать изменение капитала между сделками?
- Есть ли `equity_at_close` которое можно использовать?

### 3. Quick Reversals Prevention
Есть ли способ предотвратить открытие позиции на том же баре где закрылась предыдущая?
- Параметры `min_duration`, `delay`, `upon_*`?
- Custom entry/exit функции?

### 4. Two-Stage Architecture Assessment
Что вы думаете о нашей Two-Stage архитектуре?
- VectorBT для скрининга → Fallback для валидации
- Это оптимальный подход или есть альтернативы?
- Стоит ли пытаться улучшить VectorBT или лучше сфокусироваться на ускорении Fallback?

### 5. Альтернативы VectorBT
Какие альтернативы существуют для быстрой оптимизации?
- Numba-based backtesters?
- GPU-accelerated (CUDA/OpenCL)?
- Другие векторизованные библиотеки?
- Свой движок на чистом NumPy?

### 6. Ускорение Fallback Engine
Наш Fallback движок работает ~1 комбинация/сек. Как его ускорить без потери точности?
- Профилирование показывает основное время в bar-by-bar loop
- Можно ли сохранить точность intrabar SL/TP при ускорении?
- Numba JIT, Cython, или что-то ещё?
- Параллелизация для независимых комбинаций?

## Ожидаемый формат ответа

Пожалуйста, дай:
1. **Детальные технические рекомендации** для каждой проблемы
2. **Примеры кода** где возможно (Python, NumPy, VectorBT API)
3. **Оценку реалистичности** каждого решения (возможно/невозможно/частично)
4. **Приоритетность**: какие проблемы стоит решать в первую очередь
5. **Архитектурные рекомендации** для нашего Two-Stage подхода
"""


def main():
    print("=" * 70)
    print("DEEPSEEK FULL CONSULTATION: VectorBT Limitations")
    print("=" * 70)

    # Get API key
    km = get_key_manager()
    api_key = km.get_decrypted_key("DEEPSEEK_API_KEY")

    if not api_key:
        print("❌ DeepSeek API key not found")
        return

    print("✅ API key loaded")

    # Use deepseek-chat (reasoner is 6-8x more expensive and burns tokens fast)
    payload = {
        "model": "deepseek-chat",  # Was deepseek-reasoner — cost protection
        "messages": [
            {
                "role": "system",
                "content": "You are an expert Python developer specializing in quantitative finance, algorithmic trading, backtesting engines, and vectorized computation. You have deep knowledge of VectorBT, Numba, NumPy, and high-performance computing.",
            },
            {"role": "user", "content": FULL_PROMPT},
        ],
        "max_tokens": 8000,  # Reduced from 16000 for cost control
    }

    print("\n📤 Sending FULL request to DeepSeek...")
    print(f"   Model: {payload['model']} (thinking mode)")
    print(f"   Prompt length: {len(FULL_PROMPT)} chars")
    print(f"   Max tokens: {payload['max_tokens']}")
    print("\n⏳ This may take 2-5 minutes for deep analysis...")

    # Make request with long timeout
    try:
        with httpx.Client(timeout=600.0) as client:  # 10 minute timeout
            response = client.post(
                "https://api.deepseek.com/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )

        print(f"\n📥 Response received: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content", "")
            reasoning = message.get("reasoning_content", "")  # DeepSeek reasoner specific
            usage = data.get("usage", {})

            print(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")
            print(f"   Reasoning tokens: {usage.get('reasoning_tokens', 'N/A')}")

            # Save full response
            with open("deepseek_vectorbt_full_consultation.md", "w", encoding="utf-8") as f:
                f.write("# DeepSeek VectorBT Full Consultation\n\n")
                f.write(f"Model: {payload['model']}\n")
                f.write(f"Tokens: {usage.get('total_tokens', 'N/A')}\n\n")

                if reasoning:
                    f.write("## Chain-of-Thought Reasoning\n\n")
                    f.write(reasoning)
                    f.write("\n\n---\n\n")

                f.write("## Final Answer\n\n")
                f.write(content)

            print("\n" + "=" * 70)
            print("DEEPSEEK RESPONSE")
            print("=" * 70)

            if reasoning:
                print("\n--- REASONING (truncated) ---")
                print(reasoning[:3000])
                if len(reasoning) > 3000:
                    print(f"\n... ({len(reasoning)} chars total, see file)")

            print("\n--- FINAL ANSWER ---")
            print(content[:5000])
            if len(content) > 5000:
                print(f"\n... ({len(content)} chars total, see file)")

            print("\n📄 Full response saved to: deepseek_vectorbt_full_consultation.md")

        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)

    except httpx.TimeoutException:
        print("❌ Request timed out (10 minutes)")
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
