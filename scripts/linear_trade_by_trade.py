"""
🔬 TRADE-BY-TRADE LINEAR COMPARISON
=====================================
Compare each trade sequentially between Our Engine and TradingView.
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
from datetime import timedelta

import pandas as pd

DB_PATH = project_root / "data.sqlite3"
TV_CSV = Path(r"d:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-21.csv")

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
    """Simulate with position tracking, return list of trades"""
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
                                       'entry_price': entry_price, 'exit_reason': 'SL',
                                       'exit_time': row['datetime']})
                        in_position = False
                    elif high >= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'LONG',
                                       'entry_price': entry_price, 'exit_reason': 'TP',
                                       'exit_time': row['datetime']})
                        in_position = False
                else:
                    if high >= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'LONG',
                                       'entry_price': entry_price, 'exit_reason': 'TP',
                                       'exit_time': row['datetime']})
                        in_position = False
                    elif low <= sl_price:
                        trades.append({'entry_time': entry_time, 'direction': 'LONG',
                                       'entry_price': entry_price, 'exit_reason': 'SL',
                                       'exit_time': row['datetime']})
                        in_position = False

            elif position_type == 'SHORT':
                tp_price = entry_price * (1 - TP_PCT)
                sl_price = entry_price * (1 + SL_PCT)
                open_to_low = abs(open_price - low)
                open_to_high = abs(open_price - high)

                if open_to_low <= open_to_high:
                    if low <= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT',
                                       'entry_price': entry_price, 'exit_reason': 'TP',
                                       'exit_time': row['datetime']})
                        in_position = False
                    elif high >= sl_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT',
                                       'entry_price': entry_price, 'exit_reason': 'SL',
                                       'exit_time': row['datetime']})
                        in_position = False
                else:
                    if high >= sl_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT',
                                       'entry_price': entry_price, 'exit_reason': 'SL',
                                       'exit_time': row['datetime']})
                        in_position = False
                    elif low <= tp_price:
                        trades.append({'entry_time': entry_time, 'direction': 'SHORT',
                                       'entry_price': entry_price, 'exit_reason': 'TP',
                                       'exit_time': row['datetime']})
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
    """Load TV trades from CSV (Russian localization)"""
    df = pd.read_csv(TV_CSV)

    # Find entry rows
    if 'Тип' in df.columns:
        entries = df[df['Тип'].str.contains('Вход', na=False, case=False)].copy()
    else:
        return None

    entries = entries.reset_index(drop=True)

    result = []
    for _, row in entries.iterrows():
        direction = 'LONG'

        type_col = str(row.get('Тип', ''))
        if 'короткую' in type_col.lower():
            direction = 'SHORT'
        elif 'длинную' in type_col.lower():
            direction = 'LONG'

        price = row.get('Цена USDT', 0)
        if isinstance(price, str):
            price = float(price.replace(',', '.').replace(' ', ''))

        # Parse datetime and convert MSK to UTC
        dt_str = row.get('Дата и время', '')
        dt = pd.to_datetime(dt_str)
        dt_utc = dt - timedelta(hours=3)  # MSK to UTC

        result.append({
            'direction': direction,
            'price': float(price),
            'datetime': dt_utc
        })

    return pd.DataFrame(result)


def main():
    print("="*100)
    print("🔬 TRADE-BY-TRADE LINEAR COMPARISON: Our Engine vs TradingView")
    print("="*100)

    # Load DB data
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT open_time, open_price, high_price, low_price, close_price
        FROM bybit_kline_audit
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear'
        ORDER BY open_time ASC
    """, conn)
    conn.close()

    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
    df = df[(df['datetime'] >= '2025-10-01') & (df['datetime'] <= '2026-01-21 23:59:59')].copy()
    df = df.reset_index(drop=True)

    print(f"\n📊 LINEAR Data: {len(df)} bars")

    # Simulate our trades
    our_trades = simulate_strategy(df)
    pd.DataFrame(our_trades)

    print(f"📊 Our Trades: {len(our_trades)}")

    # Load TV trades
    tv_trades = load_tv_trades()
    print(f"📊 TV Trades: {len(tv_trades)}")

    # Sequential comparison
    print("\n" + "="*100)
    print("📋 SEQUENTIAL TRADE-BY-TRADE COMPARISON")
    print("="*100)

    max_trades = max(len(our_trades), len(tv_trades))

    print(f"\n{'#':>3} | {'Our Time':>20} | {'Our Dir':>6} | {'Our Price':>10} | {'TV Time':>20} | {'TV Dir':>6} | {'TV Price':>10} | {'Match'}")
    print("-"*110)

    matches = 0
    price_matches = 0
    direction_matches = 0

    for i in range(max_trades):
        our_time = ""
        our_dir = ""
        our_price = ""
        tv_time = ""
        tv_dir = ""
        tv_price = ""
        match_str = ""

        if i < len(our_trades):
            our = our_trades[i]
            our_time = str(our['entry_time'])[:19]
            our_dir = our['direction']
            our_price = f"${our['entry_price']:.2f}"

        if i < len(tv_trades):
            tv = tv_trades.iloc[i]
            tv_time = str(tv['datetime'])[:19]
            tv_dir = tv['direction']
            tv_price = f"${tv['price']:.2f}"

        # Check match
        if i < len(our_trades) and i < len(tv_trades):
            our = our_trades[i]
            tv = tv_trades.iloc[i]

            price_diff = abs(our['entry_price'] - tv['price'])
            dir_match = our['direction'] == tv['direction']

            if dir_match:
                direction_matches += 1

            if price_diff < 1:
                price_matches += 1
                if dir_match:
                    match_str = "✅"
                    matches += 1
                else:
                    match_str = "❌ DIR"
            elif price_diff < 50:
                match_str = f"⚠️ Δ${price_diff:.0f}"
            else:
                match_str = f"❌ Δ${price_diff:.0f}"
        elif i < len(our_trades):
            match_str = "❌ TV missing"
        else:
            match_str = "❌ Our missing"

        print(f"{i+1:>3} | {our_time:>20} | {our_dir:>6} | {our_price:>10} | {tv_time:>20} | {tv_dir:>6} | {tv_price:>10} | {match_str}")

    # Summary
    print("\n" + "="*100)
    print("📊 SUMMARY")
    print("="*100)
    print(f"""
    Our Trades:         {len(our_trades)}
    TV Trades:          {len(tv_trades)}

    Exact Matches:      {matches}/{min(len(our_trades), len(tv_trades))} ({matches/min(len(our_trades), len(tv_trades))*100:.1f}%)
    Price Matches:      {price_matches}/{min(len(our_trades), len(tv_trades))} ({price_matches/min(len(our_trades), len(tv_trades))*100:.1f}%)
    Direction Matches:  {direction_matches}/{min(len(our_trades), len(tv_trades))} ({direction_matches/min(len(our_trades), len(tv_trades))*100:.1f}%)

    🎯 SEQUENCE PARITY: {matches/min(len(our_trades), len(tv_trades))*100:.1f}%
""")


if __name__ == "__main__":
    main()
