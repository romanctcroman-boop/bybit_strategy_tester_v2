Profile performance bottlenecks in Bybit Strategy Tester v2 engine or adapter code.

Usage: /profile [file_or_component]

Examples:
  /profile                                               — profile the full backtest pipeline
  /profile backend/backtesting/engines/fallback_engine_v4.py
  /profile backend/backtesting/strategy_builder_adapter.py
  /profile backend/backtesting/indicator_handlers.py
  /profile backend/core/metrics_calculator.py
  /profile indicator rsi

Steps:
1. Identify the target component. Known hot paths ranked by impact:

   HIGH impact (profile first):
   - FallbackEngineV4 bar loop (~engine.py) — O(n_bars) per backtest
   - StrategyBuilderAdapter._execute_indicator() — called per block per bar
   - indicator_handlers.py dispatch — 40+ handlers, heavy pandas ops
   - MetricsCalculator.calculate_all() — 166 metrics, called once per backtest

   MEDIUM impact:
   - NumbaEngineV2 JIT compilation (first-call overhead only)
   - DataService.load_ohlcv() — I/O bound, check caching
   - Adapter connection graph traversal — O(blocks × connections)

   LOW impact (usually):
   - API routers — async overhead is minimal
   - Pydantic validation — BacktestConfig validation on each request

2. Read the target file. Look for these anti-patterns:

**Python loops (O(n) where vectorization is possible):**
```python
# BAD — row-by-row loop
for i, row in df.iterrows():
    result.append(some_calc(row))

# GOOD — vectorized
result = df['close'].rolling(14).mean()
```

**Repeated DataFrame copies:**
```python
# BAD — copy on every call
def handler(data, params):
    df = data.copy()   # expensive if called 40x per bar

# GOOD — operate in-place or use views
```

**Missing Numba JIT opportunities:**
```python
# Candidate: tight loops over arrays → @numba.njit
@numba.njit(cache=True)
def compute_rsi_wilder(closes, period): ...
```

**Inefficient indicator dispatch:**
```python
# BAD — long elif chain (was in adapter before refactor)
if block_type == 'rsi': ...
elif block_type == 'macd': ...

# GOOD — dict dispatch (now in INDICATOR_DISPATCH)
handler = INDICATOR_DISPATCH.get(block_type)
```

**Queue/deque misuse:**
```python
# BAD — list.pop(0) is O(n)
queue = []; queue.pop(0)

# GOOD — deque.popleft() is O(1) (already fixed in adapter)
from collections import deque; queue = deque(); queue.popleft()
```

3. Estimate the bottleneck severity:
   - If bar loop contains Python-level work per bar → HIGH: consider Numba
   - If indicator called multiple times with same params → MEDIUM: memoize
   - If DataFrame.copy() called in hot path → MEDIUM: audit necessity
   - If pure Python dict lookups → LOW: already fast

4. For Numba engine (numba_engine.py):
   - Check @njit(cache=True) on all hot functions — cold start kills benchmark
   - Verify parallel=True only where thread-safety is confirmed
   - Check array dtypes: float64 everywhere (Numba hates mixed types)

5. Output the profile report:

```
## Profile: [component]

### Hot Paths Found
| Location | Pattern | Severity | Fix |
|----------|---------|----------|-----|
| engine.py:L412 | iterrows() loop | HIGH | vectorize with np.where |
| adapter.py:L89 | df.copy() per block | MEDIUM | pass view instead |

### Numba Candidates
[functions that would benefit from @njit]

### Quick Wins (< 1 hour to implement)
[list]

### Estimated Speedup
[before/after estimate if measurable]
```

6. If a fix is clear and safe, implement it. Otherwise propose and ask for approval.

Rules:
- Never change commission_value (0.0007) as a "performance optimization"
- Numba JIT functions must produce bit-identical results to Python reference
- Run parity tests after any engine optimization: pytest tests/backend/backtesting/test_strategy_builder_parity.py -v
- Benchmark with: python -m cProfile -s cumulative main.py backtest ...
