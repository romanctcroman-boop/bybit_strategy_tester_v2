"""Compare VBT RSI vs Wilder RSI to understand TV signal at bar 212."""

import sqlite3
from datetime import UTC, datetime

import pandas as pd
import vectorbt as vbt

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"

conn = sqlite3.connect(DB_PATH)
start_ms = int(datetime(2025, 11, 1, tzinfo=UTC).timestamp() * 1000)
end_ms = int(datetime(2025, 11, 4, tzinfo=UTC).timestamp() * 1000)
df = pd.read_sql_query(
    "SELECT open_time, close_price as close FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
    "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
    conn,
    params=(start_ms, end_ms),
)
conn.close()
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("timestamp")
close = df["close"]

print(f"Total bars: {len(close)}")

# VBT RSI (what our code uses)
rsi_vbt = vbt.RSI.run(close, window=14).rsi

# Wilder RSI (RMA = alpha=1/period) - typical TradingView formula
delta = close.diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
rs = avg_gain / avg_loss
rsi_wilder = 100 - (100 / (1 + rs))

CROSS_LONG = 29
CROSS_SHORT = 55

# Signals with VBT RSI
rsi_vbt_prev = rsi_vbt.shift(1)
cross_long_vbt = (rsi_vbt_prev <= CROSS_LONG) & (rsi_vbt > CROSS_LONG)
cross_short_vbt = (rsi_vbt_prev >= CROSS_SHORT) & (rsi_vbt < CROSS_SHORT)

# Signals with Wilder RSI
rsi_wil_prev = rsi_wilder.shift(1)
cross_long_wil = (rsi_wil_prev <= CROSS_LONG) & (rsi_wilder > CROSS_LONG)
cross_short_wil = (rsi_wil_prev >= CROSS_SHORT) & (rsi_wilder < CROSS_SHORT)

print()
print(f"VBT RSI long signals: {cross_long_vbt.sum()}, short signals: {cross_short_vbt.sum()}")
print(f"Wilder RSI long signals: {cross_long_wil.sum()}, short signals: {cross_short_wil.sum()}")

print()
print(
    f"{'Bar':<5} {'Time':<32} {'close':<12} {'RSI_VBT':<10} {'RSI_Wil':<10} {'VBT_L':<6} {'VBT_S':<6} {'Wil_L':<6} {'Wil_S'}"
)
for i in range(195, 225):
    ts = df.index[i]
    cl = close.iloc[i]
    rv = rsi_vbt.iloc[i]
    rw = rsi_wilder.iloc[i]
    vl = bool(cross_long_vbt.iloc[i])
    vs = bool(cross_short_vbt.iloc[i])
    wl = bool(cross_long_wil.iloc[i])
    ws = bool(cross_short_wil.iloc[i])
    mark = ""
    if vl or vs or wl or ws:
        mark = " <---"
    print(
        f"{i:<5} {ts!s:<32} {cl:<12.2f} {rv:<10.4f} {rw:<10.4f} {vl!s:<6} {vs!s:<6} {wl!s:<6} {ws!s}{mark}"
    )
