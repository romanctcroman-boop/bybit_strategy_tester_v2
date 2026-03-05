"""
🔬 АУДИТ ПАРИТЕТА: FallbackEngineV2 vs GPU Optimizer vs VectorBT

Цель: Определить расхождения и план работ для достижения 100% паритета.
Эталон: FallbackEngineV2 (его нельзя менять)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

print("=" * 120)
print("🔬 АУДИТ ПАРИТЕТА: FallbackEngineV2 vs GPU vs VectorBT")
print("=" * 120)
print(f"Время: {datetime.now()}")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("\n📊 Загрузка данных...")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))

df = pd.read_sql(
    """
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
    LIMIT 500
""",
    conn,
)
df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
df.set_index("open_time", inplace=True)
conn.close()

print(f"   📅 Период: {df.index[0]} — {df.index[-1]}")
print(f"   📊 Баров: {len(df)}")


# ============================================================================
# RSI СИГНАЛЫ
# ============================================================================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


rsi = calculate_rsi(df["close"], period=14)
long_entries = (rsi < 30).values
long_exits = (rsi > 70).values
short_entries = (rsi > 70).values
short_exits = (rsi < 30).values

# Параметры теста
TEST_CONFIG = {
    "symbol": "BTCUSDT",
    "initial_capital": 10000.0,
    "position_size": 0.10,
    "leverage": 10,
    "stop_loss": 0.02,
    "take_profit": 0.04,
    "commission": 0.001,
    "slippage": 0.0005,
}

# ============================================================================
# ТЕСТ 1: FallbackEngineV2 (ЭТАЛОН)
# ============================================================================
print("\n" + "=" * 80)
print("🎯 ТЕСТ 1: FallbackEngineV2 (ЭТАЛОН)")
print("=" * 80)

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

input_data = BacktestInput(
    candles=df,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    symbol=TEST_CONFIG["symbol"],
    interval="60",
    initial_capital=TEST_CONFIG["initial_capital"],
    position_size=TEST_CONFIG["position_size"],
    leverage=TEST_CONFIG["leverage"],
    stop_loss=TEST_CONFIG["stop_loss"],
    take_profit=TEST_CONFIG["take_profit"],
    direction=TradeDirection.BOTH,
    taker_fee=TEST_CONFIG["commission"],
    slippage=TEST_CONFIG["slippage"],
    use_bar_magnifier=False,
)

fallback = FallbackEngineV2()
fb_result = fallback.run(input_data)

print(f"   ✅ Trades: {len(fb_result.trades)}")
print(f"   ✅ Net Profit: ${fb_result.metrics.net_profit:,.2f}")
print(f"   ✅ Total Return: {fb_result.metrics.total_return:.4f}%")
print(f"   ✅ Win Rate: {fb_result.metrics.win_rate:.4f}")
print(f"   ✅ Sharpe Ratio: {fb_result.metrics.sharpe_ratio:.4f}")
print(f"   ✅ Max Drawdown: {fb_result.metrics.max_drawdown:.4f}%")

# Сохраним эталонные значения
REFERENCE = {
    "trades": len(fb_result.trades),
    "net_profit": fb_result.metrics.net_profit,
    "total_return": fb_result.metrics.total_return,
    "win_rate": fb_result.metrics.win_rate,
    "sharpe_ratio": fb_result.metrics.sharpe_ratio,
    "max_drawdown": fb_result.metrics.max_drawdown,
}

# ============================================================================
# ТЕСТ 2: NumbaEngineV2
# ============================================================================
print("\n" + "=" * 80)
print("🚀 ТЕСТ 2: NumbaEngineV2")
print("=" * 80)

from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

numba_engine = NumbaEngineV2()
nb_result = numba_engine.run(input_data)


def compare_to_reference(name, result):
    trades_match = len(result.trades) == REFERENCE["trades"]
    profit_match = abs(result.metrics.net_profit - REFERENCE["net_profit"]) < 0.01
    return_match = abs(result.metrics.total_return - REFERENCE["total_return"]) < 0.01

    print(f"   Trades: {len(result.trades)} {'✅' if trades_match else '❌'} (ref: {REFERENCE['trades']})")
    print(
        f"   Net Profit: ${result.metrics.net_profit:,.2f} {'✅' if profit_match else '❌'} (ref: ${REFERENCE['net_profit']:,.2f})"
    )
    print(f"   Total Return: {result.metrics.total_return:.4f}% {'✅' if return_match else '❌'}")
    print(f"   Win Rate: {result.metrics.win_rate:.4f}")
    print(f"   Sharpe Ratio: {result.metrics.sharpe_ratio:.4f}")

    return trades_match and profit_match


compare_to_reference("NumbaEngineV2", nb_result)

# ============================================================================
# ТЕСТ 3: GPU Optimizer (если доступен)
# ============================================================================
print("\n" + "=" * 80)
print("🖥️ ТЕСТ 3: GPU Optimizer")
print("=" * 80)

try:
    from backend.backtesting.gpu_optimizer import (
        GPU_AVAILABLE,
        NUMBA_AVAILABLE,
        _fast_simulate_backtest,
    )

    if NUMBA_AVAILABLE:
        print(f"   GPU Available: {GPU_AVAILABLE}")
        print(f"   Numba Available: {NUMBA_AVAILABLE}")

        # Подготовим данные для GPU optimizer
        close = df["close"].values.astype(np.float64)
        high = df["high"].values.astype(np.float64)
        low = df["low"].values.astype(np.float64)
        entries = long_entries.astype(np.bool_)
        exits = long_exits.astype(np.bool_)

        # Запустим симуляцию
        gpu_result = _fast_simulate_backtest(
            close=close,
            high=high,
            low=low,
            entries=entries,
            exits=exits,
            stop_loss=TEST_CONFIG["stop_loss"],
            take_profit=TEST_CONFIG["take_profit"],
            capital=TEST_CONFIG["initial_capital"],
            commission=TEST_CONFIG["commission"],
            slippage=TEST_CONFIG["slippage"],
            position_size=TEST_CONFIG["position_size"],
        )

        # gpu_result возвращает: (final_equity, total_return, max_dd, num_trades, win_rate)
        print("\n   GPU Result:")
        print(f"   Final Equity: ${gpu_result[0]:,.2f}")
        print(f"   Total Return: {gpu_result[1]:.4f}%")
        print(f"   Max Drawdown: {gpu_result[2]:.4f}%")
        print(f"   Num Trades: {gpu_result[3]}")
        print(f"   Win Rate: {gpu_result[4]:.4f}")

        # Сравнение с эталоном
        gpu_net_profit = gpu_result[0] - TEST_CONFIG["initial_capital"]
        profit_match = abs(gpu_net_profit - REFERENCE["net_profit"]) < 0.01
        trades_match = gpu_result[3] == REFERENCE["trades"]

        print("\n   Сравнение с эталоном:")
        print(
            f"   Net Profit: ${gpu_net_profit:,.2f} {'✅' if profit_match else '❌'} (ref: ${REFERENCE['net_profit']:,.2f})"
        )
        print(f"   Trades: {gpu_result[3]} {'✅' if trades_match else '❌'} (ref: {REFERENCE['trades']})")

        if not profit_match:
            diff = gpu_net_profit - REFERENCE["net_profit"]
            print(f"   ⚠️ РАСХОЖДЕНИЕ: ${diff:,.2f} ({diff / abs(REFERENCE['net_profit']) * 100:.2f}%)")
    else:
        print("   ⚠️ Numba не доступен для GPU optimizer")

except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# ============================================================================
# ТЕСТ 4: VectorBT (если доступен)
# ============================================================================
print("\n" + "=" * 80)
print("📊 ТЕСТ 4: VectorBT")
print("=" * 80)

try:
    import vectorbt as vbt

    print(f"   VectorBT version: {vbt.__version__}")

    # Используем vectorbt_sltp для более честного сравнения
    from backend.backtesting.vectorbt_sltp import run_vectorbt_with_sltp

    # Подготовим конфиг
    vbt_config = {
        "initial_capital": TEST_CONFIG["initial_capital"],
        "leverage": TEST_CONFIG["leverage"],
        "stop_loss": TEST_CONFIG["stop_loss"],
        "take_profit": TEST_CONFIG["take_profit"],
        "commission": TEST_CONFIG["commission"],
        "slippage": TEST_CONFIG["slippage"],
        "direction": "both",
    }

    # Подготовим сигналы
    signals = {
        "long_entry": pd.Series(long_entries, index=df.index),
        "long_exit": pd.Series(long_exits, index=df.index),
        "short_entry": pd.Series(short_entries, index=df.index),
        "short_exit": pd.Series(short_exits, index=df.index),
    }

    vbt_result = run_vectorbt_with_sltp(df, signals, vbt_config)

    print("\n   VectorBT Result:")
    print(f"   Final Equity: ${vbt_result.get('final_equity', 0):,.2f}")
    print(f"   Net Profit: ${vbt_result.get('net_profit', 0):,.2f}")
    print(f"   Total Return: {vbt_result.get('total_return', 0):.4f}%")
    print(f"   Num Trades: {vbt_result.get('total_trades', 0)}")

    # Сравнение с эталоном
    vbt_profit = vbt_result.get("net_profit", 0)
    profit_match = abs(vbt_profit - REFERENCE["net_profit"]) < 0.01
    trades_match = vbt_result.get("total_trades", 0) == REFERENCE["trades"]

    print("\n   Сравнение с эталоном:")
    print(f"   Net Profit: ${vbt_profit:,.2f} {'✅' if profit_match else '❌'} (ref: ${REFERENCE['net_profit']:,.2f})")
    print(
        f"   Trades: {vbt_result.get('total_trades', 0)} {'✅' if trades_match else '❌'} (ref: {REFERENCE['trades']})"
    )

    if not profit_match:
        diff = vbt_profit - REFERENCE["net_profit"]
        print(f"   ⚠️ РАСХОЖДЕНИЕ: ${diff:,.2f}")

except ImportError:
    print("   ⚠️ VectorBT не установлен")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    import traceback

    traceback.print_exc()

# ============================================================================
# ИТОГОВЫЙ ОТЧЁТ
# ============================================================================
print("\n" + "=" * 120)
print("📋 ИТОГОВЫЙ ОТЧЁТ АУДИТА")
print("=" * 120)

print("""
   ┌───────────────────────────────────────────────────────────────────────────┐
   │ MOVEMENT               │ TRADES │ NET PROFIT  │ PARITY STATUS            │
   ├───────────────────────────────────────────────────────────────────────────┤
   │ FallbackEngineV2       │ ЭТАЛОН │ ЭТАЛОН      │ ✅ REFERENCE             │
   │ NumbaEngineV2          │   ?    │     ?       │ ? (check above)          │
   │ GPU Optimizer          │   ?    │     ?       │ ? (check above)          │
   │ VectorBT               │   ?    │     ?       │ ? (check above)          │
   └───────────────────────────────────────────────────────────────────────────┘
""")

print("=" * 120)
