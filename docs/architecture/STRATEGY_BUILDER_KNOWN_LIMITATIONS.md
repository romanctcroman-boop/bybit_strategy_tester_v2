# Strategy Builder — Known Limitations

> **Last updated:** 2026-02-20
> **File:** `backend/backtesting/strategy_builder_adapter.py`

---

## 1. Divergence Detection: Edge Bars Not Covered

**Affected lines:** ~3485 (pivot detection)

The divergence detection algorithm uses a `pivot_interval` parameter (default: 5 bars) to identify swing highs/lows. Due to the sliding window approach, the **first** and **last** `pivot_interval` bars of the dataset will never generate divergence signals.

**Impact:**

- For `pivot_interval=5` on a 10,000-bar dataset: 10 bars (0.1%) are unscanned.
- Negligible for most practical use cases.

**Workaround:** Load extra bars at the start of the date range to ensure coverage.

---

## 2. Multi-Timeframe (MTF) Fallback Behavior

**Affected lines:** ~1297

When MTF data is unavailable (e.g., insufficient history for weekly candles), the adapter silently falls back to the **primary timeframe** without warning the user.

**Current behavior:**

1. MTF indicator requested (e.g., RSI on Weekly)
2. Data fetch fails or returns too few bars
3. Adapter uses single-timeframe data instead
4. No error, no UI warning

**Impact:** The user may believe they are using a multi-timeframe strategy when they are not.

**Recommendation:** A `logger.warning()` has been considered but deferred to avoid log noise. The frontend could display MTF availability status.

---

## 3. Stochastic K-Smoothing Not Supported

**Affected lines:** ~844, ~848

The `k_smooth` parameter (`stoch_k_smoothing`) is accepted by the Stochastic indicator node and logged in debug output, but it is **not passed** to the underlying `vbt.STOCH.run()` call.

**Why:**

- VectorBT's `STOCH.run()` does not accept a `k_window_smooth` parameter (it only has `k_window` and `d_window`).
- The parameter is preserved in config for potential future use with a custom Stochastic implementation.

**Current behavior:**

```python
stoch = vbt.STOCH.run(high, low, close,
    k_window=k_period,    # ✅ Used
    d_window=d_smooth,    # ✅ Used
    d_ewm=False)          # ✅ Used
# k_smooth is IGNORED — not passed to vbt
```

**Impact:** Users setting `k_smooth != 1` will not see any effect on the %K line. The %K is always unsmoothed (SMA=1).

**Workaround:** To get smoothed %K, apply a separate SMA/EMA block after the Stochastic node.

---

## 4. Direction Mode Mapping

**Affected file:** `backend/backtesting/vectorbt_sltp.py`

The direction mode uses integer encoding:

| Mode | Meaning             |
| ---- | ------------------- |
| `0`  | Both (long + short) |
| `1`  | Long only           |
| `2`  | Short only          |

This is an internal convention matching the VectorBT `Direction` enum. The values are validated at the engine level.

---

_Document generated from audit findings A9, A13, A14 + P4.2/P4.3_
