"""Check bar details for TV trade #126 TP and trade #127 entry."""

import sqlite3
from datetime import UTC, datetime

import pandas as pd

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"

conn = sqlite3.connect(DB_PATH)
# Feb 19 2026 14:00-20:00 UTC
start_ms = int(datetime(2026, 2, 19, 14, 0, tzinfo=UTC).timestamp() * 1000)
end_ms = int(datetime(2026, 2, 19, 20, 0, tzinfo=UTC).timestamp() * 1000)
df = pd.read_sql_query(
    "SELECT open_time, open_price as open, high_price as high, low_price as low, close_price as close "
    "FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
    "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
    conn,
    params=(start_ms, end_ms),
)
conn.close()
df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)

# TV trade #126: Entry long at 14:15 UTC (signal bar 14:00 UTC)
# Entry price = close at 14:00 UTC = 66002.20
# TP = 66002.20 * 1.015 = 66992.23
# TV says exit at 17:15 UTC (bar 17:00 UTC close, or 17:15 UTC bar?)

entry_price = 66002.20  # TV exact close
tp_price = entry_price * 1.015
print(f"TV Trade #126 entry_price: {entry_price:.2f}")
print(f"TV TP price: {tp_price:.2f}")
print()
print(f"{'Bar UTC':<35} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'TP hit?':>8}")
for _, row in df.iterrows():
    ts = row["ts"]
    tp_hit = row["high"] >= tp_price
    marker = ""
    if str(ts).startswith("2026-02-19 17:00"):
        marker = " <-- TV exit bar"
    if str(ts).startswith("2026-02-19 17:15"):
        marker = " <-- Next bar (TV#127 short signal)"
    print(
        f"{ts!s:<35} {row['open']:>10.2f} {row['high']:>10.2f} {row['low']:>10.2f} {row['close']:>10.2f} {tp_hit!s:>8}{marker}"
    )
