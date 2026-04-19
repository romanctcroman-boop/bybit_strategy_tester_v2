"""
Deep analysis: Why are we missing TV trades and generating extra ones?
Focus on signal generation debugging.
"""

import csv
import json
import sqlite3
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "D:/bybit_strategy_tester_v2")

TV_CSV = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"
DB_PATH = "D:/bybit_strategy_tester_v2/data.sqlite3"

# Load TV trades
tv = {}
with open(TV_CSV, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        keys = list(row.keys())
        num_key = keys[0]
        num_str = row[num_key].strip()
        if not num_str:
            continue
        num = int(num_str)
        ttype = row[keys[1]]
        dt_str = row[keys[2]]
        sig = row[keys[3]]
        price = float(row[keys[4]])
        pnl = float(row[keys[8]])
        if num not in tv:
            tv[num] = {}
        if "Entry" in ttype:
            tv[num]["dir"] = "long" if "long" in ttype.lower() else "short"
            tv[num]["entry_dt"] = dt_str
            tv[num]["entry_price"] = price
        elif "Exit" in ttype:
            tv[num]["exit_dt"] = dt_str
            tv[num]["exit_price"] = price
            tv[num]["pnl_pct"] = pnl
            tv[num]["exit_sig"] = sig

tv_sorted = [(n, tv[n]) for n in sorted(tv.keys()) if "entry_dt" in tv[n]]
print(f"TV trades: {len(tv_sorted)}")

# Load our trades
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(
    """SELECT b.id, b.trades FROM backtests b JOIN strategies s ON s.id=b.strategy_id
       WHERE s.name LIKE '%RSI_L%S%3%' AND s.is_deleted=0
       ORDER BY b.created_at DESC LIMIT 1"""
)
row = cur.fetchone()
conn.close()

bid = row[0]
raw_our = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
raw_our.sort(key=lambda t: t.get("entry_time", ""))
our_list = [
    {
        "side": t.get("side", ""),
        "entry_time": t.get("entry_time", "")[:16],
        "entry_price": float(t.get("entry_price", 0) or 0),
        "exit_time": t.get("exit_time", "")[:16],
        "exit_price": float(t.get("exit_price", 0) or 0),
        "pnl_pct": float(t.get("pnl_pct", 0) or 0),
        "exit_comment": t.get("exit_comment", ""),
    }
    for t in raw_our
]
print(f"Our trades: {len(our_list)} (backtest_id={bid})")
print()


def parse_dt(s):
    if not s:
        return None
    s = s[:16]
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


# Build our index
our_by_entry = {}
for o in our_list:
    dt = parse_dt(o["entry_time"])
    if dt:
        our_by_entry[dt] = o

TV_TOLERANCE = timedelta(hours=4)

matched = []
unmatched_tv = []
used_our = set()

for tv_num, t in tv_sorted:
    tv_dt = parse_dt(t.get("entry_dt", ""))
    if tv_dt is None:
        unmatched_tv.append(tv_num)
        continue

    best_key = None
    best_delta = TV_TOLERANCE + timedelta(seconds=1)
    for odt, o in our_by_entry.items():
        if id(o) in used_our:
            continue
        delta = abs(tv_dt - odt)
        if delta < best_delta:
            best_delta = delta
            best_key = odt

    if best_key is not None:
        o = our_by_entry[best_key]
        used_our.add(id(o))
        matched.append((tv_num, t, o, best_delta.total_seconds() / 60))
    else:
        unmatched_tv.append(tv_num)

unmatched_our = [o for o in our_list if id(o) not in used_our]

print(f"MATCHED: {len(matched)}/{len(tv_sorted)}")
print(f"MISSING TV trades: {len(unmatched_tv)}")
print(f"EXTRA our trades: {len(unmatched_our)}")
print()

# Analyze patterns in unmatched TV trades
print("=" * 80)
print("MISSING TV TRADES (first 20):")
print(f"{'#':>4} {'Dir':5} {'Entry':>16} {'EP':>10} {'Exit':>16} {'XP':>10} {'PnL':>6} {'Sig':12}")
print("-" * 90)
for tv_num in unmatched_tv[:20]:
    t = tv[tv_num]
    print(
        f"{tv_num:>4} {t.get('dir', '?'):5} {t.get('entry_dt', '')[:16]:>16} "
        f"{t.get('entry_price', 0):>10.1f} {t.get('exit_dt', '')[:16]:>16} "
        f"{t.get('exit_price', 0):>10.1f} {t.get('pnl_pct', 0):>6.2f} {t.get('exit_sig', '')[:12]:12}"
    )

print()
print("=" * 80)
print("EXTRA OUR TRADES (first 20):")
print(f"{'Dir':5} {'Entry':>16} {'EP':>10} {'Exit':>16} {'XP':>10} {'PnL_lev%':>9} {'Comment':20}")
print("-" * 90)
for o in unmatched_our[:20]:
    print(
        f"{o['side']:5} {o['entry_time'][:16]:>16} {o['entry_price']:>10.1f} "
        f"{o['exit_time'][:16]:>16} {o['exit_price']:>10.1f} {o['pnl_pct']:>9.2f} {o['exit_comment'][:20]}"
    )

print()
print("=" * 80)

# Check overlap: missing TV around what our has
print("\nANALYSIS: Check if missing TV trades are adjacent to matched ones")
matched_tv_nums = {tv_num for tv_num, t, o, dm in matched}
print("Consecutive missing runs:")
run = []
for tv_num, t in tv_sorted:
    if tv_num in matched_tv_nums:
        if run:
            print(f"  Missing run: {run}")
            run = []
    else:
        run.append(tv_num)
if run:
    print(f"  Missing run: {run}")

# Statistics on matching
print()
print("MATCHED QUALITY (entry time delta distribution):")
deltas = sorted(d for _, _, _, d in matched)
bins = [0, 15, 30, 60, 120, 240]
for i in range(len(bins) - 1):
    count = sum(1 for d in deltas if bins[i] <= d < bins[i + 1])
    print(f"  {bins[i]}-{bins[i + 1]}min: {count} trades")
exact = sum(1 for d in deltas if d == 0)
print(f"  Exact match (0min): {exact}/{len(deltas)}")

# Check direction distribution
tv_longs = sum(1 for _, t in tv_sorted if t.get("dir") == "long")
tv_shorts = sum(1 for _, t in tv_sorted if t.get("dir") == "short")
our_longs = sum(1 for o in our_list if o["side"] == "long")
our_shorts = sum(1 for o in our_list if o["side"] == "short")
print()
print("DIRECTION DISTRIBUTION:")
print(f"  TV:  longs={tv_longs} shorts={tv_shorts}")
print(f"  Our: longs={our_longs} shorts={our_shorts}")

miss_longs = sum(1 for n in unmatched_tv if tv[n].get("dir") == "long")
miss_shorts = sum(1 for n in unmatched_tv if tv[n].get("dir") == "short")
extra_longs = sum(1 for o in unmatched_our if o["side"] == "long")
extra_shorts = sum(1 for o in unmatched_our if o["side"] == "short")
print(f"  Missing: longs={miss_longs} shorts={miss_shorts}")
print(f"  Extra:   longs={extra_longs} shorts={extra_shorts}")
