"""Verify top-1 params via server API backtest endpoint."""

import copy
import json
import urllib.request

STRATEGY_ID = "824561e0-5e27-4be4-a33a-b064a726d14c"
TOP1_PARAMS = {
    "block_1772832197062_q10k0.period": 15,
    "block_1772832197062_q10k0.long_rsi_more": 32.0,
    "block_1772832197062_q10k0.cross_long_level": 25.0,
    "block_1772832197062_q10k0.cross_short_level": 65.0,
    "block_1772832203873_c5bgo.stop_loss_percent": 3.0,
    "block_1772832203873_c5bgo.take_profit_percent": 5.0,
}
BASE = "http://localhost:8000"

# Fetch strategy graph
url = f"{BASE}/api/v1/strategy-builder/strategies/{STRATEGY_ID}"
with urllib.request.urlopen(url, timeout=10) as resp:
    strategy = json.loads(resp.read())

graph = copy.deepcopy(strategy["builder_graph"])
symbol = strategy["symbol"]
timeframe = strategy["timeframe"]
print(f"Strategy: {strategy['name']} | {symbol} {timeframe}")

# Apply top-1 params
for param_path, value in TOP1_PARAMS.items():
    block_id, param_key = param_path.split(".", 1)
    for block in graph["blocks"]:
        if block["id"] == block_id:
            block.setdefault("params", {})[param_key] = value
            print(f"  Set {block_id}.{param_key} = {value}")

graph["interval"] = timeframe

# Try the strategy-builder backtest endpoint
payload = {
    "strategy_graph": graph,
    "symbol": symbol,
    "interval": timeframe,
    "start_date": "2025-01-01",
    "end_date": "2026-03-01",
    "initial_capital": 10000.0,
    "position_size": 0.1,
    "leverage": 10.0,
    "commission_value": 0.0007,
    "direction": "both",
    "market_type": "linear",
}

# Try different endpoints
endpoints = [
    "/api/v1/strategy-builder/run",
    "/api/strategy-builder/run",
    f"/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest",
]

data = json.dumps(payload).encode()

for ep in endpoints:
    url = BASE + ep
    print(f"\nTrying {ep}...")
    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            print(f"  SUCCESS! Keys: {list(result.keys())[:8]}")
            m = result.get("metrics") or result.get("performance_metrics") or result
            print(f"  Total trades:  {m.get('total_trades', 'N/A')}")
            np_val = m.get("net_profit", 0)
            tr_val = m.get("total_return", 0)
            print(f"  Net profit:    ${np_val:.2f} ({tr_val:.2f}%)")
            print(f"  Sharpe:        {m.get('sharpe_ratio', 0):.4f}")
            print(f"  Win rate:      {m.get('win_rate', 0):.2f}%")
            print(f"  Max drawdown:  {m.get('max_drawdown', 0):.2f}%")
            print("\nExpected (Numba): 43T, $460.89 (4.62%), Sharpe=0.268, WR=53.5%, DD=1.73%")
            break
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  HTTP {e.code}: {body}")
    except Exception as e:
        print(f"  Error: {e}")
