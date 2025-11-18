#!/usr/bin/env python3
"""
ПОЛНЫЙ АНАЛИЗ ВСЕХ ТЗ через Multi-Agent Channel
DeepSeek + Perplexity совместная работа
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from multi_agent_channel import MultiAgentChannel

def read_tz_documents():
    """Читаем все ТЗ документы"""
    docs = {}
    
    # ТЗ 3-1
    tz_3_1 = Path(r"d:\PERP\Demo\Расширенное техническое задание_3-1.md")
    if tz_3_1.exists():
        with open(tz_3_1, 'r', encoding='utf-8') as f:
            docs['tz_3_1'] = f.read()[:8000]  # Первые 8000 символов
        print(f"✅ ТЗ 3-1 прочитан ({len(docs['tz_3_1'])} chars)")
    
    # ТЗ 3-2
    tz_3_2 = Path(r"d:\PERP\Demo\Расширенное техническое задание_3-2.md")
    if tz_3_2.exists():
        with open(tz_3_2, 'r', encoding='utf-8') as f:
            docs['tz_3_2'] = f.read()[:8000]
        print(f"✅ ТЗ 3-2 прочитан ({len(docs['tz_3_2'])} chars)")
    
    # Текущий план реализации
    impl_plan = Path("docs/TZ_IMPLEMENTATION_PLAN.md")
    if impl_plan.exists():
        with open(impl_plan, 'r', encoding='utf-8') as f:
            docs['current_state'] = f.read()[:4000]
        print(f"✅ Текущее состояние прочитано ({len(docs['current_state'])} chars)")
    
    return docs

def main():
    print("=" * 80)
    print("ПОЛНЫЙ АНАЛИЗ ВСЕХ ТЗ: DeepSeek + Perplexity")
    print("=" * 80)
    print()
    
    # Читаем документы
    docs = read_tz_documents()
    print()
    
    if not docs:
        print("❌ Не удалось прочитать ТЗ документы!")
        return
    
    # Создаём канал
    channel = MultiAgentChannel()
    
    # === АНАЛИЗ 1: QUICK WIN #1 (KNOWLEDGE BASE) ===
    print()
    print("=" * 80)
    print("АНАЛИЗ: Quick Win #1 (Knowledge Base)")
    print("=" * 80)
    print()
    
    kb_results = channel.collaborative_analysis(
        topic="Quick Win #1: Knowledge Base System",
        deepseek_task=f"""КОНТЕКСТ ТЗ:
{docs.get('tz_3_1', '')[:2000]}

ЗАДАЧА:
Дай детальный технический план реализации Knowledge Base для хранения reasoning chains:

1. **Database Schema:**
   - Какие таблицы нужны? (reasoning_traces, chain_of_thought, strategy_evolution)
   - Какие индексы для быстрого поиска?
   - Связи между таблицами?

2. **Storage Service:**
   - Какие методы API?
   - Как хранить большие reasoning chains (сжатие, партиционирование)?
   - Semantic search (pgvector)?

3. **MCP Integration:**
   - Как автоматически логировать все AI вызовы?
   - trace-id система?
   - Middleware для прозрачного логирования?

4. **Оценка времени:**
   - Реалистичная оценка (дни) для каждого этапа
   - Критические риски
   - Dependencies

Формат: конкретные технические решения с примерами кода.""",
        
        perplexity_task=f"""КОНТЕКСТ ТЗ:
{docs.get('tz_3_1', '')[:2000]}

ЗАДАЧА:
Дай стратегическую оценку Quick Win #1 (Knowledge Base):

1. **Business Value:**
   - Какую бизнес-ценность даёт KB?
   - Immediate benefits vs долгосрочная ценность?
   - ROI оценка?

2. **Приоритизация:**
   - Почему KB важнее/менее важен чем Sandbox?
   - Можно ли начинать параллельно с Sandbox?
   - Блокирующие dependencies?

3. **Риски:**
   - Какие риски при реализации KB?
   - Как митигировать?
   - Performance bottlenecks?

4. **Success Criteria:**
   - Как понять что KB готов к production?
   - KPI для оценки успеха?

Формат: стратегические рекомендации с обоснованием.""",
        iterations=1  # Только одна итерация для скорости
    )
    
    # Сохраняем результаты
    kb_path = channel.save_session(kb_results, "analysis_quick_win_1_kb.json")
    print(f"\n✅ Анализ Quick Win #1 сохранён: {kb_path}")
    
    # === АНАЛИЗ 2: QUICK WIN #2 (SANDBOX) ===
    print()
    print("=" * 80)
    print("АНАЛИЗ: Quick Win #2 (Sandbox Executor)")
    print("=" * 80)
    print()
    
    sandbox_results = channel.collaborative_analysis(
        topic="Quick Win #2: Sandbox Executor",
        deepseek_task=f"""КОНТЕКСТ ТЗ:
{docs.get('tz_3_2', '')[:2000]}

ЗАДАЧА:
Дай детальный технический план реализации Sandbox Executor:

1. **Docker Architecture:**
   - Dockerfile для изоляции?
   - Resource limits (CPU, RAM, Time)?
   - Network isolation?
   - Volume management?

2. **Security Validation:**
   - AST analysis для опасных операций?
   - Blacklist/Whitelist подход?
   - Security scoring (0-100)?
   - Примеры опасного кода для детекции?

3. **Executor API:**
   - Методы для запуска/остановки/мониторинга?
   - Как передавать код и данные?
   - Streaming logs?
   - Timeout handling?

4. **Оценка времени:**
   - Реалистичная оценка для каждого этапа
   - Критические риски (Docker security, resource leaks)
   - Dependencies (Docker daemon, libraries)

Формат: конкретные технические решения с примерами кода.""",
        
        perplexity_task=f"""КОНТЕКСТ ТЗ:
{docs.get('tz_3_2', '')[:2000]}

ЗАДАЧА:
Дай стратегическую оценку Quick Win #2 (Sandbox):

1. **Business Value:**
   - Почему Sandbox КРИТИЧЕН?
   - Security impact?
   - Immediate benefits?

2. **Приоритизация:**
   - Sandbox vs Knowledge Base - что первым?
   - Можно ли делать параллельно?
   - Блокирует ли что-то?

3. **Риски:**
   - Docker security risks?
   - Performance overhead?
   - Complexity of implementation?
   - Mitigation strategies?

4. **Success Criteria:**
   - Как оценить готовность Sandbox к production?
   - Security audit требования?
   - Performance benchmarks?

Формат: стратегические рекомендации с обоснованием.""",
        iterations=1
    )
    
    sandbox_path = channel.save_session(sandbox_results, "analysis_quick_win_2_sandbox.json")
    print(f"\n✅ Анализ Quick Win #2 сохранён: {sandbox_path}")
    
    # === АНАЛИЗ 3: QUICK WIN #3 (TOURNAMENT + ML) ===
    print()
    print("=" * 80)
    print("АНАЛИЗ: Quick Win #3 (Tournament + ML/AutoML)")
    print("=" * 80)
    print()
    
    tournament_results = channel.collaborative_analysis(
        topic="Quick Win #3: Tournament System + ML/AutoML",
        deepseek_task=f"""ТЕКУЩИЙ КОД Quick Win #3 уже реализован (strategy_arena.py, 450 lines).

ПРОБЛЕМА: Нет интеграции с:
- ML/AutoML (Optuna, LSTM/CNN/RL)
- Sandbox (выполнение в изоляции)
- Knowledge Base (логирование reasoning)

ЗАДАЧА:
Дай технический план доработки Quick Win #3:

1. **ML/AutoML Integration:**
   - Как интегрировать Optuna для optimization?
   - Где хранить ML модели?
   - Feature engineering pipeline?
   - Market regime detection (Wyckoff method)?

2. **Sandbox Integration:**
   - Как запускать стратегии в sandbox?
   - Performance impact?
   - Error handling?

3. **Knowledge Base Integration:**
   - Что логировать из tournament?
   - Reasoning chains для каждого решения?
   - Strategy evolution tracking?

4. **Оценка времени:**
   - Сколько времени на каждую интеграцию?
   - Критические риски?

Формат: конкретный план доработки с примерами кода.""",
        
        perplexity_task="""Quick Win #3 уже частично реализован (35-65% TZ compliance).

ЗАДАЧА:
Дай стратегическую оценку:

1. **Текущий статус:**
   - Что работает хорошо?
   - Что критично отсутствует?
   - Business impact текущих пробелов?

2. **Приоритизация доработок:**
   - ML/AutoML vs Sandbox vs Knowledge Base интеграция - что первым?
   - Можно ли делать параллельно?
   - Minimum viable improvement?

3. **ROI Analysis:**
   - Какую ценность добавит каждая интеграция?
   - Quick wins vs долгосрочная ценность?

4. **Roadmap:**
   - В каком порядке дорабатывать Quick Win #3?
   - Когда можно считать готовым к production?

Формат: стратегические рекомендации.""",
        iterations=1
    )
    
    tournament_path = channel.save_session(tournament_results, "analysis_quick_win_3_tournament.json")
    print(f"\n✅ Анализ Quick Win #3 сохранён: {tournament_path}")
    
    # === ИТОГОВАЯ СВОДКА ===
    print()
    print("=" * 80)
    print("ИТОГОВАЯ СВОДКА АНАЛИЗА")
    print("=" * 80)
    print()
    
    all_results = kb_results + sandbox_results + tournament_results
    success_count = sum(1 for r in all_results if r.get("success"))
    total_count = len(all_results)
    
    print(f"Quick Win #1 (Knowledge Base): {len(kb_results)} запросов")
    print(f"Quick Win #2 (Sandbox): {len(sandbox_results)} запросов")
    print(f"Quick Win #3 (Tournament): {len(tournament_results)} запросов")
    print()
    print(f"Всего запросов: {total_count}")
    print(f"Успешных: {success_count}")
    print(f"Success Rate: {success_count / total_count * 100:.1f}%")
    print()
    print("✅ Все анализы сохранены в markdown!")
    print()
    print("Файлы:")
    print(f"  - {kb_path}")
    print(f"  - {sandbox_path}")
    print(f"  - {tournament_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
