"""
🔬 Compare RAW OHLC Data: DB vs TV CSV Files
=============================================
Check if our database OHLC matches TradingView exports.
"""
import sqlite3
from datetime import timedelta
from pathlib import Path

import pandas as pd

DB_PATH = Path("data.sqlite3")

# TV CSV export files
TV_SPOT_OHLC = Path(r"d:\TV\BYBIT_BTCUSDT, 15 (2).csv")
TV_LINEAR_OHLC = Path(r"d:\TV\BYBIT_BTCUSDT.P, 15 (2).csv")


def load_db_data(market_type):
    """Load OHLC from database"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"""
        SELECT open_time, open_price, high_price, low_price, close_price
        FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='{market_type}'
        ORDER BY open_time ASC
    """, conn)
    conn.close()

    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
    return df


def load_tv_ohlc(csv_path):
    """Load OHLC from TradingView exported CSV"""
    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        return None

    df = pd.read_csv(csv_path)
    print(f"TV CSV columns: {df.columns.tolist()}")

    # TradingView export format varies, try to detect columns
    # Common formats: time, open, high, low, close

    # Rename columns to standard names
    col_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if 'time' in col_lower or 'дата' in col_lower or 'date' in col_lower:
            col_map[col] = 'datetime'
        elif 'open' in col_lower or 'откр' in col_lower:
            col_map[col] = 'open'
        elif 'high' in col_lower or 'макс' in col_lower:
            col_map[col] = 'high'
        elif 'low' in col_lower or 'мин' in col_lower:
            col_map[col] = 'low'
        elif 'close' in col_lower or 'закр' in col_lower:
            col_map[col] = 'close'

    df = df.rename(columns=col_map)

    # Parse datetime
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        # Convert MSK to UTC if needed
        if df['datetime'].iloc[0].hour > 12:  # Likely MSK
            df['datetime'] = df['datetime'] - timedelta(hours=3)

    return df


def compare_ohlc(db_df, tv_df, market_name):
    """Compare OHLC data"""
    print(f"\n{'='*80}")
    print(f"📊 {market_name} OHLC COMPARISON: DB vs TV CSV")
    print("="*80)

    if tv_df is None:
        print("❌ TV data not available")
        return

    print(f"\nDB data:  {len(db_df)} bars ({db_df['datetime'].min()} to {db_df['datetime'].max()})")
    print(f"TV data:  {len(tv_df)} bars ({tv_df['datetime'].min()} to {tv_df['datetime'].max()})")

    # Make both timezone-naive for comparison
    if db_df['datetime'].dt.tz is not None:
        db_df['datetime'] = db_df['datetime'].dt.tz_localize(None)
    if tv_df['datetime'].dt.tz is not None:
        tv_df['datetime'] = tv_df['datetime'].dt.tz_localize(None)

    # Find overlapping period
    db_min = db_df['datetime'].min()
    db_max = db_df['datetime'].max()
    tv_min = tv_df['datetime'].min()
    tv_max = tv_df['datetime'].max()

    overlap_start = max(db_min, tv_min)
    overlap_end = min(db_max, tv_max)

    print(f"\nOverlap:  {overlap_start} to {overlap_end}")

    # Filter to overlap
    db_overlap = db_df[(db_df['datetime'] >= overlap_start) & (db_df['datetime'] <= overlap_end)].copy()
    tv_overlap = tv_df[(tv_df['datetime'] >= overlap_start) & (tv_df['datetime'] <= overlap_end)].copy()

    print(f"DB bars in overlap: {len(db_overlap)}")
    print(f"TV bars in overlap: {len(tv_overlap)}")

    # Merge on datetime
    db_overlap = db_overlap.set_index('datetime')
    tv_overlap = tv_overlap.set_index('datetime')

    merged = db_overlap.join(tv_overlap, lsuffix='_db', rsuffix='_tv', how='inner')
    print(f"Matched bars:       {len(merged)}")

    if len(merged) == 0:
        print("❌ No matching bars found!")
        return

    # Compare prices
    print(f"\n{'='*60}")
    print("📋 PRICE COMPARISON (first 10 matching bars)")
    print("="*60)

    if 'open_price' in merged.columns and 'open' in merged.columns:
        db_open_col = 'open_price'
        tv_open_col = 'open'
    elif 'open_db' in merged.columns and 'open_tv' in merged.columns:
        db_open_col = 'open_db'
        tv_open_col = 'open_tv'
    else:
        print(f"Columns: {merged.columns.tolist()}")
        return

    print(f"\n{'Datetime':>20} | {'DB Open':>12} | {'TV Open':>12} | {'Diff':>10}")
    print("-"*65)

    exact_matches = 0
    close_matches = 0

    for i, (dt, row) in enumerate(merged.head(10).iterrows()):
        db_open = row.get(db_open_col, row.get('open_price', 0))
        tv_open = row.get(tv_open_col, row.get('open', 0))

        diff = abs(db_open - tv_open)

        if diff < 0.01:
            match_str = "✅"
            exact_matches += 1
        elif diff < 1:
            match_str = f"⚠️ Δ${diff:.2f}"
            close_matches += 1
        else:
            match_str = f"❌ Δ${diff:.2f}"

        print(f"{dt!s:>20} | ${db_open:>10.2f} | ${tv_open:>10.2f} | {match_str}")

    # Calculate overall match rate
    if db_open_col in merged.columns and tv_open_col in merged.columns:
        merged['diff'] = abs(merged[db_open_col] - merged[tv_open_col])
        exact = (merged['diff'] < 0.01).sum()
        close = (merged['diff'] < 1).sum()

        print("\n📊 OVERALL MATCH RATE:")
        print(f"   Exact matches (<$0.01): {exact}/{len(merged)} ({exact/len(merged)*100:.1f}%)")
        print(f"   Close matches (<$1):    {close}/{len(merged)} ({close/len(merged)*100:.1f}%)")

        if exact / len(merged) < 0.9:
            # Find biggest differences
            print("\n🔍 BIGGEST DIFFERENCES:")
            top_diff = merged.nlargest(5, 'diff')
            for dt, row in top_diff.iterrows():
                print(f"   {dt}: DB=${row[db_open_col]:.2f} vs TV=${row[tv_open_col]:.2f} (Δ${row['diff']:.2f})")


def main():
    print("="*80)
    print("🔬 RAW OHLC DATA COMPARISON: DB vs TV CSV")
    print("="*80)

    # ========== SPOT ==========
    print("\n" + "="*80)
    print("📈 SPOT MARKET")
    print("="*80)

    db_spot = load_db_data('spot')
    print(f"Loaded {len(db_spot)} SPOT bars from DB")

    tv_spot = load_tv_ohlc(TV_SPOT_OHLC)
    if tv_spot is not None:
        print(f"Loaded {len(tv_spot)} bars from TV SPOT CSV")
        compare_ohlc(db_spot, tv_spot, "SPOT")

    # ========== LINEAR ==========
    print("\n" + "="*80)
    print("📈 LINEAR MARKET")
    print("="*80)

    db_linear = load_db_data('linear')
    print(f"Loaded {len(db_linear)} LINEAR bars from DB")

    tv_linear = load_tv_ohlc(TV_LINEAR_OHLC)
    if tv_linear is not None:
        print(f"Loaded {len(tv_linear)} bars from TV LINEAR CSV")
        compare_ohlc(db_linear, tv_linear, "LINEAR")


if __name__ == "__main__":
    main()
