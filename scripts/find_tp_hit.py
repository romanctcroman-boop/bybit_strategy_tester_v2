"""Find when ETH hit TP for last long trade (entry=1859.70, TP=1902.54)."""

import sqlite3
from datetime import UTC, datetime, timezone

# TP target: 1859.70 * 1.023 = 1902.54
TP_TARGET = 1859.70 * 1.023
print(f"TP target: {TP_TARGET:.4f}")

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
c = conn.cursor()

# Look from 2026-02-25 00:00 onwards
start_ms = 1771977600000  # 2026-02-25 00:00 UTC
end_ms = 1772064000000  # 2026-02-26 00:00 UTC

c.execute(
    """
    SELECT open_time, open_price, high_price, low_price, close_price
    FROM bybit_kline_audit
    WHERE symbol = 'ETHUSDT' AND interval = '30' AND market_type = 'linear'
      AND open_time >= ?
      AND open_time <= ?
    ORDER BY open_time
""",
    (start_ms, end_ms),
)
rows = c.fetchall()

print("\nETH bars from 2026-02-25 00:00 onwards:")
print(f"{'Time':20s} {'Open':10s} {'High':10s} {'Low':10s} {'Close':10s}")
for row in rows:
    dt = datetime.fromtimestamp(row[0] / 1000, tz=UTC)
    flag = " *** TP HIT!" if row[2] >= TP_TARGET else ""
    print(f"  {dt.strftime('%Y-%m-%d %H:%M'):20s} {row[1]:10.4f} {row[2]:10.4f} {row[3]:10.4f} {row[4]:10.4f}{flag}")
    if row[2] >= TP_TARGET:
        print(f"  -> TP would be hit in bar starting {dt.strftime('%Y-%m-%d %H:%M')}")
        break

conn.close()
