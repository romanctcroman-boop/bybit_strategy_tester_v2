import sys

import requests

sid = "963da4df-8e09-4c8e-a361-3143914b3581"
payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00",
    "end_date": "2026-03-05T23:59:59",
    "initial_capital": 10000,
    "leverage": 10,
    "commission": 0.0007,
    "direction": "both",
    "position_size": 0.1,
    "position_size_type": "percent",
    "stop_loss_pct": 0.132,
    "take_profit_pct": 0.066,
    "market_type": "linear",
    "pyramiding": 1,
}
url = f"http://localhost:8000/api/v1/strategy-builder/strategies/{sid}/backtest"
sys.stdout.write(f"POST {url}\n")
sys.stdout.flush()
r = requests.post(url, json=payload, timeout=180)
sys.stdout.write(f"Status: {r.status_code}\n")
sys.stdout.flush()

if r.status_code == 200:
    data = r.json()
    bt = data.get("backtest", data)
    sys.stdout.write(f"Backtest ID: {bt.get('id')}\n")
    sys.stdout.write(f"Status: {bt.get('status')}\n")
    sys.stdout.write(f"Total trades: {bt.get('total_trades')}\n")
    trades = bt.get("trades", [])
    sys.stdout.write(f"Trades in response: {len(trades)}\n")
    if trades:
        last = trades[-1]
        sys.stdout.write("--- Last trade ---\n")
        for k in (
            "exit_comment",
            "is_open",
            "entry_time",
            "entry_price",
            "exit_time",
            "exit_price",
            "direction",
            "pnl",
            "open_pnl",
        ):
            sys.stdout.write(f"  {k}: {last.get(k)}\n")
    metrics = bt.get("metrics", {})
    if metrics:
        sys.stdout.write("\n--- Key metrics ---\n")
        for k in ("net_profit", "total_trades", "open_trades", "win_rate"):
            sys.stdout.write(f"  {k}: {metrics.get(k)}\n")
else:
    sys.stdout.write(f"Error: {r.text[:2000]}\n")
sys.stdout.flush()
