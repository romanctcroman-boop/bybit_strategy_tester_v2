"""Verify strategy was updated correctly."""

import json
import urllib.request

STRATEGY_ID = "824561e0-5e27-4be4-a33a-b064a726d14c"
BASE = "http://localhost:8000"
EXPECTED = {
    "period": 15,
    "long_rsi_more": 32.0,
    "cross_long_level": 25.0,
    "cross_short_level": 65.0,
    "stop_loss_percent": 3.0,
    "take_profit_percent": 5.0,
}

url = f"{BASE}/api/v1/strategy-builder/strategies/{STRATEGY_ID}"
with urllib.request.urlopen(url, timeout=10) as resp:
    strategy = json.loads(resp.read())

print(f"Strategy: {strategy['name']}")
all_ok = True
for block in strategy["builder_graph"]["blocks"]:
    bid = block["id"]
    params = block.get("params", {})
    for key, expected_val in EXPECTED.items():
        if key in params:
            actual = params[key]
            ok = abs(float(actual) - float(expected_val)) < 0.001
            status = "✅" if ok else "❌"
            print(f"  {status} {bid}.{key}: {actual} (expected {expected_val})")
            if not ok:
                all_ok = False

if all_ok:
    print("\n✅ All top-1 params saved correctly!")
else:
    print("\n❌ Some params did not save correctly")
