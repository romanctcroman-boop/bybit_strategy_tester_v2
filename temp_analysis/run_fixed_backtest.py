"""
Бэктест Strategy_RSI_L\\S_15 после исправления и сравнение с TV
"""
import sqlite3
import json
import pandas as pd
import numpy as np
from datetime import datetime
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

from backend.services.data_service import DataService
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput

# Параметры TV (из a5.csv)
SYMBOL = "ETHUSDT"
INTERVAL = "30"
START_DATE = "2025-01-01T00:00:00+00:00"
END_DATE = "2026-02-27T23:00:00+00:00"

# TV результаты (эталон из a1.csv, a2.csv)
TV_RESULTS = {
    "net_profit": 1001.98,
    "net_profit_percent": 10.02,
    "total_trades": 154,
    "winning_trades": 139,
    "losing_trades": 15,
    "win_rate": 90.26,
    "avg_profit": 21.61,
    "avg_loss": 133.44,
    "total_commission": 215.03,
    "long_trades": 30,
    "short_trades": 124,
    "max_drawdown": 670.46,
    "max_drawdown_percent": 6.70,
    "profit_factor": 1.501,
}

print("=" * 100)
print("БЭКТЕСТ Strategy_RSI_L\\S_15 ПОСЛЕ ИСПРАВЛЕНИЯ (OR логика)")
print("=" * 100)

# Загружаем стратегию из БД
DB_PATH = "d:/bybit_strategy_tester_v2/data.sqlite3"
conn = sqlite3.connect(DB_PATH)
row = conn.execute(
    "SELECT id, name, builder_blocks, builder_connections FROM strategies WHERE id=?",
    ("2e5bb802-572b-473f-9ee9-44d38bf9c531",)
).fetchone()
conn.close()

if not row:
    print("❌ Стратегия не найдена!")
    exit(1)

strategy_id, name, blocks_json, connections_json = row
blocks = json.loads(blocks_json)
connections = json.loads(connections_json) if connections_json else []

print(f"\nСтратегия: {name}")
print(f"ID: {strategy_id}")

# Загружаем данные
print(f"\nЗагрузка данных...")
with DataService() as ds:
    eth_data = ds.get_market_data(
        symbol=SYMBOL,
        timeframe=INTERVAL,
        start_time=START_DATE,
        end_time=END_DATE,
        limit=100000,
    )
    btc_data = ds.get_market_data(
        symbol="BTCUSDT",
        timeframe=INTERVAL,
        start_time=START_DATE,
        end_time=END_DATE,
        limit=100000,
    )

print(f"  ETHUSDT баров: {len(eth_data)}")
print(f"  BTCUSDT баров: {len(btc_data)}")

# Конвертируем в DataFrame
ohlcv = pd.DataFrame([{
    'open': d.open_price,
    'high': d.high_price,
    'low': d.low_price,
    'close': d.close_price,
    'volume': d.volume,
} for d in eth_data])
ohlcv.index = pd.to_datetime([d.open_time_dt for d in eth_data])
ohlcv.index.name = 'time'

btc_ohlcv = pd.DataFrame([{
    'open': d.open_price,
    'high': d.high_price,
    'low': d.low_price,
    'close': d.close_price,
    'volume': d.volume,
} for d in btc_data])
btc_ohlcv.index = pd.to_datetime([d.open_time_dt for d in btc_data])
btc_ohlcv.index.name = 'time'

print(f"  Диапазон: {ohlcv.index.min()} - {ohlcv.index.max()}")

# Генерируем сигналы
print(f"\nГенерация сигналов...")
strategy_graph = {
    "blocks": blocks,
    "connections": connections,
    "market_type": "linear",
    "direction": "both",
    "interval": INTERVAL,
}

adapter = StrategyBuilderAdapter(
    strategy_graph=strategy_graph,
    btcusdt_ohlcv=btc_ohlcv,
)

signals = adapter.generate_signals(ohlcv=ohlcv)

print(f"  LONG сигналов (entries): {signals.entries.sum()}")
print(f"  SHORT сигналов (short_entries): {signals.short_entries.sum() if signals.short_entries is not None else 0}")

# Запускаем бэктест
print(f"\nЗапуск бэктеста...")

# Конвертируем сигналы в numpy массивы
long_entries = signals.entries.values if signals.entries is not None else np.zeros(len(ohlcv), dtype=bool)
short_entries = signals.short_entries.values if signals.short_entries is not None else np.zeros(len(ohlcv), dtype=bool)
long_exits = pd.Series(False, index=ohlcv.index).values
short_exits = pd.Series(False, index=ohlcv.index).values

# Создаем input data
input_data = BacktestInput(
    candles=ohlcv,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    symbol=SYMBOL,
    interval=INTERVAL,
    initial_capital=10000,
    position_size=0.10,  # 10% от капитала
    leverage=10,
    taker_fee=0.0007,  # 0.07%
    slippage=0.0,  # 0%
    stop_loss=0.132,  # 13.2%
    take_profit=0.023,  # 2.3%
    pyramiding=1,
)

engine = FallbackEngineV4()
result = engine.run(input_data)

print(f"\n✅ Бэктест завершен!")
print(f"  Всего сделок: {len(result.trades)}")

# Считаем метрики
if result.trades:
    winning = [t for t in result.trades if t.pnl > 0]
    losing = [t for t in result.trades if t.pnl < 0]
    long_trades = [t for t in result.trades if t.direction == "long"]
    short_trades = [t for t in result.trades if t.direction == "short"]
    
    net_profit = sum(t.pnl for t in result.trades)
    total_commission = sum(t.fees for t in result.trades)
    win_rate = len(winning) / len(result.trades) * 100 if result.trades else 0
    avg_profit = sum(t.pnl for t in winning) / len(winning) if winning else 0
    avg_loss = abs(sum(t.pnl for t in losing) / len(losing)) if losing else 0
    gross_profit = sum(t.pnl for t in winning)
    gross_loss = abs(sum(t.pnl for t in losing))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # Считаем макс. просадку
    equity_curve = [10000]
    for t in result.trades:
        equity_curve.append(equity_curve[-1] + t.pnl)
    max_dd = 0
    peak = equity_curve[0]
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    
    max_dd_pct = (max_dd / 10000) * 100

    print(f"\n📊 НАШИ РЕЗУЛЬТАТЫ:")
    print(f"  Чистая прибыль: {net_profit:.2f} USDT")
    print(f"  Чистая прибыль %: {net_profit / 10000 * 100:.2f}%")
    print(f"  Всего сделок: {len(result.trades)}")
    print(f"  Прибыльных: {len(winning)}, Убыточных: {len(losing)}")
    print(f"  Win Rate: {win_rate:.2f}%")
    print(f"  Средняя прибыль: {avg_profit:.2f} USDT")
    print(f"  Средний убыток: {avg_loss:.2f} USDT")
    print(f"  Профит фактор: {profit_factor:.3f}")
    print(f"  Комиссия: {total_commission:.2f} USDT")
    print(f"  LONG сделок: {len(long_trades)}, SHORT сделок: {len(short_trades)}")
    print(f"  Макс. просадка: {max_dd:.2f} USDT ({max_dd_pct:.2f}%)")

# Сравниваем с TV
print(f"\n" + "=" * 100)
print("СРАВНЕНИЕ С TRADINGVIEW")
print("=" * 100)
print(f"\n{'Метрика':<30} {'TV Эталон':<15} {'Наш результат':<15} {'Разница':<15} {'Совпадает':<10}")
print("-" * 100)

metrics_to_compare = [
    ("Чистая прибыль (USDT)", TV_RESULTS["net_profit"], net_profit),
    ("Чистая прибыль (%)", TV_RESULTS["net_profit_percent"], net_profit / 10000 * 100),
    ("Всего сделок", TV_RESULTS["total_trades"], len(result.trades)),
    ("Прибыльных сделок", TV_RESULTS["winning_trades"], len(winning)),
    ("Win Rate (%)", TV_RESULTS["win_rate"], win_rate),
    ("Средняя прибыль (USDT)", TV_RESULTS["avg_profit"], avg_profit),
    ("Средний убыток (USDT)", TV_RESULTS["avg_loss"], avg_loss),
    ("Комиссия (USDT)", TV_RESULTS["total_commission"], total_commission),
    ("LONG сделок", TV_RESULTS["long_trades"], len(long_trades)),
    ("SHORT сделок", TV_RESULTS["short_trades"], len(short_trades)),
    ("Макс. просадка (USDT)", TV_RESULTS["max_drawdown"], max_dd),
    ("Макс. просадка (%)", TV_RESULTS["max_drawdown_percent"], max_dd_pct),
    ("Профит фактор", TV_RESULTS["profit_factor"], profit_factor),
]

all_match = True
for metric_name, tv_val, our_val in metrics_to_compare:
    # Допускаем 1% погрешность для floating point
    if tv_val != 0:
        diff_pct = abs((our_val - tv_val) / tv_val) * 100
        diff_abs = our_val - tv_val
    else:
        diff_pct = 0
        diff_abs = our_val
    
    # Критерии совпадения
    if metric_name.startswith("Всего") or "сделок" in metric_name:
        match = abs(diff_abs) < 1  # Для кол-ва сделок - точно
    else:
        match = diff_pct < 1.0  # Для остальных - 1% погрешность
    
    match_str = "✅" if match else "❌"
    if not match:
        all_match = False
    
    print(f"{metric_name:<30} {tv_val:<15.2f} {our_val:<15.2f} {diff_abs:>+14.2f} {match_str:<10} ({diff_pct:.2f}%)")

print("\n" + "=" * 100)
if all_match:
    print("✅ 100% ПАРИТЕТ С TRADINGVIEW ДОСТИГНУТ!")
else:
    print("❌ ЕСТЬ РАСХОЖДЕНИЯ - ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНАЯ НАСТРОЙКА")
print("=" * 100)

# Показываем первые несколько сделок для сравнения
print(f"\n📊 ПЕРВЫЕ 10 СДЕЛОК:")
print(f"{'#':<4} {'Тип':<8} {'Время входа':<22} {'Время выхода':<22} {'PnL':<10} {'Exit Reason':<15}")
print("-" * 100)
for i, trade in enumerate(result.trades[:10]):
    entry_time = trade.entry_time.strftime("%Y-%m-%d %H:%M") if hasattr(trade.entry_time, 'strftime') else str(trade.entry_time)
    exit_time = trade.exit_time.strftime("%Y-%m-%d %H:%M") if hasattr(trade.exit_time, 'strftime') else str(trade.exit_time)
    print(f"{i+1:<4} {trade.direction:<8} {entry_time:<22} {exit_time:<22} {trade.pnl:>+10.2f} {trade.exit_reason:<15}")
