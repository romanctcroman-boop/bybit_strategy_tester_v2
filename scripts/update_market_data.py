#!/usr/bin/env python3
"""
Market Data Updater - обновление данных при запуске системы.

Проверяет все символы и интервалы в базе данных,
догружает недостающие данные до текущего момента.

Использование:
    python scripts/update_market_data.py [--verbose] [--dry-run]
"""

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_db_path() -> Path:
    """Get path to main database."""
    return PROJECT_ROOT / "data.sqlite3"


def get_all_symbols_intervals(conn: sqlite3.Connection) -> list:
    """Get all unique symbol/interval pairs from database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT symbol, interval
        FROM bybit_kline_audit
        ORDER BY symbol, interval
    """)
    return cursor.fetchall()


def get_newest_candle_time(
    conn: sqlite3.Connection, symbol: str, interval: str
) -> int | None:
    """Get timestamp of newest candle for symbol/interval."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT MAX(open_time) FROM bybit_kline_audit
        WHERE symbol = ? AND interval = ?
    """,
        (symbol, interval),
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] else None


def interval_to_ms(interval: str) -> int:
    """Convert interval string to milliseconds."""
    mapping = {
        "1": 60_000,
        "3": 180_000,
        "5": 300_000,
        "15": 900_000,
        "30": 1_800_000,
        "60": 3_600_000,
        "120": 7_200_000,
        "240": 14_400_000,
        "360": 21_600_000,
        "720": 43_200_000,
        "D": 86_400_000,
        "W": 604_800_000,
    }
    return mapping.get(interval, 3_600_000)


def fetch_candles_from_api(
    symbol: str, interval: str, start_ts: int, end_ts: int, max_retries: int = 3
) -> list:
    """Fetch candles from Bybit API using direct REST calls with retry logic."""
    import requests

    # Normalize interval for Bybit v5 API
    interval_norm = interval
    if interval.endswith("m") or interval.endswith("M"):
        interval_norm = interval[:-1]
    elif interval.endswith("h") or interval.endswith("H"):
        interval_norm = str(int(interval[:-1]) * 60)

    url = "https://api.bybit.com/v5/market/kline"
    all_candles = []
    current_start = start_ts

    while current_start < end_ts:
        params = {
            "category": "linear",
            "symbol": symbol.upper(),
            "interval": interval_norm,
            "start": current_start,
            "end": end_ts,
            "limit": 1000,
        }

        # Retry logic for transient network errors
        for attempt in range(max_retries):
            try:
                r = requests.get(url, params=params, timeout=15)
                r.raise_for_status()
                data = r.json()
                break
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    requests.exceptions.RequestException) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  [!] API error after {max_retries} retries: {e}")
                    return all_candles  # Return what we have so far
        else:
            break  # All retries failed

        result = data.get("result", {})
        candle_list = result.get("list", [])

        if not candle_list:
            break

        # Convert Bybit format to our format
        for c in candle_list:
            if len(c) >= 6:
                all_candles.append(
                    {
                        "open_time": int(c[0]),
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                        "volume": float(c[5]),
                    }
                )

        # Move to next batch (Bybit returns newest first, so use min)
        if candle_list:
            timestamps = [int(c[0]) for c in candle_list]
            min(timestamps)
            newest_ts = max(timestamps)
            # If we got the oldest data, move forward from newest
            current_start = newest_ts + interval_to_ms(interval)
        else:
            break

        # Rate limit protection
        time.sleep(0.1)

    return all_candles


def insert_candles(
    conn: sqlite3.Connection, symbol: str, interval: str, candles: list
) -> int:
    """Insert candles into database."""
    if not candles:
        return 0

    cursor = conn.cursor()
    inserted = 0

    for candle in candles:
        try:
            # Extract data from candle dict
            open_time = candle.get("open_time") or candle.get("timestamp")
            if not open_time:
                continue

            # Create raw JSON for the required column
            import json

            raw_json = json.dumps(candle)

            cursor.execute(
                """
                INSERT OR IGNORE INTO bybit_kline_audit
                (symbol, interval, open_time, open_price, high_price, low_price, close_price, volume, turnover, raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    symbol,
                    interval,
                    open_time,
                    candle.get("open") or candle.get("open_price"),
                    candle.get("high") or candle.get("high_price"),
                    candle.get("low") or candle.get("low_price"),
                    candle.get("close") or candle.get("close_price"),
                    candle.get("volume", 0),
                    candle.get("turnover", 0),
                    raw_json,
                ),
            )

            if cursor.rowcount > 0:
                inserted += 1

        except Exception as e:
            print(f"  ⚠️ Insert error: {e}")
            continue

    conn.commit()
    return inserted


def update_symbol_interval(
    conn: sqlite3.Connection,
    symbol: str,
    interval: str,
    verbose: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update data for a single symbol/interval pair."""
    result = {
        "symbol": symbol,
        "interval": interval,
        "status": "ok",
        "candles_added": 0,
        "gap_minutes": 0,
    }

    now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    newest_ts = get_newest_candle_time(conn, symbol, interval)

    if not newest_ts:
        result["status"] = "no_data"
        return result

    # Calculate gap
    gap_ms = now_ts - newest_ts
    gap_minutes = gap_ms / 60_000
    result["gap_minutes"] = round(gap_minutes, 1)

    # Check if update needed (more than 2 intervals behind)
    interval_ms = interval_to_ms(interval)
    if gap_ms < interval_ms * 2:
        result["status"] = "fresh"
        if verbose:
            print(f"  [OK] {symbol} {interval}: fresh data (lag {gap_minutes:.1f} min)")
        return result

    if verbose:
        print(f"  [..] {symbol} {interval}: lag {gap_minutes:.1f} min, loading...")

    if dry_run:
        result["status"] = "would_update"
        return result

    # Fetch and insert new candles
    start_ts = newest_ts + interval_ms
    candles = fetch_candles_from_api(symbol, interval, start_ts, now_ts)

    if candles:
        inserted = insert_candles(conn, symbol, interval, candles)
        result["candles_added"] = inserted
        result["status"] = "updated"
        if verbose:
            print(f"  [+] {symbol} {interval}: added {inserted} candles")
    else:
        result["status"] = "no_new_data"
        if verbose:
            print(f"  [i] {symbol} {interval}: no new data")

    return result


def main():
    parser = argparse.ArgumentParser(description="Update market data at startup")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Don't actually update, just show what would be done",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  Market Data Updater")
    print("=" * 50)

    db_path = get_db_path()
    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        sys.exit(1)

    print(f"[DB] {db_path}")

    # Use WAL mode for better concurrency and timeout for lock handling
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    # Get all symbol/interval pairs
    pairs = get_all_symbols_intervals(conn)
    print(f"[INFO] Found {len(pairs)} symbol/interval pairs")

    if args.dry_run:
        print("[DRY RUN] No actual updates will be made")

    print()

    # Update each pair
    results = {
        "total": len(pairs),
        "fresh": 0,
        "updated": 0,
        "no_data": 0,
        "errors": 0,
        "candles_added": 0,
    }

    start_time = time.time()

    for symbol, interval in pairs:
        result = update_symbol_interval(
            conn, symbol, interval, args.verbose, args.dry_run
        )

        if result["status"] == "fresh":
            results["fresh"] += 1
        elif result["status"] == "updated":
            results["updated"] += 1
            results["candles_added"] += result["candles_added"]
        elif result["status"] == "no_data":
            results["no_data"] += 1
        elif result["status"] == "would_update":
            results["updated"] += 1  # Count as would-be-updated for dry run
        else:
            results["errors"] += 1

    elapsed = time.time() - start_time

    conn.close()

    # Summary
    print()
    print("=" * 50)
    print("  Update Results")
    print("=" * 50)
    print(f"  Total pairs:      {results['total']}")
    print(f"  Fresh:            {results['fresh']}")
    print(f"  Updated:          {results['updated']}")
    print(f"  Candles added:    {results['candles_added']}")
    print(f"  No data:          {results['no_data']}")
    print(f"  Errors:           {results['errors']}")
    print(f"  Time:             {elapsed:.1f} sec")
    print("=" * 50)

    # Only fail if more than 50% errors (some pairs may not exist on Bybit)
    if results["errors"] > results["total"] // 2:
        sys.exit(1)


if __name__ == "__main__":
    main()
