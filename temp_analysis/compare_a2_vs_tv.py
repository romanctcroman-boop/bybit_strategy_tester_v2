import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
bt_id = "68758d14"

# Get the full backtest ID
cur = conn.execute("SELECT id FROM backtests WHERE id LIKE ?", (bt_id + "%",))
full_bt_id = cur.fetchone()[0]
print(f"Backtest ID: {full_bt_id}")

# Get all trades for this backtest
cur = conn.execute(
    "SELECT trade_id, side, entry_time, entry_price, exit_time, exit_price, "
    "pnl, pnl_percent, entry_signal, exit_signal, fees "
    "FROM trades WHERE backtest_id = ? ORDER BY entry_time ASC",
    (full_bt_id,),
)
trades = cur.fetchall()
print(f"Total trades in DB: {len(trades)}")
print()

# TV reference trades (from й4.csv, UTC times — TV times were UTC+3, so subtract 3h)
tv_trades = [
    # (num, side, entry_time_utc, entry_price, exit_time_utc, exit_signal, pnl)
    (1, "Short", "2025-01-01 13:30", 3334.62, "2025-01-08 17:00", "TP", 21.61),
    (
        2,
        "Short",
        "2025-01-09 00:00",
        3322.53,
        "2025-01-09 13:30",
        "TP",
        21.61,
    ),  # was 02:30 UTC+3 = 23:30 UTC prev day? let me check
    (3, "Short", "2025-01-09 17:30", 3285.67, "2025-01-09 19:30", "TP", 21.62),
    (4, "Short", "2025-01-10 21:00", 3257.99, "2025-01-13 06:30", "TP", 21.62),
    (5, "Long", "2025-01-13 13:30", 3075.39, "2025-01-14 00:00", "TP", 21.58),
]

print("=== TV Reference Trades (UTC) vs Our Trades ===")
print(
    f"{'#':>3} | {'Side':5} | {'Our Entry Time':22} | {'Our Price':10} | {'TV Price':10} | {'Δ Price':8} | {'Our PnL':8} | {'TV PnL':8} | {'Our Exit':22} | {'Our ExitSig':12}"
)
print("-" * 140)

for i, trade in enumerate(trades[:15]):
    tid, side, entry_time, entry_price, exit_time, exit_price, pnl, pnl_pct, entry_sig, exit_sig, fees = trade
    if i < len(tv_trades):
        tv = tv_trades[i]
        delta = entry_price - tv[3]
        print(
            f"{i + 1:>3} | {side:5} | {str(entry_time):22} | {entry_price:10.4f} | {tv[3]:10.2f} | {delta:+8.4f} | {pnl:8.2f} | {tv[6]:8.2f} | {str(exit_time):22} | {exit_sig or '':12}"
        )
    else:
        print(
            f"{i + 1:>3} | {side:5} | {str(entry_time):22} | {entry_price:10.4f} | {'N/A':10} | {'N/A':8} | {pnl:8.2f} | {'N/A':8} | {str(exit_time):22} | {exit_sig or '':12}"
        )

# Summary comparison
print("\n=== Aggregate Comparison ===")
our_net = sum(t[6] for t in trades)
our_wins = sum(1 for t in trades if t[6] > 0)
our_longs = sum(1 for t in trades if t[1] == "long")
our_shorts = sum(1 for t in trades if t[1] == "short")
our_fees = sum(t[10] or 0 for t in trades)

print(f"{'Metric':<25} | {'Ours':>15} | {'TV':>15} | {'Match?':>8}")
print("-" * 70)
print(f"{'Total trades':<25} | {len(trades):>15} | {155:>15} | {'✅' if len(trades) == 155 else '❌'}")
print(f"{'Net profit':<25} | {our_net:>15.2f} | {1023.57:>15.2f} | {'✅' if abs(our_net - 1023.57) < 1 else '❌'}")
print(
    f"{'Win rate %':<25} | {our_wins / len(trades) * 100:>15.2f} | {90.32:>15.2f} | {'✅' if abs(our_wins / len(trades) * 100 - 90.32) < 0.1 else '❌'}"
)
print(f"{'Long trades':<25} | {our_longs:>15} | {31:>15} | {'✅' if our_longs == 31 else '❌'}")
print(f"{'Short trades':<25} | {our_shorts:>15} | {124:>15} | {'✅' if our_shorts == 124 else '❌'}")
print(f"{'Total fees':<25} | {our_fees:>15.2f} | {216.45:>15.2f} | {'✅' if abs(our_fees - 216.45) < 1 else '❌'}")

# Get aggregate metrics from backtests table
cur = conn.execute(
    "SELECT net_profit, total_trades, win_rate, sharpe_ratio, sortino_ratio, "
    "profit_factor, long_trades, short_trades, total_commission, gross_profit, gross_loss, "
    "max_drawdown, avg_bars_in_trade "
    "FROM backtests WHERE id = ?",
    (full_bt_id,),
)
bt = cur.fetchone()
print(f"\n=== Backtest Table Metrics ===")
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
for label, our_val, tv_val in zip(labels, bt, tv_vals, strict=False):
    if our_val is not None and tv_val is not None:
        try:
            match = "✅" if abs(float(our_val) - float(tv_val)) / max(abs(float(tv_val)), 0.001) < 0.02 else "❌"
        except Exception:
            match = "?"
        print(f"  {label:<25}: ours={our_val:.4f}  tv={tv_val:.4f}  {match}")

conn.close()
