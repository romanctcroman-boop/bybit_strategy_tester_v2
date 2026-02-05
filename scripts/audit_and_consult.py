"""
Аудит выполненных улучшений Bybit Strategy Tester v2
Дата: 2026-01-18

Отправка данных в DeepSeek и Perplexity для сравнительного анализа.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

# ============================================================
# АУДИТ ВЫПОЛНЕННЫХ РАБОТ
# ============================================================

AUDIT_REPORT = """
# Аудит улучшений Bybit Strategy Tester v2
## Дата: 2026-01-18

## Выполненные улучшения

### Улучшение #1: Quick Reversals Fix
- **Проблема**: VectorBT генерировал на 25% больше сделок чем Fallback engine
- **Причина**: VectorBT открывал новую позицию на том же баре где закрылась предыдущая
- **Решение**: Добавлены параметры `upon_*_conflict="ignore"` в Portfolio.from_signals
- **Файлы**: engine.py, vectorbt_optimizer.py
- **Результат**: Trade divergence снижено с 25% до 5%

### Улучшение #2: Intrabar SL/TP Detection
- **Проблема**: VectorBT проверял SL/TP только по цене CLOSE, игнорируя HIGH/LOW
- **Причина**: Параметры `high` и `low` не передавались в Portfolio.from_signals
- **Решение**: Добавлена передача high/low серий во все вызовы VectorBT
- **Файлы**: engine.py, vectorbt_optimizer.py (3 места)
- **Результат**: Более точное определение срабатывания SL/TP

### Улучшение #3: Numba JIT Engine
- **Проблема**: Python-версия Fallback engine работала медленно (~1.3k симуляций/сек)
- **Причина**: Интерпретируемый Python код для bar-by-bar симуляции
- **Решение**: Создан numba_engine.py с JIT-компилируемыми функциями
- **Файлы**: 
  - НОВЫЙ: backend/backtesting/numba_engine.py
  - ОБНОВЛЁН: backend/backtesting/two_stage_optimizer.py
- **Результат**: 
  - Single simulation: 41x speedup (0.77ms → 0.019ms)
  - Batch simulation: 375,000 combinations/second
  - Stage 2 validation: 47x speedup

## Метрики производительности

| Метрика | ДО | ПОСЛЕ | Улучшение |
|---------|-----|-------|-----------|
| Trade divergence (VBT vs Fallback) | 25% | 5% | 80% лучше |
| Single simulation speed | 0.77ms | 0.019ms | 41x |
| Batch optimization | ~1.3k/s | 375k/s | 288x |
| Stage 2 validation (per candidate) | ~0.9s | ~0.02s | 47x |

## Тестовые результаты (504 1H candles)

### Quick Reversals Fix Test:
- VectorBT trades: 21
- Fallback trades: 20
- Divergence: 5% ✅

### Numba Benchmark:
- Python per run: 0.772ms
- Numba per run: 0.019ms
- Speedup: 41.1x ✅

### TwoStageOptimizer Integration:
- Fast Mode (Numba): 0.19s for 10 validations
- Precision Mode (BM): 0.91s for 1 validation
- Per-validation speedup: 46.9x ✅

## Архитектурные изменения

1. **Numba Engine** (`numba_engine.py`):
   - `simulate_trades_numba()` - JIT-compiled single simulation
   - `batch_simulate_numba()` - Parallel batch with prange

2. **TwoStageOptimizer** integration:
   - `use_numba_fast` parameter (default=True)
   - `_validate_with_numba()` method for fast Stage 2
   - Falls back to standard validation when Bar Magnifier enabled

## Вопросы для AI-консультации

1. Какие ещё оптимизации можно применить к Numba engine?
2. Стоит ли добавить GPU-ускорение (CUDA) для batch simulation?
3. Как улучшить точность Sharpe ratio в Numba engine?
4. Есть ли риски в текущей реализации signal conflict handling?
"""

print(AUDIT_REPORT)

# ============================================================
# ОТПРАВКА В DEEPSEEK
# ============================================================


def consult_deepseek(question: str) -> str:
    """Send question to DeepSeek API."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "ERROR: DEEPSEEK_API_KEY not found"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert in algorithmic trading, Python optimization, and backtesting systems. Analyze the provided audit and give recommendations.",
            },
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
    }

    try:
        response = httpx.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def consult_perplexity(question: str) -> str:
    """Send question to Perplexity API."""
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return "ERROR: PERPLEXITY_API_KEY not found"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert in algorithmic trading and Python performance optimization. Analyze the audit and provide actionable recommendations.",
            },
            {"role": "user", "content": question},
        ],
        "max_tokens": 2000,
    }

    try:
        response = httpx.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


# Prepare questions
AUDIT_QUESTION = f"""
Проанализируйте следующий аудит улучшений торговой системы и дайте рекомендации:

{AUDIT_REPORT}

Вопросы:
1. Оцените качество выполненных улучшений (1-10 баллов)
2. Какие потенциальные проблемы вы видите?
3. Какие дополнительные оптимизации можно применить?
4. Есть ли риски в текущей архитектуре?
5. Что бы вы добавили в первую очередь?
"""

print("\n" + "=" * 70)
print("📤 ОТПРАВКА В DEEPSEEK")
print("=" * 70)

deepseek_response = consult_deepseek(AUDIT_QUESTION)
print("\n🤖 DeepSeek ответ:")
print("-" * 50)
print(deepseek_response)

print("\n" + "=" * 70)
print("📤 ОТПРАВКА В PERPLEXITY")
print("=" * 70)

perplexity_response = consult_perplexity(AUDIT_QUESTION)
print("\n🔍 Perplexity ответ:")
print("-" * 50)
print(perplexity_response)

# Save responses
output_path = Path(__file__).resolve().parents[1] / "audit_ai_responses.md"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(f"# AI Audit Responses - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    f.write("## DeepSeek Response\n\n")
    f.write(deepseek_response)
    f.write("\n\n---\n\n")
    f.write("## Perplexity Response\n\n")
    f.write(perplexity_response)

print("\n\n✅ Ответы сохранены в audit_ai_responses.md")
