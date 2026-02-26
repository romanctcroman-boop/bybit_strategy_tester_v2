"""Debug TV#27: trace same-bar entry+exit fix."""

import json
import sqlite3
import sys
import warnings
from datetime import UTC, datetime, timedelta

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
print(f"Params: {p}")
print(f"OHLCV bars: {len(ohlcv)}")

# Find bar index of 14:30 UTC (the entry bar for TV#27)
target_ts = pd.Timestamp("2025-03-03 14:30:00", tz="UTC")
bar_idx = ohlcv.index.get_loc(target_ts)
print(f"\nEntry bar 14:30 UTC is at index {bar_idx}")
print(
    f"  open={ohlcv.iloc[bar_idx]['open']:.1f} close={ohlcv.iloc[bar_idx]['close']:.1f} low={ohlcv.iloc[bar_idx]['low']:.1f}"
)
print(f"  TP price = {ohlcv.iloc[bar_idx]['open'] * (1 - p['take_profit']):.1f}")
print(f"  TP triggered: {ohlcv.iloc[bar_idx]['low'] <= ohlcv.iloc[bar_idx]['open'] * (1 - p['take_profit'])}")

# Check the entry bar OPEN vs close of previous bar
prev_bar = ohlcv.iloc[bar_idx - 1]
print(f"\nPrev bar 14:00 UTC close={prev_bar['close']:.1f} (= next bar open = {ohlcv.iloc[bar_idx]['open']:.1f})")

# In FallbackEngine, entry is at close_price of bar i (after slippage)
# close_price of bar 14:30 is 89270.3 — NOT the entry price
# Actually looking at the script: entry_price = close_price * (1 - effective_slippage) for short
# And close_price at signal bar i is the bar close used for entry
# Wait — FallbackEngine signal triggers at bar i, entry = close_price[i]
# But the RSI signal at 14:00 bar triggers entry at close of 14:00 bar = 93163.9
# Then on bar 14:30: TP check on high/low of bar 14:30

# The actual entry bar in the engine loop is i where short_entries[i] = True
# short_entries[i] = True means signal fired at bar i
# entry_price = close_price = ohlcv.iloc[i]['close']
# TV#27 entry_price = 93163.9 = close of bar 14:00

entry_bar_signal = ohlcv.index.get_loc(pd.Timestamp("2025-03-03 14:00:00", tz="UTC"))
print(f"\nSignal bar (14:00 UTC) index = {entry_bar_signal}")
print(f"  close (= entry_price) = {ohlcv.iloc[entry_bar_signal]['close']:.1f}")

# TP check happens on bar entry_bar_signal + 1 = 14:30 UTC
tp_check_bar = entry_bar_signal + 1
print(f"\nTP check bar (14:30 UTC) index = {tp_check_bar}")
low_tp = ohlcv.iloc[tp_check_bar]["low"]
tp_price = ohlcv.iloc[entry_bar_signal]["close"] * (1 - p["take_profit"])
print(f"  low = {low_tp:.1f}, TP price = {tp_price:.1f}")
print(f"  TP triggered on same bar as entry? entry_bar_signal={entry_bar_signal}, tp fires at {tp_check_bar}")
print(f"  Entry bar for first_entry_bar = {entry_bar_signal}")

# When pending exit executes on bar tp_check_bar + 1 = 15:00 UTC bar
exec_bar = tp_check_bar + 1
print(f"\nPending exit executes at bar index {exec_bar} (15:00 UTC)")
print(f"  first_entry_bar = {entry_bar_signal}")
print(f"  i - 1 = {exec_bar - 1}")
print(f"  Match? first_entry_bar == i-1: {entry_bar_signal == exec_bar - 1}")
print(f"  close_prices[i-1] = close_prices[{exec_bar - 1}] = {ohlcv.iloc[exec_bar - 1]['close']:.1f}")
print(f"  TV exit price = 89270.3")
