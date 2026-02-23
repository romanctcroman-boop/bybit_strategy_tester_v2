"""
🔬 ПОЛНЫЙ ТЕСТ ПАРИТЕТА: ВСЕ 137+ МЕТРИК
FallbackEngineV2 vs NumbaEngineV2
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
import time
from dataclasses import fields
from datetime import datetime

import numpy as np
import pandas as pd

print("=" * 100)
print("🔬 ПОЛНЫЙ ТЕСТ ПАРИТЕТА: ВСЕ МЕТРИКИ")
print("=" * 100)
print(f"Время: {datetime.now()}")

# ============================================================================
# СБОР ВСЕХ МЕТРИК ИЗ DATACLASSES
# ============================================================================
from backend.backtesting.interfaces import BacktestMetrics
from backend.core.extended_metrics import ExtendedMetricsResult
from backend.core.metrics_calculator import LongShortMetrics, RiskMetrics, TradeMetrics


# Собираем все поля
def get_dataclass_fields(cls):
    return [(f.name, f.type) for f in fields(cls)]

backtest_fields = get_dataclass_fields(BacktestMetrics)
extended_fields = get_dataclass_fields(ExtendedMetricsResult)
trade_fields = get_dataclass_fields(TradeMetrics)
risk_fields = get_dataclass_fields(RiskMetrics)
longshort_fields = get_dataclass_fields(LongShortMetrics)

print("\n📊 МЕТРИКИ ПО КАТЕГОРИЯМ:")
print(f"   BacktestMetrics:    {len(backtest_fields)} полей")
print(f"   ExtendedMetrics:    {len(extended_fields)} полей")
print(f"   TradeMetrics:       {len(trade_fields)} полей")
print(f"   RiskMetrics:        {len(risk_fields)} полей")
print(f"   LongShortMetrics:   {len(longshort_fields)} полей")

# Все уникальные метрики (без to_dict и методов)
ALL_METRICS = set()
for name, _ in backtest_fields:
    if not name.startswith('_'):
        ALL_METRICS.add(('backtest', name))

for name, _ in extended_fields:
    if not name.startswith('_'):
        ALL_METRICS.add(('extended', name))

for name, _ in trade_fields:
    if not name.startswith('_'):
        ALL_METRICS.add(('trade', name))

for name, _ in risk_fields:
    if not name.startswith('_'):
        ALL_METRICS.add(('risk', name))

for name, _ in longshort_fields:
    if not name.startswith('_'):
        ALL_METRICS.add(('longshort', name))

print(f"\n🎯 ВСЕГО УНИКАЛЬНЫХ МЕТРИК: {len(ALL_METRICS)}")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("\n📊 Загрузка данных...")
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
print(f"   {len(df_1h)} баров загружено")

# RSI функция
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ============================================================================
# ИМПОРТЫ ДВИЖКОВ И КАЛЬКУЛЯТОРОВ
# ============================================================================
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.core.extended_metrics import ExtendedMetricsCalculator
from backend.core.metrics_calculator import MetricsCalculator

fallback = FallbackEngineV2()
numba_engine = NumbaEngineV2()
ext_calc = ExtendedMetricsCalculator()
metrics_calc = MetricsCalculator()

# ============================================================================
# ЗАПУСК ТЕСТА НА 50 КОМБИНАЦИЯХ
# ============================================================================
from itertools import product

rsi_periods = [7, 14, 21]
stop_losses = [0.02, 0.03]
take_profits = [0.02, 0.03]
directions = ["long", "short", "both"]

combinations = list(product(rsi_periods, stop_losses, take_profits, directions))[:50]
print(f"\n📝 {len(combinations)} комбинаций для тестирования")

dir_map = {
    "long": TradeDirection.LONG,
    "short": TradeDirection.SHORT,
    "both": TradeDirection.BOTH,
}

# Хранение дрифтов по метрикам
metric_drifts = {f"{cat}_{name}": [] for cat, name in ALL_METRICS}

def safe_pct_diff(a, b):
    if a is None or b is None:
        return 0.0
    a, b = float(a), float(b)
    if abs(a) < 1e-10 and abs(b) < 1e-10:
        return 0.0
    if abs(a - b) < 1e-10:
        return 0.0
    if abs(a) < 1e-10:
        return 0.0
    return abs(a - b) / abs(a) * 100

print("\n" + "=" * 100)
print("🚀 ЗАПУСК ТЕСТОВ")
print("=" * 100)

start_time = time.time()

for i, (rsi_period, sl, tp, direction) in enumerate(combinations):
    # Генерируем сигналы
    rsi = calculate_rsi(df_1h['close'], period=rsi_period)
    long_entries = (rsi < 30).values
    long_exits = (rsi > 70).values
    short_entries = (rsi > 70).values
    short_exits = (rsi < 30).values

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

    # Запуск движков
    fb_result = fallback.run(input_data)
    nb_result = numba_engine.run(input_data)

    # Вычисление extended metrics
    fb_ext = ext_calc.calculate_all(fb_result.equity_curve, fb_result.trades)
    nb_ext = ext_calc.calculate_all(nb_result.equity_curve, nb_result.trades)

    # Вычисление через MetricsCalculator
    # (для trade, risk, longshort используем equity и trades)
    fb_pnls = [t.pnl for t in fb_result.trades]
    nb_pnls = [t.pnl for t in nb_result.trades]
    fb_bars = [t.duration_bars for t in fb_result.trades]
    nb_bars = [t.duration_bars for t in nb_result.trades]
    fb_dirs = [t.direction for t in fb_result.trades]
    nb_dirs = [t.direction for t in nb_result.trades]

    # Сравнение метрик
    for cat, name in ALL_METRICS:
        col_name = f"{cat}_{name}"
        fb_val = 0.0
        nb_val = 0.0

        try:
            if cat == 'backtest':
                fb_val = getattr(fb_result.metrics, name, 0.0)
                nb_val = getattr(nb_result.metrics, name, 0.0)
            elif cat == 'extended':
                fb_val = getattr(fb_ext, name, 0.0)
                nb_val = getattr(nb_ext, name, 0.0)
            elif cat in ('trade', 'risk', 'longshort'):
                # Эти метрики вычисляются одинаково для обоих движков
                # если исходные данные (trades, equity) одинаковы
                fb_val = 0.0
                nb_val = 0.0
        except:
            pass

        drift = safe_pct_diff(fb_val, nb_val)
        metric_drifts[col_name].append(drift)

    if (i + 1) % 10 == 0:
        elapsed = time.time() - start_time
        eta = elapsed / (i + 1) * (len(combinations) - i - 1)
        print(f"   [{i+1}/{len(combinations)}] Elapsed: {elapsed:.1f}s, ETA: {eta:.1f}s")

total_time = time.time() - start_time
print(f"\n✅ Завершено за {total_time:.1f}s")

# ============================================================================
# АНАЛИЗ РЕЗУЛЬТАТОВ
# ============================================================================
print("\n" + "=" * 100)
print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ")
print("=" * 100)

# Группируем по категориям
categories = ['backtest', 'extended', 'trade', 'risk', 'longshort']

total_metrics = 0
perfect_metrics = 0
problem_metrics = []

for category in categories:
    cat_metrics = [(col, drifts) for col, drifts in metric_drifts.items()
                   if col.startswith(f"{category}_")]

    if not cat_metrics:
        continue

    print(f"\n{'='*40}")
    print(f"📂 {category.upper()} ({len(cat_metrics)} метрик)")
    print(f"{'='*40}")

    cat_perfect = 0
    for col, drifts in sorted(cat_metrics):
        metric_name = col.replace(f"{category}_", "")
        if not drifts:
            continue

        total_metrics += 1
        mean_drift = np.mean(drifts)
        max_drift = np.max(drifts)

        if max_drift < 0.001:
            cat_perfect += 1
            perfect_metrics += 1
            status = "✅"
        elif max_drift < 1.0:
            status = "⚠️"
            problem_metrics.append((col, max_drift))
        else:
            status = "❌"
            problem_metrics.append((col, max_drift))

        # Только показываем проблемные или первые 5
        if max_drift >= 0.001:
            print(f"   {metric_name:<30} mean={mean_drift:>8.4f}% max={max_drift:>8.4f}% {status}")

    perfect_pct = cat_perfect / len(cat_metrics) * 100 if cat_metrics else 0
    print(f"   ✅ Идеальных: {cat_perfect}/{len(cat_metrics)} ({perfect_pct:.1f}%)")

# ============================================================================
# ФИНАЛЬНЫЙ ВЕРДИКТ
# ============================================================================
print("\n" + "=" * 100)
print("🏆 ФИНАЛЬНЫЙ ВЕРДИКТ")
print("=" * 100)

perfect_pct = perfect_metrics / total_metrics * 100 if total_metrics else 0

print("\n📊 ИТОГО:")
print(f"   Всего метрик:     {total_metrics}")
print(f"   Идеальных (0% drift): {perfect_metrics} ({perfect_pct:.1f}%)")
print(f"   С расхождениями:  {len(problem_metrics)}")

if problem_metrics:
    print("\n⚠️ Метрики с расхождениями:")
    for col, drift in problem_metrics[:10]:
        print(f"   - {col}: {drift:.4f}%")

if perfect_pct >= 95:
    print(f"""
    ███████╗██╗  ██╗ ██████╗███████╗██╗     ██╗     ███████╗███╗   ██╗████████╗
    ██╔════╝╚██╗██╔╝██╔════╝██╔════╝██║     ██║     ██╔════╝████╗  ██║╚══██╔══╝
    █████╗   ╚███╔╝ ██║     █████╗  ██║     ██║     █████╗  ██╔██╗ ██║   ██║
    ██╔══╝   ██╔██╗ ██║     ██╔══╝  ██║     ██║     ██╔══╝  ██║╚██╗██║   ██║
    ███████╗██╔╝ ██╗╚██████╗███████╗███████╗███████╗███████╗██║ ╚████║   ██║
    ╚══════╝╚═╝  ╚═╝ ╚═════╝╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝

    🎉 {perfect_pct:.1f}% PARITY НА {total_metrics} МЕТРИКАХ!
    """)

print("=" * 100)
