"""
Test Quick Reversals Fix: Compare trade counts between VectorBT and Fallback
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from datetime import datetime

from backend.backtesting.engine import get_engine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategies import RSIStrategy

def main():
    print("=" * 70)
    print("🧪 TESTING QUICK REVERSALS FIX")
    print("=" * 70)
    
    engine = get_engine()
    
    # Load test data
    import sqlite3
    conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
    df = pd.read_sql("""
        SELECT open_time, open_price as open, high_price as high, 
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '60'
        AND open_time >= 1735689600000
        AND open_time < 1737504000000
        ORDER BY open_time ASC
    """, conn)
    conn.close()
    
    if len(df) == 0:
        print("❌ No data found")
        return
    
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df.set_index('open_time', inplace=True)
    print(f"📊 Loaded {len(df)} 1H candles")
    
    # RSI parameters
    rsi_period = 14
    rsi_overbought = 70
    rsi_oversold = 30
    
    # Test configuration
    config = BacktestConfig(
        symbol="BTCUSDT",
        interval="60",
        strategy="rsi",
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 22),
        initial_capital=10000,
        stop_loss=0.03,  # 3%
        take_profit=0.06,  # 6%
        direction="both",
        strategy_params={
            "rsi_period": rsi_period,
            "rsi_overbought": rsi_overbought,
            "rsi_oversold": rsi_oversold,
        }
    )
    
    print(f"\n📋 Config: direction={config.direction}, SL={config.stop_loss*100}%, TP={config.take_profit*100}%")
    
    # Generate signals using strategy
    strategy = RSIStrategy(params={
        "period": rsi_period,
        "oversold": rsi_oversold,
        "overbought": rsi_overbought,
    })
    signals = strategy.generate_signals(df)
    
    print(f"📡 Generated signals: {signals.entries.sum()} entries, {signals.exits.sum()} exits")
    
    # Run VectorBT engine
    print("\n🚀 Running VectorBT engine...")
    try:
        vbt_result = engine._run_vectorbt(config, df, signals)
        vbt_trades = len(vbt_result.trades)
        print(f"   VectorBT trades: {vbt_trades}")
    except Exception as e:
        print(f"   ❌ VectorBT error: {e}")
        import traceback
        traceback.print_exc()
        vbt_trades = None
    
    # Run Fallback engine
    print("\n🔧 Running Fallback engine...")
    try:
        fb_result = engine._run_fallback(config, df, signals)
        fb_trades = len(fb_result.trades)
        print(f"   Fallback trades: {fb_trades}")
    except Exception as e:
        print(f"   ❌ Fallback error: {e}")
        import traceback
        traceback.print_exc()
        fb_trades = None
    
    # Compare
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    
    if vbt_trades is not None and fb_trades is not None:
        if fb_trades > 0:
            diff_pct = abs(vbt_trades - fb_trades) / fb_trades * 100
        else:
            diff_pct = 0 if vbt_trades == 0 else 100
        
        print(f"   VectorBT trades:  {vbt_trades}")
        print(f"   Fallback trades:  {fb_trades}")
        print(f"   Difference:       {abs(vbt_trades - fb_trades)} ({diff_pct:.1f}%)")
        
        if diff_pct < 20:
            print(f"\n✅ Trade count divergence acceptable ({diff_pct:.1f}%)")
        else:
            print(f"\n⚠️  Trade count divergence high ({diff_pct:.1f}%)")
        
        # Metrics comparison
        print("\n📈 METRICS COMPARISON:")
        print(f"   VectorBT Sharpe:  {vbt_result.metrics.sharpe_ratio:.3f}")
        print(f"   Fallback Sharpe:  {fb_result.metrics.sharpe_ratio:.3f}")
        print(f"   VectorBT Return:  {vbt_result.metrics.total_return:.2f}%")
        print(f"   Fallback Return:  {fb_result.metrics.total_return:.2f}%")

if __name__ == "__main__":
    main()
