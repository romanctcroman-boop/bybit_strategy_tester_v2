"""
Detailed trade-by-trade comparison between our engine and TV.
"""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pandas as pd

TV_CSV = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"


def load_tv_trades():
    df = pd.read_csv(TV_CSV, encoding="utf-8-sig")
    df.columns = [
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
    df = df[df["type"].notna() & df["price"].notna()]
    df["datetime"] = pd.to_datetime(df["datetime"], dayfirst=False)
    df["utc"] = df["datetime"].apply(lambda x: x.replace(tzinfo=UTC) - timedelta(hours=3))
    df["direction"] = df["type"].apply(lambda x: "long" if "long" in x.lower() else "short")
    df["is_entry"] = df["type"].apply(lambda x: "entry" in x.lower())
    return df


def load_our_trades():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT trades FROM backtests WHERE status='COMPLETED' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return []
    return json.loads(row[0])


def main():
    tv_all = load_tv_trades()

    # Split into entries and exits
    tv_entries = tv_all[tv_all["is_entry"]].copy().reset_index(drop=True)
    tv_exits = tv_all[~tv_all["is_entry"]].copy().reset_index(drop=True)

    print(f"TV total rows: {len(tv_all)}")
    print(f"TV entry rows: {len(tv_entries)}")
    print(f"TV exit rows: {len(tv_exits)}")

    # Sort entries by trade_num
    tv_entries = tv_entries.sort_values("trade_num").reset_index(drop=True)
    tv_exits = tv_exits.sort_values("trade_num").reset_index(drop=True)

    # Merge entry+exit per trade
    tv_trades = tv_entries.copy()
    tv_trades.columns = [f"entry_{c}" if c not in ["trade_num", "direction"] else c for c in tv_trades.columns]

    our_trades = load_our_trades()

    print(f"\nOur trades: {len(our_trades)}")
    print(f"TV trades: {len(tv_entries)}")

    # Map our side
    side_map = {"buy": "long", "sell": "short", "long": "long", "short": "short"}

    # Show first 15 TV entry trades
    print("\n=== TV FIRST 15 ENTRY TRADES ===")
    print(f"{'#':>3} {'Dir':6} {'Entry UTC':25} {'Price':10} {'PnL%':7} {'Exit signal'}")
    for i, row in tv_entries.head(15).iterrows():
        # Find corresponding exit
        exit_row = tv_exits[tv_exits["trade_num"] == row["trade_num"]]
        exit_info = ""
        if not exit_row.empty:
            e = exit_row.iloc[0]
            exit_info = f"Exit {e['utc']} ({e['signal']})"
        print(
            f"{row['trade_num']:>3} {row['direction']:6} {row['utc']!s:25} {row['price']:>10.2f} {row['pnl_pct']:>7.2f}% {exit_info}"
        )

    # Show our first 15 trades
    print("\n=== OUR FIRST 15 TRADES ===")
    print(f"{'#':>3} {'Dir':6} {'Entry UTC':25} {'Exit UTC':25} {'Price':10} {'PnL':10} {'Exit'}")
    for i, t in enumerate(our_trades[:15]):
        entry_str = t.get("entry_time", "")
        exit_str = t.get("exit_time", "")
        try:
            entry_dt = datetime.fromisoformat(entry_str)
            if entry_dt.tzinfo is None:
                entry_dt = entry_dt.replace(tzinfo=UTC)
        except Exception:
            entry_dt = None
        try:
            exit_dt = datetime.fromisoformat(exit_str)
            if exit_dt.tzinfo is None:
                exit_dt = exit_dt.replace(tzinfo=UTC)
        except Exception:
            exit_dt = None

        direction = side_map.get(t.get("side", ""), "?")
        price = t.get("entry_price", 0)
        pnl = t.get("pnl", 0)
        exit_comment = t.get("exit_comment", "")

        # TV equivalent entry time (our + 15min)
        tv_eq = (entry_dt + timedelta(minutes=15)) if entry_dt else None

        print(
            f"{i + 1:>3} {direction:6} our={entry_dt!s:25} tv_eq={tv_eq!s:25} p={price:>10.2f} pnl={pnl:>8.2f} exit={exit_comment[:10]}"
        )

    # Compare TV and our trade sequences
    print("\n=== DETAILED COMPARISON ===")
    print(
        f"{'TV#':>3} {'TVDir':6} {'TVentry UTC':22} {'TVpnl%':7} | {'Our#':>4} {'OurDir':6} {'Ourentry UTC':22} {'Match':10}"
    )

    our_processed = []
    for t in our_trades:
        entry_str = t.get("entry_time", "")
        try:
            entry_dt = datetime.fromisoformat(entry_str)
            if entry_dt.tzinfo is None:
                entry_dt = entry_dt.replace(tzinfo=UTC)
        except Exception:
            entry_dt = None
        direction = side_map.get(t.get("side", ""), "?")
        our_processed.append({"entry_utc": entry_dt, "direction": direction, "price": t.get("entry_price", 0)})

    for i, tv_row in tv_entries.head(20).iterrows():
        tv_dir = tv_row["direction"]
        tv_time = tv_row["utc"]
        tv_pnl = tv_row["pnl_pct"]
        tv_num = tv_row["trade_num"]

        # Find best matching our trade
        best_match = None
        best_diff = 9999
        best_idx = -1

        for j, our_t in enumerate(our_processed):
            if our_t["direction"] != tv_dir:
                continue
            if our_t["entry_utc"] is None:
                continue
            our_tv_eq = our_t["entry_utc"] + timedelta(minutes=15)
            diff = abs((our_tv_eq - tv_time).total_seconds()) / 60
            if diff < best_diff:
                best_diff = diff
                best_match = our_t
                best_idx = j

        match_str = (
            "MATCH(0min)"
            if best_diff == 0
            else f"CLOSE({best_diff:.0f}min)"
            if best_diff <= 30
            else f"DIFF({best_diff:.0f}min)"
        )
        if best_match:
            our_str = f"our[{best_idx + 1}] {best_match['direction']:6} {best_match['entry_utc']!s:22}"
        else:
            our_str = "NO MATCH"

        print(f"{tv_num:>3} {tv_dir:6} {tv_time!s:22} {tv_pnl:>7.2f}% | {our_str} {match_str}")


if __name__ == "__main__":
    main()
