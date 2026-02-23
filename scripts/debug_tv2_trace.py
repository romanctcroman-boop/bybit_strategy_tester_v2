"""Debug TV#2 carry-over signal."""

import json
import sqlite3
import sys
import warnings
from datetime import UTC, datetime

import pandas as pd

sys.path.insert(0, "d:/bybit_strategy_tester_v2")
warnings.filterwarnings("ignore")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = "d:/bybit_strategy_tester_v2/data.sqlite3"
STRATEGY_ID = "5c03fd86-a821-4a62-a783-4d617bf25bc7"


def load_ohlcv():
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 25, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def load_bt_params():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT parameters, builder_blocks, timeframe FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cur.fetchone()
    conn.close()
    params = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
    blocks = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
    sltp_block = next((b for b in blocks if b.get("type") == "static_sltp"), {})
    sltp_params = sltp_block.get("params", {})
    return {
        "slippage": float(params.get("_slippage", 0.0)),
        "taker_fee": float(params.get("_commission", 0.0007)),
        "leverage": int(params.get("_leverage", 10)),
        "pyramiding": int(params.get("_pyramiding", 1)),
        "take_profit": float(sltp_params.get("take_profit_percent", 1.5)) / 100.0,
        "stop_loss": float(sltp_params.get("stop_loss_percent", 9.1)) / 100.0,
        "interval": str(sltp_params.get("timeframe") or params.get("_timeframe") or "30"),
    }


ohlcv = load_ohlcv()
p = load_bt_params()

# TV#1: short entry @94126.2, exit 2025-01-07 00:30 UTC
# TV#2: short entry @101996.9, exit 2025-01-07 11:30 UTC
# TV#2 entry = open of bar 01:00 UTC = 101996.9

# Find bars around TV#2
bar_0000 = ohlcv.index.get_loc(pd.Timestamp("2025-01-07 00:00:00", tz="UTC"))
bar_0030 = ohlcv.index.get_loc(pd.Timestamp("2025-01-07 00:30:00", tz="UTC"))
bar_0100 = ohlcv.index.get_loc(pd.Timestamp("2025-01-07 01:00:00", tz="UTC"))
bar_0130 = ohlcv.index.get_loc(pd.Timestamp("2025-01-07 01:30:00", tz="UTC"))

print(f"Bar indices: 00:00={bar_0000}, 00:30={bar_0030}, 01:00={bar_0100}, 01:30={bar_0130}")

for idx, name in [(bar_0000, "00:00"), (bar_0030, "00:30"), (bar_0100, "01:00"), (bar_0130, "01:30")]:
    row = ohlcv.iloc[idx]
    print(f"  Bar {name} (idx={idx}): open={row['open']:.1f} close={row['close']:.1f}")

# TV#2 entry @ open of bar 01:00 = 101996.9
# So bar 01:00 has open=101996.9
print(f"\nTV#2 entry = open of bar 01:00 = {ohlcv.iloc[bar_0100]['open']:.1f}")

# In the engine, entry_price = close_price * (1-slippage) at signal bar
# close[bar_0030] = ? That should be ~101996.9 if short signals at 00:30
print(f"close[bar_0030] = {ohlcv.iloc[bar_0030]['close']:.1f}")
print(f"close[bar_0100] = {ohlcv.iloc[bar_0100]['close']:.1f}")

# TV#1 exit = 2025-01-07 00:30 UTC
# In our engine, TV#1 exit is executed on bar 01:00 (i) with prev_bar_time = 00:30
# So last_exit_bar = bar_0100 (the bar where it executes)
print("\nFor TV#2 carry-over:")
print(f"  Signal fires at bar_0030={bar_0030} (carry set)")
print(f"  TV#1 exit executes at bar_0100={bar_0100} -> last_exit_bar={bar_0100}")
print(f"  Carry check: last_exit_bar == i -> {bar_0100} == {bar_0100} -> True (matches!)")
print(f"  BUT: entry_price from carry = close[bar_0100] = {ohlcv.iloc[bar_0100]['close']:.1f}")
print(f"  TV#2 entry = {ohlcv.iloc[bar_0100]['open']:.1f}")
print(f"  Difference: {abs(ohlcv.iloc[bar_0100]['close'] - 101996.9):.1f}")

# The carry uses entry_price = close_price of bar_0100, not open
# But TV entry at bar 01:00 uses open = 101996.9
# close of bar 01:00 might be different
