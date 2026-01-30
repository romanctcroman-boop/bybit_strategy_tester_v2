# Backtesting Engine Architecture

## Overview

The backtesting system uses **five engines** with different purposes:

| Engine         | Purpose           | Accuracy | Speed  | Features                       |
| -------------- | ----------------- | -------- | ------ | ------------------------------ |
| **FallbackV2** | Basic reference   | 100%     | 1x     | Bar Magnifier                  |
| **FallbackV3** | Pyramiding        | 100%     | 1x     | + Multiple entries, FIFO/LIFO  |
| **FallbackV4** | Gold Standard     | 100%     | 1x     | + Multi-TP, ATR, Trailing, DCA |
| **NumbaV2**    | Fast optimization | 100%     | 41x    | JIT compiled                   |
| **GPUV2**      | Mass optimization | 100%     | 10-50x | CUDA accelerated               |

## Engine Selection Logic

```python
# Default selection in production
if need_multi_tp or need_dca or need_atr:
    engine = FallbackEngineV4()  # Gold standard
elif need_pyramiding:
    engine = FallbackEngineV3()
elif mass_optimization and GPU_AVAILABLE:
    engine = GPUEngineV2()
elif optimization:
    engine = NumbaEngineV2()  # 41x faster
else:
    engine = FallbackEngineV2()  # Basic
```

### Why Fallback Engines are Authoritative

The Fallback engine is the **single source of truth** for all backtest metrics because:

1. **Sequential Processing**: Processes bars one-by-one, exactly like real trading
2. **Equity-Based Sizing**: Recalculates position size based on current equity
3. **Proper SL/TP**: Checks stops using High/Low prices (intrabar detection)
4. **No Quick Reversals**: Cannot open new position on same bar as close

### VectorBT Limitations

VectorBT (`Portfolio.from_signals`) has architectural differences:

1. **Quick Reversals**: Can open position on same bar where it closed previous
2. **Fixed Sizing**: Uses constant `order_value` regardless of equity changes
3. **Parallel Processing**: Processes all signals simultaneously, not sequentially
4. **Limited SL/TP**: `sl_stop`/`tp_stop` don't support re-entry after stop hit

These differences cause **10-60% metric mismatches** depending on trading direction.

## When to Use Each Engine

### Fallback Engine (Default)

- ✅ All regular backtests via `BacktestEngine.run()`
- ✅ Any backtest with SL/TP
- ✅ Bidirectional trading (long + short)
- ✅ Short-only trading
- ✅ When accuracy matters

### VectorBT Engine (Optimization Only)

- ✅ Parameter optimization (thousands of iterations)
- ✅ When relative ranking matters more than absolute values
- ⚠️ Called directly via `_run_vectorbt()` by optimizer
- ❌ NOT for final backtest validation

## Implementation Details

### Fallback Engine (`_run_fallback`)

```
Location: backend/backtesting/engine.py
Features:
- Intrabar SL/TP using high/low prices
- MFE/MAE calculation per trade
- Proper commission/slippage modeling
- Trailing stop support
- All 136+ metrics calculated
```

### VectorBT Engine (`_run_vectorbt`)

```
Location: backend/backtesting/engine.py
Features:
- Fast vectorized execution
- GPU acceleration (if available)
- Approximate metrics for ranking
- Used only by optimizer for speed
```

## Testing

### Engine Consistency Test

```bash
python scripts/test_engine_identity.py
```

This test validates that Fallback produces consistent results across all directions.

### Bar Magnifier Test

```bash
python scripts/test_full_metrics_comparison.py
```

Compares standard mode vs Bar Magnifier (1-minute data) for precision testing.

## Decision History

**January 2026**: After extensive testing, we determined that VectorBT and Fallback
engines cannot achieve 100% metric parity due to fundamental architectural differences.
Decision: Use Fallback as authoritative engine for all regular backtests, reserve
VectorBT for optimization where speed matters more than precision.

Key findings:

- LONG direction: 5 vs 4 trades (VBT creates extra trade)
- SHORT direction: Same trade count but ~10% PnL difference
- BOTH direction: 10 vs 8 trades (VBT creates 2 extra trades)

Root cause: VectorBT's `from_signals` cannot precisely emulate sequential bar-by-bar
simulation with equity-based position sizing.
