# Cursor и GitHub Copilot: синхронизация правил и путей

Краткое сравнение фич, таблица путей и как поддерживать оба IDE в одном проекте.

## Сравнение функционала (2026)

| Функция | Cursor | GitHub Copilot |
|--------|--------|----------------|
| **Composer / Edits** | Composer (Cmd+I / Ctrl+I), multi-file | Edits mode, multi-file |
| **Agent mode** | Agent в Composer | Cloud Agent (Preview) |
| **Правила** | `.cursor/rules/*.mdc` (модульные, frontmatter) | `.github/copilot-instructions.md` (один файл, ~2 стр.), `.github/instructions/*.instructions.md` (path-specific) |
| **CLI** | Базовая интеграция в терминале | Copilot CLI с агентами (Explore, Task, Plan, Code-review) |
| **MCP** | Полная поддержка (`.cursor/mcp.json`) | В основном через CLI |
| **Контекст** | @Codebase, @Folder, @File, @Docs, @Web, @Git | Workspace, path-specific instructions |
| **Скорость / контекст** | Быстрее autocomplete, сильный контекст | Хороший контекст, лимит размера инструкций |

## Пути к правилам и инструкциям

### Единый источник для обоих: `.ai/`

| Источник (.ai/) | Cursor | Copilot |
|-----------------|--------|---------|
| `.ai/rules/*.md` | Копии в `.cursor/rules/*.md` | Объединение в `.github/copilot-instructions.md` |
| `.ai/path-specific/*.md` | `.cursor/rules/path-*.md` | `.github/instructions/<name>.instructions.md` (с `applyTo`) |
| `.ai/prompts/*.md` | — | `.github/prompts/<name>.prompt.md` |
| `.ai/context/*.md` | Ручное использование | Ручное использование |

### Только Cursor (не синхронизируется в Copilot)

| Путь | Назначение |
|------|------------|
| `.cursor/rules/*.mdc` | Правила с frontmatter (alwaysApply, globs): project.mdc, task-decomposition.mdc, planning.mdc, cursor-features.mdc и др. |
| `.cursor/commands/*.md` | Runbooks (analyze-task, safe-refactor) |
| `.cursor/plans/` | Планы задач |
| `.cursor/workflow_state.md` | Текущая фаза/задача |
| `PROJECT_JOURNAL.md` | Долгосрочная память между сессиями |

### Только Copilot

| Путь | Назначение |
|------|------------|
| `.github/copilot-instructions.md` | Главный файл инструкций (генерируется из `.ai/rules/`) |
| `.github/instructions/*.instructions.md` | Path-specific (генерируется из `.ai/path-specific/`) |
| `.github/prompts/*.prompt.md` | Промпты для чата (копии из `.ai/prompts/`) |

## Синхронизация

1. **Редактировать исходники** в `.ai/rules/`, `.ai/path-specific/`, `.ai/prompts/`.
2. **Запустить скрипт:**
   ```bash
   python scripts/sync-ai-rules.py
   # или
   python scripts/sync-ai-rules.py --copilot-only   # только .github/
   python scripts/sync-ai-rules.py --cursor-only    # только .cursor/rules/
   python scripts/sync-ai-rules.py --dry-run -v    # превью
   ```
3. **Cursor** дополнительно использует `.cursor/rules/*.mdc` — их нужно править вручную; в Copilot эквивалент только то, что попало из `.ai/` в `copilot-instructions.md`.

Подробнее: `.ai/README.md`.

## Фичи Copilot 2026 (кратко)

- **Copilot CLI** — агенты: Explore (анализ кода), Task (запуск тестов/сборок), Plan (планы с зависимостями), Code-review.
- **Copilot Workspace** — продолжение сессий с GitHub.com в VS Code, правки и отладка перед PR.
- **Cloud Agent** — фоновые задачи (рефакторинг, документация, multi-file).
- **Copilot Actions** в контекстном меню — комментарии, объяснения, оптимизации по правому клику.
- **Intent Detection** — подсказки при опечатках в поиске.

## Рекомендации

- Общие принципы, стиль кода, трекинг переменных, TradingView parity — хранить в `.ai/rules/` и синхронизировать в оба IDE.
- Специфику Cursor (Composer, Agent, @mentions, MCP, PROJECT_JOURNAL) — держать в `.cursor/rules/*.mdc` и не дублировать в Copilot, если не нужны там же.
- После изменений в `.ai/` всегда запускать `python scripts/sync-ai-rules.py`, при желании — добавить в pre-commit.
