"""Test GPU Optimizer"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
import time

import pandas as pd

print("=" * 80)
print("🚀 GPU OPTIMIZER TEST")
print("=" * 80)

# Check GPU
from backend.backtesting.gpu_optimizer import GPU_AVAILABLE, GPU_NAME

print(f"GPU Available: {GPU_AVAILABLE}")
print(f"GPU Name: {GPU_NAME}")

# Load data
print("\n📊 Loading market data...")
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
print(f"   Loaded {len(df)} bars")

# Import GPU optimizer
from backend.backtesting.gpu_optimizer import GPUGridOptimizer

# Create optimizer (correct API)
optimizer = GPUGridOptimizer(position_size=1.0, force_cpu=False)

# Define parameter ranges
rsi_period_range = list(range(8, 22, 2))      # 7 values
rsi_overbought_range = list(range(65, 85, 5)) # 4 values
rsi_oversold_range = list(range(15, 40, 5))   # 5 values
stop_loss_range = [0.02, 0.03, 0.04, 0.05]    # 4 values
take_profit_range = [0.04, 0.06, 0.08, 0.10]  # 4 values

total_combos = (len(rsi_period_range) * len(rsi_overbought_range) *
                len(rsi_oversold_range) * len(stop_loss_range) * len(take_profit_range))

print("\n📈 Parameter grid:")
print(f"   rsi_period: {len(rsi_period_range)} values ({rsi_period_range})")
print(f"   rsi_overbought: {len(rsi_overbought_range)} values")
print(f"   rsi_oversold: {len(rsi_oversold_range)} values")
print(f"   stop_loss: {len(stop_loss_range)} values")
print(f"   take_profit: {len(take_profit_range)} values")
print(f"   Total combinations: {total_combos:,}")

# Run optimization
print("\n⚡ Starting GPU optimization...")
start = time.time()

result = optimizer.optimize(
    candles=df,
    rsi_period_range=rsi_period_range,
    rsi_overbought_range=rsi_overbought_range,
    rsi_oversold_range=rsi_oversold_range,
    stop_loss_range=stop_loss_range,
    take_profit_range=take_profit_range,
    initial_capital=10000.0,
    leverage=1,
    commission=0.0004,
    slippage=0.0001,
    direction="long",
    top_k=10
)

elapsed = time.time() - start

print(f"\n✅ Optimization complete in {elapsed:.2f}s")
print(f"   Speed: {total_combos / elapsed:,.0f} combinations/second")
print(f"   Execution mode: {result.execution_mode}")

if result.top_results:
    print("\n🏆 Top 5 Results:")
    for i, r in enumerate(result.top_results[:5]):
        print(f"   {i+1}. Sharpe={r.get('sharpe_ratio', 0):.2f}, "
              f"PnL=${r.get('total_pnl', 0):.2f}, "
              f"Trades={r.get('total_trades', 0)}, "
              f"RSI={r.get('rsi_period', 0)}/{r.get('rsi_overbought', 0)}/{r.get('rsi_oversold', 0)}, "
              f"SL/TP={r.get('stop_loss', 0)*100:.1f}%/{r.get('take_profit', 0)*100:.1f}%")
else:
    print("No profitable results found")
