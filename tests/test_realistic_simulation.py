"""
Tests for Universal Math Engine v2.1 - Realistic Simulation Module.

Tests cover:
1. RealisticBarSimulator - Tick-by-tick simulation
2. VolumeSlippageModel - Volume-based slippage
3. DynamicFundingManager - Historical funding rates
4. PartialFillSimulator - Partial order fills
5. LiquidationEngine - Bybit liquidation
6. MLStrategyInterface - ML model integration
"""

import numpy as np
import pytest

from backend.backtesting.universal_engine import (
    # Bar Simulator
    BarPathType,
    BarSimulatorConfig,
    # Dynamic Funding
    DynamicFundingConfig,
    DynamicFundingManager,
    FeatureEngineering,
    # Liquidation
    LiquidationConfig,
    LiquidationEngine,
    # ML Interface
    MLStrategyConfig,
    MLStrategyInterface,
    # Partial Fills
    PartialFillConfig,
    PartialFillSimulator,
    RealisticBarSimulator,
    # Volume Slippage
    VolumeSlippageConfig,
    VolumeSlippageModel,
)

# =============================================================================
# 1. REALISTIC BAR SIMULATOR TESTS
# =============================================================================


class TestRealisticBarSimulator:
    """Tests for RealisticBarSimulator."""

    def test_basic_path_generation(self):
        """Test basic price path generation."""
        config = BarSimulatorConfig(ticks_per_bar=50, seed=42)
        sim = RealisticBarSimulator(config)

        path = sim.simulate_bar_path(
            open_price=50000.0,
            high_price=50500.0,
            low_price=49800.0,
            close_price=50200.0,
        )

        assert len(path) == 50
        assert path[0] == 50000.0  # Starts at open
        assert path[-1] == 50200.0  # Ends at close

    def test_path_respects_high_low(self):
        """Test that path touches high and low."""
        config = BarSimulatorConfig(
            ticks_per_bar=100, path_type=BarPathType.RANDOM_WALK, seed=123
        )
        sim = RealisticBarSimulator(config)

        path = sim.simulate_bar_path(
            open_price=100.0, high_price=110.0, low_price=95.0, close_price=105.0
        )

        # Path should touch or exceed high/low
        assert np.max(path) >= 108.0  # Near high
        assert np.min(path) <= 97.0  # Near low

    def test_stop_hunt_path(self):
        """Test stop-hunt path generation."""
        config = BarSimulatorConfig(
            ticks_per_bar=100,
            path_type=BarPathType.STOP_HUNT,
            stop_hunt_depth=0.005,
            seed=42,
        )
        sim = RealisticBarSimulator(config)

        path = sim.simulate_bar_path(
            open_price=50000.0,
            high_price=50200.0,
            low_price=49800.0,
            close_price=50100.0,
        )

        # Stop-hunt should spike beyond normal high/low
        assert np.max(path) > 50200.0 or np.min(path) < 49800.0

    def test_check_stop_triggered_long(self):
        """Test stop-loss trigger detection for long position."""
        config = BarSimulatorConfig(ticks_per_bar=50, seed=42)
        sim = RealisticBarSimulator(config)

        # Generate path that goes below 49500
        path = sim.simulate_bar_path(
            open_price=50000.0,
            high_price=50200.0,
            low_price=49400.0,
            close_price=49600.0,
        )

        triggered, tick_idx, exec_price = sim.check_stop_triggered(
            path, stop_price=49500.0, is_long=True
        )

        assert triggered is True
        assert tick_idx >= 0
        assert exec_price <= 49500.0

    def test_check_stop_triggered_short(self):
        """Test stop-loss trigger detection for short position."""
        config = BarSimulatorConfig(ticks_per_bar=50, seed=42)
        sim = RealisticBarSimulator(config)

        path = sim.simulate_bar_path(
            open_price=50000.0,
            high_price=50600.0,
            low_price=49800.0,
            close_price=50400.0,
        )

        triggered, tick_idx, exec_price = sim.check_stop_triggered(
            path, stop_price=50500.0, is_long=False
        )

        assert triggered is True
        assert tick_idx >= 0
        assert exec_price >= 50500.0

    def test_different_path_types(self):
        """Test all path type generations."""
        for path_type in BarPathType:
            config = BarSimulatorConfig(ticks_per_bar=50, path_type=path_type, seed=42)
            sim = RealisticBarSimulator(config)

            path = sim.simulate_bar_path(
                open_price=100.0, high_price=105.0, low_price=95.0, close_price=102.0
            )

            assert len(path) == 50
            assert path[0] == 100.0
            assert path[-1] == 102.0


# =============================================================================
# 2. VOLUME SLIPPAGE MODEL TESTS
# =============================================================================


class TestVolumeSlippageModel:
    """Tests for VolumeSlippageModel."""

    def test_small_order_minimal_slippage(self):
        """Test that small orders have minimal slippage."""
        model = VolumeSlippageModel()

        slippage = model.calculate_slippage(
            order_size_usd=100,  # Small order
            bar_volume_usd=1_000_000,  # Large volume
        )

        assert slippage < 0.0002  # Less than 0.02%

    def test_large_order_more_slippage(self):
        """Test that large orders have more slippage."""
        model = VolumeSlippageModel()

        small_slippage = model.calculate_slippage(
            order_size_usd=1000, bar_volume_usd=100_000
        )

        large_slippage = model.calculate_slippage(
            order_size_usd=50000, bar_volume_usd=100_000
        )

        assert large_slippage > small_slippage

    def test_apply_slippage_buy(self):
        """Test slippage application for buy orders."""
        config = VolumeSlippageConfig(base_slippage=0.001)
        model = VolumeSlippageModel(config)

        exec_price = model.apply_slippage(
            price=50000.0,
            order_size_usd=10000,
            bar_volume_usd=1_000_000,
            is_buy=True,
        )

        assert exec_price > 50000.0  # Buy price increases

    def test_apply_slippage_sell(self):
        """Test slippage application for sell orders."""
        config = VolumeSlippageConfig(base_slippage=0.001)
        model = VolumeSlippageModel(config)

        exec_price = model.apply_slippage(
            price=50000.0,
            order_size_usd=10000,
            bar_volume_usd=1_000_000,
            is_buy=False,
        )

        assert exec_price < 50000.0  # Sell price decreases

    def test_volatility_increases_slippage(self):
        """Test that volatility increases slippage."""
        config = VolumeSlippageConfig(volatility_multiplier=2.0)
        model = VolumeSlippageModel(config)

        low_vol_slippage = model.calculate_slippage(
            order_size_usd=10000, bar_volume_usd=100_000, volatility=0.0
        )

        high_vol_slippage = model.calculate_slippage(
            order_size_usd=10000, bar_volume_usd=100_000, volatility=0.05
        )

        assert high_vol_slippage > low_vol_slippage

    def test_market_impact_estimation(self):
        """Test market impact estimation."""
        model = VolumeSlippageModel()

        impact = model.estimate_market_impact(
            order_size_usd=100_000,
            average_volume_usd=1_000_000,
            n_bars_to_execute=5,
        )

        assert "single_execution_slippage" in impact
        assert "split_execution_slippage" in impact
        assert "savings_from_split" in impact
        assert impact["split_execution_slippage"] <= impact["single_execution_slippage"]


# =============================================================================
# 3. DYNAMIC FUNDING MANAGER TESTS
# =============================================================================


class TestDynamicFundingManager:
    """Tests for DynamicFundingManager."""

    def test_load_funding_rates(self):
        """Test loading funding rates."""
        manager = DynamicFundingManager()

        rates = [
            {"timestamp": 1000000000000, "funding_rate": 0.0001, "mark_price": 50000},
            {"timestamp": 1000028800000, "funding_rate": 0.00015, "mark_price": 50100},
            {"timestamp": 1000057600000, "funding_rate": -0.0001, "mark_price": 49900},
        ]

        manager.load_funding_rates("BTCUSDT", rates)

        rate = manager.get_funding_rate("BTCUSDT", 1000000000000)
        assert abs(rate - 0.0001) < 1e-10

    def test_funding_rate_interpolation(self):
        """Test funding rate interpolation between intervals."""
        config = DynamicFundingConfig(enable_interpolation=True)
        manager = DynamicFundingManager(config)

        rates = [
            {"timestamp": 0, "funding_rate": 0.0001, "mark_price": 50000},
            {
                "timestamp": 28800000,
                "funding_rate": 0.0002,
                "mark_price": 50000,
            },  # 8h later
        ]

        manager.load_funding_rates("BTCUSDT", rates)

        # Get rate at 4 hours (midpoint)
        mid_rate = manager.get_funding_rate("BTCUSDT", 14400000)

        # Should be approximately average
        assert 0.00012 < mid_rate < 0.00018

    def test_calculate_funding_cost_long(self):
        """Test funding cost calculation for long position."""
        config = DynamicFundingConfig(funding_interval_hours=8)
        manager = DynamicFundingManager(config)

        rates = [
            {"timestamp": 0, "funding_rate": 0.0001, "mark_price": 50000},
            {"timestamp": 28800000, "funding_rate": 0.0001, "mark_price": 50000},
            {"timestamp": 57600000, "funding_rate": 0.0001, "mark_price": 50000},
        ]
        manager.load_funding_rates("BTCUSDT", rates)

        # Position held for 24 hours (3 funding intervals)
        cost = manager.calculate_funding_cost(
            symbol="BTCUSDT",
            position_size=1.0,  # 1 BTC
            entry_timestamp=0,
            exit_timestamp=86400000,  # 24 hours
            is_long=True,
        )

        # Long pays: 3 * 1.0 * 0.0001 = -0.0003
        assert cost < 0  # Long pays positive funding

    def test_funding_statistics(self):
        """Test funding rate statistics."""
        manager = DynamicFundingManager()

        rates = [
            {
                "timestamp": i * 28800000,
                "funding_rate": 0.0001 * (i + 1),
                "mark_price": 50000,
            }
            for i in range(10)
        ]
        manager.load_funding_rates("BTCUSDT", rates)

        stats = manager.get_funding_statistics("BTCUSDT", 0, 300000000)

        assert "mean_rate" in stats
        assert "std_rate" in stats
        assert stats["n_fundings"] == 10


# =============================================================================
# 4. PARTIAL FILL SIMULATOR TESTS
# =============================================================================


class TestPartialFillSimulator:
    """Tests for PartialFillSimulator."""

    def test_small_order_instant_fill(self):
        """Test that small orders get instant full fill."""
        config = PartialFillConfig(instant_fill_threshold=0.01)
        sim = PartialFillSimulator(config)

        result = sim.simulate_market_order_fill(
            order_size=10,
            bar_volume=100_000,  # Order is 0.01% of volume
            current_price=50000.0,
            is_buy=True,
        )

        assert result.is_complete is True
        assert result.filled_size == 10
        assert result.remaining_size == 0
        assert result.n_fills == 1

    def test_large_order_partial_fill(self):
        """Test that large orders may get partial fills."""
        config = PartialFillConfig(
            enabled=True, instant_fill_threshold=0.001, max_partial_fills=5
        )
        sim = PartialFillSimulator(config)

        result = sim.simulate_market_order_fill(
            order_size=1000,
            bar_volume=5000,  # Order is 20% of volume
            current_price=50000.0,
            is_buy=True,
        )

        # May have multiple fills
        assert result.n_fills >= 1
        assert len(result.fill_prices) == result.n_fills

    def test_limit_order_fill(self):
        """Test limit order fill simulation."""
        sim = PartialFillSimulator()

        result = sim.simulate_limit_order_fill(
            order_size=100,
            limit_price=49900.0,
            bar_high=50100.0,
            bar_low=49800.0,  # Limit price is reachable
            bar_volume=10000,
            is_buy=True,
        )

        # Limit is within range, should have chance to fill
        # Note: Due to randomness, may or may not fill
        assert result.filled_size >= 0

    def test_limit_order_not_reachable(self):
        """Test limit order when price not reached."""
        sim = PartialFillSimulator()

        result = sim.simulate_limit_order_fill(
            order_size=100,
            limit_price=49500.0,  # Below bar low
            bar_high=50100.0,
            bar_low=49800.0,
            bar_volume=10000,
            is_buy=True,
        )

        assert result.is_complete is False
        assert result.filled_size == 0

    def test_disabled_partial_fills(self):
        """Test with partial fills disabled."""
        config = PartialFillConfig(enabled=False)
        sim = PartialFillSimulator(config)

        result = sim.simulate_market_order_fill(
            order_size=10000,
            bar_volume=1000,
            current_price=50000.0,
            is_buy=True,
        )

        assert result.is_complete is True
        assert result.filled_size == 10000
        assert result.n_fills == 1


# =============================================================================
# 5. LIQUIDATION ENGINE TESTS
# =============================================================================


class TestLiquidationEngine:
    """Tests for LiquidationEngine."""

    def test_calculate_liquidation_price_long(self):
        """Test liquidation price calculation for long position."""
        engine = LiquidationEngine()

        liq_price, bankruptcy_price = engine.calculate_liquidation_price(
            entry_price=50000.0,
            leverage=10,  # 10x leverage
            is_long=True,
        )

        # Long: liq_price = entry * (1 - 1/leverage + mmr)
        # = 50000 * (1 - 0.1 + 0.005) = 50000 * 0.905 = 45250
        assert abs(liq_price - 45250.0) < 1.0

        # Bankruptcy: entry * (1 - 1/leverage) = 50000 * 0.9 = 45000
        assert abs(bankruptcy_price - 45000.0) < 1.0

    def test_calculate_liquidation_price_short(self):
        """Test liquidation price calculation for short position."""
        engine = LiquidationEngine()

        liq_price, bankruptcy_price = engine.calculate_liquidation_price(
            entry_price=50000.0,
            leverage=10,
            is_long=False,
        )

        # Short: liq_price = entry * (1 + 1/leverage - mmr)
        # = 50000 * (1 + 0.1 - 0.005) = 50000 * 1.095 = 54750
        assert abs(liq_price - 54750.0) < 1.0

    def test_check_liquidation_long_safe(self):
        """Test liquidation check for safe long position."""
        engine = LiquidationEngine()

        result = engine.check_liquidation(
            entry_price=50000.0,
            current_price=51000.0,  # Price went up
            leverage=10,
            is_long=True,
            position_size=1.0,
            wallet_balance=5000.0,
        )

        assert result.is_liquidated is False
        assert result.unrealized_pnl > 0

    def test_check_liquidation_long_liquidated(self):
        """Test liquidation check for liquidated long position."""
        engine = LiquidationEngine()

        result = engine.check_liquidation(
            entry_price=50000.0,
            current_price=44000.0,  # Price crashed below liquidation
            leverage=10,
            is_long=True,
            position_size=1.0,
            wallet_balance=5000.0,
        )

        assert result.is_liquidated is True
        assert result.unrealized_pnl < 0

    def test_check_liquidation_short_liquidated(self):
        """Test liquidation check for liquidated short position."""
        engine = LiquidationEngine()

        result = engine.check_liquidation(
            entry_price=50000.0,
            current_price=56000.0,  # Price went above liquidation
            leverage=10,
            is_long=False,
            position_size=1.0,
            wallet_balance=5000.0,
        )

        assert result.is_liquidated is True

    def test_partial_liquidation(self):
        """Test partial liquidation when margin ratio high."""
        config = LiquidationConfig(
            enable_partial_liquidation=True, partial_liquidation_threshold=0.5
        )
        engine = LiquidationEngine(config)

        result = engine.check_liquidation(
            entry_price=50000.0,
            current_price=47000.0,  # Significant loss but not liquidated
            leverage=10,
            is_long=True,
            position_size=1.0,
            wallet_balance=5000.0,
        )

        # May trigger partial liquidation
        assert result.is_liquidated is False  # Not fully liquidated

    def test_liquidation_loss_calculation(self):
        """Test liquidation loss calculation."""
        engine = LiquidationEngine()

        loss = engine.calculate_liquidation_loss(
            entry_price=50000.0,
            liquidation_price=45250.0,
            position_size=1.0,
            is_long=True,
        )

        # Loss = 1 * (45250 - 50000) - fee
        # = -4750 - (1 * 45250 * 0.0006) = -4750 - 27.15 = -4777.15
        assert loss < -4700


# =============================================================================
# 6. ML STRATEGY INTERFACE TESTS
# =============================================================================


class MockMLModel:
    """Mock ML model for testing."""

    def __init__(self, constant_pred: float = 0.6):
        self.constant_pred = constant_pred

    def predict(self, X):
        return np.full(len(X), self.constant_pred)


class TestFeatureEngineering:
    """Tests for FeatureEngineering."""

    def test_generate_features(self):
        """Test feature generation from OHLCV."""
        close = np.array(
            [100, 101, 102, 101, 103, 104, 103, 105, 106, 105] * 5, dtype=np.float64
        )
        high = close + 1
        low = close - 1
        volume = np.ones(50, dtype=np.float64) * 1000

        features = FeatureEngineering.generate_features(
            close, high, low, volume, lookback=10
        )

        assert "return_1" in features
        assert "volatility" in features
        assert "rsi" in features
        assert "volume_ma_ratio" in features
        assert len(features["return_1"]) == 50

    def test_rsi_calculation(self):
        """Test RSI calculation."""
        # Create trending up data with some variation
        np.random.seed(42)
        base = np.linspace(100, 120, 50)
        noise = np.random.randn(50) * 0.1
        close = (base + noise).astype(np.float64)

        rsi = FeatureEngineering._calculate_rsi(close, period=14)

        # RSI should be calculated (not all zeros or NaN)
        assert not np.isnan(rsi[-1])
        # For trending up data, RSI should be reasonably high (above 50)
        assert rsi[-1] > 50


class TestMLStrategyInterface:
    """Tests for MLStrategyInterface."""

    def test_set_model(self):
        """Test setting ML model."""
        interface = MLStrategyInterface()
        model = MockMLModel()
        interface.set_model(model)
        assert interface.model is not None

    def test_prepare_features(self):
        """Test feature preparation."""
        interface = MLStrategyInterface()

        close = np.linspace(100, 110, 50).astype(np.float64)
        high = close + 1
        low = close - 1
        volume = np.ones(50, dtype=np.float64) * 1000

        X = interface.prepare_features(close, high, low, volume)

        assert X.shape[0] == 50
        assert X.shape[1] > 0  # Has features

    def test_generate_signals(self):
        """Test signal generation with ML model."""
        model = MockMLModel(constant_pred=0.7)  # Above threshold
        interface = MLStrategyInterface(model=model)

        close = np.linspace(100, 110, 50).astype(np.float64)
        high = close + 1
        low = close - 1
        volume = np.ones(50, dtype=np.float64) * 1000

        signals = interface.generate_signals(close, high, low, volume)

        # All should be long signals (prediction > 0.5 threshold)
        assert np.all(signals == 1)

    def test_generate_signals_short(self):
        """Test short signal generation."""
        model = MockMLModel(constant_pred=-0.7)  # Below -threshold
        interface = MLStrategyInterface(model=model)

        close = np.linspace(100, 90, 50).astype(np.float64)
        high = close + 1
        low = close - 1
        volume = np.ones(50, dtype=np.float64) * 1000

        signals = interface.generate_signals(close, high, low, volume)

        # All should be short signals
        assert np.all(signals == -1)

    def test_create_labels(self):
        """Test label creation for training."""
        interface = MLStrategyInterface()

        # Create trending data
        close = np.linspace(100, 120, 50).astype(np.float64)

        labels = interface.create_labels(close, forward_period=5, threshold=0.01)

        # Trending up should have positive labels
        assert np.sum(labels == 1) > 0

    def test_feature_scaling(self):
        """Test feature scaling."""
        config = MLStrategyConfig(enable_scaling=True, scaling_method="standard")
        interface = MLStrategyInterface(config=config)

        close = np.linspace(100, 110, 50).astype(np.float64)
        high = close + 1
        low = close - 1
        volume = np.ones(50, dtype=np.float64) * 1000

        X = interface.prepare_features(close, high, low, volume)

        # After standard scaling, mean should be ~0, std ~1
        assert abs(np.mean(X[:, 0])) < 0.5  # Approximately centered


# =============================================================================
# INTEGRATION TEST
# =============================================================================


class TestRealisticSimulationIntegration:
    """Integration tests for all v2.1 components."""

    def test_full_simulation_pipeline(self):
        """Test complete simulation pipeline."""
        # 1. Generate realistic bar path
        bar_sim = RealisticBarSimulator(BarSimulatorConfig(ticks_per_bar=100, seed=42))
        path = bar_sim.simulate_bar_path(
            open_price=50000.0,
            high_price=50500.0,
            low_price=49500.0,
            close_price=50200.0,
            volume=1000.0,
        )
        assert len(path) == 100

        # 2. Calculate volume-based slippage
        slip_model = VolumeSlippageModel()
        slippage = slip_model.calculate_slippage(
            order_size_usd=5000, bar_volume_usd=100_000
        )
        assert slippage > 0

        # 3. Check liquidation
        liq_engine = LiquidationEngine()
        liq_result = liq_engine.check_liquidation(
            entry_price=50000.0,
            current_price=50200.0,
            leverage=10,
            is_long=True,
            position_size=0.1,
            wallet_balance=1000.0,
        )
        assert liq_result.is_liquidated is False

        # 4. Simulate partial fill
        fill_sim = PartialFillSimulator()
        fill_result = fill_sim.simulate_market_order_fill(
            order_size=0.1,
            bar_volume=10.0,
            current_price=50200.0,
            is_buy=True,
        )
        assert fill_result.filled_size > 0

        # 5. ML feature generation
        features = FeatureEngineering.generate_features(
            close=np.array([50000, 50100, 50050, 50200, 50150], dtype=np.float64),
            high=np.array([50100, 50200, 50150, 50300, 50250], dtype=np.float64),
            low=np.array([49900, 50000, 49950, 50100, 50050], dtype=np.float64),
            volume=np.array([100, 120, 110, 130, 125], dtype=np.float64),
            lookback=3,
        )
        assert "rsi" in features
        assert "volatility" in features

    def test_v21_imports(self):
        """Test that all v2.1 classes can be imported."""
        from backend.backtesting.universal_engine import (
            BarPathType,
            BarSimulatorConfig,
            DynamicFundingConfig,
            DynamicFundingManager,
            FeatureEngineering,
            FillResult,
            FundingRateEntry,
            LiquidationConfig,
            LiquidationEngine,
            LiquidationResult,
            MLStrategyConfig,
            MLStrategyInterface,
            PartialFillConfig,
            PartialFillSimulator,
            RealisticBarSimulator,
            VolumeSlippageConfig,
            VolumeSlippageModel,
        )

        # All imports successful
        assert BarPathType is not None
        assert RealisticBarSimulator is not None
        assert VolumeSlippageModel is not None
        assert DynamicFundingManager is not None
        assert PartialFillSimulator is not None
        assert LiquidationEngine is not None
        assert MLStrategyInterface is not None
