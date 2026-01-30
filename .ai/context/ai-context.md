# AI Context - Project State Tracking

> **Auto-updated by AI agents during sessions**
> Single source of truth for project context

## Current Focus

**Active Task:** None
**Priority:** -
**Status:** Idle

## Recent Changes

| Date       | Change                         | Files Affected             | Agent   |
| ---------- | ------------------------------ | -------------------------- | ------- |
| 2025-01-30 | Created unified .ai/ structure | .ai/\*, docs/ai-context.md | Copilot |

## Architecture Decisions (Recent)

- **Commission Rate:** 0.0007 (0.07%) - MUST match TradingView
- **Gold Standard Engine:** FallbackEngineV2
- **Metrics Count:** 166 metrics calculated

## Variable Tracker

Critical variables that must never be lost:

| Variable          | Type  | Location         | Status    |
| ----------------- | ----- | ---------------- | --------- |
| `commission_rate` | float | BacktestConfig   | ✅ Active |
| `initial_capital` | float | BacktestConfig   | ✅ Active |
| `strategy_params` | dict  | Strategy classes | ✅ Active |

## Session Log

### Latest Session

**Date:** -
**Duration:** -
**Completed:**

-   -

**In Progress:**

-   -

**Next Steps:**

-   -

## Known Issues

| Issue | Severity | Status | Notes |
| ----- | -------- | ------ | ----- |
| -     | -        | -      | -     |

## Performance Baselines

| Metric                  | Value  | Date Measured |
| ----------------------- | ------ | ------------- |
| Backtest speed (1 year) | ~2s    | -             |
| API response time       | <100ms | -             |
| Test suite runtime      | ~30s   | -             |

---

_Last updated: 2025-01-30_
