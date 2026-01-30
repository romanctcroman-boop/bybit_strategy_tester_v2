"""
Tests for Strategy Portfolio Backtester.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.backtesting.interfaces import BacktestInput
from backend.backtesting.portfolio_strategy import (
    StrategyPortfolioBacktester,
    StrategyPortfolioResult,
    run_strategy_portfolio_backtest,
)
from backend.services.advanced_backtesting.portfolio import (
    AllocationMethod,
    AssetAllocation,
)


def create_test_candles(
    n_bars: int = 200,
    base_price: float = 100.0,
    trend: str = "up",
    volatility: float = 0.01,
) -> pd.DataFrame:
    """Create test OHLCV data."""
    timestamps = [datetime(2025, 1, 1) + timedelta(hours=i) for i in range(n_bars)]

    if trend == "up":
        closes = np.linspace(base_price, base_price * 1.3, n_bars)
    elif trend == "down":
        closes = np.linspace(base_price * 1.3, base_price, n_bars)
    else:
        closes = (
            base_price + np.sin(np.linspace(0, 4 * np.pi, n_bars)) * base_price * 0.1
        )

    # Add noise
    noise = np.random.normal(0, base_price * volatility, n_bars)
    closes = closes + noise

    highs = closes * 1.01
    lows = closes * 0.99
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    volumes = np.random.uniform(1000, 5000, n_bars)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def create_multi_asset_data(
    symbols: list[str], n_bars: int = 200
) -> dict[str, pd.DataFrame]:
    """Create test data for multiple assets."""
    np.random.seed(42)
    data = {}
    trends = ["up", "down", "sideways"]

    for i, symbol in enumerate(symbols):
        base_price = 100 * (i + 1)  # Different base prices
        trend = trends[i % len(trends)]
        data[symbol] = create_test_candles(n_bars, base_price, trend)

    return data


class TestStrategyPortfolioBacktester:
    """Test StrategyPortfolioBacktester."""

    def test_basic_portfolio_backtest(self):
        """Test basic portfolio backtest runs successfully."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        data = create_multi_asset_data(symbols)

        backtester = StrategyPortfolioBacktester(
            symbols=symbols,
            initial_capital=10000.0,
        )

        config = BacktestInput(
            candles=data["BTCUSDT"],  # Will be overridden
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
            direction="both",
        )

        result = backtester.run(data, config)

        assert result.status == "completed"
        assert len(result.per_asset) == 2
        assert "BTCUSDT" in result.per_asset
        assert "ETHUSDT" in result.per_asset

    def test_equal_weight_allocation(self):
        """Test equal weight allocation distributes capital evenly."""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        data = create_multi_asset_data(symbols)

        allocation = AssetAllocation(method=AllocationMethod.EQUAL_WEIGHT)
        expected_weight = 1.0 / len(symbols)

        backtester = StrategyPortfolioBacktester(
            symbols=symbols,
            initial_capital=10000.0,
        )

        config = BacktestInput(
            candles=data["BTCUSDT"],
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
        )

        result = backtester.run(data, config, allocation)

        # Check weights are equal
        for symbol, weight in result.config["weights"].items():
            assert abs(weight - expected_weight) < 0.01

    def test_risk_parity_allocation(self):
        """Test risk parity allocation weights by inverse volatility."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        data = create_multi_asset_data(symbols)

        allocation = AssetAllocation(method=AllocationMethod.RISK_PARITY)

        backtester = StrategyPortfolioBacktester(
            symbols=symbols,
            initial_capital=10000.0,
        )

        config = BacktestInput(
            candles=data["BTCUSDT"],
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
        )

        result = backtester.run(data, config, allocation)

        # Weights should sum to 1
        total_weight = sum(result.config["weights"].values())
        assert abs(total_weight - 1.0) < 0.01

    def test_portfolio_equity_aggregation(self):
        """Test portfolio equity curve is aggregated correctly."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        data = create_multi_asset_data(symbols)

        backtester = StrategyPortfolioBacktester(
            symbols=symbols,
            initial_capital=10000.0,
        )

        config = BacktestInput(
            candles=data["BTCUSDT"],
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
        )

        result = backtester.run(data, config)

        # Portfolio equity should exist
        assert len(result.portfolio_equity_curve) > 0

        # First value should be close to initial capital
        assert abs(result.portfolio_equity_curve[0] - 10000) < 1000

    def test_correlation_analysis(self):
        """Test correlation analysis is calculated."""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        data = create_multi_asset_data(symbols)

        backtester = StrategyPortfolioBacktester(
            symbols=symbols,
            initial_capital=10000.0,
        )

        config = BacktestInput(
            candles=data["BTCUSDT"],
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
        )

        result = backtester.run(data, config)

        # Correlation matrix should have all symbols
        assert len(result.correlation.correlation_matrix) == len(symbols)

        # Diagonal should be 1.0
        for symbol in symbols:
            assert result.correlation.correlation_matrix[symbol][symbol] == 1.0

    def test_trades_collected_from_all_assets(self):
        """Test that trades from all assets are collected."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        data = create_multi_asset_data(symbols, n_bars=500)

        backtester = StrategyPortfolioBacktester(
            symbols=symbols,
            initial_capital=10000.0,
        )

        config = BacktestInput(
            candles=data["BTCUSDT"],
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
            direction="both",
        )

        result = backtester.run(data, config)

        # Should have trades
        if result.all_trades:
            # Trades should have symbol tag
            symbols_in_trades = set(t["symbol"] for t in result.all_trades)
            assert len(symbols_in_trades) > 0

    def test_missing_data_error(self):
        """Test error handling when data is missing for a symbol."""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        data = create_multi_asset_data(["BTCUSDT", "ETHUSDT"])  # Missing SOLUSDT

        backtester = StrategyPortfolioBacktester(
            symbols=symbols,
            initial_capital=10000.0,
        )

        config = BacktestInput(
            candles=data["BTCUSDT"],
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
        )

        result = backtester.run(data, config)

        assert result.status == "error"
        assert "Missing" in result.config.get("error", "")

    def test_portfolio_metrics_calculation(self):
        """Test portfolio metrics are calculated."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        data = create_multi_asset_data(symbols, n_bars=365)

        backtester = StrategyPortfolioBacktester(
            symbols=symbols,
            initial_capital=10000.0,
        )

        config = BacktestInput(
            candles=data["BTCUSDT"],
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
        )

        result = backtester.run(data, config)

        metrics = result.portfolio_metrics

        # Check metrics exist
        assert metrics is not None
        assert hasattr(metrics, "total_return")
        assert hasattr(metrics, "max_drawdown")
        assert hasattr(metrics, "sharpe_ratio")

    def test_convenience_function(self):
        """Test run_strategy_portfolio_backtest convenience function."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        data = create_multi_asset_data(symbols)

        config = BacktestInput(
            candles=data["BTCUSDT"],
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
        )

        result = run_strategy_portfolio_backtest(
            data=data,
            strategy_config=config,
            allocation_method="equal_weight",
            initial_capital=10000.0,
        )

        assert isinstance(result, StrategyPortfolioResult)
        assert result.status == "completed"

    def test_to_dict_serialization(self):
        """Test result can be serialized to dict."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        data = create_multi_asset_data(symbols)

        backtester = StrategyPortfolioBacktester(
            symbols=symbols,
            initial_capital=10000.0,
        )

        config = BacktestInput(
            candles=data["BTCUSDT"],
            symbol="BTCUSDT",
            interval="60",
            initial_capital=10000,
            leverage=1,
            stop_loss=0.02,
            take_profit=0.03,
        )

        result = backtester.run(data, config)
        result_dict = result.to_dict()

        assert "status" in result_dict
        assert "per_asset" in result_dict
        assert "portfolio_metrics" in result_dict
        assert "config" in result_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
