# Refactor Checklist for AI Agents

Before refactoring any core subsystem, walk through this checklist **in order**. Skip a step only if it's genuinely irrelevant.

## Pre-flight

- [ ] Read `CLAUDE.md` §5 (Critical Constants) and §7 (Cross-cutting Parameters table)
- [ ] `grep -rn <symbol_you_are_changing> backend/ frontend/` — count ALL usages
- [ ] Check if the symbol is in the cross-cutting table above — if yes, plan multi-file update
- [ ] Read `DECISIONS.md` for any prior ADR about this area

## High-risk parameter changes

If changing `commission_rate`, `initial_capital`, `position_size`, `leverage`, `pyramiding`, or `direction`:

- [ ] Update **BacktestConfig** in `backend/backtesting/models.py`
- [ ] Update **all bridges** (`backtest_bridge.py`, `walk_forward_bridge.py`)
- [ ] Update **optimization models** (`optimization/models.py`, `optimization/utils.py`)
- [ ] Update **engine** (`engine.py`) if default/semantics change
- [ ] Update **MetricsCalculator** (`metrics_calculator.py`) if it depends on the param
- [ ] Update **frontend defaults** (`strategy_builder.js`, `leverageManager.js`)
- [ ] Update **agent tools** (`agents/mcp/tools/backtest.py`, `api/routers/agents.py`)
- [ ] Run commission parity check: `grep -rn commission backend/ | grep -v 0.0007 | grep -v .pyc`
- [ ] Run `pytest tests/backend/backtesting/test_engine.py tests/backend/backtesting/test_strategy_builder_parity.py -v`

## Engine changes

- [ ] Confirm engine selector (`engine_selector.py`) still routes correctly
- [ ] All engines MUST delegate metrics to `MetricsCalculator.calculate_all()` — never reimplement
- [ ] If adding engine type, update `ENGINE_MAP` in engine_selector.py and `EngineType` enum in models.py
- [ ] Run: `pytest tests/backend/backtesting/test_engine.py -v`

## Strategy / Adapter changes

- [ ] `generate_signals()` must return `SignalResult` (entries/exits/short_entries/short_exits)
- [ ] `SignalResult` contract: all Series must have same index as input OHLCV DataFrame
- [ ] Indicator periods clamped [1, 500] via `_clamp_period()` in adapter
- [ ] Port alias fallback works for divergence blocks (`long` ↔ `bullish`, `short` ↔ `bearish`)
- [ ] Run: `pytest tests/backend/backtesting/ -v -m "not slow"`

## API / Router changes

- [ ] Direction default is `"long"` in `BacktestCreateRequest` vs `"both"` in `BacktestConfig` — be aware
- [ ] Validate date range ≤ 730 days (`validate_dates()` in models.py)
- [ ] Async DB operations use `asyncio.to_thread()` for blocking SQLite calls
- [ ] Check Swagger docs still render: `http://localhost:8000/docs`

## Frontend changes

- [ ] No build step — pure ES modules, test by reloading browser
- [ ] Commission UI is in **percent** (0.07) → backend converts to decimal (0.0007)
- [ ] Leverage slider capped at 125 (Bybit max), color-coded for high values
- [ ] All strategy params flow through Properties panel → `strategy_params` dict

## Post-flight

- [ ] `ruff check . --fix && ruff format .`
- [ ] `pytest tests/ -v -m "not slow"` — all green
- [ ] Update `CHANGELOG.md` with what changed
- [ ] If structural change, update `CLAUDE.md` (this file) and `docs/ARCHITECTURE.md`
- [ ] Commit with descriptive message
