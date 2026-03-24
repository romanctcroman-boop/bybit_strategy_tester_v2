"""Debug - check _std_dca_enabled and infeasibility."""

import sys

sys.path.insert(0, ".")
import os

os.environ["LOG_LEVEL"] = "ERROR"

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

# Check _std_dca_enabled computation
try:
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter as _SBA

    _probe_adapter = _SBA(dca_rsi_graph)
    _probe_dca_config = _probe_adapter.extract_dca_config()
    _std_dca_enabled = _probe_adapter.has_dca_blocks() or _probe_dca_config.get("dca_enabled", False)
    print(f"_std_dca_enabled: {_std_dca_enabled}")
except Exception as e:
    print(f"Exception in adapter probe: {e}")

# Check _is_dca_sltp_only_optimization
from backend.optimization.builder_optimizer import _is_dca_sltp_only_optimization, build_infeasibility_checker

is_sltp_only, sltp_block_ids = _is_dca_sltp_only_optimization(combos, dca_rsi_graph)
print(f"is_sltp_only: {is_sltp_only}, sltp_block_ids: {sltp_block_ids}")

# Check infeasibility
checker = build_infeasibility_checker(dca_rsi_graph)
for combo in combos:
    is_infeasible = checker(combo)
    print(f"  combo {combo} -> infeasible={is_infeasible}")
