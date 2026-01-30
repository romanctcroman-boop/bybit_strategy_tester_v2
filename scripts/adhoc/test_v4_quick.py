import sys
from pathlib import Path

# Project root: parent of scripts/
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import numpy as np
import pandas as pd

from backend.backtesting.engine_selector import get_engine
from backend.backtesting.interfaces import BacktestInput

# Create test data
np.random.seed(42)
n = 100
ts = pd.date_range(start="2025-01-01", periods=n, freq="15min")
close = 50000 + np.cumsum(np.random.randn(n) * 50)
df = pd.DataFrame(
    {
        "timestamp": ts,
        "open": close + np.random.randn(n) * 10,
        "high": close + np.abs(np.random.randn(n) * 100),
        "low": close - np.abs(np.random.randn(n) * 100),
        "close": close,
        "volume": np.random.randint(100, 1000, n).astype(float),
    }
)
df["high"] = df[["open", "close", "high"]].max(axis=1)
df["low"] = df[["open", "close", "low"]].min(axis=1)

# Create signals
le = np.zeros(n, dtype=bool)
lx = np.zeros(n, dtype=bool)
se = np.zeros(n, dtype=bool)
sx = np.zeros(n, dtype=bool)
le[5] = True
le[30] = True

# Test
engine = get_engine(engine_type="fallback_v4")
print(f"Engine: {type(engine).__name__}")

inp = BacktestInput(
    candles=df,
    long_entries=le,
    long_exits=lx,
    short_entries=se,
    short_exits=sx,
    symbol="BTCUSDT",
    interval="15m",
    initial_capital=10000.0,
    leverage=10,
    direction="long",
    stop_loss=0.02,
    take_profit=0.03,
    maker_fee=0.0002,
    taker_fee=0.00055,
    pyramiding=1,
)

result = engine.run(inp)
print(f"Trades: {result.metrics.total_trades}")
print(f"Profit: ${result.metrics.net_profit:.2f}")
print("SUCCESS!")
