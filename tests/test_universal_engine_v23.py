"""
Quick validation tests for Universal Math Engine v2.3 modules.

Tests:
1. Multi-Exchange Arbitrage
2. Real-time Data Streaming
3. Advanced ML Signals
"""

import asyncio

import numpy as np
import pytest


class TestMultiExchange:
    """Tests for multi_exchange.py module."""

    def test_exchange_connector_init(self):
        """Test ExchangeConnector initialization."""
        from backend.backtesting.universal_engine import (
            ExchangeConfig,
            ExchangeConnector,
            ExchangeName,
        )

        config = ExchangeConfig(exchange=ExchangeName.BYBIT, testnet=True)
        connector = ExchangeConnector(config)

        assert connector.config.exchange == ExchangeName.BYBIT
        assert connector.config.testnet is True
        assert connector.fees.taker_fee == 0.0006

    def test_arbitrage_detector(self):
        """Test ArbitrageDetector with spatial arbitrage."""
        from backend.backtesting.universal_engine import (
            ArbitrageConfig,
            ArbitrageDetector,
            ExchangeConfig,
            ExchangeConnector,
            ExchangeName,
            ExchangeTicker,
        )

        # Create connectors
        connectors = [
            ExchangeConnector(ExchangeConfig(exchange=ExchangeName.BYBIT)),
            ExchangeConnector(ExchangeConfig(exchange=ExchangeName.BINANCE)),
        ]

        detector = ArbitrageDetector(connectors, ArbitrageConfig())

        # Create tickers with arbitrage opportunity
        tickers = {
            ExchangeName.BYBIT: ExchangeTicker(
                exchange=ExchangeName.BYBIT,
                symbol="BTCUSDT",
                timestamp=1000000,
                bid=50000,
                ask=50010,  # Buy here
                bid_size=10,
                ask_size=10,
                last_price=50005,
                volume_24h=1000000,
            ),
            ExchangeName.BINANCE: ExchangeTicker(
                exchange=ExchangeName.BINANCE,
                symbol="BTCUSDT",
                timestamp=1000000,
                bid=50100,  # Sell here - profit!
                ask=50110,
                bid_size=10,
                ask_size=10,
                last_price=50105,
                volume_24h=1000000,
            ),
        }

        opportunities = detector.scan_spatial(tickers)

        # Should find at least one opportunity
        assert len(opportunities) >= 1

        # Best opportunity should be profitable
        best = max(opportunities, key=lambda x: x.net_spread)
        assert best.is_profitable
        assert best.buy_exchange == ExchangeName.BYBIT
        assert best.sell_exchange == ExchangeName.BINANCE

    def test_fee_calculator(self):
        """Test FeeCalculator."""
        from backend.backtesting.universal_engine import (
            ExchangeFees,
            ExchangeName,
            FeeCalculator,
        )

        fees = {
            ExchangeName.BYBIT: ExchangeFees(taker_fee=0.0006),
            ExchangeName.BINANCE: ExchangeFees(taker_fee=0.0005),
        }

        calc = FeeCalculator(fees)

        # Calculate fees for $10,000 trade
        breakdown = calc.calculate_trade_fees(ExchangeName.BYBIT, 10000)
        assert breakdown.taker_fee == 10000 * 0.0006  # $6

    def test_latency_simulator(self):
        """Test LatencySimulator."""
        from backend.backtesting.universal_engine import (
            ExchangeName,
            LatencySimulator,
        )

        sim = LatencySimulator(seed=42)

        # Simulate latencies
        rest_lat = sim.simulate_rest_latency(ExchangeName.BYBIT)
        ws_lat = sim.simulate_ws_latency(ExchangeName.BYBIT)
        order_lat = sim.simulate_order_latency(ExchangeName.BYBIT)

        assert rest_lat > 0
        assert ws_lat > 0
        assert order_lat > 0
        assert ws_lat < rest_lat  # WS should be faster


class TestRealtimeData:
    """Tests for realtime_data.py module."""

    def test_ticker_update(self):
        """Test TickerUpdate dataclass."""
        from backend.backtesting.universal_engine import TickerUpdate

        ticker = TickerUpdate(
            symbol="BTCUSDT",
            timestamp=1000000,
            bid=50000,
            ask=50010,
            bid_size=10,
            ask_size=10,
            last_price=50005,
            last_size=1.0,
            volume_24h=1000000,
            high_24h=51000,
            low_24h=49000,
            change_24h=0.02,
        )

        assert ticker.mid_price == 50005
        assert ticker.spread == 10

    def test_candle_aggregator(self):
        """Test CandleAggregator."""
        from backend.backtesting.universal_engine import (
            CandleAggregator,
            TradeUpdate,
        )

        aggregator = CandleAggregator(intervals=["1m"])

        # Simulate trades
        base_time = 1704067200000  # 2024-01-01 00:00:00 UTC

        trades = [
            TradeUpdate(
                symbol="BTCUSDT",
                timestamp=base_time,
                trade_id="1",
                price=50000,
                size=1.0,
                side="buy",
            ),
            TradeUpdate(
                symbol="BTCUSDT",
                timestamp=base_time + 10000,
                trade_id="2",
                price=50100,
                size=0.5,
                side="buy",
            ),
            TradeUpdate(
                symbol="BTCUSDT",
                timestamp=base_time + 20000,
                trade_id="3",
                price=49900,
                size=0.3,
                side="sell",
            ),
        ]

        for trade in trades:
            aggregator.process_trade(trade)

        # Check current candle
        candle = aggregator.get_current_candle("BTCUSDT", "1m")
        assert candle is not None
        assert candle.open == 50000
        assert candle.high == 50100
        assert candle.low == 49900
        assert candle.close == 49900
        assert candle.volume == 1.8  # 1.0 + 0.5 + 0.3

    @pytest.mark.asyncio
    async def test_stream_manager(self):
        """Test StreamManager initialization."""
        from backend.backtesting.universal_engine import (
            StreamManager,
            StreamManagerConfig,
        )

        config = StreamManagerConfig(
            enable_ticker=True,
            enable_orderbook=True,
            enable_trades=True,
        )

        manager = StreamManager(config)

        # Start streams
        result = await manager.start(["BTCUSDT"])
        assert result is True

        # Check status
        status = manager.get_status()
        assert "ticker" in status
        assert status["ticker"] == "connected"

        # Stop streams
        await manager.stop()


class TestAdvancedSignals:
    """Tests for advanced_signals.py module."""

    def test_feature_engine_basic(self):
        """Test FeatureEngine with basic features."""
        from backend.backtesting.universal_engine import (
            FeatureCategory,
            FeatureConfig,
            FeatureEngine,
        )

        config = FeatureConfig(
            short_period=5,
            medium_period=20,
            long_period=50,
            categories=[FeatureCategory.PRICE, FeatureCategory.MOMENTUM],
            normalize=False,
        )

        engine = FeatureEngine(config)

        # Generate test data
        np.random.seed(42)
        n = 100
        close = 50000 + np.cumsum(np.random.randn(n) * 50)
        open_arr = close - np.random.uniform(-20, 20, n)
        high = np.maximum(close, open_arr) + np.random.uniform(0, 30, n)
        low = np.minimum(close, open_arr) - np.random.uniform(0, 30, n)
        volume = np.random.uniform(100, 1000, n)

        ohlcv = {
            "open": open_arr,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }

        features = engine.generate_features(ohlcv)

        # Check price features
        assert "return_1" in features
        assert "log_return" in features
        assert "price_position" in features

        # Check momentum features
        assert "rsi_14" in features
        assert "macd" in features
        assert "stoch_k" in features

        # Check shapes
        for name, arr in features.items():
            assert len(arr) == n, f"Feature {name} has wrong length"

    def test_signal_types(self):
        """Test SignalType enum."""
        from backend.backtesting.universal_engine import SignalType

        assert SignalType.STRONG_BUY.value == 2
        assert SignalType.BUY.value == 1
        assert SignalType.NEUTRAL.value == 0
        assert SignalType.SELL.value == -1
        assert SignalType.STRONG_SELL.value == -2

    def test_simple_mlp_classifier(self):
        """Test SimpleMLPClassifier initialization."""
        from backend.backtesting.universal_engine import (
            ClassifierConfig,
            SimpleMLPClassifier,
        )

        config = ClassifierConfig(
            hidden_layers=[32, 16],
            learning_rate=0.01,
            epochs=50,
            batch_size=16,
        )

        classifier = SimpleMLPClassifier(config)

        # Test initialization
        assert classifier.config.hidden_layers == [32, 16]
        assert not classifier._is_trained

    def test_ensemble_predictor(self):
        """Test EnsemblePredictor initialization."""
        from backend.backtesting.universal_engine import (
            EnsembleConfig,
            EnsemblePredictor,
            SimpleMLPClassifier,
        )

        config = EnsembleConfig(
            n_models=3,
            bagging_fraction=0.7,
            feature_fraction=0.7,
        )

        ensemble = EnsemblePredictor(SimpleMLPClassifier, config)

        # Test initialization
        assert ensemble.config.n_models == 3
        assert ensemble.config.bagging_fraction == 0.7


class TestOrderBook:
    """Tests for existing order_book.py module."""

    def test_order_book_simulator(self):
        """Test OrderBookSimulator."""
        from backend.backtesting.universal_engine import (
            OrderBookConfig,
            OrderBookSimulator,
        )

        config = OrderBookConfig(
            depth_levels=25,
            tick_size=0.1,
            base_liquidity=10.0,
        )

        sim = OrderBookSimulator(config)

        # Initialize and get snapshot
        sim.initialize(mid_price=50000.0)
        snapshot = sim.get_snapshot()

        assert snapshot is not None
        assert len(snapshot.bids) > 0
        assert len(snapshot.asks) > 0
        assert snapshot.bids[0].price < snapshot.asks[0].price

    def test_market_impact_calculator(self):
        """Test MarketImpactCalculator."""
        from backend.backtesting.universal_engine import (
            MarketImpactCalculator,
            MarketImpactConfig,
        )

        impact_config = MarketImpactConfig(
            permanent_impact_coef=0.1,
            temporary_impact_coef=0.2,
        )

        calc = MarketImpactCalculator(impact_config)

        # Calculate impact for 1 BTC order
        result = calc.calculate_impact(
            order_size=1.0,
            average_volume=100.0,
            current_price=50000.0,
            volatility=0.02,
            is_buy=True,
        )

        assert result.total_impact >= 0

    def test_order_flow_analyzer(self):
        """Test OrderFlowAnalyzer."""
        from backend.backtesting.universal_engine import OrderFlowAnalyzer

        analyzer = OrderFlowAnalyzer()

        # Analyze with correct parameters
        metrics = analyzer.analyze(
            buy_volume=500.0,
            sell_volume=400.0,
            n_buy_trades=50,
            n_sell_trades=40,
            current_price=50000.0,
        )

        assert metrics.buy_volume == 500.0
        assert metrics.sell_volume == 400.0
        # Check net volume instead of total volume
        assert metrics.net_volume == 100.0  # 500 - 400


class TestGPUAcceleration:
    """Tests for existing gpu_acceleration.py module."""

    def test_gpu_backend_init(self):
        """Test GPUBackend initialization."""
        from backend.backtesting.universal_engine import (
            GPUBackend,
            GPUBackendType,
            GPUConfig,
        )

        config = GPUConfig(
            preferred_backend=GPUBackendType.CPU,  # Force CPU for testing
        )
        backend = GPUBackend(config)

        assert backend.xp is not None  # Should have numpy or cupy

    def test_vectorized_indicators(self):
        """Test VectorizedIndicators."""
        from backend.backtesting.universal_engine import (
            GPUBackend,
            GPUBackendType,
            GPUConfig,
            VectorizedIndicators,
        )

        config = GPUConfig(preferred_backend=GPUBackendType.CPU)
        backend = GPUBackend(config)
        vi = VectorizedIndicators(backend)

        # Generate test data
        np.random.seed(42)
        close = 50000 + np.cumsum(np.random.randn(100) * 50)

        # Test RSI
        rsi = vi.rsi(close, 14)
        assert len(rsi) == len(close)
        # RSI should be between 0-100 (or NaN for warmup)
        valid = ~np.isnan(rsi)
        if valid.any():
            assert np.all((rsi[valid] >= 0) & (rsi[valid] <= 100))

    def test_batch_backtester(self):
        """Test BatchBacktester."""
        from backend.backtesting.universal_engine import (
            BatchBacktestConfig,
            BatchBacktester,
            GPUBackend,
            GPUBackendType,
            GPUConfig,
        )

        gpu_config = GPUConfig(preferred_backend=GPUBackendType.CPU)
        backend = GPUBackend(gpu_config)

        config = BatchBacktestConfig(
            batch_size=10,
        )

        backtester = BatchBacktester(backend, config)
        assert backtester is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
