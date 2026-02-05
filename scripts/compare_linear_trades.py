"""
🔬 Trade-by-Trade Sequence Comparison: LINEAR
==============================================
Compare our trades with TradingView trades by entry price matching.
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3

import pandas as pd

DB_PATH = project_root / "data.sqlite3"

# Strategy params
RSI_PERIOD = 14
RSI_OVERSOLD = 25
RSI_OVERBOUGHT = 70
TP_PCT = 0.015
SL_PCT = 0.03


def calculate_rsi_wilder(close, period=14):
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


def simulate_strategy(df):
    """Simulate with position tracking"""
    df = df.copy()
    df['rsi'] = calculate_rsi_wilder(df['close_price'], RSI_PERIOD)
    df['prev_rsi'] = df['rsi'].shift(1)

    trades = []
    in_position = False
    position_type = None
    entry_price = 0
    entry_time = None

    for i in range(1, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        prev_rsi = row['prev_rsi']
        curr_rsi = row['rsi']

        if pd.isna(prev_rsi) or pd.isna(curr_rsi):
            continue

        if in_position:
            high = row['high_price']
            low = row['low_price']
            open_price = row['open_price']

            if position_type == 'LONG':
                tp_price = entry_price * (1 + TP_PCT)
                sl_price = entry_price * (1 - SL_PCT)

                open_to_low = abs(open_price - low)
                open_to_high = abs(open_price - high)

                if open_to_low <= open_to_high:
                    if low <= sl_price:
                        trades.append({'entry_time': entry_time, 'direction': 'LONG',
                                       'entry_price': entry_price, 'exit_reason': 'SL'})
                        in_position = False
                    elif high >= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'LONG',
                                       'entry_price': entry_price, 'exit_reason': 'TP'})
                        in_position = False
                else:
                    if high >= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'LONG',
                                       'entry_price': entry_price, 'exit_reason': 'TP'})
                        in_position = False
                    elif low <= sl_price:
                        trades.append({'entry_time': entry_time, 'direction': 'LONG',
                                       'entry_price': entry_price, 'exit_reason': 'SL'})
                        in_position = False

            elif position_type == 'SHORT':
                tp_price = entry_price * (1 - TP_PCT)
                sl_price = entry_price * (1 + SL_PCT)

                open_to_low = abs(open_price - low)
                open_to_high = abs(open_price - high)

                if open_to_low <= open_to_high:
                    if low <= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT',
                                       'entry_price': entry_price, 'exit_reason': 'TP'})
                        in_position = False
                    elif high >= sl_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT',
                                       'entry_price': entry_price, 'exit_reason': 'SL'})
                        in_position = False
                else:
                    if high >= sl_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT',
                                       'entry_price': entry_price, 'exit_reason': 'SL'})
                        in_position = False
                    elif low <= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT',
                                       'entry_price': entry_price, 'exit_reason': 'TP'})
                        in_position = False

        if not in_position:
            if prev_rsi <= RSI_OVERSOLD and curr_rsi > RSI_OVERSOLD:
                in_position = True
                position_type = 'LONG'
                entry_price = next_row['open_price']
                entry_time = next_row['datetime']

            elif prev_rsi >= RSI_OVERBOUGHT and curr_rsi < RSI_OVERBOUGHT:
                in_position = True
                position_type = 'SHORT'
                entry_price = next_row['open_price']
                entry_time = next_row['datetime']

    return trades


def load_tv_trades():
    """Load TV trades from CSV"""
    csv_path = Path(r"d:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-21.csv")

    if not csv_path.exists():
        # Try alternative names
        alternatives = list(Path(r"d:\TV").glob("*BTCUSDT.P*2026*.csv"))
        if alternatives:
            csv_path = alternatives[0]
        else:
            print("⚠️ TV CSV not found!")
            return None

    df = pd.read_csv(csv_path)
    print(f"TV CSV columns: {df.columns.tolist()}")

    # Find entry rows
    if 'Type' in df.columns:
        entries = df[df['Type'].str.contains('Entry', na=False, case=False)].copy()
    elif 'Тип' in df.columns:
        entries = df[df['Тип'].str.contains('Вход', na=False, case=False)].copy()
    else:
        # Assume every other row is entry/exit
        print("Using alternating rows as entries")
        entries = df.iloc[::2].copy()

    entries = entries.reset_index(drop=True)

    # Parse direction and price
    result = []
    for _, row in entries.iterrows():
        direction = 'LONG'
        price = 0

        # Find direction (handle Russian localization)
        type_col = str(row.get('Type', row.get('Тип', '')))

        # Russian: "Вход в короткую позицию" = SHORT, "Вход в длинную позицию" = LONG
        if 'короткую' in type_col.lower() or 'short' in type_col.lower():
            direction = 'SHORT'
        elif 'длинную' in type_col.lower() or 'long' in type_col.lower():
            direction = 'LONG'
        elif 'продажа' in type_col.lower():
            direction = 'SHORT'
        elif 'покупка' in type_col.lower():
            direction = 'LONG'

        # Find price
        price_col = row.get('Price USDT', row.get('Цена USDT', row.get('Price', 0)))
        if isinstance(price_col, str):
            price_col = float(price_col.replace(',', '.').replace(' ', ''))
        price = float(price_col)

        # Find datetime
        dt_col = row.get('Date and time', row.get('Дата/время', row.get('Date', '')))

        result.append({
            'direction': direction,
            'price': price,
            'datetime': str(dt_col)
        })

    return pd.DataFrame(result)


def main():
    print("="*80)
    print("🔬 TRADE-BY-TRADE SEQUENCE COMPARISON (LINEAR)")
    print("="*80)

    # Load our data (LINEAR only, filtered by date)
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT open_time, open_price, high_price, low_price, close_price
        FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear'
        ORDER BY open_time ASC
    """, conn)
    conn.close()

    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

    # Filter to TV date range
    df = df[(df['datetime'] >= '2025-10-01') & (df['datetime'] <= '2026-01-21 23:59:59')].copy()
    df = df.reset_index(drop=True)

    print(f"\n📊 Our Data: {len(df)} bars")

    # Simulate
    our_trades = simulate_strategy(df)
    our_df = pd.DataFrame(our_trades)

    print(f"📊 Our Trades: {len(our_trades)}")

    # Load TV trades
    tv_trades = load_tv_trades()

    if tv_trades is None or len(tv_trades) == 0:
        print("❌ Could not load TV trades!")
        return

    print(f"📊 TV Trades: {len(tv_trades)}")

    # Compare by price
    print("\n" + "="*80)
    print("📋 PRICE-BASED MATCHING (First 40 trades)")
    print("="*80)

    print(f"\n{'Our#':>4} | {'Our Time':>19} | {'Our Dir':>6} | {'Our Price':>10} || {'TV#':>4} | {'TV Dir':>6} | {'TV Price':>10} | {'Match'}")
    print("-"*110)

    matched = 0
    unmatched_ours = []
    unmatched_tv = set(range(len(tv_trades)))

    for our_idx, our in our_df.iterrows():
        if our_idx >= 40:
            break

        # Find matching TV trade by price
        best_match = None
        best_diff = float('inf')

        for tv_idx, tv in tv_trades.iterrows():
            price_diff = abs(our['entry_price'] - tv['price'])
            if price_diff < best_diff:
                best_diff = price_diff
                best_match = tv_idx

        if best_match is not None and best_diff < 50:  # $50 tolerance
            tv = tv_trades.iloc[best_match]
            dir_match = our['direction'] == tv['direction']

            if dir_match and best_diff < 10:
                match_str = "✅"
                matched += 1
                unmatched_tv.discard(best_match)
            elif dir_match:
                match_str = f"⚠️ Δ${best_diff:.0f}"
            else:
                match_str = "❌ DIR"

            print(f"{our_idx+1:>4} | {str(our['entry_time'])[:19]:>19} | {our['direction']:>6} | ${our['entry_price']:>9.2f} || {best_match+1:>4} | {tv['direction']:>6} | ${tv['price']:>9.2f} | {match_str}")
        else:
            print(f"{our_idx+1:>4} | {str(our['entry_time'])[:19]:>19} | {our['direction']:>6} | ${our['entry_price']:>9.2f} || {'N/A':>4} | {'':>6} | {'':>10} | ❌ NO MATCH")
            unmatched_ours.append(our_idx)

    # Summary
    print("\n" + "="*80)
    print("📊 SEQUENCE PARITY SUMMARY")
    print("="*80)

    total_our = len(our_trades)
    total_tv = len(tv_trades)

    print(f"\nOur trades:       {total_our}")
    print(f"TV trades:        {total_tv}")
    print(f"Matched:          {matched} (of first 40)")

    # Calculate sequence parity
    # Try to match ALL trades
    all_matched = 0
    for our_idx, our in our_df.iterrows():
        for tv_idx, tv in tv_trades.iterrows():
            if abs(our['entry_price'] - tv['price']) < 5 and our['direction'] == tv['direction']:
                all_matched += 1
                break

    seq_parity = all_matched / max(total_our, total_tv) * 100

    print(f"\n🎯 SEQUENCE PARITY: {all_matched}/{max(total_our, total_tv)} = {seq_parity:.1f}%")

    # Find extra trades (ours but not in TV)
    print("\n" + "="*80)
    print("🔍 UNMATCHED TRADES ANALYSIS")
    print("="*80)

    our_prices = set(round(t['entry_price'], 0) for t in our_trades)
    tv_prices = set(round(p, 0) for p in tv_trades['price'])

    extra_ours = our_prices - tv_prices
    missing_tv = tv_prices - our_prices

    print(f"\nPrices only in OUR trades: {len(extra_ours)}")
    for p in sorted(extra_ours)[:5]:
        print(f"  ${p:.0f}")

    print(f"\nPrices only in TV trades: {len(missing_tv)}")
    for p in sorted(missing_tv)[:5]:
        print(f"  ${p:.0f}")


if __name__ == "__main__":
    main()
