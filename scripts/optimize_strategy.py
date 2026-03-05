"""
🔧 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ СТРАТЕГИИ
Используем NumbaEngineV2 для быстрой оптимизации
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
import time
from datetime import datetime
from itertools import product

import pandas as pd

print("=" * 100)
print("🔧 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ СТРАТЕГИИ")
print("=" * 100)
print(f"Время: {datetime.now()}")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("\n📊 Загрузка данных...")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df_1h = pd.read_sql(
    """
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
""",
    conn,
)
df_1h["open_time"] = pd.to_datetime(df_1h["open_time"], unit="ms")
df_1h.set_index("open_time", inplace=True)
conn.close()

print(f"   📅 Период: {df_1h.index[0]} - {df_1h.index[-1]}")
print(f"   📊 Баров: {len(df_1h):,}")

# ============================================================================
# ПАРАМЕТРЫ ДЛЯ ОПТИМИЗАЦИИ
# ============================================================================
print("\n⚙️ ПАРАМЕТРЫ ОПТИМИЗАЦИИ:")

rsi_periods = [7, 10, 14, 21, 28]
rsi_oversold = [20, 25, 30, 35]
rsi_overbought = [65, 70, 75, 80]
stop_losses = [0.01, 0.015, 0.02, 0.025, 0.03]
take_profits = [0.02, 0.03, 0.04, 0.05, 0.06]
ema_fast = [20, 50]
ema_slow = [100, 200]
directions = ["both", "long", "short"]

total_combos = (
    len(rsi_periods)
    * len(rsi_oversold)
    * len(rsi_overbought)
    * len(stop_losses)
    * len(take_profits)
    * len(ema_fast)
    * len(ema_slow)
    * len(directions)
)

print(f"   RSI Period:    {rsi_periods}")
print(f"   RSI Oversold:  {rsi_oversold}")
print(f"   RSI Overbought: {rsi_overbought}")
print(f"   Stop Loss:     {[f'{x * 100:.1f}%' for x in stop_losses]}")
print(f"   Take Profit:   {[f'{x * 100:.1f}%' for x in take_profits]}")
print(f"   EMA Fast:      {ema_fast}")
print(f"   EMA Slow:      {ema_slow}")
print(f"   Direction:     {directions}")
print(f"\n   📊 Всего комбинаций: {total_combos:,}")

# Ограничим для скорости
MAX_COMBOS = 1000
print(f"   🔄 Тестируем: {min(total_combos, MAX_COMBOS):,} комбинаций")


# ============================================================================
# ФУНКЦИИ
# ============================================================================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ============================================================================
# ИМПОРТЫ
# ============================================================================
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

engine = NumbaEngineV2()

dir_map = {
    "long": TradeDirection.LONG,
    "short": TradeDirection.SHORT,
    "both": TradeDirection.BOTH,
}

# ============================================================================
# ОПТИМИЗАЦИЯ
# ============================================================================
print("\n" + "=" * 100)
print("🚀 ЗАПУСК ОПТИМИЗАЦИИ")
print("=" * 100)

results = []
start_time = time.time()

# Генерируем все комбинации
all_combos = list(
    product(rsi_periods, rsi_oversold, rsi_overbought, stop_losses, take_profits, ema_fast, ema_slow, directions)
)[:MAX_COMBOS]

for i, (rsi_p, rsi_os, rsi_ob, sl, tp, ema_f, ema_s, direction) in enumerate(all_combos):
    # Расчёт индикаторов
    rsi = calculate_rsi(df_1h["close"], period=rsi_p)
    ema_fast_line = df_1h["close"].ewm(span=ema_f).mean()
    ema_slow_line = df_1h["close"].ewm(span=ema_s).mean()

    # Сигналы с EMA фильтром
    bullish = ema_fast_line > ema_slow_line
    bearish = ema_fast_line < ema_slow_line

    long_entries = ((rsi < rsi_os) & bullish).values
    long_exits = (rsi > rsi_ob).values
    short_entries = ((rsi > rsi_ob) & bearish).values
    short_exits = (rsi < rsi_os).values

    # Запуск
    input_data = BacktestInput(
        candles=df_1h,
        candles_1m=None,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        symbol="BTCUSDT",
        interval="60",
        initial_capital=10000.0,
        position_size=0.10,
        leverage=10,
        stop_loss=sl,
        take_profit=tp,
        direction=dir_map[direction],
        taker_fee=0.001,
        slippage=0.0005,
        use_bar_magnifier=False,
    )

    result = engine.run(input_data)
    m = result.metrics

    if m.total_trades >= 10:  # Минимум 10 сделок
        results.append(
            {
                "rsi_period": rsi_p,
                "rsi_os": rsi_os,
                "rsi_ob": rsi_ob,
                "sl": sl,
                "tp": tp,
                "ema_fast": ema_f,
                "ema_slow": ema_s,
                "direction": direction,
                "net_profit": m.net_profit,
                "total_return": m.total_return,
                "max_drawdown": m.max_drawdown,
                "sharpe": m.sharpe_ratio,
                "sortino": m.sortino_ratio,
                "profit_factor": m.profit_factor,
                "win_rate": m.win_rate,
                "total_trades": m.total_trades,
                "expectancy": m.expectancy,
                "recovery_factor": m.recovery_factor,
            }
        )

    # Прогресс
    if (i + 1) % 100 == 0:
        elapsed = time.time() - start_time
        eta = elapsed / (i + 1) * (len(all_combos) - i - 1)
        print(f"   [{i + 1}/{len(all_combos)}] Elapsed: {elapsed:.1f}s, ETA: {eta:.1f}s, Найдено: {len(results)}")

total_time = time.time() - start_time
print(f"\n✅ Завершено за {total_time:.1f}s")
print(f"📊 Найдено {len(results)} стратегий с >= 10 сделок")

# ============================================================================
# РЕЗУЛЬТАТЫ
# ============================================================================
df = pd.DataFrame(results)

print("\n" + "=" * 100)
print("🏆 ТОП-10 ПО NET PROFIT")
print("=" * 100)

if len(df) > 0:
    df_sorted = df.sort_values("net_profit", ascending=False)

    print(
        f"\n{'#':<3} {'RSI':<12} {'SL/TP':<12} {'EMA':<10} {'Dir':<6} {'Net Profit':>12} {'Return':>8} {'MaxDD':>8} {'Sharpe':>8} {'WR':>6} {'PF':>6} {'Trades':>6}"
    )
    print("-" * 110)

    for i, (_, row) in enumerate(df_sorted.head(10).iterrows()):
        rsi_str = f"{row['rsi_period']}/{row['rsi_os']}/{row['rsi_ob']}"
        sltp_str = f"{row['sl'] * 100:.1f}/{row['tp'] * 100:.1f}"
        ema_str = f"{row['ema_fast']}/{row['ema_slow']}"
        print(
            f"{i + 1:<3} {rsi_str:<12} {sltp_str:<12} {ema_str:<10} {row['direction']:<6} ${row['net_profit']:>10,.2f} {row['total_return']:>7.1f}% {row['max_drawdown']:>7.1f}% {row['sharpe']:>7.2f} {row['win_rate'] * 100:>5.1f}% {row['profit_factor']:>5.2f} {int(row['total_trades']):>6}"
        )

    # ТОП по Sharpe
    print("\n" + "=" * 100)
    print("🏆 ТОП-10 ПО SHARPE RATIO")
    print("=" * 100)

    df_sorted = df.sort_values("sharpe", ascending=False)
    print(
        f"\n{'#':<3} {'RSI':<12} {'SL/TP':<12} {'EMA':<10} {'Dir':<6} {'Net Profit':>12} {'Return':>8} {'MaxDD':>8} {'Sharpe':>8} {'WR':>6} {'PF':>6} {'Trades':>6}"
    )
    print("-" * 110)

    for i, (_, row) in enumerate(df_sorted.head(10).iterrows()):
        rsi_str = f"{row['rsi_period']}/{row['rsi_os']}/{row['rsi_ob']}"
        sltp_str = f"{row['sl'] * 100:.1f}/{row['tp'] * 100:.1f}"
        ema_str = f"{row['ema_fast']}/{row['ema_slow']}"
        print(
            f"{i + 1:<3} {rsi_str:<12} {sltp_str:<12} {ema_str:<10} {row['direction']:<6} ${row['net_profit']:>10,.2f} {row['total_return']:>7.1f}% {row['max_drawdown']:>7.1f}% {row['sharpe']:>7.2f} {row['win_rate'] * 100:>5.1f}% {row['profit_factor']:>5.2f} {int(row['total_trades']):>6}"
        )

    # ТОП с положительным profit
    profitable = df[df["net_profit"] > 0]
    print(f"\n✅ Прибыльных стратегий: {len(profitable)} из {len(df)} ({len(profitable) / len(df) * 100:.1f}%)")

    if len(profitable) > 0:
        print("\n" + "=" * 100)
        print("🏆 ЛУЧШАЯ ПРИБЫЛЬНАЯ СТРАТЕГИЯ")
        print("=" * 100)

        best = profitable.sort_values("sharpe", ascending=False).iloc[0]
        print(f"""
   📈 ПАРАМЕТРЫ:
      RSI Period:     {int(best["rsi_period"])}
      RSI Oversold:   {int(best["rsi_os"])}
      RSI Overbought: {int(best["rsi_ob"])}
      Stop Loss:      {best["sl"] * 100:.1f}%
      Take Profit:    {best["tp"] * 100:.1f}%
      EMA Fast:       {int(best["ema_fast"])}
      EMA Slow:       {int(best["ema_slow"])}
      Direction:      {best["direction"]}

   📊 РЕЗУЛЬТАТЫ:
      Net Profit:     ${best["net_profit"]:,.2f}
      Total Return:   {best["total_return"]:.2f}%
      Max Drawdown:   {best["max_drawdown"]:.2f}%
      Sharpe Ratio:   {best["sharpe"]:.2f}
      Sortino Ratio:  {best["sortino"]:.2f}
      Win Rate:       {best["win_rate"] * 100:.1f}%
      Profit Factor:  {best["profit_factor"]:.2f}
      Total Trades:   {int(best["total_trades"])}
      Expectancy:     ${best["expectancy"]:.2f}
      Recovery Factor: {best["recovery_factor"]:.2f}
""")
else:
    print("❌ Не найдено стратегий с >= 10 сделок")

print("=" * 100)
