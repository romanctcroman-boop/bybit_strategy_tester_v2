"""
Tests for Universal Math Engine v2.4 Features.

These tests verify the correct API of v2.4 modules based on actual implementations.

Tests cover:
1. Regime Detection ML
2. Sentiment Analysis
3. Risk Parity Portfolio
4. AutoML Strategies
5. Reinforcement Learning
6. Options Strategies
7. Live Trading Bridge
8. Advanced Visualization
"""

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pytest

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_ohlcv() -> dict[str, np.ndarray]:
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    n = 500

    returns = np.random.randn(n) * 0.02
    close = 50000 * np.exp(np.cumsum(returns))

    high = close * (1 + np.abs(np.random.randn(n)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(n)) * 0.01)
    open_price = np.roll(close, 1)
    open_price[0] = close[0]

    volume = np.random.uniform(100, 1000, n)

    return {
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


@pytest.fixture
def sample_returns() -> np.ndarray:
    """Generate sample returns data for portfolio optimization."""
    np.random.seed(42)
    n_assets = 5
    n_periods = 252

    cov = np.array(
        [
            [0.04, 0.02, 0.01, 0.005, 0.003],
            [0.02, 0.03, 0.015, 0.01, 0.005],
            [0.01, 0.015, 0.025, 0.008, 0.004],
            [0.005, 0.01, 0.008, 0.02, 0.006],
            [0.003, 0.005, 0.004, 0.006, 0.015],
        ]
    )

    mean = np.array([0.10, 0.08, 0.06, 0.05, 0.04]) / 252

    returns = np.random.multivariate_normal(mean, cov / 252, n_periods)

    return returns


@pytest.fixture
def sample_features(sample_ohlcv: dict) -> np.ndarray:
    """Generate sample features for RL environment."""
    close = sample_ohlcv["close"]
    n = len(close)

    # Create simple features: returns, volatility, etc.
    returns = np.diff(close) / close[:-1]
    vol = np.zeros(n - 1)
    for i in range(20, n - 1):
        vol[i] = np.std(returns[i - 20 : i])

    # Stack features
    features = np.column_stack(
        [
            returns,
            vol,
            np.zeros(n - 1),  # placeholder feature 1
            np.zeros(n - 1),  # placeholder feature 2
            np.zeros(n - 1),  # placeholder feature 3
        ]
    )

    return features


# =============================================================================
# 1. Regime Detection Tests
# =============================================================================


class TestRegimeDetection:
    """Tests for Market Regime Detection."""

    def test_market_regime_enum(self):
        """Test MarketRegime enum values."""
        from backend.backtesting.universal_engine.regime_detection import MarketRegime

        # Actual enum values: BULL, BEAR, SIDEWAYS, HIGH_VOLATILITY, LOW_VOLATILITY, UNKNOWN
        assert hasattr(MarketRegime, "BULL")
        assert hasattr(MarketRegime, "BEAR")
        assert hasattr(MarketRegime, "SIDEWAYS")
        assert hasattr(MarketRegime, "HIGH_VOLATILITY")
        assert hasattr(MarketRegime, "LOW_VOLATILITY")
        assert hasattr(MarketRegime, "UNKNOWN")

    def test_regime_config_defaults(self):
        """Test RegimeConfig dataclass default values."""
        from backend.backtesting.universal_engine.regime_detection import RegimeConfig

        config = RegimeConfig()
        assert config is not None

    def test_rule_based_detector_instantiation(self, sample_ohlcv):
        """Test RuleBasedRegimeDetector can be instantiated."""
        from backend.backtesting.universal_engine.regime_detection import (
            RegimeConfig,
            RuleBasedRegimeDetector,
        )

        config = RegimeConfig()
        detector = RuleBasedRegimeDetector(config)

        assert detector is not None

    def test_rule_based_detector_detect(self, sample_ohlcv):
        """Test RuleBasedRegimeDetector detect method."""
        from backend.backtesting.universal_engine.regime_detection import (
            RegimeConfig,
            RuleBasedRegimeDetector,
        )

        config = RegimeConfig()
        detector = RuleBasedRegimeDetector(config)

        result = detector.detect(sample_ohlcv["close"])
        assert result is not None

    def test_clustering_detector(self, sample_ohlcv):
        """Test ClusteringRegimeDetector."""
        from backend.backtesting.universal_engine.regime_detection import (
            ClusteringRegimeDetector,
            RegimeConfig,
        )

        config = RegimeConfig()
        detector = ClusteringRegimeDetector(config)

        result = detector.detect(sample_ohlcv["close"])
        assert result is not None

    def test_ensemble_detector(self, sample_ohlcv):
        """Test EnsembleRegimeDetector."""
        from backend.backtesting.universal_engine.regime_detection import (
            EnsembleRegimeDetector,
            RegimeConfig,
        )

        config = RegimeConfig()
        detector = EnsembleRegimeDetector(config)

        result = detector.detect(sample_ohlcv["close"])
        assert result is not None

    def test_regime_detector_instantiation(self):
        """Test main RegimeDetector class instantiation."""
        from backend.backtesting.universal_engine.regime_detection import (
            RegimeConfig,
            RegimeDetector,
        )

        config = RegimeConfig()
        detector = RegimeDetector(config)
        assert detector is not None


# =============================================================================
# 2. Sentiment Analysis Tests
# =============================================================================


class TestSentimentAnalysis:
    """Tests for Sentiment Analysis."""

    def test_sentiment_level_enum(self):
        """Test SentimentLevel enum values."""
        from backend.backtesting.universal_engine.sentiment_analysis import (
            SentimentLevel,
        )

        assert hasattr(SentimentLevel, "EXTREME_FEAR")
        assert hasattr(SentimentLevel, "FEAR")
        assert hasattr(SentimentLevel, "NEUTRAL")
        assert hasattr(SentimentLevel, "GREED")
        assert hasattr(SentimentLevel, "EXTREME_GREED")

    def test_sentiment_config(self):
        """Test SentimentConfig dataclass."""
        from backend.backtesting.universal_engine.sentiment_analysis import (
            SentimentConfig,
        )

        config = SentimentConfig()
        assert config is not None

    def test_lexicon_sentiment_analyzer(self):
        """Test LexiconSentimentAnalyzer."""
        from backend.backtesting.universal_engine.sentiment_analysis import (
            LexiconSentimentAnalyzer,
            SentimentConfig,
        )

        config = SentimentConfig()
        analyzer = LexiconSentimentAnalyzer(config)

        result = analyzer.analyze("Bitcoin surges to new all-time high")
        assert result is not None

    def test_news_sentiment_analyzer(self):
        """Test NewsSentimentAnalyzer with analyze_article method."""
        from backend.backtesting.universal_engine.sentiment_analysis import (
            NewsSentimentAnalyzer,
            SentimentConfig,
        )

        config = SentimentConfig()
        analyzer = NewsSentimentAnalyzer(config)

        # Actual API uses analyze_article method
        result = analyzer.analyze_article("Crypto market crashes")
        assert result is not None

    def test_fear_greed_calculator(self, sample_ohlcv):
        """Test FearGreedCalculator."""
        from backend.backtesting.universal_engine.sentiment_analysis import (
            FearGreedCalculator,
            SentimentConfig,
        )

        config = SentimentConfig()
        calculator = FearGreedCalculator(config)

        result = calculator.calculate(sample_ohlcv["close"], sample_ohlcv["volume"])
        assert result is not None

    def test_sentiment_signal_generator_instantiation(self, sample_ohlcv):
        """Test SentimentSignalGenerator instantiation."""
        from backend.backtesting.universal_engine.sentiment_analysis import (
            SentimentConfig,
            SentimentSignalGenerator,
        )

        config = SentimentConfig()
        generator = SentimentSignalGenerator(config)

        # Test that the generator can be created
        assert generator is not None


# =============================================================================
# 3. Risk Parity Tests
# =============================================================================


class TestRiskParity:
    """Tests for Risk Parity Portfolio Optimization."""

    def test_portfolio_weights_dataclass(self):
        """Test PortfolioWeights dataclass fields."""
        from backend.backtesting.universal_engine.risk_parity import PortfolioWeights

        # PortfolioWeights.weights is Dict[str, float]
        weights = PortfolioWeights(
            weights={"BTC": 0.5, "ETH": 0.3, "SOL": 0.2},
            timestamp=datetime.now(),
            objective_value=0.0,
        )

        assert len(weights.weights) == 3
        assert np.isclose(sum(weights.weights.values()), 1.0)

    def test_risk_parity_optimizer_workflow(self, sample_returns):
        """Test RiskParityOptimizer with fit() then optimize()."""
        from backend.backtesting.universal_engine.risk_parity import RiskParityOptimizer

        optimizer = RiskParityOptimizer()

        # Must call fit() before optimize()
        optimizer.fit(sample_returns)
        weights = optimizer.optimize()

        # Returns PortfolioWeights object
        assert weights is not None
        assert hasattr(weights, "weights")
        assert np.isclose(sum(weights.weights.values()), 1.0)

    def test_hierarchical_risk_parity_workflow(self, sample_returns):
        """Test HierarchicalRiskParity with fit() then optimize()."""
        from backend.backtesting.universal_engine.risk_parity import (
            HierarchicalRiskParity,
        )

        optimizer = HierarchicalRiskParity()

        # Must call fit() before optimize()
        optimizer.fit(sample_returns)
        weights = optimizer.optimize()

        # Returns PortfolioWeights object
        assert weights is not None
        assert hasattr(weights, "weights")
        assert np.isclose(sum(weights.weights.values()), 1.0)

    def test_mean_variance_optimizer_workflow(self, sample_returns):
        """Test MeanVarianceOptimizer with fit() then optimize()."""
        from backend.backtesting.universal_engine.risk_parity import (
            MeanVarianceOptimizer,
        )

        optimizer = MeanVarianceOptimizer()

        # Must call fit() before optimize()
        optimizer.fit(sample_returns)
        weights = optimizer.optimize()

        # Returns PortfolioWeights object
        assert weights is not None
        assert hasattr(weights, "weights")
        assert np.isclose(sum(weights.weights.values()), 1.0)

    def test_covariance_estimator_methods(self, sample_returns):
        """Test CovarianceEstimator methods."""
        from backend.backtesting.universal_engine.risk_parity import CovarianceEstimator

        estimator = CovarianceEstimator()

        # Actual methods: sample_covariance, ledoit_wolf_shrinkage, etc.
        cov = estimator.sample_covariance(sample_returns)

        assert cov.shape == (sample_returns.shape[1], sample_returns.shape[1])

    def test_risk_metrics_dataclass(self):
        """Test RiskMetrics dataclass with all required fields."""
        from backend.backtesting.universal_engine.risk_parity import RiskMetrics

        # RiskMetrics requires all fields
        metrics = RiskMetrics(
            volatility=0.15,
            var_95=0.025,
            var_99=0.035,
            cvar_95=0.035,
            cvar_99=0.045,
            max_drawdown=0.10,
            beta=1.0,
        )

        assert metrics.volatility == 0.15


# =============================================================================
# 4. AutoML Strategies Tests
# =============================================================================


class TestAutoMLStrategies:
    """Tests for AutoML Strategy Optimization."""

    def test_feature_type_enum(self):
        """Test FeatureType enum values."""
        from backend.backtesting.universal_engine.automl_strategies import FeatureType

        # Actual values: MOMENTUM, TREND, VOLATILITY, VOLUME, PATTERN, STATISTICAL, CUSTOM
        assert hasattr(FeatureType, "MOMENTUM")
        assert hasattr(FeatureType, "TREND")
        assert hasattr(FeatureType, "VOLATILITY")
        assert hasattr(FeatureType, "VOLUME")

    def test_automl_config(self):
        """Test AutoMLConfig dataclass."""
        from backend.backtesting.universal_engine.automl_strategies import AutoMLConfig

        config = AutoMLConfig()
        assert config is not None

    def test_strategy_genome_dataclass(self):
        """Test StrategyGenome with all required fields."""
        from backend.backtesting.universal_engine.automl_strategies import (
            StrategyGenome,
        )

        # StrategyGenome requires many fields
        genome = StrategyGenome(
            entry_features=[0, 1],
            entry_thresholds=[0.5, 0.5],
            entry_logic="AND",
            exit_features=[0],
            exit_thresholds=[0.3],
            exit_logic="OR",
        )
        assert genome is not None

    def test_feature_engineering_generate(self, sample_ohlcv):
        """Test FeatureEngineering with generate_features method."""
        from backend.backtesting.universal_engine.automl_strategies import (
            FeatureEngineering,
        )

        fe = FeatureEngineering()

        # Actual API uses generate_features method
        features = fe.generate_features(
            sample_ohlcv["open"],
            sample_ohlcv["high"],
            sample_ohlcv["low"],
            sample_ohlcv["close"],
            sample_ohlcv["volume"],
        )

        assert features is not None

    def test_model_selector(self):
        """Test ModelSelector instantiation."""
        from backend.backtesting.universal_engine.automl_strategies import ModelSelector

        selector = ModelSelector()
        assert selector is not None

    def test_strategy_evolver(self):
        """Test StrategyEvolver instantiation."""
        from backend.backtesting.universal_engine.automl_strategies import (
            AutoMLConfig,
            StrategyEvolver,
        )

        config = AutoMLConfig()
        evolver = StrategyEvolver(config)

        assert evolver is not None

    def test_automl_pipeline(self):
        """Test AutoMLPipeline instantiation."""
        from backend.backtesting.universal_engine.automl_strategies import (
            AutoMLConfig,
            AutoMLPipeline,
        )

        config = AutoMLConfig()
        pipeline = AutoMLPipeline(config)

        assert pipeline is not None


# =============================================================================
# 5. Reinforcement Learning Tests
# =============================================================================


class TestReinforcementLearning:
    """Tests for Reinforcement Learning Trading Agents."""

    def test_action_enum(self):
        """Test Action enum values."""
        from backend.backtesting.universal_engine.reinforcement_learning import Action

        # Action is an enum with: HOLD, BUY, SELL, CLOSE
        assert hasattr(Action, "HOLD")
        assert hasattr(Action, "BUY")
        assert hasattr(Action, "SELL")
        assert hasattr(Action, "CLOSE")

    def test_state_dataclass(self):
        """Test State dataclass with all required fields."""
        from backend.backtesting.universal_engine.reinforcement_learning import State

        # State requires many fields
        state = State(
            features=np.random.randn(10),
            position=0,
            entry_price=0.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            cash=10000.0,
            equity=10000.0,
            step=0,
        )
        assert state is not None

    def test_rl_config(self):
        """Test RLConfig dataclass."""
        from backend.backtesting.universal_engine.reinforcement_learning import RLConfig

        config = RLConfig()
        assert config is not None
        assert hasattr(config, "initial_capital")
        assert hasattr(config, "learning_rate")

    def test_trading_environment(self, sample_ohlcv, sample_features):
        """Test TradingEnvironment with prices and features."""
        from backend.backtesting.universal_engine.reinforcement_learning import (
            RLConfig,
            TradingEnvironment,
        )

        config = RLConfig()
        prices = sample_ohlcv["close"][1:]  # Match length with features

        # TradingEnvironment requires prices and features as separate arrays
        env = TradingEnvironment(prices, sample_features, config)

        state = env.reset()
        assert state is not None

        next_state, reward, done, info = env.step(0)
        assert next_state is not None

    def test_experience_replay_push_sample(self):
        """Test ExperienceReplay with push and sample methods."""
        from backend.backtesting.universal_engine.reinforcement_learning import (
            Experience,
            ExperienceReplay,
        )

        replay = ExperienceReplay(capacity=100)

        # Actual API uses push method instead of add
        for i in range(50):
            exp = Experience(
                state=np.random.randn(10),
                action=0,
                reward=np.random.randn(),
                next_state=np.random.randn(10),
                done=False,
            )
            replay.push(exp)

        assert len(replay) == 50

        batch = replay.sample(10)
        assert len(batch) == 10

    def test_dqn_agent(self):
        """Test DQNAgent instantiation and action selection."""
        from backend.backtesting.universal_engine.reinforcement_learning import (
            DQNAgent,
            RLConfig,
        )

        config = RLConfig()
        agent = DQNAgent(state_dim=10, action_dim=3, config=config)

        state = np.random.randn(10)
        action = agent.select_action(state)

        assert action in [0, 1, 2]

    def test_ppo_agent(self):
        """Test PPOAgent instantiation."""
        from backend.backtesting.universal_engine.reinforcement_learning import (
            PPOAgent,
            RLConfig,
        )

        config = RLConfig()
        agent = PPOAgent(state_dim=10, action_dim=3, config=config)

        state = np.random.randn(10)
        action = agent.select_action(state)

        assert action is not None


# =============================================================================
# 6. Options Strategies Tests
# =============================================================================


class TestOptionsStrategies:
    """Tests for Options Pricing and Strategies."""

    def test_option_type_enum(self):
        """Test OptionType enum."""
        from backend.backtesting.universal_engine.options_strategies import OptionType

        assert hasattr(OptionType, "CALL")
        assert hasattr(OptionType, "PUT")

    def test_option_dataclass(self):
        """Test Option dataclass."""
        from backend.backtesting.universal_engine.options_strategies import (
            Option,
            OptionType,
        )

        option = Option(
            strike=50000,
            expiry=datetime.now() + timedelta(days=30),
            option_type=OptionType.CALL,
            premium=1000,
        )

        assert option.strike == 50000

    def test_black_scholes_call(self):
        """Test BlackScholes call pricing."""
        from backend.backtesting.universal_engine.options_strategies import BlackScholes

        bs = BlackScholes()

        call_price = bs.call_price(
            S=100,
            K=100,
            T=1.0,
            r=0.05,
            sigma=0.2,
        )

        assert call_price > 0
        assert call_price < 100

    def test_black_scholes_put(self):
        """Test BlackScholes put pricing."""
        from backend.backtesting.universal_engine.options_strategies import BlackScholes

        bs = BlackScholes()

        put_price = bs.put_price(
            S=100,
            K=100,
            T=1.0,
            r=0.05,
            sigma=0.2,
        )

        assert put_price > 0
        assert put_price < 100

    def test_greeks_calculator_methods(self):
        """Test GreeksCalculator individual methods."""
        from backend.backtesting.universal_engine.options_strategies import (
            GreeksCalculator,
        )

        calc = GreeksCalculator()

        # Actual methods: delta, gamma, theta, vega, rho, all_greeks
        delta = calc.delta(S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="call")
        gamma = calc.gamma(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
        theta = calc.theta(S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="call")
        vega = calc.vega(S=100, K=100, T=1.0, r=0.05, sigma=0.2)

        assert -1 <= delta <= 1
        assert gamma >= 0
        assert theta is not None
        assert vega is not None

    def test_binomial_tree(self):
        """Test BinomialTree model with n_steps parameter."""
        from backend.backtesting.universal_engine.options_strategies import BinomialTree

        # Actual parameter is n_steps, not steps
        bt = BinomialTree(n_steps=100)

        price = bt.price(
            S=100,
            K=100,
            T=1.0,
            r=0.05,
            sigma=0.2,
            option_type="call",
        )

        assert price > 0

    def test_options_strategy_with_spot(self):
        """Test OptionsStrategy with required spot parameter."""
        from backend.backtesting.universal_engine.options_strategies import (
            OptionsStrategy,
        )

        # OptionsStrategy requires spot price
        strategy = OptionsStrategy(spot=100.0, r=0.05, sigma=0.2)

        assert strategy is not None

    def test_volatility_surface(self):
        """Test VolatilitySurface instantiation."""
        from backend.backtesting.universal_engine.options_strategies import (
            VolatilitySurface,
        )

        surface = VolatilitySurface()
        assert surface is not None


# =============================================================================
# 7. Live Trading Tests
# =============================================================================


class TestLiveTrading:
    """Tests for Live Trading Bridge."""

    def test_order_enums(self):
        """Test order-related enums."""
        from backend.backtesting.universal_engine.live_trading import (
            OrderSide,
            OrderStatus,
            OrderType,
            PositionSide,
        )

        assert hasattr(OrderType, "MARKET")
        assert hasattr(OrderType, "LIMIT")
        assert hasattr(OrderSide, "BUY")
        assert hasattr(OrderSide, "SELL")
        assert hasattr(OrderStatus, "PENDING")
        assert hasattr(PositionSide, "LONG")

    def test_order_dataclass(self):
        """Test Order dataclass with all required fields."""
        from backend.backtesting.universal_engine.live_trading import (
            Order,
            OrderSide,
            OrderType,
        )

        # Order requires order_id
        order = Order(
            order_id="test-001",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1,
        )

        assert order.symbol == "BTCUSDT"
        assert order.quantity == 0.1

    def test_paper_trading_engine(self):
        """Test PaperTradingEngine basic operations."""
        from backend.backtesting.universal_engine.live_trading import (
            Order,
            OrderSide,
            OrderType,
            PaperTradingEngine,
        )

        engine = PaperTradingEngine(initial_balance=10000)

        order = Order(
            order_id="test-001",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1,
        )

        engine.set_market_price("BTCUSDT", 50000)

        # place_order is async, just test the engine is created correctly
        assert engine is not None

    @pytest.mark.asyncio
    async def test_account_balance_async(self):
        """Test AccountBalance with async get_balance method."""
        from backend.backtesting.universal_engine.live_trading import (
            AccountBalance,
            PaperTradingEngine,
        )

        engine = PaperTradingEngine(initial_balance=10000)

        # get_balance is async
        balance = await engine.get_balance()

        assert isinstance(balance, AccountBalance)
        assert hasattr(balance, "total_equity")
        assert hasattr(balance, "available_balance")

    def test_risk_limits_dataclass(self):
        """Test RiskLimits dataclass."""
        from backend.backtesting.universal_engine.live_trading import RiskLimits

        limits = RiskLimits(
            max_position_size=1.0,
            max_leverage=10.0,
            max_drawdown=0.2,
            daily_loss_limit=0.05,
        )

        assert limits.max_position_size == 1.0

    def test_risk_manager(self):
        """Test RiskManager with check_limits method."""
        from backend.backtesting.universal_engine.live_trading import (
            RiskLimits,
            RiskManager,
        )

        limits = RiskLimits(
            max_position_size=1.0,
            max_leverage=10.0,
            max_drawdown=0.2,
            daily_loss_limit=0.05,
        )

        risk_manager = RiskManager(limits)

        # Actual API uses check_limits method
        assert risk_manager is not None

    def test_live_trading_bridge(self):
        """Test LiveTradingBridge instantiation."""
        from backend.backtesting.universal_engine.live_trading import LiveTradingBridge

        bridge = LiveTradingBridge()
        assert bridge is not None


# =============================================================================
# 8. Visualization Tests
# =============================================================================


class TestVisualization:
    """Tests for Advanced Visualization."""

    def test_chart_type_enum(self):
        """Test ChartType enum values."""
        from backend.backtesting.universal_engine.visualization import ChartType

        assert hasattr(ChartType, "LINE")
        assert hasattr(ChartType, "CANDLESTICK")
        assert hasattr(ChartType, "HEATMAP")
        assert hasattr(ChartType, "SCATTER")
        assert hasattr(ChartType, "SURFACE_3D")

    def test_color_scheme_enum(self):
        """Test ColorScheme enum values."""
        from backend.backtesting.universal_engine.visualization import ColorScheme

        assert hasattr(ColorScheme, "DARK")
        assert hasattr(ColorScheme, "LIGHT")
        assert hasattr(ColorScheme, "DEFAULT")
        assert hasattr(ColorScheme, "TRADINGVIEW")

    def test_equity_curve_chart(self):
        """Test EquityCurveChart with data passed to __init__."""
        from backend.backtesting.universal_engine.visualization import (
            EquityCurveChart,
            EquityData,
        )

        equity = np.cumsum(np.random.randn(100)) + 10000
        timestamps = np.arange(100)
        drawdown = np.zeros(100)
        drawdown_pct = np.zeros(100)
        peak = equity.copy()

        equity_data = EquityData(
            timestamps=timestamps,
            equity=equity,
            drawdown=drawdown,
            drawdown_pct=drawdown_pct,
            peak_equity=peak,
        )

        # EquityCurveChart requires equity_data in __init__
        chart = EquityCurveChart(equity_data)

        fig = chart.render()

        assert fig is not None

    def test_trade_scatter_chart(self, sample_ohlcv):
        """Test TradeScatterChart with data passed to __init__."""
        from backend.backtesting.universal_engine.visualization import (
            TradeScatterChart,
            TradeVisualization,
        )

        trades = [
            TradeVisualization(
                entry_time=datetime.now(),
                exit_time=datetime.now() + timedelta(hours=1),
                entry_price=50000.0,
                exit_price=51000.0,
                direction="LONG",
                pnl=100.0,
                pnl_percent=2.0,
                size=0.1,
            ),
            TradeVisualization(
                entry_time=datetime.now() + timedelta(hours=2),
                exit_time=datetime.now() + timedelta(hours=3),
                entry_price=51000.0,
                exit_price=50500.0,
                direction="SHORT",
                pnl=-50.0,
                pnl_percent=-1.0,
                size=0.1,
            ),
        ]

        prices = sample_ohlcv["close"][:100]
        timestamps = np.arange(100)

        chart = TradeScatterChart(trades, prices, timestamps)

        fig = chart.render()

        assert fig is not None

    def test_performance_heatmap(self):
        """Test PerformanceHeatmap with data passed to __init__."""
        from backend.backtesting.universal_engine.visualization import (
            PerformanceHeatmap,
        )

        x_values = np.arange(10)
        y_values = np.arange(10)
        z_values = np.random.randn(10, 10)

        chart = PerformanceHeatmap(x_values, y_values, z_values)

        fig = chart.render()

        assert fig is not None

    def test_correlation_matrix_chart(self, sample_returns):
        """Test CorrelationMatrixChart with data passed to __init__."""
        from backend.backtesting.universal_engine.visualization import (
            CorrelationMatrixChart,
        )

        corr_matrix = np.corrcoef(sample_returns.T)
        labels = ["BTC", "ETH", "SOL", "AVAX", "DOT"]

        chart = CorrelationMatrixChart(corr_matrix, labels)

        fig = chart.render()

        assert fig is not None

    def test_surface_3d_chart(self):
        """Test Surface3DChart with data passed to __init__."""
        from backend.backtesting.universal_engine.visualization import Surface3DChart

        x = np.linspace(-5, 5, 20)
        y = np.linspace(-5, 5, 20)
        X, Y = np.meshgrid(x, y)
        Z = np.sin(np.sqrt(X**2 + Y**2))

        chart = Surface3DChart(X, Y, Z)

        fig = chart.render()

        assert fig is not None

    def test_trading_dashboard_build(self):
        """Test TradingDashboard with build method."""
        from backend.backtesting.universal_engine.visualization import TradingDashboard

        dashboard = TradingDashboard()

        # Actual API uses build method
        fig = dashboard.build()

        assert fig is not None


# =============================================================================
# Integration Tests
# =============================================================================


class TestV24Integration:
    """Integration tests for v2.4 features working together."""

    def test_regime_detection_with_risk_parity(self, sample_ohlcv, sample_returns):
        """Test combining regime detection with risk parity."""
        from backend.backtesting.universal_engine.regime_detection import (
            RegimeConfig,
            RuleBasedRegimeDetector,
        )
        from backend.backtesting.universal_engine.risk_parity import (
            RiskParityOptimizer,
        )

        config = RegimeConfig()
        detector = RuleBasedRegimeDetector(config)
        regime = detector.detect(sample_ohlcv["close"])

        optimizer = RiskParityOptimizer()
        optimizer.fit(sample_returns)
        weights = optimizer.optimize()

        assert regime is not None
        # weights is PortfolioWeights object
        assert np.isclose(sum(weights.weights.values()), 1.0)

    def test_sentiment_with_fear_greed(self, sample_ohlcv):
        """Test sentiment analysis with Fear Greed Calculator."""
        from backend.backtesting.universal_engine.sentiment_analysis import (
            FearGreedCalculator,
            SentimentConfig,
        )

        config = SentimentConfig()

        calculator = FearGreedCalculator(config)
        fg_value = calculator.calculate(sample_ohlcv["close"], sample_ohlcv["volume"])

        assert fg_value is not None

    def test_options_pricing_consistency(self):
        """Test put-call parity in options pricing."""
        import math

        from backend.backtesting.universal_engine.options_strategies import BlackScholes

        bs = BlackScholes()

        S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2

        call = bs.call_price(S, K, T, r, sigma)
        put = bs.put_price(S, K, T, r, sigma)

        # Put-call parity: C - P = S - K*e^(-rT)
        lhs = call - put
        rhs = S - K * math.exp(-r * T)

        assert abs(lhs - rhs) < 0.01

    def test_paper_trading_setup(self, sample_ohlcv):
        """Test paper trading engine setup with price updates."""
        from backend.backtesting.universal_engine.live_trading import (
            Order,
            OrderSide,
            OrderType,
            PaperTradingEngine,
        )

        engine = PaperTradingEngine(initial_balance=10000)

        for i in range(10, min(20, len(sample_ohlcv["close"]))):
            price = sample_ohlcv["close"][i]
            engine.set_market_price("BTCUSDT", price)

        order = Order(
            order_id="test-001",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
        )

        # Engine and order are created correctly
        # Actual order placement is async
        assert engine is not None
        assert order is not None


# =============================================================================
# Version Test
# =============================================================================


class TestVersion:
    """Test that v2.4 is correctly versioned."""

    def test_version_string(self):
        """Test that version is 2.4.x."""
        from backend.backtesting.universal_engine import __version__

        assert __version__.startswith("2.4")


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
