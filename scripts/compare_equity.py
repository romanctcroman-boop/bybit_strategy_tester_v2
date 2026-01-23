"""
Compare Fallback and Numba equity curves directly
"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

import numpy as np
import pandas as pd
import sqlite3

# Load data
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

print(f"Loaded {len(df)} candles")

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

print(f"\n=== NUMBA ===")
print(f"Trades: {n_trades}")
print(f"Final equity: {equity_numba[-1]:.2f}")

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

# Extract equity from fallback
equity_fallback = np.array(result_fallback.equity_curve) if hasattr(result_fallback, 'equity_curve') else None

print(f"\n=== FALLBACK ===")
print(f"Trades: {len(result_fallback.trades)}")
print(f"Sharpe: {result_fallback.metrics.sharpe_ratio:.3f}")

# Calculate Sharpe from Numba equity
equity_fixed = equity_numba.copy()
equity_fixed[equity_fixed <= 0] = 10000.0

with np.errstate(divide='ignore', invalid='ignore'):
    returns_numba = np.diff(equity_fixed) / equity_fixed[:-1]
returns_numba = np.nan_to_num(returns_numba, nan=0.0, posinf=0.0, neginf=0.0)

mean_ret = np.mean(returns_numba)
std_ret = np.std(returns_numba, ddof=1)
periods_per_year = 8760
risk_free_rate = 0.02
period_rfr = risk_free_rate / periods_per_year

sharpe_numba = (mean_ret - period_rfr) / std_ret * np.sqrt(periods_per_year) if std_ret > 1e-10 else 0

print(f"\n=== SHARPE COMPARISON ===")
print(f"Fallback Sharpe: {result_fallback.metrics.sharpe_ratio:.3f}")
print(f"Numba Sharpe:    {sharpe_numba:.3f}")
print(f"Difference:      {abs(result_fallback.metrics.sharpe_ratio - sharpe_numba):.3f}")

# Check equity curves
if result_fallback.equity_curve is not None:
    print(f"\n=== EQUITY CURVES ===")
    equity_fallback = np.array(result_fallback.equity_curve.equity)
    print(f"Fallback length: {len(equity_fallback)}")
    print(f"Numba length:    {len(equity_numba)}")
    print(f"Fallback final equity: {equity_fallback[-1]:.2f}")
    print(f"Numba final equity:    {equity_numba[-1]:.2f}")
    
    # Compare
    min_len = min(len(equity_fallback), len(equity_numba))
    diff = np.abs(equity_fallback[:min_len] - equity_numba[:min_len])
    print(f"Max equity diff: {np.max(diff):.2f}")
    print(f"Mean equity diff: {np.mean(diff):.2f}")
    
    # Now calculate Sharpe using Fallback equity curve
    print(f"\n=== SHARPE USING FALLBACK EQUITY ===")
    with np.errstate(divide='ignore', invalid='ignore'):
        returns_fb = np.diff(equity_fallback) / equity_fallback[:-1]
    returns_fb = np.nan_to_num(returns_fb, nan=0.0, posinf=0.0, neginf=0.0)
    
    mean_ret_fb = np.mean(returns_fb)
    std_ret_fb = np.std(returns_fb, ddof=1)
    
    sharpe_recalc = (mean_ret_fb - period_rfr) / std_ret_fb * np.sqrt(periods_per_year) if std_ret_fb > 1e-10 else 0
    print(f"Recalculated from Fallback equity: {sharpe_recalc:.3f}")
    print(f"Fallback reported Sharpe:          {result_fallback.metrics.sharpe_ratio:.3f}")
else:
    print("\nFallback equity curve not available directly")
