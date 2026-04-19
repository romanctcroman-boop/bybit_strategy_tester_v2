"""
Verify SE signal array from generate_signals() vs manual RSI computation.
Cases E#82 and E#88 show ETH RSI < 50 (out of range [50,70]) but engine entered.
Either:
  A) generate_signals() produces SE=True there anyway (bug in range check?)
  B) generate_signals() correctly says SE=False and engine ignores it (engine bug)
"""

import os
import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.chdir(r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

# ---------- load data ----------
DB = r"d:\bybit_strategy_tester_v2\bybit_klines_15m.db"
import sqlite3


def load_klines(symbol, tf_min, start, end):
    conn = sqlite3.connect(DB)
    interval = str(tf_min)
    q = """
        SELECT open_time, open, high, low, close, volume
        FROM klines
        WHERE symbol=? AND interval=? AND open_time>=? AND open_time<=?
        ORDER BY open_time
    """
    s_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    e_ms = int(pd.Timestamp(end, tz="UTC").timestamp() * 1000)
    df = pd.read_sql_query(q, conn, params=(symbol, interval, s_ms, e_ms))
    conn.close()
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    return df


# BTC warmup from 2020 for RSI convergence
btc_warm = load_klines("BTCUSDT", 30, "2020-01-01", "2024-12-31 23:59")
btc_main = load_klines("BTCUSDT", 30, "2025-01-01", "2026-02-25")
btc = pd.concat([btc_warm, btc_main], ignore_index=True)

eth_warm = load_klines("ETHUSDT", 30, "2020-01-01", "2024-12-31 23:59")
eth_main = load_klines("ETHUSDT", 30, "2025-01-01", "2026-02-25")
eth = pd.concat([eth_warm, eth_main], ignore_index=True)

# ---------- generate signals ----------
strategy_graph = {
    "nodes": [
        {
            "id": "ind_rsi_1",
            "type": "indicator",
            "indicator_type": "rsi",
            "params": {
                "period": 14,
                "source": "close",
                "use_btc_source": True,
                "use_long_range": True,
                "long_rsi_more": 28,
                "long_rsi_less": 50,
                "use_short_range": True,
                "short_rsi_more": 50,
                "short_rsi_less": 70,
                "use_cross_level": True,
                "cross_long_level": 24,
                "cross_short_level": 52,
                "opposite_signal": False,
                "use_cross_memory": False,
            },
        },
        {"id": "sig_long_1", "type": "signal", "signal_type": "entry_long"},
        {"id": "sig_short_1", "type": "signal", "signal_type": "entry_short"},
    ],
    "edges": [
        {"source": "ind_rsi_1", "target": "sig_long_1", "source_output": "long_entry"},
        {"source": "ind_rsi_1", "target": "sig_short_1", "source_output": "short_entry"},
    ],
}

adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
result = adapter.generate_signals(eth)

le = result.entries.values
se = (
    result.short_entries.values
    if result.short_entries is not None
    else pd.Series(False, index=result.entries.index).values
)
lx = result.exits.values if result.exits is not None else pd.Series(False, index=result.entries.index).values
sx = (
    result.short_exits.values if result.short_exits is not None else pd.Series(False, index=result.entries.index).values
)

# Find main data start index
main_start = eth[eth["open_time"] >= pd.Timestamp("2025-01-01", tz="UTC")].index[0]
times = eth["open_time"].values

# ---------- check the 6 UNKNOWN cases ----------
cases = [
    ("E#20/TV#22", "2025-02-22 10:30", "2025-02-22 14:30"),
    ("E#54/TV#56", "2025-05-09 15:00", "2025-05-09 19:00"),
    ("E#82/TV#85", "2025-08-16 01:00", "2025-08-16 13:30"),
    ("E#86/TV#89", "2025-08-27 02:30", "2025-08-27 12:00"),
    ("E#88/TV#91", "2025-09-02 11:00", "2025-09-02 18:00"),
    ("E#117/TV#119", "2025-11-25 00:00", "2025-11-25 05:00"),
]

print("=" * 120)
print("SE signal array values from generate_signals() at divergent bars")
print("=" * 120)

for label, eng_ts, tv_ts in cases:
    eng_t = np.datetime64(pd.Timestamp(eng_ts, tz="UTC"))
    tv_t = np.datetime64(pd.Timestamp(tv_ts, tz="UTC"))

    eng_idx = np.where(times == eng_t)[0]
    tv_idx = np.where(times == tv_t)[0]

    if len(eng_idx) == 0 or len(tv_idx) == 0:
        print(f"  {label}: timestamp not found!")
        continue

    ei = eng_idx[0]
    ti = tv_idx[0]

    # Get ETH RSI values at these bars
    eth_close_ei = eth.iloc[ei]["close"]
    eth_close_ti = eth.iloc[ti]["close"]
    btc_close_ei = btc.iloc[ei]["close"] if ei < len(btc) else "N/A"
    btc_close_ti = btc.iloc[ti]["close"] if ti < len(btc) else "N/A"

    se_eng = se[ei]
    se_tv = se[ti]
    le_eng = le[ei]
    le_tv = le[ti]

    print(f"\n  {label}")
    print(f"    Engine bar {eng_ts}: SE={se_eng}  LE={le_eng}  (idx={ei})")
    print(f"    TV bar     {tv_ts}: SE={se_tv}  LE={le_tv}  (idx={ti})")

    # Also check a window around engine signal
    print("    SE window around engine signal bar:")
    for j in range(max(0, ei - 3), min(len(se), ei + 4)):
        t = pd.Timestamp(times[j]).strftime("%Y-%m-%d %H:%M")
        marker = " ← ENG" if j == ei else (" ← TV" if j == ti else "")
        print(f"      [{j}] {t}  SE={se[j]}  LE={le[j]}{marker}")


# ---------- also check INTRA-BAR cases ----------
print("\n" + "=" * 120)
print("INTRA-BAR cases: check SE at TV signal bars and engine signal bars")
print("=" * 120)

ib_cases = [
    ("TV#1", "2025-01-01 13:00", "E#1=2025-01-02 22:00"),
    ("TV#9", "2025-01-28 14:00", "E#6=2025-01-28 17:30"),
    ("TV#136", "2026-02-01 10:00", None),
]

for label, tv_ts, eng_info in ib_cases:
    tv_t = np.datetime64(pd.Timestamp(tv_ts, tz="UTC"))
    tv_idx = np.where(times == tv_t)[0]

    if len(tv_idx) == 0:
        print(f"  {label}: TV timestamp {tv_ts} not found")
        continue

    ti = tv_idx[0]
    print(f"\n  {label} - TV signal at {tv_ts}")
    print(f"    SE={se[ti]}  LE={le[ti]}")

    # Window around
    for j in range(max(0, ti - 2), min(len(se), ti + 5)):
        t = pd.Timestamp(times[j]).strftime("%Y-%m-%d %H:%M")
        se_val = se[j]
        le_val = le[j]
        marker = " ← TV" if j == ti else ""
        if se_val or le_val:
            marker += " *** SIGNAL ***"
        print(f"      [{j}] {t}  SE={se_val}  LE={le_val}{marker}")


# ---------- E#82/E#88: check if engine produced trade at SE=False bar ----------
print("\n" + "=" * 120)
print("CRITICAL: Do E#82 and E#88 have SE=True?")
print("=" * 120)
# If SE=False at engine signal bar, then the engine is entering WITHOUT a signal → engine bug
# If SE=True, then the range check in generate_signals() is different from our manual calc

# Let's also manually recompute ETH RSI at these bars
from backend.core.indicators.momentum import calculate_rsi

btc_rsi_full = pd.Series(calculate_rsi(btc["close"], period=14), index=btc.index)
eth_rsi_full = pd.Series(calculate_rsi(eth["close"], period=14), index=eth.index)

for label, eng_ts, tv_ts in [
    ("E#82/TV#85", "2025-08-16 01:00", "2025-08-16 13:30"),
    ("E#88/TV#91", "2025-09-02 11:00", "2025-09-02 18:00"),
]:
    eng_t = np.datetime64(pd.Timestamp(eng_ts, tz="UTC"))
    ei = np.where(times == eng_t)[0][0]

    eth_rsi_val = eth_rsi_full.iloc[ei]
    btc_rsi_val = btc_rsi_full.iloc[ei]
    btc_rsi_prev = btc_rsi_full.iloc[ei - 1]

    print(f"\n  {label} at engine bar {eng_ts} (idx={ei}):")
    print(f"    ETH RSI = {eth_rsi_val:.4f}  (range [50,70]? {'YES' if 50 <= eth_rsi_val <= 70 else 'NO'})")
    print(
        f"    BTC RSI = {btc_rsi_val:.4f}  prev = {btc_rsi_prev:.4f}  cross↓52? {'YES' if btc_rsi_prev >= 52 and btc_rsi_val < 52 else 'NO'}"
    )
    print(f"    SE from generate_signals() = {se[ei]}")

    # Check: is this the RSI being computed on BTC source?
    # The _handle_rsi should compute RSI on BTC close, but apply range on that RSI too?
    # Or does it compute RSI on BTC for cross, and RSI on ETH for range?
    # Let's check the code

    # Actually let's look at what _handle_rsi returns by checking the signal components
    # The range condition uses `rsi` which is BTC RSI (since use_btc_source=True)
    # Wait - does the range condition apply to BTC RSI or ETH RSI?

print("\n" + "=" * 120)
print("QUESTION: Does the range condition [50,70] apply to BTC RSI or ETH RSI?")
print("If use_btc_source=True, RSI is computed on BTC close.")
print("The range condition `short_rsi_more` and `short_rsi_less` are applied to this same RSI.")
print("=" * 120)

# Let's check BTC RSI at those bars instead
for label, eng_ts, tv_ts in [
    ("E#82/TV#85", "2025-08-16 01:00", "2025-08-16 13:30"),
    ("E#88/TV#91", "2025-09-02 11:00", "2025-09-02 18:00"),
]:
    eng_t = np.datetime64(pd.Timestamp(eng_ts, tz="UTC"))
    ei = np.where(times == eng_t)[0][0]

    btc_rsi_val = btc_rsi_full.iloc[ei]
    print(f"\n  {label} at engine bar {eng_ts}:")
    print(f"    BTC RSI = {btc_rsi_val:.4f}  (range [50,70]? {'YES' if 50 <= btc_rsi_val <= 70 else 'NO'})")
    print("    This IS the RSI used for both cross AND range when use_btc_source=True")
