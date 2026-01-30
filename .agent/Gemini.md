# 🚀 Gemini Global Rules

## Bybit Strategy Tester v2

> **Model**: Gemini 3 Pro
> **Mode**: Fast (simple tasks) / Planning (complex)
> **Autonomy Level**: Maximum

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
git commit                  # Committing (with messages)
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
black .                     # Format code
isort .                     # Organize imports

# Testing & Analysis
pytest -v --cov            # Tests with coverage
cProfile, memory_profiler  # Profiling

# Documentation
# Updating CHANGELOG.md
# Adding docstrings
# Creating/updating .md files

# Refactoring (Safe)
# Renaming (non-public)
# Extracting methods/classes
# Removing dead code
# Simplifying logic

# Bug Fixes (Low Risk)
# Syntax errors, type hints
# Import errors, linter warnings
# Obvious bugs (with tests)
```

---

## Memory Priority

1. Check Knowledge Items first
2. Read .agent/docs/
3. Check applicable Skills
4. Then do independent research

---

## Documentation

After every task:

- Update CHANGELOG.md
- Add inline comments for complex logic
- Document decisions in DECISIONS.md

---

_Version: 1.0_
_Last Updated: 2026-01-24_
