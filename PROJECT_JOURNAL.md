# PROJECT JOURNAL: Bybit Strategy Tester v2

## Метаинформация

- **Создан:** 2026-01-30
- **Последнее обновление:** 2026-01-30
- **Статус проекта:** В разработке
- **Цель:** Бэктестер торговых стратегий Bybit с движками Fallback/Numba/GPU, 166 метрик, TradingView parity.

---

## Как использовать

- **В начале сессии:** прочитать журнал, восстановить контекст, проверить таблицу переменных и TODO.
- **В конце сессии:** обновить таблицу переменных, записать решения и баги, оставить TODO для следующей сессии.
- Правила работы с журналом: `.cursor/rules/project-journal.mdc`.

---

## СЕССИЯ: 2026-01-30 (MCP DeepSeek)

### Цели сессии

- [x] MCP DeepSeek Node.js — создан `mcp-deepseek/`, 2 инструмента (deepseek_chat, deepseek_code_completion), ESM + SDK 0.6, запись в `.cursor/mcp.json`.
- [x] deepseek-node в Cursor — «2 tools enabled», без ошибки (запуск через `cmd /c cd /d ...\mcp-deepseek && node server.js`).
- [x] Docker MCP — в `.cursor/mcp.json` переключён запуск на `npx` без `cmd` (как у filesystem); при необходимости отключить в Settings, если ошибка остаётся.

### Следующая сессия

**TODO для AI:** при работе с DeepSeek через MCP задавать `DEEPSEEK_API_KEY` в env или в `mcp-deepseek/.env`.

---

## СЕССИЯ: [дата время]

### Цели сессии

- [ ] …
- [ ] …

### Контекст для AI

**Архитектура проекта:**

- Бэктест: `backend/backtesting/` (engine.py, engine_selector.py, engines/, interfaces.py)
- Метрики: `backend/core/metrics_calculator.py` (166 метрик)
- API: `backend/api/`, `backend/services/adapters/bybit.py`
- Фронт: `frontend/` (HTML/JS/CSS)
- Утилиты: `scripts/`, тесты: `tests/`

**Критические переменные (отслеживание):**

| Переменная        | Файл:строка      | Тип   | Зависимости        | Статус   |
|-------------------|------------------|-------|--------------------|----------|
| strategy_params   | …                | dict  | get_signals, run   | Active   |
| initial_capital   | …                | float | BacktestEngine     | Active   |
| commission        | …                | float | 0.07% для TV parity| Не менять |

**Активные зависимости:**

- BacktestEngine → StrategyExecutor, DataLoader, ResultsAnalyzer
- (дополнить по текущей задаче)

### Решения и обоснования

- **РЕШЕНИЕ:** …
- **ОБОСНОВАНИЕ:** …
- **АЛЬТЕРНАТИВЫ:** …
- **РЕЗУЛЬТАТ:** …

### Баги и решения

- **Проблема:** …
- **Решение:** …
- **Урок:** …

### Следующая сессия

**TODO для AI:**

1. Прочитать этот журнал полностью.
2. Проверить статус переменных в таблице.
3. Продолжить с точки остановки.
4. Обновить журнал с новыми решениями.

---

## ИСТОРИЯ ИЗМЕНЕНИЙ

- 2026-01-30: MCP DeepSeek Node (mcp-deepseek/, deepseek-node в Cursor), правка Docker MCP (npx без cmd), запись в CHANGELOG.
- 2026-01-30: Создан PROJECT_JOURNAL; добавлены правила декомпозиции и task-decomposition/task-breakdown.
