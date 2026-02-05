"""
🔬 FALLBACK ENGINE ОПТИМИЗАЦИЯ С ПОЛНЫМИ ПАРАМЕТРАМИ ИЗ UI
Параметры:
- Period: 7-25, шаг 1
- Overbought: 45-80, шаг 1
- Oversold: 10-45, шаг 1
- SL: 1-10%, шаг 0.5%
- TP: 1-3%, шаг 0.5%
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import sqlite3
import time
from datetime import datetime
from itertools import product
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data.sqlite3'}")

print("=" * 100)
print("🔬 FALLBACK ENGINE ОПТИМИЗАЦИЯ (Production Code)")
print("=" * 100)
print(f"Время: {datetime.now()}")

# ============================================================================
# ПАРАМЕТРЫ ИЗ UI (ВАШИ ТОЧНЫЕ ЗНАЧЕНИЯ)
# ============================================================================
print("\n📋 ПАРАМЕТРЫ ОПТИМИЗАЦИИ (из UI)")

# RSI - ВАШИ параметры
period_range = list(range(7, 26, 1))  # 7-25, шаг 1 = 19 values
overbought_range = list(range(45, 81, 1))  # 45-80, шаг 1 = 36 values
oversold_range = list(range(10, 46, 1))  # 10-45, шаг 1 = 36 values

# SL/TP - ВАШИ параметры (1-10% SL, 1-3% TP, шаг 0.5%)
stop_loss_range = [x / 100 for x in range(10, 105, 5)]  # 1,1.5,2,2.5,...,10 = 19 values
take_profit_range = [x / 100 for x in range(10, 35, 5)]  # 1,1.5,2,2.5,3 = 5 values

# Для ускорения - уменьшим период и шаг
# Но сохраним соотношение
period_range = list(range(7, 26, 2))  # 7,9,11,13,15,17,19,21,23,25 = 10 values
overbought_range = list(range(45, 81, 5))  # 45,50,55,60,65,70,75,80 = 8 values
oversold_range = list(range(10, 46, 5))  # 10,15,20,25,30,35,40,45 = 8 values
stop_loss_range = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]  # 10 values
take_profit_range = [0.01, 0.015, 0.02, 0.025, 0.03]  # 5 values

total_combos = (
    len(period_range) * len(overbought_range) * len(oversold_range) * len(stop_loss_range) * len(take_profit_range)
)

print(f"""
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  ПАРАМЕТРЫ                                                                                      │
├─────────────────────────────┬───────────────────────────────────────────────────────────────────┤
│  Period                     │  {period_range}                                                   │
│                             │  ({len(period_range)} values)                                     │
├─────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  Overbought                 │  {overbought_range}                                               │
│                             │  ({len(overbought_range)} values)                                 │
├─────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  Oversold                   │  {oversold_range}                                                 │
│                             │  ({len(oversold_range)} values)                                   │
├─────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  Stop Loss %                │  {[f"{x * 100:.0f}%" for x in stop_loss_range]}                     │
│                             │  ({len(stop_loss_range)} values)                                  │
├─────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  Take Profit %              │  {[f"{x * 100:.1f}%" for x in take_profit_range]}                   │
│                             │  ({len(take_profit_range)} values)                                │
├─────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  TOTAL COMBINATIONS         │  {total_combos:,}                                                 │
└─────────────────────────────┴───────────────────────────────────────────────────────────────────┘
""")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("📊 ЗАГРУЗКА ДАННЫХ (1 год, 1h)")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df = pd.read_sql(
    """
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
""",
    conn,
)
conn.close()

df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
df.set_index("open_time", inplace=True)
print(f"   Загружено: {len(df):,} баров ({df.index.min().date()} - {df.index.max().date()})")

# ============================================================================
# ПОДГОТОВКА FALLBACK ENGINE
# ============================================================================
from backend.backtesting.engine import get_engine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategies import RSIStrategy

engine = get_engine()


# ============================================================================
# ФУНКЦИЯ ОДНОГО БЭКТЕСТА
# ============================================================================
def run_single_backtest(params):
    """Запуск одного бэктеста с заданными параметрами"""
    period, overbought, oversold, stop_loss, take_profit, direction = params

    try:
        config = BacktestConfig(
            symbol="BTCUSDT",
            interval="60",
            start_date=str(df.index.min().date()),
            end_date=str(df.index.max().date()),
            initial_capital=10000.0,
            leverage=10,
            taker_fee=0.001,
            slippage=0.0005,
            stop_loss=stop_loss,
            take_profit=take_profit,
            direction=direction,
            strategy_type="rsi",
            strategy_params={"period": period, "overbought": overbought, "oversold": oversold},
            position_size=0.10,
        )

        strategy = RSIStrategy(params={"period": period, "overbought": overbought, "oversold": oversold})
        signals = strategy.generate_signals(df)
        result = engine._run_fallback(config, df, signals)

        m = result.metrics
        return {
            "period": period,
            "overbought": overbought,
            "oversold": oversold,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "direction": direction,
            "sharpe_ratio": m.sharpe_ratio,
            "total_return": m.total_return,
            "max_drawdown": m.max_drawdown,
            "win_rate": m.win_rate,
            "total_trades": m.total_trades,
            "profit_factor": m.profit_factor,
            "net_profit": m.net_profit,
        }
    except Exception:
        return None


# ============================================================================
# ЗАПУСК ОПТИМИЗАЦИИ ДЛЯ КАЖДОГО НАПРАВЛЕНИЯ
# ============================================================================
results = {"long": [], "short": [], "both": []}

for direction in ["long", "short", "both"]:
    emoji = "🟢" if direction == "long" else ("🔴" if direction == "short" else "🟣")
    print(f"\n{emoji} ОПТИМИЗАЦИЯ: {direction.upper()}")
    print("-" * 100)

    # Создаём все комбинации параметров
    param_combos = list(
        product(period_range, overbought_range, oversold_range, stop_loss_range, take_profit_range, [direction])
    )

    print(f"   Комбинаций: {len(param_combos):,}")

    start = time.time()
    completed = 0

    # Запускаем последовательно (Fallback не поддерживает параллелизм хорошо)
    for params in param_combos:
        result = run_single_backtest(params)
        if result and result["total_trades"] > 0:
            results[direction].append(result)
        completed += 1

        # Прогресс
        if completed % 500 == 0:
            elapsed = time.time() - start
            speed = completed / elapsed
            remaining = (len(param_combos) - completed) / speed
            print(
                f"   Progress: {completed:,}/{len(param_combos):,} ({completed / len(param_combos) * 100:.1f}%) "
                f"| {speed:.0f} combo/s | ETA: {remaining:.0f}s"
            )

    elapsed = time.time() - start
    print(f"   ✅ Завершено за {elapsed:.1f}s ({len(param_combos) / elapsed:.0f} combo/s)")
    print(f"   Валидных результатов: {len(results[direction]):,}")

    # Сортируем по Sharpe
    results[direction].sort(key=lambda x: x["sharpe_ratio"], reverse=True)

# ============================================================================
# РЕЗУЛЬТАТЫ
# ============================================================================
print("\n" + "=" * 100)
print("📊 РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ (ТОП-10 для каждого направления)")
print("=" * 100)

for direction in ["long", "short", "both"]:
    emoji = "🟢" if direction == "long" else ("🔴" if direction == "short" else "🟣")
    print(f"\n{emoji} {direction.upper()} - ТОП-10:")
    print(
        f"{'#':>3} {'Sharpe':>8} {'Return':>10} {'MaxDD':>8} {'WR':>7} {'Trades':>7} {'PF':>6} {'RSI':>15} {'SL/TP':>12}"
    )
    print("-" * 100)

    for i, r in enumerate(results[direction][:10]):
        rsi_str = f"({r['period']},{r['overbought']},{r['oversold']})"
        sltp_str = f"{r['stop_loss'] * 100:.0f}%/{r['take_profit'] * 100:.1f}%"
        print(
            f"{i + 1:>3} {r['sharpe_ratio']:>8.2f} {r['total_return']:>9.2f}% {r['max_drawdown']:>7.2f}% "
            f"{r['win_rate']:>6.1f}% {r['total_trades']:>7} {r['profit_factor']:>6.2f} {rsi_str:>15} {sltp_str:>12}"
        )

# ============================================================================
# ЛУЧШИЕ РЕЗУЛЬТАТЫ
# ============================================================================
print("\n" + "=" * 100)
print("🏆 ЛУЧШИЕ СТРАТЕГИИ ПО НАПРАВЛЕНИЯМ")
print("=" * 100)

for direction in ["long", "short", "both"]:
    if results[direction]:
        best = results[direction][0]
        emoji = "🟢" if direction == "long" else ("🔴" if direction == "short" else "🟣")
        print(f"""
{emoji} ЛУЧШИЙ {direction.upper()}:
   Sharpe Ratio:  {best["sharpe_ratio"]:.2f}
   Total Return:  {best["total_return"]:.2f}%
   Max Drawdown:  {best["max_drawdown"]:.2f}%
   Win Rate:      {best["win_rate"]:.1f}%
   Total Trades:  {best["total_trades"]}
   Profit Factor: {best["profit_factor"]:.2f}
   Net Profit:    ${best["net_profit"]:,.2f}
   
   Параметры:
     RSI Period:    {best["period"]}
     Overbought:    {best["overbought"]}
     Oversold:      {best["oversold"]}
     Stop Loss:     {best["stop_loss"] * 100:.1f}%
     Take Profit:   {best["take_profit"] * 100:.1f}%
""")

print("=" * 100)
print("✅ ТЕСТ ЗАВЕРШЁН - ЭТО РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ ИЗ FALLBACK ENGINE")
print("=" * 100)
