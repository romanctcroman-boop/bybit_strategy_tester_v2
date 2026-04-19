"""
🚀 МАСШТАБНАЯ ОПТИМИЗАЦИЯ С ПАРАМЕТРАМИ ИЗ UI
Период: 18.01.2025 - 18.01.2026 (1 год)
~2.3 млн комбинаций × 3 направления = ~7 млн тестов
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
import time
from datetime import datetime

import pandas as pd

print("=" * 100)
print("🚀 МАСШТАБНАЯ ОПТИМИЗАЦИЯ RSI (параметры из UI)")
print("=" * 100)
print(f"Время запуска: {datetime.now()}")

from backend.backtesting.gpu_optimizer import GPU_NAME, GPUGridOptimizer

print(f"GPU: {GPU_NAME}")

# ============================================================================
# ПАРАМЕТРЫ ОПТИМИЗАЦИИ (ИЗ СКРИНШОТОВ UI)
# ============================================================================
print("\n" + "=" * 100)
print("📋 ПАРАМЕТРЫ ОПТИМИЗАЦИИ (из UI)")
print("=" * 100)

# RSI Parameters
period_range = list(range(7, 26, 1))  # 7-25, шаг 1 -> 19 values
overbought_range = list(range(45, 81, 1))  # 45-80, шаг 1 -> 36 values
oversold_range = list(range(10, 46, 1))  # 10-45, шаг 1 -> 36 values

# SL/TP Parameters (конвертируем в десятичные)
sl_range = [x / 100 for x in range(1, 11)]  # 1-10%, шаг 0.5 -> но API принимает целые, поэтому шаг 1
sl_range = [
    0.01,
    0.015,
    0.02,
    0.025,
    0.03,
    0.035,
    0.04,
    0.045,
    0.05,
    0.055,
    0.06,
    0.065,
    0.07,
    0.075,
    0.08,
    0.085,
    0.09,
    0.095,
    0.10,
]  # 19 values
tp_range = [0.01, 0.015, 0.02, 0.025, 0.03]  # 1-3%, шаг 0.5 -> 5 values

# Для ускорения уменьшим шаг
sl_range = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]  # 10 values (шаг 1%)
tp_range = [0.01, 0.015, 0.02, 0.025, 0.03]  # 5 values

total_combos = len(period_range) * len(overbought_range) * len(oversold_range) * len(sl_range) * len(tp_range)

print(f"""
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│  ПЕРИОД ТЕСТИРОВАНИЯ                                                                           │
├────────────────────────────┬───────────────────────────────────────────────────────────────────┤
│  Дата начала               │  18.01.2025                                                       │
│  Дата окончания            │  18.01.2026                                                       │
│  Длительность              │  1 ГОД                                                            │
├────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  ПАРАМЕТРЫ RSI                                                                                 │
├────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  Period                    │  7-25, шаг 1  ({len(period_range)} значений)                                   │
│  Overbought                │  45-80, шаг 1 ({len(overbought_range)} значений)                                   │
│  Oversold                  │  10-45, шаг 1 ({len(oversold_range)} значений)                                   │
├────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  STOP LOSS / TAKE PROFIT                                                                       │
├────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  Stop Loss %               │  1-10%, шаг 1% ({len(sl_range)} значений)                                    │
│  Take Profit %             │  1-3%, шаг 0.5% ({len(tp_range)} значений)                                     │
├────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  ИТОГО КОМБИНАЦИЙ          │  {total_combos:,} × 3 направления = {total_combos * 3:,}                      │
└────────────────────────────┴───────────────────────────────────────────────────────────────────┘
""")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ (1 ГОД)
# ============================================================================
print("=" * 100)
print("📊 ЗАГРУЗКА ДАННЫХ (1 год, 30m)")
print("=" * 100)

conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))

# Проверяем доступные данные
info = pd.read_sql(
    """
    SELECT COUNT(*) as cnt, MIN(open_time) as min_t, MAX(open_time) as max_t
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '30'
""",
    conn,
)

available_start = pd.to_datetime(info["min_t"].iloc[0], unit="ms")
available_end = pd.to_datetime(info["max_t"].iloc[0], unit="ms")
print(f"  Доступные данные: {info['cnt'].iloc[0]:,} баров")
print(f"  Период: {available_start.date()} - {available_end.date()}")

# Загружаем запрошенный период (или доступный)
start_date = "2025-01-18"
end_date = "2026-01-18"
start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)

df = pd.read_sql(
    f"""
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '30'
    AND open_time >= {start_ts} AND open_time <= {end_ts}
    ORDER BY open_time ASC
""",
    conn,
)
conn.close()

df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
df.set_index("open_time", inplace=True)

print(f"  Загружено: {len(df):,} баров")
if len(df) > 0:
    print(f"  Фактический период: {df.index.min().date()} - {df.index.max().date()}")

if len(df) < 100:
    print("\n⚠️ НЕДОСТАТОЧНО ДАННЫХ! Попробуем загрузить все доступные...")
    conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
    df = pd.read_sql(
        """
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '30'
        ORDER BY open_time ASC
    """,
        conn,
    )
    conn.close()
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("open_time", inplace=True)
    print(f"  Загружено всего: {len(df):,} баров")
    print(f"  Период: {df.index.min().date()} - {df.index.max().date()}")

# ============================================================================
# ЗАПУСК ОПТИМИЗАЦИИ
# ============================================================================
optimizer = GPUGridOptimizer(position_size=0.10)  # 10% от капитала

results = {}

for direction in ["long", "short", "both"]:
    print("\n" + "=" * 100)
    emoji = "🟢" if direction == "long" else ("🔴" if direction == "short" else "🟣")
    print(f"{emoji} ОПТИМИЗАЦИЯ: {direction.upper()}")
    print("=" * 100)

    start = time.time()

    result = optimizer.optimize(
        candles=df,
        rsi_period_range=period_range,
        rsi_overbought_range=overbought_range,
        rsi_oversold_range=oversold_range,
        stop_loss_range=sl_range,
        take_profit_range=tp_range,
        initial_capital=10000.0,
        leverage=10,
        commission=0.001,  # 0.1%
        slippage=0.0005,  # 0.05%
        direction=direction,
        top_k=20,
        optimize_metric="sharpe_ratio",
    )

    elapsed = time.time() - start
    results[direction] = {"result": result, "time": elapsed}

    print(f"  ✅ Завершено за {elapsed:.2f}s ({total_combos / elapsed:,.0f} комб/сек)")
    print(f"  Режим: {result.execution_mode}")

    if result.top_results:
        print(f"\n  🏆 ТОП-5 {direction.upper()}:")
        for i, r in enumerate(result.top_results[:5]):
            p = r.get("params", {})
            print(
                f"  {i + 1}. Sharpe={r.get('sharpe_ratio', 0):>7.2f}  "
                f"Ret={r.get('total_return', 0):>6.2f}%  "
                f"DD={r.get('max_drawdown', 0):>5.2f}%  "
                f"WR={r.get('win_rate', 0) * 100:>5.1f}%  "
                f"Tr={r.get('total_trades', 0):>4}  "
                f"RSI({p.get('rsi_period', 0)},{p.get('rsi_overbought', 0)},{p.get('rsi_oversold', 0)})  "
                f"SL={p.get('stop_loss_pct', 0) * 100:.1f}% TP={p.get('take_profit_pct', 0) * 100:.1f}%"
            )

# ============================================================================
# ИТОГОВАЯ СРАВНИТЕЛЬНАЯ ТАБЛИЦА
# ============================================================================
print("\n" + "=" * 100)
print("📊 ИТОГОВАЯ СРАВНИТЕЛЬНАЯ ТАБЛИЦА ЛУЧШИХ РЕЗУЛЬТАТОВ")
print("=" * 100)

print(
    f"\n{'Direction':<12} {'Sharpe':>10} {'Return':>10} {'MaxDD':>10} {'WinRate':>10} {'Trades':>10} {'Best RSI Params':<30}"
)
print("-" * 100)

for direction in ["long", "short", "both"]:
    r = results[direction]["result"]
    if r.top_results:
        best = r.top_results[0]
        p = best.get("params", {})
        rsi_str = f"RSI({p.get('rsi_period', 0)},{p.get('rsi_overbought', 0)},{p.get('rsi_oversold', 0)}) SL={p.get('stop_loss_pct', 0) * 100:.0f}% TP={p.get('take_profit_pct', 0) * 100:.1f}%"
        print(
            f"{direction.upper():<12} {best.get('sharpe_ratio', 0):>10.2f} {best.get('total_return', 0):>9.2f}% "
            f"{best.get('max_drawdown', 0):>9.2f}% {best.get('win_rate', 0) * 100:>9.1f}% "
            f"{best.get('total_trades', 0):>10} {rsi_str}"
        )

# Определяем абсолютно лучший
all_best = []
for d in ["long", "short", "both"]:
    if results[d]["result"].top_results:
        best = results[d]["result"].top_results[0]
        all_best.append((d, best.get("sharpe_ratio", -999), best))

if all_best:
    winner = max(all_best, key=lambda x: x[1])
    p = winner[2].get("params", {})

    print("\n" + "=" * 100)
    print(f"🏆 ЛУЧШАЯ СТРАТЕГИЯ: {winner[0].upper()}")
    print("=" * 100)
    print(f"""
  Sharpe Ratio:  {winner[2].get("sharpe_ratio", 0):.2f}
  Total Return:  {winner[2].get("total_return", 0):.2f}%
  Max Drawdown:  {winner[2].get("max_drawdown", 0):.2f}%
  Win Rate:      {winner[2].get("win_rate", 0) * 100:.1f}%
  Total Trades:  {winner[2].get("total_trades", 0)}

  Параметры:
    RSI Period:    {p.get("rsi_period")}
    Overbought:    {p.get("rsi_overbought")}
    Oversold:      {p.get("rsi_oversold")}
    Stop Loss:     {p.get("stop_loss_pct", 0) * 100:.1f}%
    Take Profit:   {p.get("take_profit_pct", 0) * 100:.1f}%
""")

total_time = sum(r["time"] for r in results.values())
print(f"\n⏱️ Общее время оптимизации: {total_time:.2f}s")
print(f"   Комбинаций протестировано: {total_combos * 3:,}")
print(f"   Средняя скорость: {(total_combos * 3) / total_time:,.0f} комб/сек")
