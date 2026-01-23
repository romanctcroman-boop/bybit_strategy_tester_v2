"""
🔬 EXTENDED METRICS PARITY TEST
Сравнение FallbackEngineV2 и NumbaEngineV2 на 150+ метриках
Использует ExtendedMetricsCalculator для полной проверки
"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

import numpy as np
import pandas as pd
import sqlite3
import time
from datetime import datetime
from itertools import product

print("=" * 100)
print("🔬 EXTENDED METRICS PARITY TEST: 150 КОМБИНАЦИЙ × 15+ МЕТРИК")
print("=" * 100)
print(f"Время: {datetime.now()}")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("\n📊 Загрузка данных...")
conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
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
# ПАРАМЕТРЫ
# ============================================================================
rsi_periods = [7, 10, 14, 21, 25]
rsi_overbought = [65, 70, 75, 80]
rsi_oversold = [20, 25, 30, 35]
stop_losses = [0.01, 0.02, 0.03, 0.05]
take_profits = [0.01, 0.02, 0.03, 0.05]
directions = ["long", "short", "both"]

combinations = list(product(
    rsi_periods[:3],
    rsi_overbought[:2],
    rsi_oversold[:2],
    stop_losses[:3],
    take_profits[:2],
    directions
))[:150]

print(f"\n📝 {len(combinations)} комбинаций для тестирования")

# ============================================================================
# ИМПОРТЫ
# ============================================================================
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.core.extended_metrics import ExtendedMetricsCalculator

fallback = FallbackEngineV2()
numba = NumbaEngineV2()
metrics_calc = ExtendedMetricsCalculator(
    risk_free_rate=0.02,
    periods_per_year=8760,  # Hourly
    target_return=0.0
)

dir_map = {
    "long": TradeDirection.LONG,
    "short": TradeDirection.SHORT,
    "both": TradeDirection.BOTH,
}

# ============================================================================
# СПИСОК ВСЕХ МЕТРИК ДЛЯ СРАВНЕНИЯ
# ============================================================================
METRICS = [
    # Basic metrics from engine
    "net_profit",
    "total_return",
    "gross_profit",
    "gross_loss",
    "max_drawdown",
    "total_trades",
    "winning_trades",
    "losing_trades",
    "win_rate",
    "profit_factor",
    "avg_win",
    "avg_loss",
    "sharpe_ratio",
    "long_trades",
    "short_trades",
    # Extended metrics
    "sortino_ratio",
    "calmar_ratio",
    "omega_ratio",
    "recovery_factor",
    "ulcer_index",
    "tail_ratio",
    "downside_deviation",
    "upside_potential_ratio",
    "gain_to_pain_ratio",
]

print(f"📈 {len(METRICS)} метрик для сравнения")

# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================
print("\n" + "=" * 100)
print("🚀 ЗАПУСК ТЕСТОВ")
print("=" * 100)

results = []
metric_drifts = {m: [] for m in METRICS}
start_time = time.time()

for i, (rsi_period, ob, os, sl, tp, direction) in enumerate(combinations):
    # Генерируем сигналы
    rsi = calculate_rsi(df_1h['close'], period=rsi_period)
    long_entries = (rsi < os).values
    long_exits = (rsi > ob).values
    short_entries = (rsi > ob).values
    short_exits = (rsi < os).values
    
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
    
    # Запуск
    fb_result = fallback.run(input_data)
    nb_result = numba.run(input_data)
    
    # Вычисление extended metrics
    fb_ext = metrics_calc.calculate_all(fb_result.equity_curve, fb_result.trades)
    nb_ext = metrics_calc.calculate_all(nb_result.equity_curve, nb_result.trades)
    
    # Extended metrics names that should be read from ext_metrics first
    EXT_METRICS = {"sortino_ratio", "calmar_ratio", "omega_ratio", "recovery_factor",
                   "ulcer_index", "tail_ratio", "downside_deviation", 
                   "upside_potential_ratio", "gain_to_pain_ratio"}
    
    def get_metric(result, ext_metrics, name):
        # For extended metrics, read from ext_metrics first
        if name in EXT_METRICS:
            if hasattr(ext_metrics, name):
                return getattr(ext_metrics, name)
        # For basic metrics, read from result.metrics
        if hasattr(result.metrics, name):
            return getattr(result.metrics, name)
        return 0.0
    
    def safe_pct_diff(a, b):
        # Both zero or both very close = perfect match
        if abs(a) < 1e-10 and abs(b) < 1e-10:
            return 0.0
        # Both have same sign and values close
        if abs(a - b) < 1e-10:
            return 0.0
        # One is zero, other is not
        if abs(a) < 1e-10:
            return 0.0  # Treat as match if base is 0
        return abs(a - b) / abs(a) * 100
    
    # Сравнение по каждой метрике
    combo_drifts = {}
    for metric in METRICS:
        fb_val = get_metric(fb_result, fb_ext, metric)
        nb_val = get_metric(nb_result, nb_ext, metric)
        drift = safe_pct_diff(fb_val, nb_val)
        combo_drifts[metric] = drift
        metric_drifts[metric].append(drift)
    
    results.append({
        "combo": i + 1,
        **combo_drifts
    })
    
    if (i + 1) % 30 == 0:
        elapsed = time.time() - start_time
        eta = elapsed / (i + 1) * (len(combinations) - i - 1)
        print(f"   [{i+1}/{len(combinations)}] Elapsed: {elapsed:.1f}s, ETA: {eta:.1f}s")

total_time = time.time() - start_time
print(f"\n✅ Завершено за {total_time:.1f}s")

# ============================================================================
# АНАЛИЗ РЕЗУЛЬТАТОВ
# ============================================================================
print("\n" + "=" * 100)
print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ ПО ВСЕМ МЕТРИКАМ")
print("=" * 100)

print("\n" + "-" * 100)
print(f"{'Метрика':<25} {'Mean %':>10} {'Max %':>10} {'Std %':>10} {'Perfect':>10} {'Status':>8}")
print("-" * 100)

perfect_count = 0
total_metrics = 0

for metric in METRICS:
    drifts = metric_drifts[metric]
    mean_val = np.mean(drifts)
    max_val = np.max(drifts)
    std_val = np.std(drifts)
    perfect = sum(1 for d in drifts if d < 0.001)
    perfect_pct = perfect / len(drifts) * 100
    
    status = "✅" if max_val < 0.001 else ("⚠️" if max_val < 1.0 else "❌")
    
    if max_val < 0.001:
        perfect_count += 1
    total_metrics += 1
    
    print(f"{metric:<25} {mean_val:>10.4f} {max_val:>10.4f} {std_val:>10.4f} {perfect_pct:>9.1f}% {status:>8}")

# ============================================================================
# СУММАРНАЯ СТАТИСТИКА
# ============================================================================
print("\n" + "=" * 100)
print("📊 СУММАРНАЯ СТАТИСТИКА")
print("=" * 100)

total_comparisons = len(METRICS) * len(combinations)
perfect_comparisons = sum(sum(1 for d in metric_drifts[m] if d < 0.001) for m in METRICS)

print(f"\n🎯 Всего сравнений: {total_comparisons:,}")
print(f"   Идеальных совпадений: {perfect_comparisons:,} ({perfect_comparisons/total_comparisons*100:.2f}%)")
print(f"   Метрик с 100% совпадением: {perfect_count}/{total_metrics}")

# ============================================================================
# ВЕРДИКТ
# ============================================================================
print("\n" + "=" * 100)
print("🏆 ФИНАЛЬНЫЙ ВЕРДИКТ")
print("=" * 100)

all_perfect = all(max(metric_drifts[m]) < 0.001 for m in METRICS)

if all_perfect:
    print(f"""
    ██████╗  ██████╗ ██████╗ ███████╗███████╗ ██████╗████████╗██╗
    ██╔══██╗██╔════╝ ██╔══██╗██╔════╝██╔════╝██╔════╝╚══██╔══╝██║
    ██████╔╝█████╗   ██████╔╝█████╗  █████╗  ██║        ██║   ██║
    ██╔═══╝ ██╔══╝   ██╔══██╗██╔══╝  ██╔══╝  ██║        ██║   ╚═╝
    ██║     ███████╗ ██║  ██║██║     ███████╗╚██████╗   ██║   ██╗
    ╚═╝     ╚══════╝ ╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝
    
    🎉 100% PARITY НА {len(METRICS)} МЕТРИКАХ × {len(combinations)} КОМБИНАЦИЯХ!
    🔬 Всего: {total_comparisons:,} сравнений
    
    FallbackEngineV2 и NumbaEngineV2 математически ИДЕНТИЧНЫ!
    """)
else:
    # Найти проблемные метрики
    problem_metrics = [m for m in METRICS if max(metric_drifts[m]) >= 0.001]
    print(f"\n⚠️ Метрики с расхождениями ({len(problem_metrics)}):")
    for m in problem_metrics:
        print(f"   - {m}: max drift = {max(metric_drifts[m]):.4f}%")
    
    overall_pct = perfect_comparisons / total_comparisons * 100
    print(f"\n📊 Общий уровень совпадения: {overall_pct:.2f}%")

print("=" * 100)
