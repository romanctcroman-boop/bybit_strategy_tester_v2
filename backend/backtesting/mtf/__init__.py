"""
🎯 Multi-Timeframe (MTF) Backtesting Module

This module provides multi-timeframe support for backtesting strategies.
Key features:
- HTF trend filters (EMA200, SMA200)
- BTC correlation filters
- Lookahead prevention
- Signal enhancement with HTF context

Example usage:
    from backend.backtesting.mtf import (
        MTFDataLoader,
        HTFTrendFilter,
        BTCCorrelationFilter,
        create_htf_index_map,
    )

    # Load MTF data
    loader = MTFDataLoader()
    mtf_data = loader.load(
        symbol="ETHUSDT",
        ltf_interval="5",
        htf_interval="60",
        start_date="2024-01-01",
        end_date="2024-12-31"
    )

    # Create HTF filter
    htf_filter = HTFTrendFilter(period=200, filter_type="sma")

    # Generate signals with HTF filtering
    signals = generate_mtf_signals(
        ltf_candles=mtf_data.ltf_candles,
        htf_candles=mtf_data.htf_candles,
        htf_index_map=mtf_data.htf_index_map,
        htf_filter=htf_filter
    )
"""

from backend.backtesting.mtf.data_loader import MTFData, MTFDataLoader
from backend.backtesting.mtf.filters import (
    BTCCorrelationFilter,
    HTFFilter,
    HTFTrendFilter,
    IchimokuFilter,
    MACDFilter,
    SuperTrendFilter,
    calculate_atr,
    calculate_ichimoku,
    calculate_macd,
    calculate_supertrend,
)
from backend.backtesting.mtf.index_mapper import (
    create_htf_index_map,
    get_htf_bar_at_ltf,
)
from backend.backtesting.mtf.signals import (
    generate_mtf_rsi_signals,
    generate_mtf_sma_crossover_signals,
)

__all__ = [
    "BTCCorrelationFilter",
    # Filters
    "HTFFilter",
    "HTFTrendFilter",
    "IchimokuFilter",
    "MACDFilter",
    # Data
    "MTFData",
    "MTFDataLoader",
    "SuperTrendFilter",
    "calculate_atr",
    "calculate_ichimoku",
    "calculate_macd",
    # Indicator calculations
    "calculate_supertrend",
    # Index mapping
    "create_htf_index_map",
    # Signals
    "generate_mtf_rsi_signals",
    "generate_mtf_sma_crossover_signals",
    "get_htf_bar_at_ltf",
]
