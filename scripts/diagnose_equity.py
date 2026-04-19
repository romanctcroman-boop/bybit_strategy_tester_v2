"""
🔍 ДИАГНОСТИКА РАСХОЖДЕНИЯ EQUITY CURVE
Fallback Sharpe=5.13 vs Numba Sharpe=-4.15
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

import numpy as np
import pandas as pd

print("=" * 100)
print("🔍 ДИАГНОСТИКА EQUITY CURVE")
print("=" * 100)

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
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


rsi = calculate_rsi(df_1h["close"], period=14)
long_entries = (rsi < 30).values
long_exits = (rsi > 70).values
short_entries = (rsi > 70).values
short_exits = (rsi < 30).values

# ============================================================================
# ЗАПУСК ДВИЖКОВ
# ============================================================================
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

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

fallback = FallbackEngineV2()
fb_result = fallback.run(input_data)

numba = NumbaEngineV2()
nb_result = numba.run(input_data)

# ============================================================================
# СРАВНЕНИЕ EQUITY CURVES
# ============================================================================
fb_eq = fb_result.equity_curve
nb_eq = nb_result.equity_curve

print(f"\nFallback Equity Curve: len={len(fb_eq)}")
print(f"  Start: ${fb_eq[0]:,.2f}")
print(f"  End:   ${fb_eq[-1]:,.2f}")
print(f"  Min:   ${fb_eq.min():,.2f}")
print(f"  Max:   ${fb_eq.max():,.2f}")

print(f"\nNumba Equity Curve: len={len(nb_eq)}")
print(f"  Start: ${nb_eq[0]:,.2f}")
print(f"  End:   ${nb_eq[-1]:,.2f}")
print(f"  Min:   ${nb_eq.min():,.2f}")
print(f"  Max:   ${nb_eq.max():,.2f}")

# Проверка на NaN/Inf
print(f"\nFallback NaN: {np.isnan(fb_eq).sum()}, Inf: {np.isinf(fb_eq).sum()}")
print(f"Numba NaN: {np.isnan(nb_eq).sum()}, Inf: {np.isinf(nb_eq).sum()}")

# Сравнение
diff = fb_eq - nb_eq
print("\nРазница Equity:")
print(f"  Mean: ${diff.mean():,.2f}")
print(f"  Max:  ${diff.max():,.2f}")
print(f"  Min:  ${diff.min():,.2f}")

# Найти точки максимального расхождения
max_diff_idx = np.argmax(np.abs(diff))
print(f"\nМаксимальное расхождение в точке {max_diff_idx}:")
print(f"  Fallback: ${fb_eq[max_diff_idx]:,.2f}")
print(f"  Numba:    ${nb_eq[max_diff_idx]:,.2f}")
print(f"  Diff:     ${diff[max_diff_idx]:,.2f}")

# ============================================================================
# ВЫЧИСЛЕНИЕ SHARPE ВРУЧНУЮ
# ============================================================================
print("\n" + "=" * 100)
print("📊 ВЫЧИСЛЕНИЕ SHARPE ВРУЧНУЮ")
print("=" * 100)


def calc_sharpe(equity):
    returns = np.diff(equity) / equity[:-1]
    returns = np.nan_to_num(returns, nan=0, posinf=0, neginf=0)
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24)
        return sharpe, returns
    return 0, returns


fb_sharpe, fb_returns = calc_sharpe(fb_eq)
nb_sharpe, nb_returns = calc_sharpe(nb_eq)

print("\nFallback Returns:")
print(f"  Mean: {fb_returns.mean():.6f}")
print(f"  Std:  {fb_returns.std():.6f}")
print(f"  Sharpe: {fb_sharpe:.2f}")

print("\nNumba Returns:")
print(f"  Mean: {nb_returns.mean():.6f}")
print(f"  Std:  {nb_returns.std():.6f}")
print(f"  Sharpe: {nb_sharpe:.2f}")

# Первые 20 equity values
print("\n" + "-" * 80)
print("Первые 20 equity values:")
print(f"{'idx':<5} {'Fallback':>15} {'Numba':>15} {'Diff':>15}")
for i in range(min(20, len(fb_eq))):
    print(f"{i:<5} ${fb_eq[i]:>13,.2f} ${nb_eq[i]:>13,.2f} ${diff[i]:>13,.2f}")

# Точки значительного расхождения
print("\n" + "-" * 80)
print("Точки со значительным расхождением (>$100):")
significant = np.where(np.abs(diff) > 100)[0]
print(f"Найдено {len(significant)} точек")
for i in significant[:10]:
    print(f"  idx={i}: Fallback=${fb_eq[i]:,.2f}, Numba=${nb_eq[i]:,.2f}, Diff=${diff[i]:,.2f}")

print("\n" + "=" * 100)
print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 100)
