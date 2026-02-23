"""
🔬 ТЕСТ СРАВНЕНИЯ ДВИЖКОВ V2
Сравнивает Fallback (эталон) и Numba с Bar Magnifier
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
from datetime import datetime

import pandas as pd

print("=" * 100)
print("🔬 ТЕСТ СРАВНЕНИЯ ДВИЖКОВ V2")
print("=" * 100)
print(f"Время: {datetime.now()}")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("\n📊 ЗАГРУЗКА ДАННЫХ")

conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))

# Основные данные (1h)
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

# 1-минутные данные для Bar Magnifier
df_1m = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '1'
    ORDER BY open_time ASC
""", conn)
df_1m['open_time'] = pd.to_datetime(df_1m['open_time'], unit='ms')
df_1m.set_index('open_time', inplace=True)

conn.close()

print(f"   1h данные: {len(df_1h)} баров ({df_1h.index.min().date()} - {df_1h.index.max().date()})")
print(f"   1m данные: {len(df_1m)} баров для Bar Magnifier")

# ============================================================================
# ГЕНЕРАЦИЯ RSI СИГНАЛОВ
# ============================================================================
print("\n📈 ГЕНЕРАЦИЯ СИГНАЛОВ RSI(14, 70, 30)")

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

print(f"   Long entries:  {long_entries.sum()}")
print(f"   Short entries: {short_entries.sum()}")

# ============================================================================
# СОЗДАНИЕ BACKTEST INPUT
# ============================================================================
from backend.backtesting.interfaces import BacktestInput, TradeDirection

# Тест БЕЗ Bar Magnifier
input_without_bm = BacktestInput(
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
    stop_loss=0.03,       # 3%
    take_profit=0.02,     # 2%
    direction=TradeDirection.BOTH,
    taker_fee=0.001,
    slippage=0.0005,
    use_bar_magnifier=False,
)

# Тест С Bar Magnifier
input_with_bm = BacktestInput(
    candles=df_1h,
    candles_1m=df_1m,
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
    use_bar_magnifier=True,
)

# ============================================================================
# ТЕСТ ДВИЖКОВ
# ============================================================================
print("\n" + "=" * 100)
print("🚀 ТЕСТИРОВАНИЕ ДВИЖКОВ")
print("=" * 100)

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

engines = [
    FallbackEngineV2(),
    NumbaEngineV2(),
]

results = {}

for engine in engines:
    print(f"\n{'='*50}")
    print(f"📊 {engine.name}")
    print(f"   Bar Magnifier: {'✅' if engine.supports_bar_magnifier else '❌'}")
    print(f"   Parallel: {'✅' if engine.supports_parallel else '❌'}")
    print(f"{'='*50}")

    # Тест БЕЗ Bar Magnifier
    print("\n   [1] Без Bar Magnifier...")
    result_no_bm = engine.run(input_without_bm)

    print(f"       Время: {result_no_bm.execution_time:.3f}s")
    print(f"       Trades: {result_no_bm.metrics.total_trades}")
    print(f"       Net Profit: ${result_no_bm.metrics.net_profit:,.2f}")
    print(f"       Sharpe: {result_no_bm.metrics.sharpe_ratio:.2f}")
    print(f"       Max DD: {result_no_bm.metrics.max_drawdown:.2f}%")
    print(f"       Win Rate: {result_no_bm.metrics.win_rate*100:.1f}%")

    # Тест С Bar Magnifier (если поддерживается)
    if engine.supports_bar_magnifier:
        print("\n   [2] С Bar Magnifier...")
        result_with_bm = engine.run(input_with_bm)

        print(f"       Время: {result_with_bm.execution_time:.3f}s")
        print(f"       Trades: {result_with_bm.metrics.total_trades}")
        print(f"       Net Profit: ${result_with_bm.metrics.net_profit:,.2f}")
        print(f"       Sharpe: {result_with_bm.metrics.sharpe_ratio:.2f}")
        print(f"       Max DD: {result_with_bm.metrics.max_drawdown:.2f}%")
        print(f"       Win Rate: {result_with_bm.metrics.win_rate*100:.1f}%")

        results[engine.name] = {
            "no_bm": result_no_bm,
            "with_bm": result_with_bm,
        }
    else:
        results[engine.name] = {
            "no_bm": result_no_bm,
            "with_bm": None,
        }

# ============================================================================
# СРАВНЕНИЕ РЕЗУЛЬТАТОВ
# ============================================================================
print("\n" + "=" * 100)
print("📊 СРАВНЕНИЕ ДВИЖКОВ (БЕЗ Bar Magnifier)")
print("=" * 100)

print(f"\n{'Engine':<20} {'Time':>10} {'Trades':>8} {'Net Profit':>12} {'Sharpe':>8} {'Max DD':>8} {'Win Rate':>10}")
print("-" * 100)

fallback_result = results["FallbackEngineV2"]["no_bm"]

for name, data in results.items():
    r = data["no_bm"]
    m = r.metrics
    speedup = fallback_result.execution_time / r.execution_time if r.execution_time > 0 else 0

    print(f"{name:<20} {r.execution_time:>8.3f}s {m.total_trades:>8} ${m.net_profit:>10,.2f} "
          f"{m.sharpe_ratio:>8.2f} {m.max_drawdown:>7.2f}% {m.win_rate*100:>9.1f}%")

    if name != "FallbackEngineV2":
        print(f"{'  Speedup:':<20} {speedup:>8.1f}x")

        # Drift calculation
        ref = fallback_result.metrics
        drift_profit = abs(m.net_profit - ref.net_profit) / abs(ref.net_profit) * 100 if ref.net_profit != 0 else 0
        drift_sharpe = abs(m.sharpe_ratio - ref.sharpe_ratio) / abs(ref.sharpe_ratio) * 100 if ref.sharpe_ratio != 0 else 0

        print(f"{'  Profit Drift:':<20} {drift_profit:>8.2f}%")
        print(f"{'  Sharpe Drift:':<20} {drift_sharpe:>8.2f}%")

print("\n" + "=" * 100)
print("📊 СРАВНЕНИЕ С BAR MAGNIFIER")
print("=" * 100)

for name, data in results.items():
    if data["with_bm"]:
        no_bm = data["no_bm"].metrics
        with_bm = data["with_bm"].metrics

        print(f"\n{name}:")
        print(f"   {'Metric':<20} {'Без BM':>12} {'С BM':>12} {'Разница':>12}")
        print(f"   {'-'*60}")
        print(f"   {'Trades':<20} {no_bm.total_trades:>12} {with_bm.total_trades:>12} {with_bm.total_trades - no_bm.total_trades:>12}")
        print(f"   {'Net Profit':<20} ${no_bm.net_profit:>10,.2f} ${with_bm.net_profit:>10,.2f} ${with_bm.net_profit - no_bm.net_profit:>10,.2f}")
        print(f"   {'Sharpe':<20} {no_bm.sharpe_ratio:>12.2f} {with_bm.sharpe_ratio:>12.2f} {with_bm.sharpe_ratio - no_bm.sharpe_ratio:>12.2f}")
        print(f"   {'Max DD':<20} {no_bm.max_drawdown:>11.2f}% {with_bm.max_drawdown:>11.2f}% {with_bm.max_drawdown - no_bm.max_drawdown:>11.2f}%")
        print(f"   {'Win Rate':<20} {no_bm.win_rate*100:>11.1f}% {with_bm.win_rate*100:>11.1f}% {(with_bm.win_rate - no_bm.win_rate)*100:>11.1f}%")

print("\n" + "=" * 100)
print("✅ ТЕСТ ЗАВЕРШЁН")
print("=" * 100)
