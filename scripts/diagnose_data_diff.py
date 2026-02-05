"""
🔬 DIAGNOSTIC: Why DB data differs from TV data?
=================================================
Both claim to be from Bybit REST API.
"""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("data.sqlite3")
TV_SPOT = Path(r"d:\TV\BYBIT_BTCUSDT, 15 (2).csv")
TV_LINEAR = Path(r"d:\TV\BYBIT_BTCUSDT.P, 15 (2).csv")


def load_db():
    conn = sqlite3.connect(DB_PATH)

    # Check all unique combinations
    print("="*60)
    print("📊 DATABASE SCHEMA CHECK")
    print("="*60)

    cur = conn.execute("""
        SELECT symbol, interval, market_type, COUNT(*) as cnt,
               MIN(datetime(open_time/1000, 'unixepoch')) as min_dt,
               MAX(datetime(open_time/1000, 'unixepoch')) as max_dt
        FROM bybit_kline_audit 
        GROUP BY symbol, interval, market_type
        ORDER BY symbol, interval, market_type
    """)

    print(f"\n{'Symbol':<15} | {'Interval':<8} | {'Market':<8} | {'Count':>8} | {'From':>20} | {'To':>20}")
    print("-"*95)
    for row in cur.fetchall():
        print(f"{row[0]:<15} | {row[1]:<8} | {row[2]:<8} | {row[3]:>8} | {row[4]:>20} | {row[5]:>20}")

    # Load SPOT and LINEAR samples
    spot_df = pd.read_sql_query("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='spot'
        ORDER BY open_time ASC
        LIMIT 10
    """, conn)

    linear_df = pd.read_sql_query("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear'
        ORDER BY open_time ASC
        LIMIT 10
    """, conn)

    conn.close()

    spot_df['datetime'] = pd.to_datetime(spot_df['open_time'], unit='ms')
    linear_df['datetime'] = pd.to_datetime(linear_df['open_time'], unit='ms')

    return spot_df, linear_df


def load_tv(csv_path):
    df = pd.read_csv(csv_path)
    df.columns = ['datetime', 'open', 'high', 'low', 'close']
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df


def compare_timestamps(db_df, tv_df, name):
    """Compare timestamps and find alignment issues"""
    print(f"\n{'='*60}")
    print(f"🕐 TIMESTAMP ANALYSIS: {name}")
    print("="*60)

    # Get first few timestamps
    print("\nFirst 5 DB timestamps:")
    for i, row in db_df.head().iterrows():
        print(f"  {row['datetime']} | Open: ${row['open_price']:.2f}")

    print("\nFirst 5 TV timestamps:")
    tv_df['datetime'] = tv_df['datetime'].dt.tz_localize(None) if tv_df['datetime'].dt.tz else tv_df['datetime']
    for i, row in tv_df.head().iterrows():
        print(f"  {row['datetime']} | Open: ${row['open']:.2f}")

    # Check timezone offset
    print("\n🕐 TIMEZONE CHECK:")
    db_first = db_df['datetime'].iloc[0]
    tv_first = tv_df['datetime'].iloc[0]

    # Try to find matching price in TV with different offsets
    db_price = db_df['open_price'].iloc[0]

    print(f"\nDB first bar: {db_first} @ ${db_price:.2f}")
    print(f"TV first bar: {tv_first} @ ${tv_df['open'].iloc[0]:.2f}")

    # Search for matching price in TV
    print(f"\n🔍 Searching for DB price ${db_price:.2f} in TV data...")
    for i, row in tv_df.iterrows():
        if abs(row['open'] - db_price) < 1:
            offset = (row['datetime'] - db_first).total_seconds() / 3600
            print(f"  FOUND! TV row {i}: {row['datetime']} @ ${row['open']:.2f}")
            print(f"  Time offset: {offset:.1f} hours")
            break
    else:
        # Search with tolerance
        matches = tv_df[abs(tv_df['open'] - db_price) < 100]
        if len(matches) > 0:
            print("  Closest matches (within $100):")
            for i, row in matches.head(3).iterrows():
                offset = (row['datetime'] - db_first).total_seconds() / 3600
                print(f"    {row['datetime']} @ ${row['open']:.2f} (Δ${abs(row['open']-db_price):.2f}, offset: {offset:.1f}h)")


def check_data_source():
    """Check how data was loaded"""
    print("\n" + "="*60)
    print("📝 DATA SOURCE CHECK")
    print("="*60)

    # Check if there's any audit/log info
    conn = sqlite3.connect(DB_PATH)

    # Check table structure
    cur = conn.execute("PRAGMA table_info(bybit_kline_audit)")
    columns = cur.fetchall()
    print("\nTable columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")

    # Sample data with all columns
    print("\nSample row (all columns):")
    cur = conn.execute("""
        SELECT * FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' 
        LIMIT 1
    """)
    row = cur.fetchone()
    col_names = [desc[0] for desc in cur.description]
    for name, val in zip(col_names, row):
        print(f"  {name}: {val}")

    conn.close()


def compare_same_timestamp(db_spot, db_linear, tv_spot, tv_linear):
    """Find same timestamp in all 4 sources and compare"""
    print("\n" + "="*60)
    print("🔍 SAME TIMESTAMP COMPARISON")
    print("="*60)

    # Find a common timestamp that exists in all
    # Use a specific date that should exist in all
    target_dt = pd.Timestamp('2025-10-15 12:00:00')

    # Adjust for timezones
    tv_spot['datetime'] = tv_spot['datetime'].dt.tz_localize(None) if tv_spot['datetime'].dt.tz else tv_spot['datetime']
    tv_linear['datetime'] = tv_linear['datetime'].dt.tz_localize(None) if tv_linear['datetime'].dt.tz else tv_linear['datetime']

    print(f"\nLooking for data around: {target_dt}")

    # Load more data from DB
    conn = sqlite3.connect(DB_PATH)

    db_spot_full = pd.read_sql_query("""
        SELECT open_time, open_price FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='spot'
        AND open_time BETWEEN 1728993600000 AND 1729000800000
        ORDER BY open_time
    """, conn)

    db_linear_full = pd.read_sql_query("""
        SELECT open_time, open_price FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear'
        AND open_time BETWEEN 1728993600000 AND 1729000800000
        ORDER BY open_time
    """, conn)

    conn.close()

    if len(db_spot_full) > 0:
        db_spot_full['datetime'] = pd.to_datetime(db_spot_full['open_time'], unit='ms')
        print("\nDB SPOT around Oct 15:")
        for _, row in db_spot_full.head(5).iterrows():
            print(f"  {row['datetime']} | ${row['open_price']:.2f}")

    # TV data around same date
    tv_oct15_spot = tv_spot[(tv_spot['datetime'] >= '2025-10-15 10:00') &
                           (tv_spot['datetime'] <= '2025-10-15 14:00')]
    if len(tv_oct15_spot) > 0:
        print("\nTV SPOT around Oct 15:")
        for _, row in tv_oct15_spot.head(5).iterrows():
            print(f"  {row['datetime']} | ${row['open']:.2f}")

    # Check if DB and TV have same timestamps but different prices
    # or different timestamps (timezone issue)


def main():
    # Load DB data
    db_spot, db_linear = load_db()

    # Load TV data
    tv_spot = load_tv(TV_SPOT)
    tv_linear = load_tv(TV_LINEAR)

    print(f"\nTV SPOT loaded: {len(tv_spot)} bars")
    print(f"TV LINEAR loaded: {len(tv_linear)} bars")

    # Check data source
    check_data_source()

    # Compare timestamps
    compare_timestamps(db_spot, tv_spot, "SPOT")
    compare_timestamps(db_linear, tv_linear, "LINEAR")

    # Compare same timestamp across all sources
    compare_same_timestamp(db_spot, db_linear, tv_spot, tv_linear)

    print("\n" + "="*60)
    print("💡 HYPOTHESIS")
    print("="*60)
    print("""
Possible reasons for data difference:
1. TIMEZONE OFFSET: DB might be UTC, TV might be MSK (UTC+3)
2. DIFFERENT SYMBOL: Maybe DB has BTCUSD and TV has BTCUSDT?
3. DIFFERENT MARKET: Maybe DB has futures data labeled as spot?
4. API VERSION: Bybit V3 vs V5 API might return different data
5. TIMESTAMP ALIGNMENT: First bar of 15m candle might differ
""")


if __name__ == "__main__":
    main()
