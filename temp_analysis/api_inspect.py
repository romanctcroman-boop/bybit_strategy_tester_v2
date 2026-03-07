import requests

payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-03-06T00:00:00Z",
    "initial_capital": 10000,
    "leverage": 10,
    "position_size": 10,
    "commission": 0.0007,
}

strategy_id = "f46c7cc3-1098-483a-a177-67b7867dd72e"
r = requests.post(
    f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
    json=payload,
    timeout=120,
)
data = r.json()
trades = data.get("trades", [])
m = data.get("metrics", {})

# Print top-level keys
print("=== TOP LEVEL KEYS ===")
print([k for k in data.keys()])

print("\n=== METRICS KEYS ===")
print(list(m.keys()) if isinstance(m, dict) else type(m))

print("\n=== FIRST TRADE KEYS ===")
if trades:
    print(list(trades[0].keys()))
    print("First trade:", {k: trades[0][k] for k in list(trades[0].keys())[:15]})

# Find DCA-related keys
print("\n=== DCA-related metrics ===")
if isinstance(m, dict):
    for k, v in m.items():
        if any(x in k.lower() for x in ["dca", "order", "grid", "avg", "trade"]):
            print(f"  {k}: {v}")
