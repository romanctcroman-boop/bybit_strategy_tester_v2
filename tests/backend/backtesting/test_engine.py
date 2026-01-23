"""
Tests for Backtesting Engine

Tests strategy implementations, engine execution, and metrics calculation.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from backend.backtesting.engine import BacktestEngine, get_engine
from backend.backtesting.models import (
    BacktestConfig,
    BacktestStatus,
    StrategyType,
)
from backend.backtesting.strategies import (
    BollingerBandsStrategy,
    MACDStrategy,
    RSIStrategy,
    SMAStrategy,
    get_strategy,
    list_available_strategies,
)

# ============================================
# Fixtures
# ============================================


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate sample OHLCV data for testing"""
    np.random.seed(42)

    n_periods = 500
    dates = pd.date_range(
        start="2024-01-01",
        periods=n_periods,
        freq="1h",
        tz=timezone.utc,
    )

    # Generate random walk price
    returns = np.random.normal(0.0002, 0.02, n_periods)
    close = 40000 * np.exp(np.cumsum(returns))

    # Generate OHLC from close
    high = close * (1 + np.abs(np.random.normal(0, 0.005, n_periods)))
    low = close * (1 - np.abs(np.random.normal(0, 0.005, n_periods)))
    open_price = close + np.random.normal(0, 50, n_periods)
    volume = np.random.uniform(100, 1000, n_periods)

    return pd.DataFrame(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


@pytest.fixture
def engine() -> BacktestEngine:
    """Get backtest engine instance"""
    return BacktestEngine()


@pytest.fixture
def sample_config() -> BacktestConfig:
    """Sample backtest configuration"""
    return BacktestConfig(
        symbol="BTCUSDT",
        interval="1h",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 1, 21, tzinfo=timezone.utc),
        strategy_type=StrategyType.SMA_CROSSOVER,
        strategy_params={"fast_period": 10, "slow_period": 30},
        initial_capital=10000.0,
        position_size=1.0,
    )


# ============================================
# Strategy Tests
# ============================================


class TestSMAStrategy:
    """Tests for SMA Crossover Strategy"""

    def test_default_params(self):
        """Test default parameters"""
        strategy = SMAStrategy()
        assert strategy.fast_period == 10
        assert strategy.slow_period == 30

    def test_custom_params(self):
        """Test custom parameters"""
        strategy = SMAStrategy({"fast_period": 5, "slow_period": 20})
        assert strategy.fast_period == 5
        assert strategy.slow_period == 20

    def test_invalid_params(self):
        """Test validation of invalid parameters"""
        with pytest.raises(ValueError, match="fast_period.*must be.*slow_period"):
            SMAStrategy({"fast_period": 30, "slow_period": 10})

    def test_generate_signals(self, sample_ohlcv):
        """Test signal generation"""
        strategy = SMAStrategy({"fast_period": 10, "slow_period": 30})
        signals = strategy.generate_signals(sample_ohlcv)

        assert len(signals.entries) == len(sample_ohlcv)
        assert len(signals.exits) == len(sample_ohlcv)
        assert signals.entries.dtype == bool
        assert signals.exits.dtype == bool

        # Should have at least some signals
        assert signals.entries.sum() > 0
        assert signals.exits.sum() > 0


class TestRSIStrategy:
    """Tests for RSI Strategy"""

    def test_default_params(self):
        """Test default parameters"""
        strategy = RSIStrategy()
        assert strategy.period == 14
        assert strategy.oversold == 30
        assert strategy.overbought == 70

    def test_custom_params(self):
        """Test custom parameters"""
        strategy = RSIStrategy({"period": 7, "oversold": 20, "overbought": 80})
        assert strategy.period == 7
        assert strategy.oversold == 20
        assert strategy.overbought == 80

    def test_invalid_levels(self):
        """Test validation of invalid levels"""
        with pytest.raises(ValueError, match="Invalid levels"):
            RSIStrategy({"oversold": 80, "overbought": 20})

    def test_generate_signals(self, sample_ohlcv):
        """Test signal generation"""
        strategy = RSIStrategy()
        signals = strategy.generate_signals(sample_ohlcv)

        assert len(signals.entries) == len(sample_ohlcv)
        assert len(signals.exits) == len(sample_ohlcv)


class TestMACDStrategy:
    """Tests for MACD Strategy"""

    def test_default_params(self):
        """Test default parameters"""
        strategy = MACDStrategy()
        assert strategy.fast_period == 12
        assert strategy.slow_period == 26
        assert strategy.signal_period == 9

    def test_generate_signals(self, sample_ohlcv):
        """Test signal generation"""
        strategy = MACDStrategy()
        signals = strategy.generate_signals(sample_ohlcv)

        assert len(signals.entries) == len(sample_ohlcv)
        assert len(signals.exits) == len(sample_ohlcv)


class TestBollingerBandsStrategy:
    """Tests for Bollinger Bands Strategy"""

    def test_default_params(self):
        """Test default parameters"""
        strategy = BollingerBandsStrategy()
        assert strategy.period == 20
        assert strategy.std_dev == 2.0

    def test_generate_signals(self, sample_ohlcv):
        """Test signal generation"""
        strategy = BollingerBandsStrategy()
        signals = strategy.generate_signals(sample_ohlcv)

        assert len(signals.entries) == len(sample_ohlcv)
        assert len(signals.exits) == len(sample_ohlcv)


class TestStrategyRegistry:
    """Tests for strategy factory and registry"""

    def test_get_strategy(self):
        """Test getting strategy by name"""
        strategy = get_strategy("sma_crossover")
        assert isinstance(strategy, SMAStrategy)

        strategy = get_strategy("rsi", {"period": 7})
        assert isinstance(strategy, RSIStrategy)
        assert strategy.period == 7

    def test_unknown_strategy(self):
        """Test error on unknown strategy"""
        with pytest.raises(ValueError, match="Unknown strategy type"):
            get_strategy("unknown_strategy")

    def test_list_strategies(self):
        """Test listing available strategies"""
        strategies = list_available_strategies()

        assert len(strategies) >= 4
        assert any(s["name"] == "sma_crossover" for s in strategies)
        assert any(s["name"] == "rsi" for s in strategies)
        assert any(s["name"] == "macd" for s in strategies)
        assert any(s["name"] == "bollinger_bands" for s in strategies)

        # Each strategy should have name, description, default_params
        for s in strategies:
            assert "name" in s
            assert "description" in s
            assert "default_params" in s


# ============================================
# Engine Tests
# ============================================


class TestBacktestEngine:
    """Tests for BacktestEngine"""

    def test_engine_creation(self, engine):
        """Test engine instantiation"""
        assert engine is not None

    def test_global_engine(self):
        """Test global engine singleton"""
        engine1 = get_engine()
        engine2 = get_engine()
        assert engine1 is engine2

    def test_run_backtest_sma(self, engine, sample_ohlcv, sample_config):
        """Test running SMA backtest"""
        result = engine.run(sample_config, sample_ohlcv)

        assert result.id is not None
        assert result.status == BacktestStatus.COMPLETED
        assert result.metrics is not None
        assert result.config == sample_config

        # Check metrics are calculated
        metrics = result.metrics
        assert metrics.total_trades >= 0
        assert 0 <= metrics.win_rate <= 100  # win_rate is percentage (0-100)
        assert metrics.sharpe_ratio is not None

    def test_run_backtest_rsi(self, engine, sample_ohlcv):
        """Test running RSI backtest"""
        config = BacktestConfig(
            symbol="BTCUSDT",
            interval="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 21, tzinfo=timezone.utc),
            strategy_type=StrategyType.RSI,
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000.0,
        )

        result = engine.run(config, sample_ohlcv)
        assert result.status == BacktestStatus.COMPLETED

    def test_run_backtest_macd(self, engine, sample_ohlcv):
        """Test running MACD backtest"""
        config = BacktestConfig(
            symbol="BTCUSDT",
            interval="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 21, tzinfo=timezone.utc),
            strategy_type=StrategyType.MACD,
            initial_capital=10000.0,
        )

        result = engine.run(config, sample_ohlcv)
        assert result.status == BacktestStatus.COMPLETED

    def test_equity_curve(self, engine, sample_ohlcv, sample_config):
        """Test equity curve generation"""
        result = engine.run(sample_config, sample_ohlcv)

        assert result.equity_curve is not None
        assert len(result.equity_curve.equity) > 0
        assert len(result.equity_curve.timestamps) == len(result.equity_curve.equity)

        # First equity should be close to initial capital
        assert result.equity_curve.equity[0] >= sample_config.initial_capital * 0.9

    def test_trade_records(self, engine, sample_ohlcv, sample_config):
        """Test trade records extraction"""
        result = engine.run(sample_config, sample_ohlcv)

        if result.metrics.total_trades > 0:
            assert len(result.trades) > 0

            trade = result.trades[0]
            assert trade.entry_time is not None
            assert trade.exit_time is not None
            assert trade.entry_price > 0
            assert trade.exit_price > 0

    def test_insufficient_data(self, engine, sample_config):
        """Test handling of insufficient data"""
        small_ohlcv = pd.DataFrame(
            {
                "open": [100, 101],
                "high": [102, 103],
                "low": [99, 100],
                "close": [101, 102],
                "volume": [1000, 1100],
            },
            index=pd.date_range("2024-01-01", periods=2, freq="1h"),
        )

        result = engine.run(sample_config, small_ohlcv)
        assert result.status == BacktestStatus.FAILED
        assert "Insufficient data" in result.error_message

    def test_missing_columns(self, engine, sample_config):
        """Test handling of missing OHLCV columns"""
        bad_ohlcv = pd.DataFrame(
            {
                "close": [100, 101, 102],
            },
            index=pd.date_range("2024-01-01", periods=3, freq="1h"),
        )

        result = engine.run(sample_config, bad_ohlcv)
        assert result.status == BacktestStatus.FAILED
        assert "Missing required columns" in result.error_message

    def test_result_caching(self, engine, sample_ohlcv, sample_config):
        """Test result caching"""
        result = engine.run(sample_config, sample_ohlcv)

        cached = engine.get_result(result.id)
        assert cached is not None
        assert cached.id == result.id

        # List results
        results = engine.list_results()
        assert len(results) >= 1
        assert any(r.id == result.id for r in results)


# ============================================
# Metrics Tests
# ============================================


class TestPerformanceMetrics:
    """Tests for performance metrics calculation"""

    def test_sharpe_ratio(self, engine, sample_ohlcv, sample_config):
        """Test Sharpe ratio calculation"""
        result = engine.run(sample_config, sample_ohlcv)

        # Sharpe should be a reasonable number (not NaN or inf)
        assert not np.isnan(result.metrics.sharpe_ratio)
        assert not np.isinf(result.metrics.sharpe_ratio)

    def test_max_drawdown(self, engine, sample_ohlcv, sample_config):
        """Test max drawdown calculation"""
        result = engine.run(sample_config, sample_ohlcv)

        # Drawdown is percentage (0-100)
        assert 0 <= result.metrics.max_drawdown <= 100

    def test_win_rate(self, engine, sample_ohlcv, sample_config):
        """Test win rate calculation"""
        result = engine.run(sample_config, sample_ohlcv)

        # Win rate is percentage (0-100)
        assert 0 <= result.metrics.win_rate <= 100

        # Winning + losing trades should approximately equal total trades
        # (may differ due to break-even trades or open positions)
        assert (
            result.metrics.winning_trades + result.metrics.losing_trades
            <= result.metrics.total_trades
        )
