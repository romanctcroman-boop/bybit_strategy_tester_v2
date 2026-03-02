"""
Детальное сравнение первой сделки TV vs Наша реализация
"""
import sqlite3
import json
import pandas as pd
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

from backend.services.data_service import DataService
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter

# Параметры
SYMBOL = "ETHUSDT"
INTERVAL = "30m"
START_DATE = "2025-01-01T00:00:00+00:00"
END_DATE = "2026-02-27T23:00:00+00:00"

# TV первая сделка (из a4.csv)
TV_FIRST_SHORT = {
    "entry_time": "2025-01-01 16:30",
    "entry_price": 3334.62,
    "signal": "RsiSE",  # RSI Short Entry
}

print("=" * 100)
print("FIRST TRADE ANALYSIS")
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
    print("Strategy not found!")
    exit(1)

strategy_id, name, blocks_json, connections_json = row
blocks = json.loads(blocks_json)
connections = json.loads(connections_json) if connections_json else []

print(f"\nStrategy: {name}")

# Загружаем данные
print(f"\nLoading data...")
data_service = DataService()
ohlcv = data_service.load_ohlcv(
    symbol=SYMBOL,
    interval=INTERVAL,
    start_date=START_DATE,
    end_date=END_DATE,
)
btc_ohlcv = data_service.load_ohlcv(
    symbol="BTCUSDT",
    interval=INTERVAL,
    start_date=START_DATE,
    end_date=END_DATE,
)

print(f"  ETHUSDT bars: {len(ohlcv)}")
print(f"  BTCUSDT bars: {len(btc_ohlcv)}")

# Показываем бары вокруг первой сделки TV
print(f"\nETHUSDT bars around first TV trade ({TV_FIRST_SHORT['entry_time']}):")
ohlcv_df = ohlcv.copy()
ohlcv_df.index = pd.to_datetime(ohlcv_df.index)
target_time = pd.to_datetime("2025-01-01 16:30:00+00:00")

# Находим бары с 15:00 до 18:00
mask = (ohlcv_df.index >= pd.to_datetime("2025-01-01 15:00:00+00:00")) & \
       (ohlcv_df.index <= pd.to_datetime("2025-01-01 18:00:00+00:00"))
print(ohlcv_df[mask][['open', 'high', 'low', 'close']].to_string())

# Генерируем сигналы
print(f"\nGenerating signals...")
adapter = StrategyBuilderAdapter()
adapter._btcusdt_30m_ohlcv = btc_ohlcv

strategy_graph = {
    "blocks": blocks,
    "connections": connections,
    "market_type": "linear",
    "direction": "both",
}

signals = adapter.generate_signals(
    strategy_graph=strategy_graph,
    ohlcv=ohlcv,
)

print(f"  LONG signals: {signals['long'].sum()}")
print(f"  SHORT signals: {signals['short'].sum()}")

# Показываем первые SHORT сигналы
print(f"\nFirst 5 SHORT signals:")
short_signals = signals['short'][signals['short']]
if len(short_signals) > 0:
    for i, (idx, _) in enumerate(short_signals.head(5).items()):
        bar = ohlcv.iloc[idx]
        print(f"  #{i+1}: {ohlcv.index[idx]} - Price: {bar['close']}")
else:
    print("  No SHORT signals!")

# Показываем первые 5 LONG сигналов
print(f"\nFirst 5 LONG signals:")
long_signals = signals['long'][signals['long']]
if len(long_signals) > 0:
    for i, (idx, _) in enumerate(long_signals.head(5).items()):
        bar = ohlcv.iloc[idx]
        print(f"  #{i+1}: {ohlcv.index[idx]} - Price: {bar['close']}")
else:
    print("  No LONG signals!")

# Сравниваем с TV
print(f"\n" + "=" * 100)
print("COMPARISON WITH TV")
print("=" * 100)
print(f"\nTV first trade:")
print(f"  Time: {TV_FIRST_SHORT['entry_time']}")
print(f"  Price: {TV_FIRST_SHORT['entry_price']}")
print(f"  Signal: {TV_FIRST_SHORT['signal']}")

print(f"\nOur first trade:")
if len(short_signals) > 0:
    first_short_idx = short_signals.index[0]
    first_short_bar = ohlcv.iloc[first_short_idx]
    print(f"  Time: {ohlcv.index[first_short_idx]}")
    print(f"  Price: {first_short_bar['close']}")
    
    match = "OK" if ohlcv.index[first_short_idx] == target_time else "MISMATCH"
    print(f"\n{match} Time match: TV={target_time}, Ours={ohlcv.index[first_short_idx]}")
else:
    print("  No SHORT signals for comparison!")
