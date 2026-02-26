"""Run backtest with 2026-02-25T12:00Z end date and compare full metrics."""

import requests

strategy_id = "01cd8861-60eb-40dd-a9a9-8baa6f2db0fa"
payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-02-25T13:30:00Z",  # use full available data
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
print("Backtest results vs TV target:")
print(f"{'Metric':30s} {'Our':>15s} {'TV Target':>15s}")
print("-" * 65)
metrics = [
    ("Total trades", res.get("total_trades"), 151),
    ("Net profit", res.get("net_profit"), 1091.53),
    ("Win rate", res.get("win_rate"), 90.73),
    ("Max drawdown %", res.get("max_drawdown_pct"), 6.00),
    ("Sharpe ratio", res.get("sharpe_ratio"), 0.357),
    ("Profit factor", res.get("profit_factor"), 1.584),
]
for name, our, tv in metrics:
    our_str = f"{our:.4f}" if isinstance(our, float) else str(our)
    tv_str = f"{tv:.4f}" if isinstance(tv, float) else str(tv)
    print(f"  {name:28s} {our_str:>15s} {tv_str:>15s}")
