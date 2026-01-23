"""
🎯 LINEAR PARITY TEST - BTCUSDT.P Perpetual Futures
====================================================

TV Reference (BTCUSDT.P):
- Total Trades: 83
- Net Profit: +146.39 USDT
- Win Rate: 73.49%
- Profit Factor: 1.212
- Max Drawdown: 112.63 USDT
- Long: 39, Short: 44
"""
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
import pandas as pd
import numpy as np
from datetime import timedelta

DB_PATH = project_root / "data.sqlite3"

# ===================== TV REFERENCE METRICS (LINEAR) =====================
TV_METRICS = {
    'total_trades': 83,
    'net_profit': 146.39,
    'win_rate': 73.49,
    'profit_factor': 1.212,
    'max_drawdown': 112.63,
    'long_trades': 39,
    'short_trades': 44,
    'winning_trades': 61,
    'losing_trades': 22,
    'avg_profit': 13.72,
    'avg_loss': 31.40,
}

# ===================== STRATEGY PARAMS =====================
RSI_PERIOD = 14
RSI_OVERSOLD = 25
RSI_OVERBOUGHT = 70
TP_PCT = 0.015  # 1.5%
SL_PCT = 0.03   # 3%
BASE_QTY = 100  # USDT
LEVERAGE = 10
FEE = 0.0007  # 0.07% taker


def calculate_rsi_wilder(close, period=14):
    """Wilder's RSI (exact TradingView match)"""
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
    """Full strategy simulation with position tracking"""
    df = df.copy()
    df['rsi'] = calculate_rsi_wilder(df['close_price'], RSI_PERIOD)
    df['prev_rsi'] = df['rsi'].shift(1)
    
    trades = []
    equity_curve = [0]
    
    in_position = False
    position_type = None
    entry_price = 0
    entry_time = None
    entry_bar = 0
    
    for i in range(1, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        prev_rsi = row['prev_rsi']
        curr_rsi = row['rsi']
        
        if pd.isna(prev_rsi) or pd.isna(curr_rsi):
            continue
        
        # Check exit
        if in_position:
            high = row['high_price']
            low = row['low_price']
            open_price = row['open_price']
            
            if position_type == 'LONG':
                tp_price = entry_price * (1 + TP_PCT)
                sl_price = entry_price * (1 - SL_PCT)
                
                exit_price = None
                exit_reason = None
                
                open_to_high = abs(open_price - high)
                open_to_low = abs(open_price - low)
                
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
                
                if exit_price:
                    pnl_pct = (exit_price - entry_price) / entry_price
                    gross_pnl = BASE_QTY * LEVERAGE * pnl_pct
                    fees = BASE_QTY * LEVERAGE * FEE * 2
                    net_pnl = gross_pnl - fees
                    
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': row['datetime'],
                        'direction': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'pnl': net_pnl,
                        'bars': i - entry_bar
                    })
                    equity_curve.append(equity_curve[-1] + net_pnl)
                    in_position = False
                    
            elif position_type == 'SHORT':
                tp_price = entry_price * (1 - TP_PCT)
                sl_price = entry_price * (1 + SL_PCT)
                
                exit_price = None
                exit_reason = None
                
                open_to_high = abs(open_price - high)
                open_to_low = abs(open_price - low)
                
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
                
                if exit_price:
                    pnl_pct = (entry_price - exit_price) / entry_price
                    gross_pnl = BASE_QTY * LEVERAGE * pnl_pct
                    fees = BASE_QTY * LEVERAGE * FEE * 2
                    net_pnl = gross_pnl - fees
                    
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': row['datetime'],
                        'direction': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'pnl': net_pnl,
                        'bars': i - entry_bar
                    })
                    equity_curve.append(equity_curve[-1] + net_pnl)
                    in_position = False
        
        # Check entry
        if not in_position:
            if prev_rsi <= RSI_OVERSOLD and curr_rsi > RSI_OVERSOLD:
                in_position = True
                position_type = 'LONG'
                entry_price = next_row['open_price']
                entry_time = next_row['datetime']
                entry_bar = i + 1
                
            elif prev_rsi >= RSI_OVERBOUGHT and curr_rsi < RSI_OVERBOUGHT:
                in_position = True
                position_type = 'SHORT'
                entry_price = next_row['open_price']
                entry_time = next_row['datetime']
                entry_bar = i + 1
    
    return trades, equity_curve


def calculate_metrics(trades, equity_curve):
    if not trades:
        return {}
    
    df = pd.DataFrame(trades)
    
    total = len(df)
    wins = df[df['pnl'] > 0]
    losses = df[df['pnl'] <= 0]
    
    longs = df[df['direction'] == 'LONG']
    shorts = df[df['direction'] == 'SHORT']
    
    gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 1
    
    peak = 0
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    
    return {
        'total_trades': total,
        'net_profit': df['pnl'].sum(),
        'win_rate': len(wins) / total * 100 if total > 0 else 0,
        'profit_factor': gross_profit / gross_loss if gross_loss > 0 else 0,
        'max_drawdown': max_dd,
        'long_trades': len(longs),
        'short_trades': len(shorts),
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'avg_profit': wins['pnl'].mean() if len(wins) > 0 else 0,
        'avg_loss': abs(losses['pnl'].mean()) if len(losses) > 0 else 0,
    }


def compare_with_tv(our_metrics, tv_metrics):
    print("\n" + "="*80)
    print("📊 PARITY COMPARISON: Our Engine vs TradingView (LINEAR)")
    print("="*80)
    
    comparisons = [
        ('Total Trades', 'total_trades', '', 0),
        ('Net Profit', 'net_profit', 'USDT', 2),
        ('Win Rate', 'win_rate', '%', 2),
        ('Profit Factor', 'profit_factor', '', 3),
        ('Max Drawdown', 'max_drawdown', 'USDT', 2),
        ('Long Trades', 'long_trades', '', 0),
        ('Short Trades', 'short_trades', '', 0),
        ('Winning Trades', 'winning_trades', '', 0),
        ('Losing Trades', 'losing_trades', '', 0),
        ('Avg Profit', 'avg_profit', 'USDT', 2),
        ('Avg Loss', 'avg_loss', 'USDT', 2),
    ]
    
    print(f"\n{'Metric':<20} | {'Our Engine':>15} | {'TradingView':>15} | {'Diff':>12} | {'Parity'}")
    print("-"*85)
    
    total_match = 0
    total_metrics = 0
    
    for name, key, unit, decimals in comparisons:
        our = our_metrics.get(key, 0)
        tv = tv_metrics.get(key, 0)
        
        if decimals == 0:
            diff = int(our - tv)
            diff_str = f"{diff:+d}"
            our_str = f"{int(our)}"
            tv_str = f"{int(tv)}"
        else:
            diff = our - tv
            diff_str = f"{diff:+.{decimals}f}"
            our_str = f"{our:.{decimals}f}"
            tv_str = f"{tv:.{decimals}f}"
        
        if tv != 0:
            parity_pct = (1 - abs(diff) / abs(tv)) * 100
        else:
            parity_pct = 100 if our == 0 else 0
        
        parity_pct = max(0, min(100, parity_pct))
        
        if parity_pct >= 99:
            status = "✅ 100%"
            total_match += 1
        elif parity_pct >= 95:
            status = f"⚠️ {parity_pct:.1f}%"
            total_match += 0.5
        else:
            status = f"❌ {parity_pct:.1f}%"
        
        total_metrics += 1
        
        print(f"{name:<20} | {our_str:>12} {unit:<3} | {tv_str:>12} {unit:<3} | {diff_str:>12} | {status}")
    
    overall_parity = (total_match / total_metrics) * 100
    print("-"*85)
    print(f"{'OVERALL PARITY':<20} | {' '*31} | {' '*12} | {overall_parity:.1f}%")
    
    return overall_parity


def main():
    print("="*80)
    print("🎯 LINEAR PARITY TEST - BTCUSDT.P Perpetual 15m")
    print("    TradingView Reference: Jan 21, 2026")
    print("="*80)
    
    # Load LINEAR data
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear'
        ORDER BY open_time ASC
    """, conn)
    conn.close()
    
    if df.empty:
        print("\n⚠️ No LINEAR data found with market_type='linear'")
        print("   Trying without market_type filter...")
        
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT open_time, open_price, high_price, low_price, close_price, volume
            FROM bybit_kline_audit 
            WHERE symbol='BTCUSDT' AND interval='15'
            ORDER BY open_time ASC
        """, conn)
        conn.close()
    
    if df.empty:
        print("❌ No BTCUSDT 15m data found!")
        return
    
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
    
    # Filter to match TV date range: Oct 1, 2025 - Jan 21, 2026
    start_date = '2025-10-01'
    end_date = '2026-01-21 23:59:59'
    df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)].copy()
    df = df.reset_index(drop=True)
    
    print(f"\n📊 LINEAR Data: {len(df)} bars")
    print(f"   Range: {df['datetime'].min()} to {df['datetime'].max()}")
    
    print(f"\n⚙️ Strategy Parameters:")
    print(f"   RSI Period:   {RSI_PERIOD}")
    print(f"   Oversold:     {RSI_OVERSOLD}")
    print(f"   Overbought:   {RSI_OVERBOUGHT}")
    print(f"   Take Profit:  {TP_PCT*100}%")
    print(f"   Stop Loss:    {SL_PCT*100}%")
    print(f"   Base Qty:     {BASE_QTY} USDT")
    print(f"   Leverage:     {LEVERAGE}x")
    
    # Run simulation
    print("\n🔄 Running simulation...")
    trades, equity_curve = simulate_strategy(df)
    
    # Calculate metrics
    our_metrics = calculate_metrics(trades, equity_curve)
    
    print(f"\n📊 Our Results:")
    print(f"   Total Trades: {our_metrics['total_trades']}")
    print(f"   Net Profit:   ${our_metrics['net_profit']:.2f}")
    print(f"   Win Rate:     {our_metrics['win_rate']:.2f}%")
    print(f"   Profit Factor: {our_metrics['profit_factor']:.3f}")
    
    # Compare with TV
    overall_parity = compare_with_tv(our_metrics, TV_METRICS)
    
    # Final verdict
    print("\n" + "="*80)
    print("🏁 FINAL LINEAR PARITY VERDICT")
    print("="*80)
    print(f"""
   📊 Trade Count:    {our_metrics['total_trades']}/{TV_METRICS['total_trades']} ({our_metrics['total_trades']/TV_METRICS['total_trades']*100:.1f}%)
   💰 Net Profit:     ${our_metrics['net_profit']:.2f} vs ${TV_METRICS['net_profit']:.2f}
   📈 Win Rate:       {our_metrics['win_rate']:.1f}% vs {TV_METRICS['win_rate']:.1f}%
   📉 Max Drawdown:   ${our_metrics['max_drawdown']:.2f} vs ${TV_METRICS['max_drawdown']:.2f}
   
   🎯 Overall Parity: {overall_parity:.1f}%
""")


if __name__ == "__main__":
    main()
