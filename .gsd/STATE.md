# Project State

## Project Reference

See: .gsd/PROJECT.md (updated 2026-02-18)

**Core value:** TradingView-parity backtesting platform for Bybit crypto strategies
**Current focus:** GSD bootstrapped — codebase scanned — ready for first goal

## Current Position

Phase: [0] of [0] (No phases defined yet)
Plan: [0] of [0] in current phase
Status: Bootstrapped — awaiting first goal → ROADMAP.md
Last activity: 2026-02-18 — GSD bootstrap complete (codebase scanned)

Progress: [░░░░░░░░░░] 0%

## Codebase Metrics (scanned 2026-02-18)

| Metric               | Value |
| -------------------- | ----- |
| Backend Python files | 557   |
| API routers          | 79    |
| API routes           | 753   |
| Backtest engines     | 7     |
| Strategies (library) | 11    |
| Services             | 52    |
| Core modules         | 14    |
| Frontend HTML pages  | 51    |
| Frontend JS files    | 3,178 |
| Frontend CSS files   | 52    |
| Test files           | 179   |
| Tests collected      | 169   |
| Ruff errors          | 2,677 |
| Backend packages     | 22    |

**Codebase analysis files:** See `.gsd/codebase/` for STRUCTURE, STACK, ARCHITECTURE, PATTERNS, CONCERNS.

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: N/A
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
| ----- | ----- | ----- | -------- |
| -     | -     | -     | -        |

**Recent Trend:**

- Last 5 plans: N/A
- Trend: N/A

## Accumulated Context

### Key Decisions

- 2026-02-18: GSD workflow initialized with custom agents, prompts, skills for algotrading domain
- 2026-02-18: GSD bootstrap executed — codebase scanned with real metrics
- Commission rate locked at 0.0007 (TradingView parity)
- FallbackEngineV4 is gold standard engine
- 9 supported timeframes: 1, 5, 15, 30, 60, 240, D, W, M

### Known Issues

- 2,677 ruff errors (60% cosmetic unicode/whitespace, auto-fixable)
- Deprecation warning in `backend.agents.llm.connections`
- Strategy location split: 1 in `backtesting/strategies/`, 11 in `services/strategies/`
- Universal engine scope creep: 33 modules, many experimental
- See `.gsd/codebase/CONCERNS.md` for full analysis
- See `docs/DECISIONS.md` for architecture decision records
- See `CHANGELOG.md` for recent changes

### Patterns Established

- Strategies: BaseStrategy → LibraryStrategy subclass with `generate_signals()` → DataFrame with 'signal' column
- API: FastAPI router with `/api/v1/` prefix, loguru logging, HTTPException error handling
- DB: SQLAlchemy + SQLite, `asyncio.to_thread` for blocking operations in async context
- Tests: pytest with `test_[function]_[scenario]` naming, mock Bybit API
- See `.gsd/codebase/PATTERNS.md` for full pattern documentation
