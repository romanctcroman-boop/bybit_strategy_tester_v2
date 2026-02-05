"""
Direct DeepSeek API call for VectorBT consultation (simplified version)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import httpx

from backend.security.key_manager import get_key_manager

PROMPT = """# VectorBT vs Fallback Engine: Консультация

## Проблемы VectorBT

| # | Ограничение | Объяснение |
|---|-------------|------------|
| 1 | ❌ Intrabar SL/TP | Проверяет стопы только по CLOSE, не по High/Low внутри бара |
| 2 | ❌ MAE/MFE | Не отслеживает максимальную прибыль/убыток внутри сделки |
| 3 | ❌ Equity-Based Sizing | Использует фиксированный order_value, не пересчёт по капиталу |
| 4 | ❌ Quick Reversals | Может открыть позицию на том же баре, где закрыл предыдущую (+25% сделок) |
| 5 | ❌ Bar Magnifier | Не может использовать 1-минутные данные для симуляции |
| 6 | ❌ Trailing Stop | Не поддерживает |
| 7 | ❌ Sequential Processing | Обрабатывает все сигналы параллельно (векторно) |

## Вопросы:

1. Есть ли способы реализовать intrabar SL/TP в VectorBT?
2. Можно ли в VectorBT реализовать Equity-Based Position Sizing?
3. Есть ли способ предотвратить Quick Reversals?
4. Наша Two-Stage архитектура (VectorBT для скрининга → Fallback для валидации) - это оптимально?
5. Какие альтернативы VectorBT существуют для быстрой оптимизации?
6. Как ускорить Fallback движок (~1 комб/сек) без потери точности?

Дай краткие, практичные рекомендации с примерами кода где возможно.
"""

def main():
    print("=" * 70)
    print("DEEPSEEK DIRECT API CALL")
    print("=" * 70)

    # Get API key
    km = get_key_manager()
    api_key = km.get_decrypted_key("DEEPSEEK_API_KEY")

    if not api_key:
        print("❌ DeepSeek API key not found")
        return

    print("✅ API key loaded")

    # Prepare request - use deepseek-chat for faster response
    payload = {
        "model": "deepseek-chat",  # Use chat model (faster than reasoner)
        "messages": [
            {"role": "system", "content": "You are an expert Python developer specializing in quantitative finance, backtesting, and VectorBT library."},
            {"role": "user", "content": PROMPT},
        ],
        "max_tokens": 4000,
        "temperature": 0.7,
    }

    print("\n📤 Sending request...")
    print(f"   Model: {payload['model']}")
    print(f"   Prompt length: {len(PROMPT)} chars")

    # Make request
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                "https://api.deepseek.com/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )

        print(f"\n📥 Response received: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            print(f"   Tokens used: {usage.get('total_tokens', 'N/A')}")

            print("\n" + "=" * 70)
            print("DEEPSEEK RESPONSE")
            print("=" * 70)
            print(content)

            # Save to file
            with open("deepseek_vectorbt_consultation.md", "w", encoding="utf-8") as f:
                f.write("# DeepSeek VectorBT Consultation\n\n")
                f.write(content)

            print("\n📄 Response saved to: deepseek_vectorbt_consultation.md")

        else:
            print(f"❌ Error: {response.text}")

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
