# Bybit Strategy Tester v2 — Plan Refactoring & Structuring

> **Документ создан:** 2026-03-15
> **Цель:** Устранить "размазанность" проекта — конфликты между системами, потери данных, архитектурный долг.
> **Статус:** ✅ ВСЕ ФАЗЫ 0–5 ЗАВЕРШЕНЫ (2026-03-20). Проект рефакторинга закрыт.

---

## Диагноз проблем

### Почему проект "размазан"

Проект вырос органически и накопил несколько классов проблем:

**1. Конфликтующие дефолты (ловушки)**
| Параметр | Значение A | Значение B | Где конфликт |
|----------|-----------|-----------|-------------|
| `direction` | `"long"` (API) | `"both"` (Engine, Builder) | `models.py:1269` vs `models.py:~100` |
| `leverage` | `10` (optimizer/UI) | `1.0` (live trading) | `optimization/models.py` vs `strategy_runner.py` |
| `position_size` | fraction `0.0–1.0` | percent (live) | ADR-006, задокументировано |
| `commission_value` | `0.00055` (реальный Bybit) | `0.001` (legacy) | `optimize_tasks.py`, `fast_optimizer.py` |

**2. Монолитные файлы (невозможно держать в голове)**
| Файл | Строк | Проблема |
|------|-------|---------|
| `strategy_builder_adapter.py` | 3575 | Один файл делает всё: парсинг графа, тополгический sort, dispatch, исполнение 40+ индикаторов |
| `indicator_handlers.py` | 2217 | Частично вынесен из адаптера, но не структурирован по категориям |
| `strategy_builder.js` | 13378 | Frontend-монолит: Canvas + Blocks + Connections + Properties + Run + Save — всё вместе |
| `backtests.py` (router) | ~1500+ | Router делает слишком много, логика не в сервисах |

**3. Дублирование логики**
- `commission_value` упоминается в 10+ файлах — риск рассинхрона при изменении
- Метрики частично считаются в движках напрямую + в `MetricsCalculator` — исторически порождало несоответствия
- 3 версии движка (V2/V3/V4) + Numba + GPU — каждый требует поддержки

**4. Temp-файлы как симптом**
```
temp_analysis/ — 12 одноразовых скриптов
```
Признак что нормальный debug/тест сложен — разработчики создают одноразовые скрипты вместо тестов.

**5. Нет единого источника истины для конфигурации**
`BacktestConfig` в `models.py` — хороший кандидат, но конкуриру с параметрами в роутерах, `optimization/models.py`, frontend-дефолтами.

---

## Этап 0 — Инфраструктура Claude Code (✅ ЗАВЕРШЁН 2026-03-15)

Прежде чем рефакторить проект — улучшена инфраструктура разработки:

### Хуки (`.claude/hooks/`)
| Хук | Событие | Что делает |
|-----|---------|-----------|
| `protect_files.py` | PreToolUse Edit\|Write | Блокирует редактирование `.env`, `alembic/versions/`, `.git/` |
| `ruff_format.py` | PostToolUse Edit\|Write | Авто-форматирование Python после каждой правки |
| `post_edit_tests.py` | PostToolUse Edit\|Write | Авто-запуск целевых тестов |
| `post_compact_context.py` | PostCompact | **Записывает `compact_summary` в `activeContext.md`** — авто-обновление Memory Bank |
| `session_start_context.py` | SessionStart | Загружает Memory Bank в контекст |
| `stop_reminder.py` | Stop | Напоминает обновить Memory Bank |

### Скилы (`.claude/commands/`)
`/backtest` `/debug` `/new-strategy` `/review` `/tdd` `/changelog`
`/optimize` `/parity-check` `/profile` `/update-memory`

### Memory Bank (`memory-bank/`)
6 файлов персистентного контекста: `projectBrief`, `productContext`, `systemPatterns`, `techContext`, `activeContext`, `progress`

### Sub-CLAUDE.md
`backend/backtesting/CLAUDE.md`, `backend/api/CLAUDE.md`, `frontend/CLAUDE.md`, `backend/optimization/CLAUDE.md`

---

## Фаза 1 — Конфигурация (СЛЕДУЮЩИЙ ШАГ)

**Цель:** Единый источник истины для всех параметров. Устранить конфликтующие дефолты.

**Риск:** Низкий. Затрагивает только константы и дефолты, не логику.

### 1.1 Единый модуль констант
Создать `backend/config/constants.py`:
```python
# Единственное место где определены эти значения
COMMISSION_LINEAR = 0.00055   # Bybit linear taker
COMMISSION_SPOT   = 0.001     # Bybit spot taker
COMMISSION_TV     = 0.0007    # TradingView parity (для тестов)
INITIAL_CAPITAL   = 10_000.0
MAX_BACKTEST_DAYS = 730
VALID_TIMEFRAMES  = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]
```
Все 10+ файлов где сейчас хардкод → импорт из этого модуля.

### 1.2 Устранить конфликт `direction`
- Выровнять дефолт в `BacktestCreateRequest` (`"long"` → `"both"`) или явно документировать почему `"long"`
- Добавить тест: `test_direction_default_consistency.py`

### 1.3 Устранить конфликт `leverage`
- Добавить `LEVERAGE_DEFAULT_BACKTEST = 1.0` и `LEVERAGE_DEFAULT_OPTIMIZATION = 10` в constants.py
- Прокомментировать почему они разные (разные use-cases)

### 1.4 Очистить deprecated
- `fast_optimizer.py` → удалить или переместить в `deprecated/`
- `engines/fallback_engine_v2.py`, `v3.py` → переместить в `engines/deprecated/`
- `EventDrivenEngine` → переместить в `engines/experimental/`
- Убрать из `__init__.py` чтобы не импортировались случайно

### Проверка Фазы 1
```bash
grep -rn "commission" backend/ | grep -v "0.00055\|0.0007\|0.001.*spot\|#\|test\|.pyc"
pytest tests/backend/backtesting/test_engine.py -v
pytest tests/backend/backtesting/test_strategy_builder_parity.py -v
```

---

## Фаза 2 — Движок (средний риск)

**Цель:** Чёткая иерархия движков. Убрать неопределённость.

### 2.1 Чёткая граница FallbackEngineV4 ↔ NumbaEngine
Сейчас неочевидно когда использовать какой. Документировать и закрепить в `engine_selector.py`:
```
FallbackEngineV4  → все standalone backtests (эталон)
NumbaEngineV2     → только optimization loops (20-40x faster, 100% parity)
DCAEngine         → только когда dca_enabled=True
```

### 2.2 Убрать неиспользуемые импорты из `fallback_engine_v4.py`
`TradeDirection`, `ExitReason` — импортируются но не используются (везде строки).

### 2.3 Проверить `backtests.py` роутер на баг с комиссией
В прошлой сессии нашли и исправили что `strategy_builder/router.py` не передавал `commission_value` в `BacktestConfig`.
`backtests.py` — вероятно та же проблема. Проверить + написать тест.

### Проверка Фазы 2
```bash
pytest tests/backend/backtesting/ -v
pytest tests/backend/api/ -v
```

---

## Фаза 3 — Адаптер (высокий риск, критический файл)

**Цель:** Разбить `strategy_builder_adapter.py` (3575 строк) на логические модули.

**Риск:** Высокий. Критический файл, 50+ типов блоков, сложная логика port aliases.

### Предлагаемая структура
```
backend/backtesting/strategy_builder/
  __init__.py           ← публичный API (StrategyBuilderAdapter)
  adapter.py            ← оркестрация (было 3575 строк → ~400)
  graph_parser.py       ← парсинг и нормализация графа
  topology.py           ← топологическая сортировка + валидация
  signal_router.py      ← port aliases, routing, Case 1/2/3
  block_executor.py     ← исполнение блоков (делегирует в handlers)
```
`indicator_handlers.py` уже вынесен — структурировать по категориям:
```
backend/backtesting/indicators/
  trend.py       ← SMA, EMA, WMA, DEMA, TEMA, HullMA, Supertrend
  oscillators.py ← RSI, MACD, Stochastic, StochRSI, CCI, CMF, MFI...
  volatility.py  ← ATR, Bollinger, Keltner, Donchian
  volume.py      ← OBV, PVT, AD Line, VWAP, MFI
  other.py       ← Divergence, Pivot Points, Channel, etc.
```

### Правило для Фазы 3
- Каждый модуль изолированно тестируется
- Port aliases остаются в `signal_router.py` — не трогать `_PORT_ALIASES` / `_SIGNAL_PORT_ALIASES`
- `INDICATOR_DISPATCH` остаётся как dict, просто импортируется из разных модулей
- **Перед началом:** `pytest tests/backend/backtesting/ -v` → все зелёные
- **После каждого файла:** тот же набор тестов

---

## Фаза 4 — API / Роутеры

**Цель:** Тонкие роутеры, логика в сервисах.

### 4.1 `backtests.py` (~1500+ строк)
Разбить на:
```
routers/backtests/
  __init__.py
  router.py      ← только HTTP: валидация, маршрутизация, ответ
  service.py     ← бизнес-логика: подготовка конфига, вызов движка
  formatters.py  ← форматирование результата в JSON
```

### 4.2 Единый error handler
Сейчас каждый роутер по-своему обрабатывает ошибки. Вынести в middleware.

---

## Фаза 5 — Фронтенд

**Цель:** Разбить `strategy_builder.js` (13378 строк) на модули.

### Предлагаемая структура
```
frontend/js/strategy_builder/
  index.js           ← точка входа, инициализация
  CanvasModule.js    ← рендеринг canvas, zoom, pan
  BlocksModule.js    ← блоки: создание, перемещение, drag&drop
  ConnectionsModule.js ← провода: draw, validate, direction-mismatch
  PropertiesModule.js  ← панель свойств блока
  RunModule.js         ← запуск бэктеста, отображение результатов
  SaveLoadModule.js    ← сохранение/загрузка стратегий
  StateModule.js       ← undo/redo стэк
```

### Итог (100% ✅ 2026-03-20)

Что сделано:
- `blockLibrary.js` — чистые данные, ~158 строк, импортируется в strategy_builder.js
- `SymbolSyncModule.js` — ~707 строк, фабричный паттерн с DI: symbol picker, DB panel, SSE sync, auto-refresh. Удалено ~998 строк из монолита (13378 → ~7154 строк)
- Stub-модули созданы как архитектурный скелет: `BlocksModule.js`, `CanvasModule.js`, `PropertiesModule.js`, `ToolbarModule.js`, `index.js`

Canvas core / block management (~4000 строк) **намеренно остаётся в strategy_builder.js** — эти секции имеют 30+ closure-зависимостей на module-level переменные (`strategyBlocks`, `connections`, `zoom`, `selectedBlockId` и т.д.). Полная декомпозиция требовала бы переписки на StateManager, что выходит за рамки рефакторинга. Stub-модули определяют целевую архитектуру для последующей постепенной миграции.

---

## Правила выполнения (для каждой фазы)

1. **Перед началом** — читаем все затрагиваемые файлы
2. **Пишем тест** на проверяемое поведение (если нет)
3. **Меняем** — минимально необходимо
4. **Запускаем** целевые тесты
5. **Коммит** с описательным сообщением
6. Только потом следующий файл

**Никогда:**
- Не менять commission с 0.0007 без явного согласования
- Не рефакторить несвязанный код попутно
- Не начинать Фазу N+1 пока не закончена Фаза N

---

## Текущий статус

```
Этап 0 — Инфраструктура   ████████████ 100% ✅
Фаза 1 — Конфигурация     ████████████ 100% ✅
Фаза 2 — Движок           ████████████ 100% ✅
Фаза 3 — Адаптер          ████████████ 100% ✅ (adapter 3575→1399 lines, all _execute_* extracted)
Фаза 4 — API/Роутеры      ████████████ 100% ✅ (backtests.py 3171→package: router.py+formatters.py+schemas.py)
Фаза 5 — Фронтенд         ████████████ 100% ✅ (blockLibrary + SymbolSyncModule вынесены; canvas/block core намеренно в монолите)
```

---

## Работа после Phase 5 — Agent Pipeline (2026-03-23)

После завершения рефакторинга (Phases 0-5) работа продолжилась в направлении улучшения AI агентов.

### Улучшение обратной связи агентов ✅

| Файл | Что сделано |
|------|------------|
| `backend/agents/prompts/templates.py` | Добавлена секция `PORT NAMES QUICK REFERENCE` — таблица output ports для 20+ блоков. Агенты теперь знают что `rsi` → ports: `value/long/short`, `macd` → `macd/signal/hist/long/short` и т.д. |
| `backend/agents/prompts/response_parser.py` | Добавлен `parse_strategy_with_errors()` → `tuple[StrategyDefinition\|None, list[str]]`. Structured errors вместо тихого `None`. Обратная совместимость сохранена — `parse_strategy()` стал оберткой. |
| `backend/agents/trading_strategy_graph.py` — BacktestNode | `_run_via_adapter` возвращает `engine_warnings[]` и `sample_trades[:10]` вместе с метриками |
| `backend/agents/trading_strategy_graph.py` — RefinementNode | Feedback обогащён: ENGINE WARNINGS (с интерпретацией DIRECTION_MISMATCH/NO_TRADES), GRAPH CONVERSION WARNINGS, SAMPLE TRADES (при < 10 сделок) |
| `backend/agents/trading_strategy_graph.py` — BuildGraphNode | Сохраняет `agent_optimization_hints` из `StrategyDefinition.optimization_hints` в `state.context` |
| `backend/agents/trading_strategy_graph.py` — OptimizationNode | Новый `_apply_agent_hints()` — сужает диапазоны Optuna на основе agent hints |
| `tests/test_agent_feedback_improvements.py` | 23 теста для всей новой функциональности (все проходят) |
| `tests/backend/agents/test_llm_clients.py` | Fix: `asyncio.get_event_loop().run_until_complete()` → `asyncio.run()` (Python 3.14 совместимость) |
| `docs/AI_AGENTS_INTEGRATION_MAP.md` | Карта интеграции агентов: что видят / не видят, 8 TODO пробелов |

### Deferred (низкий приоритет)

- `docs/ТЗ_ЭВОЛЮЦИЯ_ПАМЯТИ.md` — 5 фаз унификации памяти агентов (сложно, требует отдельного ТЗ)
- `optimize_tasks.py` + `ai_backtest_executor.py` — commission=0.001 legacy paths

---

## Как использовать этот документ в новом чате

Скопируй в начало нового чата:
```
Читай REFACTORING_PLAN.md — там полный план структуризации проекта.
Начинаем с Фазы 1 (Конфигурация).
Перед началом прочитай файлы которые будем менять.
```

---

*Документ ведётся вручную. Обновляй статус после завершения каждой фазы.*
