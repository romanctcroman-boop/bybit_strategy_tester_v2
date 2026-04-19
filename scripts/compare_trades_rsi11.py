"""
Deep diagnostic: compare TV trades from q4.csv vs our backtest trades.
Find the missing 4 trades and understand why they're not being generated.
"""

import json
import sqlite3
from datetime import datetime

conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()

# Get latest backtest for Strategy_RSI_LS_11
strategy_id = "01cd8861-60eb-40dd-a9a9-8baa6f2db0fa"
cur.execute(
    f"SELECT id, trades, total_trades, net_profit, win_rate, total_commission "
    f"FROM backtests WHERE strategy_id='{strategy_id}' "
    f"ORDER BY created_at DESC LIMIT 1"
)
row = cur.fetchone()
col_names = [d[0] for d in cur.description]
bt = dict(zip(col_names, row, strict=False))

print(f"Backtest ID: {bt['id']}")
print(f"Total trades: {bt['total_trades']}")
print(f"Net profit: {bt['net_profit']}")
print(f"Win rate: {bt['win_rate']}")
print(f"Commission: {bt['total_commission']}")

trades_json = json.loads(bt["trades"]) if bt["trades"] else []
print(f"\nOur {len(trades_json)} trades:")
for i, t in enumerate(trades_json[:10]):
    print(
        f"  {i + 1}. {t.get('side', '?')} "
        f"entry={t.get('entry_time', '?')} exit={t.get('exit_time', '?')} "
        f"ep={t.get('entry_price', '?'):.2f} xp={t.get('exit_price', '?'):.4f} "
        f"pnl={t.get('pnl', '?'):.2f} pnl%={t.get('pnl_pct', '?'):.2f}"
    )

# TV trades from q4.csv (first 30 trades)
tv_trades = [
    # trade#, side, entry_time, exit_time, entry_price, exit_price, pnl_usdt, pnl_pct
    (1, "short", "2025-01-01T13:30", "2025-01-08T17:00", 3334.62, 3257.92, 21.61, 2.16),
    (2, "short", "2025-01-09T00:30", "2025-01-09T13:30", 3322.53, 3246.11, 21.61, 2.16),
    (3, "short", "2025-01-09T18:30", "2025-01-09T20:30", 3285.67, 3210.09, 21.62, 2.16),
    (4, "short", "2025-01-10T22:00", "2025-01-13T07:30", 3257.99, 3183.05, 21.62, 2.16),
    (5, "long", "2025-01-13T14:30", "2025-01-14T01:00", 3075.39, 3146.13, 21.58, 2.16),
    (6, "short", "2025-01-14T17:30", "2025-01-27T06:30", 3191.83, 3118.41, 21.61, 2.16),
    (7, "long", "2025-01-27T09:00", "2025-01-27T15:30", 3068.83, 3139.42, 21.58, 2.16),
    (8, "short", "2025-01-27T17:30", "2025-01-27T19:30", 3117.00, 3045.30, 21.62, 2.16),
    (9, "short", "2025-01-28T15:30", "2025-01-28T21:30", 3170.30, 3097.38, 21.62, 2.16),
    (10, "short", "2025-01-29T06:00", "2025-02-02T12:30", 3122.65, 3050.82, 21.62, 2.16),
]

print("\nTradingView first 10 trades (UTC+3):")
for t in tv_trades:
    print(f"  {t[0]}. {t[1]} entry={t[2]} exit={t[3]} ep={t[4]:.2f} xp={t[5]:.2f} pnl={t[6]:.2f} pnl%={t[7]:.2f}")

print("\n--- Comparing entry prices (our vs TV) ---")
print("TV entry 1: 2025-01-01T13:30+03 = 2025-01-01T10:30Z, entry=3334.62")
print("TV entry 2: 2025-01-09T00:30+03 = 2025-01-08T21:30Z, entry=3322.53")

# Show our first trade's entry
if trades_json:
    t0 = trades_json[0]
    print(f"Our trade 1: entry={t0.get('entry_time')} price={t0.get('entry_price')}")

conn.close()
