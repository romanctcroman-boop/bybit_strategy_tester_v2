"""
Диагностика Strategy_DCA_RSI_02:
- Показывает сколько сигналов генерирует RSI блок
- Показывает что получает DCAEngine
- Показывает сколько открывается сделок и ордеров сетки
"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import json
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# 1. Загрузить стратегию
conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()
cur.execute("SELECT id, name, builder_blocks, builder_connections FROM strategies WHERE name = 'Strategy_DCA_RSI_02'")
row = cur.fetchone()
conn.close()

if not row:
    print("Стратегия Strategy_DCA_RSI_02 не найдена!")
    sys.exit(1)

print(f"Стратегия: {row[1]} (id={row[0]})")
blocks = json.loads(row[2])
connections = json.loads(row[3])
strategy_graph = {"blocks": blocks, "connections": connections}

# 2. Создать синтетические OHLCV данные (400 баров, понижение → подъём)
np.random.seed(42)
n = 400
dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz=timezone.utc)
# Цена падает в первой половине (RSI уйдёт в oversold), потом растёт
prices = np.concatenate(
    [
        np.linspace(50000, 43000, n // 2) + np.random.randn(n // 2) * 200,
        np.linspace(43000, 52000, n // 2) + np.random.randn(n // 2) * 200,
    ]
)
ohlcv = pd.DataFrame(
    {
        "open": prices,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "close": prices,
        "volume": np.full(n, 10.0),
    },
    index=dates,
)

print(f"\nОHLCV: {len(ohlcv)} баров, цены {ohlcv['close'].min():.0f}–{ohlcv['close'].max():.0f}")

# 3. Создать адаптер и сгенерировать сигналы
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(strategy_graph)
signal_result = adapter.generate_signals(ohlcv)

long_entries = int(signal_result.entries.sum())
short_entries = int(signal_result.short_entries.sum()) if signal_result.short_entries is not None else 0
print(f"\n=== СИГНАЛЫ ОТ АДАПТЕРА ===")
print(f"Лонг сигналов: {long_entries}")
print(f"Шорт сигналов: {short_entries}")

if long_entries > 0:
    entry_bars = ohlcv.index[signal_result.entries].tolist()
    print(f"Первые 5 лонг сигналов: {entry_bars[:5]}")

# 4. Извлечь DCA конфиг
dca_config = adapter.extract_dca_config()
has_dca = adapter.has_dca_blocks()
print(f"\n=== DCA КОНФИГ ===")
print(f"has_dca_blocks: {has_dca}")
print(f"dca_enabled: {dca_config.get('dca_enabled')}")
print(f"dca_order_count: {dca_config.get('dca_order_count')}")
print(f"dca_grid_size_percent: {dca_config.get('dca_grid_size_percent')}")
print(f"dca_martingale_coef: {dca_config.get('dca_martingale_coef')}")

# 5. Запустить DCAEngine
from backend.backtesting.engines.dca_engine import DCAEngine, DCAGridConfig


# Имитируем BacktestConfig
class FakeConfig:
    symbol = "BTCUSDT"
    interval = "1h"
    start_date = dates[0]
    end_date = dates[-1]
    strategy_type = "custom"
    strategy_params = dca_config.get("strategy_params", {})
    initial_capital = 10000.0
    position_size = 0.1
    leverage = 1
    direction = "long"
    stop_loss = 0.132  # 13.2% из блока static_sltp
    take_profit = 0.023  # 2.3%
    taker_fee = 0.0007
    maker_fee = 0.0007
    slippage = 0.0
    pyramiding = 1
    market_type = "linear"
    # DCA fields from extracted config
    dca_enabled = dca_config.get("dca_enabled", True)
    dca_direction = dca_config.get("dca_direction", "both")
    dca_order_count = dca_config.get("dca_order_count", 5)
    dca_grid_size_percent = dca_config.get("dca_grid_size_percent", 6.0)
    dca_martingale_coef = dca_config.get("dca_martingale_coef", 1.0)
    dca_martingale_mode = dca_config.get("dca_martingale_mode", "multiply_each")
    dca_log_step_enabled = dca_config.get("dca_log_step_enabled", False)
    dca_log_step_coef = dca_config.get("dca_log_step_coef", 1.2)
    dca_drawdown_threshold = dca_config.get("dca_drawdown_threshold", 30.0)
    dca_safety_close_enabled = dca_config.get("dca_safety_close_enabled", True)
    dca_custom_orders = dca_config.get("custom_orders", None)
    dca_grid_trailing_percent = dca_config.get("grid_trailing_percent", 0.0)
    dca_multi_tp_enabled = dca_config.get("dca_multi_tp_enabled", False)
    dca_tp1_percent = dca_config.get("dca_tp1_percent", 0.5)
    dca_tp1_close_percent = dca_config.get("dca_tp1_close_percent", 25.0)
    dca_tp2_percent = dca_config.get("dca_tp2_percent", 1.0)
    dca_tp2_close_percent = dca_config.get("dca_tp2_close_percent", 25.0)
    dca_tp3_percent = dca_config.get("dca_tp3_percent", 2.0)
    dca_tp3_close_percent = dca_config.get("dca_tp3_close_percent", 25.0)
    dca_tp4_percent = dca_config.get("dca_tp4_percent", 3.0)
    dca_tp4_close_percent = dca_config.get("dca_tp4_close_percent", 25.0)


config = FakeConfig()


# Passthrough adapter (как в роутере)
class PrecomputedAdapter:
    def __init__(self, signals):
        self._signals = signals

    def generate_signals(self, data):
        return self._signals


engine = DCAEngine()
result = engine.run_from_config(config, ohlcv, custom_strategy=PrecomputedAdapter(signal_result))

print(f"\n=== РЕЗУЛЬТАТ БЭКТЕСТА ===")
print(f"Статус: {result.status}")
print(f"Сделок: {len(result.trades) if result.trades else 0}")
if result.metrics:
    print(
        f"Net PnL: {result.metrics.net_profit:.2f}"
        if hasattr(result.metrics, "net_profit")
        else f"Метрики: {result.metrics}"
    )

if result.trades:
    print("\nПервые 3 сделки:")
    for t in result.trades[:3]:
        print(
            f"  side={t.side}, entry={t.entry_price:.0f}, exit={t.exit_price:.0f}, pnl={t.pnl:.2f}, size={t.size:.4f}"
        )

# 6. Проверить сетку - сколько ордеров заполнилось
print(f"\n=== ДИАГНОСТИКА СЕТКИ ===")
print(
    f"Ожидаем: 1 RSI сигнал → открытие первого ордера + {dca_config.get('dca_order_count', 5) - 1} ордеров сетки ниже"
)
print(f"Реально сделок: {len(result.trades) if result.trades else 0}")

# Проверим engine статистику
print(f"\nEngine total_signals (RSI входов): {engine.total_signals}")
print(f"Engine total_orders_filled (всего ордеров): {engine.total_orders_filled}")
