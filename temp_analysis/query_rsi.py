"""Query RSI strategies from DB."""

import json
import sqlite3

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== RSI Strategies ===")
cur.execute(
    "SELECT id, name, status, symbol, timeframe, direction, initial_capital, "
    "position_size, stop_loss_pct, take_profit_pct, total_return, total_trades "
    "FROM strategies WHERE name LIKE '%RSI%' ORDER BY created_at DESC"
)
for r in cur.fetchall():
    print(
        f"\n{r['id']} | {r['name']} | {r['status']}\n"
        f"  sym={r['symbol']} tf={r['timeframe']} dir={r['direction']}\n"
        f"  trades={r['total_trades']} netret={r['total_return']}\n"
        f"  sl={r['stop_loss_pct']} tp={r['take_profit_pct']}"
    )

print("\n=== Backtests for RSI strategies ===")
print("\n=== Backtests for Strategy_RSI_L/S_15 (2e5bb802) ===")
cur.execute(
    "SELECT id, status, total_trades, net_profit, win_rate, profit_factor, sharpe_ratio, "
    "start_date, end_date, symbol, timeframe FROM backtests "
    "WHERE strategy_id=? ORDER BY created_at DESC LIMIT 5",
    ("2e5bb802-572b-473f-9ee9-44d38bf9c531",),
)
bt_rows = cur.fetchall()
for r in bt_rows:
    print(
        f"\n  {r['id']} | {r['status']} | {r['symbol']} {r['timeframe']}\n"
        f"  trades={r['total_trades']} net={r['net_profit']} wr={r['win_rate']} pf={r['profit_factor']}\n"
        f"  date={r['start_date']} to {r['end_date']}"
    )
for r in cur.fetchall():
    print(f"  Backtest {r['id'][:8]} | {r['strat_name']} | {r['status']}")

# Also check the specific strategy ID from compare_tv.py
STRAT_ID = "2e5bb802-572b-473f-9ee9-44d38bf9c531"
print(f"\n=== Strategy {STRAT_ID[:8]} ===")
cur.execute("SELECT id, name, status, symbol, timeframe, builder_blocks FROM strategies WHERE id=?", (STRAT_ID,))
r = cur.fetchone()
if r:
    print(f"  {r['id']} | {r['name']} | {r['status']} | sym={r['symbol']} tf={r['timeframe']}")
    if r["builder_blocks"]:
        blocks = json.loads(r["builder_blocks"])
        for b in blocks:
            if b.get("type") in ("rsi", "macd", "static_sltp"):
                print(f"  Block {b['type']}: {json.dumps(b.get('params', {}), indent=4)}")
else:
    print("  NOT FOUND")

conn.close()
