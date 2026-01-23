"""Match trades between fallback and vectorbt reports.
Reads logs/compare_vectorbt_vs_fallback.json and outputs logs/matched_trades.json
"""

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "logs" / "compare_vectorbt_vs_fallback.json"
OUT = ROOT / "logs" / "matched_trades.json"

if not IN.exists():
    print("Input report not found:", IN)
    raise SystemExit(1)

with IN.open("r", encoding="utf-8") as f:
    data = json.load(f)

fb_trades = data.get("sample_trades", {}).get("fallback_trades_sample", [])
vb_trades = data.get("sample_trades", {}).get("vectorbt_trades_sample", [])

# parse times and build simple match by side and nearest entry_time
from dateutil import parser

for t in fb_trades:
    t["entry_dt"] = parser.parse(t["entry_time"]) if t.get("entry_time") else None
for t in vb_trades:
    t["entry_dt"] = parser.parse(t["entry_time"]) if t.get("entry_time") else None

matches = []
used_vb = set()

for i, ft in enumerate(fb_trades):
    best_j = None
    best_dt = None
    for j, vt in enumerate(vb_trades):
        if j in used_vb:
            continue
        # match by side first
        if ft.get("side") != vt.get("side"):
            continue
        if not ft.get("entry_dt") or not vt.get("entry_dt"):
            continue
        dt = abs((ft["entry_dt"] - vt["entry_dt"]).total_seconds())
        if best_dt is None or dt < best_dt:
            best_dt = dt
            best_j = j
    if best_j is not None and best_dt is not None and best_dt <= 86400:  # within 1 day
        used_vb.add(best_j)
        matches.append(
            {
                "fallback_idx": i,
                "vectorbt_idx": best_j,
                "time_diff_s": best_dt,
                "fallback": ft,
                "vectorbt": vb_trades[best_j],
            }
        )
    else:
        matches.append(
            {
                "fallback_idx": i,
                "vectorbt_idx": None,
                "time_diff_s": None,
                "fallback": ft,
                "vectorbt": None,
            }
        )

# any vb trades not matched
unmatched_vb = [
    {"vectorbt_idx": j, "vectorbt": vt}
    for j, vt in enumerate(vb_trades)
    if j not in used_vb
]

out = {
    "matches": matches,
    "unmatched_vectorbt": unmatched_vb,
    "counts": {
        "fallback_sample": len(fb_trades),
        "vectorbt_sample": len(vb_trades),
        "matched_pairs": sum(1 for m in matches if m["vectorbt_idx"] is not None),
        "unmatched_vectorbt": len(unmatched_vb),
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, default=str, ensure_ascii=False)

print("Wrote", OUT)
