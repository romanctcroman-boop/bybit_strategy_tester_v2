"""
CORRECTED P&L PARITY ANALYSIS
==============================
Parse TV CSV correctly (2 rows per trade = Entry + Exit).
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3

import pandas as pd

DB_PATH = project_root / "data.sqlite3"
TV_CSV = Path(r"d:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-21.csv")

# Strategy params
RSI_PERIOD = 14
RSI_OVERSOLD = 25
RSI_OVERBOUGHT = 70
TP_PCT = 0.015
SL_PCT = 0.03
INITIAL_CAPITAL = 100.0
LEVERAGE = 10


def calculate_rsi_wilder(close, period=14):
    """Wilder's RSI calculation"""
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


def parse_tv_trades():
    """Parse TV CSV - correctly handle 2 rows per trade"""
    df = pd.read_csv(TV_CSV, encoding='utf-8-sig')

    # Get actual trades (Exit rows contain the final P&L)
    # Each trade has Entry and Exit row with same № Сделки (Trade Number)
    pnl_col = 'Чистая прибыль / убыток USDT'

    trades = []
    trade_nums = df['№ Сделки'].unique()

    for trade_num in trade_nums:
        trade_rows = df[df['№ Сделки'] == trade_num]
        if len(trade_rows) != 2:
            continue

        # Get entry and exit rows
        exit_row = trade_rows[trade_rows['Тип'].str.contains('Выход')]
        entry_row = trade_rows[trade_rows['Тип'].str.contains('Вход')]

        if len(exit_row) == 0 or len(entry_row) == 0:
            continue

        exit_row = exit_row.iloc[0]
        entry_row = entry_row.iloc[0]

        pnl = float(str(exit_row[pnl_col]).replace(',', '.').replace(' ', ''))

        # Direction
        direction = 'LONG' if 'длинную' in entry_row['Тип'] else 'SHORT'

        trades.append({
            'trade_num': trade_num,
            'direction': direction,
            'entry_time': entry_row['Дата и время'],
            'exit_time': exit_row['Дата и время'],
            'entry_price': entry_row['Цена USDT'],
            'exit_price': exit_row['Цена USDT'],
            'signal': exit_row['Сигнал'],
            'pnl': pnl,
            'is_win': pnl > 0
        })

    return pd.DataFrame(trades)


def simulate_our_trades(df):
    """Our engine simulation - EXACT TP PRICE (TV standard behavior)"""
    df = df.copy()
    df['rsi'] = calculate_rsi_wilder(df['close_price'], RSI_PERIOD)
    df['prev_rsi'] = df['rsi'].shift(1)

    trades = []
    in_position = False
    position_type = None
    entry_price = 0
    entry_time = None
    position_size = INITIAL_CAPITAL * LEVERAGE

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

            exit_price = None
            exit_reason = None

            if position_type == 'LONG':
                tp_price = entry_price * (1 + TP_PCT)
                sl_price = entry_price * (1 - SL_PCT)

                if abs(open_price - low) <= abs(open_price - high):
                    if low <= sl_price:
                        exit_price = sl_price
                        exit_reason = 'SL'
                    elif high >= tp_price:
                        # Exit at TP price (standard TradingView)
                        exit_price = tp_price
                        exit_reason = 'TP'
                else:
                    if high >= tp_price:
                        exit_price = tp_price
                        exit_reason = 'TP'
                    elif low <= sl_price:
                        exit_price = sl_price
                        exit_reason = 'SL'

            elif position_type == 'SHORT':
                tp_price = entry_price * (1 - TP_PCT)
                sl_price = entry_price * (1 + SL_PCT)

                if abs(open_price - low) <= abs(open_price - high):
                    if low <= tp_price:
                        exit_price = tp_price
                        exit_reason = 'TP'
                    elif high >= sl_price:
                        exit_price = sl_price
                        exit_reason = 'SL'
                else:
                    if high >= sl_price:
                        exit_price = sl_price
                        exit_reason = 'SL'
                    elif low <= tp_price:
                        exit_price = tp_price
                        exit_reason = 'TP'

            if exit_price and exit_reason:
                if position_type == 'LONG':
                    pnl_pct = (exit_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - exit_price) / entry_price

                # Commission: 0.07% entry + 0.07% exit = 0.14% total
                commission_pct = 0.0014
                net_pnl = position_size * pnl_pct - position_size * commission_pct

                trades.append({
                    'direction': position_type,
                    'entry_time': entry_time,
                    'exit_time': row['datetime'],
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'pnl': net_pnl,
                    'is_win': net_pnl > 0
                })
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

    return pd.DataFrame(trades)


def main():
    print("="*100)
    print("CORRECTED P&L PARITY ANALYSIS - Trade by Trade Comparison")
    print("="*100)

    # Parse TV trades
    tv_trades = parse_tv_trades()
    print(f"\nTV Trades: {len(tv_trades)}")
    print(f"TV Net Profit: {tv_trades['pnl'].sum():.2f}")
    print(f"TV Wins: {tv_trades['is_win'].sum()}, Losses: {(~tv_trades['is_win']).sum()}")

    # Simulate our trades
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

    our_trades = simulate_our_trades(df)
    print(f"\nOur Trades: {len(our_trades)}")
    print(f"Our Net Profit: {our_trades['pnl'].sum():.2f}")
    print(f"Our Wins: {our_trades['is_win'].sum()}, Losses: {(~our_trades['is_win']).sum()}")

    # Trade by trade comparison
    print("\n" + "="*100)
    print("TRADE-BY-TRADE P&L COMPARISON")
    print("="*100)
    print(f"\n{'#':>3} | {'Dir':>5} | {'TV P&L':>10} | {'Our P&L':>10} | {'Diff':>10} | {'Status'}")
    print("-"*65)

    total_diff = 0
    exact_matches = 0

    for i in range(min(len(tv_trades), len(our_trades))):
        tv_pnl = tv_trades.iloc[i]['pnl']
        our_pnl = our_trades.iloc[i]['pnl']
        direction = our_trades.iloc[i]['direction']
        diff = our_pnl - tv_pnl
        total_diff += abs(diff)

        if abs(diff) < 0.1:
            status = "✓ MATCH"
            exact_matches += 1
        elif abs(diff) < 1.0:
            status = "~ CLOSE"
        else:
            status = "✗ DIFF"

        print(f"{i+1:>3} | {direction:>5} | {tv_pnl:>+10.2f} | {our_pnl:>+10.2f} | {diff:>+10.2f} | {status}")

    # Summary
    print("\n" + "="*100)
    print("PARITY SUMMARY")
    print("="*100)

    tv_total = tv_trades['pnl'].sum()
    our_total = our_trades['pnl'].sum()

    print(f"""
    TV Net Profit:        {tv_total:>10.2f} USDT
    Our Net Profit:       {our_total:>10.2f} USDT
    Difference:           {our_total - tv_total:>+10.2f} USDT ({(our_total - tv_total)/tv_total*100:+.2f}%)

    Exact P&L Matches:    {exact_matches} / {min(len(tv_trades), len(our_trades))} ({exact_matches/min(len(tv_trades), len(our_trades))*100:.1f}%)
    Total Abs Diff:       {total_diff:.2f} USDT
    Avg Diff per Trade:   {total_diff/min(len(tv_trades), len(our_trades)):.2f} USDT
""")

    # Analyze where differences come from
    print("\n--- Win/Loss P&L Distribution ---")

    tv_wins = tv_trades[tv_trades['is_win']]['pnl']
    tv_losses = tv_trades[~tv_trades['is_win']]['pnl']
    our_wins = our_trades[our_trades['is_win']]['pnl']
    our_losses = our_trades[~our_trades['is_win']]['pnl']

    print(f"\nTV Winning trades P&L: min={tv_wins.min():.2f}, max={tv_wins.max():.2f}, avg={tv_wins.mean():.2f}")
    print(f"Our Winning trades P&L: min={our_wins.min():.2f}, max={our_wins.max():.2f}, avg={our_wins.mean():.2f}")

    print(f"\nTV Losing trades P&L: min={tv_losses.min():.2f}, max={tv_losses.max():.2f}, avg={tv_losses.mean():.2f}")
    print(f"Our Losing trades P&L: min={our_losses.min():.2f}, max={our_losses.max():.2f}, avg={our_losses.mean():.2f}")


if __name__ == "__main__":
    main()
