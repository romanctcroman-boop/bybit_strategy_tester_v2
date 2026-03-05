"""
Direct backtest run bypassing HTTP API, to test the qty truncation fix.
"""

import os
import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import csv
from datetime import datetime, timezone

import pandas as pd

# Import the engine directly
from backend.backtesting.engine import BacktestConfig, BacktestEngine
from backend.services.adapters.bybit import BybitAdapter

# ---------------------------------------------------------------------------
# Load TV reference
# ---------------------------------------------------------------------------
TV_CSV = r"d:\bybit_strategy_tester_v2\temp_analysis\a4.csv"


def parse_tv_trades():
    trades = []
    with open(TV_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            pnl_str = row.get("Прибыль/убыток", "") or row.get("Profit", "") or ""
            pnl_str = pnl_str.replace(" ", "").replace("\u202f", "").replace(",", ".")
            if not pnl_str:
                continue
            try:
                pnl = float(pnl_str)
            except ValueError:
                continue
            # Entry time
            et_str = row.get("Время сделки", "") or row.get("Trade time", "") or ""
            trades.append({"pnl": pnl, "entry_raw": et_str})
    return trades


tv_trades = parse_tv_trades()
print(f"TV trades loaded: {len(tv_trades)}")

# ---------------------------------------------------------------------------
# Load OHLCV data (fetch from DB or via adapter)
# ---------------------------------------------------------------------------
import sqlite3
from pathlib import Path

db_path = Path(r"d:\bybit_strategy_tester_v2\data.sqlite3")

# Pull 30m ETHUSDT candles
conn = sqlite3.connect(str(db_path))
df = pd.read_sql(
    """
    SELECT open_time, open_price as open, high_price as high, low_price as low,
           close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol='ETHUSDT' AND interval='30'
    AND open_time >= 1735689600000
    AND open_time <= 1740700200000
    ORDER BY open_time ASC
""",
    conn,
)
conn.close()

if len(df) == 0:
    # Try alternative table name
    conn = sqlite3.connect(str(db_path))
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
    conn.close()
    print("Tables:", tables["name"].tolist())
    sys.exit(1)

df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df.set_index("open_time", inplace=True)
print(f"OHLCV loaded: {len(df)} bars")
print(f"  Range: {df.index[0]} to {df.index[-1]}")

# ---------------------------------------------------------------------------
# Run the strategy to generate signals
# ---------------------------------------------------------------------------
from backend.backtesting.strategies.rsi_ls_15 import StrategyRSILS15

strategy_params = {
    "rsi_period": 14,
    "timeframe": "30",
    "use_btc_source": True,
    "btc_ticker": "BTCUSDT",
    "overbought": 70,
    "oversold": 30,
}

strategy = StrategyRSILS15(strategy_params)

# Load BTC data for the RSI source
conn = sqlite3.connect(str(db_path))
btc_df = pd.read_sql(
    """
    SELECT open_time, open_price as open, high_price as high, low_price as low,
           close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol='BTCUSDT' AND interval='30'
    AND open_time >= 1735689600000
    AND open_time <= 1740700200000
    ORDER BY open_time ASC
""",
    conn,
)
conn.close()

if len(btc_df) > 0:
    btc_df["open_time"] = pd.to_datetime(btc_df["open_time"], unit="ms", utc=True)
    btc_df.set_index("open_time", inplace=True)
    print(f"BTC data loaded: {len(btc_df)} bars")

# Generate signals
signals = strategy.generate_signals(df)
print(f"Signals generated")

# ---------------------------------------------------------------------------
# Run backtest
# ---------------------------------------------------------------------------
config = BacktestConfig(
    symbol="ETHUSDT",
    interval="30",
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2026, 2, 27, 23, 30, tzinfo=timezone.utc),
    initial_capital=10000,
    commission_value=0.0007,
    slippage=0.0,
    position_size=0.1,
    leverage=10,
    pyramiding=1,
    direction="both",
    stop_loss=0.132,
    take_profit=0.023,
    sl_type="average_price",
)

engine = BacktestEngine()
result = engine.run(config, df, signals)
print(f"\nBacktest result:")
print(f"  Total trades: {len(result.trades)}")
print(f"  Net profit: {result.metrics.get('net_profit', 'N/A')}")

# Check a few SL trades
print("\nSample SL trades (should match TV):")
sl_trades = [
    t for t in result.trades if getattr(t, "exit_comment", "") == "SL" or getattr(t, "exit_reason", "") == "stop_loss"
]
for t in sl_trades[:5]:
    print(f"  entry={t.entry_price:.2f} size={t.size:.6f} pnl={t.pnl:.4f}")
