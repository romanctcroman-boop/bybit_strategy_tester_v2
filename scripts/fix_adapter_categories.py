"""Fix missing close_conditions entries in _BLOCK_CATEGORY_MAP and bars param key."""

adapter_path = r"d:\bybit_strategy_tester_v2\backend\backtesting\strategy_builder_adapter.py"

with open(adapter_path, encoding="utf-8") as f:
    content = f.read()

# ── Fix #1: Add close_conditions to _BLOCK_CATEGORY_MAP ────────────────────
# Insert after the "divergence" entry (line 504), before "# Universal filters"
OLD_MAP = '        "divergence": "divergence",\n        # Universal filters'
NEW_MAP = (
    '        "divergence": "divergence",\n'
    "        # Close condition blocks (Bug fix: were missing from map; _infer_category\n"
    '        # fell back to "indicator" so _execute_close_condition was never called)\n'
    '        "close_by_time": "close_conditions",\n'
    '        "close_channel": "close_conditions",\n'
    '        "close_ma_cross": "close_conditions",\n'
    '        "close_rsi": "close_conditions",\n'
    '        "close_stochastic": "close_conditions",\n'
    '        "close_psar": "close_conditions",\n'
    "        # Universal filters"
)

if OLD_MAP in content:
    content = content.replace(OLD_MAP, NEW_MAP, 1)
    print("[OK] Fix #1 applied: close_conditions added to _BLOCK_CATEGORY_MAP")
else:
    print("[WARN] Fix #1: pattern not found, skipping")

# ── Fix #2: bars_since_entry key in _execute_close_condition ───────────────
# The frontend stores "bars_since_entry" but adapter reads params.get("bars", 10)
OLD_BARS = '            bars = params.get("bars", 10)\n            # Return config, actual implementation in engine'
NEW_BARS = (
    '            # Bug fix: frontend stores key as "bars_since_entry", not "bars"\n'
    '            bars = int(params.get("bars_since_entry", params.get("bars", 10)))\n'
    "            # Return config, actual implementation in engine"
)

if OLD_BARS in content:
    content = content.replace(OLD_BARS, NEW_BARS, 1)
    print("[OK] Fix #2 applied: bars_since_entry key fixed")
else:
    print("[WARN] Fix #2: pattern not found, skipping")

with open(adapter_path, "w", encoding="utf-8") as f:
    f.write(content)

print("[DONE] strategy_builder_adapter.py updated")
