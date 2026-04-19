"""Compare the two backtests in detail."""

import json
import sqlite3

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
c = conn.cursor()

for bt_id in ["bbab7cbc-dd59-4b53-9f46-24f8d24b8f95", "5e3e8b2f-8749-48e0-8e8e-1511e3b5ba40"]:
    c.execute(
        """
        SELECT symbol, timeframe, total_trades, net_profit, parameters
        FROM backtests WHERE id = ?
    """,
        (bt_id,),
    )
    row = c.fetchone()
    params = json.loads(row[4]) if row[4] else {}
    print(f"\nBacktest {bt_id[:8]}:")
    print(f"  Symbol: {row[0]}, TF: {row[1]}")
    print(f"  Trades: {row[2]}, Net profit: {row[3]:.2f}")
    print(f"  Slippage: {params.get('_slippage')}")
    print(f"  SL: {params.get('stop_loss_pct')}, TP: {params.get('take_profit_pct')}")

    c.execute("SELECT trades FROM backtests WHERE id = ?", (bt_id,))
    trades_raw = c.fetchone()[0]
    if trades_raw:
        trades = json.loads(trades_raw)
        print(f"  Trades in JSON: {len(trades)}")
        print("  First 3 trades:")
        for i, t in enumerate(trades[:3], 1):
            et = t.get("entry_time", "?")
            ep = float(t.get("entry_price", 0))
            xp = float(t.get("exit_price", 0))
            pnl = float(t.get("pnl", 0))
            side = t.get("side", "?")
            print(f"    {i}. {side} entry={et} ep={ep:.4f} xp={xp:.4f} pnl={pnl:.4f}")

conn.close()
