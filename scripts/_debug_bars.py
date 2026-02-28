"""Debug: find why MFE/MAE bars are missing for some trades."""

import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime

conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()
cur.execute("SELECT id, equity_curve, trades FROM backtests ORDER BY created_at DESC LIMIT 1")
row = cur.fetchone()
if not row:
    print("No backtests found")
    conn.close()
    exit()

bid, ec_json, trades_json = row
trades = json.loads(trades_json) if trades_json else []
ec = json.loads(ec_json) if ec_json else {}
ts_list = ec.get("timestamps", []) if isinstance(ec, dict) else []


def to_sec(s):
    if not s:
        return None
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


ec_sec = [to_sec(t) for t in ts_list]


def closest(exit_sec, win=21600):
    if not exit_sec:
        return None, None
    best_i, best_d = None, 9e9
    for i, e in enumerate(ec_sec):
        if e is None:
            continue
        d = abs(e - exit_sec)
        if d < best_d:
            best_d = d
            best_i = i
    if best_i is not None and best_d <= win:
        return ec_sec[best_i], best_d
    return None, None


print(f"Backtest: {bid}")
print(f"Trades={len(trades)}  EC_pts={len(ts_list)}")

cmap = defaultdict(list)
no_match = []
for i, t in enumerate(trades):
    ex = to_sec(t.get("exit_time", ""))
    et, diff = closest(ex)
    cmap[et].append((i + 1, diff))
    if et is None:
        no_match.append(i + 1)

print()
print("=== Collisions (multiple trades -> same EC timestamp) ===")
found = False
for et, items in sorted(cmap.items(), key=lambda x: x[0] or 0):
    if len(items) > 1:
        found = True
        dt = datetime.fromtimestamp(et, tz=UTC).strftime("%Y-%m-%d %H:%M") if et else "None"
        nums = [n for n, _ in items]
        diffs = [d for _, d in items]
        print(f"  {dt}: trades {nums}  diffs(s)={[int(d) for d in diffs]}")
if not found:
    print("  None found")

print()
print(f"=== Trades with NO EC match (window=6h): {no_match if no_match else 'None'} ===")

print()
print("=== First 20 trades: exit_time vs nearest EC time ===")
for i, t in enumerate(trades[:20]):
    ex = to_sec(t.get("exit_time", ""))
    et, diff = closest(ex)
    mfe = abs(t.get("mfe") or 0)
    mae = abs(t.get("mae") or 0)
    et_str = datetime.fromtimestamp(et, tz=UTC).strftime("%Y-%m-%d %H:%M") if et else "NONE"
    print(f"  #{i + 1:3d} exit={t.get('exit_time', '')}  ec={et_str}  diff={diff}s  mfe={mfe:.2f}  mae={mae:.2f}")

conn.close()

