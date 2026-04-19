# 🚀 Gemini 3 Pro — Agent Rules

## Bybit Strategy Tester v2

> **Model**: Gemini 3 Pro
> **Mode**: Fast (simple tasks) / Planning (complex)
> **Autonomy Level**: Maximum
> **Version**: 1.1
> **Last Updated**: 2026-02-14

---

## 🌐 Язык общения

**Вывод беседы в чат на Русском языке.** Все ответы, объяснения, комментарии к задачам и отчёты о проделанной работе — на русском. Код, имена переменных и комментарии в коде остаются на английском (Google-style docstrings, etc.).

---

## Session Workflow

### Fast Mode (Simple Tasks)

- Quick edits, explanations, single-file changes
- No task artifacts needed
- Direct execution

### Planning Mode (Complex Tasks)

- Multi-file changes, architecture work
- Create task.md and implementation_plan
- Document in artifacts

---

## ⚠️ Critical Project Rules

### NEVER violate:

- **Commission Rate** = `0.0007` (0.07%) — TradingView parity
- **Engine** = `FallbackEngineV4` is the gold standard
- **Data Policy** = No data before `2025-01-01` (import from `backend/config/database_policy.py`)
- **Timeframes** = Only 9 supported: `1, 5, 15, 30, 60, 240, D, W, M`

---

## Terminal Autonomy

Maximum permissions for autonomous work:

```powershell
# Development & Scripts
py -3.14 *.py              # All Python scripts
python -m pytest           # All test variants
npm run dev/build/test     # Node scripts
ruff check/format .        # Linting & formatting
mypy, black, isort         # Type checking & formatting

# Git (local operations)
git add                     # Staging changes
git commit --no-verify     # Committing (hooks broken on Windows)
git checkout -b             # Creating branches
git merge                   # Local merges
git pull, fetch             # Updating
git diff, log, status       # Read operations

# Docker
docker-compose up/down/logs
docker build, run, exec

# File operations
mkdir, touch                # Creating files/dirs
mv, cp                      # Moving/copying (within workspace)
cat, head, tail, find, grep # Reading/searching

# Code Quality
ruff check --fix .          # Auto-fix linting
ruff format .               # Format code

# Testing & Analysis
pytest -v --cov            # Tests with coverage (80% minimum)
```

### Ask Before:

- `git push` (especially to main)
- Database migrations / schema changes
- Installing new dependencies
- Changing `commission_rate` or engine selection
- Modifying `.env` or secrets

---

## Memory Priority

1. Check Knowledge Items first
2. Read `.agent/docs/` for architecture context
3. Check applicable Skills in `.github/skills/`
4. Check `.github/instructions/` for path-specific rules
5. Then do independent research

---

## Documentation

After every task:

- Update `CHANGELOG.md`
- Add inline comments for complex logic
- Document decisions in `docs/DECISIONS.md`

---

_Version: 1.1_
_Last Updated: 2026-02-14_
