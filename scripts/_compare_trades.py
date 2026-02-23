import csv
import json
import sqlite3
from datetime import datetime, timedelta

TV_CSV = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"
DB_PATH = "D:/bybit_strategy_tester_v2/data.sqlite3"

tv = {}
with open(TV_CSV, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        keys = list(row.keys())
        num = int(row[keys[0]])
        ttype = row[keys[1]]
        dt = row[keys[2]]
        sig = row[keys[3]]
        price = float(row[keys[4]])
        pnl = float(row[keys[8]])
        if num not in tv:
            tv[num] = {}
        if "Entry" in ttype:
            tv[num]["dir"] = "long" if "long" in ttype.lower() else "short"
            tv[num]["entry_dt"] = dt
            tv[num]["entry_price"] = price
        elif "Exit" in ttype:
            tv[num]["exit_dt"] = dt
            tv[num]["exit_price"] = price
            tv[num]["pnl_pct"] = pnl
            tv[num]["exit_sig"] = sig

print(f"TV total trades: {len(tv)}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""SELECT b.id, b.trades FROM backtests b JOIN strategies s ON s.id=b.strategy_id
               WHERE s.name LIKE '%RSI_L%S%3%' AND s.is_deleted=0
               ORDER BY b.created_at DESC LIMIT 1""")
row = cur.fetchone()
conn.close()

bid = row[0]
trades_json = row[1]
raw_our = json.loads(trades_json) if isinstance(trades_json, str) else (trades_json or [])
raw_our.sort(key=lambda t: t.get("entry_time", ""))
our_list = [
    {
        "side": t.get("side", ""),
        "entry_time": t.get("entry_time", "")[:16],
        "entry_price": float(t.get("entry_price", 0) or 0),
        "exit_time": t.get("exit_time", "")[:16],
        "exit_price": float(t.get("exit_price", 0) or 0),
        "pnl_pct": float(t.get("pnl_pct", 0) or 0),  # stored with leverage e.g. 14.3%
        "exit_comment": t.get("exit_comment", ""),
    }
    for t in raw_our
]
print(f"Our total trades: {len(our_list)} (BID: {bid})")
print()


# ── Match TV trades to our trades by entry time proximity ──
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


# Build our index by entry_time
our_by_entry = {}
for o in our_list:
    dt = parse_dt(o["entry_time"])
    if dt:
        our_by_entry[dt] = o

# For each TV trade find best match in our trades (within 4 bars = 1h on 15m)
TV_TOLERANCE = timedelta(hours=4)

matched = []
unmatched_tv = []
used_our = set()

tv_sorted = [(n, tv[n]) for n in sorted(tv.keys()) if "entry_dt" in tv[n]]

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

# Our trades with no TV match
unmatched_our = [o for o in our_list if id(o) not in used_our]

# ── Print matched comparison ──
print(
    f"{'#':>3}  {'Dir':5}  {'TV Entry':>16}  {'TVep':>10}  {'OurEntry':>16}  {'OurEP':>10}  "
    f"{'DT(min)':>7}  {'TV Exit':>16}  {'TVxp':>10}  {'OurExit':>16}  {'OurXP':>10}  "
    f"{'TV%':>6}  {'OurLev%':>7}  TV Sig"
)
print("-" * 185)

ep_diffs = []
for tv_num, t, o, delta_min in matched:
    ten = t.get("entry_dt", "")[:16]
    tep = t.get("entry_price", 0)
    txn = t.get("exit_dt", "")[:16]
    txp = t.get("exit_price", 0)
    tpnl = t.get("pnl_pct", 0)
    tsig = t.get("exit_sig", "")[:12]

    oen = o["entry_time"][:16]
    oep = o["entry_price"]
    oxn = o["exit_time"][:16]
    oxp = o["exit_price"]
    opnl_lev = o["pnl_pct"]  # with leverage

    ep_diff = tep - oep
    ep_diffs.append(ep_diff)
    flag = f"  EPdelta={ep_diff:+.0f}" if abs(ep_diff) > 50 else ""
    flag += f"  SHIFT={delta_min / 15:.1f}bars" if delta_min > 15 else ""

    print(
        f"{tv_num:>3}  {t.get('dir', '?'):5}  {ten:>16}  {tep:>10.1f}  {oen:>16}  {oep:>10.1f}  "
        f"{delta_min:>7.0f}  {txn:>16}  {txp:>10.1f}  {oxn:>16}  {oxp:>10.1f}  "
        f"{tpnl:>6.2f}  {opnl_lev:>7.2f}  {tsig}{flag}"
    )

print()
print(f"=== MATCHED: {len(matched)}/{len(tv_sorted)} TV trades ===")
print(f"=== UNMATCHED TV  (MISSING from our engine): {unmatched_tv} ===")
print(f"=== UNMATCHED OUR (EXTRA in our engine): {len(unmatched_our)} ===")
if unmatched_our:
    for o in unmatched_our:
        print(
            f"     OUR extra: {o['side']:5} entry={o['entry_time']} @ {o['entry_price']:.1f}  "
            f"exit={o['exit_time']} pnl={o['pnl_pct']:.2f}%"
        )

if unmatched_tv:
    print()
    for tv_num in unmatched_tv:
        t = tv[tv_num]
        print(
            f"     TV  miss#: {tv_num}  {t.get('dir', '?'):5} entry={t.get('entry_dt', '')[:16]} @ "
            f"{t.get('entry_price', 0):.1f}  exit={t.get('exit_dt', '')[:16]} pnl={t.get('pnl_pct', 0):.2f}%  {t.get('exit_sig', '')}"
        )

print()
if ep_diffs:
    avg_diff = sum(ep_diffs) / len(ep_diffs)
    pos_diffs = [d for d in ep_diffs if d > 0]
    neg_diffs = [d for d in ep_diffs if d < 0]
    print("Entry price delta (TV_ep - Our_ep):")
    print(f"  avg={avg_diff:+.1f}  median={sorted(ep_diffs)[len(ep_diffs) // 2]:+.1f}")
    print(f"  min={min(ep_diffs):+.1f}  max={max(ep_diffs):+.1f}")
    print(f"  TV > Our (TV enters higher): {len(pos_diffs)}/{len(ep_diffs)}")
    print(f"  TV < Our (TV enters lower):  {len(neg_diffs)}/{len(ep_diffs)}")
    print("  -> Consistent with TV entering at signal-bar CLOSE, we at NEXT bar OPEN")

print()
tv_p = [v["pnl_pct"] for v in tv.values() if "pnl_pct" in v]
our_p = [o["pnl_pct"] for o in our_list]
print(
    f"TV  wins={sum(1 for p in tv_p if p > 0)}/{len(tv_p)}  sum(raw%)={sum(tv_p):.2f}%  avg={sum(tv_p) / len(tv_p):.3f}%/trade"
)
print(
    f"Our wins={sum(1 for p in our_p if p > 0)}/{len(our_p)}  sum(lev%)={sum(our_p):.2f}%  avg={sum(our_p) / len(our_p):.3f}%/trade  (with 10x leverage)"
)
print(
    f"Our wins={sum(1 for p in our_p if p > 0)}/{len(our_p)}  sum(adj%)={sum(our_p) / 10:.2f}%  avg={sum(our_p) / len(our_p) / 10:.3f}%/trade  (div10 for raw equiv)"
)
print()
print("REFERENCE: TV 1.36% = TP(1.5%) - commission x2 (0.14%). TV -3.34% = SL(-3.2%) - commission x2")
print("Our TP at 10x: +15% approx (1.5% x10) - fees. Our SL at 10x: -33% approx (3.2% x10) + fees")
