"""
🔧 RELOAD SPOT DATA
===================
Clears existing SPOT data for BTCUSDT and reloads from Bybit API
with correct market_type='spot'.
"""
import asyncio
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

DB_PATH = project_root / "data.sqlite3"

# Date range (SPOT data starts from Oct 2025 based on TV)
DATA_START_TS = int(datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
NOW_TS = int(datetime.now(timezone.utc).timestamp() * 1000)


async def reload_spot_data():
    """Reload SPOT data from Bybit with correct market_type."""
    from backend.services.adapters.bybit import BybitAdapter
    
    adapter = BybitAdapter()
    
    symbol = "BTCUSDT"
    interval = "15"
    market_type = "spot"
    
    print("="*70)
    print(f"🔄 RELOADING {symbol} {interval}m {market_type.upper()} DATA")
    print("="*70)
    
    # Step 1: Check current state
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("""
        SELECT COUNT(*) FROM bybit_kline_audit 
        WHERE symbol=? AND interval=? AND market_type=?
    """, (symbol, interval, market_type))
    current_count = cur.fetchone()[0]
    conn.close()
    
    print(f"\n📊 Current {market_type.upper()} records: {current_count}")
    
    # Step 2: Delete existing SPOT data
    print(f"\n🗑️ Deleting existing {market_type} data...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        DELETE FROM bybit_kline_audit 
        WHERE symbol=? AND interval=? AND market_type=?
    """, (symbol, interval, market_type))
    conn.commit()
    deleted = conn.total_changes
    conn.close()
    print(f"   Deleted {deleted} records")
    
    # Step 3: Fetch fresh data from Bybit with correct market_type
    print(f"\n📡 Fetching fresh {market_type} data from Bybit API...")
    print(f"   Range: {datetime.fromtimestamp(DATA_START_TS/1000)} to {datetime.fromtimestamp(NOW_TS/1000)}")
    
    try:
        candles = await adapter.get_historical_klines(
            symbol=symbol,
            interval=interval,
            start_time=DATA_START_TS,
            end_time=NOW_TS,
            limit=1000,
            market_type=market_type,
        )
        
        print(f"   Fetched {len(candles)} candles")
        
        if candles:
            # Add interval to rows
            rows_with_interval = [{**r, "interval": interval} for r in candles]
            
            # Persist with correct market_type
            print(f"\n💾 Persisting to database with market_type={market_type}...")
            adapter._persist_klines_to_db(symbol, rows_with_interval, market_type=market_type)
            print(f"   Saved {len(rows_with_interval)} candles")
            
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        raise
    
    # Step 4: Verify
    print("\n✅ Verifying...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("""
        SELECT COUNT(*), MIN(datetime(open_time/1000, 'unixepoch')), MAX(datetime(open_time/1000, 'unixepoch'))
        FROM bybit_kline_audit 
        WHERE symbol=? AND interval=? AND market_type=?
    """, (symbol, interval, market_type))
    count, min_dt, max_dt = cur.fetchone()
    
    # Get sample prices
    cur = conn.execute("""
        SELECT datetime(open_time/1000, 'unixepoch'), open_price
        FROM bybit_kline_audit 
        WHERE symbol=? AND interval=? AND market_type=?
        ORDER BY open_time LIMIT 5
    """, (symbol, interval, market_type))
    samples = cur.fetchall()
    conn.close()
    
    print(f"\n📊 New {market_type.upper()} stats:")
    print(f"   Count: {count}")
    print(f"   Range: {min_dt} to {max_dt}")
    print(f"\n   Sample prices:")
    for dt, price in samples:
        print(f"   {dt} | ${price:.2f}")
    
    print("\n" + "="*70)
    print("✅ SPOT DATA RELOAD COMPLETE")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(reload_spot_data())
