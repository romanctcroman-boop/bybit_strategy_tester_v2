import sqlite3
from datetime import UTC

conn = sqlite3.connect("data.sqlite3")
rows = conn.execute(
    "SELECT market_type, interval, COUNT(*) as cnt, MIN(open_time) as min_ts, MAX(open_time) as max_ts "
    "FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='15' GROUP BY market_type"
).fetchall()
for r in rows:
    from datetime import datetime

    min_dt = datetime.fromtimestamp(r[3] / 1000, tz=UTC) if r[3] else None
    max_dt = datetime.fromtimestamp(r[4] / 1000, tz=UTC) if r[4] else None
    print(f"market_type={r[0]} count={r[2]} from={min_dt} to={max_dt}")
conn.close()
