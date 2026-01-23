"""
🔬 Full FallbackEngineV2 Test + RSI Boundary Analysis
======================================================
1. Run FallbackEngineV2 with SPOT BTCUSDT data
2. Compare trades with TradingView
3. Find exact RSI boundary divergence
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
import pandas as pd
import numpy as np
from datetime import timedelta

# Import engine
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.interfaces import BacktestInput

DB_PATH = project_root / "data.sqlite3"
TV_CSV = Path(r"d:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT_2026-01-21 (1).csv")


def load_spot_ohlcv():
    """Load SPOT OHLCV data."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit 
        WHERE symbol='BTCUSDT' AND interval='15' AND market_type='spot'
        ORDER BY open_time ASC
    """, conn)
    conn.close()
    
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
    return df


def load_tv_trades():
    """Load TradingView entries."""
    df = pd.read_csv(TV_CSV)
    entries = df[df['Type'].str.contains('Entry', na=False)].copy().reset_index(drop=True)
    entries['datetime'] = pd.to_datetime(entries['Date and time']) - timedelta(hours=3)  # MSK→UTC
    entries['direction'] = entries['Type'].apply(lambda x: 'long' if 'long' in x.lower() else 'short')
    entries['price'] = entries['Price USDT']
    
    # Get exit info
    exits = df[df['Type'].str.contains('Exit', na=False)].copy()
    exits['pnl'] = exits['Net P&L USDT']
    
    return entries, exits


def run_engine_backtest(df):
    """Run FallbackEngineV2 backtest."""
    print("\n" + "="*80)
    print("🚀 RUNNING FallbackEngineV2")
    print("="*80)
    
    # Prepare candles DataFrame (engine expects specific column names)
    candles = df[['datetime', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']].copy()
    candles.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
    candles['timestamp'] = df['open_time'].values
    
    # Generate RSI signals
    close = candles['close'].values
    
    # Calculate RSI
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    
    period = 14
    avg_gain = np.zeros(len(close))
    avg_loss = np.zeros(len(close))
    
    # Initial SMA
    avg_gain[period-1] = np.mean(gain[:period])
    avg_loss[period-1] = np.mean(loss[:period])
    
    # Wilder's smoothing
    for i in range(period, len(close)):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gain[i]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + loss[i]) / period
    
    rs = np.divide(avg_gain, avg_loss, where=avg_loss != 0, out=np.zeros_like(avg_gain))
    rsi = 100 - (100 / (1 + rs))
    
    # Generate signals
    OVERSOLD = 30
    OVERBOUGHT = 70
    
    long_entries = np.zeros(len(close), dtype=bool)
    short_entries = np.zeros(len(close), dtype=bool)
    long_exits = np.zeros(len(close), dtype=bool)
    short_exits = np.zeros(len(close), dtype=bool)
    
    for i in range(1, len(close)):
        # Long: RSI crosses above oversold
        if rsi[i-1] <= OVERSOLD and rsi[i] > OVERSOLD:
            long_entries[i] = True
        # Short: RSI crosses below overbought
        if rsi[i-1] >= OVERBOUGHT and rsi[i] < OVERBOUGHT:
            short_entries[i] = True
    
    # Create input
    from backend.backtesting.interfaces import TradeDirection
    
    bt_input = BacktestInput(
        candles=candles,
        candles_1m=None,
        long_entries=long_entries,
        short_entries=short_entries,
        long_exits=long_exits,
        short_exits=short_exits,
        symbol="BTCUSDT",
        interval="15",
        initial_capital=10000.0,
        position_size=0.01,
        use_fixed_amount=True,
        fixed_amount=100.0,
        leverage=10,
        stop_loss=0.03,
        take_profit=0.015,
        direction=TradeDirection.BOTH,
        taker_fee=0.0007,
        slippage=0.0,
        use_bar_magnifier=False,
    )
    
    # Run engine
    engine = FallbackEngineV2()
    output = engine.run(bt_input)
    
    print(f"\n📊 Engine Results:")
    print(f"   Total Trades: {output.metrics.total_trades}")
    print(f"   Net Profit:   ${output.metrics.net_profit:.2f}")
    print(f"   Win Rate:     {output.metrics.win_rate:.1f}%")
    print(f"   Long Trades:  {output.metrics.long_trades}")
    print(f"   Short Trades: {output.metrics.short_trades}")
    
    return output


def compare_trades(engine_output, tv_entries):
    """Compare engine trades with TV trades."""
    print("\n" + "="*80)
    print("📋 TRADE-BY-TRADE COMPARISON (First 30)")
    print("="*80)
    
    trades = engine_output.trades
    
    print(f"\nEngine trades: {len(trades)}")
    print(f"TV trades:     {len(tv_entries)}")
    
    print(f"\n{'#':>3} | {'Engine Time':>19} | {'Eng Dir':>6} | {'Eng Price':>10} | {'TV Time':>19} | {'TV Dir':>6} | {'TV Price':>10} | {'Match'}")
    print("-"*120)
    
    matches = 0
    first_div = None
    
    for i in range(min(30, max(len(trades), len(tv_entries)))):
        eng_str = ""
        tv_str = ""
        match = False
        
        if i < len(trades):
            t = trades[i]
            eng_time = pd.Timestamp(t.entry_time, unit='ms')
            eng_dir = t.direction.name if hasattr(t.direction, 'name') else str(t.direction)
            eng_price = t.entry_price
            eng_str = f"{str(eng_time)[:19]:>19} | {eng_dir:>6} | ${eng_price:>9.2f}"
        else:
            eng_str = f"{'N/A':>19} | {'N/A':>6} | {'N/A':>10}"
        
        if i < len(tv_entries):
            tv = tv_entries.iloc[i]
            tv_time = tv['datetime']
            tv_dir = tv['direction'].upper()
            tv_price = tv['price']
            tv_str = f"{str(tv_time)[:19]:>19} | {tv_dir:>6} | ${tv_price:>9.2f}"
            
            # Check match
            if i < len(trades):
                t = trades[i]
                eng_time = pd.Timestamp(t.entry_time, unit='ms')
                eng_dir = t.direction.name if hasattr(t.direction, 'name') else str(t.direction)
                
                time_diff = abs((eng_time - tv_time).total_seconds() / 60)
                price_diff = abs(t.entry_price - tv_price)
                dir_match = eng_dir.upper() == tv_dir.upper()
                
                match = time_diff <= 60 and price_diff < 50 and dir_match
        else:
            tv_str = f"{'N/A':>19} | {'N/A':>6} | {'N/A':>10}"
        
        if match:
            matches += 1
            match_str = "✅"
        else:
            match_str = "❌"
            if first_div is None:
                first_div = i + 1
        
        print(f"{i+1:>3} | {eng_str} | {tv_str} | {match_str}")
    
    print(f"\n📊 Matches: {matches}/{min(30, len(tv_entries))}")
    if first_div:
        print(f"🔴 First divergence at trade #{first_div}")
    
    return trades, first_div


def find_rsi_boundary_divergence(df, trades, tv_entries):
    """Find where RSI at boundary causes divergence."""
    print("\n" + "="*80)
    print("🔬 RSI BOUNDARY ANALYSIS")
    print("="*80)
    
    # Calculate RSI
    close = df['close_price']
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    period = 14
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    for i in range(period, len(close)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df['rsi'] = rsi
    
    # Find boundary cases
    OVERSOLD = 30
    OVERBOUGHT = 70
    
    print("\n🔍 Bars where RSI is VERY close to threshold:")
    print("-"*80)
    
    boundary_cases = []
    for i in range(1, len(df)):
        curr_rsi = df['rsi'].iloc[i]
        prev_rsi = df['rsi'].iloc[i-1]
        
        # Check if very close to threshold
        if (29.9 <= curr_rsi <= 30.1) or (69.9 <= curr_rsi <= 70.1):
            boundary_cases.append({
                'idx': i,
                'datetime': df['datetime'].iloc[i],
                'curr_rsi': curr_rsi,
                'prev_rsi': prev_rsi,
                'close': df['close_price'].iloc[i],
                'threshold': 30 if curr_rsi < 50 else 70
            })
    
    print(f"Total boundary cases: {len(boundary_cases)}")
    print("\nFirst 20 boundary cases:")
    for bc in boundary_cases[:20]:
        cross_type = ""
        if bc['prev_rsi'] <= bc['threshold'] and bc['curr_rsi'] > bc['threshold']:
            cross_type = "↗️ CROSS UP"
        elif bc['prev_rsi'] >= bc['threshold'] and bc['curr_rsi'] < bc['threshold']:
            cross_type = "↘️ CROSS DOWN"
        elif bc['prev_rsi'] < bc['threshold'] and bc['curr_rsi'] < bc['threshold']:
            cross_type = "→ still below"
        else:
            cross_type = "→ still above"
        
        distance = abs(bc['curr_rsi'] - bc['threshold'])
        print(f"  {bc['datetime']} | RSI: {bc['prev_rsi']:.4f} → {bc['curr_rsi']:.4f} | Δ from {bc['threshold']}: {distance:.4f} | {cross_type}")
    
    # Find the critical one - around first divergence
    print("\n" + "="*80)
    print("🎯 CRITICAL BOUNDARY (around divergence point)")
    print("="*80)
    
    # Get first few trade times
    if len(trades) >= 2:
        t1_time = pd.Timestamp(trades[0].entry_time, unit='ms')
        t2_time = pd.Timestamp(trades[1].entry_time, unit='ms')
        
        # Find bars between these times
        mask = (df['datetime'] >= t1_time) & (df['datetime'] <= t2_time + timedelta(hours=1))
        region = df[mask]
        
        print(f"\nBars between Trade #1 ({t1_time}) and Trade #2 ({t2_time}):")
        print("-"*80)
        
        for _, row in region.iterrows():
            curr_rsi = row['rsi']
            is_boundary = (29.9 <= curr_rsi <= 30.1) or (69.9 <= curr_rsi <= 70.1)
            marker = " 🔴 BOUNDARY!" if is_boundary else ""
            print(f"  {row['datetime']} | RSI: {curr_rsi:.4f} | Close: ${row['close_price']:.2f}{marker}")


def main():
    print("="*80)
    print("🔬 FULL ENGINE TEST + RSI BOUNDARY ANALYSIS")
    print("="*80)
    
    # Load data
    df = load_spot_ohlcv()
    tv_entries, tv_exits = load_tv_trades()
    
    print(f"\n📊 Data loaded:")
    print(f"   SPOT bars:  {len(df)}")
    print(f"   TV trades:  {len(tv_entries)}")
    print(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    
    # Run engine
    output = run_engine_backtest(df)
    
    # Compare trades
    trades, first_div = compare_trades(output, tv_entries)
    
    # Find RSI boundary
    find_rsi_boundary_divergence(df, trades, tv_entries)
    
    print("\n" + "="*80)
    print("🏁 ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
