# Git Integration for GSD Workflow

## Commit Strategy

### Atomic Commits per Plan

Each completed plan gets ONE commit:

```
git add -A
git commit -m "gsd: Phase XX Plan YY — [one-liner from SUMMARY.md]"
```

### Commit Message Format

```
gsd: Phase {phase} Plan {plan} — {substantive one-liner}

{Optional body with details}

Refs: .gsd/phases/{phase-dir}/{phase}-{plan}-SUMMARY.md
```

### Examples

```
gsd: Phase 01 Plan 01 — RSI strategy with divergence detection via pandas_ta
gsd: Phase 02 Plan 02 — Walk-forward optimizer with rolling window validation
gsd: Phase 03 Plan 01 — Multi-timeframe API endpoints with 9 supported intervals
```

### Bad Examples

```
gsd: Phase 01 Plan 01 — Phase complete          # Too vague
gsd: Update files                                 # No GSD context
fix: stuff                                        # Not substantive
```

## Branch Strategy

### Feature Branches

```
gsd/{phase-name}                    # e.g., gsd/01-rsi-divergence
gsd/{phase-name}/{plan}             # e.g., gsd/01-rsi-divergence/plan-02
```

### When to Branch

- New phase → new branch from main
- Large phase (4+ plans) → branch per plan
- Quick fixes → direct to main (with gsd: prefix)

## State File Handling

### Always Commit `.gsd/` Changes

```
.gsd/STATE.md          → Updated after each plan
.gsd/phases/           → PLAN.md + SUMMARY.md files
.gsd/debug/            → Debug session files (if investigation happened)
```

### Never Commit

```
.gsd/CONTINUE-HERE.md  → Temporary, delete after resume
```

## Quality Gate Before Commit

1. `pytest tests/ -v -m "not slow"` — all pass
2. `ruff check .` — no errors
3. `ruff format . --check` — formatted
4. No hardcoded paths or secrets
5. CHANGELOG.md updated
