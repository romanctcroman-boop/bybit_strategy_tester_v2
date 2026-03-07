"""
DB Diagnostic & Repair for Strategy_DCA_RSI_02.

What this does:
1. Reads the strategy from the database
2. Shows builder_blocks / builder_connections / builder_graph state
3. If builder_blocks is NULL, copies from builder_graph["blocks"] (repair)
4. Tests has_dca_blocks() and extract_dca_config() from the adapter
5. Shows what engine would be selected

Run with:
    py -3.14 temp_analysis/db_repair_dca_rsi02.py
    py -3.14 temp_analysis/db_repair_dca_rsi02.py --repair   # actually write to DB
"""

import sys
import json
import sqlite3

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

STRATEGY_NAME = "Strategy_DCA_RSI_02"
DB_PATH = "data.sqlite3"

DO_REPAIR = "--repair" in sys.argv

# ─── 1. Load strategy from DB ────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(
    "SELECT id, name, builder_blocks, builder_connections, builder_graph "
    "FROM strategies WHERE name = ? AND is_deleted = 0",
    (STRATEGY_NAME,),
)
row = cur.fetchone()

if not row:
    print(f"ERROR: strategy '{STRATEGY_NAME}' not found in DB.")
    conn.close()
    sys.exit(1)

strat_id, strat_name = row[0], row[1]
raw_blocks = row[2]
raw_connections = row[3]
raw_graph = row[4]

builder_blocks = json.loads(raw_blocks) if raw_blocks else None
builder_connections = json.loads(raw_connections) if raw_connections else None
builder_graph = json.loads(raw_graph) if raw_graph else None

print("=" * 60)
print(f"Strategy: {strat_name}")
print(f"ID:       {strat_id}")
print("=" * 60)

print(f"\nbuilder_blocks:      {'NULL' if builder_blocks is None else f'{len(builder_blocks)} blocks'}")
print(f"builder_connections: {'NULL' if builder_connections is None else f'{len(builder_connections)} connections'}")

if builder_graph:
    bg_keys = list(builder_graph.keys())
    bg_blocks = builder_graph.get("blocks", [])
    bg_conns = builder_graph.get("connections", [])
    print(f"builder_graph:       {len(bg_blocks)} blocks, {len(bg_conns)} connections (keys: {bg_keys})")
else:
    print("builder_graph:       NULL")

# ─── 2. Determine effective blocks ───────────────────────────────────────────
effective_blocks = builder_blocks
effective_connections = builder_connections

if not effective_blocks and builder_graph:
    effective_blocks = builder_graph.get("blocks", [])
    effective_connections = builder_graph.get("connections", [])
    print(f"\n[!] builder_blocks is NULL — falling back to builder_graph['blocks'] ({len(effective_blocks)} blocks)")

if not effective_blocks:
    print("\nERROR: No blocks found anywhere (builder_blocks AND builder_graph both empty).")
    conn.close()
    sys.exit(1)

print("\nEffective blocks:")
for b in effective_blocks:
    print(f"  type={b.get('type', '?')!r:25} category={b.get('category', '')!r:20} id={b.get('id', '')!r}")

# ─── 3. Optionally repair DB ─────────────────────────────────────────────────
if DO_REPAIR and not builder_blocks and effective_blocks:
    print("\n[REPAIR] Writing blocks/connections to builder_blocks / builder_connections in DB...")
    cur.execute(
        "UPDATE strategies SET builder_blocks = ?, builder_connections = ? WHERE id = ?",
        (
            json.dumps(effective_blocks),
            json.dumps(effective_connections or []),
            strat_id,
        ),
    )
    conn.commit()
    print(f"  Written {len(effective_blocks)} blocks and {len(effective_connections or [])} connections.")
elif DO_REPAIR and builder_blocks:
    print("\n[REPAIR] builder_blocks already populated — no repair needed.")
elif not DO_REPAIR and not builder_blocks:
    print("\n[INFO] Run with --repair to copy blocks from builder_graph to builder_blocks.")

conn.close()

# ─── 4. Test adapter DCA detection ───────────────────────────────────────────
print("\n" + "─" * 60)
print("Adapter DCA Detection")
print("─" * 60)

try:
    from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter
except ImportError:
    # Fall back to backward-compat stub location
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

strategy_graph = {
    "name": strat_name,
    "blocks": effective_blocks,
    "connections": effective_connections or [],
    "interval": "15",
}
# Include main_strategy if present in builder_graph
if builder_graph and builder_graph.get("main_strategy"):
    strategy_graph["main_strategy"] = builder_graph["main_strategy"]

adapter = StrategyBuilderAdapter(strategy_graph)

has_dca = adapter.has_dca_blocks()
dca_cfg = adapter.extract_dca_config()

print(f"has_dca_blocks():  {has_dca}")
print(f"dca_enabled:       {dca_cfg.get('dca_enabled')}")
print(f"order_count:       {dca_cfg.get('dca_order_count')}")
print(f"grid_size_percent: {dca_cfg.get('dca_grid_size_percent')}")
print(f"direction:         {dca_cfg.get('dca_direction')}")
print(f"martingale_coef:   {dca_cfg.get('dca_martingale_coef')}")
print(f"custom_orders:     {dca_cfg.get('custom_orders') is not None}")

# Router engine-selection simulation
request_dca_enabled = False  # user did NOT set dca_enabled in the request
dca_enabled_final = (
    request_dca_enabled
    or has_dca
    or dca_cfg.get("dca_enabled", False)
)

print(f"\nEngine selection: dca_enabled = {dca_enabled_final}")
if dca_enabled_final:
    print("  → DCAEngine would be used ✓")
else:
    print("  → FallbackEngineV4 would be used ✗  (BUG!)")

# ─── 5. Summary ──────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
checks = [
    ("builder_blocks in DB",             bool(builder_blocks)),
    ("blocks available (any source)",    bool(effective_blocks)),
    ("has_dca_blocks() = True",          has_dca),
    ("extract_dca_config dca_enabled",   dca_cfg.get("dca_enabled", False)),
    ("DCAEngine selected",               dca_enabled_final),
]
all_ok = all(ok for _, ok in checks)
for desc, ok in checks:
    icon = "✓" if ok else "✗"
    print(f"  {icon} {desc}")
print("=" * 60)
print("RESULT:", "ALL CHECKS PASSED ✓" if all_ok else "ISSUES DETECTED ✗")
if not builder_blocks:
    print("\nACTION: Run with --repair to fix builder_blocks in DB:")
    print(f"  py -3.14 temp_analysis/db_repair_dca_rsi02.py --repair")
print()
