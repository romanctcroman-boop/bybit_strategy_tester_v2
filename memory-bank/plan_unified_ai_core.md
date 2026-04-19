# Plan: Unified AI Core — Единое AI ядро

> Создан: 2026-04-11  
> Статус: PLANNING (не начат)  
> Цель: Объединить trading_strategy_graph.py и builder_workflow.py в единый мощный пайплайн на базе Claude + Perplexity

---

## Архитектурное решение

**НЕ создаём новый файл.** Расширяем `trading_strategy_graph.py` как единое AI ядро.  
`builder_workflow.py` → тонкий адаптер, делегирует в unified pipeline.

### Почему trading_strategy_graph.py как основа:
- Уже имеет LangGraph (checkpointing, streaming, HITL)
- Уже имеет `seed_graph` параметр → готовый крюк для OPTIMIZE режима
- Memory, WF validation, ML validation уже работают
- `OptimizationNode` уже читает `agent_optimization_hints` из state.context
- `top_trials` уже записывается в state → нужно только добавить AnalysisNode

### Что остаётся без изменений (SACRED):
- API route paths (обратная совместимость)
- `BacktestEngine` / FallbackEngineV4
- Commission = 0.0007
- `StrategyBuilderAdapter`
- WF/ML validation логика
- Memory system internals
- SSE streaming протокол

---

## Режимы работы единого пайплайна

```
ЕДИНЫЙ ПАЙПЛАЙН
│
├── CREATE mode  (symbol + timeframe → новая стратегия)
│   Step 3: Claude Sonnet генерирует StrategyDefinition → converter → граф блоков
│
└── OPTIMIZE mode  (existing_strategy_id → улучшить параметры)
    Step 3: Загружаем блоки из БД → seed_graph (уже поддерживается!)

Всё остальное ИДЕНТИЧНО для обоих режимов.
```

---

## Пошаговый план (9 фаз)

### Фаза 1: Unified Entry & Mode Support
**Цель**: `run_strategy_pipeline()` принимает `existing_strategy_id`, оба режима работают

**Изменения в `trading_strategy_graph.py`**:
- Добавить `existing_strategy_id: str | None = None` в `run_strategy_pipeline()`
- Добавить `pipeline_mode: str` в AgentState (через langgraph_orchestrator.py)
- В начале pipeline: если `existing_strategy_id` → загрузить граф из БД → передать как `seed_graph`
- `GenerateStrategiesNode` / `build_graph`: если `seed_graph` уже есть → пропустить генерацию

**Новые поля AgentState** (в `langgraph_orchestrator.py`):
```python
pipeline_mode: str = "create"          # "create" | "optimize"
existing_strategy_id: str | None = None
opt_iterations: list[dict] = field(default_factory=list)   # история прогонов
opt_insights: dict = field(default_factory=dict)            # анализ top-20
debate_outcome: dict | None = None
```

**Тест CP1**: `tests/test_unified_pipeline_modes.py`
```python
# CREATE mode: нет existing_strategy_id → pipeline генерирует StrategyDefinition
# OPTIMIZE mode: есть existing_strategy_id → pipeline загружает граф, пропускает генерацию
# Оба режима: state.pipeline_mode установлен корректно
```

---

### Фаза 2: Real A2A Strategy Generation (восстановить деградировавший MoA)
**Цель**: Заменить единственный вызов Claude настоящим A2A (Claude + Perplexity)

**Изменения в `GenerateStrategiesNode`** (trading_strategy_graph.py ~line 522):
- Параллельный вызов:
  - **Claude Sonnet**: генерирует структуру стратегии (блоки, логику, параметры)
  - **Perplexity sonar-pro**: валидирует рыночный контекст ("есть ли смысл RSI для текущей волатильности BTC?")
- **Claude Haiku**: синтезирует оба ответа в финальный `StrategyDefinition`
- Если Perplexity недоступен → только Claude (graceful fallback)
- Передавать реальный `symbol` в Perplexity (убрать заглушку)

**Тест CP2**: `tests/test_strategy_generation_a2a.py`
```python
# A2A: 2 параллельных вызова, синтез валиден
# Fallback: без Perplexity ключа → только Claude, StrategyDefinition корректен
# Perplexity получает реальный symbol, не ""
```

---

### Фаза 3: Optimization Analysis Node (анализ top-20)
**Цель**: После Optuna sweep Claude анализирует весь массив top-20, находит паттерны

**Изменения**:
1. Увеличить `top_n: 5 → 20` в `run_builder_optuna_search()` и `OptimizationNode`
2. Новая нода `OptimizationAnalysisNode` (после `optimize_strategy`):
   - Вход: `state.results["optimize_strategy"]["top_trials"]` (top-20 с полными метриками)
   - Claude анализирует:
     - Кластеры параметров (какие значения встречаются в топ-5)
     - Чувствительность (Spearman уже считается → использовать)
     - "Winning zone": диапазон параметров где Sharpe > threshold
     - Red flags: конфигурации с высоким Sharpe но огромным DD
   - Выход: `state.opt_insights` dict с `param_clusters`, `winning_zones`, `risks`, `next_ranges`
3. Подключить ноду в граф: `optimize_strategy → analysis_opt → [debate | wf_validation]`

**Тест CP3**: `tests/test_optimization_analysis_node.py`
```python
# top-20 передаётся в ноду корректно
# Нода возвращает param_clusters, winning_zones, risks
# При 0 trials → graceful skip
# Claude prompt содержит все поля top-20 (sharpe, DD, trades, params)
```

---

### Фаза 4: Iterative Optimization Loop (3 прохода с обучением)
**Цель**: После первого sweep агенты видят анализ и предлагают уточнённые диапазоны → повтор

**Изменения**:
1. Новая нода `A2AParamRangeNode` (заменяет/расширяет существующий `agent_optimization_hints`):
   - Вход: `state.opt_insights` (анализ предыдущего sweep) + текущие метрики бэктеста
   - A2A: Claude + Perplexity предлагают уточнённые диапазоны
   - Perplexity получает symbol + "что происходит на рынке сейчас"
   - Claude читает memory: "какие RSI периоды работали для BTC в trending режиме?"
   - Выход: `state.context["agent_optimization_hints"]` (уже читается OptimizationNode!)
2. Роутер `opt_iteration_router`:
   - Условие CONTINUE: `iterations < 3` AND `not converged`
   - Конвергенция: top-1 params стабильны (разница < 5%) между итерациями
   - Loop: `A2AParamRangeNode → optimize_strategy → OptimizationAnalysisNode → [router]`
3. Каждая итерация пишется в `state.opt_iterations` (история для финального отчёта)

**Тест CP4**: `tests/test_optimization_loop.py`
```python
# 3 итерации: ranges сужаются, best_sharpe улучшается
# Конвергенция: loop останавливается при стабильных params
# Iteration history: state.opt_iterations содержит 3 записи с metrics
# Memory hit: param ranges включают историческое знание
```

---

### Фаза 5: AnalysisDebateNode (реализовать и подключить)
**Цель**: Структурированный дебаттинг перед Walk-Forward gate

**Реализация** (новый класс в trading_strategy_graph.py):
```python
class AnalysisDebateNode(AgentNode):
    """
    Два Claude вызова с разными системными промптами:
    - "Оптимист" (Sonnet): аргументы за деплой стратегии
    - "Риск-менеджер" (Haiku): аргументы против (drawdown, overfitting risk)
    Синтез: структурированное решение с risk_score и conditions
    Timeout: 45s (не 150s как в DebateNode)
    """
```

- Вход: финальные метрики + top-20 analysis + opt_iterations history
- Выход: `state.debate_outcome = {"decision": "proceed|reject|conditional", "risk_score": 0-10, "conditions": [], "rationale": str}`
- Роутер: если `decision == "reject"` → переход к `reflection` (не сохранять)
- Подключить в граф: `OptimizationAnalysisNode → analysis_debate → wf_validation`

**Тест CP5**: `tests/test_analysis_debate_node.py`
```python
# Дебаттинг завершается за < 45s
# decision ∈ {"proceed", "reject", "conditional"}
# "reject" → pipeline пропускает WF и memory_update
# risk_score коррелирует с max_drawdown стратегии
```

---

### Фаза 6: Memory во время оптимизации
**Цель**: A2AParamRangeNode читает память перед предложением диапазонов

**Изменения** в `A2AParamRangeNode`:
- Запрос к HierarchicalMemory: `"successful strategies in {regime} regime for {symbol}"`
- Формат ответа памяти → добавить в промпт агентам: "В похожем trending режиме лучшие RSI периоды: 14, 21 (Sharpe > 1.5)"
- После успешного сохранения: записать `(regime, symbol, best_params, sharpe)` в EPISODIC память
- Namespace: `"optimization_params"` (не "shared" — изоляция)

**Тест CP6**: `tests/test_memory_param_correlation.py`
```python
# Memory hit → промпт содержит исторические параметры
# Memory miss → нормальная работа без hint
# После сохранения: следующий run находит запись в памяти
# Namespace изоляция: "optimization_params" не виден в "shared"
```

---

### Фаза 7: Thin builder_workflow.py Adapter
**Цель**: builder_workflow.py делегирует в unified pipeline, сохраняет API совместимость

**Изменения в `builder_workflow.py`**:
```python
async def run(self, config: BuilderWorkflowConfig) -> BuilderWorkflowResult:
    # 1. Если existing_strategy_id → загрузить граф из БД
    seed_graph = await self._load_strategy_graph(config.existing_strategy_id)
    
    # 2. Запустить unified pipeline
    state = await run_strategy_pipeline(
        symbol=config.symbol,
        timeframe=config.timeframe,
        df=df,
        existing_strategy_id=config.existing_strategy_id,
        seed_graph=seed_graph,
        run_wf_validation=True,
        event_fn=self._forward_event,  # SSE проброс
        pipeline_timeout=config.timeout,
    )
    
    # 3. Конвертировать AgentState → BuilderWorkflowResult (API compat)
    return self._state_to_result(state)
```

- SSE streaming: `self._forward_event` прокидывает pipeline events в существующий SSE handler
- API routes `/builder/task` и `/builder/task/stream` — БЕЗ изменений
- Старый код builder_workflow (3400 строк логики) → удалить после успешного теста

**Тест CP7**: `tests/test_builder_workflow_adapter.py`
```python
# AI Build на существующей стратегии → вызывает run_strategy_pipeline()
# Результат конвертируется в BuilderWorkflowResult корректно
# SSE events прокидываются через event_fn
# API /builder/task возвращает ожидаемый формат
```

---

### Фаза 8: Enhanced Report
**Цель**: Финальный отчёт содержит всё что нужно для принятия решения

**Изменения в `ReportNode`**:
- Top-20 таблица с метриками (Sharpe, DD, WR, trades, params)
- Iteration history: как менялись Sharpe/DD по итерациям
- `opt_insights`: param clusters, winning zones, risks
- `debate_outcome`: решение и обоснование
- Comparison: initial vs final (если OPTIMIZE mode)

**Тест CP8**: встроен в CP7 (E2E тест проверяет report структуру)

---

### Фаза 9: E2E тесты и регрессия
```bash
# Новые E2E тесты
pytest tests/test_unified_e2e_create.py -v     # CREATE mode полный прогон
pytest tests/test_unified_e2e_optimize.py -v   # OPTIMIZE mode полный прогон

# Регрессия — все существующие тесты должны пройти
pytest tests/backend/agents/ -v
pytest tests/test_p1_features.py tests/test_p2_features.py -v
pytest tests/test_pipeline_streaming_hitl.py -v
pytest tests/test_refinement_loop.py -v
```

---

## Граф нод ПОСЛЕ рефакторинга

```
analyze_market
    ↓
regime_classifier
    ↓
memory_recall  ←── Hierarchical Memory (wins/failures/regime)
    ↓
grounding (Perplexity — market research с реальным symbol)
    ↓
[CREATE] generate_strategies (A2A: Claude Sonnet + Perplexity → Haiku synthesis)
[OPTIMIZE] load_existing_strategy (seed_graph из БД)
    ↓
parse_responses / select_best (ConsensusEngine)
    ↓
build_graph (StrategyDefToGraphConverter)
    ↓
backtest (FallbackEngineV4)
    ↓
backtest_analysis
    ↓
[structural refine loop ≤3] ←── если sparse signals, direction mismatch
    ↓
A2AParamRangeNode (Claude + Perplexity → param ranges → читает memory)
    ↓
optimize_strategy (Optuna TPE, top_n=20)
    ↓
OptimizationAnalysisNode (Claude анализирует top-20 → param_clusters, winning_zones)
    ↓
[opt_iteration_router] ──── если iter < 3 AND not converged → A2AParamRangeNode
    ↓ (после ≤3 итераций)
analysis_debate (Claude Sonnet "Оптимист" vs Haiku "Риск-менеджер" → decision)
    ↓
[wf_validation] (WalkForward: ratio ≥ 0.5 OR abs ≥ 0.5)
    ↓
ml_validation (IS/OOS, regime, perturbation)
    ↓
[hitl_check] (опционально)
    ↓
memory_update (opt_result["best_sharpe"] + param correlation)
    ↓
reflection
    ↓
report (top-20, iterations, debate, comparison)
```

---

## Ключевые технические решения

| Вопрос | Решение |
|--------|---------|
| Новый файл? | НЕТ — расширяем trading_strategy_graph.py |
| DebateNode implementation? | 2 Claude вызова с разными system prompts (Sonnet "оптимист" + Haiku "риск") |
| top_n | 5 → 20 |
| Perplexity symbol | Убрать `symbol: ""` заглушку, передавать реальный тикер |
| A2A в pipeline нодах | Использовать AgentToAgentCommunicator из builder_workflow |
| builder_workflow.py | Тонкий адаптер (100-150 строк) поверх run_strategy_pipeline() |
| Memory в оптимизации | Namespace "optimization_params", query перед proposal |
| Convergence check | top-1 params разница < 5% между итерациями |

---

## Порядок реализации (рекомендуемый)

1. **Фаза 1** (AgentState + mode) — основа, без неё ничего не работает
2. **Фаза 3** (top-20 + AnalysisNode) — высокий приоритет, дешёво, сразу даёт ценность
3. **Фаза 2** (A2A генерация) — восстанавливает деградировавшую MoA
4. **Фаза 4** (Iterative loop) — зависит от Фазы 3
5. **Фаза 5** (DebateNode) — зависит от Фазы 3
6. **Фаза 6** (Memory в opt) — зависит от Фазы 4
7. **Фаза 7** (builder_workflow adapter) — зависит от Фаз 1-6
8. **Фаза 8** (Report) — последний
9. **Фаза 9** (E2E + регрессия) — финальная проверка

---

## Что НЕ меняем (риск регрессии высок)

- `BacktestEngine.run()` и FallbackEngineV4
- `StrategyBuilderAdapter` (adapter.py 1399 строк)
- `HierarchicalMemory` / `SQLiteBackend` / `VectorStore`
- `WalkForwardValidationNode` логика прохождения
- `MLValidationNode` три параллельные проверки
- Все существующие API endpoints и их request/response форматы
- SSE протокол (`{"type": "stage_change", "data": {...}}`)
- Commission = 0.0007

---

## Оценка объёма работ

| Фаза | Сложность | Новых строк | Тестов |
|------|-----------|-------------|--------|
| 1 | Средняя | ~150 | 6 |
| 2 | Средняя | ~200 | 8 |
| 3 | Средняя | ~250 | 10 |
| 4 | Высокая | ~300 | 12 |
| 5 | Средняя | ~200 | 8 |
| 6 | Средняя | ~150 | 8 |
| 7 | Высокая | ~200 (удалить ~3200) | 10 |
| 8 | Лёгкая | ~100 | встроены |
| 9 | Лёгкая | ~200 тестов | 20+ |
| **Итого** | | **~1550 новых** | **~82 теста** |
