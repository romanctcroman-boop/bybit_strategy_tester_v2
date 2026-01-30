"""
Deep compare individual trades between Fallback and Numba
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import sqlite3

# Load data
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

df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)

# ============ NUMBA ============
from backend.backtesting.strategies import RSIStrategy
from backend.backtesting.numba_engine import simulate_trades_numba

strategy = RSIStrategy(params={"period": 14, "overbought": 70, "oversold": 30})
signals = strategy.generate_signals(df)

close = df['close'].values.astype(np.float64)
high = df['high'].values.astype(np.float64)
low = df['low'].values.astype(np.float64)

long_entries = signals.entries.values.astype(np.bool_)
long_exits = signals.exits.values.astype(np.bool_)
short_entries = signals.short_entries.values.astype(np.bool_)
short_exits = signals.short_exits.values.astype(np.bool_)

trades_numba, equity_numba, _, n_trades = simulate_trades_numba(
    close, high, low,
    long_entries, long_exits,
    short_entries, short_exits,
    10000.0, 1.0, 0.0004, 0.0001,
    0.03, 0.06, 1.0, 2
)

# ============ FALLBACK ============
from backend.backtesting.engine import get_engine
from backend.backtesting.models import BacktestConfig

engine = get_engine()

config = BacktestConfig(
    symbol="BTCUSDT",
    interval="60",
    start_date="2025-01-01",
    end_date="2025-01-22",
    initial_capital=10000.0,
    leverage=1,
    taker_fee=0.0004,
    slippage=0.0001,
    stop_loss=0.03,
    take_profit=0.06,
    direction="both",
    strategy_type="rsi",
    strategy_params={"period": 14, "overbought": 70, "oversold": 30},
    use_bar_magnifier=False,
)

result_fallback = engine._run_fallback(config, df, signals)

# Compare trades
print("=" * 80)
print("TRADE BY TRADE COMPARISON")
print("=" * 80)

print(f"\nFallback: {len(result_fallback.trades)} trades")
print(f"Numba:    {n_trades} trades")

total_pnl_fb = 0
total_pnl_numba = 0

for i in range(min(len(result_fallback.trades), n_trades)):
    fb_trade = result_fallback.trades[i]
    numba_trade = trades_numba[i]
    
    fb_pnl = fb_trade.pnl
    numba_pnl = numba_trade[5]  # pnl column
    
    fb_entry = fb_trade.entry_price
    fb_exit = fb_trade.exit_price
    
    numba_entry = numba_trade[3]
    numba_exit = numba_trade[4]
    
    fb_is_long = fb_trade.side == 'buy'
    numba_is_long = numba_trade[2] == 1.0
    
    total_pnl_fb += fb_pnl
    total_pnl_numba += numba_pnl
    
    pnl_diff = abs(fb_pnl - numba_pnl)
    
    status = "✅" if pnl_diff < 1.0 else "⚠️" if pnl_diff < 10.0 else "❌"
    
    print(f"\n{status} Trade {i+1}:")
    print(f"   Type:      FB={('LONG' if fb_is_long else 'SHORT'):5} | NUMBA={('LONG' if numba_is_long else 'SHORT'):5}")
    print(f"   Entry:     FB={fb_entry:10.2f} | NUMBA={numba_entry:10.2f} | diff={abs(fb_entry-numba_entry):.4f}")
    print(f"   Exit:      FB={fb_exit:10.2f} | NUMBA={numba_exit:10.2f} | diff={abs(fb_exit-numba_exit):.4f}")
    print(f"   PnL:       FB={fb_pnl:10.2f} | NUMBA={numba_pnl:10.2f} | diff={pnl_diff:.2f}")

print("\n" + "=" * 80)
print(f"TOTAL PnL: FB={total_pnl_fb:.2f} | NUMBA={total_pnl_numba:.2f} | diff={abs(total_pnl_fb-total_pnl_numba):.2f}")
print("=" * 80)
