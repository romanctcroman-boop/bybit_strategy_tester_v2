"""
Fetch pre-2025 warmup candles for ETHUSDT and BTCUSDT 30m from Bybit API.
Stores them into bybit_kline_audit table (will be marked with a flag or just inserted).

We need ~30 bars before 2025-01-01 00:00 UTC for RSI(14) warmup.
We'll fetch 2024-12-15 to 2024-12-31 (safer: 2 weeks = 672 bars).
"""

import json
import sqlite3
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Config ────────────────────────────────────────────────────────────────────
WARMUP_START = datetime(2024, 12, 1, tzinfo=UTC)  # fetch from here
WARMUP_END = datetime(2025, 1, 1, tzinfo=UTC)  # up to (exclusive)

SYMBOLS = ["ETHUSDT", "BTCUSDT"]
INTERVAL = "30"
CATEGORY = "linear"
BYBIT_URL = "https://api.bybit.com/v5/market/kline"


def ts_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> list[dict]:
    """Fetch klines from Bybit v5 API with pagination (descending → reverse)."""
    all_rows = []
    current_end = end_ms
    iteration = 0

    while True:
        iteration += 1
        params = {
            "category": CATEGORY,
            "symbol": symbol,
            "interval": interval,
            "limit": 1000,
            "start": start_ms,
            "end": current_end,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{BYBIT_URL}?{query}"

        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"  HTTP error: {e}")
            time.sleep(2)
            continue

        if data.get("retCode") != 0:
            print(f"  API error: {data.get('retMsg')}")
            break

        klines = data["result"]["list"]  # [[ts, open, high, low, close, vol, turnover], ...]
        if not klines:
            break

        # Each row: [timestamp_ms_str, open, high, low, close, volume, turnover]
        for k in klines:
            ts = int(k[0])
            if ts < start_ms or ts >= end_ms:
                continue
            all_rows.append(
                {
                    "open_time": ts,
                    "open_price": float(k[1]),
                    "high_price": float(k[2]),
                    "low_price": float(k[3]),
                    "close_price": float(k[4]),
                    "volume": float(k[5]),
                    "turnover": float(k[6]) if len(k) > 6 else 0.0,
                }
            )

        # Bybit returns newest first — oldest row is last
        oldest_ts = int(klines[-1][0])
        if oldest_ts <= start_ms:
            break  # We've covered the full range

        # Next page: end = oldest_ts - 1 bar (30m = 30*60*1000 ms)
        current_end = oldest_ts - 1
        if current_end < start_ms:
            break

        time.sleep(0.1)  # rate limit courtesy

        if iteration > 100:
            print("  Too many iterations, stopping")
            break

    # Deduplicate and sort ascending
    seen = set()
    unique = []
    for r in all_rows:
        if r["open_time"] not in seen:
            seen.add(r["open_time"])
            unique.append(r)
    unique.sort(key=lambda x: x["open_time"])
    return unique


def insert_warmup_candles(conn: sqlite3.Connection, symbol: str, rows: list[dict]):
    """Insert warmup candles into bybit_kline_audit. Skip if already exists."""
    inserted = 0
    skipped = 0
    for r in rows:
        open_time_ms = r["open_time"]
        open_time_dt = datetime.fromtimestamp(open_time_ms / 1000, tz=UTC).isoformat()

        # Check if exists
        cur = conn.execute(
            "SELECT 1 FROM bybit_kline_audit WHERE symbol=? AND interval=? AND market_type=? AND open_time=?",
            (symbol, INTERVAL, CATEGORY, open_time_ms),
        )
        if cur.fetchone():
            skipped += 1
            continue

        conn.execute(
            "INSERT INTO bybit_kline_audit "
            "(symbol, interval, market_type, open_time, open_time_dt, open_price, high_price, low_price, close_price, volume, turnover, raw, inserted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                symbol,
                INTERVAL,
                CATEGORY,
                open_time_ms,
                open_time_dt,
                r["open_price"],
                r["high_price"],
                r["low_price"],
                r["close_price"],
                r["volume"],
                r["turnover"],
                json.dumps(r),
                datetime.now(UTC).isoformat(),
            ),
        )
        inserted += 1

    conn.commit()
    return inserted, skipped


# ── Main ──────────────────────────────────────────────────────────────────────
start_ms = ts_ms(WARMUP_START)
end_ms = ts_ms(WARMUP_END)

print(f"Fetching warmup candles: {WARMUP_START.date()} → {WARMUP_END.date()}")
print(f"Interval: {INTERVAL}m, Symbols: {SYMBOLS}")
print()

conn = sqlite3.connect("data.sqlite3")

for symbol in SYMBOLS:
    print(f"[{symbol}] Fetching from Bybit API...", end=" ", flush=True)
    rows = fetch_klines(symbol, INTERVAL, start_ms, end_ms)
    print(f"got {len(rows)} candles")

    if not rows:
        print(f"  WARNING: No data returned for {symbol}!")
        continue

    first_dt = datetime.fromtimestamp(rows[0]["open_time"] / 1000, tz=UTC)
    last_dt = datetime.fromtimestamp(rows[-1]["open_time"] / 1000, tz=UTC)
    print(f"  Range: {first_dt} → {last_dt}")

    ins, skip = insert_warmup_candles(conn, symbol, rows)
    print(f"  Inserted: {ins}, Skipped (already exists): {skip}")
    print()

conn.close()

# Verify
print("Verification:")
conn2 = sqlite3.connect("data.sqlite3")
for symbol in SYMBOLS:
    cur = conn2.execute(
        "SELECT MIN(open_time_dt), MAX(open_time_dt), COUNT(*) "
        "FROM bybit_kline_audit WHERE symbol=? AND interval=? AND market_type=?",
        (symbol, INTERVAL, CATEGORY),
    )
    r = cur.fetchone()
    print(f"  {symbol} {INTERVAL}m: {r[0]} → {r[1]}, total={r[2]}")
conn2.close()

print()
print("Done! Now re-run calibrate_engines.py with WARMUP_START = 2024-12-01")
