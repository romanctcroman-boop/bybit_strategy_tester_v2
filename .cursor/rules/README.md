# Cursor Rules — Bybit Strategy Tester v2

Правила в `.cursor/rules/*.mdc` используются **AI в Cursor** (чаты, Cmd+K, Agent). Это и есть «скиллы» агента в Cursor.

## Автономность (alwaysApply)

| Файл | Назначение |
|------|------------|
| `autonomy.mdc` | Что выполнять без запроса / спрашивать / не делать (терминал, git, правки кода). |
| `enhanced-autonomy.mdc` | Проактивность: авто-фикс линтинга и тестов, рефакторинг, восстановление после ошибок. |
| `cursor-features.mdc` | Когда использовать Composer (Cmd+I), Agent, @mentions (@Codebase/@Folder/@File/@Docs/@Web/@Git), Privacy/.cursorignore, MCP, выбор модели, терминал, изображения. |

## Декомпозиция и контекст (alwaysApply)

| Файл | Назначение |
|------|------------|
| `task-decomposition.mdc` | Фазы АНАЛИЗ → ПЛАН → ВЫПОЛНЕНИЕ → ВАЛИДАЦИЯ; отслеживание переменных и зависимостей; Grep/SemanticSearch/Read; ссылка на PROJECT_JOURNAL. |
| `task-breakdown.mdc` | Когда задача считается сложной (>3 файлов, >50 строк, новые зависимости, API); алгоритм разбиения на подзадачи и карта переменных. |
| `project-journal.mdc` | Работа с PROJECT_JOURNAL.md: чтение в начале сессии, обновление в конце (переменные, решения, баги, TODO). |
| `planning.mdc` | Когда запрашивать одобрение плана; сохранение планов в .cursor/plans/; исследование через LS/Grep/SemanticSearch. |

## Скиллы по доменам (globs / по описанию)

| Файл | Когда подключается | Назначение |
|------|--------------------|------------|
| `project.mdc` | **Всегда** (alwaysApply) | Архитектура, движки бэктеста, TradingView parity, пути, `dev.ps1`. |
| `backtesting.mdc` | `backend/backtesting/**`, `scripts/*calibrate*`, `*backtest*`, `*engine*`, `compare_*` | Выбор движка, 0.07% комиссия, калибровка, VectorBT только для оптимизации. |
| `trading-context.mdc` | `backend/backtesting/**`, `backend/services/**`, `backend/core/metrics_calculator.py`, `backend/api/**` | Критические переменные (strategy_params, initial_capital, commission), Bybit API, walk-forward, валидация. |
| `code-standards.mdc` | `**/*.py` | Python 3.14, ruff, pytest, **не хардкодить** `d:\`, `except Exception`, extended_metrics. |
| `backend-api.mdc` | `backend/api/**` | FastAPI, роутеры, `json.dumps` в ответах, один `security`, CONFIG в lifespan. |
| `cursor-copilot-sync.mdc` | по запросу | Таблица путей Cursor vs Copilot; синхронизация через .ai/ и scripts/sync-ai-rules.py; см. docs/ai/CURSOR_COPILOT_SYNC.md. |

## Файлы вне rules/

| Путь | Назначение |
|------|------------|
| **PROJECT_JOURNAL.md** (корень) | Долгосрочная память между сессиями: контекст, переменные, решения, баги, TODO. Правила: `project-journal.mdc`. |
| **.cursor/workflow_state.md** | Опционально: текущая фаза (ANALYZE/PLAN/EXECUTE/VALIDATE), подзадачи, переменные, лог действий. |
| **.cursor/plans/** | Сохранённые планы сложных задач (один .md на задачу). Шаблон: `.cursor/commands/analyze-task.md`. |
| **.cursor/commands/** | Runbooks для агента: `analyze-task.md` (глубокий анализ), `safe-refactor.md` (безопасный рефакторинг). Cursor не загружает их автоматически; правила ссылаются на них. |

## Cursor и GitHub Copilot

Правила можно синхронизировать с GitHub Copilot через единый источник `.ai/` и скрипт `scripts/sync-ai-rules.py`.

| Что | Cursor | Copilot |
|-----|--------|---------|
| Основные правила | `.cursor/rules/*.mdc` и `.cursor/rules/*.md` (из .ai/) | `.github/copilot-instructions.md` (из .ai/rules/) |
| Path-specific | `.cursor/rules/path-*.md` или globs в .mdc | `.github/instructions/*.instructions.md` |
| Промпты | `.cursor/commands/` | `.github/prompts/*.prompt.md` |
| Синхронизация | `python scripts/sync-ai-rules.py` | тот же скрипт генерирует .github/ |

- **Правило с таблицей путей:** `cursor-copilot-sync.mdc`.
- **Подробно:** `.ai/README.md`, `docs/ai/CURSOR_COPILOT_SYNC.md` (сравнение фич, пути, Copilot 2026).

## Дополнительно

- **AGENTS.MD** — полные правила проекта. Чтобы Cursor их подхватывал, добавьте в  
  **Cursor → Settings → General → Rules for AI** путь `AGENTS.MD` или его содержимое.
- **.agent/** — конфиги и правила под другие инструменты / модел-специфичные настройки;  
  Cursor их **не** загружает автоматически. Папка `.agent/skills/` в `.gitignore` — скиллы для других агент-систем;  
  в Cursor роль «скиллов» выполняют правила в `.cursor/rules/*.mdc`.
- **MCP** — при необходимости контекста из внешних систем (файлы, браузер, Docker и т.д.) используйте доступные MCP-серверы (см. `.cursor/mcp.json`).
- **.cursorignore** (в корне проекта) — для Privacy Mode: не отправлять в AI секреты и чувствительные данные. Рекомендуемые записи: `.env`, `.env.*`, `*.key`, `*_secret*`, `backend/config/encrypted_secrets.json`; при необходимости — `logs/`, `backtest_results/`. Подробнее: `cursor-features.mdc`.

## Как добавить правило

1. Создать `.cursor/rules/имя-правила.mdc`.
2. В начале файла — YAML frontmatter:
   ```yaml
   ---
   description: Краткое описание, когда правило применяется
   alwaysApply: true   # или false
   globs: "**/*.py"   # опционально: только для этих файлов
   ---
   ```
3. Дальше — текст правила в Markdown.
