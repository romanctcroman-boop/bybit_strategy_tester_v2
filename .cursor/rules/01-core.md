# Core Principles

> These rules apply to ALL AI interactions in this workspace.

## Project Overview

- **Project:** Bybit Strategy Tester v2
- **Stack:** Python 3.14+, FastAPI, SQLAlchemy, Pandas, NumPy, Bybit API v5
- **Purpose:** Backtesting system for Bybit trading strategies with TradingView parity

## Core Workflow: ANALYZE → PLAN → APPROVE → EXECUTE → VALIDATE

### ANALYZE Phase

For ANY non-trivial task:

1. **Understand:** Rephrase task, ask clarifying questions
2. **Search:** Find affected files and similar patterns in codebase
3. **Map:** Build dependency graph of affected components
4. **Identify:** List all variables that will be touched

### PLAN Phase

Create detailed execution plan:

```markdown
## Task: [name]

**Files affected:** [list with full paths]
**Variables tracked:** [name, type, file:line]
**Dependencies:** [component → dependencies]
**Execution order:** [step-by-step]
**Validation:** [how to verify success]
```

**STOP and REQUEST APPROVAL before proceeding**

### VALIDATE Phase

After changes:

- Run: `pytest tests/` (all tests must pass)
- Check: `ruff check .` (no lint errors)
- Verify: All tracked variables still exist
- Test: Manual verification if needed

## Autonomy Guidelines

### Auto-Execute (Safe)

- File reads, directory listings
- `git status`, `git log`, `git diff`
- `pytest`, `ruff check`, `ruff format`
- Creating/editing code files

### Ask Before

- `git push` (especially to main)
- Database migrations
- Installing new dependencies
- Modifying security-critical code

### Never Auto-Execute

- Destructive database operations
- Commands with sudo/admin
- External API calls without explicit permission
