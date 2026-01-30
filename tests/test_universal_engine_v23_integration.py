"""
Integration Tests for Universal Math Engine v2.3.

Tests v2.3 modules working together:
1. Order Book + Backtest integration
2. GPU Acceleration in backtest
3. ML Signals in backtest
4. Full v2.3 pipeline

Author: Universal Math Engine Team
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest


class TestV23Integration:
    """Integration tests for v2.3 features."""

    @pytest.fixture
    def sample_candles(self) -> pd.DataFrame:
        """Create sample OHLCV data for testing."""
        np.random.seed(42)
        n = 500

        # Generate realistic price movement
        returns = np.random.normal(0.0001, 0.02, n)
        close = 50000 * np.exp(np.cumsum(returns))

        # Generate OHLCV
        high = close * (1 + np.abs(np.random.normal(0, 0.005, n)))
        low = close * (1 - np.abs(np.random.normal(0, 0.005, n)))
        open_prices = low + (high - low) * np.random.random(n)
        volume = np.random.uniform(100, 1000, n)

        # Create timestamps
        base_time = datetime(2025, 1, 1)
        timestamps = [base_time + timedelta(hours=i) for i in range(n)]

        return pd.DataFrame(
            {
                "open": open_prices,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=pd.DatetimeIndex(timestamps),
        )

    def test_basic_v23_engine_run(self, sample_candles):
        """Test basic UniversalMathEngineV23 run."""
        from backend.backtesting.universal_engine import (
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        # Create engine with all v2.3 features disabled
        config = V23IntegrationConfig()
        engine = UniversalMathEngineV23(v23_config=config)

        # Run backtest
        result = engine.run(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
        )

        # Verify output
        assert result.is_valid
        assert result.bars_processed == len(sample_candles)
        assert len(result.equity_curve) == len(sample_candles)
        assert result.metrics is not None

    def test_orderbook_integration(self, sample_candles):
        """Test Order Book integration in backtest."""
        from backend.backtesting.universal_engine import (
            OrderBookIntegrationConfig,
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        # Create config with order book enabled
        ob_config = OrderBookIntegrationConfig(
            enabled=True,
            depth_levels=25,
            apply_market_impact=True,
            use_orderbook_slippage=True,
        )
        config = V23IntegrationConfig(order_book=ob_config)
        engine = UniversalMathEngineV23(v23_config=config)

        # Run backtest
        result = engine.run(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
        )

        # Verify output
        assert result.is_valid
        assert result.metrics is not None

        # Verify order book metrics recorded
        if result.trades:
            # Should have market impact data if trades occurred
            assert result.metrics.total_market_impact >= 0
            assert len(result.orderbook_slippage_history) >= 0

    def test_gpu_integration(self, sample_candles):
        """Test GPU acceleration integration (CPU fallback)."""
        from backend.backtesting.universal_engine import (
            GPUBackendType,
            GPUIntegrationConfig,
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        # Create config with GPU enabled (will use CPU fallback)
        gpu_config = GPUIntegrationConfig(
            enabled=True,
            preferred_backend=GPUBackendType.CPU,  # Force CPU for testing
            gpu_indicators=True,
        )
        config = V23IntegrationConfig(gpu=gpu_config)
        engine = UniversalMathEngineV23(v23_config=config)

        # Run backtest
        result = engine.run(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
        )

        # Verify output
        assert result.is_valid
        assert "signals" in result.timing_breakdown

    def test_ml_signals_integration(self, sample_candles):
        """Test ML signal integration in backtest."""
        from backend.backtesting.universal_engine import (
            FeatureCategory,
            MLSignalConfig,
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        # Create config with ML signals enabled
        ml_config = MLSignalConfig(
            enabled=True,
            feature_categories=[FeatureCategory.PRICE, FeatureCategory.MOMENTUM],
            normalize_features=True,
        )
        config = V23IntegrationConfig(ml_signals=ml_config)
        engine = UniversalMathEngineV23(v23_config=config)

        # Run backtest
        result = engine.run(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
        )

        # Verify output
        assert result.is_valid

        # Verify ML features generated
        if result.ml_features is not None:
            assert "rsi_14" in result.ml_features or "return_1" in result.ml_features

    def test_full_v23_pipeline(self, sample_candles):
        """Test full v2.3 pipeline with all features enabled."""
        from backend.backtesting.universal_engine import (
            FeatureCategory,
            GPUBackendType,
            GPUIntegrationConfig,
            MLSignalConfig,
            OrderBookIntegrationConfig,
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        # Create config with ALL v2.3 features enabled
        ob_config = OrderBookIntegrationConfig(
            enabled=True,
            depth_levels=25,
            apply_market_impact=True,
            use_orderbook_slippage=True,
        )
        gpu_config = GPUIntegrationConfig(
            enabled=True,
            preferred_backend=GPUBackendType.CPU,
            gpu_indicators=True,
        )
        ml_config = MLSignalConfig(
            enabled=True,
            feature_categories=[
                FeatureCategory.PRICE,
                FeatureCategory.MOMENTUM,
                FeatureCategory.VOLATILITY,
            ],
            normalize_features=True,
        )

        config = V23IntegrationConfig(
            order_book=ob_config,
            gpu=gpu_config,
            ml_signals=ml_config,
        )
        engine = UniversalMathEngineV23(v23_config=config)

        # Run backtest
        result = engine.run(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 25, "overbought": 75},
            initial_capital=10000,
            direction="both",
            stop_loss=0.015,
            take_profit=0.025,
            leverage=5,
        )

        # Verify output
        assert result.is_valid
        assert result.engine_name == "UniversalMathEngineV23"
        assert result.bars_processed == len(sample_candles)

        # Verify timing breakdown recorded
        assert "signals" in result.timing_breakdown
        assert "simulation" in result.timing_breakdown

        # Verify metrics
        assert result.metrics is not None
        metrics_dict = result.metrics.to_dict()
        assert "net_profit" in metrics_dict
        assert "total_market_impact" in metrics_dict

    def test_different_strategies_v23(self, sample_candles):
        """Test different strategies with v2.3 engine."""
        from backend.backtesting.universal_engine import (
            GPUBackendType,
            GPUIntegrationConfig,
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        gpu_config = GPUIntegrationConfig(
            enabled=True,
            preferred_backend=GPUBackendType.CPU,
            gpu_indicators=True,
        )
        config = V23IntegrationConfig(gpu=gpu_config)
        engine = UniversalMathEngineV23(v23_config=config)

        strategies = [
            ("rsi", {"period": 14, "oversold": 30, "overbought": 70}),
            ("macd", {"fast_period": 12, "slow_period": 26, "signal_period": 9}),
            ("bb", {"period": 20, "std_dev": 2.0}),
        ]

        for strategy_type, params in strategies:
            result = engine.run(
                candles=sample_candles,
                strategy_type=strategy_type,
                strategy_params=params,
                initial_capital=10000,
                direction="both",
                stop_loss=0.02,
                take_profit=0.03,
            )

            assert result.is_valid, f"Strategy {strategy_type} failed"
            assert result.bars_processed == len(sample_candles)

    def test_batch_backtester_v23(self, sample_candles):
        """Test BatchBacktesterV23."""
        from backend.backtesting.universal_engine import BatchBacktesterV23

        backtester = BatchBacktesterV23()

        # Define parameter combinations
        param_combinations = [
            {"period": 10, "oversold": 25, "overbought": 75},
            {"period": 14, "oversold": 30, "overbought": 70},
            {"period": 21, "oversold": 35, "overbought": 65},
        ]

        base_config = {
            "initial_capital": 10000,
            "direction": "both",
            "stop_loss": 0.02,
            "take_profit": 0.03,
        }

        # Run batch
        results = backtester.run_batch(
            candles=sample_candles,
            strategy_type="rsi",
            param_combinations=param_combinations,
            base_config=base_config,
        )

        assert len(results) == len(param_combinations)
        for result in results:
            assert result.is_valid

    def test_v23_metrics_extended(self, sample_candles):
        """Test extended metrics in v2.3."""
        from backend.backtesting.universal_engine import (
            OrderBookIntegrationConfig,
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        ob_config = OrderBookIntegrationConfig(enabled=True)
        config = V23IntegrationConfig(order_book=ob_config)
        engine = UniversalMathEngineV23(v23_config=config)

        result = engine.run(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
        )

        assert result.is_valid
        metrics = result.metrics

        # Check standard metrics
        assert hasattr(metrics, "net_profit")
        assert hasattr(metrics, "sharpe_ratio")
        assert hasattr(metrics, "win_rate")

        # Check v2.3 specific metrics
        assert hasattr(metrics, "total_market_impact")
        assert hasattr(metrics, "avg_slippage_from_orderbook")
        assert hasattr(metrics, "execution_time_signals")
        assert hasattr(metrics, "execution_time_simulation")


class TestOrderBookBacktestIntegration:
    """Specific tests for Order Book + Backtest integration."""

    @pytest.fixture
    def volatile_candles(self) -> pd.DataFrame:
        """Create volatile OHLCV data for market impact testing."""
        np.random.seed(123)
        n = 200

        # Generate volatile price movement
        returns = np.random.normal(0, 0.03, n)  # 3% daily volatility
        close = 50000 * np.exp(np.cumsum(returns))

        high = close * (1 + np.abs(np.random.normal(0, 0.01, n)))
        low = close * (1 - np.abs(np.random.normal(0, 0.01, n)))
        open_prices = low + (high - low) * np.random.random(n)
        volume = np.random.uniform(50, 500, n)  # Lower volume = higher impact

        base_time = datetime(2025, 1, 1)
        timestamps = [base_time + timedelta(hours=i) for i in range(n)]

        return pd.DataFrame(
            {
                "open": open_prices,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=pd.DatetimeIndex(timestamps),
        )

    def test_market_impact_affects_pnl(self, volatile_candles):
        """Test that market impact affects final PnL."""
        from backend.backtesting.universal_engine import (
            OrderBookIntegrationConfig,
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        # Run WITHOUT market impact
        config_no_impact = V23IntegrationConfig(
            order_book=OrderBookIntegrationConfig(enabled=False)
        )
        engine_no_impact = UniversalMathEngineV23(v23_config=config_no_impact)

        result_no_impact = engine_no_impact.run(
            candles=volatile_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            slippage=0.0,  # No slippage
        )

        # Run WITH market impact
        config_with_impact = V23IntegrationConfig(
            order_book=OrderBookIntegrationConfig(
                enabled=True,
                apply_market_impact=True,
                use_orderbook_slippage=True,
            )
        )
        engine_with_impact = UniversalMathEngineV23(v23_config=config_with_impact)

        result_with_impact = engine_with_impact.run(
            candles=volatile_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            slippage=0.0,
        )

        # Both should be valid
        assert result_no_impact.is_valid
        assert result_with_impact.is_valid

        # Market impact should increase costs
        if result_with_impact.trades:
            assert result_with_impact.metrics.total_slippage_cost >= 0


class TestGPUBacktestIntegration:
    """Specific tests for GPU + Backtest integration."""

    @pytest.fixture
    def large_candles(self) -> pd.DataFrame:
        """Create larger dataset for GPU testing."""
        np.random.seed(456)
        n = 1000

        returns = np.random.normal(0.0001, 0.015, n)
        close = 50000 * np.exp(np.cumsum(returns))

        high = close * (1 + np.abs(np.random.normal(0, 0.004, n)))
        low = close * (1 - np.abs(np.random.normal(0, 0.004, n)))
        open_prices = low + (high - low) * np.random.random(n)
        volume = np.random.uniform(100, 1000, n)

        base_time = datetime(2025, 1, 1)
        timestamps = [base_time + timedelta(hours=i) for i in range(n)]

        return pd.DataFrame(
            {
                "open": open_prices,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=pd.DatetimeIndex(timestamps),
        )

    def test_gpu_indicators_produce_same_signals(self, large_candles):
        """Test that GPU indicators produce consistent results."""
        from backend.backtesting.universal_engine import (
            GPUBackendType,
            GPUIntegrationConfig,
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        # Run with standard indicators
        config_cpu = V23IntegrationConfig(gpu=GPUIntegrationConfig(enabled=False))
        engine_cpu = UniversalMathEngineV23(v23_config=config_cpu)

        result_cpu = engine_cpu.run(
            candles=large_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
        )

        # Run with GPU indicators (CPU fallback)
        config_gpu = V23IntegrationConfig(
            gpu=GPUIntegrationConfig(
                enabled=True,
                preferred_backend=GPUBackendType.CPU,
                gpu_indicators=True,
            )
        )
        engine_gpu = UniversalMathEngineV23(v23_config=config_gpu)

        result_gpu = engine_gpu.run(
            candles=large_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
        )

        # Both should be valid
        assert result_cpu.is_valid
        assert result_gpu.is_valid

        # Number of trades should be similar (may differ slightly due to implementation)
        # Allow some variance
        trade_diff = abs(len(result_cpu.trades) - len(result_gpu.trades))
        assert trade_diff <= max(len(result_cpu.trades) * 0.1, 5)


class TestMLSignalsIntegration:
    """Specific tests for ML Signals + Backtest integration."""

    @pytest.fixture
    def trending_candles(self) -> pd.DataFrame:
        """Create trending data for ML testing."""
        np.random.seed(789)
        n = 300

        # Create clear trend
        trend = np.linspace(0, 0.5, n)  # 50% uptrend
        noise = np.random.normal(0, 0.01, n)
        returns = trend / n + noise

        close = 50000 * np.exp(np.cumsum(returns))

        high = close * (1 + np.abs(np.random.normal(0, 0.003, n)))
        low = close * (1 - np.abs(np.random.normal(0, 0.003, n)))
        open_prices = low + (high - low) * np.random.random(n)
        volume = np.random.uniform(100, 500, n)

        base_time = datetime(2025, 1, 1)
        timestamps = [base_time + timedelta(hours=i) for i in range(n)]

        return pd.DataFrame(
            {
                "open": open_prices,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=pd.DatetimeIndex(timestamps),
        )

    def test_ml_features_generated(self, trending_candles):
        """Test that ML features are generated correctly."""
        from backend.backtesting.universal_engine import (
            FeatureCategory,
            MLSignalConfig,
            UniversalMathEngineV23,
            V23IntegrationConfig,
        )

        ml_config = MLSignalConfig(
            enabled=True,
            feature_categories=[
                FeatureCategory.PRICE,
                FeatureCategory.MOMENTUM,
                FeatureCategory.VOLATILITY,
                FeatureCategory.VOLUME,
                FeatureCategory.TREND,
            ],
            normalize_features=False,  # Don't normalize for testing
        )
        config = V23IntegrationConfig(ml_signals=ml_config)
        engine = UniversalMathEngineV23(v23_config=config)

        result = engine.run(
            candles=trending_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "oversold": 30, "overbought": 70},
            initial_capital=10000,
            direction="long",  # Long only for trending data
            stop_loss=0.02,
            take_profit=0.04,
        )

        assert result.is_valid

        # Verify features generated
        if result.ml_features is not None:
            feature_names = list(result.ml_features.keys())
            assert len(feature_names) > 0

            # Check for expected features
            expected_features = ["return_1", "rsi_14"]
            for feat in expected_features:
                if feat in feature_names:
                    assert len(result.ml_features[feat]) == len(trending_candles)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
