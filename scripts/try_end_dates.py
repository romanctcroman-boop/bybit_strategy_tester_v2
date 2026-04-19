"""Run backtest with extended end date to check for missing trade."""

import requests

strategy_id = "01cd8861-60eb-40dd-a9a9-8baa6f2db0fa"

# Try different end dates
for end_date in ["2026-02-25T00:00:00Z", "2026-02-25T12:00:00Z", "2026-02-26T00:00:00Z"]:
    payload = {
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": end_date,
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
    res = data.get("results", {})
    print(
        f"end_date={end_date}: trades={res.get('total_trades')} profit={res.get('net_profit'):.4f} win_rate={res.get('win_rate'):.4f}"
    )
