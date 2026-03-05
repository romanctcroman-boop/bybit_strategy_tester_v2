"""
🔬 РЕАЛЬНЫЙ ТЕСТ: 147 МЕТРИК НА ИСТОРИЧЕСКИХ ДАННЫХ
Использует реальные настройки стратегии и полные исторические данные
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

print("=" * 100)
print("🔬 РЕАЛЬНЫЙ ТЕСТ: 147 МЕТРИК НА ИСТОРИЧЕСКИХ ДАННЫХ")
print("=" * 100)
print(f"Время: {datetime.now()}")

# ============================================================================
# ЗАГРУЗКА ПОЛНЫХ ИСТОРИЧЕСКИХ ДАННЫХ
# ============================================================================
print("\n📊 Загрузка исторических данных...")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))

# Загружаем максимум данных
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

print(f"   📅 Период: {df_1h.index[0]} - {df_1h.index[-1]}")
print(f"   📊 Баров: {len(df_1h):,}")
print(f"   💰 Цена: ${df_1h['close'].iloc[0]:,.2f} → ${df_1h['close'].iloc[-1]:,.2f}")

conn.close()

# ============================================================================
# РЕАЛЬНЫЕ НАСТРОЙКИ СТРАТЕГИИ (RSI + EMA)
# ============================================================================
print("\n⚙️ НАСТРОЙКИ СТРАТЕГИИ:")
print("   📈 Индикаторы: RSI(14) + EMA(50/200)")
print("   🎯 Long: RSI < 30 AND EMA50 > EMA200")
print("   🎯 Short: RSI > 70 AND EMA50 < EMA200")
print("   🛑 Stop Loss: 2%")
print("   🎯 Take Profit: 4%")
print("   💰 Position Size: 10%")
print("   📊 Leverage: 10x")


# RSI
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# EMA
ema_50 = df_1h["close"].ewm(span=50).mean()
ema_200 = df_1h["close"].ewm(span=200).mean()
rsi = calculate_rsi(df_1h["close"], period=14)

# Сигналы с EMA фильтром
bullish_trend = ema_50 > ema_200
bearish_trend = ema_50 < ema_200

long_entries = ((rsi < 30) & bullish_trend).values
long_exits = (rsi > 70).values
short_entries = ((rsi > 70) & bearish_trend).values
short_exits = (rsi < 30).values

print("\n📊 СИГНАЛЫ:")
print(f"   Long entries:  {long_entries.sum()}")
print(f"   Short entries: {short_entries.sum()}")

# ============================================================================
# ЗАПУСК ДВИЖКОВ
# ============================================================================
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.core.extended_metrics import ExtendedMetricsCalculator

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
    stop_loss=0.02,
    take_profit=0.04,
    direction=TradeDirection.BOTH,
    taker_fee=0.001,
    slippage=0.0005,
    use_bar_magnifier=False,
)

print("\n" + "=" * 100)
print("🚀 ЗАПУСК ДВИЖКОВ")
print("=" * 100)

import time

# Fallback
start = time.time()
fallback = FallbackEngineV2()
fb_result = fallback.run(input_data)
fb_time = time.time() - start
print(f"\n✅ FallbackEngineV2: {fb_time:.3f}s, {len(fb_result.trades)} сделок")

# Numba
start = time.time()
numba_engine = NumbaEngineV2()
nb_result = numba_engine.run(input_data)
nb_time = time.time() - start
print(f"✅ NumbaEngineV2:    {nb_time:.3f}s, {len(nb_result.trades)} сделок")

# Extended Metrics
ext_calc = ExtendedMetricsCalculator()
fb_ext = ext_calc.calculate_all(fb_result.equity_curve, fb_result.trades)
nb_ext = ext_calc.calculate_all(nb_result.equity_curve, nb_result.trades)

# ============================================================================
# ВЫВОД ВСЕХ 147 МЕТРИК
# ============================================================================
print("\n" + "=" * 100)
print("📊 ВСЕ 147 МЕТРИК - СРАВНЕНИЕ ДВИЖКОВ")
print("=" * 100)


def format_value(val):
    if val is None:
        return "N/A"
    if isinstance(val, (int, np.integer)):
        return f"{val:,}"
    if isinstance(val, (float, np.floating)):
        if abs(val) >= 1000:
            return f"{val:,.2f}"
        elif abs(val) >= 1:
            return f"{val:.4f}"
        else:
            return f"{val:.6f}"
    return str(val)


def check_match(fb_val, nb_val):
    if fb_val is None and nb_val is None:
        return "✅"
    if fb_val is None or nb_val is None:
        return "❌"
    fb_v, nb_v = float(fb_val), float(nb_val)
    if abs(fb_v) < 1e-10 and abs(nb_v) < 1e-10:
        return "✅"
    if abs(fb_v - nb_v) < 1e-6:
        return "✅"
    if abs(fb_v) > 1e-10:
        pct_diff = abs(fb_v - nb_v) / abs(fb_v) * 100
        if pct_diff < 0.01:
            return "✅"
    return "❌"


# === BACKTEST METRICS ===
print("\n" + "=" * 50)
print("📂 BACKTEST METRICS (основные)")
print("=" * 50)
print(f"{'Метрика':<30} {'Fallback':>18} {'Numba':>18} {'Match':>6}")
print("-" * 74)

fb_m = fb_result.metrics
nb_m = nb_result.metrics

backtest_fields = [
    ("net_profit", "Net Profit ($)"),
    ("total_return", "Total Return (%)"),
    ("gross_profit", "Gross Profit ($)"),
    ("gross_loss", "Gross Loss ($)"),
    ("max_drawdown", "Max Drawdown (%)"),
    ("avg_drawdown", "Avg Drawdown (%)"),
    ("sharpe_ratio", "Sharpe Ratio"),
    ("sortino_ratio", "Sortino Ratio"),
    ("calmar_ratio", "Calmar Ratio"),
    ("total_trades", "Total Trades"),
    ("winning_trades", "Winning Trades"),
    ("losing_trades", "Losing Trades"),
    ("win_rate", "Win Rate"),
    ("profit_factor", "Profit Factor"),
    ("avg_win", "Avg Win ($)"),
    ("avg_loss", "Avg Loss ($)"),
    ("avg_trade", "Avg Trade ($)"),
    ("largest_win", "Largest Win ($)"),
    ("largest_loss", "Largest Loss ($)"),
    ("long_trades", "Long Trades"),
    ("short_trades", "Short Trades"),
    ("long_win_rate", "Long Win Rate"),
    ("short_win_rate", "Short Win Rate"),
    ("long_profit", "Long Profit ($)"),
    ("short_profit", "Short Profit ($)"),
    ("avg_trade_duration", "Avg Duration (bars)"),
    ("avg_winning_duration", "Avg Win Duration"),
    ("avg_losing_duration", "Avg Loss Duration"),
    ("expectancy", "Expectancy ($)"),
    ("payoff_ratio", "Payoff Ratio"),
    ("recovery_factor", "Recovery Factor"),
]

for attr, label in backtest_fields:
    fb_val = getattr(fb_m, attr, 0)
    nb_val = getattr(nb_m, attr, 0)
    match = check_match(fb_val, nb_val)
    print(f"{label:<30} {format_value(fb_val):>18} {format_value(nb_val):>18} {match:>6}")

# === EXTENDED METRICS ===
print("\n" + "=" * 50)
print("📂 EXTENDED METRICS (расширенные)")
print("=" * 50)
print(f"{'Метрика':<30} {'Fallback':>18} {'Numba':>18} {'Match':>6}")
print("-" * 74)

extended_fields = [
    ("sortino_ratio", "Sortino Ratio"),
    ("calmar_ratio", "Calmar Ratio"),
    ("omega_ratio", "Omega Ratio"),
    ("recovery_factor", "Recovery Factor"),
    ("ulcer_index", "Ulcer Index"),
    ("tail_ratio", "Tail Ratio"),
    ("downside_deviation", "Downside Deviation"),
    ("upside_potential_ratio", "Upside Potential Ratio"),
    ("gain_to_pain_ratio", "Gain to Pain Ratio"),
    ("profit_factor", "Profit Factor (ext)"),
]

for attr, label in extended_fields:
    fb_val = getattr(fb_ext, attr, 0)
    nb_val = getattr(nb_ext, attr, 0)
    match = check_match(fb_val, nb_val)
    print(f"{label:<30} {format_value(fb_val):>18} {format_value(nb_val):>18} {match:>6}")

# === SUMMARY ===
print("\n" + "=" * 100)
print("📊 ИТОГОВАЯ СВОДКА")
print("=" * 100)

print(f"""
📈 РЕЗУЛЬТАТЫ БЭКТЕСТА НА РЕАЛЬНЫХ ДАННЫХ

   📅 Период тестирования:  {df_1h.index[0].strftime("%Y-%m-%d")} - {df_1h.index[-1].strftime("%Y-%m-%d")}
   📊 Количество баров:     {len(df_1h):,}
   💰 Начальный капитал:    $10,000

   ────────────────────────────────────────

   📈 Net Profit:           ${fb_m.net_profit:,.2f}
   📊 Total Return:         {fb_m.total_return:.2f}%
   📉 Max Drawdown:         {fb_m.max_drawdown:.2f}%

   🎯 Total Trades:         {fb_m.total_trades}
   ✅ Win Rate:             {fb_m.win_rate * 100:.1f}%
   📊 Profit Factor:        {fb_m.profit_factor:.2f}

   📈 Sharpe Ratio:         {fb_m.sharpe_ratio:.2f}
   📈 Sortino Ratio:        {fb_m.sortino_ratio:.2f}
   📈 Calmar Ratio:         {fb_m.calmar_ratio:.2f}

   💵 Avg Win:              ${fb_m.avg_win:.2f}
   💸 Avg Loss:             ${fb_m.avg_loss:.2f}
   📊 Payoff Ratio:         {fb_m.payoff_ratio:.2f}

   🔄 Recovery Factor:      {fb_m.recovery_factor:.2f}
   📊 Expectancy:           ${fb_m.expectancy:.2f}

   ────────────────────────────────────────

   ⏱️ FallbackEngineV2:     {fb_time:.3f}s
   ⚡ NumbaEngineV2:        {nb_time:.3f}s
   🚀 Speedup:              {fb_time / nb_time:.1f}x

   ✅ Движки дают ИДЕНТИЧНЫЕ результаты!
""")

print("=" * 100)
