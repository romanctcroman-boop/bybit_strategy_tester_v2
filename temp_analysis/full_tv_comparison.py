"""Full trade-by-trade comparison: Our backtest vs TradingView CSV export."""

import csv
import json
import sqlite3
from datetime import datetime

# ── Load our backtest trades ──────────────────────────────────────────────────
conn = sqlite3.connect("data.sqlite3")
cur = conn.execute("SELECT trades FROM backtests WHERE id LIKE '68758d14%'")
our_trades = json.loads(cur.fetchone()[0])
conn.close()

# ── Load TradingView trades from CSV ──────────────────────────────────────────
# Each trade in TV CSV has TWO rows: exit row first, then entry row (same trade number)
tv_csv_path = r"c:\Users\roman\Downloads\_RSI_Strategy_TP_SL_BYBIT_ETHUSDT.P_2026-03-01.csv"
tv_raw = {}  # trade_num -> {entry: row, exit: row}

ENTRY_TYPES = {"Вход в короткую позицию", "Вход в длинную позицию"}
EXIT_TYPES = {"Выход из короткой позиции", "Выход из длинной позиции"}
SIDE_MAP = {
    "Вход в короткую позицию": "short",
    "Вход в длинную позицию": "long",
    "Выход из короткой позиции": "short",
    "Выход из длинной позиции": "long",
}

with open(tv_csv_path, encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    for row in reader:
        if not row or not row[0].strip().isdigit():
            continue
        num = int(row[0].strip())
        rtype = row[1].strip()
        dt = row[2].strip()  # "YYYY-MM-DD HH:MM" — TV UTC+3
        sig = row[3].strip()
        price = float(row[4].strip())
        pnl = float(row[7].strip())

        if num not in tv_raw:
            tv_raw[num] = {}
        if rtype in ENTRY_TYPES:
            tv_raw[num]["entry_time"] = dt
            tv_raw[num]["entry_price"] = price
            tv_raw[num]["side"] = SIDE_MAP[rtype]
            tv_raw[num]["signal"] = sig
        elif rtype in EXIT_TYPES:
            tv_raw[num]["exit_time"] = dt
            tv_raw[num]["exit_price"] = price
            tv_raw[num]["exit_signal"] = sig
            tv_raw[num]["pnl"] = pnl

tv_trades = [tv_raw[k] for k in sorted(tv_raw.keys())]

# ── Compare ───────────────────────────────────────────────────────────────────
print(f"TV trades: {len(tv_trades)},  Our trades: {len(our_trades)}")
print()

mismatches_entry_time = []
mismatches_entry_price = []
mismatches_exit_time = []
mismatches_exit_price = []
mismatches_pnl = []
mismatches_side = []

for i, (tv, our) in enumerate(zip(tv_trades, our_trades, strict=False)):
    trade_num = i + 1

    # Convert our UTC entry_time to UTC+3 for comparison with TV
    our_entry_utc = datetime.fromisoformat(our["entry_time"])
    our_exit_utc = datetime.fromisoformat(our["exit_time"])
    # TV times are already in UTC+3 string format
    # Our times are UTC → add 3h to match TV display
    from datetime import timedelta

    our_entry_utc3 = (our_entry_utc + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    our_exit_utc3 = (our_exit_utc + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")

    our_side = "long" if our["side"] == "buy" else "short"

    # Check each field
    ok_entry_time = our_entry_utc3 == tv["entry_time"]
    ok_entry_price = abs(our["entry_price"] - tv["entry_price"]) < 0.01
    ok_exit_time = our_exit_utc3 == tv["exit_time"]
    ok_exit_price = abs(our["exit_price"] - tv["exit_price"]) < 0.01
    ok_pnl = abs(our["pnl"] - tv["pnl"]) < 0.02
    ok_side = our_side == tv["side"]

    if not ok_entry_time:
        mismatches_entry_time.append((trade_num, tv["entry_time"], our_entry_utc3))
    if not ok_entry_price:
        mismatches_entry_price.append((trade_num, tv["entry_price"], our["entry_price"]))
    if not ok_exit_time:
        mismatches_exit_time.append((trade_num, tv["exit_time"], our_exit_utc3))
    if not ok_exit_price:
        mismatches_exit_price.append((trade_num, tv["exit_price"], our["exit_price"]))
    if not ok_pnl:
        mismatches_pnl.append((trade_num, tv["pnl"], our["pnl"]))
    if not ok_side:
        mismatches_side.append((trade_num, tv["side"], our_side))


# ── Results ───────────────────────────────────────────────────────────────────
def report(label, mismatches):
    if not mismatches:
        print(f"  {label}: ALL {len(tv_trades)} MATCH  [OK]")
    else:
        print(f"  {label}: {len(mismatches)} MISMATCHES  [FAIL]")
        for m in mismatches:
            print(f"    Trade #{m[0]:3d}:  TV={m[1]}  Ours={m[2]}")


print("=== Field-by-field comparison (all 155 trades) ===")
report("Entry time  ", mismatches_entry_time)
report("Entry price ", mismatches_entry_price)
report("Exit time   ", mismatches_exit_time)
report("Exit price  ", mismatches_exit_price)
report("PnL         ", mismatches_pnl)
report("Side        ", mismatches_side)

total_issues = (
    len(mismatches_entry_time)
    + len(mismatches_entry_price)
    + len(mismatches_exit_time)
    + len(mismatches_exit_price)
    + len(mismatches_pnl)
    + len(mismatches_side)
)
print()
print(f"Total field mismatches: {total_issues}")
if total_issues == 0:
    print("PERFECT PARITY WITH TRADINGVIEW")
