# Optimization System Refactoring

> **Date:** 2026-02-09
> **Author:** Claude Opus 4 (Agent Mode)
> **Status:** Phase 1 Complete

---

## Problem Statement

The optimization router (`backend/api/routers/optimizations.py`) was a **4,317-line monolith** with:

| Issue                                                | Impact                                               |
| ---------------------------------------------------- | ---------------------------------------------------- |
| 6x duplicated BacktestInput construction             | ~25 fields copied 6 times = maintenance nightmare    |
| Models defined inline in router                      | No reuse, circular import risk                       |
| RSI-only hardcoded signal generation                 | Cannot optimize EMA, MACD, Bollinger, etc.           |
| `train_split`, `timeout`, `early_stopping` dead code | Frontend sends values, backend ignores them          |
| All trades stored for every combination              | Memory explosion: 10K combos × 100 trades = OOM risk |
| 50-line manual metrics extraction                    | Repeated in 3 execution paths                        |
| `_format_params()` RSI-only                          | Smart recommendations broken for non-RSI             |

---

## Solution: 6 New Modules

```
backend/optimization/
├── __init__.py          # Updated: exports all new modules
├── models.py       NEW  # Pydantic request/response models
├── scoring.py      NEW  # Composite score, multi-criteria ranking
├── filters.py      NEW  # Static + dynamic constraint filtering
├── recommendations.py NEW # Smart recommendation generation
├── utils.py        NEW  # DRY helpers, train/test, timeout, early stopping
├── workers.py      NEW  # Multiprocessing batch worker
├── optuna_optimizer.py  # Existing (unchanged)
├── ray_optimizer.py     # Existing (unchanged)
└── advanced_engine.py   # Existing (unchanged)
```

### Module Details

#### `models.py` (~200 lines)

All Pydantic models extracted from the router:

- `SyncOptimizationRequest` — Grid/Random search request (all fields incl. train_split, timeout, early_stopping)
- `SyncOptimizationResponse` — Extended with `train_metrics`, `test_metrics`, `early_stopped`, `early_stopped_at`
- `OptunaSyncRequest` — Extends SyncOptimizationRequest for Bayesian search
- `VectorbtOptimizationRequest/Response` — High-performance Numba path
- `OptimizationResult`, `SmartRecommendation`, `SmartRecommendations`

#### `scoring.py` (~190 lines)

- `calculate_composite_score()` — Supports 20 metrics with proper normalization
- `rank_by_multi_criteria()` — Average rank method with `score = -avg_rank`
- `apply_custom_sort_order()` — Multi-level sort from frontend

#### `filters.py` (~100 lines)

- `passes_filters()` — Static constraints (min_trades, max_drawdown_limit, etc.)
- `passes_dynamic_constraints()` — 6 operators: `<=`, `>=`, `<`, `>`, `==`, `!=`

#### `recommendations.py` (~130 lines)

- `generate_smart_recommendations()` — Balanced/Conservative/Aggressive
- `_format_params()` — **Universal**: supports RSI, EMA, MACD, Bollinger, generic strategies

#### `utils.py` (~340 lines)

- `build_backtest_input()` — **Single source of truth** replacing 6 duplicated construction blocks
- `generate_param_combinations()` — Grid/Random with seed support
- `split_candles(train_split)` — Train/test split with min 50 candle safety check
- `TimeoutChecker` — `is_expired()` with caching (checks every 10 calls)
- `EarlyStopper` — `should_stop(score)` with configurable patience
- `extract_metrics_from_output()` — Replaces 50-line manual dict from bt_output.metrics
- `serialize_trades()` — Memory-safe with `max_trades` parameter
- `serialize_equity_curve()` — Downsampled to `max_points`
- `parse_trade_direction()` — String → TradeDirection enum

#### `workers.py` (~120 lines)

- `run_batch_backtests()` — Subprocess-safe worker using all new utils

---

## Integration Points

### Grid-Search Handler (single-process path)

**Before:** 150+ lines of inline BacktestInput + metrics extraction
**After:** Uses `build_backtest_input()`, `extract_metrics_from_output()`, `TimeoutChecker`, `EarlyStopper`, `split_candles()`

### GPU Batch Verification

**Before:** Duplicated BacktestInput (25 lines) + manual metrics (8 lines)
**After:** Uses `build_backtest_input()`, `extract_metrics_from_output()`, `parse_trade_direction()`

### FallbackV4 Validation

**Before:** Duplicated BacktestInput (25 lines) + manual metrics (7 lines)
**After:** Uses `build_backtest_input()`, `parse_trade_direction()`

---

## New Features Enabled

### 1. Train/Test Split (now functional)

```python
train_candles, test_candles = split_candles(candles, request.train_split)
# train_split=0.7 → 70% for optimization, 30% for validation
```

### 2. Timeout Enforcement (now functional)

```python
timeout_checker = TimeoutChecker(request.timeout_seconds)
for combo in param_combinations:
    if timeout_checker.is_expired():
        break  # Graceful timeout
```

### 3. Early Stopping (now functional)

```python
early_stopper = EarlyStopper(patience=request.early_stopping_patience)
for combo in param_combinations:
    if early_stopper.should_stop(best_score):
        break  # No improvement for N iterations
```

### 4. Memory Optimization

Trades kept only for top 10 results, pruned from remaining.

---

## Test Results

**215/215 tests passing** after refactoring:

- 82 optimization panel tests
- 87 evaluation panel tests
- 46 properties panel tests

---

## Remaining Work (Phase 2)

| Task                                      | Priority | Effort |
| ----------------------------------------- | -------- | ------ |
| Universal strategy support (not RSI-only) | P1       | Medium |
| Optuna return top-N trials                | P2       | Small  |
| SSE progress reporting                    | P3       | Medium |
| Walk-Forward Analysis backend             | P3       | Large  |
| Result caching                            | P4       | Medium |

---

## Lines of Code Impact

| Metric                                   | Before      | After                                |
| ---------------------------------------- | ----------- | ------------------------------------ |
| `optimizations.py`                       | 4,357 lines | ~4,042 lines (-315)                  |
| New modules total                        | 0           | ~1,080 lines                         |
| Net code added                           | —           | ~765 lines                           |
| Duplicated BacktestInput blocks          | 6           | 1 (in `build_backtest_input`)        |
| Duplicated metrics extraction            | 3           | 1 (in `extract_metrics_from_output`) |
| Dead features (train/timeout/early_stop) | 3           | 0 (all functional)                   |
