# -*- coding: utf-8 -*-
"""
AI Agent Project Audit Script

Использует DeepSeek + Perplexity для анализа проекта и поиска:
- Нереализованных задач
- Возможностей для модернизации
- Технического долга
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from loguru import logger


async def run_project_audit():
    """Запуск AI аудита проекта"""

    try:
        from backend.agents.unified_agent_interface import UnifiedAgentInterface
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return None

    agent = UnifiedAgentInterface()

    # Собираем контекст проекта
    context = """
# Bybit Strategy Tester v2 - Project Context

## Текущий статус:
- Architecture Score: 8.5/10
- Завершено: Phase 1-5
- DeepSeek V3.2 интегрирован

## Известные pending tasks:
1. Circuit Breaker gaps в perplexity_client.py, deepseek_client.py, mcp_integration.py
2. Phase 2 tasks: Risk Dashboard, Distributed Tracing, Chaos Engineering, ML Anomaly Detection
3. TODO маркеры в коде (6 штук)

## Структура проекта:
- backend/agents/ - AI агенты (DeepSeek, Perplexity)
- backend/api/ - FastAPI endpoints
- backend/services/ - Бизнес-логика
- backend/trading/ - Торговые стратегии
- backend/ml/ - Machine Learning
- backend/monitoring/ - Мониторинг и метрики
"""

    deepseek_prompt = f"""
{context}

Проанализируй проект и определи:

1. **Критические пробелы** - что ДОЛЖНО быть реализовано для production-ready системы
2. **Технический долг** - что нужно рефакторить или улучшить
3. **Возможности оптимизации** - где можно улучшить производительность
4. **Рекомендации по приоритетам** - в каком порядке реализовывать

Дай конкретные рекомендации с указанием файлов и действий.
"""

    # Запрос к DeepSeek для глубокого анализа
    logger.info("🔍 Запуск DeepSeek анализа...")

    deepseek_response = await agent.query_deepseek(
        prompt=deepseek_prompt,
        model="deepseek-reasoner",
        max_tokens=4000,
    )

    if deepseek_response.get("response"):
        logger.success("✅ DeepSeek анализ завершён")
        print("\n" + "=" * 80)
        print("🧠 DEEPSEEK ANALYSIS")
        print("=" * 80)
        print(f"\n📋 Analysis:\n{deepseek_response['response']}")
        print(f"\n⏱️ Latency: {deepseek_response.get('latency_ms', 0):.0f}ms")
    else:
        logger.error(f"❌ DeepSeek failed: {deepseek_response.get('error', 'Unknown')}")

    # Запрос к Perplexity для поиска best practices
    logger.info("🔍 Запуск Perplexity анализа...")

    perplexity_prompt = """
Для AI-powered trading strategy platform на Python/FastAPI,
какие современные best practices и технологии стоит внедрить в 2025 году?

Фокус на:
1. AI/ML интеграция для торговых стратегий
2. Resilience patterns для финансовых API
3. Observability и мониторинг
4. Security для trading platforms

Дай конкретные рекомендации с примерами библиотек и подходов.
"""

    perplexity_response = await agent.query_perplexity(
        prompt=perplexity_prompt,
        max_tokens=4000,
    )

    if perplexity_response.get("response"):
        logger.success("✅ Perplexity анализ завершён")
        print("\n" + "=" * 80)
        print("🔍 PERPLEXITY RESEARCH")
        print("=" * 80)
        print(perplexity_response["response"])
        print(f"\n⏱️ Latency: {perplexity_response.get('latency_ms', 0):.0f}ms")

        # Показать цитаты если есть
        citations = perplexity_response.get("citations", [])
        if citations:
            print("\n📚 Sources:")
            for i, cite in enumerate(citations[:5], 1):
                print(f"  {i}. {cite}")
    else:
        logger.error(f"❌ Perplexity failed: {perplexity_response.get('error', 'Unknown')}")

    # Сохраняем результаты
    output_file = project_root / "specs" / "AI_AUDIT_RESULTS.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# AI Agent Project Audit Results\n\n")
        f.write(f"**Date:** {datetime.now().isoformat()}\n\n")

        f.write("## DeepSeek Analysis\n\n")
        if deepseek_response.get("response"):
            f.write(deepseek_response["response"] + "\n\n")
        else:
            f.write(f"Error: {deepseek_response.get('error', 'Unknown')}\n\n")

        f.write("## Perplexity Research\n\n")
        if perplexity_response.get("response"):
            f.write(perplexity_response["response"] + "\n\n")
            citations = perplexity_response.get("citations", [])
            if citations:
                f.write("### Sources\n\n")
                for cite in citations:
                    f.write(f"- {cite}\n")
        else:
            f.write(f"Error: {perplexity_response.get('error', 'Unknown')}\n\n")

    logger.success(f"📝 Results saved to: {output_file}")

    return {
        "deepseek": deepseek_response,
        "perplexity": perplexity_response,
    }


if __name__ == "__main__":
    asyncio.run(run_project_audit())
