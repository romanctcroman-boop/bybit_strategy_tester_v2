# AI Agent Knowledge: Trailing Stop Exit Block

> **Last Updated:** 2026-02-04
> **Test File:** `tests/ai_agents/test_trailing_stop_ai_agents.py`
> **Block Type:** `trailing_stop_exit`
> **Category:** `exit` (standalone, config-only)

---

## Overview

The **Trailing Stop** exit block configures a trailing stop loss for the backtest engine.
It is a **config-only** block — the adapter stores parameters but does NOT generate exit
signals. The engine (`FallbackEngineV4`) reads the configuration via `extra_data` and
applies the trailing stop bar-by-bar during position management.

---

## Parameters

| Parameter          | Type   | Default   | Optimizable | Description                             |
| ------------------ | ------ | --------- | ----------- | --------------------------------------- |
| activation_percent | number | 1.0       | ✅ Yes      | Profit % threshold to activate trailing |
| trailing_percent   | number | 0.5       | ✅ Yes      | Distance % from peak price to trigger   |
| trail_type         | select | 'percent' | ❌ No       | Type: 'percent' / 'atr' / 'points'      |

### Parameter Details

- **activation_percent** — "Активация (% прибыли)": Once the position's unrealized
  profit reaches this percentage, the trailing stop activates. Before this, no trailing
  stop is in effect.

- **trailing_percent** — "Дистанция трейла (%)": After activation, the stop follows
  the price at this distance below the peak. If price retraces by this amount from its
  highest point since activation, the position exits.

- **trail_type** — "Тип трейлинга": Controls how trailing distance is calculated:
    - `percent` (Процент) — percentage-based distance
    - `atr` (ATR) — ATR-based distance
    - `points` (Пункты) — point/pip-based distance

---

## Frontend Configuration

### Block Defaults (`strategy_builder.js`)

```javascript
trailing_stop_exit: {
    activation_percent: 1.0,
    trailing_percent: 0.5,
    trail_type: 'percent'
}
```

### Panel Fields (`customLayouts`)

```javascript
trailing_stop_exit: {
    title: 'TRAILING STOP',
    fields: [
        { key: 'activation_percent', label: 'Активация (% прибыли)', type: 'number', optimizable: true },
        { key: 'trailing_percent', label: 'Дистанция трейла (%)', type: 'number', optimizable: true },
        { key: 'trail_type', label: 'Тип трейлинга', type: 'select',
          options: ['percent', 'atr', 'points'],
          optionLabels: ['Процент', 'ATR', 'Пункты'] }
    ]
}
```

### Optimization Mode

In optimization mode, only **number** fields with `optimizable: true` get min/max/step controls:

- `activation_percent`: [min] → [max] / [step]
- `trailing_percent`: [min] → [max] / [step]
- `trail_type`: **NOT optimizable** — stays fixed as a select dropdown

---

## Backend Processing

### Adapter `_execute_exit()` (config-only)

```python
elif exit_type == "trailing_stop_exit":
    result["exit"] = pd.Series([False] * n, index=ohlcv.index)
    result["trailing_activation_percent"] = params.get("activation_percent", 1.0)
    result["trailing_percent"] = params.get("trailing_percent", 0.5)
    result["trail_type"] = params.get("trail_type", "percent")
```

**Key points:**

- Exit signal is **always False** — engine handles actual exits
- Params stored in `_value_cache[block_id]` with keys: `trailing_activation_percent`, `trailing_percent`, `trail_type`
- Note the key rename: `activation_percent` (param) → `trailing_activation_percent` (cache)

### Extra Data Collection (`generate_signals()`)

```python
for block_id, block in self.blocks.items():
    if block.get("type") == "trailing_stop_exit" and block_id in self._value_cache:
        cached = self._value_cache[block_id]
        activation = cached.get("trailing_activation_percent")
        trail_dist = cached.get("trailing_percent")
        if activation is not None and trail_dist is not None:
            extra_data["use_trailing_stop"] = True
            extra_data["trailing_activation_percent"] = float(activation)
            extra_data["trailing_percent"] = float(trail_dist)
            extra_data["trail_type"] = cached.get("trail_type", "percent")
        break  # Only one trailing_stop_exit block expected
```

**Critical difference from Static SL/TP:**

- Static SL/TP does **NOT** populate `extra_data` for its own params
- Trailing Stop **DOES** populate `extra_data` with 4 keys:
    - `use_trailing_stop` (bool) — flag for engine
    - `trailing_activation_percent` (float)
    - `trailing_percent` (float)
    - `trail_type` (str)

---

## Port Configuration

```javascript
trailing_stop_exit: {
    inputs: [],
    outputs: [{ id: 'config', label: '', type: 'config' }]
}
```

- No input ports — standalone block, no connections needed
- Single `config` output port — indicates config-only behavior
- Does NOT connect to the strategy node

---

## Test Coverage Summary

| Test Class                   | Tests | What It Verifies                                    |
| ---------------------------- | ----- | --------------------------------------------------- |
| TestTrailingStopDefaults     | 4     | Default values, empty params fallback               |
| TestTrailingConfiguration    | 10    | Activation/trailing combos, parametrized            |
| TestTrailTypeConfiguration   | 7     | All 3 trail types, independence from entries        |
| TestTrailingOptimization     | 4     | Optimization ranges, grid, non-optimizable fields   |
| TestConfigOnlyBehavior       | 4     | Exit always False, cache contents, independence     |
| TestExtraDataPopulation      | 8     | use_trailing_stop flag, all 4 extra_data fields     |
| TestRSIFilterWithTrailing    | 3     | RSI range/cross/memory + trailing combos            |
| TestMACDFilterWithTrailing   | 3     | MACD cross/histogram + trailing combos              |
| TestRSIMACDComboWithTrailing | 2     | RSI+MACD dual entry + trailing stop                 |
| TestAllParamsFullScenario    | 3     | Every param explicit, defaults fallback, full cycle |

**Total: ~48 tests**

---

## Common AI Agent Mistakes

1. **Confusing param keys:** The frontend uses `activation_percent` but the cache
   stores it as `trailing_activation_percent` (prefixed with "trailing\_").

2. **Thinking trailing stop generates signals:** It does NOT. It's config-only.
   The engine reads config from `extra_data` and applies trailing stop bar-by-bar.

3. **Trying to connect trailing stop to strategy:** No connection needed.
   It's a standalone block that the engine auto-discovers via `extra_data`.

4. **Thinking trail_type is optimizable:** It's a select field — NOT optimizable.
   Only `activation_percent` and `trailing_percent` get min/max/step in optimizer.

5. **Ignoring extra_data:** Unlike Static SL/TP, Trailing Stop populates `extra_data`.
   Tests must verify both `_value_cache` AND `extra_data` contents.

6. **Only one block expected:** The adapter uses `break` after finding the first
   `trailing_stop_exit` block — only one is expected per strategy.
