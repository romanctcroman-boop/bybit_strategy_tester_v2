"""
🔬 GPU Engine V2 Parity Test

Verifies 100% parity between GPUEngineV2 and FallbackEngineV2 (reference).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

import pandas as pd

print("=" * 100)
print("🔬 GPU ENGINE V2 PARITY TEST")
print("=" * 100)

# ============================================================================
# LOAD DATA
# ============================================================================
print("\n📊 Loading data...")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))

df = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
    LIMIT 500
""", conn)
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)
conn.close()

print(f"   Bars: {len(df)}")

# ============================================================================
# RSI SIGNALS
# ============================================================================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(df['close'], period=14)
le = (rsi < 30).values
lx = (rsi > 70).values
se = (rsi > 70).values
sx = (rsi < 30).values

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

input_data = BacktestInput(
    candles=df,
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
    use_bar_magnifier=False,
)

# ============================================================================
# RUN TESTS
# ============================================================================
print("\n" + "=" * 80)
print("Running FallbackEngineV2 (REFERENCE)...")
fb = FallbackEngineV2()
fb_result = fb.run(input_data)

print("Running GPUEngineV2...")
gpu = GPUEngineV2()
gpu_result = gpu.run(input_data)

# ============================================================================
# COMPARE RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("📊 RESULTS COMPARISON")
print("=" * 80)

def compare(name, fb_val, gpu_val, tolerance=0.01):
    match = abs(fb_val - gpu_val) < tolerance
    status = "✅" if match else "❌"
    diff = gpu_val - fb_val
    print(f"   {name:20s}: FB={fb_val:12.4f}  GPU={gpu_val:12.4f}  Diff={diff:+.4f}  {status}")
    return match

all_match = True

print("\n🔸 CORE METRICS:")
trades_match = len(fb_result.trades) == len(gpu_result.trades)
print(f"   {'Trades':20s}: FB={len(fb_result.trades):12d}  GPU={len(gpu_result.trades):12d}  {'✅' if trades_match else '❌'}")
all_match &= trades_match
all_match &= compare("Net Profit", fb_result.metrics.net_profit, gpu_result.metrics.net_profit)
all_match &= compare("Total Return", fb_result.metrics.total_return, gpu_result.metrics.total_return)
all_match &= compare("Win Rate", fb_result.metrics.win_rate, gpu_result.metrics.win_rate)
all_match &= compare("Sharpe Ratio", fb_result.metrics.sharpe_ratio, gpu_result.metrics.sharpe_ratio)
all_match &= compare("Max Drawdown", fb_result.metrics.max_drawdown, gpu_result.metrics.max_drawdown)
all_match &= compare("Profit Factor", fb_result.metrics.profit_factor, gpu_result.metrics.profit_factor)

print("\n🔸 TRADE DETAILS (First 5):")
for i in range(min(5, len(fb_result.trades))):
    fb_t = fb_result.trades[i]
    gpu_t = gpu_result.trades[i]

    pnl_match = abs(fb_t.pnl - gpu_t.pnl) < 0.01
    size_match = abs(fb_t.size - gpu_t.size) < 0.0001
    fees_match = abs(fb_t.fees - gpu_t.fees) < 0.01

    status = "✅" if (pnl_match and size_match and fees_match) else "❌"
    print(f"   Trade {i+1}: {fb_t.direction:5s} PnL=${fb_t.pnl:8.2f} vs ${gpu_t.pnl:8.2f}  Size={fb_t.size:.4f} vs {gpu_t.size:.4f}  {status}")

    all_match &= pnl_match and size_match and fees_match

# ============================================================================
# VERDICT
# ============================================================================
print("\n" + "=" * 80)
if all_match:
    print("""
    ████████████████████████████████████████████████████████████████████████████
    █                                                                          █
    █   ✅ 100% PARITY ACHIEVED: GPUEngineV2 = FallbackEngineV2                █
    █                                                                          █
    ████████████████████████████████████████████████████████████████████████████
    """)
else:
    print("""
    ████████████████████████████████████████████████████████████████████████████
    █                                                                          █
    █   ❌ PARITY FAILED: Check differences above                              █
    █                                                                          █
    ████████████████████████████████████████████████████████████████████████████
    """)

print(f"   Execution time - FB: {fb_result.execution_time:.3f}s, GPU: {gpu_result.execution_time:.3f}s")
print(f"   GPU Enabled: {gpu.gpu_enabled}")
print("=" * 80)
