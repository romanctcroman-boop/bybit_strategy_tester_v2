# AI Agent Knowledge: Close by Time Block

> **Block type:** `close_by_time`
> **Frontend menu group:** `close_conditions`
> **Category (set by frontend):** `close_conditions`
> **Handler:** `_execute_close_condition()`
> **Last updated:** 2026-02-04

---

## 1. Purpose

Close by Time forces position closure after a specified number of bars since entry.
Optionally restricts closing to profitable positions only (with min profit threshold).

**Original TradingView description:**

- Use Close By Time Since Order: `true/false`
- Close order after XX bars: `1-100`
- Close only with Profit: `true/false`
- Min Profit percent for Close %%: `0.1-20`

---

## 2. Frontend Defaults

From `strategy_builder.js` line 3678 (`blockDefaults`):

```javascript
close_by_time: {
    enabled: false,           // Master toggle (TV: "Use Close By Time Since Order")
    bars_since_entry: 10,     // Number of bars (TV: "Close order after XX bars", range 1-100)
    profit_only: false,       // Only close if profitable (TV: "Close only with Profit")
    min_profit_percent: 0     // Min profit % required (TV: "Min Profit percent for Close %%", range 0.1-20)
}
```

---

## 3. Category Dispatch Flow

```
Frontend: addBlockToCanvas("close_by_time", "close_conditions")
    → block.category = "close_conditions"
    → _execute_block() dispatches to _execute_close_condition()
    → _execute_close_condition("close_by_time", params, ohlcv, inputs)
    → Returns {exit: pd.Series(False), max_bars: pd.Series([bars]*n)}
```

### ⚠️ NOT in `_BLOCK_CATEGORY_MAP`

`close_by_time` is **NOT** registered in `_BLOCK_CATEGORY_MAP`. If the frontend
doesn't send `category`, `_infer_category()` falls back to `"indicator"` (WRONG).

The frontend **always** sends `category="close_conditions"`, so this works in practice.

---

## 4. Handler Output

From `strategy_builder_adapter.py` lines 2985-2991:

```python
if close_type == "close_by_time":
    bars = params.get("bars", 10)
    result["exit"] = pd.Series([False] * n, index=idx)
    result["max_bars"] = pd.Series([bars] * n, index=idx)
```

**Output dict:**

| Key        | Type              | Value               | Description                         |
| ---------- | ----------------- | ------------------- | ----------------------------------- |
| `exit`     | `pd.Series[bool]` | All `False`         | Engine implements actual closing    |
| `max_bars` | `pd.Series[int]`  | Constant `[bars]*n` | Number of bars after which to close |

---

## 5. ⚠️ KNOWN PARAM NAME MISMATCH

| Layer                  | Param Name         | Default |
| ---------------------- | ------------------ | ------- |
| Frontend blockDefaults | `bars_since_entry` | `10`    |
| Handler `params.get()` | `bars`             | `10`    |

**Impact:** When frontend sends `{bars_since_entry: 30}`, the handler ignores it
and uses `params.get("bars", 10)` → always gets default `10`.

**Workaround:** The engine may read `bars_since_entry` directly from block params
(bypassing the handler). Send `bars` to make the handler work correctly.

---

## 6. ⚠️ KNOWN DCA CONFIG MISMATCH

`extract_dca_config()` scans blocks by `block_type`:

| Check     | Our block_type    | Expected block_type |
| --------- | ----------------- | ------------------- |
| Line 3336 | `"close_by_time"` | `"time_bars_close"` |

**Result:** Our block's params are **NOT** auto-extracted into:

- `time_bars_close_enable`
- `close_after_bars` (default 20)
- `close_only_profit` (default True)
- `close_min_profit` (default 0.5)
- `close_max_bars` (default 100)

**Workaround:** Block params are still accessible via `adapter.blocks[block_id]["params"]`.

---

## 7. Optimizable Parameters

| Parameter            | Optimizable | Range      | Notes                         |
| -------------------- | ----------- | ---------- | ----------------------------- |
| `bars_since_entry`   | ✅ Yes      | 1-100      | Main optimization target      |
| `min_profit_percent` | ✅ Possible | 0.1-20     | Secondary optimization target |
| `enabled`            | ❌ No       | true/false | Toggle only                   |
| `profit_only`        | ❌ No       | true/false | Toggle only                   |

---

## 8. Comparison: Our Block vs TradingView Original

| Feature        | TradingView Original                | Our Implementation                         |
| -------------- | ----------------------------------- | ------------------------------------------ |
| Master toggle  | "Use Close By Time Since Order"     | `enabled` (default false)                  |
| Bar count      | "Close order after XX bars" (1-100) | `bars_since_entry` (default 10)            |
| Profit filter  | "Close only with Profit"            | `profit_only` (default false)              |
| Min profit     | "Min Profit percent" (0.1-20)       | `min_profit_percent` (default 0)           |
| Handler param  | N/A                                 | reads `"bars"` not `"bars_since_entry"` ⚠️ |
| DCA block_type | N/A                                 | `"time_bars_close"` ≠ `"close_by_time"` ⚠️ |

---

## 9. Test Coverage

Test file: `tests/ai_agents/test_close_by_time_ai_agents.py`

| Part | Class                             | Tests | Focus                               |
| ---- | --------------------------------- | ----- | ----------------------------------- |
| 1    | `TestCloseByTimeDefaults`         | 5     | Default values, enabled toggle      |
| 2    | `TestCloseByTimeCategoryDispatch` | 5     | Category mapping, fallback behavior |
| 3    | `TestCloseByTimeHandlerOutput`    | 6     | exit/max_bars series format         |
| 4    | `TestParamNameMismatch`           | 5     | bars vs bars_since_entry            |
| 5    | `TestExtractDCAConfig`            | 5     | DCA config type mismatch            |
| 6    | `TestCloseByTimeOptimization`     | 4     | Optimization sweeps                 |
| 7    | `TestRSIWithCloseByTime`          | 3     | RSI + Close by Time combos          |
| 8    | `TestMACDWithCloseByTime`         | 2     | MACD + Close by Time combos         |
| 9    | `TestTradingViewComparison`       | 4     | TV original vs our block            |
| 10   | `TestEdgeCases`                   | 7     | Boundaries, stability, standalone   |
| 11   | `TestFullScenario`                | 3     | Complete end-to-end scenarios       |

**Total: ~49 tests**

---

## 10. Key Takeaways for AI Agents

1. **Category MUST come from frontend** — block is not in `_BLOCK_CATEGORY_MAP`
2. **Handler reads `"bars"`** not `"bars_since_entry"` — param name mismatch
3. **DCA extract expects `"time_bars_close"`** not `"close_by_time"` — type mismatch
4. **Exit series is always False** — engine implements actual bar-counting logic
5. **max_bars is a constant series** — same value repeated for all rows
6. **Block works standalone** — no connections to strategy node needed
7. **profit_only + min_profit_percent** control whether closing requires profit
