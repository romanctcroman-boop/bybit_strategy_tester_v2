"""
🔍 Investigate Trade #24 - Deep RSI Analysis
=============================================
Find why Trade #24 (LONG at 14:00 UTC, Bar ~2840) was skipped.

Created: January 21, 2026
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3

import pandas as pd

# Database path
DB_PATH = project_root / "data.sqlite3"


def calculate_rsi_wilder(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate RSI using Wilder's Smoothing (RMA) - exact TradingView method.
    """
    delta = prices.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # First avg: simple average
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Wilder's smoothing for subsequent values
    for i in range(period, len(prices)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def load_spot_data():
    """Load SPOT data from database."""
    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT 
        open_time,
        open_price,
        high_price,
        low_price,
        close_price,
        volume
    FROM bybit_kline_audit 
    WHERE symbol = 'BTCUSDT' 
      AND interval = '15'
      AND market_type = 'spot'
    ORDER BY open_time ASC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("❌ No SPOT data found! Trying without market_type filter...")
        conn = sqlite3.connect(DB_PATH)
        query = """
        SELECT 
            open_time,
            open_price,
            high_price,
            low_price,
            close_price,
            volume
        FROM bybit_kline_audit 
        WHERE symbol = 'BTCUSDT' 
          AND interval = '15'
        ORDER BY open_time ASC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

    # Convert timestamp
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)

    return df


def find_trade_24_region(df: pd.DataFrame, oversold: int = 30):
    """
    Find the region around Trade #24 based on knowledge base info:
    - Trade #24 is LONG at 14:00 UTC
    - Bar ~2840
    - Should be around late October/early November 2025 based on 84 trades over ~4 months
    """
    print("\n" + "="*70)
    print("🔍 INVESTIGATING TRADE #24")
    print("="*70)

    # Calculate RSI
    df['rsi'] = calculate_rsi_wilder(df['close_price'], period=14)

    # Find crossover signals
    df['prev_rsi'] = df['rsi'].shift(1)

    # Long signal: RSI crosses ABOVE oversold (prev <= 30, curr > 30)
    df['long_signal'] = (df['prev_rsi'] <= oversold) & (df['rsi'] > oversold)

    # Short signal: RSI crosses BELOW overbought (prev >= 70, curr < 70)
    df['short_signal'] = (df['prev_rsi'] >= 70) & (df['rsi'] < 70)

    # Count signals
    long_signals = df[df['long_signal']].copy()
    short_signals = df[df['short_signal']].copy()

    print(f"\n📊 Total bars in dataset: {len(df)}")
    print(f"📈 Total LONG signals: {len(long_signals)}")
    print(f"📉 Total SHORT signals: {len(short_signals)}")

    # Look for bars around index 2840 (approximate)
    print("\n" + "-"*70)
    print("📍 Looking at bars around index 2840...")
    print("-"*70)

    if len(df) > 2850:
        region = df.iloc[2830:2850].copy()
        print("\nBars 2830-2850:")
        for _, row in region.iterrows():
            signal = ""
            if row['long_signal']:
                signal = "🟢 LONG SIGNAL"
            elif row['short_signal']:
                signal = "🔴 SHORT SIGNAL"

            print(f"  Bar {row.name}: {row['datetime']} | RSI: {row['rsi']:.3f} | prev: {row['prev_rsi']:.3f} {signal}")

    # Find all LONG signals and show around #24
    print("\n" + "-"*70)
    print("📍 All LONG signals (showing #20-30):")
    print("-"*70)

    long_signals = long_signals.reset_index()
    if len(long_signals) >= 30:
        for i in range(19, min(30, len(long_signals))):
            idx = long_signals.iloc[i]['index']
            dt = long_signals.iloc[i]['datetime']
            rsi = long_signals.iloc[i]['rsi']
            prev_rsi = long_signals.iloc[i]['prev_rsi']

            marker = " ⭐ TRADE #24?" if i == 23 else ""  # 0-indexed, so #24 is index 23

            print(f"  Signal #{i+1}: Bar {idx} | {dt} | RSI: {prev_rsi:.4f} → {rsi:.4f}{marker}")

    # Analyze the boundary case
    print("\n" + "-"*70)
    print("🔬 BOUNDARY ANALYSIS (where RSI ≈ 30)")
    print("-"*70)

    # Find bars where RSI is very close to 30
    boundary_mask = (df['rsi'] >= 29.9) & (df['rsi'] <= 30.1)
    boundary_bars = df[boundary_mask].copy()

    print(f"\nBars with RSI between 29.9 and 30.1: {len(boundary_bars)}")

    if len(boundary_bars) > 0:
        print("\nFirst 20 boundary cases:")
        for _, row in boundary_bars.head(20).iterrows():
            signal_status = ""

            # Check if this would be a signal
            if row['prev_rsi'] <= 30 and row['rsi'] > 30:
                signal_status = "✅ LONG triggered"
            elif row['prev_rsi'] <= 30 and row['rsi'] <= 30:
                signal_status = "❌ Still below 30"
            elif row['prev_rsi'] > 30 and row['rsi'] > 30:
                signal_status = "❌ Already above (no crossover)"
            elif row['prev_rsi'] > 30 and row['rsi'] <= 30:
                signal_status = "⬇️ Crossing down"

            print(f"  Bar {row.name}: RSI {row['prev_rsi']:.4f} → {row['rsi']:.4f} | {signal_status}")

    # Find the exact Trade #24 candidate
    print("\n" + "="*70)
    print("🎯 FINDING TRADE #24 EXACT LOCATION")
    print("="*70)

    # Trade #24 should be a LONG signal
    # Based on docs: "14:00 UTC, Bar 2840"

    # Find signals with RSI closest to exactly 30.0 (boundary)
    if len(long_signals) >= 24:
        trade_24_candidate = long_signals.iloc[23]  # 0-indexed
        bar_idx = trade_24_candidate['index']

        print(f"\n📍 Trade #24 Candidate (Signal #{24}):")
        print(f"   Bar Index: {bar_idx}")
        print(f"   Datetime:  {trade_24_candidate['datetime']}")
        print(f"   RSI:       {trade_24_candidate['prev_rsi']:.6f} → {trade_24_candidate['rsi']:.6f}")
        print(f"   Close:     {df.loc[bar_idx, 'close_price']}")

        # Check the exact difference
        diff_from_30 = abs(trade_24_candidate['prev_rsi'] - 30.0)
        print(f"\n🔬 Distance from exactly 30.0: {diff_from_30:.8f}")

        if diff_from_30 < 0.01:
            print("   ⚠️ VERY CLOSE TO BOUNDARY - floating point sensitivity possible!")

        # Show surrounding bars
        print("\n📊 Surrounding bars (±5):")
        start = max(0, bar_idx - 5)
        end = min(len(df), bar_idx + 6)

        for i in range(start, end):
            row = df.iloc[i]
            marker = " 👈 TRADE #24" if i == bar_idx else ""
            signal = ""
            if row['long_signal']:
                signal = "🟢"
            elif row['short_signal']:
                signal = "🔴"

            print(f"  [{i}] {row['datetime']} | Close: {row['close_price']:.2f} | RSI: {row['rsi']:.4f}{signal}{marker}")

    return df


def compare_with_tradingview():
    """
    Try to load TradingView CSV and compare RSI values.
    """
    tv_files = list(Path(r"d:\TV").glob("*.csv"))

    if not tv_files:
        print("\n⚠️ No TradingView CSV files found in d:\\TV")
        return

    print("\n" + "="*70)
    print("📊 COMPARING WITH TRADINGVIEW DATA")
    print("="*70)

    for tv_file in tv_files:
        print(f"\n📁 Found: {tv_file.name}")


if __name__ == "__main__":
    print("="*70)
    print("🔍 TRADE #24 INVESTIGATION SCRIPT")
    print("="*70)
    print(f"Database: {DB_PATH}")
    print(f"Exists: {DB_PATH.exists()}")

    if not DB_PATH.exists():
        # Try alternative path
        DB_PATH_ALT = project_root / "bybit_klines_15m.db"
        if DB_PATH_ALT.exists():
            print(f"Using alternative DB: {DB_PATH_ALT}")
            DB_PATH = DB_PATH_ALT

    df = load_spot_data()

    if df.empty:
        print("❌ No data loaded!")
        sys.exit(1)

    print(f"\n✅ Loaded {len(df)} bars")
    print(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")

    # Investigate
    df = find_trade_24_region(df)

    # Try to compare with TV
    compare_with_tradingview()

    print("\n" + "="*70)
    print("🏁 INVESTIGATION COMPLETE")
    print("="*70)
