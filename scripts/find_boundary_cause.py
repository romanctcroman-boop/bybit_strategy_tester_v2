"""
🎯 Find EXACT Boundary Case Causing Trade #24 Divergence
=========================================================
Simulate trades step-by-step and find where sequences diverge.
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


def calculate_rsi_wilder(close, period=14):
    """Calculate RSI with Wilder's smoothing."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    for i in range(period, len(close)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def simulate_trades_with_tracking(df):
    """
    Simulate trades with full position tracking (like TradingView).
    Only allow new entry after previous position exits via TP/SL.
    """
    OVERSOLD = 30
    OVERBOUGHT = 70
    TP_PCT = 0.015  # 1.5%
    SL_PCT = 0.03   # 3%

    # Calculate RSI
    df['rsi'] = calculate_rsi_wilder(df['close_price'], 14)
    df['prev_rsi'] = df['rsi'].shift(1)

    trades = []
    in_position = False
    position_type = None
    entry_price = 0
    entry_time = None
    entry_bar = 0

    boundary_triggers = []  # Track boundary cases that trigger trades

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_rsi = row['prev_rsi']
        curr_rsi = row['rsi']
        high = row['high_price']
        low = row['low_price']

        if pd.isna(prev_rsi) or pd.isna(curr_rsi):
            continue

        # Check exit conditions if in position
        if in_position:
            if position_type == 'LONG':
                tp_price = entry_price * (1 + TP_PCT)
                sl_price = entry_price * (1 - SL_PCT)

                if high >= tp_price:
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': row['datetime'],
                        'direction': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': tp_price,
                        'exit_reason': 'TP',
                        'entry_bar': entry_bar,
                        'exit_bar': i
                    })
                    in_position = False
                elif low <= sl_price:
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': row['datetime'],
                        'direction': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': sl_price,
                        'exit_reason': 'SL',
                        'entry_bar': entry_bar,
                        'exit_bar': i
                    })
                    in_position = False

            elif position_type == 'SHORT':
                tp_price = entry_price * (1 - TP_PCT)
                sl_price = entry_price * (1 + SL_PCT)

                if low <= tp_price:
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': row['datetime'],
                        'direction': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': tp_price,
                        'exit_reason': 'TP',
                        'entry_bar': entry_bar,
                        'exit_bar': i
                    })
                    in_position = False
                elif high >= sl_price:
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': row['datetime'],
                        'direction': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': sl_price,
                        'exit_reason': 'SL',
                        'entry_bar': entry_bar,
                        'exit_bar': i
                    })
                    in_position = False

        # Check entry conditions (only if not in position)
        if not in_position:
            # Check for boundary case
            boundary_distance = None

            # LONG signal: RSI crosses above oversold
            if prev_rsi <= OVERSOLD and curr_rsi > OVERSOLD:
                # Entry on next bar open
                if i + 1 < len(df):
                    next_bar = df.iloc[i + 1]
                    in_position = True
                    position_type = 'LONG'
                    entry_price = next_bar['open_price']
                    entry_time = next_bar['datetime']
                    entry_bar = i + 1

                    # Check if this is a boundary case
                    if abs(curr_rsi - OVERSOLD) < 0.1:
                        boundary_distance = curr_rsi - OVERSOLD
                        boundary_triggers.append({
                            'trade_num': len(trades) + 1,
                            'datetime': row['datetime'],
                            'prev_rsi': prev_rsi,
                            'curr_rsi': curr_rsi,
                            'threshold': OVERSOLD,
                            'distance': boundary_distance,
                            'direction': 'LONG'
                        })

            # SHORT signal: RSI crosses below overbought
            elif prev_rsi >= OVERBOUGHT and curr_rsi < OVERBOUGHT and i + 1 < len(df):
                next_bar = df.iloc[i + 1]
                in_position = True
                position_type = 'SHORT'
                entry_price = next_bar['open_price']
                entry_time = next_bar['datetime']
                entry_bar = i + 1

                if abs(curr_rsi - OVERBOUGHT) < 0.1:
                    boundary_distance = OVERBOUGHT - curr_rsi
                    boundary_triggers.append({
                        'trade_num': len(trades) + 1,
                        'datetime': row['datetime'],
                        'prev_rsi': prev_rsi,
                        'curr_rsi': curr_rsi,
                        'threshold': OVERBOUGHT,
                        'distance': boundary_distance,
                        'direction': 'SHORT'
                    })

    return trades, boundary_triggers


def main():
    print("="*80)
    print("🎯 FINDING EXACT BOUNDARY CASE FOR TRADE #24")
    print("="*80)

    # Load SPOT data
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='spot'
        ORDER BY open_time ASC
    """, conn)
    conn.close()

    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

    # Load TV trades
    tv_df = pd.read_csv(TV_CSV)
    tv_entries = tv_df[tv_df['Type'].str.contains('Entry', na=False)].copy().reset_index(drop=True)
    tv_entries['datetime'] = pd.to_datetime(tv_entries['Date and time']) - timedelta(hours=3)
    tv_entries['direction'] = tv_entries['Type'].apply(lambda x: 'LONG' if 'long' in x.lower() else 'SHORT')
    tv_entries['price'] = tv_entries['Price USDT']

    print(f"\n📊 Data: {len(df)} SPOT bars, {len(tv_entries)} TV trades")

    # Simulate trades
    print("\n🔄 Simulating trades with position tracking...")
    our_trades, boundary_triggers = simulate_trades_with_tracking(df)

    print("\n📊 Results:")
    print(f"   Our trades:     {len(our_trades)}")
    print(f"   TV trades:      {len(tv_entries)}")
    print(f"   Boundary cases: {len(boundary_triggers)}")

    # Find first divergence by comparing prices
    print("\n" + "="*80)
    print("📋 TRADE COMPARISON (Finding Trade #24)")
    print("="*80)

    pd.DataFrame(our_trades)

    print(f"\n{'Our#':>4} | {'Our Time':>19} | {'Our Dir':>6} | {'Our Price':>10} || {'TV#':>4} | {'TV Time':>19} | {'TV Dir':>6} | {'TV Price':>10} | {'Match'}")
    print("-"*130)

    # Match trades by price (allowing tolerance)
    for our_idx in range(min(35, len(our_trades))):
        our = our_trades[our_idx]

        # Find matching TV trade by price
        tv_match_idx = None
        for tv_idx in range(len(tv_entries)):
            tv = tv_entries.iloc[tv_idx]
            if abs(our['entry_price'] - tv['price']) < 1:  # Price match within $1
                tv_match_idx = tv_idx
                break

        if tv_match_idx is not None:
            tv = tv_entries.iloc[tv_match_idx]
            match = "✅" if our['direction'] == tv['direction'] else "⚠️ DIR"
            print(f"{our_idx+1:>4} | {str(our['entry_time'])[:19]:>19} | {our['direction']:>6} | ${our['entry_price']:>9.2f} || {tv_match_idx+1:>4} | {str(tv['datetime'])[:19]:>19} | {tv['direction']:>6} | ${tv['price']:>9.2f} | {match}")
        else:
            print(f"{our_idx+1:>4} | {str(our['entry_time'])[:19]:>19} | {our['direction']:>6} | ${our['entry_price']:>9.2f} || {'N/A':>4} | {'':>19} | {'':>6} | {'':>10} | ❌ NO MATCH")

    # Show boundary triggers around Trade #24
    print("\n" + "="*80)
    print("🔬 BOUNDARY CASES THAT TRIGGERED TRADES (near Trade #24)")
    print("="*80)

    # Trade #24 is around Oct 30
    target_date = pd.Timestamp('2025-10-30')

    for bt in boundary_triggers:
        dt = bt['datetime']
        if isinstance(dt, str):
            dt = pd.Timestamp(dt)

        days_from_target = abs((dt - target_date).days)
        marker = " 🔴 NEAR TRADE #24!" if days_from_target <= 5 else ""

        print(f"  Trade ~#{bt['trade_num']:>2} | {str(bt['datetime'])[:19]} | {bt['direction']:>5} | RSI: {bt['prev_rsi']:.4f} → {bt['curr_rsi']:.4f} | Δ={bt['distance']:.6f}{marker}")

    # Find the specific boundary that could cause issue
    print("\n" + "="*80)
    print("🎯 SMOKING GUN ANALYSIS")
    print("="*80)

    # Find boundaries closest to threshold
    sorted_boundaries = sorted(boundary_triggers, key=lambda x: x['distance'])

    print("\n🔥 Closest to threshold (most likely to cause divergence):")
    for i, bt in enumerate(sorted_boundaries[:5]):
        print(f"  #{i+1}: {bt['datetime']} | RSI={bt['curr_rsi']:.6f} | Δ from {bt['threshold']}={bt['distance']:.6f} | {bt['direction']}")

    # Check if any of these are before Trade #24 (Oct 30)
    print("\n" + "="*80)
    print("🔴 VERDICT: Root Cause Analysis")
    print("="*80)

    before_trade_24 = [bt for bt in sorted_boundaries if bt['datetime'] < pd.Timestamp('2025-10-30')]

    if before_trade_24:
        suspect = before_trade_24[0]
        print(f"""
The EARLIEST boundary case before Trade #24 with smallest distance:

📍 Date:       {suspect['datetime']}
📈 Direction:  {suspect['direction']}
📊 RSI:        {suspect['prev_rsi']:.6f} → {suspect['curr_rsi']:.6f}
🎯 Threshold:  {suspect['threshold']}
📐 Distance:   {suspect['distance']:.6f}

HYPOTHESIS:
  If TradingView rounds {suspect['curr_rsi']:.4f} to {suspect['threshold']:.1f},
  it would trigger a {suspect['direction']} signal that we MISS.

  This would cause a +1 trade offset that propagates to Trade #24!
""")
    else:
        print("No boundary cases found before Trade #24!")


if __name__ == "__main__":
    main()
