# TODO List

## Bybit Strategy Tester v2

> Pending tasks and improvements.

---

## In Progress

_None currently_

---

## Next Up

### High Priority

- [ ] Documentation improvements
- [ ] Frontend performance optimization

### Medium Priority

- [ ] Additional visualization features
- [ ] Multi-asset portfolio backtesting

### Low Priority

- [ ] Real-time streaming data support
- [ ] ML-based strategy optimization

---

## Completed (2026-01-26)

### Type Safety & Testing Sprint

- [x] **engine.py Mypy fixes** — 8 type errors fixed
    - Fixed `pnl_distribution` Optional type
    - Added None check for `result.metrics` logging
    - Added `trades: list[TradeRecord]` annotation
    - Fixed `has_custom_sltp` None comparisons
    - Fixed `entry_time` fallback for TradeRecord
- [x] **models.py Schema updates**
    - Added `id` field to TradeRecord
    - Added `sqn` to PerformanceMetrics
    - Added long/short_largest_win/loss_value fields
    - Removed duplicate field definitions
- [x] **bybit.py Type improvements**
    - Added mypy override in pyproject.toml
    - Fixed Optional[int] types for time parameters
    - Added missing return statement
- [x] **CI/CD verified** — workflows already exist
    - ci-cd.yml (lint, test, build, deploy)
    - pytest.yml (unit tests)
    - integration.yml (integration tests)
- [x] **GPU Acceleration Testing** — 11 tests passed
    - CuPy integration verified
    - CUDA availability detection
    - Memory management tests
    - Performance benchmarks
- [x] **Backtest API Integration Tests** — 17 tests passed
    - E2E tests for /api/v1/backtests/ endpoints
    - Run, list, get, delete operations
    - Metrics validation
- [x] **Optimizer Error Handling** — 28 tests passed
    - Custom exceptions module created
    - Parameter grid validation
    - Price data validation
- [x] **Mypy fixes in backtests.py** — 100+ type errors fixed
    - Added helper functions (\_safe_float, \_safe_int, \_safe_str, \_get_side_value)
    - Fixed SQLAlchemy Column type mismatches
    - Fixed stop_loss/take_profit parameter names
    - Added TradeDirection import and conversion
- [x] Bollinger Bands filter (mean_reversion, breakout, squeeze modes)
- [x] ADX filter (trend_only, direction, combined modes)
- [x] Monte Carlo Simulation module
- [x] Market Regime Detection (trending/ranging/volatile)
- [x] Performance Profiler with cProfile integration
- [x] 40 new tests (10 BB/ADX + 16 Monte Carlo + 14 Regime)

## Completed (2026-01-25)

- [x] MTF Phase 6-8 (Frontend UI, HTF Filters, Optimizer, Walk-Forward)
- [x] Audit project structure and documentation
- [x] Verify metrics calculator integration in engine.py
- [x] Update optimizer documentation (formulas synchronized)
- [x] Add 30 tests for metrics_calculator.py (all passed)
- [x] Update CHANGELOG.md with v2.1.1

## Completed Previously

- [x] MCP Infrastructure setup (mcp.json, bybit_mcp_server.py)
- [x] Multi-agent workflow added
- [x] Browser UI testing skill created
- [x] Bar Magnifier testing with 1m data
- [x] Claude Opus 4.5 autonomy configuration
- [x] Agent Skills setup (234+)
- [x] Innovation mode rules
- [x] Session handoff protocol

---

_Last Updated: 2026-01-26_
