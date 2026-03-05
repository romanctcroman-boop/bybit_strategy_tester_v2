"""
First trade analysis - Compare TV vs Our implementation
"""

import json
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter
from backend.services.data_service import DataService

# Parameters
SYMBOL = "ETHUSDT"
INTERVAL = "30m"
START_DATE = "2025-01-01T00:00:00+00:00"
END_DATE = "2026-02-27T23:00:00+00:00"

# TV first trade (from a4.csv)
TV_FIRST_SHORT = {
    "entry_time": "2025-01-01 16:30",
    "entry_price": 3334.62,
    "signal": "RsiSE",  # RSI Short Entry
}

print("=" * 100)
print("FIRST TRADE ANALYSIS")
print("=" * 100)

# Load strategy from DB
DB_PATH = "d:/bybit_strategy_tester_v2/data.sqlite3"
conn = sqlite3.connect(DB_PATH)
row = conn.execute(
    "SELECT id, name, builder_blocks, builder_connections FROM strategies WHERE id=?",
    ("2e5bb802-572b-473f-9ee9-44d38bf9c531",),
).fetchone()
conn.close()

if not row:
    print("Strategy not found!")
    exit(1)

strategy_id, name, blocks_json, connections_json = row
blocks = json.loads(blocks_json)
connections = json.loads(connections_json) if connections_json else []

print(f"\nStrategy: {name}")

# Load data
print("\nLoading data...")
with DataService() as ds:
    eth_data = ds.get_market_data(
        symbol=SYMBOL,
        timeframe=INTERVAL,
        start_time=START_DATE,
        end_time=END_DATE,
    )
    btc_data = ds.get_market_data(
        symbol="BTCUSDT",
        timeframe=INTERVAL,
        start_time=START_DATE,
        end_time=END_DATE,
    )

print(f"  ETHUSDT bars: {len(eth_data)}")
print(f"  BTCUSDT bars: {len(btc_data)}")

# Convert to DataFrame
ohlcv = pd.DataFrame(
    [
        {
            "open": d.open_price,
            "high": d.high_price,
            "low": d.low_price,
            "close": d.close_price,
            "volume": d.volume,
        }
        for d in eth_data
    ]
)
ohlcv.index = pd.to_datetime([d.open_time_dt for d in eth_data])
ohlcv.index.name = "time"

btc_ohlcv = pd.DataFrame(
    [
        {
            "open": d.open_price,
            "high": d.high_price,
            "low": d.low_price,
            "close": d.close_price,
            "volume": d.volume,
        }
        for d in btc_data
    ]
)
btc_ohlcv.index = pd.to_datetime([d.open_time_dt for d in btc_data])
btc_ohlcv.index.name = "time"

print(f"  OHLCV range: {ohlcv.index.min()} - {ohlcv.index.max()}")

# Show bars around first TV trade
print(f"\nETHUSDT bars around first TV trade ({TV_FIRST_SHORT['entry_time']}):")
target_time = pd.to_datetime("2025-01-01 16:30:00+00:00")
mask = (ohlcv.index >= pd.to_datetime("2025-01-01 15:00:00+00:00")) & (
    ohlcv.index <= pd.to_datetime("2025-01-01 18:00:00+00:00")
)
print(ohlcv[mask][["open", "high", "low", "close"]].to_string())

# Generate signals
print("\nGenerating signals...")
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

# Show first SHORT signals
print("\nFirst 5 SHORT signals:")
short_signals = signals["short"][signals["short"]]
if len(short_signals) > 0:
    for i, (idx, _) in enumerate(short_signals.head(5).items()):
        bar = ohlcv.iloc[idx]
        print(f"  #{i + 1}: {ohlcv.index[idx]} - Price: {bar['close']}")
else:
    print("  No SHORT signals!")

# Show first LONG signals
print("\nFirst 5 LONG signals:")
long_signals = signals["long"][signals["long"]]
if len(long_signals) > 0:
    for i, (idx, _) in enumerate(long_signals.head(5).items()):
        bar = ohlcv.iloc[idx]
        print(f"  #{i + 1}: {ohlcv.index[idx]} - Price: {bar['close']}")
else:
    print("  No LONG signals!")

# Compare with TV
print("\n" + "=" * 100)
print("COMPARISON WITH TV")
print("=" * 100)
print("\nTV first trade:")
print(f"  Time: {TV_FIRST_SHORT['entry_time']}")
print(f"  Price: {TV_FIRST_SHORT['entry_price']}")
print(f"  Signal: {TV_FIRST_SHORT['signal']}")

print("\nOur first trade:")
if len(short_signals) > 0:
    first_short_idx = short_signals.index[0]
    first_short_bar = ohlcv.iloc[first_short_idx]
    print(f"  Time: {ohlcv.index[first_short_idx]}")
    print(f"  Price: {first_short_bar['close']}")

    match = "OK" if ohlcv.index[first_short_idx] == target_time else "MISMATCH"
    print(f"\n{match} Time match: TV={target_time}, Ours={ohlcv.index[first_short_idx]}")
else:
    print("  No SHORT signals for comparison!")
