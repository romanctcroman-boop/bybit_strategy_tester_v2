"""Debug mixed path with exact test fixture."""

import logging
import sys

sys.path.insert(0, ".")
logging.basicConfig(level=logging.WARNING)

import numpy as np
import pandas as pd

np.random.seed(42)

n = 500
base_price = 50000.0
timestamps = pd.date_range(start="2025-01-01", periods=n, freq="15min", tz="UTC")
returns = np.random.randn(n) * 0.002
prices = base_price * np.cumprod(1 + returns)
sample_ohlcv = pd.DataFrame(
    {
        "timestamp": timestamps,
        "open": prices * (1 + np.random.randn(n) * 0.001),
        "high": prices * (1 + abs(np.random.randn(n)) * 0.003),
        "low": prices * (1 - abs(np.random.randn(n)) * 0.003),
        "close": prices,
        "volume": np.random.uniform(100, 1000, n),
    }
)

dca_rsi_graph = {
    "name": "DCA-RSI-6 test",
    "interval": "30",
    "blocks": [
        {
            "id": "rsi_1",
            "type": "rsi",
            "name": "RSI",
            "params": {
                "period": 14,
                "source": "close",
                "timeframe": "30",
                "use_cross_level": True,
                "cross_long_level": 29,
                "long_rsi_less": 40,
                "use_long_range": True,
            },
        },
        {
            "id": "dca_1",
            "type": "dca",
            "name": "DCA",
            "params": {
                "order_count": 3,
                "grid_size_percent": 5.0,
                "martingale_coef": 1.0,
                "tp_percent": 1.5,
                "sl_percent": 5.0,
            },
        },
        {
            "id": "sltp_1",
            "type": "static_sltp",
            "name": "SL/TP",
            "params": {"stop_loss_percent": 5.0, "take_profit_percent": 1.5, "sl_type": "average_price"},
        },
        {"id": "strategy_1", "type": "strategy", "isMain": True, "params": {}},
    ],
    "connections": [
        {"from": "rsi_1", "fromPort": "long", "to": "strategy_1", "toPort": "entry_long"},
        {"from": "dca_1", "fromPort": "output", "to": "strategy_1", "toPort": "dca"},
        {"from": "sltp_1", "fromPort": "output", "to": "strategy_1", "toPort": "sltp"},
    ],
}

combos = []
for rsi_level in (20, 25, 30):
    for tp in (1.0, 1.5, 2.0):
        combos.append(
            {
                "rsi_1.cross_long_level": rsi_level,
                "sltp_1.take_profit_percent": tp,
                "sltp_1.stop_loss_percent": 5.0,
            }
        )

config = {
    "symbol": "BTCUSDT",
    "interval": "15m",
    "initial_capital": 10000.0,
    "leverage": 1,
    "commission": 0.0007,
    "direction": "long",
    "engine_type": "fallback",
    "use_fixed_amount": False,
    "fixed_amount": 0.0,
    "stop_loss_pct": 0,
    "take_profit_pct": 0,
}

import warnings

from backend.optimization.builder_optimizer import run_builder_grid_search

warnings.filterwarnings("ignore")

# Monkey-patch to see exceptions
import backend.optimization.builder_optimizer as bopt

original_log_warning = bopt._log_warning


def patched_log_warning(msg, **kw):
    print(f"[OPTIMIZER WARNING] {msg}")
    original_log_warning(msg, **kw)


bopt._log_warning = patched_log_warning

result = run_builder_grid_search(
    base_graph=dca_rsi_graph,
    ohlcv=sample_ohlcv,
    param_combinations=combos,
    config_params=config,
)
print(f"Result keys: {list(result.keys())}")
print(f"method: {result.get('method', 'NO METHOD KEY')}")
