"""
Trace what happens on bar 499 in actual Fallback engine
"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

# Monkey-patch to add debug
import backend.backtesting.engine as engine_module

original_run_fallback = engine_module.BacktestEngine._run_fallback

def debug_run_fallback(self, config, ohlcv, signals):
    # Run original but with debug on entries
    import numpy as np
    
    close = ohlcv['close'].values if hasattr(ohlcv['close'], 'values') else ohlcv['close']
    
    long_entries = signals.entries
    short_entries = signals.short_entries
    
    direction = config.direction
    position = 0.0
    
    # Just check bars 498-503
    for i in [498, 499, 500, 501]:
        le = long_entries.iloc[i] if hasattr(long_entries, 'iloc') else long_entries[i]
        se = short_entries.iloc[i] if hasattr(short_entries, 'iloc') else short_entries[i]
        print(f"Bar {i}: position={position}, long_entry={le}, short_entry={se}")
        
        if position == 0:
            if direction in ("long", "both") and le:
                print(f"  -> Would enter LONG")
                position = 1.0
            elif direction in ("short", "both") and se:
                print(f"  -> Would enter SHORT")
                position = 1.0
    
    # Call original
    return original_run_fallback(self, config, ohlcv, signals)

engine_module.BacktestEngine._run_fallback = debug_run_fallback

# Now run
import numpy as np
import pandas as pd
import sqlite3

conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
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

df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)

from backend.backtesting.strategies import RSIStrategy
from backend.backtesting.engine import get_engine
from backend.backtesting.models import BacktestConfig

strategy = RSIStrategy(params={"period": 14, "overbought": 70, "oversold": 30})
signals = strategy.generate_signals(df)

engine = get_engine()
config = BacktestConfig(
    symbol="BTCUSDT", interval="60", start_date="2025-01-01", end_date="2025-01-22",
    initial_capital=10000.0, leverage=1, taker_fee=0.0004, slippage=0.0001,
    stop_loss=0.03, take_profit=0.06, direction="both",
    strategy_type="rsi", strategy_params={"period": 14, "overbought": 70, "oversold": 30},
    use_bar_magnifier=False,
)

print("Debug trace bars 498-501:")
result = engine._run_fallback(config, df, signals)
print(f"\nActual trades: {len(result.trades)}")
