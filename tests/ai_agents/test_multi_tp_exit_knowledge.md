# AI Agent Knowledge: Multi TP Exit Block

> **Last Updated:** 2026-02-16
> **Test File:** `tests/ai_agents/test_multi_tp_exit_ai_agents.py`
> **Block Type:** `multi_tp_exit`
> **Frontend Category:** `exits` (sends `category: 'exit'`)

---

## Overview

The **Multi TP Exit** block configures multiple Take Profit levels for partial position
closing. It has **3 TP levels** (compared to TradingView's original 4 levels):

- **TP1:** Always enabled (no toggle checkbox)
- **TP2:** Controlled by `use_tp2` checkbox (default: `true`)
- **TP3:** Controlled by `use_tp3` checkbox (default: `true`)

Each TP level specifies a **target percent** (how far price must move to trigger TP)
and a **close percent** (what fraction of the position to close at that level).

---

## Parameters (8 fields total)

### TP1 Section (always enabled)

| Parameter         | Type   | Default | Optimizable | Range  | Description                   |
| ----------------- | ------ | ------- | ----------- | ------ | ----------------------------- |
| tp1_percent       | number | 1.0     | **Yes**     | 0.5-30 | Target profit % to trigger TP |
| tp1_close_percent | number | 33      | No          | 0.5-30 | % of position to close at TP1 |

### TP2 Section (toggle: use_tp2)

| Parameter         | Type     | Default | Optimizable | Range  | Description              |
| ----------------- | -------- | ------- | ----------- | ------ | ------------------------ |
| use_tp2           | checkbox | true    | No          | -      | Enable/disable TP2 level |
| tp2_percent       | number   | 2.0     | **Yes**     | 0.5-30 | Target profit % for TP2  |
| tp2_close_percent | number   | 33      | No          | 0.5-30 | % of position at TP2     |

### TP3 Section (toggle: use_tp3)

| Parameter         | Type     | Default | Optimizable | Range  | Description              |
| ----------------- | -------- | ------- | ----------- | ------ | ------------------------ |
| use_tp3           | checkbox | true    | No          | -      | Enable/disable TP3 level |
| tp3_percent       | number   | 3.0     | **Yes**     | 0.5-30 | Target profit % for TP3  |
| tp3_close_percent | number   | 34      | No          | 0.5-30 | % of position at TP3     |

### Default Close Percent Allocation

TP1: 33% + TP2: 33% + TP3: 34% = 100% (full position)

---

## Frontend Configuration

### Block Defaults (strategy_builder.js)

```javascript
multi_tp_exit: {
    tp1_percent: 1.0,
    tp1_close_percent: 33,
    tp2_percent: 2.0,
    tp2_close_percent: 33,
    tp3_percent: 3.0,
    tp3_close_percent: 34,
    use_tp2: true,
    use_tp3: true
}
```

### Custom Layout Sections

3 sections (TP1, TP2, TP3). TP2/TP3 sections include a `use_tp{n}` checkbox.
Only `tp{n}_percent` fields have `optimizable: true`. Close percent fields are NOT optimizable.

### Optimization Mode

Only **3 target percent fields** are optimizable (min/max/step):

- `tp1_percent`, `tp2_percent`, `tp3_percent` (range 0.5-30)

Close percent fields (`tp{n}_close_percent`) are NOT optimizable.

---

## Backend Architecture

### Dual Dispatch Paths

The multi_tp_exit block has **two possible dispatch paths** depending on the `category`
field in the graph data:

**Path A - Frontend Default (category='exit'):**

The frontend always sends `category: 'exit'` for exit blocks. The adapter sees this
and dispatches to `_execute_exit()`, which has a handler for `multi_tp_exit`:

```
_execute_exit("multi_tp_exit", params, ohlcv, inputs)
  -> exit = pd.Series(False)  (no dynamic triggers)
  -> multi_tp_config = [{percent, allocation}, ...]
```

The handler produces:

- `exit`: pd.Series of all False (no dynamic triggers, engine handles TP)
- `multi_tp_config`: list of 3 dicts with `percent` and `allocation` keys

**Path B - Category Missing (fallback inference):**

When category is missing, `_infer_category()` uses `_BLOCK_CATEGORY_MAP`:

```
"multi_tp_exit" -> "multiple_tp" -> return {}
```

This returns empty dict (pure config-only).

### KNOWN PARAM NAME MISMATCH

The `_execute_exit` handler reads `tp{n}_allocation` but the frontend sends
`tp{n}_close_percent`. This means `multi_tp_config` in the cache always uses
the handler defaults (30, 30, 40), not the frontend values.

```
Handler reads:  params.get("tp1_allocation", 30)   -> falls to default 30
Frontend sends: params["tp1_close_percent"] = 80    -> not read by handler
```

The `tp{n}_close_percent` values are still accessible in `adapter.blocks[block_id]["params"]`.

### \_value_cache Behavior

```
Path A (category='exit'):
  _value_cache["multi_tp_1"] = {
      'exit': pd.Series(False),
      'multi_tp_config': [{percent: 1.0, allocation: 30}, ...]
  }

Path B (category missing):
  _value_cache["multi_tp_1"] = {}
```

### extract_dca_config() - Known Block Type Mismatch

`extract_dca_config()` scans blocks with `category=="multiple_tp"` and checks for
`block_type=="multi_tp_levels"`. Our block type is `"multi_tp_exit"`, so this
branch is NOT reached. Additionally, it expects `params.levels[]` array format,
but our frontend sends flat params.

Result: `dca_multi_tp_enabled` stays `False` (default). Block params are only
accessible directly via `adapter.blocks[block_id]["params"]`.

### DCA Config Defaults (always present)

```
dca_multi_tp_enabled: False
dca_tp1_percent: 0.5,  dca_tp1_close_percent: 25.0
dca_tp2_percent: 1.0,  dca_tp2_close_percent: 25.0
dca_tp3_percent: 2.0,  dca_tp3_close_percent: 25.0
dca_tp4_percent: 3.0,  dca_tp4_close_percent: 25.0
```

---

## Comparison with TradingView Original

| Feature                  | Our Implementation       | TradingView Original        |
| ------------------------ | ------------------------ | --------------------------- |
| TP Levels                | 3 (TP1, TP2, TP3)        | 4 (TP1, TP2, TP3, TP4)      |
| Master Toggle            | None (block presence)    | "Use Multiple Take Profits" |
| TP1 Toggle               | Always enabled           | Always enabled              |
| Last TP closes remainder | TP3 (manual allocation)  | TP4 (always closes all)     |
| Target Range             | 0.5% - 30%               | 0.5% - 30%                  |
| Param Format             | Flat (tp1_percent, etc.) | Flat (separate fields)      |

---

## Test Coverage Summary

| Test Class                 | Tests | What It Covers                                         |
| -------------------------- | ----- | ------------------------------------------------------ |
| TestMultiTPExitDefaults    | 5     | Default values, close% sum=100, config-only            |
| TestMultiTPCategoryMapping | 4     | Dual dispatch paths, auto-inference, cache content     |
| TestTPLevelConfiguration   | 6     | TP1 always on, TP2/TP3 toggles, custom targets         |
| TestClosePercentAllocation | 5     | Position allocation: 33/33/34, 80/10/10, etc.          |
| TestExtractDCAConfig       | 5     | DCA integration, block_type mismatch, levels fmt       |
| TestMultiTPOptimization    | 4     | Optimizable target%, non-optimizable close%            |
| TestConfigOnlyBehavior     | 5     | Extra data, connections, cache content, param mismatch |
| TestTPToggles              | 5     | use_tp2/use_tp3 on/off combinations                    |
| TestMultiTPWithRSI         | 3     | RSI + Multi TP combined scenarios                      |
| TestMultiTPWithMACD        | 3     | MACD + Multi TP combined scenarios                     |
| TestTradingViewComparison  | 4     | 3 levels vs 4, no master toggle, DCA 4-level           |
| TestEdgeCases              | 8     | Min/max targets, empty params, fractional, stable      |
| TestFullScenario           | 3     | Complete RSI/MACD + Multi TP + DCA config              |

**Total: 60 tests**

---

## Quick Reference for AI Agents

1. **Block type**: `multi_tp_exit`
2. **Frontend category**: `'exit'` (dispatched to `_execute_exit()`)
3. **Fallback category**: `'multiple_tp'` (when category missing, returns `{}`)
4. **TP1**: always on (no toggle)
5. **TP2/TP3**: controlled by `use_tp2` / `use_tp3` checkboxes
6. **Close percents**: should sum to 100% for active TP levels
7. **Optimizable**: only `tp{n}_percent` (target), NOT `tp{n}_close_percent`
8. **Param mismatch**: handler reads `tp{n}_allocation`, frontend sends `tp{n}_close_percent`
9. **DCA mismatch**: `extract_dca_config` checks `block_type=="multi_tp_levels"` (not our type)
10. **Access params**: `adapter.blocks[block_id]["params"]` (always works)
