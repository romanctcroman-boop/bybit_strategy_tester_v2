# Active Context — Текущая работа

> Обновлено: 2026-03-23

## Текущий фокус

AI Agent pipeline — улучшение обратной связи агентов с движком. Все фазы рефакторинга (0-5) завершены.

**ТЗ:** `docs/TZ_AGENT_INFRASTRUCTURE_INTEGRATION.md` (8 задач — все реализованы)

---

## Что сделано сегодня (2026-03-20)

### Итеративный цикл рефайнмента ✅ (новое)

**Файлы изменены:**
- `backend/agents/trading_strategy_graph.py` — добавлены:
  - `RefinementNode` (класс) — создаёт feedback-промпт с диагнозом провала, очищает устаревшие результаты, инкрементирует счётчик итераций
  - `_backtest_passes(state)` — проверка критериев (trades ≥ 5, Sharpe > 0, DD < 30%)
  - `_should_refine(state)` — guard: провал И iteration < MAX_REFINEMENTS (3)
  - `ConditionalRouter` после `BacktestNode` → `refine_strategy` или `memory_update`
  - `RefinementNode` → прямое ребро обратно в `generate_strategies`
  - `GenerateStrategiesNode` — использует `state.context["refinement_feedback"]` в промпте

- `tests/test_refinement_loop.py` — 30 тестов, все проходят:
  - `TestBacktestPasses` — граничные случаи критериев
  - `TestShouldRefine` — защита по счётчику итераций
  - `TestRefinementNode` — мутации стейта, feedback, очистка результатов
  - `TestGraphWiring` — наличие узлов и рёбер в графе
  - `TestRefinementIntegration` — симуляция 2-итерационного цикла

**Граф (с рефайнментом):**

```
analyze_market → [debate] → generate_strategies → parse_responses
                      ↑                                  │
                      │                            select_best
               refine_strategy ←               build_graph
               (iter < 3, fails)                    │
                                               backtest
                                                  ├── fails, iter < 3 → refine_strategy
                                                  └── passes / max iter → memory_update → report
```

### Живые тесты агентов ✅

- `tests/test_agent_live.py` — 10/10 тестов проходят (DeepSeek + QWEN + Perplexity)
- `tests/test_agent_soul.py` — 44/44 тестов проходят (stub, без реального API)
- Исправлены 3 бага в `response_parser.py`:
  - `ExitCondition.value = list` → берём `v[0]`
  - `ExitCondition.value = None` → возвращаем `0.0`
  - `ExitCondition.value = dict` → извлекаем первое числовое значение

### Интеграция агентов с Strategy Builder ✅

**ТЗ v3 — 8 задач, все выполнены:**

1. `backend/agents/integration/graph_converter.py` — `StrategyDefToGraphConverter`
   - Конвертирует `StrategyDefinition → strategy_graph` (40+ блоков)
   - Категории A (прямой long/short), B (через condition-блок), C (фильтры)
   - Activation flags обязательны (иначе блок = passthrough always True)

2. `tests/test_graph_converter.py` — 26 тестов, все проходят

3. `backend/agents/prompts/templates.py` — добавлена секция BLOCK ACTIVATION RULES

4. `BuildGraphNode` в `trading_strategy_graph.py` — между Consensus и Backtest

5. `BacktestNode._run_via_adapter` — использует StrategyBuilderAdapter (40+ блоков)

6. `MemoryUpdateNode._save_to_db` — сохраняет в ORM (is_builder_strategy=True)

7. `build_trading_strategy_graph()` — граф обновлён с BuildGraphNode

8. `POST /api/ai-strategy-generator/generate-and-build` — полный пайплайн через API

---

## Что сделано (2026-03-23)

### Agent Pipeline — улучшение feedback агентов ✅

1. **`templates.py`** — добавлена секция `PORT NAMES QUICK REFERENCE` перед BLOCK ACTIVATION RULES.
   Таблица output ports для всех 20+ блоков. Решает проблему агент→порт blindness.

2. **`response_parser.py`** — добавлен метод `parse_strategy_with_errors()` возвращает
   `tuple[StrategyDefinition | None, list[str]]`. Structured errors вместо просто `None`.
   Обратная совместимость: `parse_strategy()` теперь обёртка над новым методом.

3. **`trading_strategy_graph.py` — BacktestNode** — `_run_via_adapter` теперь возвращает
   `{"metrics": ..., "engine_warnings": [...], "sample_trades": [...]}`.
   engine_warnings = список предупреждений движка (DIRECTION_MISMATCH, NO_TRADES, etc.).
   sample_trades = первые 10 сделок для диагностики.

4. **`trading_strategy_graph.py` — RefinementNode** — feedback значительно обогащён:
   - ENGINE WARNINGS с интерпретацией (DIRECTION_MISMATCH, NO_TRADES)
   - GRAPH CONVERSION WARNINGS из BuildGraphNode
   - SAMPLE TRADES (первые 5) когда trades < 10

5. **`trading_strategy_graph.py` — BuildGraphNode** — сохраняет `agent_optimization_hints`
   из `StrategyDefinition.optimization_hints` в `state.context`.

6. **`trading_strategy_graph.py` — OptimizationNode** — новый метод `_apply_agent_hints()`
   применяет agent hints для сужения диапазонов параметров Optuna.

## Что сделано (2026-03-24)

### Bug fixes: production crashes в agent pipeline ✅

Глубокий аудит кода выявил 4 production-бага в `trading_strategy_graph.py`:

1. **BUG#1 — `PerformanceMetrics.get()` AttributeError**: `result.metrics` — это Pydantic модель,
   не dict. `.get()` упало бы в prod. Fix: `model_dump()` перед сохранением в стейт.

2. **BUG#2 — `result.warnings` always empty**: у `BacktestResult` нет `.warnings`,
   правильный атрибут — `.analysis_warnings`. DIRECTION_MISMATCH/NO_TRADES генерируются
   API-роутером, не движком. Fix: читаем `analysis_warnings` + синтезируем из метрик.

3. **BUG#3 — `engine_warnings=None` TypeError**: `for w in None` падало.
   Fix: `list(... or [])` везде где читаются engine_warnings / sample_trades.

4. **Trade serialization**: `model_dump()` предпочтительнее `__dict__` для Pydantic моделей.

Добавлены `TestRefinementNodeSafety` (4 теста) → 27 тестов в `test_agent_feedback_improvements.py`.

### Deprecation cleanup ✅

- `asyncio.iscoroutinefunction` → `inspect.iscoroutinefunction` (langgraph_orchestrator.py)
- `datetime.utcnow()` → `datetime.now(UTC)` (prompt_logger.py)
- `commission=0.001` → `COMMISSION_TV` (ai_backtest_executor.py, optimize_tasks.py)

### Tests ✅

- 27/27 test_agent_feedback_improvements.py
- 33/33 test_refinement_loop.py

## Что сделано (2026-03-24, продолжение)

### ТЗ_ЭВОЛЮЦИЯ_ПАМЯТИ — все 5 фаз ✅

Все фазы уже были реализованы в кодовой базе. Проверены + исправлен deprecated импорт.

- **P1** UnifiedMemoryItem — единый dataclass, `agent_namespace`, `to_dict/from_dict`, SQLite-схема
- **P2** MCP tools — `memory_store/recall/get_stats/consolidate/forget` в `mcp/tools/memory.py`
- **P3** TagNormalizer + AutoTagger — синонимы, авто-теги, консолидация разблокирована
- **P4** BM25 Hybrid Retrieval — 3-ступенчатый pipeline, degraded mode
- **P5** Deliberation integration — auto-recall/store в `deliberate_with_llm()`
- **Fix**: `real_llm_deliberation.py` → `from backend.agents.llm import` (убран DeprecationWarning)
- **286 тестов** памяти — все проходят

## Что сделано (2026-03-24, продолжение)

### P0 Agent Embodiment ✅

Закрыты 2 критических пробела архитектуры (5/10 → 7/10):

1. **MemoryRecallNode** — новый Node 1.7 в `trading_strategy_graph.py`. Читает прошлые победы/провалы из `HierarchicalMemory` ДО генерации стратегий. Инжектирует `memory_context` в промпты всех LLM-агентов. Non-blocking.

2. **BacktestAnalysisNode** — новый Node 5.5. Структурированная диагностика МЕЖДУ `BacktestNode` и conditional router. Определяет severity (`pass/near_miss/moderate/catastrophic`) и root_cause (`direction_mismatch/no_signal/sl_too_tight/...`). `RefinementNode` теперь использует эти данные вместо hardcoded if-else.

3. **GenerateStrategiesNode** — инжектирует `memory_context` в начало всех промптов (DeepSeek + другие агенты).

4. **Graph re-wired**: `analyze→[debate]→memory_recall→generate`, `backtest→backtest_analysis→[router]`.

5. **Tests**: 33 новых теста в `test_memory_recall_and_analysis_nodes.py`. Все 93 agent pipeline теста проходят.

## Что сделано (2026-03-24, финал)

### generate-and-build endpoint — интеграционные тесты ✅

**Файл создан:** `tests/backend/api/test_generate_and_build.py` — 25 тестов

**Ключевые решения при создании:**
- `run_strategy_pipeline` lazy-импортируется ВНУТРИ endpoint функции → патч по источнику:
  `backend.agents.trading_strategy_graph.run_strategy_pipeline` (НЕ по модулю роутера)
- `asyncio.to_thread` патчится как `backend.api.routers.ai_strategy_generator.asyncio.to_thread`
- TestClient требует полный путь с префиксом роутера: `/ai-strategy-generator/generate-and-build`

**Покрытие:**
- Happy path (10 тестов): ключи ответа, strategy_name, backtest_metrics, graph, warnings, proposals_count
- Request forwarding (4 теста): params → pipeline, default agents, symbol echo, single call
- Error paths (5 тестов): empty DF → 404, DB error → 503, pipeline error → 500, None → 404
- Edge cases (6 тестов): no select_best → "AI Strategy", no backtest → {}, no strategy_graph → None

**Дополнительный фикс:** `datetime.utcnow()` → `datetime.now(UTC)` в endpoint (deprecation)

## Следующие шаги

- Обновить CHANGELOG.md
- Деferred до отдельной сессии: real API integration tests, load tests

## Открытые вопросы / Блокеры

- Нет активных блокеров
- generate-and-build endpoint теперь полностью покрыт тестами ✅
