"""
Clone backtest e4e67c82 — make ALL trade fields identical to trade[0],
keeping only entry_time and exit_time of each original trade.
Save as new backtest row in DB.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone

BT_ID = "e4e67c82-1258-4ce5-bb80-48c22ebbe019"

conn = sqlite3.connect("data.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ── 1. Load source backtest ──────────────────────────────────────────────────
cur.execute("SELECT * FROM backtests WHERE id=?", (BT_ID,))
src = dict(cur.fetchone())

# ── 2. Load trades JSON ──────────────────────────────────────────────────────
trades_orig = json.loads(src["trades"])
print(f"Original trades: {len(trades_orig)}")

# ── 3. Reference values from trade[0] ───────────────────────────────────────
ref = trades_orig[0]
print(f"\nReference (trade[0]) values that will be cloned to all trades:")
clone_fields = [
    "side",
    "entry_price",
    "exit_price",
    "size",
    "pnl",
    "pnl_pct",
    "fees",
    "commission",
    "duration_bars",
    "bars_in_trade",
    "duration_hours",
    "exit_comment",
    "is_open",
    "direction",
    "mfe",
    "mae",
    "mfe_pct",
    "mae_pct",
    "dca_orders_filled",
    "grid_level",
]
for f in clone_fields:
    print(f"  {f}: {ref.get(f)}")

# ── 4. Build cloned trades list ───────────────────────────────────────────────
# Keep entry_time, exit_time, trade_number, entry_bar_index, exit_bar_index
# Replace everything else with ref values
cloned_trades = []
for i, t in enumerate(trades_orig):
    ct = dict(ref)  # start from ref
    # Preserve timing and identity fields
    ct["entry_time"] = t["entry_time"]
    ct["exit_time"] = t["exit_time"]
    ct["trade_number"] = t.get("trade_number", i + 1)
    ct["entry_bar_index"] = t.get("entry_bar_index")
    ct["exit_bar_index"] = t.get("exit_bar_index")
    cloned_trades.append(ct)

print(f"\nCloned trades: {len(cloned_trades)}")
print(f"Trade[0]:  entry={cloned_trades[0]['entry_time']}  exit={cloned_trades[0]['exit_time']}")
print(f"Trade[12]: entry={cloned_trades[12]['entry_time']}  exit={cloned_trades[12]['exit_time']}")
print(f"Trade[25]: entry={cloned_trades[25]['entry_time']}  exit={cloned_trades[25]['exit_time']}")
print(f"All mfe:  {[t['mfe'] for t in cloned_trades]}")
print(f"All mae:  {[t['mae'] for t in cloned_trades]}")

# ── 5. Build cloned equity curve (keep timestamps, set equity to linear) ─────
ec_orig = json.loads(src["equity_curve"])
ic = src["initial_capital"] or 10000
# Equity: flat — all trades same PnL, so cumulative is linear
pnl_per_trade = ref["pnl"]
ec_cloned = dict(ec_orig)
n = len(ec_orig["timestamps"])
ec_cloned["equity"] = [ic + pnl_per_trade * (i + 1) for i in range(n)]
# Keep other arrays as-is (drawdown, bh_equity, etc.)

# ── 6. Insert as new backtest row ─────────────────────────────────────────────
new_id = str(uuid.uuid4())
now = datetime.now(timezone.utc).isoformat()

# Build column list from source, excluding id + timestamps we'll override
exclude = {"id", "created_at", "updated_at", "started_at", "completed_at", "trades", "equity_curve", "notes"}
cols = [k for k in src.keys() if k not in exclude]

values = {k: src[k] for k in cols}
values["id"] = new_id
values["created_at"] = now
values["updated_at"] = now
values["started_at"] = now
values["completed_at"] = now
values["notes"] = f"CLONE_TEST: all trade fields identical (ref=trade[0]), times kept. source={BT_ID}"
values["trades"] = json.dumps(cloned_trades)
values["equity_curve"] = json.dumps(ec_cloned)

all_cols = list(values.keys())
placeholders = ", ".join(["?"] * len(all_cols))
col_names = ", ".join(all_cols)
sql = f"INSERT INTO backtests ({col_names}) VALUES ({placeholders})"

cur.execute(sql, [values[c] for c in all_cols])
conn.commit()
print(f"\n✅ Cloned backtest saved: id={new_id}")
print(f"   notes: {values['notes']}")
conn.close()
