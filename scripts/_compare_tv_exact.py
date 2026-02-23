"""
Exact comparison: TV entries vs our trades.
TV timestamps are MSK (UTC+3).
TV entry_time = signal_bar + 15min (next bar open).
TV entry_price = Close[signal_bar] = Open[signal_bar+1].
Our entry_time = signal_bar (UTC).
So: our entry_utc + 15min == TV entry_utc.
"""

import json
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, "D:/bybit_strategy_tester_v2")

STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
TV_PATH = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"


def load_our_trades():
    conn = sqlite3.connect("data.sqlite3")
    sql = "SELECT b.trades FROM backtests b WHERE b.strategy_id = ? ORDER BY b.created_at DESC LIMIT 1"
    cursor = conn.execute(sql, (STRATEGY_ID,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ValueError("No backtest found!")
    trades = json.loads(row[0])
    df = pd.DataFrame(trades)
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    if df["entry_time"].dt.tz is not None:
        df["entry_utc"] = df["entry_time"].dt.tz_convert("UTC").dt.tz_localize(None)
    else:
        df["entry_utc"] = df["entry_time"]
    # TV entry bar = our signal bar + 15min
    df["entry_bar_utc"] = df["entry_utc"] + pd.Timedelta(minutes=15)
    return df


def load_tv_entries():
    tv = pd.read_csv(TV_PATH, encoding="utf-8-sig")
    tv.columns = [
        "trade_num",
        "type",
        "datetime",
        "signal",
        "price",
        "size_qty",
        "size_price",
        "pnl_usd",
        "pnl_pct",
        "fav_usd",
        "fav_pct",
        "max_adv_usd",
        "max_adv_pct",
        "cum_pnl_usd",
        "cum_pnl_pct",
    ]
    entries = tv[tv["type"].str.contains("Entry", na=False)].copy()
    entries["dt_msk"] = pd.to_datetime(entries["datetime"])
    entries["dt_utc"] = entries["dt_msk"] - pd.Timedelta(hours=3)
    entries["dir"] = entries["type"].apply(lambda x: "long" if "long" in x.lower() else "short")
    return entries


def main():
    our = load_our_trades()
    tv = load_tv_entries()

    print(f"Our trades: {len(our)}")
    print(f"TV entries: {len(tv)}")
    print()

    matched = 0
    unmatched_tv = []
    for _, tv_row in tv.iterrows():
        tv_time = tv_row["dt_utc"]
        tv_dir = tv_row["dir"]
        our_side = "buy" if tv_dir == "long" else "sell"

        # Exact match: our signal_bar + 15min == TV entry_bar_utc
        match = our[(our["entry_bar_utc"] == tv_time) & (our["side"] == our_side)]
        if not match.empty:
            matched += 1
        else:
            # ±15min tolerance
            close = our[(abs(our["entry_bar_utc"] - tv_time) <= pd.Timedelta(minutes=15)) & (our["side"] == our_side)]
            tag = "CLOSE(±15m)" if not close.empty else "NO_MATCH"
            close_t = close["entry_bar_utc"].values[0] if not close.empty else None
            unmatched_tv.append((tv_row["trade_num"], tv_dir, tv_time, tag, close_t))

    print(f"Exact matches: {matched}/{len(tv)}  ({100 * matched / len(tv):.1f}%)")
    print(f"Unmatched TV: {len(unmatched_tv)}")
    print()

    no_match = [u for u in unmatched_tv if u[3] == "NO_MATCH"]
    close_match = [u for u in unmatched_tv if u[3] != "NO_MATCH"]

    if close_match:
        print("CLOSE matches (±15min offset):")
        for t in close_match:
            diff = pd.Timestamp(t[4]) - t[2] if t[4] is not None else None
            print(f"  TV#{t[0]:3d} {t[1]:5s} TV={t[2]}  ours={t[4]}  diff={diff}")
        print()

    if no_match:
        print("NO_MATCH TV trades (completely missing in our output):")
        for t in no_match:
            print(f"  TV#{t[0]:3d} {t[1]:5s} TV_UTC={t[2]}")
        print()

    # Also check our trades that don't match any TV entry
    print("--- Checking our extra trades (not in TV) ---")
    matched_our_bars = set()
    for _, tv_row in tv.iterrows():
        tv_time = tv_row["dt_utc"]
        tv_dir = tv_row["dir"]
        our_side = "buy" if tv_dir == "long" else "sell"
        match = our[(our["entry_bar_utc"] == tv_time) & (our["side"] == our_side)]
        for _, m in match.iterrows():
            matched_our_bars.add((m["entry_utc"], m["side"]))

    extra_ours = []
    for _, row in our.iterrows():
        key = (row["entry_utc"], row["side"])
        if key not in matched_our_bars:
            extra_ours.append(row)

    print(f"Our extra trades (in ours but not in TV): {len(extra_ours)}")
    for r in extra_ours[:20]:
        print(f"  {r['side']:4s} entry_utc={r['entry_utc']}  entry_bar={r['entry_bar_utc']}")


main()
