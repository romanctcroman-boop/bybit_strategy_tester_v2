import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get most recent completed backtest with trades
cur.execute("""
    SELECT id, strategy_type, symbol, timeframe, total_trades, created_at
    FROM backtests
    WHERE status='completed' AND total_trades > 10
    ORDER BY created_at DESC
    LIMIT 10
""")
rows = cur.fetchall()
for r in rows:
    print(dict(r))

conn.close()
