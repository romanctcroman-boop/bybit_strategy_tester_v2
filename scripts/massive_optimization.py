"""
🚀 МАСШТАБНАЯ GPU ОПТИМИЗАЦИЯ RSI СТРАТЕГИИ v2
С РЕАЛИСТИЧНЫМИ SL/TP значениями
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
import time
from datetime import datetime

import pandas as pd

print("=" * 80)
print("🚀 МАСШТАБНАЯ GPU ОПТИМИЗАЦИЯ RSI v2 (Реалистичные SL/TP)")
print("=" * 80)
print(f"Время: {datetime.now()}")

from backend.backtesting.gpu_optimizer import GPU_NAME, GPUGridOptimizer

print(f"\n📊 GPU Status: {GPU_NAME}")

# Load data
print("\n📊 Loading market data...")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
""", conn)
conn.close()
print(f"   Loaded: {len(df)} bars")

# ============================================================================
# REALISTIC PARAMETER GRID
# ============================================================================
print("\n" + "=" * 80)
print("📈 PARAMETER GRID (REALISTIC)")
print("=" * 80)

# RSI Parameters
rsi_period_range = list(range(5, 31, 1))          # 5-30 -> 26 values
rsi_overbought_range = list(range(65, 86, 3))     # 65,68,71,74,77,80,83 -> 7 values
rsi_oversold_range = list(range(15, 36, 3))       # 15,18,21,24,27,30,33 -> 7 values

# REALISTIC Risk Management (1%-6% SL, 2%-12% TP)
stop_loss_range = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06]  # 8 values
take_profit_range = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12]  # 8 values

total_combos = (len(rsi_period_range) * len(rsi_overbought_range) *
                len(rsi_oversold_range) * len(stop_loss_range) * len(take_profit_range))

print(f"   RSI Period:     {len(rsi_period_range):>3} values ({min(rsi_period_range)}-{max(rsi_period_range)})")
print(f"   RSI Overbought: {len(rsi_overbought_range):>3} values ({rsi_overbought_range})")
print(f"   RSI Oversold:   {len(rsi_oversold_range):>3} values ({rsi_oversold_range})")
print(f"   Stop Loss:      {len(stop_loss_range):>3} values ({[f'{x*100:.1f}%' for x in stop_loss_range]})")
print(f"   Take Profit:    {len(take_profit_range):>3} values ({[f'{x*100:.1f}%' for x in take_profit_range]})")
print(f"\n   🔢 TOTAL COMBINATIONS: {total_combos:,}")

optimizer = GPUGridOptimizer(position_size=1.0)

# ============================================================================
# LONG OPTIMIZATION
# ============================================================================
print("\n" + "=" * 80)
print("⚡ OPTIMIZING LONG...")
print("=" * 80)

start = time.time()
result_long = optimizer.optimize(
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
    top_k=20
)
time_long = time.time() - start
print(f"   ✅ Done in {time_long:.2f}s ({total_combos/time_long:,.0f} comb/sec)")

# ============================================================================
# SHORT OPTIMIZATION
# ============================================================================
print("\n⚡ OPTIMIZING SHORT...")
start = time.time()
result_short = optimizer.optimize(
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
    direction="short",
    top_k=20
)
time_short = time.time() - start
print(f"   ✅ Done in {time_short:.2f}s")

# ============================================================================
# RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("🏆 TOP 10 LONG STRATEGIES")
print("=" * 80)

for i, r in enumerate(result_long.top_results[:10]):
    p = r.get('params', {})
    print(f"{i+1:>2}. Sharpe={r.get('sharpe_ratio', 0):>6.2f}  "
          f"Ret={r.get('total_return', 0):>6.2f}%  "
          f"DD={r.get('max_drawdown', 0):>5.2f}%  "
          f"WR={r.get('win_rate', 0)*100:>5.1f}%  "
          f"Tr={r.get('total_trades', 0):>3}  "
          f"RSI({p.get('rsi_period', 0):>2},{p.get('rsi_overbought', 0):>2},{p.get('rsi_oversold', 0):>2})  "
          f"SL={p.get('stop_loss_pct', 0)*100:.1f}% TP={p.get('take_profit_pct', 0)*100:.1f}%")

print("\n" + "=" * 80)
print("🏆 TOP 10 SHORT STRATEGIES")
print("=" * 80)

for i, r in enumerate(result_short.top_results[:10]):
    p = r.get('params', {})
    print(f"{i+1:>2}. Sharpe={r.get('sharpe_ratio', 0):>6.2f}  "
          f"Ret={r.get('total_return', 0):>6.2f}%  "
          f"DD={r.get('max_drawdown', 0):>5.2f}%  "
          f"WR={r.get('win_rate', 0)*100:>5.1f}%  "
          f"Tr={r.get('total_trades', 0):>3}  "
          f"RSI({p.get('rsi_period', 0):>2},{p.get('rsi_overbought', 0):>2},{p.get('rsi_oversold', 0):>2})  "
          f"SL={p.get('stop_loss_pct', 0)*100:.1f}% TP={p.get('take_profit_pct', 0)*100:.1f}%")

# Best results
print("\n" + "=" * 80)
print("📊 BEST STRATEGIES SUMMARY")
print("=" * 80)

if result_long.top_results:
    best = result_long.top_results[0]
    p = best.get('params', {})
    print("\n🟢 BEST LONG:")
    print(f"   Sharpe:   {best.get('sharpe_ratio', 0):.2f}")
    print(f"   Return:   {best.get('total_return', 0):.2f}%")
    print(f"   Max DD:   {best.get('max_drawdown', 0):.2f}%")
    print(f"   Win Rate: {best.get('win_rate', 0)*100:.1f}%")
    print(f"   Trades:   {best.get('total_trades', 0)}")
    print(f"   RSI:      period={p.get('rsi_period')}, ob={p.get('rsi_overbought')}, os={p.get('rsi_oversold')}")
    print(f"   SL/TP:    {p.get('stop_loss_pct', 0)*100:.1f}% / {p.get('take_profit_pct', 0)*100:.1f}%")

if result_short.top_results:
    best = result_short.top_results[0]
    p = best.get('params', {})
    print("\n🔴 BEST SHORT:")
    print(f"   Sharpe:   {best.get('sharpe_ratio', 0):.2f}")
    print(f"   Return:   {best.get('total_return', 0):.2f}%")
    print(f"   Max DD:   {best.get('max_drawdown', 0):.2f}%")
    print(f"   Win Rate: {best.get('win_rate', 0)*100:.1f}%")
    print(f"   Trades:   {best.get('total_trades', 0)}")
    print(f"   RSI:      period={p.get('rsi_period')}, ob={p.get('rsi_overbought')}, os={p.get('rsi_oversold')}")
    print(f"   SL/TP:    {p.get('stop_loss_pct', 0)*100:.1f}% / {p.get('take_profit_pct', 0)*100:.1f}%")

print(f"\n⏱️ Total time: {time_long + time_short:.2f}s for {total_combos*2:,} combinations")
