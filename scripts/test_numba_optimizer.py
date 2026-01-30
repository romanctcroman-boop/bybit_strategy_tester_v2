"""
Test TwoStageOptimizer with Numba JIT Integration
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time
import pandas as pd
import sqlite3
from loguru import logger

print("=" * 70)
print("🚀 TESTING NUMBA-ACCELERATED TWO-STAGE OPTIMIZER")
print("=" * 70)

# Load test data
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

print(f"📊 Loaded {len(df)} 1H candles")

# Test with Numba (fast mode, no bar magnifier)
print("\n" + "=" * 70)
print("⚡ TEST 1: TwoStageOptimizer with Numba (fast mode)")
print("=" * 70)

from backend.backtesting.two_stage_optimizer import TwoStageOptimizer

optimizer_fast = TwoStageOptimizer(
    top_n=10,
    use_bar_magnifier=False,  # Disables Bar Magnifier, enables Numba
    use_numba_fast=True,
    use_pareto=True,
    parallel_workers=4,
)

start_fast = time.time()
result_fast = optimizer_fast.optimize(
    candles=df,
    symbol="BTCUSDT",
    interval="60",
    rsi_period_range=[10, 14, 21],
    rsi_overbought_range=[65, 70, 75],
    rsi_oversold_range=[25, 30, 35],
    stop_loss_range=[0.02, 0.03, 0.04],
    take_profit_range=[0.04, 0.06, 0.08],
    initial_capital=10000.0,
    leverage=10,
    commission=0.0004,
    slippage=0.0001,
    direction="both",
)
fast_time = time.time() - start_fast

print(f"\n📊 Fast Mode Results:")
print(f"   Total time: {fast_time:.2f}s")
print(f"   Stage 1: {result_fast.stage1_execution_time:.2f}s ({result_fast.stage1_tested} combinations)")
print(f"   Stage 2: {result_fast.stage2_execution_time:.2f}s ({result_fast.stage2_validated} validated)")
print(f"   Best Sharpe: {result_fast.best_validated_sharpe:.3f}")
print(f"   Best Return: {result_fast.best_validated_return:.2f}%")
print(f"   Best Params: {result_fast.best_params}")
print(f"   Reliable: {result_fast.reliable_count}/{result_fast.stage2_validated}")
print(f"   Speedup: {result_fast.speedup_factor:.0f}x")

# Test with Bar Magnifier (precision mode)
print("\n" + "=" * 70)
print("🎯 TEST 2: TwoStageOptimizer with Bar Magnifier (precision mode)")
print("=" * 70)

optimizer_precision = TwoStageOptimizer(
    top_n=5,  # Fewer for precision test
    use_bar_magnifier=True,  # Enables Bar Magnifier (disables Numba)
    use_numba_fast=True,
    use_pareto=True,
    parallel_workers=2,
)

start_precision = time.time()
result_precision = optimizer_precision.optimize(
    candles=df,
    symbol="BTCUSDT",
    interval="60",
    rsi_period_range=[14],
    rsi_overbought_range=[70],
    rsi_oversold_range=[30],
    stop_loss_range=[0.03],
    take_profit_range=[0.06],
    initial_capital=10000.0,
    leverage=10,
    commission=0.0004,
    slippage=0.0001,
    direction="both",
)
precision_time = time.time() - start_precision

print(f"\n📊 Precision Mode Results:")
print(f"   Total time: {precision_time:.2f}s")
print(f"   Stage 2: {result_precision.stage2_execution_time:.2f}s ({result_precision.stage2_validated} validated)")
print(f"   Best Sharpe: {result_precision.best_validated_sharpe:.3f}")
print(f"   Best Return: {result_precision.best_validated_return:.2f}%")

# Summary
print("\n" + "=" * 70)
print("📊 COMPARISON SUMMARY")
print("=" * 70)
print(f"   Fast Mode (Numba):     {fast_time:.2f}s for {result_fast.stage2_validated} validations")
print(f"   Precision Mode (BM):   {precision_time:.2f}s for {result_precision.stage2_validated} validations")

if result_fast.stage2_validated > 0 and result_precision.stage2_validated > 0:
    fast_per_val = fast_time / result_fast.stage2_validated
    precision_per_val = precision_time / result_precision.stage2_validated
    speedup = precision_per_val / fast_per_val if fast_per_val > 0 else 0
    print(f"   Per-validation speedup: {speedup:.1f}x")

print("\n✅ TwoStageOptimizer with Numba integration complete!")
