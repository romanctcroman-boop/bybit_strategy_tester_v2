# ТЗ: Интеграция AI-агентов с инфраструктурой проекта

> **Дата:** 2026-03-20
> **Статус:** РЕАЛИЗОВАНО (8/8 задач)
> **Сессия:** 970b0f6b-1874-49e5-97f4-2272c8acc419.jsonl
> **Версия ТЗ:** v3 (финальная после двух раундов верификации)

---

## Контекст и проблема

До реализации этого ТЗ система AI-агентов (DeepSeek/QWEN/Perplexity) существовала **отдельно** от основной инфраструктуры проекта:

```
БЫЛО:
  Агенты → StrategyDefinition → BacktestBridge → 6 типов стратегий (sma/rsi/macd/bb/grid/dca)

СТАЛО:
  Агенты → StrategyDefinition → StrategyDefToGraphConverter → strategy_graph
         → StrategyBuilderAdapter → 40+ блоков (RSI/MACD/SuperTrend/QQE/Bollinger/CCI/...)
         → FallbackEngineV4 → MetricsCalculator → ORM Strategy DB
```

**Ключевой принцип:** Агенты не генерируют код — они пользуются нодами и функциями проекта. Strategy Builder с его блоками — это их вселенная.

---

## Архитектура (финальная)

```
POST /api/ai-strategy-generator/generate-and-build
  │
  ├── load OHLCV (SQLite data.sqlite3)
  │
  └── run_strategy_pipeline()
        │
        ├── AnalyzeMarketNode        → MarketContext (symbol, regime, ATR, levels)
        ├── [DebateNode]             → MAD: мнения → cross-examination → vote (опционально)
        ├── GenerateStrategiesNode   → Self-MoA: 3× DeepSeek (T=0.3/0.7/1.1) + QWEN критик
        ├── ParseResponsesNode       → StrategyDefinition (Pydantic, валидация)
        ├── ConsensusNode            → выбор лучшей стратегии (weighted voting)
        ├── BuildGraphNode           → StrategyDefinition → strategy_graph (40+ блоков)
        ├── BacktestNode             → StrategyBuilderAdapter → FallbackEngineV4
        └── MemoryUpdateNode         → HierarchicalMemory + Strategy ORM (builder_graph)
```

---

## 8 задач ТЗ v3

### Задача 1: StrategyDefToGraphConverter ✅
**Файл:** `backend/agents/integration/graph_converter.py`

Конвертер `StrategyDefinition → strategy_graph`. Три категории блоков:

**Категория A** — прямой long/short выход:
| Signal.type | block_type | activation |
|-------------|-----------|------------|
| RSI | rsi | legacy: oversold/overbought; range: use_long_range/use_short_range |
| MACD | macd | use_macd_cross_signal=True |
| Stochastic | stochastic | use_stoch_kd_cross=True |
| SuperTrend | supertrend | use_supertrend=True |
| EMA_Crossover | two_mas | use_ma_cross=True, ma1/ma2_length, smoothing="EMA" |
| SMA_Crossover | two_mas | use_ma_cross=True, ma1/ma2_length, smoothing="SMA" |
| EMA | two_mas | use_ma1_filter=True (price > MA1 filter) |
| SMA | two_mas | use_ma1_filter=True |

**Категория B** — value output, требует condition-блок:
| Signal.type | block_type | long_cond | short_cond |
|-------------|-----------|-----------|-----------|
| CCI | cci | less_than oversold (-100) | greater_than overbought (100) |
| Williams_R | williams_r | less_than -80 | greater_than -20 |
| ADX | adx | greater_than 25 (filter) | greater_than 25 |
| ATR | atr | greater_than threshold | greater_than threshold |
| VWAP | vwap | price crossover indicator | price crossunder indicator |
| OBV | obv | greater_than 0 | less_than 0 |
| Bollinger | bollinger | price crossover lower | price crossunder upper |

**Категория C** — фильтры:
| Filter.type | block_type | activation |
|-------------|-----------|-----------|
| Volatility | atr_volatility | use_atr_volatility=True |
| Volume | volume_filter | use_volume_filter=True |
| Trend | two_mas | use_ma1_filter=True |
| ADX | adx | needs_condition: greater_than 25 |
| Time | — | SKIP (нет блока) |

**Критические детали реализации:**
- `and`/`or` блоки поддерживают 3 входа (порты a, b, c) — **не нужно цепочки**
- При >3 сигналах: and(and(a,b,c), d, e...) — рекурсивное объединение
- Param renames: `fast_period → ma1_length`, `slow_period → ma2_length` (Two MAs)
- Все `activation` флаги = False по умолчанию → без них блок всегда True (passthrough)
- Timeframe "Chart" → заменяется на `interval`

### Задача 2: Тесты ✅
**Файл:** `tests/test_graph_converter.py` — 26 тестов, все проходят

Покрытие: Category A (8 типов), Category B (5 типов), фильтры (5 типов), AND/OR (1/2/3/4+ сигналов), param renames, activation flags, integrity check соединений.

**Важная деталь:** and/or блоки создаются отдельно для long и short путей → при 3 сигналах = 2 and-блока (не 1).

### Задача 3: BLOCK_ACTIVATION_RULES в templates.py ✅
**Файл:** `backend/agents/prompts/templates.py` — добавлена секция в IMPORTANT RULES

Объясняет LLM что без activation флагов блок = passthrough (always True = нет фильтрации).

### Задача 4: BuildGraphNode ✅
**Файл:** `backend/agents/trading_strategy_graph.py`, класс `BuildGraphNode`

Вставлен между ConsensusNode и BacktestNode. Читает `state.get_result("select_best")["selected_strategy"]`, вызывает `StrategyDefToGraphConverter.convert()`, пишет `state.context["strategy_graph"]` и `state.context["graph_warnings"]`.

### Задача 5: BacktestNode._run_via_adapter ✅
**Файл:** `backend/agents/trading_strategy_graph.py`, метод `_run_via_adapter`

```python
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter
adapter = StrategyBuilderAdapter(strategy_graph)
signal_result = adapter.generate_signals(df)
# → FallbackEngineV4 → MetricsCalculator
```

Приоритет: если `strategy_graph` в context → adapter path (40+ блоков). Иначе → BacktestBridge fallback (6 типов).

### Задача 6: _save_to_db в MemoryUpdateNode ✅
**Файл:** `backend/agents/trading_strategy_graph.py`, метод `MemoryUpdateNode._save_to_db`

Синхронный метод (вызывается через `asyncio.to_thread`). Сохраняет в ORM:
```python
Strategy(
    strategy_type=StrategyType.BUILDER,
    status=StrategyStatus.DRAFT,
    is_builder_strategy=True,
    builder_graph=strategy_graph,
    builder_blocks=strategy_graph["blocks"],
    builder_connections=strategy_graph["connections"],
)
```
→ стратегия появляется в Strategy Builder UI.

### Задача 7: build_trading_strategy_graph() ✅
**Файл:** `backend/agents/trading_strategy_graph.py`, функция `build_trading_strategy_graph()`

Граф: `analyze_market → [debate] → generate → parse → select_best → build_graph → backtest → memory_update → report → END`

### Задача 8: API Endpoint ✅
**Файл:** `backend/api/routers/ai_strategy_generator.py`

```
POST /api/ai-strategy-generator/generate-and-build
```

Параметры: `symbol`, `timeframe`, `days`, `agents[]`, `run_backtest`, `run_debate`, `initial_capital`, `leverage`

Загрузка OHLCV: прямой SQL к `data.sqlite3` (таблица `bybit_kline_audit`, колонки `open_price/high_price/low_price/close_price`).

Ответ: `{strategy_name, strategy_graph, graph_warnings, backtest_metrics, saved_strategy_id, proposals_count, execution_path, errors}`

---

## Ключевые исправления от ТЗ v1 к v3

1. **Two MAs параметры:** `fast_period → ma1_length`, `slow_period → ma2_length` (не `ma1_period`)
2. **AgentState ключ:** `state.get_result("select_best")["selected_strategy"]` (не `["strategy"]`)
3. **Блоковый словарь:** уже существует в `templates.py` (STRATEGY_GENERATION_TEMPLATE) — добавлен только BLOCK_ACTIVATION_RULES
4. **Mode activation:** все universal блоки по умолчанию passthrough — MUST set activation flags
5. **and/or чейнинг:** блоки поддерживают порт `c` (3 входа без цепочки)
6. **Путь адаптера:** `backend/backtesting/strategy_builder/adapter.py` (не `strategy_builder_adapter.py`)

---

## Что НЕ реализовано (следующие шаги)

Из `docs/AGENT_STRATEGY_PIPELINE_ARCHITECTURE.md` (8-фазный пайплайн, дата 2026-01-29):
- **Фаза 6:** Optimization — агент запускает Optuna на сгенерированной стратегии
- **Фаза 7:** ML Validation
- **Итеративный цикл:** если бэктест провалился → агенты делают refinement → повтор (max 5 итераций)

Из `docs/ТЗ_ЭВОЛЮЦИЯ_ПАМЯТИ.md` (5 фаз, дата 2026-02-15):
- P1: Унификация `MemoryItem` / `PersistentMemoryItem` (разные форматы дат, нет embedding в SQLite)
- P2: MCP-инструменты памяти (агенты не могут напрямую читать/писать память)
- P3: Нормализатор тегов + авто-тегирование
- P4: Гибридный поиск BM25 + векторный
- P5: Интеграция памяти в делиберацию

Из `docs/AGENT_ECOSYSTEM_AUDIT.md` (GAP-анализ, дата 2026-02-11):
- `autonomous_workflow.py` — автономный workflow без участия пользователя
- `task_scheduler.py` — планировщик регулярных бэктестов
- `feedback_loop.py` — система оценки и самообучения
- Связь vector_store с таблицей `backtest_results` в БД

---

## Файлы изменённые сегодня (2026-03-20)

| Файл | Действие |
|------|---------|
| `backend/agents/integration/graph_converter.py` | СОЗДАН — StrategyDefToGraphConverter |
| `tests/test_graph_converter.py` | СОЗДАН — 26 тестов |
| `backend/agents/trading_strategy_graph.py` | ИЗМЕНЁН — BuildGraphNode, BacktestNode._run_via_adapter, MemoryUpdateNode._save_to_db |
| `backend/agents/prompts/templates.py` | ИЗМЕНЁН — BLOCK_ACTIVATION_RULES |
| `backend/api/routers/ai_strategy_generator.py` | ИЗМЕНЁН — GenerateAndBuildRequest, /generate-and-build endpoint |
| `tests/test_graph_converter.py` | ИСПРАВЛЕН — корректный подсчёт and-блоков (per direction) |

---

## Живые тесты агентов (из сессии)

**Файл:** `tests/test_agent_live.py` — 10/10 проходят

Исправления parser bugs обнаруженные при live тестах:
1. `ExitCondition.value = list` → берём `v[0]`
2. `ExitCondition.value = None` → возвращаем `0.0`
3. `ExitCondition.value = dict` → извлекаем первое числовое значение по ключам: `value/multiplier/percentage/pct/atr_multiplier`

**API ключи (.env):**
- `DEEPSEEK_API_KEY=<your-deepseek-api-key>`
- `PERPLEXITY_API_KEY=<your-perplexity-api-key>`
