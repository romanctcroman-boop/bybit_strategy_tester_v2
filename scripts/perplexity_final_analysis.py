#!/usr/bin/env python3
"""
Perplexity AI - Финальный анализ ТЗ (короткими запросами)
"""

import os
import requests
import json
from pathlib import Path

# API Keys
PERPLEXITY_API_KEY = "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"

def call_perplexity(prompt: str, model: str = "sonar-pro") -> dict:
    """Вызов Perplexity API"""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Ты эксперт по анализу технических заданий и архитектуре мультиагентных систем."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }
    
    print(f"📤 Sending to Perplexity (prompt length: {len(prompt)} chars)...")
    
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
        return None

def main():
    print("=" * 80)
    print("PERPLEXITY AI - АНАЛИЗ ТЗ (ОПТИМИЗИРОВАННЫЙ)")
    print("=" * 80)
    print()
    
    # Читаем DeepSeek анализ для контекста
    deepseek_report = Path("FULL_TZ_DEEPSEEK_ANALYSIS.md")
    if deepseek_report.exists():
        with open(deepseek_report, 'r', encoding='utf-8') as f:
            deepseek_content = f.read()
        print(f"✅ DeepSeek отчёт прочитан ({len(deepseek_content)} chars)")
    else:
        deepseek_content = "DeepSeek анализ не найден"
    
    # Читаем текущее состояние проекта
    implementation_plan = Path("docs/TZ_IMPLEMENTATION_PLAN.md")
    if implementation_plan.exists():
        with open(implementation_plan, 'r', encoding='utf-8') as f:
            # Берём только первые 3000 символов (резюме)
            current_state = f.read()[:3000]
        print(f"✅ Текущее состояние прочитано")
    else:
        current_state = "План реализации не найден"
    
    print()
    
    # === КОРОТКИЙ ПРОМПТ ДЛЯ PERPLEXITY ===
    prompt = f"""Проанализируй текущее состояние проекта "Bybit Strategy Tester v2" - мультиагентной лаборатории для автогенерации торговых стратегий.

**КОНТЕКСТ:**

DeepSeek уже дал детальный технический анализ с оценкой D (35/100), выявив критичные пробелы:
1. ML/AutoML: 15/25 (частично) - нет LSTM/CNN/RL, нет Optuna
2. Sandbox: 0/25 - нет Docker изоляции, критический риск безопасности
3. Knowledge Base: 0/25 - нет reasoning chains, нет explainability
4. Качество кода: 20/25 - хорошо реализовано

**ТЕКУЩЕЕ СОСТОЯНИЕ ПРОЕКТА:**

{current_state}

**ТВОЯ ЗАДАЧА:**

Дай стратегический анализ на русском языке:

1. **ПРИОРИТИЗАЦИЯ** (что делать первым?):
   - Какой Quick Win реализовать СНАЧАЛА для максимального impact?
   - Knowledge Base vs Sandbox vs ML/AutoML - что критичнее?

2. **ROADMAP** (реалистичный план):
   - Сколько времени на каждый компонент?
   - Можно ли делать параллельно?
   - Какие зависимости между модулями?

3. **РИСКИ** (что может пойти не так?):
   - Технические риски
   - Интеграционные проблемы
   - Bottleneck'и производительности

4. **BUSINESS VALUE** (зачем это нужно?):
   - Какую бизнес-ценность даёт каждый компонент?
   - Можно ли запускать в production частично?

Формат ответа: конкретные рекомендации с обоснованием, без общих фраз."""

    # Вызов Perplexity
    result = call_perplexity(prompt)
    
    if result:
        content = result['choices'][0]['message']['content']
        citations = result.get('citations', [])
        
        print(f"✅ SUCCESS: Perplexity анализ получен ({len(content)} chars)")
        print(f"📚 Citations: {len(citations)}")
        print()
        
        # Сохраняем отчёт
        report_path = Path("FULL_TZ_PERPLEXITY_STRATEGIC_ANALYSIS.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Perplexity AI - Стратегический анализ ТЗ\n\n")
            f.write(f"**Дата:** 2025-11-01\n")
            f.write(f"**Модель:** sonar-pro\n")
            f.write(f"**Контекст:** Full TZ Analysis + DeepSeek Technical Review\n\n")
            f.write("---\n\n")
            f.write(content)
            f.write("\n\n---\n\n")
            f.write("## 📚 Citations\n\n")
            for i, citation in enumerate(citations, 1):
                f.write(f"{i}. {citation}\n")
        
        print(f"📄 Отчёт сохранён: {report_path}")
        print()
        print("=" * 80)
        print("PREVIEW:")
        print("=" * 80)
        print(content[:1000])
        print("...")
        print("=" * 80)
    else:
        print("❌ FAILED: Не удалось получить анализ от Perplexity")
        print()
        print("💡 Возможные причины:")
        print("   - API quota exceeded")
        print("   - Временная недоступность сервиса")
        print("   - Payload всё ещё слишком большой")

if __name__ == "__main__":
    main()
