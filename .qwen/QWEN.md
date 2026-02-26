# Qwen Code Configuration — Bybit Strategy Tester v2

> **Назначение:** Конфигурация AI-ассистента Qwen для эффективной работы с проектом.
> **Версия:** 1.0 (2026-02-26)
> **На основе анализа:** Claude, Copilot, Cursor, Gemini skills

---

## 📚 Skills Configuration

### Available Skills

Qwen имеет доступ к следующим специализированным навыкам:

| Skill | Директория | Назначение |
|-------|------------|------------|
| **Base Skills** | `.qwen/skills/SKILL.md` | Базовые настройки проекта |
| **Code Development** | `.qwen/skills/code-development/` | Написание нового кода |
| **Safe Refactoring** | `.qwen/skills/safe-refactoring/` | Безопасный рефакторинг |
| **Debugging** | `.qwen/skills/debugging/` | Отладка и исправление багов |
| **Test Generation** | `.qwen/skills/test-generation/` | Написание тестов |
| **Documentation** | `.qwen/skills/documentation/` | Генерация документации |

### Как использовать skills

При запросе задачи Qwen автоматически выбирает подходящий skill:

```
Задача → Выбор skill → Применение паттернов → Выполнение
```

**Примеры:**

| Задача | Используемый skill |
|--------|-------------------|
| "Добавь новый API endpoint" | `code-development` |
| "Улучши структуру этого файла" | `safe-refactoring` |
| "Найди баг в расчёте метрик" | `debugging` |
| "Напиши тесты для engine" | `test-generation` |
| "Задокументируй стратегию" | `documentation` |

---

## 🎯 Критические правила

### 1. Commission Rate = 0.0007 (0.07%)

```python
# NEVER change without explicit approval
commission_rate = 0.0007  # TradingView parity — 10+ files depend on this
```

### 2. Engine Selection

```python
# FallbackEngineV4 — gold standard for single backtests
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4

# NumbaEngineV2 — for optimization (20-40x faster)
from backend.backtesting.numba_engine import NumbaEngineV2
```

### 3. Data Retention

```python
# Import from here — don't hardcode
from backend.config.database_policy import DATA_START_DATE  # 2025-01-01
RETENTION_YEARS = 2
```

### 4. High-Risk Variables

**Всегда делать grep перед изменением:**

```bash
grep -rn "commission_rate" backend/ frontend/
grep -rn "strategy_params" backend/ frontend/
grep -rn "initial_capital" backend/ frontend/
```

---

## 📖 Workflow

### Для простых задач (< 15 минут)

1. Выполнить напрямую
2. Запустить тесты: `pytest tests/ -v`
3. Проверить линтинг: `ruff check . --fix && ruff format .`
4. Обновить `CHANGELOG.md`
5. Сообщить о завершении

### Для сложных задач (> 15 минут)

1. **Анализ:** Прочитать受影响нные файлы
2. **План:** Создать план выполнения
3. **Одобрение:** Запросить одобрение плана
4. **Выполнение:** Делать по одному атомарному изменению
5. **Верификация:** Тесты после каждого изменения
6. **Документирование:** Обновить документацию

---

## 🧪 Development Commands

```powershell
# Start server
.\dev.ps1 run
# or
py -3.14 -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# Tests
pytest tests/ -v                     # All tests
pytest tests/ -v -m "not slow"       # Fast tests only
pytest tests/ --cov=backend          # With coverage

# Linting
ruff check . --fix
ruff format .

# Database migrations
alembic upgrade head
```

---

## 📂 Project Structure

```
d:/bybit_strategy_tester_v2/
├── .qwen/                    # Qwen configuration
│   └── skills/               # Specialized skills
├── backend/
│   ├── backtesting/          # Core: engine, strategies, adapter
│   ├── api/routers/          # 70+ API routers
│   ├── services/             # Services: data, risk, live trading
│   ├── optimization/         # Optuna, Ray, scoring
│   ├── core/                 # MetricsCalculator, config
│   ├── trading/              # Live trading execution
│   └── agents/               # AI agents
├── frontend/
│   ├── strategy-builder.html # Main UI
│   └── js/pages/             # Frontend logic
├── tests/                    # 214 test files
└── docs/                     # Documentation
```

---

## 🔧 Tool Usage

### File Operations

- **Read:** `read_file` — чтение файлов
- **Write:** `write_file` — создание/замена файлов
- **Edit:** `edit` — точечные изменения
- **Glob:** `glob` — поиск по паттернам
- **Grep:** `grep_search` — поиск по содержимому

### Code Operations

- **Task:** `task` — делегирование специализированным агентам
- **Run:** `run_shell_command` — выполнение команд (с осторожностью)

### Web Operations

- **Search:** `web_search` — поиск актуальной информации
- **Fetch:** `web_fetch` — получение контента с URL

---

## ⚠️ Restrictions

### Never Auto-Execute

- `git push` (especially to main)
- Database migrations without approval
- Installing new dependencies
- Modifying security-critical code

### Never Do

- Change `commission_rate` from `0.0007` without approval
- Use `FallbackEngineV2/V3` for new code
- Hardcode `d:\...` paths or API keys
- Use Bash (unreliable on Windows) — use tools instead
- Create new files when editing existing ones suffices
- Add comments to code you didn't change

---

## 📝 Documentation Standards

### Update After Changes

| Change Type | Update |
|-------------|--------|
| New feature | `CHANGELOG.md`, API docs |
| Structural change | `CLAUDE.md`, `ARCHITECTURE.md` |
| Bug fix | `CHANGELOG.md`, regression test |
| Refactoring | `CHANGELOG.md`, affected docs |

### CHANGELOG.md Format

```markdown
## [Unreleased]

### Added

- Feature: [description] ([#issue](link))

### Changed

- [Component] - [what changed]

### Fixed

- Bug: [description] - [fix summary]
```

---

## 🤝 Context Management

### Before Starting Work

1. **Read CLAUDE.md** — current architecture
2. **Check CHANGELOG.md** — recent changes
3. **Review docs/DECISIONS.md** — key decisions
4. **Understand task** — ask clarifying questions if needed

### After Completing Work

1. **Update CHANGELOG.md** — what changed
2. **Run tests** — verify nothing broken
3. **Check linting** — `ruff check . --fix && ruff format .`
4. **Commit** — descriptive message

---

## 📊 Skill Selection Guide

### When to Use Each Skill

#### Code Development

**Use when:**
- Adding new features
- Creating API endpoints
- Writing new strategies
- Implementing services

**Pattern:**
```
Understand → Gather context → Implement → Verify → Document
```

#### Safe Refactoring

**Use when:**
- Improving code structure
- Reducing file size
- Extracting methods
- Renaming variables

**Pattern:**
```
Assess impact → ONE change → Verify → Repeat
```

#### Debugging

**Use when:**
- Fixing bugs
- Investigating errors
- Resolving parity issues

**Pattern:**
```
Reproduce → Isolate → Analyze → Fix → Verify
```

#### Test Generation

**Use when:**
- Adding test coverage
- Writing regression tests
- Creating fixtures

**Pattern:**
```
Understand code → Create fixtures → Write tests → Verify coverage
```

#### Documentation

**Use when:**
- Writing docstrings
- Creating README files
- Updating API docs
- Maintaining CHANGELOG

**Pattern:**
```
Understand audience → Choose format → Write examples → Review
```

---

## 📈 Performance Tips

### For Efficiency

1. **Read CLAUDE.md first** — understand architecture
2. **Use grep_search** — find all usages before changes
3. **Make atomic changes** — one logical change at a time
4. **Run tests incrementally** — catch issues early
5. **Document as you go** — don't leave it for later

### For Quality

1. **Follow existing patterns** — match codebase style
2. **Use type hints** — all functions
3. **Write tests** — for all new logic
4. **Check linting** — before committing
5. **Update docs** — keep synchronized

---

## 🚀 Quick Reference

### Critical Constants

```python
COMMISSION_RATE = 0.0007      # TradingView parity
DATA_START_DATE = 2025-01-01  # From database_policy.py
RETENTION_YEARS = 2           # Maximum data retention
MAX_BACKTEST_DAYS = 730       # 2 years limit
```

### Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Architecture documentation |
| `CHANGELOG.md` | Recent changes |
| `docs/DECISIONS.md` | Architectural decisions |
| `backend/backtesting/engine.py` | Main backtest engine |
| `backend/core/metrics_calculator.py` | 166 metrics |

### Commands

```powershell
# Run
.\dev.ps1 run

# Test
pytest tests/ -v

# Lint
ruff check . --fix && ruff format .

# Commit
git commit -m "type: description"
```

---

*Created: 2026-02-26 for Qwen Code*
*Based on analysis of: Claude, Copilot, Cursor, Gemini skills*
*Project: Bybit Strategy Tester v2*
