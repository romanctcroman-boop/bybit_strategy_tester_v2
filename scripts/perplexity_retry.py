"""
Повторный запрос к Perplexity API
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

AUDIT_REPORT = """
# Аудит улучшений Bybit Strategy Tester v2

## Выполненные улучшения

### Улучшение #1: Quick Reversals Fix
- Проблема: VectorBT генерировал на 25% больше сделок чем Fallback engine
- Решение: Добавлены параметры upon_*_conflict="ignore" в Portfolio.from_signals
- Результат: Trade divergence снижено с 25% до 5%

### Улучшение #2: Intrabar SL/TP Detection  
- Проблема: VectorBT проверял SL/TP только по цене CLOSE
- Решение: Добавлена передача high/low серий во все вызовы VectorBT
- Результат: Более точное определение срабатывания SL/TP

### Улучшение #3: Numba JIT Engine
- Проблема: Python-версия работала медленно (~1.3k симуляций/сек)
- Решение: Создан numba_engine.py с JIT-компилируемыми функциями
- Результат: 41x speedup (0.77ms → 0.019ms per simulation)

## Метрики
- Trade divergence: 25% → 5%
- Single simulation: 41x speedup  
- Batch optimization: 375,000 combinations/second
- Stage 2 validation: 47x speedup

Вопросы:
1. Оцените качество выполненных улучшений (1-10)
2. Какие потенциальные проблемы вы видите?
3. Какие дополнительные оптимизации можно применить?
4. Что добавить в первую очередь?
"""


def consult_perplexity(question: str) -> str:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return "ERROR: PERPLEXITY_API_KEY not found"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {"model": "sonar", "messages": [{"role": "user", "content": question}], "max_tokens": 2000}

    try:
        response = httpx.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


print("=" * 70)
print("📤 ОТПРАВКА В PERPLEXITY")
print("=" * 70)

response = consult_perplexity(AUDIT_REPORT)
print("\n🔍 Perplexity ответ:")
print("-" * 50)
print(response)

# Update file
output_path = Path(__file__).resolve().parents[1] / "audit_ai_responses.md"
with open(output_path, "a", encoding="utf-8") as f:
    f.write("\n\n## Perplexity Response (Retry)\n\n")
    f.write(response)

print("\n\n✅ Ответ добавлен в audit_ai_responses.md")
