"""Verify all 3 bug fixes were applied correctly."""

adapter_path = r"d:\bybit_strategy_tester_v2\backend\backtesting\strategy_builder_adapter.py"
router_path = r"d:\bybit_strategy_tester_v2\backend\api\routers\strategy_builder.py"

with open(adapter_path, encoding="utf-8") as f:
    adapter = f.read()

with open(router_path, encoding="utf-8") as f:
    router = f.read()

checks = [
    # Fix #1: close_by_time in _BLOCK_CATEGORY_MAP
    (adapter, '"close_by_time": "close_conditions"', "Fix #1a: close_by_time in _BLOCK_CATEGORY_MAP"),
    (adapter, '"close_channel": "close_conditions"', "Fix #1b: close_channel in _BLOCK_CATEGORY_MAP"),
    (adapter, '"close_ma_cross": "close_conditions"', "Fix #1c: close_ma_cross in _BLOCK_CATEGORY_MAP"),
    (adapter, '"close_rsi": "close_conditions"', "Fix #1d: close_rsi in _BLOCK_CATEGORY_MAP"),
    (adapter, '"close_stochastic": "close_conditions"', "Fix #1e: close_stochastic in _BLOCK_CATEGORY_MAP"),
    (adapter, '"close_psar": "close_conditions"', "Fix #1f: close_psar in _BLOCK_CATEGORY_MAP"),
    # Fix #2: bars_since_entry key
    (adapter, 'params.get("bars_since_entry"', "Fix #2: bars_since_entry key in _execute_close_condition"),
    # Fix #3: max_bars_in_trade in router
    (router, "block_max_bars_in_trade", "Fix #3a: block_max_bars_in_trade variable in router"),
    (router, '"bars_since_entry"', "Fix #3b: bars_since_entry key in router"),
    (router, "max_bars_in_trade=block_max_bars_in_trade", "Fix #3c: max_bars_in_trade passed to BacktestConfig"),
]

all_ok = True
for content, pattern, label in checks:
    if pattern in content:
        print(f"[OK] {label}")
    else:
        print(f"[FAIL] {label}")
        all_ok = False

print()
if all_ok:
    print("ALL 3 FIXES VERIFIED OK")
else:
    print("SOME FIXES MISSING - check above")
