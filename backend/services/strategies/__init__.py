"""
Strategy Library - Pre-built Trading Strategies.

This module provides production-ready trading strategies that can be used
directly with the LiveStrategyRunner for live trading or backtesting.

Strategy Categories:
1. Trend Following - Follow market trends (EMA Cross, MACD, ADX)
2. Mean Reversion - Trade price reversion to mean (RSI, Bollinger)
3. Momentum - Trade momentum continuation (RSI Momentum, MACD)
4. Breakout - Trade price breakouts (Support/Resistance, ATR)
5. Grid Trading - Place orders at regular intervals
6. DCA - Dollar Cost Averaging

Each strategy:
- Inherits from BaseStrategy
- Has configurable parameters
- Includes parameter optimization ranges
- Has factory functions for common configurations

Example:
    from backend.services.strategies import (
        EMACrossoverStrategy,
        RSIMeanReversionStrategy,
        create_conservative_ema_strategy,
    )

    # Create with custom params
    strategy = EMACrossoverStrategy(
        config=config,
        fast_period=10,
        slow_period=21
    )

    # Or use factory
    strategy = create_conservative_ema_strategy(config)

    # Add to runner
    runner.add_strategy(strategy)
"""

from backend.services.strategies.base import (
    ParameterSpec,
    ParameterType,
    StrategyCategory,
    StrategyInfo,
    StrategyRegistry,
)
from backend.services.strategies.breakout import (
    ATRBreakoutParams,
    # ATR Breakout
    ATRBreakoutStrategy,
    DonchianBreakoutParams,
    # Donchian Channel
    DonchianBreakoutStrategy,
)
from backend.services.strategies.dca import (
    DCAParams,
    DCAStrategy,
    create_aggressive_dca_strategy,
    create_standard_dca_strategy,
)
from backend.services.strategies.grid_trading import (
    GridTradingParams,
    GridTradingStrategy,
    create_conservative_grid_strategy,
    create_moderate_grid_strategy,
)
from backend.services.strategies.mean_reversion import (
    BollingerBandsParams,
    # Bollinger Bands
    BollingerBandsStrategy,
    RSIMeanReversionParams,
    # RSI Mean Reversion
    RSIMeanReversionStrategy,
    create_aggressive_bollinger_strategy,
    create_aggressive_rsi_strategy,
    create_conservative_bollinger_strategy,
    create_conservative_rsi_strategy,
    create_moderate_bollinger_strategy,
    create_moderate_rsi_strategy,
)
from backend.services.strategies.momentum import (
    RSIMomentumParams,
    # RSI Momentum
    RSIMomentumStrategy,
    StochasticMomentumParams,
    # Stochastic
    StochasticMomentumStrategy,
)
from backend.services.strategies.trend_following import (
    EMACrossoverParams,
    # EMA Crossover
    EMACrossoverStrategy,
    MACDTrendParams,
    # MACD Trend
    MACDTrendStrategy,
    TripleEMAParams,
    # Triple EMA
    TripleEMAStrategy,
    create_aggressive_ema_strategy,
    create_aggressive_macd_strategy,
    create_conservative_ema_strategy,
    create_conservative_macd_strategy,
    create_moderate_ema_strategy,
    create_moderate_macd_strategy,
)

__all__ = [
    # Base
    "StrategyInfo",
    "StrategyCategory",
    "ParameterSpec",
    "ParameterType",
    "StrategyRegistry",
    # Trend Following
    "EMACrossoverStrategy",
    "EMACrossoverParams",
    "create_conservative_ema_strategy",
    "create_moderate_ema_strategy",
    "create_aggressive_ema_strategy",
    "MACDTrendStrategy",
    "MACDTrendParams",
    "create_conservative_macd_strategy",
    "create_moderate_macd_strategy",
    "create_aggressive_macd_strategy",
    "TripleEMAStrategy",
    "TripleEMAParams",
    # Mean Reversion
    "RSIMeanReversionStrategy",
    "RSIMeanReversionParams",
    "create_conservative_rsi_strategy",
    "create_moderate_rsi_strategy",
    "create_aggressive_rsi_strategy",
    "BollingerBandsStrategy",
    "BollingerBandsParams",
    "create_conservative_bollinger_strategy",
    "create_moderate_bollinger_strategy",
    "create_aggressive_bollinger_strategy",
    # Momentum
    "RSIMomentumStrategy",
    "RSIMomentumParams",
    "StochasticMomentumStrategy",
    "StochasticMomentumParams",
    # Breakout
    "ATRBreakoutStrategy",
    "ATRBreakoutParams",
    "DonchianBreakoutStrategy",
    "DonchianBreakoutParams",
    # Grid Trading
    "GridTradingStrategy",
    "GridTradingParams",
    "create_conservative_grid_strategy",
    "create_moderate_grid_strategy",
    # DCA
    "DCAStrategy",
    "DCAParams",
    "create_standard_dca_strategy",
    "create_aggressive_dca_strategy",
]
