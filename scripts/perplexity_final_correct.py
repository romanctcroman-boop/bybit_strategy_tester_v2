#!/usr/bin/env python3
"""
Финальный анализ ТЗ с ПРАВИЛЬНЫМИ API ключами
"""

import requests
import json
from pathlib import Path

# ПРАВИЛЬНЫЕ API Keys из .env
PERPLEXITY_API_KEY = "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"
DEEPSEEK_API_KEY = "sk-1630fbba63c64f88952c16ad33337242"

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
                "content": "Ты эксперт по анализу технических заданий и архитектуре мультиагентных систем. Отвечай на русском языке."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }
    
    print(f"📤 Sending to Perplexity (prompt: {len(prompt)} chars)...")
    
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
    print("PERPLEXITY AI - ФИНАЛЬНЫЙ АНАЛИЗ ТЗ (ПРАВИЛЬНЫЙ КЛЮЧ)")
    print("=" * 80)
    print()
    
    # Читаем DeepSeek анализ
    deepseek_report = Path("FULL_TZ_DEEPSEEK_ANALYSIS.md")
    if deepseek_report.exists():
        with open(deepseek_report, 'r', encoding='utf-8') as f:
            deepseek_summary = f.read()[:2000]  # Первые 2000 символов
        print(f"✅ DeepSeek отчёт прочитан")
    else:
        deepseek_summary = "DeepSeek анализ не найден"
    
    # Читаем текущий план
    impl_plan = Path("docs/TZ_IMPLEMENTATION_PLAN.md")
    if impl_plan.exists():
        with open(impl_plan, 'r', encoding='utf-8') as f:
            current_state = f.read()[:2000]  # Первые 2000 символов
        print(f"✅ Текущее состояние прочитано")
    else:
        current_state = "План не найден"
    
    print()
    
    # КОРОТКИЙ но СОДЕРЖАТЕЛЬНЫЙ промпт
    prompt = f"""Проанализируй проект "Bybit Strategy Tester v2" - мультиагентную лаборатория автогенерации торговых стратегий.

**КОНТЕКСТ:**

DeepSeek Technical Audit дал оценку **C (58/100)**:
- MCP Server: 75% ✅
- Reasoning Agents (Perplexity): 68% ✅
- Code Generation (DeepSeek): 55% ⚠️
- ML/AutoML: 0% ❌ КРИТИЧНО
- Sandbox Execution: 0% ❌ КРИТИЧНО
- Knowledge Base: 0% ❌ КРИТИЧНО

**ТЕКУЩАЯ СИТУАЦИЯ:**

{current_state}

**ТВОЯ ЗАДАЧА:**

Дай стратегические рекомендации на русском:

1. **ПРИОРИТИЗАЦИЯ** - что делать первым для максимального impact?
   - Quick Win #1 (Knowledge Base) vs Quick Win #2 (Sandbox) vs ML/AutoML?
   - Можно ли делать параллельно?

2. **ROADMAP** - реалистичный план:
   - Сколько времени займёт каждый компонент?
   - Какие зависимости между модулями?
   - Как избежать блокирующих проблем?

3. **РИСКИ** - что может пойти не так:
   - Технические риски (Docker, DB migrations, API limits)
   - Интеграционные проблемы (ML models, reasoning chains)
   - Performance bottlenecks

4. **BUSINESS VALUE** - зачем это нужно:
   - Какую пользу даёт каждый компонент?
   - Можно ли частично запускать в production?
   - Какой ROI у каждого Quick Win?

Формат: конкретные рекомендации с обоснованием."""

    # Вызов Perplexity
    result = call_perplexity(prompt)
    
    if result:
        content = result['choices'][0]['message']['content']
        citations = result.get('citations', [])
        
        print(f"✅ SUCCESS: Perplexity анализ получен ({len(content)} chars)")
        print(f"📚 Citations: {len(citations)}")
        print()
        
        # Сохраняем отчёт
        report_path = Path("PERPLEXITY_STRATEGIC_ANALYSIS_FINAL.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Perplexity AI - Стратегический анализ проекта\n\n")
            f.write(f"**Дата:** 2025-11-01\n")
            f.write(f"**Модель:** sonar-pro\n")
            f.write(f"**Контекст:** DeepSeek Technical Audit (C grade, 58/100)\n\n")
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
        print(content[:1500])
        print("\n...")
        print("=" * 80)
    else:
        print("❌ FAILED: Не удалось получить анализ от Perplexity")

if __name__ == "__main__":
    main()
