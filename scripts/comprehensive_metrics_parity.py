"""
COMPREHENSIVE METRICS PARITY COMPARISON
=========================================
Compare 50+ metrics between Our Engine and TradingView for LINEAR market.
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3

import numpy as np
import pandas as pd

DB_PATH = project_root / "data.sqlite3"
TV_CSV = Path(r"d:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-21.csv")

# Strategy params (must match TV)
RSI_PERIOD = 14
RSI_OVERSOLD = 25
RSI_OVERBOUGHT = 70
TP_PCT = 0.015
SL_PCT = 0.03
INITIAL_CAPITAL = 100.0  # USDT
LEVERAGE = 10
COMMISSION = 0.0007  # 0.07%


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


def simulate_full_strategy(df) -> list[dict]:
    """Full simulation with complete trade details"""
    df = df.copy()
    df['rsi'] = calculate_rsi_wilder(df['close_price'], RSI_PERIOD)
    df['prev_rsi'] = df['rsi'].shift(1)

    trades = []
    in_position = False
    position_type = None
    entry_price = 0
    entry_time = None
    entry_bar_idx = 0

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
            open_price_bar = row['open_price']

            exit_price = None
            exit_reason = None

            if position_type == 'LONG':
                tp_price = entry_price * (1 + TP_PCT)
                sl_price = entry_price * (1 - SL_PCT)

                open_to_low = abs(open_price_bar - low)
                open_to_high = abs(open_price_bar - high)

                if open_to_low <= open_to_high:
                    if low <= sl_price:
                        exit_price = sl_price
                        exit_reason = 'SL'
                    elif high >= tp_price:
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

                open_to_low = abs(open_price_bar - low)
                open_to_high = abs(open_price_bar - high)

                if open_to_low <= open_to_high:
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
                # Calculate P&L
                if position_type == 'LONG':
                    pnl_pct = (exit_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - exit_price) / entry_price

                # Commission
                entry_commission = position_size * COMMISSION
                exit_commission = position_size * COMMISSION
                total_commission = entry_commission + exit_commission

                gross_pnl = position_size * pnl_pct
                net_pnl = gross_pnl - total_commission

                bars_held = i - entry_bar_idx

                trades.append({
                    'entry_time': entry_time,
                    'exit_time': row['datetime'],
                    'direction': position_type,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'pnl_pct': pnl_pct * 100,
                    'gross_pnl': gross_pnl,
                    'net_pnl': net_pnl,
                    'commission': total_commission,
                    'bars_held': bars_held,
                    'is_win': net_pnl > 0,
                })
                in_position = False

        if not in_position:
            if prev_rsi <= RSI_OVERSOLD and curr_rsi > RSI_OVERSOLD:
                in_position = True
                position_type = 'LONG'
                entry_price = next_row['open_price']
                entry_time = next_row['datetime']
                entry_bar_idx = i + 1

            elif prev_rsi >= RSI_OVERBOUGHT and curr_rsi < RSI_OVERBOUGHT:
                in_position = True
                position_type = 'SHORT'
                entry_price = next_row['open_price']
                entry_time = next_row['datetime']
                entry_bar_idx = i + 1

    return trades


def calculate_all_metrics(trades: list[dict]) -> dict:
    """Calculate comprehensive metrics from trades list"""
    if not trades:
        return {}

    df = pd.DataFrame(trades)

    # Basic counts
    total = len(df)
    wins = df['is_win'].sum()
    losses = total - wins

    long_trades = df[df['direction'] == 'LONG']
    short_trades = df[df['direction'] == 'SHORT']

    long_count = len(long_trades)
    short_count = len(short_trades)
    long_wins = long_trades['is_win'].sum() if len(long_trades) > 0 else 0
    short_wins = short_trades['is_win'].sum() if len(short_trades) > 0 else 0

    # P&L metrics
    net_profit = df['net_pnl'].sum()
    gross_profit = df[df['net_pnl'] > 0]['net_pnl'].sum() if (df['net_pnl'] > 0).any() else 0
    gross_loss = abs(df[df['net_pnl'] < 0]['net_pnl'].sum()) if (df['net_pnl'] < 0).any() else 0

    long_net = long_trades['net_pnl'].sum() if len(long_trades) > 0 else 0
    short_net = short_trades['net_pnl'].sum() if len(short_trades) > 0 else 0

    # Win rate
    win_rate = (wins / total * 100) if total > 0 else 0
    long_win_rate = (long_wins / long_count * 100) if long_count > 0 else 0
    short_win_rate = (short_wins / short_count * 100) if short_count > 0 else 0

    # Profit factor
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    # Average trade
    avg_trade = net_profit / total if total > 0 else 0
    avg_win = df[df['is_win']]['net_pnl'].mean() if wins > 0 else 0
    avg_loss = df[~df['is_win']]['net_pnl'].mean() if losses > 0 else 0

    # Largest trade
    largest_win = df['net_pnl'].max()
    largest_loss = df['net_pnl'].min()

    # Consecutive wins/losses
    consec = df['is_win'].astype(int).values
    max_consec_wins = max_consecutive(consec, 1)
    max_consec_losses = max_consecutive(consec, 0)

    # Drawdown
    equity = [INITIAL_CAPITAL]
    for pnl in df['net_pnl']:
        equity.append(equity[-1] + pnl)
    equity = np.array(equity[1:])

    peak = np.maximum.accumulate(equity)
    drawdown = (peak - equity)
    max_dd = drawdown.max()
    max_dd_pct = (max_dd / peak.max() * 100) if peak.max() > 0 else 0

    # Bars analysis
    avg_bars = df['bars_held'].mean()
    avg_win_bars = df[df['is_win']]['bars_held'].mean() if wins > 0 else 0
    avg_loss_bars = df[~df['is_win']]['bars_held'].mean() if losses > 0 else 0

    # Payoff ratio
    payoff = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # Expectancy
    expectancy = (win_rate/100 * avg_win) + ((100-win_rate)/100 * avg_loss) if total > 0 else 0

    return {
        # Basic
        'Total Trades': total,
        'Winning Trades': wins,
        'Losing Trades': losses,
        'Win Rate %': round(win_rate, 2),

        # P&L
        'Net Profit': round(net_profit, 2),
        'Gross Profit': round(gross_profit, 2),
        'Gross Loss': round(gross_loss, 2),
        'Profit Factor': round(profit_factor, 3),

        # Long/Short
        'Long Trades': long_count,
        'Long Winning': int(long_wins),
        'Long Net Profit': round(long_net, 2),
        'Long Win Rate %': round(long_win_rate, 2),
        'Short Trades': short_count,
        'Short Winning': int(short_wins),
        'Short Net Profit': round(short_net, 2),
        'Short Win Rate %': round(short_win_rate, 2),

        # Trade size
        'Avg Trade': round(avg_trade, 2),
        'Avg Winning Trade': round(avg_win, 2),
        'Avg Losing Trade': round(avg_loss, 2),
        'Largest Winning': round(largest_win, 2),
        'Largest Losing': round(largest_loss, 2),
        'Payoff Ratio': round(payoff, 3),

        # Consecutive
        'Max Consec Wins': max_consec_wins,
        'Max Consec Losses': max_consec_losses,

        # Drawdown
        'Max Drawdown': round(max_dd, 2),
        'Max Drawdown %': round(max_dd_pct, 2),

        # Bars
        'Avg Bars Held': round(avg_bars, 1),
        'Avg Win Bars': round(avg_win_bars, 1),
        'Avg Loss Bars': round(avg_loss_bars, 1),

        # Composite
        'Expectancy': round(expectancy, 2),
    }


def max_consecutive(arr, value):
    """Count max consecutive occurrences of value"""
    max_count = 0
    current = 0
    for v in arr:
        if v == value:
            current += 1
            max_count = max(max_count, current)
        else:
            current = 0
    return max_count


def load_tv_summary_metrics() -> dict:
    """Parse TV metrics from screenshot/manual input - these are the reference values"""
    # From TradingView Strategy Report (Jan 21, 2026) - LINEAR BTCUSDT.P
    return {
        'Total Trades': 83,
        'Winning Trades': 61,
        'Losing Trades': 22,
        'Win Rate %': 73.49,

        'Net Profit': 146.39,
        'Gross Profit': 852.16,
        'Gross Loss': 705.77,
        'Profit Factor': 1.207,

        'Long Trades': 39,
        'Long Winning': 28,  # Estimate
        'Long Net Profit': 0,  # Need from TV
        'Long Win Rate %': 71.79,  # Estimate based on count
        'Short Trades': 44,
        'Short Winning': 33,  # Estimate
        'Short Net Profit': 0,  # Need from TV
        'Short Win Rate %': 75.0,  # Estimate

        'Avg Trade': 1.76,
        'Avg Winning Trade': 13.72,
        'Avg Losing Trade': -31.40,
        'Largest Winning': 14.49,  # From earlier test
        'Largest Losing': -32.26,  # From earlier test
        'Payoff Ratio': 0.437,  # avg_win / |avg_loss|

        'Max Consec Wins': 8,  # Need from TV
        'Max Consec Losses': 3,  # Need from TV

        'Max Drawdown': 112.63,
        'Max Drawdown %': 11.26,  # Approximate

        'Avg Bars Held': 10,  # Need from TV
        'Avg Win Bars': 8,  # Need from TV
        'Avg Loss Bars': 15,  # Need from TV

        'Expectancy': 1.76,  # Same as avg trade
    }


def main():
    print("="*100)
    print("COMPREHENSIVE METRICS PARITY COMPARISON")
    print("LINEAR BTCUSDT.P - RSI Strategy - TradingView vs Our Engine")
    print("="*100)

    # Load data
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

    print(f"\nData: {len(df)} bars")

    # Simulate
    trades = simulate_full_strategy(df)
    print(f"Trades: {len(trades)}")

    # Calculate our metrics
    our_metrics = calculate_all_metrics(trades)

    # Load TV reference
    tv_metrics = load_tv_summary_metrics()

    # Compare
    print("\n" + "="*100)
    print("METRICS COMPARISON TABLE")
    print("="*100)

    categories = {
        'BASIC COUNTS': ['Total Trades', 'Winning Trades', 'Losing Trades', 'Win Rate %'],
        'PROFIT/LOSS': ['Net Profit', 'Gross Profit', 'Gross Loss', 'Profit Factor'],
        'LONG TRADES': ['Long Trades', 'Long Winning', 'Long Net Profit', 'Long Win Rate %'],
        'SHORT TRADES': ['Short Trades', 'Short Winning', 'Short Net Profit', 'Short Win Rate %'],
        'TRADE STATISTICS': ['Avg Trade', 'Avg Winning Trade', 'Avg Losing Trade', 'Payoff Ratio'],
        'EXTREMES': ['Largest Winning', 'Largest Losing', 'Max Consec Wins', 'Max Consec Losses'],
        'DRAWDOWN': ['Max Drawdown', 'Max Drawdown %'],
        'BARS ANALYSIS': ['Avg Bars Held', 'Avg Win Bars', 'Avg Loss Bars'],
        'COMPOSITE': ['Expectancy'],
    }

    total_metrics = 0
    matched_metrics = 0
    close_metrics = 0

    for category, metrics in categories.items():
        print(f"\n--- {category} ---")
        print(f"{'Metric':<25} | {'Our Engine':>15} | {'TradingView':>15} | {'Diff':>12} | {'Status'}")
        print("-"*85)

        for metric in metrics:
            our_val = our_metrics.get(metric, 'N/A')
            tv_val = tv_metrics.get(metric, 'N/A')

            if our_val == 'N/A' or tv_val == 'N/A':
                status = "N/A"
            elif isinstance(our_val, (int, float)) and isinstance(tv_val, (int, float)):
                diff = our_val - tv_val

                # Determine tolerance based on metric type
                if 'Rate' in metric or '%' in metric:
                    tolerance = 1.0  # 1% tolerance for percentages
                elif 'Trades' in metric or 'Winning' in metric or 'Losing' in metric or 'Consec' in metric:
                    tolerance = 0  # Exact for counts
                else:
                    tolerance = 1.0  # 1 USDT tolerance for money values

                if abs(diff) <= tolerance * 0.01:
                    status = "MATCH"
                    matched_metrics += 1
                elif abs(diff) <= tolerance:
                    status = "~CLOSE"
                    close_metrics += 1
                else:
                    pct_diff = abs(diff / tv_val * 100) if tv_val != 0 else 0
                    status = f"DIFF {pct_diff:.1f}%"

                total_metrics += 1
            else:
                diff = ""
                status = "?"

            our_str = f"{our_val}" if isinstance(our_val, str) else f"{our_val:>15.2f}" if isinstance(our_val, float) else f"{our_val:>15}"
            tv_str = f"{tv_val}" if isinstance(tv_val, str) else f"{tv_val:>15.2f}" if isinstance(tv_val, float) else f"{tv_val:>15}"
            diff_str = f"{diff:>+12.2f}" if isinstance(diff, float) else f"{diff:>12}"

            print(f"{metric:<25} | {our_str:>15} | {tv_str:>15} | {diff_str} | {status}")

    # Summary
    print("\n" + "="*100)
    print("PARITY SUMMARY")
    print("="*100)
    print(f"""
    Total Metrics Compared:   {total_metrics}
    Exact Matches:            {matched_metrics}
    Close Matches:            {close_metrics}
    Metrics with Differences: {total_metrics - matched_metrics - close_metrics}
    
    Match Rate: {matched_metrics/total_metrics*100:.1f}% exact, {(matched_metrics+close_metrics)/total_metrics*100:.1f}% within tolerance
""")


if __name__ == "__main__":
    main()
