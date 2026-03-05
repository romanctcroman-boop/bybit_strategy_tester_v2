"""
🔬 MEGA PARITY TEST: 150 КОМБИНАЦИЙ ПАРАМЕТРОВ
Сравнение FallbackEngineV2 и NumbaEngineV2
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
print("🔬 MEGA PARITY TEST: 150 КОМБИНАЦИЙ")
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
    LIMIT 1000
""",
    conn,
)
df_1h["open_time"] = pd.to_datetime(df_1h["open_time"], unit="ms")
df_1h.set_index("open_time", inplace=True)
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
# ПАРАМЕТРЫ ДЛЯ ТЕСТА
# ============================================================================
rsi_periods = [7, 10, 14, 21, 25]
rsi_overbought = [65, 70, 75, 80]
rsi_oversold = [20, 25, 30, 35]
stop_losses = [0.01, 0.02, 0.03, 0.05]
take_profits = [0.01, 0.02, 0.03, 0.05]
directions = ["long", "short", "both"]

# Генерируем 150 комбинаций
combinations = list(
    product(
        rsi_periods[:3],  # 3 RSI periods
        rsi_overbought[:2],  # 2 OB levels
        rsi_oversold[:2],  # 2 OS levels
        stop_losses[:3],  # 3 SL levels
        take_profits[:2],  # 2 TP levels
        directions,  # 3 directions
    )
)

# Ограничиваем до 150
combinations = combinations[:150]
print(f"\n📝 {len(combinations)} комбинаций для тестирования")

# ============================================================================
# ИМПОРТ ДВИЖКОВ
# ============================================================================
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

fallback = FallbackEngineV2()
numba = NumbaEngineV2()

dir_map = {
    "long": TradeDirection.LONG,
    "short": TradeDirection.SHORT,
    "both": TradeDirection.BOTH,
}

# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================
print("\n" + "=" * 100)
print("🚀 ЗАПУСК ТЕСТОВ")
print("=" * 100)

results = []
start_time = time.time()

for i, (rsi_period, ob, os, sl, tp, direction) in enumerate(combinations):
    # Генерируем сигналы
    rsi = calculate_rsi(df_1h["close"], period=rsi_period)
    long_entries = (rsi < os).values
    long_exits = (rsi > ob).values
    short_entries = (rsi > ob).values
    short_exits = (rsi < os).values

    # Создаём input
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
    nb_result = numba.run(input_data)

    # Сравнение метрик
    fb_m = fb_result.metrics
    nb_m = nb_result.metrics

    # Расчёт drift
    def safe_pct_diff(a, b):
        if a == 0 and b == 0:
            return 0.0
        if a == 0:
            return 100.0 if b != 0 else 0.0
        return abs(a - b) / abs(a) * 100

    profit_drift = safe_pct_diff(fb_m.net_profit, nb_m.net_profit)
    sharpe_drift = safe_pct_diff(fb_m.sharpe_ratio, nb_m.sharpe_ratio)
    dd_drift = safe_pct_diff(fb_m.max_drawdown, nb_m.max_drawdown)
    winrate_drift = safe_pct_diff(fb_m.win_rate, nb_m.win_rate)
    trades_drift = safe_pct_diff(fb_m.total_trades, nb_m.total_trades)
    pf_drift = safe_pct_diff(fb_m.profit_factor, nb_m.profit_factor)

    results.append(
        {
            "combo": i + 1,
            "rsi": rsi_period,
            "ob": ob,
            "os": os,
            "sl": sl,
            "tp": tp,
            "dir": direction,
            "fb_trades": fb_m.total_trades,
            "nb_trades": nb_m.total_trades,
            "fb_profit": fb_m.net_profit,
            "nb_profit": nb_m.net_profit,
            "fb_sharpe": fb_m.sharpe_ratio,
            "nb_sharpe": nb_m.sharpe_ratio,
            "fb_dd": fb_m.max_drawdown,
            "nb_dd": nb_m.max_drawdown,
            "fb_wr": fb_m.win_rate,
            "nb_wr": nb_m.win_rate,
            "profit_drift": profit_drift,
            "sharpe_drift": sharpe_drift,
            "dd_drift": dd_drift,
            "winrate_drift": winrate_drift,
            "trades_drift": trades_drift,
            "pf_drift": pf_drift,
        }
    )

    # Прогресс
    if (i + 1) % 25 == 0:
        elapsed = time.time() - start_time
        eta = elapsed / (i + 1) * (len(combinations) - i - 1)
        print(f"   [{i + 1}/{len(combinations)}] Elapsed: {elapsed:.1f}s, ETA: {eta:.1f}s")

total_time = time.time() - start_time
print(f"\n✅ Завершено за {total_time:.1f}s")

# ============================================================================
# АНАЛИЗ РЕЗУЛЬТАТОВ
# ============================================================================
print("\n" + "=" * 100)
print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ")
print("=" * 100)

df = pd.DataFrame(results)

# Метрики drift
drift_cols = ["profit_drift", "sharpe_drift", "dd_drift", "winrate_drift", "trades_drift", "pf_drift"]
drift_names = ["Net Profit", "Sharpe Ratio", "Max Drawdown", "Win Rate", "Total Trades", "Profit Factor"]

print("\n📈 СТАТИСТИКА DRIFT ПО МЕТРИКАМ:")
print("-" * 80)
print(f"{'Метрика':<20} {'Mean %':>10} {'Max %':>10} {'Min %':>10} {'Std %':>10} {'Zero %':>10}")
print("-" * 80)

for col, name in zip(drift_cols, drift_names, strict=False):
    mean_val = df[col].mean()
    max_val = df[col].max()
    min_val = df[col].min()
    std_val = df[col].std()
    zero_pct = (df[col] == 0).sum() / len(df) * 100

    status = "✅" if mean_val < 0.01 and max_val < 1.0 else "⚠️"
    print(f"{name:<20} {mean_val:>10.4f} {max_val:>10.4f} {min_val:>10.4f} {std_val:>10.4f} {zero_pct:>9.1f}% {status}")

# Идеальные совпадения (0% drift)
print("\n" + "-" * 80)
perfect_profit = (df["profit_drift"] < 0.001).sum()
perfect_sharpe = (df["sharpe_drift"] < 0.001).sum()
perfect_dd = (df["dd_drift"] < 0.001).sum()
perfect_trades = (df["trades_drift"] == 0).sum()

print("\n🎯 ИДЕАЛЬНЫЕ СОВПАДЕНИЯ (<0.001% drift):")
print(f"   Net Profit:    {perfect_profit}/{len(df)} ({perfect_profit / len(df) * 100:.1f}%)")
print(f"   Sharpe Ratio:  {perfect_sharpe}/{len(df)} ({perfect_sharpe / len(df) * 100:.1f}%)")
print(f"   Max Drawdown:  {perfect_dd}/{len(df)} ({perfect_dd / len(df) * 100:.1f}%)")
print(f"   Total Trades:  {perfect_trades}/{len(df)} ({perfect_trades / len(df) * 100:.1f}%)")

# Комбинации с расхождениями
discrepancies = df[df["profit_drift"] > 0.001]
if len(discrepancies) > 0:
    print(f"\n⚠️ Комбинации с расхождением Net Profit > 0.001%: {len(discrepancies)}")
    for _, row in discrepancies.head(5).iterrows():
        print(
            f"   #{row['combo']}: RSI({row['rsi']},{row['ob']},{row['os']}) "
            f"SL={row['sl'] * 100:.0f}% TP={row['tp'] * 100:.0f}% {row['dir']} "
            f"drift={row['profit_drift']:.4f}%"
        )
else:
    print("\n🎉 ВСЕ КОМБИНАЦИИ ИМЕЮТ ИДЕАЛЬНОЕ СОВПАДЕНИЕ!")

# ============================================================================
# ФИНАЛЬНЫЙ ВЕРДИКТ
# ============================================================================
print("\n" + "=" * 100)
print("🏆 ФИНАЛЬНЫЙ ВЕРДИКТ")
print("=" * 100)

all_perfect = (
    df["profit_drift"].max() < 0.001
    and df["sharpe_drift"].max() < 0.001
    and df["dd_drift"].max() < 0.001
    and df["trades_drift"].max() == 0
)

if all_perfect:
    print("""
    ██████╗  █████╗ ███████╗███████╗███████╗██████╗
    ██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗
    ██████╔╝███████║███████╗███████╗█████╗  ██║  ██║
    ██╔═══╝ ██╔══██║╚════██║╚════██║██╔══╝  ██║  ██║
    ██║     ██║  ██║███████║███████║███████╗██████╔╝
    ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═════╝

    🎉 100% PARITY НА {len(df)} КОМБИНАЦИЯХ!

    FallbackEngineV2 и NumbaEngineV2 дают ИДЕНТИЧНЫЕ результаты.
    """)
else:
    avg_profit_drift = df["profit_drift"].mean()
    avg_sharpe_drift = df["sharpe_drift"].mean()

    print(f"""
    Средний drift Net Profit: {avg_profit_drift:.4f}%
    Средний drift Sharpe:     {avg_sharpe_drift:.4f}%

    {"✅ ПРИЕМЛЕМОЕ СОВПАДЕНИЕ" if avg_profit_drift < 1.0 else "⚠️ ТРЕБУЕТСЯ ПРОВЕРКА"}
    """)

print("=" * 100)
