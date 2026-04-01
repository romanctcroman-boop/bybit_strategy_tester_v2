---
name: profile
description: Profile performance bottlenecks in Bybit Strategy Tester v2 engine or adapter code. Use when investigating slow backtests or optimization runs.
argument-hint: "[file_or_component]"
context: fork
agent: Explore
effort: high
disable-model-invocation: true
---

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
   BAD:  `for i, row in df.iterrows(): result.append(some_calc(row))`
   GOOD: `result = df['close'].rolling(14).mean()`

   **Repeated DataFrame copies in hot path:**
   BAD:  `df = data.copy()` inside a handler called 40× per bar
   GOOD: operate in-place or use views

   **Missing Numba JIT opportunities:**
   Candidate: tight numeric loops over arrays → `@numba.njit(cache=True)`

   **Queue/deque misuse:**
   BAD:  `queue.pop(0)` is O(n)
   GOOD: `deque.popleft()` is O(1) (already fixed in adapter)

3. Estimate the bottleneck severity:
   - Python-level work per bar in bar loop → HIGH: consider Numba
   - Indicator called multiple times with same params → MEDIUM: memoize
   - DataFrame.copy() in hot path → MEDIUM: audit necessity

4. For Numba engine (numba_engine.py):
   - Check `@njit(cache=True)` on all hot functions — cold start kills benchmark
   - Verify `parallel=True` only where thread-safety is confirmed
   - Check array dtypes: float64 everywhere (Numba hates mixed types)

5. Output the profile report:

```
## Profile: [component]

### Hot Paths Found
| Location | Pattern | Severity | Fix |

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
- Run parity tests after any engine optimization
