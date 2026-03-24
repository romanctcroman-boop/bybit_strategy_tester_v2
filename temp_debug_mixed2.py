"""Debug why mixed DCA path fails with exception."""

import logging
import sys

sys.path.insert(0, ".")
logging.basicConfig(level=logging.WARNING)

import numpy as np
import pandas as pd

np.random.seed(42)
n = 200
dates = pd.date_range("2025-01-01", periods=n, freq="30min")
close = 100 * np.cumprod(1 + np.random.normal(0.001, 0.02, n))
ohlcv = pd.DataFrame(
    {
        "open": close * (1 + np.random.uniform(-0.005, 0.005, n)),
        "high": close * (1 + np.random.uniform(0, 0.01, n)),
        "low": close * (1 - np.random.uniform(0, 0.01, n)),
        "close": close,
        "volume": np.random.uniform(1000, 10000, n),
    },
    index=dates,
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
    ],
    "connections": [],
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
    "direction": "long",
    "initial_capital": 10000,
    "position_size": 0.1,
    "leverage": 10,
    "commission_value": 0.0007,
}

from backend.optimization.builder_optimizer import _run_dca_mixed_batch_numba

try:
    results = _run_dca_mixed_batch_numba(
        base_graph=dca_rsi_graph,
        ohlcv=ohlcv,
        param_combinations=combos,
        config_params=config,
        final_dca_config={"dca_enabled": True, "dca_direction": "long"},
        direction_str="long",
        sltp_block_ids=["sltp_1"],
    )
    print(f"Results count: {len(results)}")
    print(f"First result: {results[0]}")
except Exception as e:
    print(f"Exception in _run_dca_mixed_batch_numba: {e}")
    import traceback

    traceback.print_exc()
