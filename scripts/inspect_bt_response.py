"""Run backtest and dump structure of response."""

import json

import requests

strategy_id = "01cd8861-60eb-40dd-a9a9-8baa6f2db0fa"
payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-02-25T00:00:00Z",
    "initial_capital": 10000.0,
    "leverage": 10,
    "position_size": 0.1,
    "commission": 0.0007,
    "slippage": 0.0,
    "pyramiding": 1,
    "direction": "both",
    "stop_loss": 0.132,
    "take_profit": 0.023,
    "market_type": "linear",
}

r = requests.post(
    f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/backtest", json=payload, timeout=120
)
data = r.json()

# Show top-level keys
print("Top-level keys:", list(data.keys()))

# Check results sub-keys
if "results" in data:
    print("\nResults keys:", list(data["results"].keys()))
    res = data["results"]
    for k, v in res.items():
        if not isinstance(v, (list, dict)):
            print(f"  {k}: {v}")

# Check for trades in different locations
for key in ["trades", "trade_list", "closed_trades"]:
    if key in data:
        print(f"\n'{key}' has {len(data[key])} items")
        if data[key]:
            print("First trade keys:", list(data[key][0].keys()))
    if "results" in data and key in data["results"]:
        print(f"\nresults['{key}'] has {len(data['results'][key])} items")
        if data["results"][key]:
            print("First trade keys:", list(data["results"][key][0].keys()))
