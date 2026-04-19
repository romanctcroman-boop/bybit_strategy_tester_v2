# GSD Verification Patterns

## Goal-Backward Verification

**Principle:** Task completion ≠ Goal achievement.

A task "create RSI strategy" can complete by creating a file with `pass`. Verification checks that the strategy ACTUALLY generates valid signals.

## Verification Hierarchy

### Level 1: Automated (Always Run)

```bash
# Tests pass
pytest tests/ -v -m "not slow"

# Linting clean
ruff check .

# Code formatted
ruff format . --check

# Type consistency (commission rate)
grep -rn commission backend/ | grep -v 0.0007 | grep -v .pyc
```

### Level 2: Artifact Verification

For each artifact in must_haves:

1. **EXISTS** — File exists at path
2. **SUBSTANTIVE** — Not empty, not placeholder, meets min_lines
3. **EXPORTS** — Expected symbols exported
4. **CONTAINS** — Required patterns present

### Level 3: Key Link Verification

For each connection in must_haves:

1. **WIRED** — Code in `from` file actually references `to`
2. **PATTERN** — Regex match found (not in comments)
3. **FUNCTIONAL** — Connection produces expected behavior

### Level 4: Domain-Specific (Trading Platform)

```markdown
## TradingView Parity Check

- [ ] Commission rate = 0.0007 across all files
- [ ] FallbackEngineV4 is gold standard engine
- [ ] Known strategy produces metrics within tolerance

## Strategy Verification

- [ ] `generate_signals()` returns `SignalResult` — NOT a DataFrame with 'signal' column
- [ ] `result.entries` / `result.exits` are `bool` Series (`.dtype == bool`)
- [ ] No NaN in entries/exits after `.fillna(False)` (`result.entries.isna().any()` is False)
- [ ] BaseStrategy properly subclassed with `_validate_params()` raising ValueError

## Engine Verification

- [ ] PnL = (exit - entry) \* size - commission (both sides)
- [ ] Position sizing respects leverage
- [ ] Stop loss / take profit triggers correctly

## API Verification

- [ ] Endpoint returns proper HTTP status codes
- [ ] Response matches Pydantic model
- [ ] Error cases handled (400, 404, 500)
- [ ] Swagger docs auto-generated
```

## Anti-Pattern Scan

Always check modified files for:

| Pattern                     | Severity   | Description               |
| --------------------------- | ---------- | ------------------------- |
| `# TODO`                    | ⚠️ Warning | Incomplete implementation |
| `pass` (only body)          | 🛑 Blocker | Empty function/class      |
| `raise NotImplementedError` | 🛑 Blocker | Stub implementation       |
| `print()`                   | ⚠️ Warning | Should use `logger`       |
| Hardcoded dates             | ⚠️ Warning | Use DATA_START_DATE       |
| `commission` != 0.0007      | 🛑 Blocker | TradingView parity broken |

## Verification Report Status Values

- **passed** — All must_haves verified, no blockers
- **gaps_found** — One or more critical gaps, fix plans needed
- **human_needed** — Automated checks pass but human verification required
