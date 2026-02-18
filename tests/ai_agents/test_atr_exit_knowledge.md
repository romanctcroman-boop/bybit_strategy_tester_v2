# AI Agent Knowledge: ATR Exit Block

> **Last Updated:** 2026-02-16
> **Test File:** `tests/ai_agents/test_atr_exit_ai_agents.py`
> **Block Type:** `atr_exit`
> **Category:** `exit` (standalone, config-only)

---

## Overview

The **ATR Exit** block configures ATR-based Stop Loss and/or Take Profit for the engine.
It has **two independent sections**: ATR Stop Loss and ATR Take Profit.
Each section can be enabled/disabled independently with its own smoothing method,
period, multiplier, and on-wicks flag.

Unlike simpler config-only blocks, ATR Exit actually **computes ATR pd.Series** in
the adapter using `calculate_atr_smoothed()`, then passes them to the engine via
`extra_data` for bar-by-bar execution.

---

## Parameters (10 fields total)

### ATR Stop Loss Section (5 fields)

| Parameter         | Type     | Default | Optimizable | Description                             |
| ----------------- | -------- | ------- | ----------- | --------------------------------------- |
| use_atr_sl        | checkbox | false   | No          | Enable ATR-based Stop Loss              |
| atr_sl_on_wicks   | checkbox | false   | No          | Check wicks (high/low) for SL trigger   |
| atr_sl_smoothing  | select   | 'WMA'   | No          | Smoothing method: WMA / RMA / SMA / EMA |
| atr_sl_period     | number   | 140     | Yes (1-150) | ATR calculation period                  |
| atr_sl_multiplier | number   | 4.0     | Yes (0.1-4) | Exit if loss >= multiplier x ATR        |

### ATR Take Profit Section (5 fields)

| Parameter         | Type     | Default | Optimizable | Description                             |
| ----------------- | -------- | ------- | ----------- | --------------------------------------- |
| use_atr_tp        | checkbox | false   | No          | Enable ATR-based Take Profit            |
| atr_tp_on_wicks   | checkbox | false   | No          | Check wicks for TP trigger              |
| atr_tp_smoothing  | select   | 'WMA'   | No          | Smoothing method: WMA / RMA / SMA / EMA |
| atr_tp_period     | number   | 140     | Yes (1-150) | ATR calculation period                  |
| atr_tp_multiplier | number   | 4.0     | Yes (0.1-4) | Exit if profit >= multiplier x ATR      |

### Smoothing Methods (for both SL and TP)

- **WMA** — Weighted Moving Average (default)
- **RMA** — Running Moving Average (Wilder's)
- **SMA** — Simple Moving Average
- **EMA** — Exponential Moving Average

Invalid smoothing values fall back to `'RMA'`.

---

## Frontend Configuration

### Block Defaults (`strategy_builder.js`)

```javascript
atr_exit: {
    use_atr_sl: false,
    atr_sl_on_wicks: false,
    atr_sl_smoothing: 'WMA',
    atr_sl_period: 140,
    atr_sl_multiplier: 4.0,
    use_atr_tp: false,
    atr_tp_on_wicks: false,
    atr_tp_smoothing: 'WMA',
    atr_tp_period: 140,
    atr_tp_multiplier: 4.0
}
```

### Optimization Mode

Only **4 number fields** are optimizable (min/max/step):

- `atr_sl_period`: [min] -> [max] / [step]
- `atr_sl_multiplier`: [min] -> [max] / [step]
- `atr_tp_period`: [min] -> [max] / [step]
- `atr_tp_multiplier`: [min] -> [max] / [step]

**NOT optimizable** (6 fields): checkboxes (use_atr_sl, atr_sl_on_wicks, use_atr_tp,
atr_tp_on_wicks) and selects (atr_sl_smoothing, atr_tp_smoothing).

---

## Backend Processing

### Adapter `_execute_exit()` — Computes ATR Series

```python
elif exit_type == "atr_exit":
    result["exit"] = pd.Series([False] * n, index=ohlcv.index)
    result["use_atr_sl"] = use_atr_sl
    result["use_atr_tp"] = use_atr_tp

    if use_atr_sl:
        sl_period = max(1, min(150, int(params.get("atr_sl_period", 150))))
        sl_smoothing = params.get("atr_sl_smoothing", "WMA")
        sl_mult = max(0.1, min(4.0, float(params.get("atr_sl_multiplier", 4.0))))
        atr_sl = calculate_atr_smoothed(high, low, close, period=sl_period, method=sl_smoothing)
        result["atr_sl"] = atr_sl        # pd.Series
        result["atr_sl_mult"] = sl_mult   # float
        result["atr_sl_on_wicks"] = sl_on_wicks  # bool

    if use_atr_tp:
        # Same structure for TP...
```

**Key points:**

- Exit signal is always False (config-only)
- Period is **clamped** to range `[1, 150]`
- Multiplier is **clamped** to range `[0.1, 4.0]`
- Invalid smoothing method falls back to `'RMA'`
- ATR is computed as a `pd.Series` with `calculate_atr_smoothed()`

### Extra Data Collection (`generate_signals()`)

```python
for block_id, block in self.blocks.items():
    if block.get("type") == "atr_exit" and block_id in self._value_cache:
        cached = self._value_cache[block_id]
        if cached.get("use_atr_sl"):
            extra_data["use_atr_sl"] = True
            extra_data["atr_sl"] = cached["atr_sl"]          # pd.Series
            extra_data["atr_sl_mult"] = cached["atr_sl_mult"]  # float
            extra_data["atr_sl_on_wicks"] = cached.get("atr_sl_on_wicks", False)
        if cached.get("use_atr_tp"):
            extra_data["use_atr_tp"] = True
            extra_data["atr_tp"] = cached["atr_tp"]
            extra_data["atr_tp_mult"] = cached["atr_tp_mult"]
            extra_data["atr_tp_on_wicks"] = cached.get("atr_tp_on_wicks", False)
        break  # Only one atr_exit block expected
```

**Conditional population:** Unlike trailing stop (which always populates extra_data),
ATR exit only populates fields for **enabled** sections:

- `use_atr_sl=True` → adds 4 SL fields to extra_data
- `use_atr_tp=True` → adds 4 TP fields to extra_data
- Both disabled → NO ATR fields in extra_data

---

## Test Coverage Summary

| Test Class                  | Tests | What It Verifies                                       |
| --------------------------- | ----- | ------------------------------------------------------ |
| TestATRExitDefaults         | 3     | Both disabled by default, no extra_data, entries exist |
| TestATRStopLossConfig       | 12    | SL enable/disable, on_wicks, period/mult, clamping     |
| TestATRTakeProfitConfig     | 8     | TP enable/disable, on_wicks, period/mult combos        |
| TestSmoothingMethods        | 10    | WMA/RMA/SMA/EMA for SL and TP, invalid fallback        |
| TestCombinedATRSLTP         | 4     | Both enabled, SL-only, TP-only, different settings     |
| TestATROptimization         | 5     | Period/mult ranges, full grid, non-optimizable fields  |
| TestConfigOnlyBehavior      | 3     | Exit always False, independence from entry             |
| TestExtraDataPopulation     | 5     | SL-only, TP-only, both, empty, series length           |
| TestRSIFilterWithATRExit    | 2     | RSI range/cross + ATR exit combos                      |
| TestMACDFilterWithATRExit   | 2     | MACD cross/histogram + ATR exit combos                 |
| TestRSIMACDComboWithATRExit | 2     | RSI+MACD dual entry + ATR exit                         |
| TestAllParamsFullScenario   | 3     | Every param explicit, defaults, smoothing cycle        |

**Total: ~59 tests**

---

## Common AI Agent Mistakes

1. **Thinking ATR exit generates signals:** It does NOT. Exit is always False.
   The engine reads ATR series from `extra_data` and checks bar-by-bar.

2. **Confusing SL and TP sections:** They are INDEPENDENT. Each has its own
   smoothing, period, multiplier, and on_wicks. They can be enabled separately.

3. **Thinking smoothing is optimizable:** It's a select — NOT optimizable.
   Only `period` and `multiplier` get min/max/step in the optimizer.

4. **Forgetting conditional extra_data:** Unlike trailing stop, ATR exit only
   populates extra_data for ENABLED sections. Disabled sections = no data.

5. **Not knowing value clamping:** Period is clamped to [1, 150], multiplier
   to [0.1, 4.0]. Values outside range are silently clamped.

6. **Only one block expected:** The adapter uses `break` after finding the first
   `atr_exit` block — only one is expected per strategy.
