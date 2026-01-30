"""
🔍 ДИАГНОСТИКА РАСХОЖДЕНИЯ ДВИЖКОВ
Почему Fallback: 59 trades, Numba: 58 trades?
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime

print("=" * 100)
print("🔍 ДИАГНОСТИКА РАСХОЖДЕНИЯ: Fallback (59) vs Numba (58) trades")
print("=" * 100)

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))

df_1h = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
    LIMIT 1000
""", conn)
df_1h['open_time'] = pd.to_datetime(df_1h['open_time'], unit='ms')
df_1h.set_index('open_time', inplace=True)
conn.close()

print(f"Данные: {len(df_1h)} баров")

# RSI сигналы
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

rsi = calculate_rsi(df_1h['close'], period=14)
long_entries = (rsi < 30).values
long_exits = (rsi > 70).values
short_entries = (rsi > 70).values
short_exits = (rsi < 30).values

print(f"Long entries: {long_entries.sum()}, Short entries: {short_entries.sum()}")

# ============================================================================
# ЗАПУСК ДВИЖКОВ И СБОР СДЕЛОК
# ============================================================================
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

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
    stop_loss=0.03,
    take_profit=0.02,
    direction=TradeDirection.BOTH,
    taker_fee=0.001,
    slippage=0.0005,
    use_bar_magnifier=False,
)

print("\n" + "=" * 100)
print("Запуск Fallback...")
fallback = FallbackEngineV2()
fb_result = fallback.run(input_data)

print("Запуск Numba...")
numba = NumbaEngineV2()
nb_result = numba.run(input_data)

# ============================================================================
# СРАВНЕНИЕ СДЕЛОК
# ============================================================================
print("\n" + "=" * 100)
print("📊 СРАВНЕНИЕ СДЕЛОК")
print("=" * 100)

print(f"\nFallback: {len(fb_result.trades)} сделок")
print(f"Numba: {len(nb_result.trades)} сделок")
print(f"Разница: {len(fb_result.trades) - len(nb_result.trades)} сделок")

# Создадим таблицы для сравнения
fb_trades = [(t.entry_time, t.direction, t.entry_price, t.exit_price, t.pnl, t.exit_reason.name) 
             for t in fb_result.trades]
nb_trades = [(t.entry_time, t.direction, t.entry_price, t.exit_price, t.pnl, t.exit_reason.name) 
             for t in nb_result.trades]

print("\n" + "-" * 100)
print("FALLBACK TRADES (первые 10):")
print("-" * 100)
print(f"{'#':<3} {'Entry Time':<22} {'Dir':<6} {'Entry Price':>12} {'Exit Price':>12} {'PnL':>12} {'Reason':<12}")
for i, t in enumerate(fb_trades[:10]):
    print(f"{i+1:<3} {str(t[0]):<22} {t[1]:<6} {t[2]:>12.2f} {t[3]:>12.2f} {t[4]:>12.2f} {t[5]:<12}")

print("\n" + "-" * 100)
print("NUMBA TRADES (первые 10):")
print("-" * 100)
print(f"{'#':<3} {'Entry Time':<22} {'Dir':<6} {'Entry Price':>12} {'Exit Price':>12} {'PnL':>12} {'Reason':<12}")
for i, t in enumerate(nb_trades[:10]):
    print(f"{i+1:<3} {str(t[0]):<22} {t[1]:<6} {t[2]:>12.2f} {t[3]:>12.2f} {t[4]:>12.2f} {t[5]:<12}")

# ============================================================================
# НАЙТИ ОТЛИЧАЮЩУЮСЯ СДЕЛКУ
# ============================================================================
print("\n" + "=" * 100)
print("🔍 ПОИСК ОТЛИЧИЙ")
print("=" * 100)

# Создадим set по entry_time для быстрого поиска
fb_entry_times = set(t[0] for t in fb_trades)
nb_entry_times = set(t[0] for t in nb_trades)

only_in_fb = fb_entry_times - nb_entry_times
only_in_nb = nb_entry_times - fb_entry_times

print(f"\nСделки только в Fallback ({len(only_in_fb)}):")
for t in fb_trades:
    if t[0] in only_in_fb:
        print(f"  {t[0]} | {t[1]} | entry={t[2]:.2f} | exit={t[3]:.2f} | PnL={t[4]:.2f} | {t[5]}")

print(f"\nСделки только в Numba ({len(only_in_nb)}):")
for t in nb_trades:
    if t[0] in only_in_nb:
        print(f"  {t[0]} | {t[1]} | entry={t[2]:.2f} | exit={t[3]:.2f} | PnL={t[4]:.2f} | {t[5]}")

# ============================================================================
# ДЕТАЛЬНОЕ СРАВНЕНИЕ СОВПАДАЮЩИХ СДЕЛОК
# ============================================================================
print("\n" + "=" * 100)
print("📊 СРАВНЕНИЕ СОВПАДАЮЩИХ СДЕЛОК (с расхождениями)")
print("=" * 100)

common_times = fb_entry_times & nb_entry_times
fb_by_time = {t[0]: t for t in fb_trades}
nb_by_time = {t[0]: t for t in nb_trades}

diffs = []
for time in sorted(common_times):
    fb_t = fb_by_time[time]
    nb_t = nb_by_time[time]
    
    pnl_diff = abs(fb_t[4] - nb_t[4])
    entry_diff = abs(fb_t[2] - nb_t[2])
    exit_diff = abs(fb_t[3] - nb_t[3])
    
    if pnl_diff > 0.01 or entry_diff > 0.01 or exit_diff > 0.01:
        diffs.append((time, fb_t, nb_t, pnl_diff))

print(f"Найдено {len(diffs)} сделок с расхождениями > $0.01:")
for time, fb_t, nb_t, pnl_diff in diffs[:10]:
    print(f"\n  Time: {time}")
    print(f"    Fallback: {fb_t[1]:<6} entry={fb_t[2]:.2f} exit={fb_t[3]:.2f} PnL={fb_t[4]:.2f} {fb_t[5]}")
    print(f"    Numba:    {nb_t[1]:<6} entry={nb_t[2]:.2f} exit={nb_t[3]:.2f} PnL={nb_t[4]:.2f} {nb_t[5]}")
    print(f"    Diff: PnL ${pnl_diff:.2f}")

# ============================================================================
# СУММАРНАЯ СТАТИСТИКА
# ============================================================================
print("\n" + "=" * 100)
print("📊 СУММАРНАЯ СТАТИСТИКА")
print("=" * 100)

fb_total_pnl = sum(t[4] for t in fb_trades)
nb_total_pnl = sum(t[4] for t in nb_trades)

print(f"\nFallback Total PnL: ${fb_total_pnl:,.2f}")
print(f"Numba Total PnL:    ${nb_total_pnl:,.2f}")
print(f"Разница:            ${fb_total_pnl - nb_total_pnl:,.2f}")

# Причина отсутствующей сделки
if only_in_fb:
    missing_pnl = sum(t[4] for t in fb_trades if t[0] in only_in_fb)
    print(f"\nPnL отсутствующих в Numba сделок: ${missing_pnl:,.2f}")
    print(f"Объясняет разницу? {abs(missing_pnl - (fb_total_pnl - nb_total_pnl)) < 1:.0f}")

print("\n" + "=" * 100)
print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 100)
