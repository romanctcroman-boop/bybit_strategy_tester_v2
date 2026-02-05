"""
🔬 CORRECT PARITY COMPARISON
=============================
1. TV SPOT (BTCUSDT) vs Our SPOT data
2. TV LINEAR (BTCUSDT.P) vs Our LINEAR data
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3

import pandas as pd

DB_PATH = project_root / "data.sqlite3"

# Strategy params (from TV screenshot)
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
    """Simulate trades with position tracking"""
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
                    if low <= sl_price or high >= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'LONG', 'entry_price': entry_price})
                        in_position = False
                else:
                    if high >= tp_price or low <= sl_price:
                        trades.append({'entry_time': entry_time, 'direction': 'LONG', 'entry_price': entry_price})
                        in_position = False

            elif position_type == 'SHORT':
                tp_price = entry_price * (1 - TP_PCT)
                sl_price = entry_price * (1 + SL_PCT)

                open_to_low = abs(open_price - low)
                open_to_high = abs(open_price - high)

                if open_to_low <= open_to_high:
                    if low <= tp_price or high >= sl_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT', 'entry_price': entry_price})
                        in_position = False
                else:
                    if high >= sl_price or low <= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT', 'entry_price': entry_price})
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


def load_tv_trades(csv_path):
    """Load TV trades from CSV (handle Russian localization)"""
    if not csv_path.exists():
        return None

    df = pd.read_csv(csv_path)

    # Find entry rows
    if 'Тип' in df.columns:
        entries = df[df['Тип'].str.contains('Вход', na=False, case=False)].copy()
    elif 'Type' in df.columns:
        entries = df[df['Type'].str.contains('Entry', na=False, case=False)].copy()
    else:
        return None

    entries = entries.reset_index(drop=True)

    result = []
    for _, row in entries.iterrows():
        direction = 'LONG'
        price = 0

        type_col = str(row.get('Тип', row.get('Type', '')))

        # Russian localization
        if 'короткую' in type_col.lower() or 'short' in type_col.lower():
            direction = 'SHORT'
        elif 'длинную' in type_col.lower() or 'long' in type_col.lower():
            direction = 'LONG'

        # Price
        price_col = row.get('Цена USDT', row.get('Price USDT', row.get('Price', 0)))
        if isinstance(price_col, str):
            price_col = float(price_col.replace(',', '.').replace(' ', ''))
        price = float(price_col)

        result.append({'direction': direction, 'price': price})

    return pd.DataFrame(result)


def compare_trades(our_trades, tv_trades, market_name):
    """Compare trade sequences"""
    print(f"\n{'='*80}")
    print(f"📊 {market_name} TRADE COMPARISON")
    print("="*80)

    our_df = pd.DataFrame(our_trades)

    print(f"\nOur {market_name} trades: {len(our_trades)}")
    print(f"TV {market_name} trades:  {len(tv_trades)}")

    # Match by price (within $1 tolerance)
    matched = 0
    matched_direction = 0
    close_matches = 0

    for _, our in our_df.iterrows():
        for _, tv in tv_trades.iterrows():
            price_diff = abs(our['entry_price'] - tv['price'])
            if price_diff < 1:  # Exact match
                matched += 1
                if our['direction'] == tv['direction']:
                    matched_direction += 1
                break
            elif price_diff < 50:  # Close match
                close_matches += 1
                break

    exact_parity = matched / len(tv_trades) * 100 if len(tv_trades) > 0 else 0

    print("\n📋 Results:")
    print(f"   Exact price matches (<$1):      {matched}/{len(tv_trades)} ({exact_parity:.1f}%)")
    print(f"   Direction matches:              {matched_direction}/{matched}")
    print(f"   Close matches ($1-50):          {close_matches}")

    # Show first 20 comparisons
    print(f"\n{'Our#':>4} | {'Our Dir':>6} | {'Our Price':>10} || {'TV#':>4} | {'TV Dir':>6} | {'TV Price':>10} | {'Match'}")
    print("-"*85)

    for our_idx in range(min(20, len(our_trades))):
        our = our_df.iloc[our_idx]

        # Find closest TV match
        best_match = None
        best_diff = float('inf')

        for tv_idx, tv in tv_trades.iterrows():
            diff = abs(our['entry_price'] - tv['price'])
            if diff < best_diff:
                best_diff = diff
                best_match = tv_idx

        if best_match is not None and best_diff < 100:
            tv = tv_trades.iloc[best_match]

            if best_diff < 1:
                match_str = "✅"
            elif best_diff < 10:
                match_str = f"⚠️ Δ${best_diff:.0f}"
            else:
                match_str = f"❌ Δ${best_diff:.0f}"

            print(f"{our_idx+1:>4} | {our['direction']:>6} | ${our['entry_price']:>9.2f} || {best_match+1:>4} | {tv['direction']:>6} | ${tv['price']:>9.2f} | {match_str}")
        else:
            print(f"{our_idx+1:>4} | {our['direction']:>6} | ${our['entry_price']:>9.2f} || {'N/A':>4} | {'':>6} | {'':>10} | ❌")

    return exact_parity


def main():
    print("="*80)
    print("🔬 CORRECT MARKET-TO-MARKET PARITY COMPARISON")
    print("="*80)

    # ========== SPOT COMPARISON ==========
    print("\n" + "="*80)
    print("📈 1. SPOT MARKET: TV SPOT vs Our SPOT")
    print("="*80)

    conn = sqlite3.connect(DB_PATH)
    spot_df = pd.read_sql_query("""
        SELECT open_time, open_price, high_price, low_price, close_price
        FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='spot'
        ORDER BY open_time ASC
    """, conn)
    conn.close()

    spot_df['datetime'] = pd.to_datetime(spot_df['open_time'], unit='ms')
    print(f"SPOT Data: {len(spot_df)} bars ({spot_df['datetime'].min()} to {spot_df['datetime'].max()})")

    our_spot_trades = simulate_strategy(spot_df)

    # Load TV SPOT trades
    tv_spot_csv = Path(r"d:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT_2026-01-21.csv")
    if not tv_spot_csv.exists():
        tv_spot_csv = list(Path(r"d:\TV").glob("*BTCUSDT_2026*.csv"))[0]

    tv_spot_trades = load_tv_trades(tv_spot_csv)

    if tv_spot_trades is not None:
        spot_parity = compare_trades(our_spot_trades, tv_spot_trades, "SPOT")

    # ========== LINEAR COMPARISON ==========
    print("\n" + "="*80)
    print("📈 2. LINEAR MARKET: TV PERP vs Our LINEAR")
    print("="*80)

    conn = sqlite3.connect(DB_PATH)
    linear_df = pd.read_sql_query("""
        SELECT open_time, open_price, high_price, low_price, close_price
        FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear'
        ORDER BY open_time ASC
    """, conn)
    conn.close()

    linear_df['datetime'] = pd.to_datetime(linear_df['open_time'], unit='ms')

    # Filter to same date range as SPOT/TV
    linear_df = linear_df[(linear_df['datetime'] >= '2025-10-01') &
                          (linear_df['datetime'] <= '2026-01-21 23:59:59')].copy()
    linear_df = linear_df.reset_index(drop=True)

    print(f"LINEAR Data: {len(linear_df)} bars ({linear_df['datetime'].min()} to {linear_df['datetime'].max()})")

    our_linear_trades = simulate_strategy(linear_df)

    # Load TV LINEAR trades
    tv_linear_csv = Path(r"d:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-21.csv")
    if not tv_linear_csv.exists():
        matches = list(Path(r"d:\TV").glob("*BTCUSDT.P*2026*.csv"))
        if matches:
            tv_linear_csv = matches[0]

    tv_linear_trades = load_tv_trades(tv_linear_csv)

    if tv_linear_trades is not None:
        linear_parity = compare_trades(our_linear_trades, tv_linear_trades, "LINEAR")

    # ========== FINAL SUMMARY ==========
    print("\n" + "="*80)
    print("🏁 FINAL PARITY SUMMARY")
    print("="*80)
    print(f"""
   SPOT MARKET (BTCUSDT):
     Our trades:    {len(our_spot_trades)}
     TV trades:     {len(tv_spot_trades) if tv_spot_trades is not None else 'N/A'}
     Parity:        {spot_parity:.1f}%

   LINEAR MARKET (BTCUSDT.P):
     Our trades:    {len(our_linear_trades)}
     TV trades:     {len(tv_linear_trades) if tv_linear_trades is not None else 'N/A'}
     Parity:        {linear_parity:.1f}%
""")


if __name__ == "__main__":
    main()
