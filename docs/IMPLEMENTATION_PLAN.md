# 📋 План реализации: Система LLM-агентов для торговых стратегий

> **Создан:** 2026-02-09  
> **Основа:** ТЗ "Система LLM-агентов" (ТЗ_01/Система LLM-агентов.txt)  
> **Статус:** Активный

---

## 📊 Сводка текущего состояния

| Компонент                     | Файл/Модуль                                                              | Готовность | Статус                                                            |
| ----------------------------- | ------------------------------------------------------------------------ | ---------- | ----------------------------------------------------------------- |
| LLM Agents Pool               | `agents/llm/connections.py`                                              | 85%        | DeepSeek ✅, Qwen ✅, Perplexity ✅, Ollama ✅                    |
| Unified Agent Interface       | `agents/unified_agent_interface.py`                                      | 80%        | Работает, ключи, fallback, health ✅                              |
| Domain Agents                 | `agents/consensus/domain_agents.py`                                      | 70%        | 4 агента (Trading, Risk, Code, Market) ✅                         |
| Real LLM Deliberation         | `agents/consensus/real_llm_deliberation.py`                              | **100%**   | **✅ DeepSeek + Perplexity + Qwen, 35 тестов**                    |
| LangGraph Orchestrator        | `agents/langgraph_orchestrator.py`                                       | **100%**   | **✅ StateGraph pipeline, 40 тестов**                              |
| AI Backtest Integration       | `agents/integration/ai_backtest_integration.py`                          | **100%**   | **✅ AIBacktestAnalyzer + AIOptimizationAnalyzer, 28 тестов**      |
| Hierarchical Memory           | `agents/memory/hierarchical_memory.py`                                   | **100%**   | **✅ 4-tier memory, persistence, consolidation, 53 тестов**        |
| Self-Reflection               | `agents/self_improvement/self_reflection.py`                             | **100%**   | **✅ LLMReflectionProvider + LLMSelfReflectionEngine, 26 тестов** |
| RLHF Module                   | `agents/self_improvement/rlhf_module.py`                                 | **100%**   | **✅ RewardModel + RLHFModule, 51 тест**                           |
| Walk-Forward                  | `services/walk_forward.py` + `agents/integration/walk_forward_bridge.py` | **100%**   | **✅ WalkForwardBridge, Stage 7 в pipeline, 39 тестов**            |
| **Strategy Controller**       | **`agents/strategy_controller.py`**                                      | **100%**   | **✅ 7-stage pipeline, WF интеграция, 26 тестов**                 |
| **Prompt Engineer**           | **`agents/prompts/prompt_engineer.py`**                                  | **100%**   | **✅ PromptEngineer + TemplateLibrary**                           |
| **Response Parser**           | **`agents/prompts/response_parser.py`**                                  | **100%**   | **✅ StrategyDefinition, Signal, ExitConditions**                 |
| **Consensus Engine (полный)** | **`agents/consensus/consensus_engine.py`**                               | **100%**   | **✅ Weighted/Bayesian/BestOf, 31 тест**                          |
| **Metrics Analyzer**          | **`agents/metrics_analyzer.py`**                                         | **100%**   | **✅ Grading A-F, recommendations, 30 тестов**                    |

### Общая готовность: 100% ✅ (445 тестов, все проходят)

---

## 🎯 Приоритеты (P0 → P3)

### P0 — Критический путь (без этого ничего не работает)

Эти компоненты составляют **ядро pipeline** по ТЗ: от запроса пользователя до сгенерированной и оттестированной стратегии.

### P1 — Высокий приоритет (значительно улучшает качество)

Компоненты, которые делают систему **умнее**: мульти-агентный консенсус, анализ рынка, обратная связь.

### P2 — Средний приоритет (расширение возможностей)

Walk-forward, UI интеграция, отчёты, мониторинг.

### P3 — Низкий приоритет (polish)

RLHF training loop, мета-обучение, A/B тесты агентов.

---

## 🚀 Фаза 1: Ядро Pipeline (P0) — ~3-4 дня

### 1.1 Prompt Engineer (`backend/agents/prompts/prompt_engineer.py`)

**Цель:** Система шаблонов промптов для LLM-агентов с контекстом рынка и платформы.

**Что создать:**

```
backend/agents/prompts/
├── __init__.py
├── prompt_engineer.py       # Главный класс PromptEngineer
├── templates.py             # PROMPT_TEMPLATES словарь
└── context_builder.py       # Построение рыночного контекста
```

**Ключевые компоненты:**

- `PromptEngineer` — класс с методами:
    - `create_strategy_prompt(market_context, platform_config, agent_specialization)` → str
    - `create_optimization_prompt(strategy, backtest_results, issues)` → str
    - `create_market_analysis_prompt(symbol, timeframe, data_summary)` → str
    - `create_validation_prompt(strategy_json)` → str
- `PROMPT_TEMPLATES` — словарь шаблонов по типам (из ТЗ раздел 3.2)
- `ContextBuilder` — подготовка market_context из OHLCV данных:
    - Определение рыночного режима (тренд/рейндж/волатильность)
    - Расчёт ключевых уровней (S/R)
    - Техническая сводка (ATR, объём, тренд)

**Зависимости:** нет (standalone)
**Оценка:** 4-5 часов

---

### 1.2 Response Parser (`backend/agents/prompts/response_parser.py`)

**Цель:** Парсинг LLM-ответов в структурированные JSON-стратегии с валидацией.

**Что создать:**

```
backend/agents/prompts/response_parser.py
```

**Ключевые компоненты:**

- `ResponseParser` — класс:
    - `parse_strategy(llm_response: str)` → `StrategyDefinition | None`
    - `_extract_json(text: str)` → dict — извлечение JSON из markdown/text
    - `_fix_json(text: str)` → str — автоисправление невалидного JSON
    - `_validate_strategy(strategy: dict)` → `ValidationResult`
- `StrategyDefinition` — Pydantic-модель:
    - `strategy_name`, `description`
    - `signals: list[Signal]` — индикаторы (RSI, MACD, EMA, etc.)
    - `filters: list[Filter]` — фильтры (Volume, Trend, Time)
    - `entry_conditions`, `exit_conditions`
    - `position_management`
    - `optimization_hints`
- Валидация: проверка допустимых индикаторов, диапазонов параметров, совместимости с движком

**Зависимости:** нет
**Оценка:** 3-4 часа

---

### 1.3 Strategy Controller (`backend/agents/strategy_controller.py`)

**Цель:** Workflow-менеджер для полного цикла: анализ рынка → генерация → бэктест → оптимизация → отчёт.

**Что создать:**

```
backend/agents/strategy_controller.py
```

**Ключевые компоненты:**

- `StrategyController` — главный класс:
    - `run_full_workflow(config: WorkflowConfig)` → `WorkflowResult`
    - `_analyze_market()` → MarketContext
    - `_generate_strategies_parallel()` → list[StrategyDefinition]
    - `_apply_consensus()` → StrategyDefinition
    - `_run_backtests()` → BacktestResults
    - `_optimize_strategy()` → OptimizationResults
    - `_validate_oos()` → ValidationResults (out-of-sample)
    - `_generate_report()` → Report
- `WorkflowConfig` — Pydantic-модель запроса:
    - `symbol`, `timeframe`, `date_range`
    - `agents: list[AgentType]` — какие LLM использовать
    - `consensus_method` — weighted_voting / bayesian
    - `optimization_method` — grid / bayesian / genetic
    - `enable_walk_forward: bool`
- `WorkflowResult` — Pydantic-модель ответа с метриками каждого шага

**Зависимости:** PromptEngineer, ResponseParser, UnifiedAgentInterface, BacktestEngine
**Оценка:** 6-8 часов

---

### 1.4 Backtest Bridge (`backend/agents/integration/backtest_bridge.py`)

**Цель:** Мост между LLM-сгенерированными стратегиями и BacktestEngine.

**Что создать:**

```
backend/agents/integration/backtest_bridge.py
```

**Ключевые компоненты:**

- `BacktestBridge` — класс:
    - `convert_llm_strategy_to_engine_format(strategy: StrategyDefinition)` → dict
    - `run_backtest(strategy, symbol, timeframe, dates)` → BacktestResult
    - `run_walk_forward(strategy, ...)` → WalkForwardResult
- Маппинг LLM-сигналов → генераторы сигналов движка (RSI, MACD, EMA, SMA, Bollinger)
- Конвертация LLM exit_conditions → SL/TP параметры движка
- Обработка ошибок (невалидные параметры, отсутствие данных)

**Зависимости:** StrategyDefinition, FallbackEngineV4, DataService
**Оценка:** 4-5 часов

---

## 🔬 Фаза 2: Мульти-агентный интеллект (P1) — ~2-3 дня

### 2.1 Qwen в Real LLM Deliberation ✅ DONE

**Цель:** Добавить Qwen как третий агент в систему мульти-агентного консенсуса.

**Файл:** `backend/agents/consensus/real_llm_deliberation.py`

**Реализовано (2026-02-09):**

- `_initialize_clients()` — QwenClient уже был (pre-existing)
- `_real_ask()` — использует `AGENT_SYSTEM_PROMPTS` для агент-специфичных системных промптов
- Специализации: deepseek=quantitative, qwen=technical, perplexity=market_research
- `deliberate_with_llm()` — по умолчанию использует все доступные агенты (до 3)
- `_ask_agent()` в `deliberation.py` — исправлен маппинг для qwen
- **35 тестов** в `test_real_llm_deliberation.py` (все проходят)

**Зависимости:** QwenClient (уже реализован)
**Оценка:** 2-3 часа → Выполнено

---

### 2.2 Расширенный Consensus Engine

**Цель:** Реализовать полноценную агрегацию стратегий из ТЗ (раздел 3.4).

**Файл:** `backend/agents/consensus/consensus_engine.py` (новый)

**Что создать:**

- `ConsensusEngine` — класс:
    - `_weighted_voting()` — взвешенное голосование (основной)
    - `_bayesian_aggregation()` — байесовское объединение
    - `_calculate_agent_weight()` — вес агента по исторической точности
    - `_calculate_agreement_score()` — уровень согласия (Jaccard similarity)
    - `_calculate_consensus_params()` — медиана параметров
- Интеграция с `StrategyController._apply_consensus()`

**Зависимости:** StrategyDefinition, HistoricalPerformance
**Оценка:** 4-5 часов

---

### 2.3 Market Context Analyzer

**Цель:** Автоматический анализ рыночных данных для обогащения промптов.

**Файл:** `backend/agents/prompts/context_builder.py`

**Что создать:**

- `MarketContextBuilder` — класс:
    - `build_context(symbol, timeframe, candles_df)` → MarketContext
    - `_detect_regime()` → "trending" / "ranging" / "volatile"
    - `_find_support_resistance()` → list[float]
    - `_calculate_volatility_metrics()` → dict (ATR, historical vol)
    - `_analyze_volume_profile()` → dict
    - `_summarize_indicators()` → str (текстовая сводка RSI/MACD/BB)

**Зависимости:** pandas, pandas_ta, DataService
**Оценка:** 3-4 часа

---

### 2.4 LangGraph Pipeline Integration ✅ DONE

**Цель:** Связать LangGraph orchestrator с StrategyController для управляемого pipeline.

**Файл:** `backend/agents/integration/langgraph_pipeline.py` (новый, ~660 строк)

**Реализовано (2026-02-09):**

- `TradingStrategyGraph` — предопределённый граф из 7 узлов:
    ```
    MarketAnalysis → ParallelGeneration → Consensus → Backtest → QualityCheck
                         ↑                                         ↓
                         └── re_generate ←── DD > 20%             │
                              re_optimize ←── Sharpe < 1.0       │
                              Report ←── PASS ────────────────────┘
    ```
- Conditional edges через `ConditionalRouter`:
    - Sharpe < `min_sharpe` → `re_optimize` (walk-forward parameter tuning)
    - MaxDD > `max_drawdown_pct` → `re_generate` (full re-generation)
    - PASS → `report`
- `ParallelGenerationNode` — parallel `asyncio.gather` для LLM calls
- `PipelineConfig` — dataclass с пороговыми значениями
- `TradingStrategyGraph.run()` — single entry point
- **40 тестов** в `test_langgraph_pipeline.py` (все проходят)

**Зависимости:** StrategyController, ConsensusEngine, BacktestBridge, WalkForwardBridge
**Оценка:** 4-5 часов → Выполнено

---

## 📈 Фаза 3: Валидация и расширение (P2) — ~2 дня

### 3.1 Walk-Forward Integration ✅ ЗАВЕРШЕНО (2026-02-09)

**Цель:** Подключить WalkForwardOptimizer к pipeline.

**Создано:** `backend/agents/integration/walk_forward_bridge.py` (~470 строк)

**Реализовано:**

- `WalkForwardBridge` — адаптер между StrategyDefinition и WalkForwardOptimizer
- `build_strategy_runner()` / `build_param_grid()` — конвертация AI-формата в WF-формат
- `_execute_backtest()` — candles → DataFrame → signals → FallbackEngineV4 → metrics
- `DEFAULT_PARAM_RANGES` для 7 типов стратегий
- Stage 7: Walk-Forward Validation в StrategyController
- `PipelineResult.walk_forward` для хранения результатов
- 39 тестов в `tests/backend/agents/test_walk_forward_bridge.py`

---

### 3.2 API Endpoints для Agent Pipeline ✅ ЗАВЕРШЕНО (2026-02-09)

**Цель:** REST API для запуска и мониторинга pipeline.

**Файл:** `backend/api/routers/ai_pipeline.py` (обновлён — 6 endpoints)

**Endpoints (все работают):**

- `POST /ai-pipeline/generate` — запуск полного pipeline (с walk-forward опцией)
- `GET /ai-pipeline/agents` — список доступных LLM агентов
- `POST /ai-pipeline/analyze-market` — анализ рынка (regime, trend, volatility, levels)
- `POST /ai-pipeline/improve-strategy` — оптимизация через walk-forward
- `GET /ai-pipeline/pipeline/{id}/status` — статус и прогресс выполнения
- `GET /ai-pipeline/pipeline/{id}/result` — получение результата
- In-memory `_pipeline_jobs` для трекинга async pipeline
- 28 тестов в `tests/backend/api/test_ai_pipeline_endpoints.py`

---

### 3.3 Тесты для Pipeline

**Цель:** Unit и integration тесты для всех новых компонентов.

**Файлы:**

```
tests/backend/agents/
├── test_prompt_engineer.py        # 20+ тестов
├── test_response_parser.py        # 25+ тестов
├── test_strategy_controller.py    # 15+ тестов
├── test_backtest_bridge.py        # 10+ тестов
├── test_consensus_engine.py       # 15+ тестов
├── test_market_context.py         # 10+ тестов
```

**Оценка:** 4-5 часов

---

## 🧠 Фаза 4: Self-Improvement (P3) — ✅ DONE (2026-02-09)

### 4.1 LLM-backed Self-Reflection ✅ DONE

**Цель:** Подключить реальные LLM к self_reflection для анализа результатов.

- `backend/agents/self_improvement/llm_reflection.py` (~470 lines)
- `LLMReflectionProvider` — 3 провайдера (deepseek/qwen/perplexity), lazy init, fallback
- `LLMSelfReflectionEngine` — расширение SelfReflectionEngine с LLM
- **26 тестов** — все проходят

### 4.2 Feedback Loop ✅ DONE

**Цель:** Автоматический сбор обратной связи (бэктест → улучшение промпта).

- `backend/agents/self_improvement/feedback_loop.py` (~670 lines)
- `FeedbackLoop` — backtest → reflect → improve → repeat с детекцией сходимости
- `PromptImprovementEngine` — анализ метрик и генерация корректировок
- **33 теста** — все проходят

### 4.3 Agent Performance Tracking ✅ DONE

**Цель:** Трекинг качества каждого агента для динамического веса в консенсусе.

- `backend/agents/self_improvement/agent_tracker.py` (~480 lines)
- `AgentPerformanceTracker` — rolling window, dynamic weights, leaderboard
- `sync_to_consensus_engine()` — интеграция с ConsensusEngine
- **35 тестов** — все проходят

**Итого Phase 4: 94 теста, 313 всего в agents/ — все проходят**

---

## 📅 Предлагаемый порядок работы

```
Неделя 1 (сейчас):
├── День 1: PromptEngineer + ResponseParser (P0)
├── День 2: Strategy Controller + BacktestBridge (P0)
├── День 3: Qwen в Deliberation + ConsensusEngine (P1)
└── День 4: MarketContextBuilder + LangGraph Pipeline (P1)

Неделя 2:
├── День 5: WalkForward integration + API endpoints (P2)
├── День 6: Тесты (80%+ coverage) (P2)
└── День 7: Self-Improvement + Polish (P3)
```

---

## ⚠️ Риски и зависимости

| Риск                                    | Влияние | Митигация                                     |
| --------------------------------------- | ------- | --------------------------------------------- |
| Qwen API rate limits                    | Средний | Ротация 2 ключей, circuit breaker уже есть    |
| Невалидный JSON от LLM                  | Высокий | ResponseParser с автоисправлением + retry     |
| Медленный pipeline (>60s)               | Средний | Async + параллельная генерация + streaming    |
| Несовместимость LLM-стратегии с движком | Высокий | BacktestBridge с валидацией + fallback params |
| Overfitting при оптимизации             | Средний | Walk-forward validation + OOS проверка        |

---

## 📐 Архитектура данных (Pydantic модели)

```python
# Ключевые модели, которые нужно создать:

class WorkflowConfig:
    symbol: str                    # "BTCUSDT"
    timeframe: str                 # "15" (минуты)
    start_date: str                # "2025-01-01"
    end_date: str                  # "2025-06-01"
    agents: list[str]              # ["deepseek", "qwen"]
    consensus_method: str          # "weighted_voting"
    optimization_method: str       # "bayesian"
    initial_capital: float         # 10000
    leverage: int                  # 10
    commission: float              # 0.0007
    enable_walk_forward: bool      # True
    max_iterations: int            # 3

class StrategyDefinition:
    strategy_name: str
    description: str
    signals: list[Signal]          # RSI, MACD, EMA, etc.
    filters: list[Filter]          # Volume, Trend, Time
    entry_conditions: EntryConditions
    exit_conditions: ExitConditions
    position_management: PositionManagement
    optimization_hints: OptimizationHints
    agent_metadata: AgentMetadata

class Signal:
    id: str
    type: str                      # "RSI", "MACD", "EMA_Crossover"
    timeframe: str
    params: dict[str, Any]
    weight: float
    condition: str

class WorkflowResult:
    status: str                    # "completed", "failed"
    market_analysis: MarketContext
    generated_strategies: list[StrategyDefinition]
    consensus_strategy: StrategyDefinition
    backtest_metrics: dict
    optimization_results: dict
    walk_forward_results: dict | None
    ai_report: str
    total_time_seconds: float
```

---

_Этот план обновляется по мере прогресса. Актуальный статус — в CHANGELOG.md._
