---
name: Debugging
description: "Systematic approach to finding and fixing bugs with minimal disruption."
---

# Debugging Skill for Qwen

## Overview

Systematic debugging methodology for efficiently identifying and fixing bugs while maintaining code quality.

## 🔍 Debugging Workflow

### Phase 1: Reproduce

**BEFORE fixing — reproduce the bug:**

1. **Get exact steps:**
   - What input causes the bug?
   - What is the expected vs actual output?
   - Does it happen consistently?

2. **Create minimal reproduction:**
   ```python
   # test_bug_reproduction.py
   def test_specific_bug():
       """Reproduce the reported bug."""
       input_data = {...}  # Minimal data that triggers bug
       result = function_under_test(input_data)
       assert result == expected, f"Bug reproduced: {result}"
   ```

3. **Run reproduction test:**
   ```powershell
   pytest tests/test_bug_reproduction.py -v
   ```

### Phase 2: Isolate

**Narrow down the root cause:**

1. **Add logging at boundaries:**
   ```python
   from loguru import logger
   
   def suspicious_function(data):
       logger.debug(f"Input: {data}")
       # ... processing
       logger.debug(f"Intermediate: {intermediate_result}")
       # ... more processing
       logger.debug(f"Output: {result}")
       return result
   ```

2. **Binary search through code:**
   - Add log at midpoint
   - Is bug before or after?
   - Repeat on affected half

3. **Check recent changes:**
   ```bash
   git log --oneline -10
   git diff HEAD~5..HEAD -- backend/path/to/file.py
   ```

### Phase 3: Analyze

**Understand WHY the bug occurs:**

1. **Check common causes:**
   - ❌ Off-by-one errors in loops
   - ❌ None/NaN handling
   - ❌ Type mismatches
   - ❌ Timezone issues
   - ❌ Floating point precision
   - ❌ Race conditions (async code)

2. **Inspect data flow:**
   ```python
   # Add validation at each step
   assert data is not None, "Data is None"
   assert len(data) > 0, "Data is empty"
   assert isinstance(value, expected_type), f"Wrong type: {type(value)}"
   ```

3. **Check edge cases:**
   - Empty inputs
   - Maximum values
   - Special characters
   - Missing keys

### Phase 4: Fix

**Apply minimal fix:**

1. **Choose fix strategy:**
   - ✅ Fix root cause (preferred)
   - ✅ Add validation (defensive)
   - ⚠️ Workaround (if root cause unclear)

2. **Write fix:**
   ```python
   # Before - bug
   def calculate_percentage(part: float, whole: float) -> float:
       return (part / whole) * 100  # DivisionByZero if whole=0
   
   # After - fix
   def calculate_percentage(part: float, whole: float) -> float:
       if whole == 0:
           logger.warning("calculate_percentage: whole=0, returning 0")
           return 0.0
       return (part / whole) * 100
   ```

3. **Add regression test:**
   ```python
   def test_calculate_percentage_zero_whole():
       """Regression test for division by zero bug."""
       result = calculate_percentage(50, 0)
       assert result == 0.0, "Should handle zero whole gracefully"
   ```

### Phase 5: Verify

**Ensure fix works and doesn't break anything:**

1. **Run reproduction test:**
   ```powershell
   pytest tests/test_bug_reproduction.py -v  # Should PASS now
   ```

2. **Run related tests:**
   ```powershell
   pytest tests/backend/module/ -v  # All tests in affected area
   ```

3. **Run full suite:**
   ```powershell
   pytest tests/ -v -m "not slow"  # Fast tests
   ```

4. **Check linting:**
   ```powershell
   ruff check . --fix && ruff format .
   ```

## 🐛 Common Bug Patterns

### Pattern 1: NoneType Errors

```python
# Bug
value = data.get('key')  # Returns None if missing
result = value.upper()   # AttributeError: 'NoneType'

# Fix
value = data.get('key', '')  # Default value
# OR
if value is None:
    logger.warning("Missing key: 'key'")
    return default_result
result = value.upper()
```

### Pattern 2: Type Mismatch

```python
# Bug
def process(value: int) -> str:
    return str(value * 2)

result = process("123")  # TypeError: can't multiply str * int

# Fix
def process(value: int | str) -> str:
    if isinstance(value, str):
        value = int(value)
    return str(value * 2)
```

### Pattern 3: Floating Point Precision

```python
# Bug
if total == 100.0:  # May fail due to floating point
    process()

# Fix
if abs(total - 100.0) < 0.001:  # Epsilon comparison
    process()
```

### Pattern 4: Timezone Issues

```python
# Bug
now = datetime.now()  # Naive datetime
end_date = datetime(2025, 12, 31, tzinfo=UTC)  # Aware
if now > end_date:  # TypeError: can't compare naive and aware

# Fix
from datetime import UTC
now = datetime.now(UTC)  # Always use aware datetimes
```

### Pattern 5: Async Blocking

```python
# Bug
async def fetch_data():
    response = requests.get(url)  # Blocking call in async!

# Fix
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

## 🛠️ Debugging Tools

### Logging

```python
from loguru import logger

# Set debug level
logger.debug("Detailed info: {variable}", variable=value)
logger.info("Normal operation")
logger.warning("Something unexpected")
logger.error("Error occurred", exc_info=True)
```

### Breakpoints (for local debugging)

```python
# Insert breakpoint
import pdb; pdb.set_trace()
# Or in Python 3.7+
breakpoint()

# Useful commands:
# n (next line)
# c (continue)
# p variable (print)
# l (list code)
```

### Git Bisect (find commit that introduced bug)

```powershell
# Start bisect
git bisect start
git bisect bad          # Current commit has bug
git bisect good v1.0.0  # Old commit was good

# Git will checkout commits - test each
git bisect reset        # When done
```

## 📋 Debugging Checklist

- [ ] Bug reproduced consistently
- [ ] Minimal reproduction test created
- [ ] Root cause identified (not just symptoms)
- [ ] Fix is minimal and targeted
- [ ] Regression test added
- [ ] All tests pass
- [ ] No lint errors
- [ ] CHANGELOG.md updated
- [ ] Bug documented if recurring

## 📝 Bug Report Template

```markdown
## Bug: [Brief description]

### Symptoms
- What happens: [actual behavior]
- Expected: [expected behavior]

### Reproduction Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]

### Root Cause
[What caused the bug]

### Fix
[What was changed to fix it]

### Prevention
[How to avoid similar bugs]

### Files Changed
- `backend/...` - [change description]
- `tests/...` - [test added]
```

## Post-Fix Actions

After fixing bug:

1. **Update bug tracker** (if applicable)
2. **Document in CHANGELOG.md:**
   ```markdown
   ### Fixed
   
   - [Bug description] - [fix summary]
   ```
3. **Add to known issues** (if workaround, not full fix)
4. **Share learnings** (team knowledge base)
5. **Commit:**
   ```bash
   git commit -m "fix: [brief description of bug fix]"
   ```
