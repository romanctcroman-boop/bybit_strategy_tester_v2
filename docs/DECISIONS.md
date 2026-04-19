# Design Decisions

> Журнал значимых архитектурных и технических решений проекта.
> Обновляется при изменении структуры, контрактов API или критичных правил.

---

## ADR-001: Пути и конфигурация

**Дата:** 2026-01-30
**Статус:** Принято

- Не хардкодить абсолютные пути вида `d:\bybit_strategy_tester_v2` в коде и тестах.
- Использовать:
    - `Path(__file__).resolve().parents[N]` для корня проекта/модуля;
    - `os.environ.get("DATABASE_PATH", str(ROOT / "data.sqlite3"))` для БД;
    - `os.environ.get("CACHE_DIR", ...)` для кэша.
- В скриптах: `sys.path.insert(0, str(ROOT))` вместо жёсткого пути к репозиторию.

**Ссылка:** `.cursor/rules/project.mdc`, `docs/CURSOR_RULES_ANALYSIS.md`.

---

## ADR-002: TradingView parity

**Дата:** (историческое)
**Статус:** Принято

- Комиссия **0.07%** используется для сравнения с TradingView.
- Эталон точности: FallbackEngineV4 (gold standard). FallbackEngineV2 deprecated, оставлен для parity тестов.
- Калибровка: `scripts/calibrate_166_metrics.py`, `scripts/compare_*`.

**Ссылка:** `.cursor/rules/backtesting.mdc`, `docs/architecture/ENGINE_PARITY.md`.

---

## ADR-003: Обработка исключений

**Дата:** 2026-01-30
**Статус:** Принято

- Не использовать `except Exception: pass` без логирования — это нарушает правила Cursor (code-standards.mdc, AGENTS.md).
- Использовать `except Exception as e:` и логировать: `logger.debug("...", exc_info=True)` или `logger.warning(...)`.
- Осознанные исключения (например, платформо-специфичный код в app.py для UTF-8) допускаются с комментарием и записью в этом документе.

**Ссылка:** `docs/CURSOR_RULES_ANALYSIS.md`, раздел 2.4.

---

## ADR-004: Документация для агентов

**Дата:** 2026-01-30
**Статус:** Принято

- Архитектура: основная документация в **docs/** и **docs/architecture/** (ENGINE_ARCHITECTURE.md, STRATEGY_BUILDER_ARCHITECTURE.md и т.д.).
- Для агентов: **.agent/docs/** содержит краткие ARCHITECTURE.md и DECISIONS.md со ссылками на docs/.
- Решения: фиксируются в **docs/DECISIONS.md** (этот файл).

**Ссылка:** AGENTS.md, `docs/CURSOR_RULES_ANALYSIS.md`.

---

## ADR-005: dev.ps1

**Дата:** 2026-01-30
**Статус:** Принято

- В корне проекта присутствует **dev.ps1** для Windows: команды `run`, `lint`, `format`, `test`, `test-cov`, `clean`, `mypy`, `help`.
- Внутри вызываются: `py -3.14 -m uvicorn ...`, `ruff check . --fix`, `ruff format .`, `pytest tests/ -v` и т.д.
- При отсутствии dev.ps1 допустимо вызывать эти команды напрямую (правила допускают оба варианта).

**Ссылка:** `.cursor/rules/project.mdc`, README.md.

---

## ADR-006: position_size — fraction vs percent

**Дата:** 2026-02-21
**Статус:** Принято

### Контекст

Параметр `position_size` используется в 12+ файлах. Frontend отображает его в **процентах** (0–100%), а backend — в **дробях** (0.0–1.0). Это создаёт потенциал для ошибок при передаче данных.

### Решение

- **Backend API** (`position_size` в BacktestConfig, BacktestInput, стратегиях): **всегда fraction** (0.01–1.0).
- **Frontend** (Properties Panel): показывает **проценты** (1–100%), конвертирует при отправке (`/ 100`) и при получении (`* 100`).
- **Конвертация** происходит ТОЛЬКО в `strategy_builder.js` (строка ~10199):

    ```js
    position_size: positionSizeType === "percent" ? positionSizeVal / 100 : positionSizeVal;
    ```

- Для `position_size_type = "fixed_amount"` значение передаётся как есть (например, 5000.0).
- Backend валидирует: `ge=0.01, le=1.0` для percent-mode.

### Affected files

| Слой      | Файл                              | Формат                                      |
| --------- | --------------------------------- | ------------------------------------------- |
| Frontend  | `strategy_builder.js`             | percent (0-100) → fraction при отправке     |
| Frontend  | `leverageManager.js`              | percent (0-100) → `/100` при расчёте margin |
| API       | `backtests.py`                    | fraction (0.01–1.0)                         |
| API       | `strategy_builder.py`             | fraction (0.01–1.0)                         |
| Engine    | `engine.py`, `fallback_*.py`      | fraction (0.01–1.0)                         |
| Optimizer | `utils.py`, `optuna_optimizer.py` | fraction                                    |

### Правило

> Никогда не передавать position_size в процентах через API. Конвертация — ответственность frontend.

**Ссылка:** CLAUDE.md §7 (Cross-cutting Parameters).

---

_При добавлении новых решений добавляйте секцию ADR-NNN с датой, статусом и ссылками._

---

## ADR-007: LightweightCharts — текущая версия и план миграции на v5

**Дата:** 2026-03-25
**Статус:** Принято (миграция запланирована)

### Контекст

Текущие продуктовые HTML-страницы используют LightweightCharts через CDN в разных версиях:

| Файл                    | Версия    | CDN      |
| ----------------------- | --------- | -------- |
| `trading.html`          | **4.2.0** | jsdelivr |
| `market-chart.html`     | **4.2.0** | jsdelivr |
| `backtest-results.html` | **4.2.0** | jsdelivr |
| `tick-chart.html`       | **4.1.0** | unpkg    |

### Известные особенности v4 (критичные для нас)

1. **`setData()` требует строго возрастающего порядка timestamps** (oldest first).
   API Bybit возвращает данные в обратном порядке (newest first) — **необходима сортировка перед `setData`**.
   Без сортировки — silent crash: `Error: Value is null` внутри `assertDefined` (минифицированный код).
   ✅ Исправлено в `trading.js` коммит `1a40a672` — `.sort((a,b) => ta - tb)` перед маппингом.

2. **Watermark** задаётся через `createChart({watermark: {...}})` — опция в v4.

3. **Маркеры** через `series.setMarkers([...])` — прямой метод серии.

### Breaking changes при миграции на v5.1

При обновлении на v5 потребуется:

```js
// v4 → v5: создание серий
chart.addCandlestickSeries()  →  chart.addSeries(CandlestickSeries)
chart.addHistogramSeries()    →  chart.addSeries(HistogramSeries)
chart.addLineSeries()         →  chart.addSeries(LineSeries)
chart.addAreaSeries()         →  chart.addSeries(AreaSeries)

// v4 → v5: маркеры
series.setMarkers([...])      →  createSeriesMarkers(series, [...])

// v4 → v5: watermark
createChart({watermark:{...}}) →  createTextWatermark(chart.panes()[0], {lines:[{text,...}]})
```

### Затронутые файлы для миграции

- `frontend/js/pages/trading.js` — `addCandlestickSeries`, `addHistogramSeries`
- `frontend/js/pages/market_chart.js` — `addCandlestickSeries`, `addHistogramSeries`
- `frontend/js/pages/backtest_results.js` — `addLineSeries`, `addAreaSeries`, маркеры
- `frontend/js/pages/tick_chart.js` — `addCandlestickSeries`

### Решение

**Не мигрировать сейчас** — v4 стабильна, breaking changes требуют рефакторинга 4+ файлов.
Мигрировать в отдельной задаче после выхода стабильного v5.x-патча.

**Правило (до миграции):** всегда сортировать данные ascending перед `setData`.

```js
// Обязательный паттерн для setData в v4 (и v5):
const sorted = [...data].sort((a, b) => a.open_time - b.open_time);
series.setData(sorted.map(k => ({time: Math.floor(k.open_time / 1000), ...})));
```

**Ссылка:** [v4→v5 migration guide](https://tradingview.github.io/lightweight-charts/docs/migrations/from-v4-to-v5), коммит `1a40a672`.

---



## ADR-008: Unified API-key resolution via APIKeyPoolManager

**Дата:** 2026-04-17
**Статус:** Принято

### Контекст

В слое AI-агентов (`backend/agents/trading_strategy_graph.py`) одновременно использовались два источника API-ключей:

1. `KeyManager.get_decrypted_key("ANTHROPIC_API_KEY")` — прямой lookup без health-tracking.
2. `APIKeyPoolManager` — health-tracking, ротация, cooldown — но только для Claude.

Perplexity ключ всегда шёл мимо pool → никакой rotation/rate-limit телеметрии → при 429 весь pipeline ложился.

### Решение

Введён единый резолвер `_LLMCallMixin._resolve_api_key(agent_type, fallback_name) → (api_key, pool_obj)`:

```python
@staticmethod
async def _resolve_api_key(agent_type, fallback_name):
    pool = APIKeyPoolManager()
    pool_obj = await pool.get_active_key(agent_type)       # health-tracking
    if pool_obj and pool_obj.key_name:
        return km.get_decrypted_key(pool_obj.key_name), pool_obj
    return km.get_decrypted_key(fallback_name), None       # fallback
```

Все 5 сайтов lookup'а (Perplexity + Claude в `_call_llm`, 2 в `GroundingNode`, 1 в `GenerateStrategiesNode`) мигрированы. Каждый `client.chat()` обёрнут в `try/except` с `pool.mark_success / mark_rate_limit / mark_auth_error / mark_error`.

### Последствия

- ✅ Единый контракт: pool → KeyManager → None (fail-safe chain).
- ✅ Health-tracking и ротация работают для всех провайдеров.
- ✅ `pool_obj` — opaque ручка, передаётся обратно для `mark_*` — никакой утечки имени ключа.
- ⚠️ `_resolve_api_key` теперь `async` — все call-сайты должны использовать `await`.

**Ссылка:** тесты `tests/backend/agents/test_integration_polish.py::TestResolveApiKeyPoolFirst`.

---


## ADR-009: SecurityOrchestrator как fail-closed gate в `_call_llm`

**Дата:** 2026-04-17
**Статус:** Принято

### Контекст

`PromptGuard` (regex) и `SemanticPromptGuard` (embedding) существовали как независимые компоненты — ни один не вызывался автоматически из pipeline. Вредоносный промпт мог пройти прямо в `client.chat()`, попасть в логи провайдера и увеличить биллинг.

`SecurityOrchestrator.analyze(prompt) → SecurityVerdict` уже существовал (собирает оба guard'а по WEIGHTED policy), но никогда не подключался.

### Решение

`_LLMCallMixin._call_llm()` теперь **первой строкой** запускает:

```python
verdict = get_security_orchestrator().analyze(prompt)
if not verdict.is_safe:
    state.add_error("_call_llm", RuntimeError(f"blocked: {verdict.blocked_by}"))
    return None                                            # fail-closed
```

При ошибке самого orchestrator'а (импорт, инициализация guard'ов) — **fail-open** с `logger.debug`: безопасность не должна ломать pipeline. Введён singleton `get_security_orchestrator()` — guards инициализируются 1 раз на процесс (semantic guard тянет embeddings).

### Последствия

- ✅ 100 % промптов проходят двухслойную проверку.
- ✅ Блокировка записывается в `state.errors` для audit trail.
- ✅ Fail-closed: при срабатывании — `return None`, провайдер НЕ вызывается, токены не тратятся.
- ⚠️ При ложном срабатывании (false positive) — ответ будет `None`; вызывающий код уже обрабатывает `None` как "LLM unavailable".

**Ссылка:** `backend/agents/security/security_orchestrator.py:214`, тесты `TestLLMCallSecurityGate`.

---


## ADR-010: Логический split `trading_strategy_graph.py` через `nodes/` package

**Дата:** 2026-04-17
**Статус:** Принято (первый этап)

### Контекст

`backend/agents/trading_strategy_graph.py` разросся до **4569 строк**, содержит **22 Node-класса** + mixin + глобальный кэш. Навигация затруднена, архитектурные границы (market / generation / backtest / refine / control) не видны.

Физический перенос классов ломает 1771+ импорт в тестах и внешних модулях → нужен безопасный переходный этап.

### Решение

Создан пакет `backend/agents/nodes/` с 6 тонкими **re-export** модулями:

| Модуль        | Node-классы                                                                                                      |
| ------------- | ---------------------------------------------------------------------------------------------------------------- |
| `llm`         | `_LLMCallMixin` + публичный alias `LLMCallMixin`                                                                 |
| `market`      | `AnalyzeMarketNode`, `RegimeClassifierNode`, `GroundingNode`, `MemoryRecallNode`                                 |
| `generation`  | `GenerateStrategiesNode`, `ParseResponsesNode`, `ConsensusNode`, `BuildGraphNode`                                |
| `backtest`    | `BacktestNode`, `BacktestAnalysisNode`, `MLValidationNode`                                                       |
| `refine`      | `RefinementNode`, `OptimizationNode`, `OptimizationAnalysisNode`, `A2AParamRangeNode`, `WalkForwardValidationNode`, `AnalysisDebateNode` |
| `control`     | `HITLCheckNode`, `PostRunReflectionNode`, `MemoryUpdateNode`                                                     |

### Последствия

- ✅ Новый код пишет `from backend.agents.nodes.market import GroundingNode` — canonical.
- ✅ Старые импорты `from backend.agents.trading_strategy_graph import ...` продолжают работать.
- ✅ Архитектурные границы видны в tree view и в тестах.
- 🔄 Этап 2 (физический перенос) — отдельный PR, выполняется инкрементально (класс за классом с sed-обновлением импортов).

**Ссылка:** `backend/agents/nodes/__init__.py`, тесты `TestNodesPackageReExports`.

---


## ADR-011: RiskVetoGuard как hard-safety gate в paper trading

**Дата:** 2026-04-17
**Статус:** Принято

### Контекст

`RiskVetoGuard` (drawdown / daily-loss / max-positions / agreement / emergency-stop / manual-block) подключён в `BacktestAnalysisNode` (аудит консенсуса), но **не** в `AgentPaperTrader`. При этом paper trading — это ближайший к production слой и должен иметь identical safety-контракт.

### Решение

`AgentPaperTrader._execute_paper_signal()` прогоняет каждый `buy`/`sell` через `get_risk_veto_guard().check(...)` ДО открытия позиции. При `is_vetoed=True`:

1. WARNING в лог с `session_id`, `signal`, `reasons`.
2. `session.veto_log.append(decision.to_dict())` — audit trail для UI.
3. `return` — позиция НЕ создаётся.

Сигнал `close` намеренно **не** проходит через guard — закрытие позиций не должно быть заблокировано ни при каких обстоятельствах. При ошибке guard'а — fail-open с `logger.error`: защитный код никогда не ломает торговую логику.

### Последствия

- ✅ Paper trading = live trading по safety-контракту.
- ✅ `session.veto_log` — прозрачный audit trail.
- ✅ Close-сигналы не блокируются — избежать "стрельбы в ногу" при срабатывании на выходе.
- ⚠️ `session.veto_log` — динамический атрибут (не в dataclass), намеренно — чтобы не ломать legacy сериализацию `to_dict()`.

**Ссылка:** `backend/agents/trading/paper_trader.py:404-472`, тесты `TestPaperTraderRiskVeto`.

---
