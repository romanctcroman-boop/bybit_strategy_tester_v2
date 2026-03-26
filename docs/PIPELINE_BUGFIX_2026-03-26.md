# AI Pipeline Bug Fix Report — 2026-03-26

**Branch:** `main`  
**Scope:** `backend/agents/trading_strategy_graph.py`, `backend/agents/prompts/response_parser.py`, `temp_pipeline_runner.py`  
**Result:** Pipeline exits 0 — 35 nodes, 0 errors, ~$0.036/run

---

## Background

The AI pipeline (`run_strategy_pipeline`) was executing all 35 LangGraph nodes and making 12 LLM calls per run ($0.036) but producing **no usable output** — the backtest always failed, the refinement loop always maxed out at 4 iterations, and every run ended with `severity=catastrophic, root_cause=no_signal`.

A Claude Code session had diagnosed some surface symptoms but left the root causes unfixed. This session re-verified all findings from scratch and applied complete fixes.

---

## Bugs Fixed

### Bug 1 — `BacktestConfig` missing required fields (Pydantic ValidationError)

**File:** `backend/agents/trading_strategy_graph.py` — `_run_via_adapter()`  
**Symptom:** Every backtest attempt raised a Pydantic `ValidationError` and silently fell back to `BacktestBridge`, which produced stub metrics.

**Root cause:** `BacktestConfig` was constructed with `timeframe=timeframe` (wrong field name — the model field is `interval`) and without the required `start_date` / `end_date` fields.

**Fix:**
```python
# Derive start/end from the OHLCV DataFrame index
df_start = df.index[0].to_pydatetime().replace(tzinfo=UTC)
df_end   = df.index[-1].to_pydatetime().replace(tzinfo=UTC)

cfg = BacktestConfig(
    symbol=symbol,
    interval=timeframe,   # was: timeframe=timeframe
    start_date=df_start,  # was: missing
    end_date=df_end,      # was: missing
    ...
)
```

---

### Bug 2 — `ResponseParser` rejected LLM output in `blocks/connections` format

**File:** `backend/agents/prompts/response_parser.py` — `_build_strategy()`  
**Symptom:** `parse_responses` node always produced 0 proposals (0.00s execution time).

**Root cause:** The LLM sometimes returns a Strategy Builder graph format (`blocks` / `connections` keys) instead of the `StrategyDefinition` format (`signals` / `filters`). `ResponseParser` had no fallback and returned `None` silently.

**Fix:** Added pre-normalisation in `_build_strategy()` + a `_convert_blocks_to_signals()` converter that maps block types (RSI, EMA, Bollinger, etc.) to `StrategyDefinition` signal entries:
```python
# Pre-normalise: Strategy Builder format → signals/filters
if "blocks" in data and "connections" in data and "signals" not in data:
    data = self._convert_blocks_to_signals(data)
```

---

### Bug 3 — `temp_pipeline_runner.py` — `MarketContext` not subscriptable

**File:** `temp_pipeline_runner.py`  
**Symptom:** `TypeError: 'MarketContext' object is not subscriptable` on `ctx[:400]`.

**Fix:**
```python
ctx_str = getattr(ctx, "summary", None) or getattr(ctx, "description", None)
if ctx_str is None:
    ctx_str = str(ctx)
print(f"\n--- Market Context ---\n{ctx_str[:400]}")
```

---

### Bug 4 — `BacktestEngine.run()` called with wrong keyword arguments

**File:** `backend/agents/trading_strategy_graph.py` — `_run_sync()` inside `_run_via_adapter()`  
**Symptom:** `BacktestEngine.run() got an unexpected keyword argument 'data'` — backtest always fell back to `BacktestBridge`.

**Root cause:** The code called:
```python
engine.run(data=df, signals=signal_result, config=cfg)
```
But the actual `BacktestEngine.run()` signature is:
```python
def run(self, config: BacktestConfig, ohlcv: pd.DataFrame, silent=False, custom_strategy=None)
```
`signals` is not a parameter at all. The `signal_result` from `StrategyBuilderAdapter.generate_signals()` needed to be injected via `custom_strategy`.

**Fix:** Wrapped the pre-computed `SignalResult` in a `BaseStrategy` subclass:
```python
_precomputed = signal_result

class _PrecomputedStrategy(BaseStrategy):
    def _validate_params(self) -> None:
        pass
    def generate_signals(self, ohlcv):
        return _precomputed

engine = BacktestEngine()
result = engine.run(
    config=cfg,
    ohlcv=df,
    custom_strategy=_PrecomputedStrategy(),
)
```

---

### Bug 5 — `BacktestAnalysisNode` false `catastrophic` severity on valid backtests

**File:** `backend/agents/trading_strategy_graph.py` — `BacktestAnalysisNode.execute()`  
**Symptom:** Backtests with real metrics (`Return=2.65%, Sharpe=1.77`) were classified as `severity=catastrophic, root_cause=signal_connectivity` and triggered the maximum refinement loop every run.

**Root cause:** `BacktestEngine` marks positions closed at end-of-backtest as `is_open=True` (TradingView parity). These are filtered out of `closed_trades_for_metrics`, so `total_trades=0` even when a real position was taken and held. The analysis node used only `total_trades` for its pass/fail check.

**Fix:** Added `open_trades` (EOB positions) to an `effective_trades` counter used throughout all severity and root-cause logic:
```python
open_trades: int = int(metrics.get("open_trades", 0))
effective_trades: int = trades + open_trades
# ... use effective_trades everywhere instead of trades
```

---

### Bug 6 — False `[NO_TRADES]` engine warning when EOB position exists

**File:** `backend/agents/trading_strategy_graph.py` — `_run_via_adapter()`  
**Symptom:** The warning `[NO_TRADES] Signals were generated but no trades executed` was emitted even when `open_trades=1`, causing `RefinementNode` to generate a wrong `signal_connectivity` diagnosis.

**Fix:** Changed the guard condition from `if trades_count == 0` to `if effective_count == 0`:
```python
open_count = metrics.get("open_trades", 0)
effective_count = trades_count + open_count
if effective_count == 0:
    engine_warnings.append("[NO_TRADES] ...")
```

---

### Bug 7 — `OptimizationNode` `KeyError: 'interval'` in `build_backtest_input`

**File:** `backend/agents/trading_strategy_graph.py` — `OptimizationNode._run_optimization()`  
**Symptom:** Every optimization trial crashed with `KeyError: 'interval'`; optimizer reported `0 trials, best_score=0.000`.

**Root cause:** `config_params` dict used the wrong keys:
- `"timeframe"` instead of `"interval"` (as expected by `build_backtest_input`)
- `"commission_value"` instead of `"commission"`

**Fix:**
```python
config_params = {
    "symbol": symbol,
    "interval": timeframe,          # was: "timeframe"
    "initial_capital": initial_capital,
    "leverage": leverage,
    "commission": COMMISSION_TV,    # was: "commission_value"
    "direction": "both",
}
```

---

### Bug 8 — `UnicodeEncodeError` in `temp_pipeline_runner.py` on Windows cp1251 console

**File:** `temp_pipeline_runner.py`  
**Symptom:** Script crashed with `UnicodeEncodeError: 'charmap' codec can't encode character '\u2705'` on the final summary print.

**Fix:** Replaced emoji characters in `print()` calls and added safe encoding for captured log lines:
```python
for line in warnings_text.strip().split("\n")[:20]:
    safe = line.encode("cp1251", errors="replace").decode("cp1251")
    print(f"  {safe}")
```

---

## Pipeline State Before / After

| Metric | Before | After |
|--------|--------|-------|
| Exit code | 1 (crash) | **0** |
| `BacktestEngine.run()` error | Every iteration | None |
| Proposals parsed | 0 | 1+ per iteration |
| Backtest result | `severity=catastrophic` | `severity=moderate` (correct) |
| `OptimizationNode` trials | 0 (KeyError) | **50 trials** |
| Refinement loop reason | Wrong diagnosis | Correct: `too few trades` (500-bar window) |
| Memory stored | No | Yes (`MemoryUpdateNode`) |
| ML validation | No | Yes (passes) |
| LLM cost | $0.036 wasted | $0.036 productive |

---

## Remaining Known Issues (lower priority)

| Issue | Location | Notes |
|-------|----------|-------|
| `Unknown indicator type 'input'/'condition'` | `StrategyBuilderAdapter` | LLM generates raw `input`/`condition` pseudo-blocks not in `BLOCK_REGISTRY`. Needs handlers registered. |
| Port resolver warnings | `StrategyBuilderAdapter` | Side-effect of above — `const_N` and `cond_N` ports fail to resolve. |
| `total_trades=0` in short test windows | `BacktestEngine` / test data | 500 bars × 15min = 5.2 days. Mean-reversion strategies take 1 position held to EOB. Use ≥2000 bars for meaningful trade counts. |
| `best_score=0.000` in optimizer | `OptimizationNode` | Optimizer scores based on closed trades; EOB positions not counted → score=0. Inherits from Bug 5 semantics. Lower priority. |

---

## Files Modified

| File | Changes |
|------|---------|
| `backend/agents/trading_strategy_graph.py` | Bugs 1, 4, 5, 6, 7 |
| `backend/agents/prompts/response_parser.py` | Bug 2 |
| `temp_pipeline_runner.py` | Bugs 3, 8 |
| `.github/skills/strategy-development/SKILL.md` | Corrected import path + interface (separate session) |
| `.github/skills/metrics-calculator/SKILL.md` | Corrected line count 1483 → 1303 (separate session) |
