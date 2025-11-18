"""
Real DeepSeek Agent Audit - Using DeepSeekCodeAgent pool

Отправляет реальные файлы в DeepSeek через унифицированный агент, избегая прямых HTTP вызовов.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Добавляем корневую папку проекта, чтобы обеспечить доступ к backend-пакетам
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

from automation.deepseek_code_agent.code_agent import (
    CodeGenerationRequest,
    DeepSeekCodeAgent,
)

load_dotenv()

FORMAT_INSTRUCTIONS = (
    "ФОРМАТ ОТВЕТА:\n"
    "1. Ответь на русском языке с профессиональным тоном.\n"
    "2. Используй структурированный Markdown с заголовками и маркированными списками.\n"
    "3. Оберни весь итоговый ответ в блок ```markdown ... ``` и не выводи текст вне блока."
)


def build_prompt(prompt_body: str, system_prompt: Optional[str] = None) -> str:
    """Собрать полный промпт с ролью эксперта и требованиями к формату."""
    sections = []
    if system_prompt:
        sections.append("Роль эксперта:\n" + system_prompt.strip())
    sections.append(prompt_body.strip())
    sections.append(FORMAT_INSTRUCTIONS)
    return "\n\n".join(sections)


async def request_analysis(
    agent: DeepSeekCodeAgent,
    prompt: str,
    *,
    max_tokens: int = 3500
) -> tuple[str, int]:
    """Отправить промпт через DeepSeekCodeAgent и вернуть текст анализа с количеством токенов."""
    request = CodeGenerationRequest(
        prompt=prompt.strip(),
        language="markdown",
        style="production",
        max_tokens=max_tokens,
    )
    response = await agent.generate_code(request)
    if not response.get("success", True):
        raise RuntimeError(response.get("error", "Unknown DeepSeek error"))
    analysis_text = response.get("code", "").strip()
    tokens_used = int(response.get("tokens_used") or 0)
    return analysis_text, tokens_used


async def run_audit_section(
    agent: DeepSeekCodeAgent,
    *,
    title: str,
    category: str,
    prompt: str,
    file: Optional[str] = None,
    max_tokens: int = 3500
) -> dict:
    """Единый запуск секции аудита через DeepSeekCodeAgent."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print("\n📤 Отправка запроса в DeepSeek Code Agent...")
    try:
        analysis, tokens = await request_analysis(
            agent,
            prompt,
            max_tokens=max_tokens
        )
        print(f"✅ Анализ завершён ({tokens} токенов)")
        print("\n" + "-" * 80)
        print(analysis)
        print("-" * 80)
        result = {
            "category": category,
            "analysis": analysis,
            "tokens": tokens,
        }
        if file:
            result["file"] = file
        return result
    except Exception as exc:
        print(f"❌ Не удалось получить ответ: {exc}")
        return {
            "category": category,
            "file": file,
            "error": str(exc)
        }


async def audit_security_implementation(agent: DeepSeekCodeAgent) -> dict:
    """Audit Fix #2: API Keys Security"""
    with open("backend/core/secrets_manager.py", "r", encoding="utf-8") as f:
        code = f.read()
    prompt_body = f"""
Проведи комплексный аудит безопасности следующей реализации шифрования.

FILE: backend/core/secrets_manager.py
CONTEXT: 19 API ключей перенесены из .env в зашифрованное хранилище на базе Fernet.

{code}

АНАЛИЗ:
1. Насколько надёжна выбранная схема шифрования (Fernet) для production API ключей?
2. Насколько безопасно хранить master key в переменных окружения?
3. Есть ли уязвимости в механизмах ротации ключей?
4. Достаточно ли реализовано аудит-логирование для соответствия требованиям compliance?
5. Есть ли риск тайминговых атак при расшифровке?
6. Готова ли реализация к production-нагрузкам?

ПРЕДОСТАВЬ:
- Оценку безопасности (1-10)
- Критические уязвимости (если есть)
- Конкретные рекомендации по улучшению
- Краткую оценку соответствия GDPR/SOC2
- Альтернативные решения (AWS KMS, Azure Key Vault)
"""
    system_prompt = (
        "Ты выступаешь в роли ведущего инженера по безопасности с опытом в криптографии и secrets management. "
        "Сфокусируйся на практических рисках и лучших практиках."
    )
    full_prompt = build_prompt(prompt_body, system_prompt)
    return await run_audit_section(
        agent,
        title="🔐 SECURITY AUDIT: API Keys Encryption",
        category="Security",
        prompt=full_prompt,
        file="backend/core/secrets_manager.py"
    )


async def audit_coverage_gaps(agent: DeepSeekCodeAgent) -> dict:
    """Audit Fix #3: Test Coverage Gaps"""
    prompt_body = """
Проанализируй пробелы в тестовом покрытии торговой платформы.

ТЕКУЩЕЕ ПОКРЫТИЕ: 22.57%
- Всего операторов: 18 247
- Покрыто: 4 576
- Не покрыто: 13 671

КРИТИЧЕСКИЕ ГАПЫ:
1. AI-агенты (0%): backend/agents/deepseek.py, backend/agents/perplexity.py, backend/agents/agent_background_service.py
2. Модули безопасности (~16%): backend/security/rate_limiter.py, backend/security/crypto.py
3. API-роутеры (0-20%): backend/api/routers/*
4. ML-модули (0%): backend/ml/drift_detector.py, backend/ml/market_regime_detector.py

ВОПРОСЫ:
1. Какие файлы тестировать в первую очередь? (топ-5)
2. Как быстрее всего выйти на 35% покрытия?
3. Какие модули несут максимальный риск без тестов?
4. Какой тип тестов предпочтителен по каждому направлению (unit/integration/E2E)?
5. Какие сценарии обязательны для AI-агентов (deepseek.py)?

ПРОСЬБА:
- Дай приоритезированный список файлов
- Укажи «быстрые победы»
- Оцени риски и предложи подход к scaffolding тестов
- Прикинь таймлайн до 35% покрытия
"""
    system_prompt = (
        "Ты опытный QA-инженер по Python/pytest и торговым системам. "
        "Фокус на практичных шагах с максимальным ROI."
    )
    full_prompt = build_prompt(prompt_body, system_prompt)
    return await run_audit_section(
        agent,
        title="🧪 TEST COVERAGE AUDIT: Critical Gaps Analysis",
        category="Test Coverage",
        prompt=full_prompt
    )


async def audit_performance_bottlenecks(agent: DeepSeekCodeAgent) -> dict:
    """Audit Performance Issues"""
    prompt_body = """
Проанализируй производительность системы бэктестинга.

АРХИТЕКТУРА:
- FastAPI backend (async) + Celery workers (sync)
- PostgreSQL + SQLAlchemy
- Redis Streams (очередь), Redis (кэш)

ПРОБЛЕМЫ:
1. Нет критичных индексов (backfill_progress 200 мс, bybit_klines 500 мс, task_queue 150 мс)
2. Нет кеширования результатов (Walk-Forward Optimization, поиск бэктестов)
3. Большие JSON-ответы (>10 МБ) без пагинации (/api/backtests/list)
4. Один Redis-инстанс — точка отказа

ВОПРОСЫ:
1. Какие индексы критичны? (дай SQL)
2. Что и как кешировать? (TTL, invalidation)
3. Какую пагинацию выбрать (cursor vs offset)?
4. Нужен ли Redis cluster прямо сейчас?
5. На сколько ускоримся после внедрения индексов?

ПРОСЬБА:
- Конкретные CREATE INDEX
- План кеширования
- Приоритизация улучшений
- Оценка выигрыша и roadmap масштабирования
"""
    system_prompt = (
        "Ты ведущий архитектор PostgreSQL/Redis с опытом оптимизации trading-систем. "
        "Дай конкретные SQL и стратегии." 
    )
    full_prompt = build_prompt(prompt_body, system_prompt)
    return await run_audit_section(
        agent,
        title="⚡ PERFORMANCE AUDIT: Database & Query Optimization",
        category="Performance",
        prompt=full_prompt
    )


async def run_real_deepseek_audit() -> None:
    """Run real DeepSeek Agent audit via DeepSeekCodeAgent"""
    print("\n" + "=" * 80)
    print("🤖 REAL DEEPSEEK AGENT AUDIT")
    print("=" * 80)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔑 DeepSeekCodeAgent pool (без прямых HTTP запросов)")
    print("=" * 80)

    agent = DeepSeekCodeAgent(model="deepseek-chat")
    results = []

    results.append(await audit_security_implementation(agent))
    results.append(await audit_coverage_gaps(agent))
    results.append(await audit_performance_bottlenecks(agent))

    total_tokens = sum(r.get("tokens", 0) for r in results if isinstance(r, dict))
    output_file = "REAL_DEEPSEEK_AUDIT.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "audit_date": datetime.now().isoformat(),
                "api_used": "DeepSeekCodeAgent",
                "model": "deepseek-chat",
                "results": results,
                "total_tokens": total_tokens,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("\n" + "=" * 80)
    print("✅ REAL AUDIT COMPLETE!")
    print(f"📄 Results saved: {output_file}")
    print(f"💰 Total tokens: {total_tokens:,}")
    print("=" * 80)


def main() -> None:
    """Sync wrapper for asyncio.run"""
    asyncio.run(run_real_deepseek_audit())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as exc:
        print(f"\n❌ Audit failed: {exc}")
        import traceback
        traceback.print_exc()
