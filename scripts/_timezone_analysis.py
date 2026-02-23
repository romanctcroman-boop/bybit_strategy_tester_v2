"""
Better trade comparison: normalize side names, use shorter tolerance.
TV uses long/short, our engine uses buy/sell.
Entry times differ: TV has '2025-11-01 09:45', ours has '2025-11-01T01:45' (UTC vs Moscow?).
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
tv: dict = {}
with open(TV_CSV, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        keys = list(row.keys())
        num_str = row[keys[0]].strip()
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

raw_our = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
raw_our.sort(key=lambda t: t.get("entry_time", ""))


# Normalize side: buy->long, sell->short
def normalize_side(s):
    s = (s or "").lower()
    if s in ("buy", "long"):
        return "long"
    if s in ("sell", "short"):
        return "short"
    return s


our_list = [
    {
        "side": normalize_side(t.get("side", "")),
        "entry_time": t.get("entry_time", "")[:16].replace("T", " "),
        "entry_price": float(t.get("entry_price", 0) or 0),
        "exit_time": t.get("exit_time", "")[:16].replace("T", " "),
        "exit_price": float(t.get("exit_price", 0) or 0),
        "pnl_pct": float(t.get("pnl_pct", 0) or 0),
        "exit_comment": t.get("exit_comment", ""),
    }
    for t in raw_our
]

print(f"TV trades: {len(tv_sorted)}")
print(f"Our trades: {len(our_list)}")
print()


def parse_dt(s):
    if not s:
        return None
    s = s[:16].replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M",):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


# Print time difference analysis
print("=== ENTRY TIME COMPARISON (first 20 from each) ===")
print(f"TV first 5 entries: {[t[1].get('entry_dt', '')[:16] for t in tv_sorted[:5]]}")
print(f"Our first 5 entries: {[o['entry_time'][:16] for o in our_list[:5]]}")
print()

# Check time offset between TV and our times
# TV: 2025-11-01 09:45, Our: 2025-11-01T01:45 = 8 hour difference?
# Or TV: 2025-11-01 09:45 Moscow time = 2025-11-01 06:45 UTC?
# Our first extra trade: 2025-11-01T01:45
# TV first trade: 2025-11-01 09:45
# Difference = 8 hours?? That would be UTC+8 = SGT/HKT/CST
# But Moscow = UTC+3. So 09:45 Moscow = 06:45 UTC? But our is 01:45 = diff is 5h?
#
# Wait: TV shows "2025-11-01 09:45" - this could be exchange local time or user's timezone
# Our shows "2025-11-01T01:45" in UTC
# Diff: 09:45 - 01:45 = 8 hours offset.
# That's UTC+8 (China/Singapore/HK time) in TV settings?

tv_first_dt = parse_dt(tv_sorted[0][1]["entry_dt"])
our_first_dt = parse_dt(our_list[0]["entry_time"])
if tv_first_dt and our_first_dt:
    offset = tv_first_dt - our_first_dt
    print(f"TV first entry time: {tv_first_dt}")
    print(f"Our first entry time: {our_first_dt}")
    print(f"Offset: {offset} ({offset.total_seconds() / 3600:.1f} hours)")
    print()

# Try matching WITH time offset correction
# Let's try different offsets: 0h, 3h (Moscow), 5h, 8h
for offset_hours in [0, 3, 5, 6, 7, 8]:
    offset = timedelta(hours=offset_hours)
    matched_count = 0
    TIGHT = timedelta(minutes=30)  # 2 bars tolerance

    used_local = set()
    our_index = {}
    for o in our_list:
        dt = parse_dt(o["entry_time"])
        if dt:
            our_index[dt] = o

    for tv_num, t in tv_sorted:
        tv_dt = parse_dt(t.get("entry_dt", ""))
        if tv_dt is None:
            continue
        tv_dt_adj = tv_dt - offset  # Convert TV time to UTC

        best_key = None
        best_delta = TIGHT + timedelta(seconds=1)
        for odt, o in our_index.items():
            if id(o) in used_local:
                continue
            delta = abs(tv_dt_adj - odt)
            if delta < best_delta:
                best_delta = delta
                best_key = odt

        if best_key is not None:
            used_local.add(id(our_index[best_key]))
            matched_count += 1

    print(f"Offset={offset_hours}h: matched {matched_count}/{len(tv_sorted)} (within 30min)")

print()
print("=== DETAILED MATCH WITH BEST OFFSET ===")
# Use offset=8h based on the analysis above
OFFSET = timedelta(hours=8)
TIGHT = timedelta(minutes=30)

our_index2 = {}
for o in our_list:
    dt = parse_dt(o["entry_time"])
    if dt:
        our_index2[dt] = o

matched2 = []
unmatched_tv2 = []
used2 = set()

for tv_num, t in tv_sorted:
    tv_dt = parse_dt(t.get("entry_dt", ""))
    if tv_dt is None:
        unmatched_tv2.append(tv_num)
        continue
    tv_dt_adj = tv_dt - OFFSET

    best_key = None
    best_delta = TIGHT + timedelta(seconds=1)
    for odt, o in our_index2.items():
        if id(o) in used2:
            continue
        if normalize_side("long") != o["side"] and normalize_side("short") != o["side"]:
            continue
        # Also check direction matches
        tv_dir = t.get("dir", "")
        if o["side"] != tv_dir:
            continue
        delta = abs(tv_dt_adj - odt)
        if delta < best_delta:
            best_delta = delta
            best_key = odt

    if best_key is not None:
        o = our_index2[best_key]
        used2.add(id(o))
        matched2.append((tv_num, t, o, best_delta.total_seconds() / 60))
    else:
        unmatched_tv2.append(tv_num)

unmatched_our2 = [o for o in our_list if id(o) not in used2]
print("With offset=8h + direction match + 30min tolerance:")
print(f"  Matched: {len(matched2)}/{len(tv_sorted)}")
print(f"  Missing TV: {len(unmatched_tv2)}")
print(f"  Extra Our: {len(unmatched_our2)}")
print()
print("  Match quality (time deltas):")
deltas2 = sorted(d for _, _, _, d in matched2)
for threshold in [0, 1, 2, 5, 15, 30]:
    c = sum(1 for d in deltas2 if d <= threshold)
    print(f"    <= {threshold}min: {c}/{len(deltas2)}")

print()
print("MISSING TV trades (first 30):")
for n in unmatched_tv2[:30]:
    t = tv[n]
    print(
        f"  #{n:3} {t.get('dir', ''):5} {t.get('entry_dt', '')[:16]} @{t.get('entry_price', 0):.0f} -> {t.get('exit_sig', '')[:10]}"
    )

print()
print("EXTRA Our trades (first 30):")
for o in unmatched_our2[:30]:
    print(f"  {o['side']:5} {o['entry_time'][:16]} @{o['entry_price']:.0f} -> {o['exit_comment'][:10]}")
