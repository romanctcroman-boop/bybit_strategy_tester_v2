"""
Backend Backtesting DCA Strategies Package.

Provides various DCA trading strategies for backtesting:
- DCA with Multi-TP
- DCA with ATR-based TP/SL
- Multi-Timeframe filtering
"""

from backend.backtesting.dca_strategies.dca_multi_tp import (
    DCADealState,
    DCADirection,
    DCAMultiTPConfig,
    DCAMultiTPStrategy,
    SLMode,
    TPMode,
    create_dca_long_atr_tp_sl,
    create_dca_long_multi_tp,
    create_dca_short_atr_tp_sl,
    create_dca_short_multi_tp,
)

__all__ = [
    "DCADirection",
    "DCADealState",
    "DCAMultiTPConfig",
    "DCAMultiTPStrategy",
    "TPMode",
    "SLMode",
    "create_dca_long_multi_tp",
    "create_dca_short_multi_tp",
    "create_dca_long_atr_tp_sl",
    "create_dca_short_atr_tp_sl",
]
