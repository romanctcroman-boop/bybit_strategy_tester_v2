import requests

STRATEGY_ID = "3fc04505-a70d-4ede-98ee-275369d1008f"

base_payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00+00:00",
    "initial_capital": 10000,
    "commission": 0.0007,
    "slippage": 0.0,
    "position_size": 0.1,
    "position_size_type": "percent",
    "leverage": 10,
    "pyramiding": 1,
    "direction": "both",
    "market_type": "linear",
}

test_cases = [
    "2026-03-04",  # UI was sending this (no time = T00:00:00)
    "2026-03-04T00:00:00",  # explicit midnight
    "2026-03-04T23:59:59",  # FIXED: end of day
    "2026-03-04T21:30:00+00:00",  # our script value
]

print(f"{'End date':<35} {'Trades':>7} {'Net profit':>12} {'Win rate':>10}")
print("-" * 70)
for end_date in test_cases:
    payload = {**base_payload, "end_date": end_date}
    resp = requests.post(
        f"http://localhost:8000/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest", json=payload, timeout=60
    )
    if resp.status_code != 200 or not resp.text.strip():
        print(f"  {end_date:<33}   HTTP {resp.status_code}: {resp.text[:80]}")
        continue
    d = resp.json()
    trades = d.get("trades", d.get("closed_trades", []))
    m = d.get("metrics", {})
    print(f"  {end_date:<33} {len(trades):>7} {m.get('net_profit', 0):>12.2f} {m.get('win_rate', 0):>10.2f}%")
