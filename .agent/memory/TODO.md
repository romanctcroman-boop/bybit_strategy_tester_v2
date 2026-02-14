# TODO List

## Bybit Strategy Tester v2

> Pending tasks and improvements.
> Last updated: 2026-02-14

---

## In Progress

_None currently_

---

## Next Up

### High Priority

- [ ] Frontend performance optimization (strategy_builder.js ~3000 lines)
- [ ] Walk-forward optimization end-to-end testing
- [ ] E2E testing skill with Playwright

### Medium Priority

- [ ] Performance profiling skill (cProfile integration)
- [ ] Multi-asset portfolio backtesting
- [ ] DCA engine comprehensive test coverage

### Low Priority

- [ ] Real-time streaming data support (WebSocket)
- [ ] ML-based strategy optimization (scikit-learn/PyTorch)
- [ ] Subagent orchestration with `agents:` restriction

---

## Completed (2026-02-14)

### Agent Configuration Audit & Cleanup

- [x] Removed 19.5 MB generic skills (232 dirs) from `.agent/skills/`
- [x] Created 3 project-specific skills (database-operations, metrics-calculator, bybit-api-integration)
- [x] Fixed workflows (start_app.md, multi_agent.md) — removed Claude Code syntax
- [x] Updated Claude.md v2.0 → v3.1 for Sonnet 4 / Opus 4
- [x] Updated Gemini.md v1.0 → v1.1
- [x] Updated CONTEXT.md with current state
- [x] Security: replaced hardcoded API keys with `${env:...}`
- [x] Security: gitignored `.agent/mcp.json`, cleaned git history
- [x] Deleted backup files and empty directories

## Completed (2026-01-26)

### Type Safety & Testing Sprint

- [x] engine.py Mypy fixes — 8 type errors fixed
- [x] models.py Schema updates (TradeRecord, PerformanceMetrics)
- [x] bybit.py Type improvements
- [x] GPU Acceleration Testing — 11 tests passed
- [x] Backtest API Integration Tests — 17 tests passed
- [x] Optimizer Error Handling — 28 tests passed
- [x] Mypy fixes in backtests.py — 100+ type errors fixed
- [x] Bollinger Bands filter, ADX filter
- [x] Monte Carlo Simulation module
- [x] Market Regime Detection
- [x] Performance Profiler with cProfile integration
- [x] 40 new tests

## Completed (2026-01-25)

- [x] MTF Phase 6-8 (Frontend UI, HTF Filters, Optimizer, Walk-Forward)
- [x] Metrics calculator integration in engine.py
- [x] 30 tests for metrics_calculator.py
- [x] MCP Infrastructure setup
- [x] Bar Magnifier testing with 1m data

---

_Last Updated: 2026-02-14_
