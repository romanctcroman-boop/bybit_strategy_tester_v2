# Codebase Refactoring Audit Plan# 🔍 АУДИТ СИСТЕМ ДЛЯ РЕФАКТОРИНГА

> **Created:** 2026-02-27 **Дата:** 2026-02-26

> **Replaces:** AUDIT_REFACTORING_PLAN.md (2026-02-26, outdated line counts) **Статус:** ✅ Аудит проведён

> **Status:** Active — work in progress

> **Scope:** Full backend + frontend audit for technical debt reduction ---

> **Baseline:** 616 Python files, 224 files > 500 lines, ~15,083 lines in P0 alone

> **All line counts verified** via `Get-Content | Measure-Object -Line`## 📊 ОБЗОР ПРОЕКТА

---**Всего файлов:**

- Python (backend): 612 файлов

## Table of Contents- JavaScript (frontend): 116 файлов

1. [Executive Summary](#1-executive-summary)**Крупные файлы (>500 строк):**

2. [Project Statistics](#2-project-statistics)- Backend: 142 файла

3. [P0 — Critical Monoliths (Act Now)](#3-p0--critical-monoliths-act-now)- Frontend: 15 файлов (без node_modules)

4. [P1 — Important Complex Files (2 Weeks)](#4-p1--important-complex-files-2-weeks)

5. [P2 — Universal Engine Deprecation](#5-p2--universal-engine-deprecation)---

6. [P2 — Services Consolidation](#6-p2--services-consolidation)

7. [Frontend Debt](#7-frontend-debt)## 🔴 КРИТИЧЕСКИЕ СИСТЕМЫ ДЛЯ РЕФАКТОРИНГА

8. [Legacy engine.py Dependency Map](#8-legacy-enginepy-dependency-map)

9. [Timeline and Priority Order](#9-timeline-and-priority-order)### 1. **Backend: Крупные файлы (>1000 строк)**

10. [Refactoring Checklist Template](#10-refactoring-checklist-template)

11. [Ongoing Monitoring Commands](#11-ongoing-monitoring-commands)| Файл | Строк | Приоритет | Проблема | Рекомендация |

|------|-------|-----------|----------|--------------|

---| `backtesting/gpu_optimizer.py` | 3,500 | 🔴 P0 | Монолит | Разбить на модули |

| `api/routers/optimizations.py` | 3,264 | 🔴 P0 | Монолит | Выделить endpoints |

## 1. Executive Summary| `api/routers/strategy_builder.py` | 3,109 | 🔴 P0 | Монолит | Разбить по функциям |

| `backtesting/strategy_builder_adapter.py` | 3,087 | 🔴 P0 | Монолит | Модульная архитектура |

The codebase has grown organically with several monolith files exceeding 2,500 lines and entire| `backtesting/engines/numba_engine_v2.py` | 3,000 | 🟡 P1 | Сложный | Документировать |

subsystems (Universal Engine, Services) that need structural attention. This audit identifies:| `backtesting/engines/fallback_engine_v4.py` | 2,563 | 🟡 P1 | Сложный | Уже рефакторинг |

| `api/routers/backtests.py` | 2,455 | 🟡 P1 | Монолит | Разделить CRUD |

- **4 P0 files** — 15,083 total verified lines — split immediately| `agents/workflows/builder_workflow.py` | 2,405 | 🟡 P1 | Workflow | State machine |

- **6 P1 files** — 17,005 total verified lines — document then refactor over 2 weeks| `backtesting/engine.py` | 2,357 | 🟡 P1 | Legacy | Заменить на V4 |

- **1 P2 subsystem** — Universal Engine: 27 files, 28,364 lines — targeted for deprecation| `api/routers/marketdata.py` | 2,126 | 🟡 P1 | Монолит | Выделить сервисы |

- **1 P2 subsystem** — Services: 85+ files — targeted for consolidation| `backtesting/indicator_handlers.py` | 1,931 | 🟢 P2 | Длинный | Уже модульный |

- **Frontend** — `strategy_builder.js` alone is 9,819 lines| `backtesting/fast_optimizer.py` | 1,642 | 🟢 P2 | Оптимизация | Numba engine |

| `backtesting/universal_engine/automl_strategies.py` | 1,560 | 🟢 P2 | AutoML | Выделить стратегии |

### Key Risk Factors| `services/adapters/bybit.py` | 1,499 | 🟢 P2 | API adapter | Уже рефакторинг |

| `agents/mcp/tools/strategy_builder.py` | 1,490 | 🟢 P2 | MCP tools | Разбить по инструментам |

| Risk | Severity | Scope || `backtesting/engines/dca_engine.py` | 1,452 | 🟢 P2 | DCA | Уже специализирован |

|------|----------|-------|| `core/indicators/price_action_numba.py` | 1,428 | 🟢 P2 | Индикаторы | Numba оптимизация |

| `commission_rate = 0.0007` must not drift | CRITICAL | 12+ files || `core/metrics_calculator.py` | 1,306 | ✅ DONE | Метрики | formulas.py создан |

| `engine.py` (legacy) consumed by 8 production files | HIGH | 8 consumers || `services/advanced_backtesting/engine.py` | 1,296 | 🟢 P2 | Engine | Уже advanced |

| No size limit enforced on any file | HIGH | 224 files > 500 ln |

| Universal Engine has near-zero external consumers | MEDIUM | 2 external files |---

| `backend/services/` is a catch-all directory | MEDIUM | 85+ files |

### 2. **Frontend: Крупные файлы (>500 строк)**

---

| Файл | Строк | Приоритет | Проблема | Рекомендация |

## 2. Project Statistics|------|-------|-----------|----------|--------------|

| `js/pages/strategy_builder.js` | 9,816 | ✅ 95% | Монолит | StateManager + модули |

### Backend (Python)| `js/pages/market_chart.js` | ~800 | 🟢 P2 | Chart | Вынести chart logic |

| `js/pages/backtest_results.js` | ~600 | ✅ DONE | Results | ChartManager + utilities |

| Metric | Count || `js/pages/dashboard.js` | ~600 | ✅ DONE | Dashboard | StateManager |

|--------|-------|| `js/pages/optimization_panels.js` | ~600 | 🟢 P2 | Optimization | Разбить панели |

| Total Python files | **616** || `js/pages/optimization_results.js` | ~600 | 🟢 P2 | Results | Вынести компоненты |

| Files > 500 lines | **224** (36%) || `js/components/BacktestModule.js` | ~600 | 🟢 P2 | Module | Уже модуль |

| Files > 2,000 lines | 10 (verified) || `js/pages/optimization_config_panel.js` | ~550 | 🟢 P2 | Config | Разбить настройки |

| Files > 3,000 lines | 6 (verified) || `js/pages/analytics_advanced.js` | ~550 | 🟢 P2 | Analytics | Вынести метрики |

| `js/pages/trading.js` | ~550 | 🟢 P2 | Trading | Разделить логику |

### Top 15 Largest Python Files (verified)| `js/components/TradingViewEquityChart.js` | ~550 | 🟢 P2 | Chart | TV integration |

| `js/pages/optimization.js` | ~550 | 🟢 P2 | Optimization | Вынести логику |

| Rank | Lines | File || `js/testing/TestUtils.js` | ~550 | 🟢 P2 | Testing | TestUtils |

|------|-------|------|| `js/core/PerformanceMonitor.js` | ~550 | 🟢 P2 | Perf | Monitoring |

| 1 | **4,121** | `backend/backtesting/gpu_optimizer.py` || `js/core/ApiClient.js` | ~550 | 🟢 P2 | API | Уже сервис |

| 2 | **3,834** | `backend/api/routers/optimizations.py` |

| 3 | **3,574** | `backend/backtesting/strategy_builder_adapter.py` |---

| 4 | **3,554** | `backend/api/routers/strategy_builder.py` |

| 5 | **3,448** | `backend/backtesting/engines/numba_engine_v2.py` |### 3. **Backend: Universal Engine (legacy)**

| 6 | **2,923** | `backend/backtesting/engines/fallback_engine_v4.py` |

| 7 | **2,753** | `backend/api/routers/backtests.py` |**Директория:** `backend/backtesting/universal_engine/`

| 8 | **2,729** | `backend/agents/workflows/builder_workflow.py` |

| 9 | **2,658** | `backend/backtesting/engine.py` || Файл | Строк | Статус | Рекомендация |

| 10 | **2,494** | `backend/api/routers/marketdata.py` ||------|-------|--------|--------------|

| 11 | **2,217** | `backend/backtesting/indicator_handlers.py` || `core_v23.py` | 903 | ⚠️ Legacy | Заменить на fallback_v4 |

| 12 | **1,935** | `backend/backtesting/universal_engine/automl_strategies.py` || `advanced_features.py` | 659 | ⚠️ Legacy | Интегрировать в v4 |

| 13 | **1,900** | `backend/backtesting/fast_optimizer.py` || `advanced_optimization.py` | 807 | ⚠️ Legacy | Genetic optimizer |

| 14 | **1,821** | `backend/core/indicators/price_action_numba.py` || `advanced_signals.py` | 972 | ⚠️ Legacy | Advanced blocks |

| 15 | **1,773** | `backend/backtesting/engines/dca_engine.py` || `gpu_acceleration.py` | 812 | ⚠️ Legacy | Numba engine |

| `live_trading.py` | 1,013 | ⚠️ Legacy | Unified API |

### Frontend (JavaScript — `frontend/js/`, no node_modules)| `multi_exchange.py` | 893 | ⚠️ Legacy | Multi-exchange |

| `options_strategies.py` | 927 | ⚠️ Legacy | Options |

| Lines | File || `order_book.py` | 962 | ⚠️ Legacy | L2 collector |

|-------|------|| `portfolio_metrics.py` | 780 | ⚠️ Legacy | Portfolio module |

| **9,819** | `frontend/js/pages/strategy_builder.js` || `realistic_simulation.py` | 1,218 | ⚠️ Legacy | Execution simulator |

| **5,712** | `frontend/js/pages/market_chart.js` || `regime_detection.py` | 926 | ⚠️ Legacy | Market regime |

| **4,917** | `frontend/js/pages/backtest_results.js` || `reinforcement_learning.py` | 1,116 | ⚠️ Legacy | RL env |

| **2,364** | `frontend/js/pages/dashboard.js` || `risk_parity.py` | 1,089 | ⚠️ Legacy | Portfolio risk_parity |

| **1,552** | `frontend/js/pages/optimization_panels.js` || `sentiment_analysis.py` | 858 | ⚠️ Legacy | Sentiment blocks |

| **1,390** | `frontend/js/pages/optimization_results.js` || `signal_generator.py` | 706 | ⚠️ Legacy | Signal flow |

| **1,144** | `frontend/js/components/BacktestModule.js` || `trade_executor.py` | 720 | ⚠️ Legacy | Order executor |

| **1,109** | `frontend/js/pages/analytics_advanced.js` || `trading_enhancements.py` | 1,027 | ⚠️ Legacy | Enhancements |

| `visualization.py` | 1,180 | ⚠️ Legacy | Visualization |

---

**Рекомендация:** Полная депрекация и миграция на новые модули

## 3. P0 — Critical Monoliths (Act Now)

---

**Target:** Split within current sprint. Each resulting file should be < 600 lines.

**Rule:** Move code only — do NOT modify logic during a split.### 4. **Backend: Agents (требуют упрощения)**

---| Файл | Строк | Проблема | Рекомендация |

|------|-------|----------|--------------|

### 3.1 `backend/backtesting/gpu_optimizer.py` — 4,121 lines| `agents/consensus/deliberation.py` | 1,175 | Сложная логика | Упростить flow |

| `agents/prompts/templates.py` | 1,262 | Много шаблонов | Вынести в JSON |

**Priority:** P0-1 (largest file in project)| `agents/consensus/consensus_engine.py` | 750 | Engine | Уже рефакторинг |

| `agents/consensus/domain_agents.py` | 731 | Agents | Уже модули |

**Proposed split:**| `agents/consensus/perplexity_integration.py` | 592 | Integration | Уже сервис |

```| `agents/consensus/real_llm_deliberation.py` | 580 | Deliberation | Уже поток |

backend/backtesting/gpu/| `agents/self_improvement/performance_evaluator.py` | 713 | Evaluator | Уже метрики |

    __init__.py               ← re-export public API for backward compat| `agents/self_improvement/strategy_evolution.py` | 651 | Evolution | Уже эволюция |

    optimizer.py              ← orchestrator class, ~400 ln| `agents/self_improvement/rlhf_module.py` | 640 | RLHF | Уже RLHF |

    kernels.py                ← CUDA/numba @jit/@cuda.jit kernels| `agents/self_improvement/self_reflection.py` | 511 | Reflection | Уже рефлексия |

    parameter_grid.py         ← grid/param generation utilities| `agents/strategy_controller.py` | 744 | Controller | Уже контроллер |

    fitness.py                ← fitness/scoring functions| `agents/unified_agent_interface.py` | 728 | Interface | Уже интерфейс |

    population.py             ← evolution, selection, mutation

    result_aggregator.py      ← result ranking and output formatting---

````

### 5. **Services (требуют модернизации)**

**Risks:**

- Numba JIT cache is keyed by file path — run a cold start test after moving kernels| Файл | Строк | Проблема | Рекомендация |

- Circular imports if `kernels.py` needs optimizer state → introduce a data-only `types.py`|------|-------|----------|--------------|

- `backend/api/routers/optimizations.py` (P0-2) imports from this file — coordinate splits| `services/state_manager.py` | 1,036 | State | Уже StateManager JS |

| `services/smart_kline_service.py` | 1,047 | Klines | Уже data_service |

**Effort:** 3–4 days (includes tests and JIT recompile validation)| `services/db_maintenance_server.py` | 1,040 | DB maint | Уже maintenance |

| `services/kms_integration.py` | 950 | KMS | Уже KMS |

---| `services/git_secrets_scanner.py` | 851 | Secrets | Уже scanner |

| `services/data_service.py` | 845 | Data | Уже сервис |

### 3.2 `backend/api/routers/optimizations.py` — 3,834 lines| `services/strategy_builder/code_generator.py` | 969 | Code gen | Уже генератор |

| `services/strategy_builder/indicators.py` | 916 | Indicators | Уже индикаторы |

**Priority:** P0-2| `services/strategy_builder/builder.py` | 907 | Builder | Уже builder |

| `services/strategy_builder/templates.py` | 820 | Templates | Уже шаблоны |

**Proposed split:**| `services/strategy_builder/validator.py` | 677 | Validator | Уже валидатор |

```| `services/advanced_backtesting/portfolio.py` | 821 | Portfolio | Уже portfolio |

backend/api/routers/| `services/tournament_orchestrator.py` | 777 | Tournament | Уже оркестратор |

    optimizations.py            ← slim include_router hub| `services/data_quality_service.py` | 771 | Quality | Уже quality |

    optimizations/| `services/live_trading/order_executor.py` | 758 | Orders | Уже executor |

        __init__.py| `services/paper_trading.py` | 658 | Paper | Уже paper trading |

        genetic.py              ← genetic algorithm endpoints| `services/risk_management/risk_engine.py` | 654 | Risk | Уже risk limits |

        grid_search.py          ← grid/random search endpoints| `services/report_export.py` | 617 | Reports | Уже reports |

        results.py              ← result retrieval and pagination| `services/service_registry.py` | 612 | Registry | Уже registry |

        tournament.py           ← tournament/competition logic| `services/live_trading/bybit_websocket.py` | 612 | WebSocket | Уже websocket_client |

        models.py               ← shared Pydantic request/response models| `services/trading_engine_interface.py` | 604 | Interface | Уже unified_api |

```| `services/property_testing.py` | 587 | Testing | Уже тесты |

| `services/db_metrics.py` | 581 | Metrics | Уже метрики |

**Risks:**| `services/ab_testing.py` | 569 | A/B | Уже A/B |

- FastAPI `include_router` prefix ordering — verify no path collisions| `services/event_bus.py` | 538 | EventBus | Уже event bus |

- Tests that `from backend.api.routers.optimizations import SomeModel` need import path updates| `services/data_quality.py` | 544 | Quality | Уже quality |

- Read `CLAUDE.md §7` before touching optimization scoring or `commission_value`| `services/tick_service.py` | 542 | Tick | Уже tick service |

| `services/advanced_backtesting/analytics.py` | 540 | Analytics | Уже analytics |

**Effort:** 2–3 days| `services/advanced_backtesting/slippage.py` | 533 | Slippage | Уже slippage |

| `services/api_key_rotation.py` | 510 | Keys | Уже rotation |

---| `services/monte_carlo.py` | 508 | Monte Carlo | Уже monte_carlo |

| `services/secure_config.py` | 505 | Config | Уже config |

### 3.3 `backend/backtesting/strategy_builder_adapter.py` — 3,574 lines| `services/synthetic_monitoring.py` | 502 | Monitoring | Уже monitoring |



**Priority:** P0-3---



**Proposed split:**## 🟡 ПРИОРИТЕТЫ РЕФАКТОРИНГА

````

backend/backtesting/strategy_builder/### P0 — Критичные (немедленно)

    __init__.py               ← re-export StrategyBuilderAdapter

    adapter.py                ← thin façade, delegates to sub-modules1. **`backtesting/gpu_optimizer.py`** (3,500 строк)

    indicators.py             ← indicator dispatch and computation   - Разбить на: `gpu_optimizer.py`, `cupy_optimizer.py`, `optimizer_config.py`

    signals.py                ← signal generation pipeline   - Выделить: GPU kernels, optimization logic, result processing

    params.py                 ← parameter validation and normalization

    compiler.py               ← code generation / compilation2. **`api/routers/optimizations.py`** (3,264 строк)

```  - Разбить на:`grid_search.py`, `bayesian.py`, `genetic.py`, `walk_forward.py`

- Выделить: Endpoints, business logic, result processing

**Risks:**

- `strategy_params` is cross-cutting — verify in all 3 consuming routers before touching3. **`api/routers/strategy_builder.py`** (3,109 строк)

- `builder_workflow.py` (P1) depends on this adapter — update imports after split - Разбить на: `blocks.py`, `validation.py`, `code_gen.py`, `templates.py`

- Many conditional branches keyed on indicator type → move type enum to `types.py` - Выделить: CRUD, validation, code generation

**Effort:** 3–4 days4. **`backtesting/strategy_builder_adapter.py`** (3,087 строк)

- Разбить на: `graph_parser.py`, `signal_generator.py`, `block_executors.py`

--- - Выделить: Graph processing, signal generation, execution

### 3.4 `backend/api/routers/strategy_builder.py` — 3,554 lines### P1 — Важные (2 недели)

**Priority:** P0-45. **`backtesting/engines/`** (numba_engine_v2.py, fallback_engine_v4.py)

- Документировать

**Proposed split:** - Выделить общие части

````- Создать abstract base engine

backend/api/routers/

    strategy_builder.py            ← slim include_router hub6. **`api/routers/backtests.py`** (2,455 строк)

    strategy_builder/   - Разделить CRUD операции

        __init__.py   - Выделить business logic

        build.py                   ← build/preview endpoints

        indicators.py              ← indicator configuration endpoints7. **`agents/workflows/builder_workflow.py`** (2,405 строк)

        templates.py               ← template management   - State machine pattern

        validation.py              ← validation endpoints   - Выделить шаги workflow

        models.py                  ← shared Pydantic models

```8. **`backtesting/engine.py`** (2,357 строк)

   - Заменить на fallback_engine_v4

**Risks:**   - Депрекейт legacy

- `direction` default is "long" in API, "both" in engine — do NOT change during split

- Leverage default mismatch (10 vs 1.0) — do NOT touch defaults during split### P2 — Желательные (1 месяц)

- Tests under `tests/api/test_strategy_builder*.py` need import path updates

9. **Universal Engine** (18 файлов, ~15,000 строк)

**Effort:** 2–3 days   - Полная депрекация

   - Миграция на новые модули

---

10. **Services** (30+ файлов, ~20,000 строк)

## 4. P1 — Important Complex Files (2 Weeks)    - Консолидация дублирующегося кода

    - Удаление legacy

**Target:** Document thoroughly first, then refactor. These are hot paths.

---

---

## 📈 ПЛАН РЕФАКТОРИНГА

### 4.1 `backend/backtesting/engines/numba_engine_v2.py` — 3,448 lines

### Этап 1: Критичные P0 (2 недели)

**Approach:** Document → extract JIT kernels → extract metric computation

````

**Proposed split:**Неделя 1:

````├── gpu_optimizer.py → модули

backend/backtesting/engines/├── optimizations.py → endpoints

    numba_engine_v2.py         ← orchestrator, ~700 ln└── Тесты

    numba_kernels_v2.py        ← @njit functions (pure numeric, portable)

    numba_metrics_v2.py        ← post-trade metric computationНеделя 2:

```├── strategy_builder.py → модули

├── strategy_builder_adapter.py → модули

**Key constraint:** `@njit` functions must remain pure numeric (no object mode). Keep them└── Тесты

separate from any class-level state.```



**Effort:** 4–5 days (JIT recompile testing adds time)### Этап 2: Важные P1 (2 недели)



---```

Неделя 3:

### 4.2 `backend/backtesting/engines/fallback_engine_v4.py` — 2,923 lines├── Engines документация

├── backtests.py → CRUD

**Approach:** This is the **gold standard engine** — treat with extreme care.└── Тесты



**Steps:**Неделя 4:

1. Add comprehensive inline documentation for every branch├── builder_workflow.py → state machine

2. Extract pure helper functions into `fallback_helpers_v4.py` (no logic changes)├── engine.py → депрекация

3. Keep the main class intact in this file└── Тесты

````

**Critical constraint:** `commission_rate = 0.0007` must not change. Run TradingView parity

tests (`pytest tests/ -k "parity"`) after ANY edit to this file.### Этап 3: Желательные P2 (1 месяц)

**Effort:** 3 days (documentation-first, no structural split)```

Неделя 5-6: Universal Engine депрекация

---Неделя 7-8: Services консолидация

````

### 4.3 `backend/api/routers/backtests.py` — 2,753 lines

---

**Proposed split:**

```## 🎯 ИТОГОВЫЕ ЦИФРЫ

backend/api/routers/

    backtests.py              ← execute/run endpoints**К рефакторингу:**

    backtests_crud.py         ← list, get, delete endpoints- Backend: 142 файла (>500 строк)

    backtests_results.py      ← results formatting and comparison- Frontend: 15 файлов (>500 строк)

    backtests_models.py       ← shared Pydantic models- Universal Engine: 18 файлов (депрекация)

```- Services: 30+ файлов (консолидация)



**Effort:** 2 days**Общий объём:** ~60,000 строк кода



---**Оценка времени:**

- P0: 2 недели

### 4.4 `backend/agents/workflows/builder_workflow.py` — 2,729 lines- P1: 2 недели

- P2: 1 месяц

**Proposed split:**

```**Итого:** ~2 месяца полного рефакторинга

backend/agents/workflows/

    builder_workflow.py           ← orchestrator---

    builder_phases/

        __init__.py*Аудит проведён: 2026-02-26*

        validation_phase.py*Статус: ✅ Готово к планированию*

        compilation_phase.py
        optimization_phase.py
        result_phase.py
````

**Effort:** 3 days

---

### 4.5 `backend/backtesting/engine.py` — 2,658 lines (LEGACY)

**Approach:** Do NOT split yet — migrate all 8 consumers to `FallbackEngineV4` first.

**Steps:**

1. Add `DeprecationWarning` to all public entry points in this file
2. Create `backend/core/engine_v4_shim.py` as compatibility layer
3. Migrate consumers one-by-one (order in §8)
4. Delete `engine.py` only after all 8 consumers are migrated and tests pass

**See §8** for the full consumer migration map.

**Effort:** 5–7 days (migration-first, delete-last)

---

### 4.6 `backend/api/routers/marketdata.py` — 2,494 lines

**Proposed split:**

```
backend/api/routers/
    marketdata.py               ← OHLCV / klines (primary endpoint group)
    marketdata_orderbook.py     ← order book endpoints
    marketdata_tickers.py       ← ticker and price feed endpoints
    marketdata_symbols.py       ← symbol info and search
```

**Effort:** 2 days

---

## 5. P2 — Universal Engine Deprecation

### Actual Location

```
backend/backtesting/universal_engine/
```

> ⚠️ The path is **NOT** `backend/universal_engine/` — that directory does not exist.

### Size (verified)

| Metric      | Verified   | Originally Reported |
| ----------- | ---------- | ------------------- |
| Total files | **27**     | 18                  |
| Total lines | **28,364** | ~15,000             |

### All Files by Line Count

| Lines | File                        |
| ----- | --------------------------- |
| 1,935 | `automl_strategies.py`      |
| 1,501 | `realistic_simulation.py`   |
| 1,464 | `reinforcement_learning.py` |
| 1,393 | `visualization.py`          |
| 1,377 | `risk_parity.py`            |
| 1,284 | `trading_enhancements.py`   |
| 1,237 | `live_trading.py`           |
| 1,216 | `advanced_signals.py`       |
| 1,196 | `order_book.py`             |
| 1,155 | `options_strategies.py`     |
| 1,102 | `multi_exchange.py`         |
| 1,089 | `core_v23.py`               |
| 1,038 | `sentiment_analysis.py`     |
| 1,033 | `advanced_optimization.py`  |
| 1,028 | `gpu_acceleration.py`       |
| 979   | `portfolio_metrics.py`      |
| 953   | `regime_detection.py`       |
| 876   | `filter_engine.py`          |
| 867   | `trade_executor.py`         |
| 863   | `advanced_features.py`      |
| ~845  | `signal_generator.py`       |
| 775   | `position_manager.py`       |
| 583   | `core.py`                   |
| ~300  | `optimizer.py`              |
| ~200  | `examples.py`               |
| ~100  | `__init__.py`               |
| ~50   | (remaining)                 |

### External Consumers (OUTSIDE the module)

Only **2 files** import from `universal_engine` outside the module:

```
backend/experimental/l2_lob/models.py
backend/experimental/l2_lob/replay.py
```

Both are in `backend/experimental/` — not in any production API path.

### Internal Cross-Imports

`__init__.py`, `core.py`, `core_v23.py`, `examples.py`, and `optimizer.py` import from each
other within the module.

### Deprecation Plan

**Phase 1 — Isolate (Week 1):**

1. Add `# DEPRECATED: universal_engine — see docs/DECISIONS.md` to all 27 file headers
2. Add `DeprecationWarning` to all public class/function `__init__` methods
3. Document the deprecation decision in `docs/DECISIONS.md`

**Phase 2 — Extract Value (Weeks 2–3):**  
Identify algorithms worth preserving before deletion:

| File                      | Decision                          | Target Location                             |
| ------------------------- | --------------------------------- | ------------------------------------------- |
| `realistic_simulation.py` | Preserve slippage/fill modeling   | `services/advanced_backtesting/slippage.py` |
| `risk_parity.py`          | Preserve risk calculations        | `services/risk_management/`                 |
| `regime_detection.py`     | Preserve regime logic             | `core/indicators/`                          |
| `visualization.py`        | Partial — review for unique logic | `core/` or delete                           |
| All others                | Delete                            | —                                           |

**Phase 3 — Migrate l2_lob (Week 3):**

1. Migrate `backend/experimental/l2_lob/models.py` off `universal_engine`
2. Migrate `backend/experimental/l2_lob/replay.py` off `universal_engine`
3. Provide local type copies in `l2_lob/` if needed (it's experimental, not stable)

**Phase 4 — Delete (Week 4):**

1. Remove `backend/backtesting/universal_engine/` entirely
2. Remove `universal_engine` from any `__init__.py` re-exports
3. Update `pyproject.toml` if the path is referenced
4. Run full test suite: `pytest tests/ -v`

**Overall risk:** LOW — `experimental/` is not in any production API route.

---

## 6. P2 — Services Consolidation

### Overview

`backend/services/` contains **85+ files** across 6 subdirectories plus many standalone files.
There is no enforced rule about what belongs here vs. `backend/core/` vs. `backend/backtesting/`.

```
backend/services/
    adapters/              ← Bybit, Binance API connectors
    strategy_builder/      ← builder sub-service
    advanced_backtesting/  ← extended backtest features
    live_trading/          ← live/paper order execution
    risk_management/       ← risk rules engine
    unified_trading/       ← thin abstractions (< 130 lines each)
    [standalone files]     ← 30+ loose service files
```

### Key Files by Subdirectory

#### `adapters/`

| Lines | File                    |
| ----- | ----------------------- |
| 1,700 | `bybit.py`              |
| 1,016 | `bybit_from_history.py` |
| 708   | `bybit_alembic.py`      |
| 80    | `binance.py`            |

#### `strategy_builder/`

| Lines | File                |
| ----- | ------------------- |
| 1,155 | `code_generator.py` |
| 1,094 | `indicators.py`     |
| 1,011 | `builder.py`        |
| 957   | `templates.py`      |
| 797   | `validator.py`      |

#### `advanced_backtesting/`

| Lines | File           |
| ----- | -------------- |
| 1,520 | `engine.py`    |
| 992   | `portfolio.py` |
| 650   | `analytics.py` |
| 634   | `slippage.py`  |
| 546   | `metrics.py`   |

#### `live_trading/`

| Lines | File                   |
| ----- | ---------------------- |
| 884   | `order_executor.py`    |
| 847   | `strategy_runner.py`   |
| 745   | `bybit_websocket.py`   |
| 679   | `position_manager.py`  |
| 440   | `graceful_shutdown.py` |

#### `risk_management/`

| Lines | File                     |
| ----- | ------------------------ |
| 775   | `risk_engine.py`         |
| 715   | `trade_validator.py`     |
| 668   | `exposure_controller.py` |
| 568   | `stop_loss_manager.py`   |
| 539   | `position_sizing.py`     |

#### `unified_trading/` (5 tiny files — merge candidate)

| Lines | File                          |
| ----- | ----------------------------- |
| 125   | `simulated_executor.py`       |
| 113   | `strategy_runner.py`          |
| 102   | `historical_data_provider.py` |
| 94    | `interfaces.py`               |
| 73    | `live_data_provider.py`       |

#### Largest Standalone Files

| Lines | File                          |
| ----- | ----------------------------- |
| 1,259 | `state_manager.py`            |
| 1,242 | `db_maintenance_server.py`    |
| 1,240 | `smart_kline_service.py`      |
| 1,171 | `kms_integration.py`          |
| 971   | `data_service.py`             |
| 952   | `git_secrets_scanner.py`      |
| 931   | `tournament_orchestrator.py`  |
| 917   | `data_quality_service.py`     |
| 792   | `paper_trading.py`            |
| 764   | `service_registry.py`         |
| 730   | `trading_engine_interface.py` |
| 712   | `ab_testing.py`               |
| 701   | `ai_strategy_generator.py`    |

### Consolidation Rules (post-refactor)

| Directory                   | Belongs Here                                         |
| --------------------------- | ---------------------------------------------------- |
| `services/adapters/`        | External API connectors only (Bybit, Binance)        |
| `services/data/`            | Data acquisition, caching, quality (new dir)         |
| `services/live_trading/`    | Live/paper order execution — no changes needed       |
| `services/risk_management/` | Risk rules engine — no changes needed                |
| `services/backtesting/`     | Merge `advanced_backtesting/` here (rename)          |
| `backend/core/`             | Shared utilities, metrics, indicators — not services |

### Files to Move OUT of `services/`

| File                         | Target                 |
| ---------------------------- | ---------------------- |
| `git_secrets_scanner.py`     | `backend/security/`    |
| `kms_integration.py`         | `backend/security/`    |
| `ab_testing.py`              | `backend/experiments/` |
| `ai_strategy_generator.py`   | `backend/ml/`          |
| `tournament_orchestrator.py` | `backend/backtesting/` |
| `db_maintenance_server.py`   | `backend/maintenance/` |

### Files to Consolidate

- `unified_trading/` (5 files, ~507 lines) → merge into `live_trading/interfaces.py`
- `smart_kline_service.py` + `data_service.py` + `data_quality_service.py` → `services/data/`

**Effort:** 1–2 weeks (primarily mechanical moves + import updates + test fixes)

---

## 7. Frontend Debt

### Largest JS Files

| Lines | File                           | Recommended Action                |
| ----- | ------------------------------ | --------------------------------- |
| 9,819 | `pages/strategy_builder.js`    | Split into feature modules        |
| 5,712 | `pages/market_chart.js`        | Extract chart plugins             |
| 4,917 | `pages/backtest_results.js`    | Extract table and chart renderers |
| 2,364 | `pages/dashboard.js`           | Document first — low urgency      |
| 1,552 | `pages/optimization_panels.js` | Leave as-is                       |

### `strategy_builder.js` — 9,819 lines (Highest Priority Frontend)

Suggested module split:

```
frontend/js/pages/
    strategy_builder.js              ← app shell, event bus, ~600 ln
    strategy_builder/
        indicator_panel.js           ← indicator add/remove/configure UI
        signal_logic_panel.js        ← entry/exit signal logic
        backtest_panel.js            ← backtest config and run button
        optimization_panel.js        ← optimizer config (reuse existing file)
        results_panel.js             ← inline results display
        api_client.js                ← all fetch() calls to backend
        state.js                     ← global state object
```

**Risks:**

- `leverageManager.js` and `direction` defaults — see `CLAUDE.md §3` — do NOT change defaults
- Circular event handlers if not split cleanly — use a central event bus
- E2E tests reference DOM IDs — IDs must not change during split

**Effort:** 5–7 days (JS module wiring, E2E tests)

---

## 8. Legacy `engine.py` Dependency Map

`backend/backtesting/engine.py` (2,658 lines) is being superseded by `FallbackEngineV4`.
It must not be deleted until all 8 consumers are migrated.

### All 8 Consumers

| File                                      | Migration Path                             |
| ----------------------------------------- | ------------------------------------------ |
| `backend/api/routers/backtests.py`        | Route through `engine_selector.py`         |
| `backend/api/routers/optimizations.py`    | Route through `engine_selector.py`         |
| `backend/api/routers/strategy_builder.py` | Route through `engine_selector.py`         |
| `backend/backtesting/__init__.py`         | Update re-exports after all above migrated |
| `backend/backtesting/service.py`          | Migrate to FallbackEngineV4 API directly   |
| `backend/backtesting/validation_suite.py` | **KEEP** — TradingView parity tests        |
| `backend/core/engine_adapter.py`          | Redirect shim to V4                        |
| `backend/ml/ai_backtest_executor.py`      | Migrate to FallbackEngineV4 API directly   |

### Recommended Migration Order (least-risky first)

1. `ml/ai_backtest_executor.py` — isolated, no UI dependency
2. `backtesting/service.py` — internal, easy to test
3. `core/engine_adapter.py` — shim by design
4. `api/routers/backtests.py` — high value, needs thorough testing
5. `api/routers/strategy_builder.py` — P0 split already planned, combine
6. `api/routers/optimizations.py` — P0 split already planned, combine
7. `backtesting/__init__.py` — last, update re-exports
8. `backtesting/validation_suite.py` — **do not migrate** — keep for parity tests

### Migration Pattern

```python
# BEFORE (legacy engine.py)
from backend.backtesting.engine import BacktestEngine
engine = BacktestEngine(config)
result = engine.run(data)

# AFTER (FallbackEngineV4)
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngine
engine = FallbackEngine(config)
result = engine.run(data)
# Note: FallbackEngine uses commission_rate=0.0007 by default — NEVER override
```

---

## 9. Timeline and Priority Order

### Sprint 1 (Week 1–2): P0 Splits

| Day  | Task                                       | Files                                   |
| ---- | ------------------------------------------ | --------------------------------------- |
| 1–2  | Split `gpu_optimizer.py`                   | `backend/backtesting/gpu/`              |
| 3–4  | Split `optimizations.py` router            | `optimizations/` sub-routers            |
| 5–6  | Split `strategy_builder_adapter.py`        | `backend/backtesting/strategy_builder/` |
| 7–8  | Split `strategy_builder.py` router         | `strategy_builder/` sub-routers         |
| 9–10 | Integration tests, ruff, parity validation | All P0 files                            |

### Sprint 2 (Week 3–4): P1 Documentation + `engine.py` Migration

| Day  | Task                                                     |
| ---- | -------------------------------------------------------- |
| 1–2  | Inline-document `fallback_engine_v4.py`                  |
| 3–4  | Document + extract JIT kernels from `numba_engine_v2.py` |
| 5–6  | Split `backtests.py` router                              |
| 7–8  | Migrate first 3 `engine.py` consumers to V4              |
| 9–10 | Migrate remaining 4 consumers, add deprecation warnings  |

### Sprint 3 (Week 5–6): P2 Universal Engine Deprecation

| Day  | Task                                                                       |
| ---- | -------------------------------------------------------------------------- |
| 1–2  | Add deprecation warnings to all 27 UE files                                |
| 3–4  | Extract `realistic_simulation.py`, `risk_parity.py`, `regime_detection.py` |
| 5–6  | Migrate `l2_lob/models.py` and `l2_lob/replay.py`                          |
| 7–8  | Delete `backend/backtesting/universal_engine/`                             |
| 9–10 | Update imports, run full test suite                                        |

### Sprint 4 (Week 7–8): P2 Services + Frontend

| Day  | Task                                                    |
| ---- | ------------------------------------------------------- |
| 1–3  | Relocate misplaced services (security, experiments, ml) |
| 4–5  | Merge `unified_trading/` into `live_trading/`           |
| 6–7  | Begin `strategy_builder.js` split                       |
| 8–10 | Frontend integration, E2E tests                         |

---

## 10. Refactoring Checklist Template

Use this for every file split:

```markdown
## Refactor: <file_name>

- [ ] Read CLAUDE.md §15 (Refactor Checklist) before starting
- [ ] grep all imports of this file: grep -rn "from backend.path.file import" backend/ frontend/
- [ ] Document public API surface before splitting (function signatures, return types)
- [ ] Create new module structure with **init**.py re-exports for backward compat
- [ ] MOVE code only — do NOT change logic during the move
- [ ] Update all import sites
- [ ] Run: pytest tests/ -v
- [ ] Run: ruff check . --fix && ruff format .
- [ ] If engine touched, run parity test: pytest tests/ -k "parity" -v
- [ ] Verify commission_rate unchanged:
      grep -rn commission backend/ | grep -v 0.0007 | grep -v .pyc | grep -v **pycache**
- [ ] Update CHANGELOG.md entry
- [ ] Commit: "refactor(<module>): split <file> into <n> modules"
```

---

## 11. Ongoing Monitoring Commands

Run these periodically to track progress (PowerShell):

```powershell
# Count files currently exceeding 500 lines
$count = (Get-ChildItem -Recurse -Filter "*.py" backend/ | ForEach-Object {
    (Get-Content $_.FullName | Measure-Object -Line).Lines
} | Where-Object { $_ -gt 500 }).Count
Write-Host "Files > 500 lines: $count"

# List all current monoliths > 1000 lines
Get-ChildItem -Recurse -Filter "*.py" backend/ | ForEach-Object {
    $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines
    if ($lines -gt 1000) { "$lines`t$($_.FullName)" }
} | Sort-Object { [int]($_ -split "`t")[0] } -Descending

# Verify commission_rate consistency (MUST always return empty)
Select-String -Path "backend\**\*.py" -Pattern "commission" -Recurse |
    Where-Object { $_ -notmatch "0\.0007" } |
    Where-Object { $_ -notmatch "__pycache__" } |
    Where-Object { $_ -notmatch "\.pyc" }
```

---

_All line counts verified via `Get-Content | Measure-Object -Line` as of 2026-02-27._  
_Update this document at the end of each sprint._  
_See also: `CLAUDE.md`, `docs/DECISIONS.md`, `CHANGELOG.md`_
