"""
Compare our engine trades vs TradingView trades after proper timing fix.
Hypothesis: our entry_time + 15min == TV entry_time (UTC)
And our entry_price * (1/(1-slippage)) == TV entry_price (no slippage in TV)
"""

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

TV_CSV = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"
BACKTEST_ID = "4d48fc0a-71cb-468b-b55a-0a6156cea940"
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
    # Parse datetime (UTC+3 Moscow)
    df["datetime"] = pd.to_datetime(df["datetime"], dayfirst=False)
    df["utc"] = df["datetime"].apply(lambda x: x.replace(tzinfo=UTC) - timedelta(hours=3))
    df["direction"] = df["type"].apply(lambda x: "long" if "long" in x.lower() else "short")
    return df


def load_our_trades():
    conn = sqlite3.connect(DB_PATH)
    # Get the most recent completed backtest for this strategy
    row = conn.execute(
        "SELECT trades FROM backtests WHERE status='COMPLETED' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return []
    return json.loads(row[0])


def main():
    tv = load_tv_trades()
    our = load_our_trades()

    print(f"TV trades: {len(tv)}")
    print(f"Our trades: {len(our)}")

    # Map our side to direction
    side_map = {"buy": "long", "sell": "short", "long": "long", "short": "short"}

    # Convert our trades to dicts with normalized times
    our_list = []
    for t in our:
        entry_str = t.get("entry_time", "")
        try:
            if "T" in entry_str:
                # ISO format: 2025-11-01T06:30:00
                entry_dt = datetime.fromisoformat(entry_str)
                if entry_dt.tzinfo is None:
                    entry_dt = entry_dt.replace(tzinfo=UTC)
            else:
                entry_dt = datetime.fromisoformat(entry_str)
                if entry_dt.tzinfo is None:
                    entry_dt = entry_dt.replace(tzinfo=UTC)
        except Exception:
            continue

        # Our entry_time = signal bar close time
        # TV entry_time = signal bar + 15min (entry bar open time)
        our_tv_equiv = entry_dt + timedelta(minutes=15)

        direction = side_map.get(t.get("side", ""), "long")
        our_list.append(
            {
                "entry_utc": entry_dt,
                "tv_equiv_utc": our_tv_equiv,
                "direction": direction,
                "price": t.get("entry_price", 0),
                "pnl": t.get("pnl", 0),
            }
        )

    print("\n=== COMPARISON (our_entry_utc + 15min == TV entry UTC) ===")

    matched = 0
    close_match = 0
    no_match = 0

    tv_matched = set()

    for i, our_t in enumerate(our_list):
        our_tv_time = our_t["tv_equiv_utc"]
        our_dir = our_t["direction"]
        our_price = our_t["price"]

        # Find matching TV trade
        best_match = None
        best_diff_min = 9999

        for j, tv_row in tv.iterrows():
            if j in tv_matched:
                continue
            tv_dir = tv_row["direction"]
            tv_time = tv_row["utc"]

            if our_dir != tv_dir:
                continue

            diff_min = abs((our_tv_time - tv_time).total_seconds()) / 60
            if diff_min < best_diff_min:
                best_diff_min = diff_min
                best_match = (j, tv_row)

        if best_diff_min == 0:
            matched += 1
            tv_matched.add(best_match[0])
            tv_row = best_match[1]
            # Check price match
            tv_price = tv_row["price"]
            price_diff_pct = abs(our_price - tv_price) / tv_price * 100
            if price_diff_pct > 0.1:
                print(
                    f"  [{i + 1}] MATCH(time) but PRICE DIFF: our={our_price:.2f} tv={tv_price:.2f} diff={price_diff_pct:.3f}%"
                )
        elif best_diff_min <= 15:
            close_match += 1
            tv_matched.add(best_match[0])
            tv_row = best_match[1]
            print(
                f"  [{i + 1}] CLOSE({best_diff_min:.0f}min): our_tv_eq={our_tv_time} tv={tv_row['utc']} dir={our_dir} our_price={our_price:.2f} tv_price={tv_row['price']:.2f}"
            )
        else:
            no_match += 1
            if no_match <= 15:
                print(
                    f"  [{i + 1}] NO_MATCH: our_tv_eq={our_tv_time} dir={our_dir} price={our_price:.2f} (best diff={best_diff_min:.0f}min)"
                )

    print("\n=== RESULTS ===")
    print(f"Exact matches (0 min diff): {matched}/{len(our_list)}")
    print(f"Close matches (<=15 min): {close_match}/{len(our_list)}")
    print(f"No match: {no_match}/{len(our_list)}")

    print("\n=== TV trades with no match in our results ===")
    unmatched_tv = 0
    for j, tv_row in tv.iterrows():
        if j not in tv_matched:
            unmatched_tv += 1
            if unmatched_tv <= 20:
                print(
                    f"  TV[{j}] dir={tv_row['direction']} time={tv_row['utc']} price={tv_row['price']:.2f} pnl={tv_row['pnl_pct']}"
                )
    print(f"Total unmatched TV trades: {unmatched_tv}")

    # Show our first 10 trades
    print("\n=== OUR FIRST 10 TRADES ===")
    for i, t in enumerate(our_list[:10]):
        print(
            f"  [{i + 1}] {t['direction']:5s} entry={t['entry_utc']} tv_eq={t['tv_equiv_utc']} price={t['price']:.2f} pnl={t['pnl']:.2f}"
        )

    # Show TV first 10 trades
    print("\n=== TV FIRST 10 TRADES ===")
    for _, row in tv.head(10).iterrows():
        print(
            f"  [{row['trade_num']}] {row['direction']:5s} time={row['utc']} price={row['price']:.1f} pnl={row['pnl_pct']}"
        )


if __name__ == "__main__":
    main()
