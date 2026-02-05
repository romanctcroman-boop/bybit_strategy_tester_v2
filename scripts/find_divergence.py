"""
🔍 Find First Divergence Point between TradingView and Our Engine
==================================================================
Compare trade sequences to find where they start diverging.
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
from datetime import timedelta

import pandas as pd

DB_PATH = project_root / "data.sqlite3"
TV_CSV = Path(r"d:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT_2026-01-21 (1).csv")


def calculate_rsi_wilder(prices: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    for i in range(period, len(prices)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def load_our_signals() -> pd.DataFrame:
    """Load our LONG/SHORT signals from database."""
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT open_time, open_price, high_price, low_price, close_price
    FROM bybit_kline_audit 
    WHERE symbol = 'BTCUSDT' AND interval = '15' AND market_type = 'spot'
    ORDER BY open_time ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)

    # Calculate RSI
    df['rsi'] = calculate_rsi_wilder(df['close_price'], 14)
    df['prev_rsi'] = df['rsi'].shift(1)

    # Signals
    OVERSOLD = 30
    OVERBOUGHT = 70
    df['long_signal'] = (df['prev_rsi'] <= OVERSOLD) & (df['rsi'] > OVERSOLD)
    df['short_signal'] = (df['prev_rsi'] >= OVERBOUGHT) & (df['rsi'] < OVERBOUGHT)

    # Extract signals
    signals = []
    for i, row in df.iterrows():
        if row['long_signal']:
            signals.append({
                'datetime': row['datetime'],
                'direction': 'LONG',
                'price': row['close_price'],
                'rsi': row['rsi'],
                'bar_idx': i
            })
        elif row['short_signal']:
            signals.append({
                'datetime': row['datetime'],
                'direction': 'SHORT',
                'price': row['close_price'],
                'rsi': row['rsi'],
                'bar_idx': i
            })

    return pd.DataFrame(signals)


def load_tv_trades() -> pd.DataFrame:
    """Load TradingView trade entries."""
    df = pd.read_csv(TV_CSV)

    # Filter entries only
    entries = df[df['Type'].str.contains('Entry', na=False)].copy()
    entries = entries.reset_index(drop=True)

    # Parse
    entries['datetime'] = pd.to_datetime(entries['Date and time'])
    entries['direction'] = entries['Type'].apply(
        lambda x: 'LONG' if 'long' in x.lower() else 'SHORT'
    )
    entries['price'] = entries['Price USDT']

    return entries[['datetime', 'direction', 'price']].copy()


def find_divergence():
    """Compare sequences to find first divergence."""
    print("="*80)
    print("🔍 FINDING FIRST DIVERGENCE POINT")
    print("="*80)

    # Load data
    our_signals = load_our_signals()
    tv_trades = load_tv_trades()

    print(f"\n📊 Our signals: {len(our_signals)}")
    print(f"📊 TV trades:   {len(tv_trades)}")

    # Adjust TV times (MSK to UTC: subtract 3 hours)
    tv_trades['datetime_utc'] = tv_trades['datetime'] - timedelta(hours=3)

    print("\n" + "="*80)
    print("📋 SEQUENTIAL COMPARISON (First 30 trades)")
    print("="*80)
    print(f"{'#':>3} | {'TV Time':>19} | {'TV Dir':>6} | {'TV Price':>10} | {'Our Time':>19} | {'Our Dir':>6} | {'Our Price':>10} | {'Match':>6}")
    print("-"*120)

    matches = 0
    first_divergence = None
    tolerance_minutes = 60  # Allow 60 min tolerance for matching

    for i in range(min(30, len(tv_trades))):
        tv = tv_trades.iloc[i]

        # Try to find matching signal in our data
        if i < len(our_signals):
            our = our_signals.iloc[i]

            # Check if they match (within tolerance)
            time_diff = abs((our['datetime'] - tv['datetime_utc']).total_seconds() / 60)
            price_diff = abs(our['price'] - tv['price'])
            dir_match = our['direction'] == tv['direction']

            # Match criteria
            is_match = (
                time_diff <= tolerance_minutes and
                price_diff < 100 and  # $100 tolerance
                dir_match
            )

            match_str = "✅" if is_match else "❌"
            if is_match:
                matches += 1
            elif first_divergence is None:
                first_divergence = i + 1

            print(f"{i+1:>3} | {str(tv['datetime_utc'])[:19]:>19} | {tv['direction']:>6} | ${tv['price']:>9.2f} | {str(our['datetime'])[:19]:>19} | {our['direction']:>6} | ${our['price']:>9.2f} | {match_str}")
        else:
            print(f"{i+1:>3} | {str(tv['datetime_utc'])[:19]:>19} | {tv['direction']:>6} | ${tv['price']:>9.2f} | {'N/A':>19} | {'N/A':>6} | {'N/A':>10} | ❌")
            if first_divergence is None:
                first_divergence = i + 1

    print("\n" + "="*80)
    print("📊 DIVERGENCE ANALYSIS")
    print("="*80)
    print(f"Matches in first 30: {matches}/30")

    if first_divergence:
        print(f"\n🔴 FIRST DIVERGENCE AT TRADE #{first_divergence}")

        # Show details of divergence
        tv = tv_trades.iloc[first_divergence - 1]
        print(f"\n TradingView Trade #{first_divergence}:")
        print(f"   Time:      {tv['datetime_utc']} (UTC)")
        print(f"   Direction: {tv['direction']}")
        print(f"   Price:     ${tv['price']:.2f}")

        if first_divergence <= len(our_signals):
            our = our_signals.iloc[first_divergence - 1]
            print(f"\n Our Signal #{first_divergence}:")
            print(f"   Time:      {our['datetime']}")
            print(f"   Direction: {our['direction']}")
            print(f"   Price:     ${our['price']:.2f}")
            print(f"   RSI:       {our['rsi']:.4f}")

            # Analyze why
            time_diff = (our['datetime'] - tv['datetime_utc']).total_seconds() / 3600
            print("\n 📐 Differences:")
            print(f"   Time diff:  {time_diff:.1f} hours")
            print(f"   Price diff: ${abs(our['price'] - tv['price']):.2f}")
            print(f"   Direction:  {'SAME' if our['direction'] == tv['direction'] else 'DIFFERENT!'}")

    # Show aligned comparison (by price matching)
    print("\n" + "="*80)
    print("🔄 PRICE-BASED ALIGNMENT (Find where prices match)")
    print("="*80)

    for i in range(min(10, len(tv_trades))):
        tv = tv_trades.iloc[i]

        # Find closest price match in our signals
        price_diffs = abs(our_signals['price'] - tv['price'])
        closest_idx = price_diffs.idxmin()
        closest = our_signals.iloc[closest_idx]

        if price_diffs[closest_idx] < 1:  # Exact match
            our_num = closest_idx + 1
            print(f"TV #{i+1} (${tv['price']:.2f}) → Our #{our_num} (${closest['price']:.2f}) | Offset: {our_num - (i+1):+d}")

    return first_divergence


if __name__ == "__main__":
    divergence_point = find_divergence()

    print("\n" + "="*80)
    print("🏁 INVESTIGATION COMPLETE")
    print("="*80)
