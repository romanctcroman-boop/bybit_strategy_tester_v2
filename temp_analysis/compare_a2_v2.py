import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
bt_id = "68758d14"

# Get the full backtest ID
cur = conn.execute("SELECT id FROM backtests WHERE id LIKE ?", (bt_id + "%",))
full_bt_id = cur.fetchone()[0]

# Get trades JSON from backtest row
cur = conn.execute(
    "SELECT trades, metrics_json, net_profit, total_trades, win_rate, sharpe_ratio, "
    "sortino_ratio, profit_factor, long_trades, short_trades, total_commission, "
    "gross_profit, gross_loss, max_drawdown, avg_bars_in_trade "
    "FROM backtests WHERE id = ?",
    (full_bt_id,),
)
row = cur.fetchone()
trades_raw = row[0]

print(f"trades field type: {type(trades_raw)}, len: {len(trades_raw) if trades_raw else 'None'}")

if trades_raw:
    trades = json.loads(trades_raw)
    print(f"Number of trades: {len(trades)}")
    if trades:
        print(f"\nFirst trade keys: {list(trades[0].keys())}")
        print("\nFirst 3 trades:")
        for t in trades[:3]:
            print(f"  {t}")
else:
    print("No trades JSON found — checking metrics_json...")
    if row[1]:
        metrics = json.loads(row[1])
        print(f"metrics_json keys: {list(metrics.keys())[:20]}")

# Print aggregate metrics
print("\n=== Aggregate Metrics from backtests table ===")
labels = [
    "net_profit",
    "total_trades",
    "win_rate",
    "sharpe_ratio",
    "sortino_ratio",
    "profit_factor",
    "long_trades",
    "short_trades",
    "total_commission",
    "gross_profit",
    "gross_loss",
    "max_drawdown",
    "avg_bars_in_trade",
]
tv_vals = [1023.57, 155, 90.32, 0.35, 0.587, 1.511, 31, 124, 216.45, 3025.18, 2001.62, 670.46, 98]
for label, our_val, tv_val in zip(labels, row[2:], tv_vals, strict=False):
    if our_val is not None and tv_val is not None:
        try:
            pct_diff = abs(float(our_val) - float(tv_val)) / max(abs(float(tv_val)), 0.001) * 100
            match = "✅" if pct_diff < 2 else f"❌ ({pct_diff:.1f}% diff)"
        except Exception:
            match = "?"
        print(f"  {label:<25}: ours={our_val:<12}  tv={tv_val:<12}  {match}")

conn.close()
