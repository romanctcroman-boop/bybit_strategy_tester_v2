import requests

STRATEGY_ID = "fb9fa6d0-b431-4730-81b7-83767d76fd61"

# The UI shows 42 trades — test different end dates to reproduce
test_cases = [
    ("2026-03-04T21:30:00+00:00", "our script (43 trades)"),
    ("2026-03-04T17:30:00+00:00", "last trade exit time"),
    ("2026-03-04T00:00:00+00:00", "midnight today"),
    ("2026-03-03T23:59:00+00:00", "yesterday EOD"),
    ("2026-03-03T21:30:00+00:00", "yesterday 21:30"),
    ("2026-03-03T00:00:00+00:00", "yesterday midnight"),
]

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

print(f"{'End date':<30} {'Trades':>7} {'Net profit':>12} {'Win rate':>10}  Note")
print("-" * 75)
for end_date, note in test_cases:
    payload = {**base_payload, "end_date": end_date}
    try:
        resp = requests.post(
            f"http://localhost:8000/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest", json=payload, timeout=60
        )
        d = resp.json()
        trades = d.get("trades", d.get("closed_trades", []))
        m = d.get("metrics", {})
        print(
            f"  {end_date[:19]:<28} {len(trades):>7} {m.get('net_profit', 0):>12.2f} {m.get('win_rate', 0):>10.2f}%  {note}"
        )
    except Exception as e:
        print(f"  {end_date[:19]:<28}   ERROR: {e}")
