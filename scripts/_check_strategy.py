import json
import sqlite3

conn = sqlite3.connect("D:/bybit_strategy_tester_v2/data.sqlite3")
cur = conn.cursor()

# Get latest backtest for Strategy_RSI_L\S_3
cur.execute(
    """
    SELECT s.name, b.symbol, b.timeframe, b.start_date, b.end_date,
           b.initial_capital, b.parameters, b.total_trades, b.win_rate, b.total_return
    FROM backtests b
    JOIN strategies s ON s.id = b.strategy_id
    WHERE s.name LIKE '%RSI_L%S%3%' AND s.is_deleted=0
    ORDER BY b.created_at DESC LIMIT 5
    """
)
rows = cur.fetchall()
for r in rows:
    name, sym, tf, sd, ed, cap, params_raw, trades, wr, ret = r
    params = json.loads(params_raw) if params_raw else {}
    print(f"\n=== {name} ===")
    print(f"  Symbol: {sym}  TF: {tf}  Period: {sd[:10]} → {ed[:10]}")
    print(
        f"  Capital: {cap}  Trades: {trades}  WinRate: {round((wr or 0) * 100, 1)}%  Return: {round((ret or 0) * 100, 2)}%"
    )
    print(f"  Params: {json.dumps(params, indent=2)}")
conn.close()
