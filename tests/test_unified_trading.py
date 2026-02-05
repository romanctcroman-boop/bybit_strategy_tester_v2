"""
Unit tests for unified Backtest/Paper/Live API.

StrategyRunner, SimulatedExecutor, mock DataProvider.
"""

import numpy as np
import pandas as pd

from backend.services.unified_trading.interfaces import DataProvider
from backend.services.unified_trading.simulated_executor import SimulatedExecutor
from backend.services.unified_trading.strategy_runner import StrategyRunner


class MockDataProvider(DataProvider):
    """Mock DataProvider для тестов без БД."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def get_klines(self, symbol: str, interval: str, limit: int, **kwargs) -> pd.DataFrame:
        out = self.df.head(limit).copy()
        return out

    def get_current_price(self, symbol: str) -> float:
        return float(self.df["close"].iloc[-1])


def _make_sample_klines(n: int = 50) -> pd.DataFrame:
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(n) * 0.3)
    prices = np.maximum(prices, 50)
    df = pd.DataFrame({
        "open": prices * 0.99,
        "high": prices * 1.02,
        "low": prices * 0.98,
        "close": prices,
        "volume": np.random.rand(n) * 1e6,
    })
    df["open_time"] = pd.date_range("2024-01-01", periods=n, freq="1h")
    return df


def _simple_strategy(df):
    """Простая стратегия: buy при close > SMA(5), sell при close < SMA(5)."""
    if len(df) < 6:
        return False, False, 0.01
    close = df["close"].values
    sma = np.mean(close[-6:-1])
    last_close = close[-1]
    if last_close > sma * 1.001:
        return True, False, 0.01
    if last_close < sma * 0.999:
        return False, True, 0.01
    return False, False, 0.01


class TestStrategyRunner:
    def test_run_backtest_with_mock_provider(self):
        df = _make_sample_klines(30)
        provider = MockDataProvider(df)
        executor = SimulatedExecutor(slippage_bps=0, fill_probability=1.0)
        runner = StrategyRunner(provider, executor, initial_capital=10000.0)

        result = runner.run_backtest(
            symbol="BTCUSDT",
            interval="60",
            limit=30,
            strategy_fn=_simple_strategy,
            mode="backtest",
        )

        assert result.mode == "backtest"
        assert result.error is None
        assert len(result.equity_curve) > 1
        assert result.final_equity >= 0


class TestSimulatedExecutor:
    def test_place_market_order_with_price_provider(self):
        exec_ = SimulatedExecutor(slippage_bps=0, fill_probability=1.0)
        price = 100.0
        exec_.set_price_provider(lambda s: price)

        res = exec_.place_market_order("BTCUSDT", "buy", 0.1)
        assert res.status == "filled"
        assert res.filled_qty == 0.1
        assert res.filled_price == price
