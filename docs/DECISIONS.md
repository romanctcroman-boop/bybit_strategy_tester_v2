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
