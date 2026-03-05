"""
Inspect why our entry/exit points differ from TradingView.
Focus: signal timing - at what bar does MACD generate a signal?
"""

import json
import sqlite3
import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

# ── Load strategy config ──────────────────────────────────────────────────────
conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
cur = conn.cursor()
cur.execute("""
    SELECT id, name, strategy_config
    FROM strategies
    WHERE name LIKE '%MACD%' AND is_deleted=0
    ORDER BY created_at DESC LIMIT 5
""")
rows = cur.fetchall()

print("=== MACD Strategies ===")
strategy_id = None
strategy_cfg = None
for r in rows:
    cfg = json.loads(r[2]) if r[2] else {}
    print(f"\nID: {r[0]}")
    print(f"Name: {r[1]}")
    if "blocks" in cfg:
        for b in cfg["blocks"]:
            print(f"  Block type: {b.get('type', '?')}")
            print(f"  Config: {json.dumps(b.get('config', {}), ensure_ascii=False, indent=4)}")
    if strategy_id is None:
        strategy_id = r[0]
        strategy_cfg = cfg

print("\n\n=== Checking signal generation mode ===")
print("Key question: does the strategy use 'signal on close' or 'signal on next bar open'?")

# ── Load some ETHUSDT 30m candles around the known trade dates ────────────────
print("\n=== Loading ETHUSDT 30m candles around March 4, 2026 ===")

# Check what table has the klines
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%kline%' OR name LIKE '%candle%'")
tables = cur.fetchall()
print(f"Tables: {[t[0] for t in tables]}")

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
all_tables = [t[0] for t in cur.fetchall()]
kline_tables = [t for t in all_tables if "kline" in t.lower() or "candle" in t.lower() or "ohlcv" in t.lower()]
print(f"Kline-like tables: {kline_tables}")

conn.close()
