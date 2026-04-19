"""
Detailed RSI signal analysis: check exactly which bars get RSI crossover signals
and compare with TV trade times.
"""

import asyncio
import csv
import json
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, "D:/bybit_strategy_tester_v2")

TV_CSV = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
DB_PATH = "D:/bybit_strategy_tester_v2/data.sqlite3"

# TV params for Strategy_RSI_L\S_3
RSI_PERIOD = 14
CROSS_LONG = 29
CROSS_SHORT = 55


async def main():
    # Load strategy
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT builder_graph, builder_blocks, builder_connections FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    builder_blocks = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])

    # Check RSI params in blocks
    for b in builder_blocks:
        if b.get("type") == "rsi":
            print(f"RSI block params: {b.get('params', {})}")

    # Get OHLCV
    from backend.backtesting.service import BacktestService

    svc = BacktestService()
    ohlcv = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="15",
        start_date=pd.Timestamp("2025-11-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-23", tz="UTC"),
    )
    print(f"OHLCV: {len(ohlcv)} bars")

    close = ohlcv["close"]

    # Calculate RSI manually using vectorbt (same as our adapter)
    import vectorbt as vbt

    rsi_vbt = vbt.RSI.run(close, window=RSI_PERIOD).rsi
    rsi = rsi_vbt
    rsi_prev = rsi.shift(1)

    # Crossover signals
    long_sig = (rsi_prev <= CROSS_LONG) & (rsi > CROSS_LONG)
    short_sig = (rsi_prev >= CROSS_SHORT) & (rsi < CROSS_SHORT)

    print(f"\nManual RSI({RSI_PERIOD}) crossover signals:")
    print(f"  Long (cross above {CROSS_LONG}): {long_sig.sum()}")
    print(f"  Short (cross below {CROSS_SHORT}): {short_sig.sum()}")

    # Load TV entries
    tv_entries = []
    with open(TV_CSV, encoding="utf-8-sig") as f:
        for row_csv in csv.DictReader(f):
            keys = list(row_csv.keys())
            num_str = row_csv[keys[0]].strip()
            if not num_str:
                continue
            if "Entry" not in row_csv[keys[1]]:
                continue
            tv_entries.append(
                {
                    "num": int(num_str),
                    "dir": "long" if "long" in row_csv[keys[1]].lower() else "short",
                    "tv_time": row_csv[keys[2]].strip(),
                    "price": float(row_csv[keys[4]]),
                }
            )

    print(f"\nTV entries: {len(tv_entries)}")

    # For each TV entry, find the closest signal bar
    # TV time format: "2025-11-01 09:45" — need to check timezone
    # Try UTC, UTC+3, UTC+8

    print("\n=== SIGNAL BAR vs TV ENTRY TIME ANALYSIS ===")
    print("TV first 10 trades (signal bar search):\n")

    # Build signal bar lists
    short_bars = ohlcv.index[short_sig.fillna(False)]
    long_bars = ohlcv.index[long_sig.fillna(False)]

    for entry in tv_entries[:15]:
        tv_time_str = entry["tv_time"]
        tv_dt = pd.Timestamp(tv_time_str)  # naive
        tv_dir = entry["dir"]

        # Check which signal bars are nearby (±2h)
        signal_bars = long_bars if tv_dir == "long" else short_bars

        nearby = []
        for sb in signal_bars:
            sb_naive = sb.replace(tzinfo=None) if hasattr(sb, "tzinfo") and sb.tzinfo else sb
            diff = abs((tv_dt - sb_naive).total_seconds()) / 60
            if diff <= 120:  # 2h
                nearby.append((diff, sb_naive))

        nearby.sort()
        if nearby:
            best_diff, best_bar = nearby[0]
            # Also show signal+1 bar
            sb_plus1 = best_bar + pd.Timedelta(minutes=15)
            print(
                f"  TV#{entry['num']:3} {tv_dir:5} TV={tv_time_str}  "
                f"Signal_bar={best_bar} ({best_diff:.0f}min diff)  "
                f"Signal+1={sb_plus1}"
            )
        else:
            print(f"  TV#{entry['num']:3} {tv_dir:5} TV={tv_time_str}  NO NEARBY SIGNAL")

    print()
    print("HYPOTHESIS TEST: Is TV entry_time = our_signal_bar + 15min?")
    correct = 0
    total = min(30, len(tv_entries))
    for entry in tv_entries[:total]:
        tv_dt = pd.Timestamp(entry["tv_time"])
        tv_dir = entry["dir"]
        signal_bars = long_bars if tv_dir == "long" else short_bars

        # Check if any signal_bar + 15min == tv_dt
        for sb in signal_bars:
            sb_naive = sb.replace(tzinfo=None) if hasattr(sb, "tzinfo") and sb.tzinfo else sb
            if sb_naive + pd.Timedelta(minutes=15) == tv_dt:
                correct += 1
                break

    print(f"  Exact signal+15min matches: {correct}/{total}")

    # Try: TV time - 3h = UTC time, then TV entry = UTC signal bar
    print()
    print("HYPOTHESIS: TV time = UTC+3, signal = signal bar (not entry bar)")
    correct2 = 0
    for entry in tv_entries[:total]:
        tv_dt_utc = pd.Timestamp(entry["tv_time"]) - pd.Timedelta(hours=3)
        tv_dir = entry["dir"]
        signal_bars = long_bars if tv_dir == "long" else short_bars

        for sb in signal_bars:
            sb_naive = sb.replace(tzinfo=None) if hasattr(sb, "tzinfo") and sb.tzinfo else sb
            if sb_naive == tv_dt_utc:
                correct2 += 1
                break

    print(f"  Exact signal bar (UTC+3 offset) matches: {correct2}/{total}")

    # Try: TV time = UTC+3, entry = signal+1
    print()
    print("HYPOTHESIS: TV time = signal_bar+1 (UTC+3 offset)")
    correct3 = 0
    for entry in tv_entries[:total]:
        tv_dt_utc = pd.Timestamp(entry["tv_time"]) - pd.Timedelta(hours=3)
        tv_dir = entry["dir"]
        signal_bars = long_bars if tv_dir == "long" else short_bars

        # TV entry bar = signal_bar + 1 bar (15min)
        for sb in signal_bars:
            sb_naive = sb.replace(tzinfo=None) if hasattr(sb, "tzinfo") and sb.tzinfo else sb
            if sb_naive + pd.Timedelta(minutes=15) == tv_dt_utc:
                correct3 += 1
                break

    print(f"  signal+1 bar (UTC+3 offset) matches: {correct3}/{total}")


asyncio.run(main())
