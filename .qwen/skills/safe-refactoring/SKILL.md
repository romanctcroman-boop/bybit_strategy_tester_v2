---
name: Safe Refactoring
description: "Refactor code safely with test verification, dependency tracking, and incremental changes."
---

# Safe Refactoring Skill for Qwen

## Overview

Refactor code while maintaining correctness. Every refactoring step is verified with tests.

## ⚠️ Critical Rules

**BEFORE ANY REFACTORING:**

1. **Find ALL usages** of the symbol being changed
2. **Run existing tests** to establish baseline
3. **Check high-risk variables**: `commission_rate`, `strategy_params`, `initial_capital`

```powershell
# Baseline test run
pytest tests/ -v --tb=short 2>&1 | Tee-Object baseline_results.txt

# Find all usages
grep -rn "symbol_name" backend/ frontend/ tests/
```

## Refactoring Workflow

### Step 1: Assess Impact

```markdown
## Refactoring Plan

**Target:** [file/class/function to refactor]
**Goal:** [what improvement is expected]
**Risk Level:** Low/Medium/High

### Affected Files

1. `backend/...` - [what changes]
2. `tests/...` - [what tests need updating]
3. `frontend/...` - [if applicable]

### Dependencies

- [Component A] uses this → update first
- [Component B] imports this → update second
```

### Step 2: Make ONE Change

Apply a **single, atomic refactoring**:

- ✅ Rename private variable: `_old_name` → `_new_name`
- ✅ Extract method: 20+ lines → `_helper_function()`
- ✅ Inline variable: simple one-liners
- ✅ Remove dead code: verified unused via grep
- ✅ Simplify conditional: reduce nesting

### Step 3: Verify IMMEDIATELY

```powershell
# Run tests after EACH change
pytest tests/ -v --tb=short

# Check for lint errors
ruff check . --diff

# Verify type safety (if mypy configured)
mypy backend/ --ignore-missing-imports
```

### Step 4: Repeat

Go back to **Step 2** for the next change.

## Safe Refactoring Patterns

### Extract Method ✅

```python
# Before - monolithic function
def process_order(data: dict) -> dict:
    # 20 lines of validation
    if not data.get('id'):
        raise ValueError("Missing ID")
    # ... more validation
    
    # 10 lines of computation
    result = data['value'] * 1.07
    # ... more computation
    
    # 5 lines of formatting
    return {'result': result, 'status': 'ok'}

# After - extracted helpers
def process_order(data: dict) -> dict:
    validated = _validate_order_data(data)
    result = _compute_order_result(validated)
    return _format_order_response(result)
```

### Rename (Non-Public) ✅

```python
# SAFE: internal variables, private methods
_old_internal_name → _new_internal_name
local_var → more_descriptive_name

# DANGEROUS: public API, exported names
# ALWAYS grep for all usages first!
# Check __init__.py exports
# Verify no external dependencies
```

### Remove Dead Code ✅

Before removing, verify ALL:

```bash
# No callers in backend
grep -r "function_name" backend/ --include="*.py"

# No test references
grep -r "function_name" tests/ --include="*.py"

# No frontend usage
grep -r "function_name" frontend/ --include="*.js"

# Not in __init__.py exports
grep -r "function_name" backend/**/__init__.py
```

### Simplify Conditional ✅

```python
# Before - deep nesting
def calculate_fee(user: User, amount: float) -> float:
    if user.is_premium:
        if amount > 10000:
            if user.vip:
                return amount * 0.001
            else:
                return amount * 0.002
        else:
            return amount * 0.003
    else:
        return amount * 0.005

# After - guard clauses
def calculate_fee(user: User, amount: float) -> float:
    if user.vip and amount > 10000:
        return amount * 0.001
    if user.is_premium and amount > 10000:
        return amount * 0.002
    if user.is_premium:
        return amount * 0.003
    return amount * 0.005
```

## 🔴 High-Risk Variables (NEVER DELETE)

| Variable | Files | Risk | Verification Required |
|----------|-------|------|----------------------|
| `commission_rate` | 10+ | TradingView parity | grep + all tests |
| `strategy_params` | All strategies | System-wide break | grep + integration tests |
| `initial_capital` | Engine, metrics | Wrong calculations | grep + parity tests |
| `DATA_START_DATE` | Database policy | Data loss | grep + DB tests |
| Port aliases | Adapter | Silent signal loss | grep + E2E tests |

## Refactoring Checklist

- [ ] All usages identified via `grep -rn`
- [ ] Tests pass BEFORE refactoring (baseline)
- [ ] ONE atomic change at a time
- [ ] Tests pass AFTER each change
- [ ] No high-risk variables modified
- [ ] Ruff check passes: `ruff check . --fix`
- [ ] Type hints preserved/updated
- [ ] Documentation updated (docstrings)
- [ ] Commit after each logical group

## Post-Refactoring

After completing refactoring:

1. **Full test suite:**
   ```powershell
   pytest tests/ -v -m "not slow"
   ```

2. **Linting:**
   ```powershell
   ruff check . --fix && ruff format .
   ```

3. **Import verification:**
   ```powershell
   python -c "from backend.api.app import app; print('OK')"
   ```

4. **Update CHANGELOG.md:**
   ```markdown
   ### Refactored
   
   - [Component] - [what was improved]
   ```

5. **Commit:**
   ```bash
   git commit -m "refactor: [brief description of improvement]"
   ```

## Common Refactoring Scenarios

### Scenario 1: Reduce Function Length

**Trigger:** Function > 50 lines

**Approach:**
1. Identify logical blocks
2. Extract each block to helper function
3. Replace with descriptive call
4. Test after each extraction

### Scenario 2: Reduce File Size

**Trigger:** File > 500 lines

**Approach:**
1. Identify related functions
2. Create new module file
3. Move functions + update imports
4. Test after each move

### Scenario 3: Improve Naming

**Trigger:** Unclear variable/function names

**Approach:**
1. Grep all usages
2. Rename (private: direct, public: deprecate first)
3. Update all call sites
4. Test immediately

### Scenario 4: Remove Duplication

**Trigger:** Same code pattern in 3+ places

**Approach:**
1. Extract common logic to utility function
2. Replace all occurrences with call
3. Test each replacement site
4. Remove original duplicates
