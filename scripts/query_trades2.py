"""Query trades from the latest backtest stored in 'trades' JSON column."""

import json
import sqlite3

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
cursor = conn.cursor()

bt_id = "bbab7cbc-dd59-4b53-9f46-24f8d24b8f95"

# Get trades JSON from backtests table
cursor.execute("SELECT trades, metrics_json FROM backtests WHERE id = ?", (bt_id,))
row = cursor.fetchone()

if row and row[0]:
    trades_raw = row[0]
    trades = json.loads(trades_raw) if isinstance(trades_raw, str) else trades_raw
    print(f"Total trades in JSON: {len(trades)}")

    # Show first trade keys
    if trades:
        print(f"Trade keys: {list(trades[0].keys())}")
        print()
        print("First 10 trades:")
        for i, t in enumerate(trades[:10], 1):
            side = t.get("side", t.get("direction", "?"))
            entry_time = t.get("entry_time", t.get("entry_date", "?"))
            exit_time = t.get("exit_time", t.get("exit_date", "?"))
            entry_price = t.get("entry_price", 0)
            exit_price = t.get("exit_price", t.get("close_price", 0))
            pnl = t.get("pnl", t.get("profit", t.get("net_pnl", 0)))
            print(
                f"  {i}. {side} entry={entry_time} ep={float(entry_price):.2f} exit={exit_time} xp={float(exit_price):.2f} pnl={float(pnl):.4f}"
            )

        print()
        print("Last 5 trades:")
        for i, t in enumerate(trades[-5:], len(trades) - 4):
            side = t.get("side", t.get("direction", "?"))
            entry_time = t.get("entry_time", t.get("entry_date", "?"))
            exit_time = t.get("exit_time", t.get("exit_date", "?"))
            entry_price = t.get("entry_price", 0)
            pnl = t.get("pnl", t.get("profit", t.get("net_pnl", 0)))
            print(f"  {i}. {side} entry={entry_time} ep={float(entry_price):.2f} pnl={float(pnl):.4f}")

        # Find biggest loss trades
        print()

        def get_pnl(t):
            return float(t.get("pnl", t.get("profit", t.get("net_pnl", 0))))

        sorted_by_pnl = sorted(trades, key=get_pnl)
        print("5 biggest losers:")
        for t in sorted_by_pnl[:5]:
            side = t.get("side", "?")
            entry_time = t.get("entry_time", "?")
            pnl = get_pnl(t)
            entry_price = float(t.get("entry_price", 0))
            print(f"  {side} entry={entry_time} ep={entry_price:.2f} pnl={pnl:.4f}")

        print("\n5 biggest winners:")
        for t in sorted_by_pnl[-5:]:
            side = t.get("side", "?")
            entry_time = t.get("entry_time", "?")
            pnl = get_pnl(t)
            entry_price = float(t.get("entry_price", 0))
            print(f"  {side} entry={entry_time} ep={entry_price:.2f} pnl={pnl:.4f}")

else:
    print("No trades data found")

conn.close()
