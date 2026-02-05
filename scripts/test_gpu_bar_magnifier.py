"""
GPU Engine V2 - Bar Magnifier Parity Test

Verifies GPUEngineV2 with Bar Magnifier produces 100% identical results 
to FallbackEngineV2 (reference).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

import pandas as pd

print("=" * 100)
print("GPU ENGINE V2 - BAR MAGNIFIER PARITY TEST")
print("=" * 100)

# Load 60m data
print("\nLoading 60m data...")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))

df_60m = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
    LIMIT 500
""", conn)
df_60m['open_time'] = pd.to_datetime(df_60m['open_time'], unit='ms')
df_60m.set_index('open_time', inplace=True)

# Load 1m data for Bar Magnifier
print("Loading 1m data...")
start_ts = int(df_60m.index[0].timestamp() * 1000)
end_ts = int(df_60m.index[-1].timestamp() * 1000) + 60 * 60 * 1000

df_1m = pd.read_sql(f"""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '1'
      AND open_time >= {start_ts} AND open_time <= {end_ts}
    ORDER BY open_time ASC
""", conn)
df_1m['open_time'] = pd.to_datetime(df_1m['open_time'], unit='ms')
df_1m.set_index('open_time', inplace=True)
conn.close()

print(f"   60m bars: {len(df_60m)}")
print(f"   1m bars: {len(df_1m)}")

# RSI signals
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(df_60m['close'], period=14)
le = (rsi < 30).values
lx = (rsi > 70).values
se = (rsi > 70).values
sx = (rsi < 30).values

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

input_data = BacktestInput(
    candles=df_60m,
    candles_1m=df_1m,  # Bar Magnifier data
    long_entries=le,
    long_exits=lx,
    short_entries=se,
    short_exits=sx,
    symbol='BTCUSDT',
    interval='60',
    initial_capital=10000.0,
    position_size=0.10,
    leverage=10,
    stop_loss=0.02,
    take_profit=0.04,
    direction=TradeDirection.BOTH,
    taker_fee=0.001,
    slippage=0.0005,
    use_bar_magnifier=True,  # ENABLED
)

# Run tests
print("\n" + "=" * 80)
print("Running FallbackEngineV2 with Bar Magnifier...")
fb = FallbackEngineV2()
fb_result = fb.run(input_data)

print("Running GPUEngineV2 with Bar Magnifier...")
gpu = GPUEngineV2()
gpu_result = gpu.run(input_data)

# Compare
print("\n" + "=" * 80)
print("RESULTS COMPARISON (Bar Magnifier ON)")
print("=" * 80)

def compare(name, fb_val, gpu_val, tolerance=0.01):
    match = abs(fb_val - gpu_val) < tolerance
    status = "OK" if match else "FAIL"
    diff = gpu_val - fb_val
    print(f"   {name:20s}: FB={fb_val:12.4f}  GPU={gpu_val:12.4f}  Diff={diff:+.4f}  {status}")
    return match

all_match = True

print("\nCore Metrics:")
trades_match = len(fb_result.trades) == len(gpu_result.trades)
print(f"   {'Trades':20s}: FB={len(fb_result.trades):12d}  GPU={len(gpu_result.trades):12d}  {'OK' if trades_match else 'FAIL'}")
all_match &= trades_match

all_match &= compare("Net Profit", fb_result.metrics.net_profit, gpu_result.metrics.net_profit)
all_match &= compare("Total Return", fb_result.metrics.total_return, gpu_result.metrics.total_return)
all_match &= compare("Win Rate", fb_result.metrics.win_rate, gpu_result.metrics.win_rate)
all_match &= compare("Sharpe Ratio", fb_result.metrics.sharpe_ratio, gpu_result.metrics.sharpe_ratio)
all_match &= compare("Max Drawdown", fb_result.metrics.max_drawdown, gpu_result.metrics.max_drawdown)

print("\nTrade Details (First 5):")
for i in range(min(5, len(fb_result.trades))):
    fb_t = fb_result.trades[i]
    gpu_t = gpu_result.trades[i]

    pnl_match = abs(fb_t.pnl - gpu_t.pnl) < 0.01
    reason_match = fb_t.exit_reason == gpu_t.exit_reason

    status = "OK" if (pnl_match and reason_match) else "FAIL"
    print(f"   Trade {i+1}: {fb_t.direction:5s} PnL=${fb_t.pnl:8.2f} vs ${gpu_t.pnl:8.2f}  Exit={fb_t.exit_reason.name} vs {gpu_t.exit_reason.name}  {status}")

    all_match &= pnl_match and reason_match

# Verdict
print("\n" + "=" * 80)
if all_match:
    print("  100% PARITY ACHIEVED: GPUEngineV2 + Bar Magnifier = FallbackEngineV2")
else:
    print("  PARITY FAILED: Check differences above")

print(f"   Execution time - FB: {fb_result.execution_time:.3f}s, GPU: {gpu_result.execution_time:.3f}s")
print(f"   GPU Enabled: {gpu.gpu_enabled}")
print(f"   Supports Bar Magnifier: {gpu.supports_bar_magnifier}")
print("=" * 80)
