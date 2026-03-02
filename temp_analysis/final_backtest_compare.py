"""
Final backtest comparison: Strategy_RSI_L\\S_15 vs TradingView
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
from backend.backtesting.models import BacktestConfig
from backend.models import MarketData

# Parameters (from TV a5.csv)
SYMBOL = "ETHUSDT"
INTERVAL = "30"  # Without 'm'
START_DATE = "2025-01-01T00:00:00+00:00"
END_DATE = "2026-02-27T23:00:00+00:00"

# TV Results (from a1.csv, a2.csv)
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
print("BACKTEST COMPARISON: Strategy_RSI_L\\S_15 vs TradingView")
print("=" * 100)

# Load strategy from DB
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
print(f"ID: {strategy_id}")

# Show RSI params
for b in blocks:
    if b["type"] == "rsi":
        print(f"\nRSI Params:")
        for k, v in b["params"].items():
            print(f"  {k}: {v}")
    elif b["type"] == "static_sltp":
        print(f"\nSL/TP Params:")
        for k, v in b["params"].items():
            print(f"  {k}: {v}")

# Load data
print(f"\nLoading data...")
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

print(f"  ETHUSDT bars: {len(eth_data)}")
print(f"  BTCUSDT bars: {len(btc_data)}")

# Convert to DataFrame
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

print(f"  OHLCV range: {ohlcv.index.min()} - {ohlcv.index.max()}")

# Generate signals
print(f"\nGenerating signals...")

strategy_graph = {
    "blocks": blocks,
    "connections": connections,
    "market_type": "linear",
    "direction": "both",
    "interval": INTERVAL,  # Main chart timeframe
}

adapter = StrategyBuilderAdapter(
    strategy_graph=strategy_graph,
    btcusdt_ohlcv=btc_ohlcv,
)

signals = adapter.generate_signals(ohlcv=ohlcv)

print(f"  LONG signals (entries): {signals.entries.sum()}")
print(f"  SHORT signals (short_entries): {signals.short_entries.sum() if signals.short_entries is not None else 0}")

# Show first few signals
print(f"\nFirst 5 LONG signals:")
if signals.entries is not None and signals.entries.any():
    long_signal_indices = np.where(signals.entries)[0][:5]
    for i, idx in enumerate(long_signal_indices):
        print(f"  #{i+1}: Bar {idx} - {ohlcv.index[idx]} - Close: {ohlcv.iloc[idx]['close']}")

print(f"\nFirst 5 SHORT signals:")
if signals.short_entries is not None and signals.short_entries.any():
    short_signal_indices = np.where(signals.short_entries)[0][:5]
    for i, idx in enumerate(short_signal_indices):
        print(f"  #{i+1}: Bar {idx} - {ohlcv.index[idx]} - Close: {ohlcv.iloc[idx]['close']}")

# Run backtest
print(f"\nRunning backtest...")
config = BacktestConfig(
    symbol=SYMBOL,
    interval=INTERVAL,
    initial_capital=10000,
    commission_value=0.0007,
    slippage_value=0.0,
    position_size_pct=10,
    leverage=10,
    pyramiding=1,
    long_enabled=True,
    short_enabled=True,
)

engine = FallbackEngineV4()

# Convert signals to numpy arrays
long_entries = signals.entries.values if signals.entries is not None else np.zeros(len(ohlcv), dtype=bool)
short_entries = signals.short_entries.values if signals.short_entries is not None else np.zeros(len(ohlcv), dtype=bool)
long_exits = pd.Series(False, index=ohlcv.index).values
short_exits = pd.Series(False, index=ohlcv.index).values

# Create input data
from backend.backtesting.interfaces import BacktestInput

input_data = BacktestInput(
    candles=ohlcv,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    initial_capital=10000,
    commission_value=0.0007,
    slippage_value=0.0,
    position_size_pct=10,
    leverage=10,
    pyramiding=1,
)

result = engine.run(input_data)

print(f"\nBacktest completed!")
print(f"  Total trades: {len(result.trades)}")

# Calculate metrics
if result.trades:
    winning = [t for t in result.trades if t.pnl > 0]
    losing = [t for t in result.trades if t.pnl < 0]
    long_trades = [t for t in result.trades if t.direction == "long"]
    short_trades = [t for t in result.trades if t.direction == "short"]
    
    net_profit = sum(t.pnl for t in result.trades)
    total_commission = sum(t.fees for t in result.trades)
    win_rate = len(winning) / len(result.trades) * 100 if result.trades else 0
    avg_profit = sum(t.pnl for t in winning) / len(winning) if winning else 0
    avg_loss = sum(t.pnl for t in losing) / len(losing) if losing else 0
    
    print(f"\nOur Results:")
    print(f"  Net Profit: {net_profit:.2f} USDT")
    print(f"  Net Profit %: {net_profit / 10000 * 100:.2f}%")
    print(f"  Total Trades: {len(result.trades)}")
    print(f"  Winning: {len(winning)}, Losing: {len(losing)}")
    print(f"  Win Rate: {win_rate:.2f}%")
    print(f"  Avg Profit: {avg_profit:.2f} USDT")
    print(f"  Avg Loss: {avg_loss:.2f} USDT")
    print(f"  Total Commission: {total_commission:.2f} USDT")
    print(f"  Long Trades: {len(long_trades)}, Short Trades: {len(short_trades)}")

# Compare with TV
print(f"\n" + "=" * 100)
print("COMPARISON WITH TRADINGVIEW")
print("=" * 100)
print(f"\n{'Metric':<30} {'TV Expected':<15} {'Our Result':<15} {'Match':<10}")
print("-" * 100)

metrics_to_compare = [
    ("Net Profit (USDT)", TV_RESULTS["net_profit"], net_profit),
    ("Net Profit (%)", TV_RESULTS["net_profit_percent"], net_profit / 10000 * 100),
    ("Total Trades", TV_RESULTS["total_trades"], len(result.trades)),
    ("Winning Trades", TV_RESULTS["winning_trades"], len(winning)),
    ("Win Rate (%)", TV_RESULTS["win_rate"], win_rate),
    ("Avg Profit (USDT)", TV_RESULTS["avg_profit"], avg_profit),
    ("Avg Loss (USDT)", TV_RESULTS["avg_loss"], avg_loss),
    ("Commission (USDT)", TV_RESULTS["total_commission"], total_commission),
    ("Long Trades", TV_RESULTS["long_trades"], len(long_trades)),
    ("Short Trades", TV_RESULTS["short_trades"], len(short_trades)),
]

for metric_name, tv_val, our_val in metrics_to_compare:
    # Allow 5% tolerance for floating point differences
    if tv_val != 0:
        diff_pct = abs((our_val - tv_val) / tv_val) * 100
        match = "OK" if diff_pct < 5 else "MISMATCH"
    else:
        match = "OK" if our_val == 0 else "MISMATCH"
    
    print(f"{metric_name:<30} {tv_val:<15.2f} {our_val:<15.2f} {match:<10} ({diff_pct:.1f}%)")

print("\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
