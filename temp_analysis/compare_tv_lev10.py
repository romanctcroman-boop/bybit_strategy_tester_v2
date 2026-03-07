import sys

sys.path.insert(0, ".")
import requests

# Test with leverage=10 to match TradingView
r = requests.post(
    "http://localhost:8000/api/v1/strategy-builder/strategies/f46c7cc3-1098-483a-a177-67b7867dd72e/backtest",
    json={
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2026-03-07T00:00:00Z",
        "initial_capital": 10000.0,
        "position_size": 0.1,
        "leverage": 10,
        "direction": "both",
        "commission": 0.0007,
    },
    timeout=180,
)
data = r.json()
trades = data.get("trades", [])
metrics = data.get("metrics", {})
print("=== Leverage=10 ===")
print("Total trades:", len(trades))
print("net_profit:", round(metrics.get("net_profit", 0), 2))
print("win_rate:", round(metrics.get("win_rate", 0), 2))

print("\nFirst 5 trades (leverage=10):")
for t in trades[:5]:
    n = t.get("trade_number", "?")
    ep = t.get("entry_price", 0)
    sz = t.get("size", 0)
    pnl = t.get("pnl", 0)
    odf = t.get("dca_orders_filled", 0)
    print(f"  #{n}  entry={ep:.2f}  size={sz:.4f}  pnl={pnl:.2f}  orders_filled={odf}")

print("\n=== TradingView CSV reference ===")
csv_ref = [
    (1, 3564.93, 16.83, 53959.48, 3),
    (2, 3356.07, 11.92, 35998.05, 3),
    (3, 3326.43, 12.02, 35736.61, 3),
    (4, 3274.38, 18.32, 53166.10, 4),
    (5, 3261.92, 6.18, 369.80, 1),
]
for n, ep, sz, pnl, odf in csv_ref:
    print(f"  #{n}  entry={ep:.2f}  size={sz:.2f}  pnl={pnl:.2f}  orders_filled~={odf}")
