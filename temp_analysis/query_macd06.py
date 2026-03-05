import json
import sqlite3

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("=== Tables ===")
for r in cur.fetchall():
    print(" ", r[0])

print("\n=== MACD Strategies ===")
cur.execute(
    "SELECT id, name, strategy_type, status, parameters, symbol, timeframe, direction, initial_capital, position_size, stop_loss_pct, take_profit_pct, total_return, sharpe_ratio, win_rate, total_trades FROM strategies WHERE name LIKE '%MACD%'"
)
rows = cur.fetchall()
for r in rows:
    print(f"\n  id={r['id']}")
    print(f"  name={r['name']}")
    print(f"  type={r['strategy_type']} status={r['status']}")
    print(f"  symbol={r['symbol']} tf={r['timeframe']} dir={r['direction']}")
    print(
        f"  capital={r['initial_capital']} pos={r['position_size']} sl={r['stop_loss_pct']} tp={r['take_profit_pct']}"
    )
    print(
        f"  total_return={r['total_return']} sharpe={r['sharpe_ratio']} wr={r['win_rate']} trades={r['total_trades']}"
    )
    if r["parameters"]:
        try:
            p = json.loads(r["parameters"])
            print(f"  parameters={json.dumps(p, indent=4)}")
        except Exception:
            print(f"  parameters={r['parameters']}")

conn.close()
