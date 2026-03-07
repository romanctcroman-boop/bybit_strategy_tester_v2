import json

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
print("Status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    m = data.get("metrics", {})
    trades = data.get("trades", [])
    total_orders = sum(t.get("dca_orders_count", t.get("orders_filled", 1)) for t in trades)
    avg_orders = total_orders / max(len(trades), 1)

    print(f"Total trades:      {len(trades)}")
    print(f"Win rate:          {m.get('win_rate', '?')}")
    print(f"Net profit %:      {m.get('net_profit_percent', m.get('net_pnl_pct', '?'))}")
    print(f"Max drawdown %:    {m.get('max_drawdown_percent', '?')}")
    print(f"Avg orders/trade:  {avg_orders:.2f}")
    print(f"Total signals:     {data.get('total_signals', '?')}")
    print(f"Total ord filled:  {data.get('total_orders_filled', total_orders)}")

    print("\nFirst 5 trades:")
    for i, t in enumerate(trades[:5]):
        n = t.get("dca_orders_count", t.get("orders_filled", "?"))
        entry = t.get("entry_price", "?")
        pnl = t.get("pnl_percent", "?")
        reason = t.get("exit_reason", "?")
        bars = t.get("bars_held", t.get("duration_bars", "?"))
        print(f"  #{i + 1}: entry={entry} orders={n} pnl%={pnl} bars={bars} reason={reason}")
else:
    print(r.text[:1500])
