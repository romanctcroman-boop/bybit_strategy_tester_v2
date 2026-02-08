---
name: Safe Refactoring
description: "Refactor code safely with test verification, dependency tracking, and incremental changes."
---

# Safe Refactoring Skill

## Overview

Refactor code while maintaining correctness. Every refactoring step is verified with tests.

## Refactoring Workflow

### Step 1: Assess Impact

Before ANY refactoring:

1. **Find all usages** of the symbol being changed
2. **Run existing tests** to establish baseline
3. **Check for high-risk variables**: `commission_rate`, `strategy_params`, `initial_capital`

```powershell
# Baseline test run
pytest tests/ -v --tb=short 2>&1 | Tee-Object baseline_results.txt
```

### Step 2: Make ONE Change

Apply a single, atomic refactoring:

- Rename variable/function
- Extract method
- Inline variable
- Remove dead code
- Simplify conditional

### Step 3: Verify

```powershell
# Run tests after each change
pytest tests/ -v --tb=short

# Check for lint errors
ruff check . --diff

# Verify no type errors
mypy backend/ --ignore-missing-imports
```

### Step 4: Repeat

Go back to Step 2 for the next change.

## Safe Refactoring Patterns

### Extract Method

```python
# Before
def process():
    # 20 lines of validation
    # 10 lines of computation
    # 5 lines of formatting
    pass

# After
def process():
    validated = _validate(data)
    result = _compute(validated)
    return _format(result)
```

### Rename (Non-Public)

```python
# Safe: internal variables, private methods
_old_name → _new_name
old_var → new_var  # local scope only

# DANGEROUS: public API, exported names
# Always grep for all usages first!
```

### Remove Dead Code

Before removing, verify:

1. `grep -r "function_name" backend/` — no callers
2. `grep -r "function_name" tests/` — no test references
3. `grep -r "function_name" frontend/` — no frontend usage
4. Check `__init__.py` exports

## High-Risk Variables (NEVER delete)

| Variable          | Files                         | Risk                      |
| ----------------- | ----------------------------- | ------------------------- |
| `commission_rate` | 10+ files                     | TradingView parity breaks |
| `strategy_params` | All strategies, optimizer, UI | Entire system breaks      |
| `initial_capital` | Engine, metrics, UI           | Calculations wrong        |

## Checklist

- [ ] All usages identified before change
- [ ] Tests pass BEFORE refactoring
- [ ] ONE atomic change at a time
- [ ] Tests pass AFTER each change
- [ ] No high-risk variables modified
- [ ] Ruff check passes
- [ ] Commit after each logical group
