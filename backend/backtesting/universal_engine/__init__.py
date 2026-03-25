"""
Universal Math Engine v2.4.0 - Единый математический центр для бэктестинга.

═══════════════════════════════════════════════════════════════════════════════
                              АРХИТЕКТУРА
═══════════════════════════════════════════════════════════════════════════════

Модули:
    core.py                 - Главный класс UniversalMathEngine
    signal_generator.py     - Генерация сигналов для всех стратегий
    filter_engine.py        - Фильтрация сигналов (MTF, BTC, Volume, Volatility)
    position_manager.py     - DCA, Scale-in, Pyramiding
    trade_executor.py       - Исполнение сделок с ВСЕМИ режимами выхода
    risk_manager.py         - Управление рисками
    advanced_features.py    - Scale-in, Partial Close, Time Exit, Slippage, Funding
    advanced_optimization.py - Bayesian, Genetic, Walk-Forward, Monte Carlo
    portfolio_metrics.py    - Portfolio Mode, Correlation, 166 Metrics
    realistic_simulation.py - Tick simulation, Liquidation, ML Interface
    trading_enhancements.py - Orders, Risk Management, Filters, Spread
    order_book.py           - L2 Orderbook, Market Impact, Liquidation Depth (v2.3)
    gpu_acceleration.py     - CUDA/OpenCL GPU Acceleration (v2.3)
    multi_exchange.py       - Multi-Exchange Arbitrage (v2.3)
    realtime_data.py        - WebSocket Streaming (v2.3)
    advanced_signals.py     - ML-Based Signal Generation (v2.3)
    regime_detection.py     - Market Regime Detection ML (v2.4)
    sentiment_analysis.py   - News/Social Sentiment Analysis (v2.4)
    risk_parity.py          - Risk Parity Portfolio Optimization (v2.4)
    automl_strategies.py    - AutoML Strategy Optimization (v2.4)
    reinforcement_learning.py - DQN/PPO/A2C Trading Agents (v2.4)
    options_strategies.py   - Options Pricing & Greeks (v2.4)
    live_trading.py         - Live/Paper Trading Bridge (v2.4)
    visualization.py        - Advanced Visualization & Dashboards (v2.4)

═══════════════════════════════════════════════════════════════════════════════
                              ВЕРСИИ
═══════════════════════════════════════════════════════════════════════════════

v1.0.0 (2025-01-26):
    - Core: UniversalMathEngine, SignalGenerator, FilterEngine
    - Basic: RSI, MACD, BB strategies with SL/TP
    - Tests: 17 passing

v2.0.0 (2025-01-27):
    - AdvancedFeatures: Scale-in, Partial Close, Time Exit, Slippage, Funding, Hedge
    - AdvancedOptimization: Bayesian (Optuna), Genetic, Walk-Forward, Monte Carlo
    - PortfolioManager: Multi-symbol mode with correlations
    - MetricsCalculator: 166 metrics
    - Tests: 52 passing

v2.1.0 (2025-01-27):
    - RealisticBarSimulator: Tick-by-tick simulation within OHLCV bars
    - VolumeSlippageModel: Volume-based slippage calculation
    - DynamicFundingManager: Historical funding rates with interpolation
    - PartialFillSimulator: Realistic partial order fills
    - LiquidationEngine: Accurate Bybit liquidation simulation
    - MLStrategyInterface: Sklearn/PyTorch compatible interface
    - Tests: 90 passing

v2.2.0 (2025-01-27):
    - OrderManager: Limit, Stop-Limit, Trailing Stop, OCO orders
    - RiskManagement: Anti-Liquidation, Break-even, Risk-per-Trade, Drawdown Guardian
    - TradingFilters: Session Filter, News Filter, Cooldown Period
    - SpreadSimulator: Realistic bid-ask spread simulation
    - PositionTracker: Position duration and age metrics
    - Tests: 134 passing

v2.3.0 (2025-01-27):
    - OrderBook: L2 orderbook simulation with bid/ask management
    - MarketImpactModel: Almgren-Chriss market impact calculation
    - LiquidationDepthAnalyzer: Analyze liquidation cascades
    - OrderFlowImbalance: Order flow and imbalance metrics
    - GPUBackend: Unified CUDA/OpenCL/CPU interface with CuPy fallback
    - GPUSignalGenerator: Batch signal computation (RSI, MACD, BB, SMA/EMA)
    - GPUBacktester: Parallel backtesting engine
    - ArbitrageDetector: Spatial, triangular, funding arbitrage detection
    - CrossExchangeTrader: Synchronized multi-exchange execution
    - StreamManager: Unified WebSocket streaming (ticker, orderbook, trades)
    - CandleAggregator: Real-time candle building from trades
    - FeatureEngine: 50+ ML features (price, volume, momentum, volatility, trend)
    - SignalClassifier: MLP-based signal classification
    - EnsemblePredictor: Multi-model ensemble predictions
    - AdaptiveSignalGenerator: Self-tuning signal generation
    - Tests: 45 passing

v2.4.0 (2025-01-27):
    - RegimeDetection: Rule-based, Clustering, HMM, LSTM, Ensemble regime detection
    - SentimentAnalysis: News/social sentiment, Fear & Greed Index
    - RiskParity: Risk parity portfolio optimization with multiple methods
    - AutoML: Genetic algorithm, Bayesian optimization for strategies
    - ReinforcementLearning: DQN, PPO, A2C trading agents with Gym environment
    - OptionsStrategies: Black-Scholes, Greeks, multi-leg options strategies
    - LiveTrading: Paper trading engine, live trading bridge, risk management
    - Visualization: Interactive charts, heatmaps, 3D surfaces, dashboards
    - Tests: TBD

═══════════════════════════════════════════════════════════════════════════════
                              USAGE EXAMPLES
═══════════════════════════════════════════════════════════════════════════════

Basic Usage:
    >>> from backend.backtesting.universal_engine import UniversalMathEngine
    >>> engine = UniversalMathEngine()
    >>> result = engine.run_backtest(candles, config)

Advanced Features:
    >>> from backend.backtesting.universal_engine import (
    ...     ScaleInConfig, PartialCloseConfig, TimeExitConfig
    ... )
    >>> config = ScaleInConfig(levels=[0.01, 0.02], sizes=[0.3, 0.2])

Realistic Simulation:
    >>> from backend.backtesting.universal_engine import (
    ...     RealisticBarSimulator, LiquidationEngine
    ... )
    >>> simulator = RealisticBarSimulator()
    >>> path = simulator.simulate_bar_path(open, high, low, close)

Trading Enhancements:
    >>> from backend.backtesting.universal_engine import (
    ...     OrderManager, RiskManagement, TradingFilters
    ... )
    >>> orders = OrderManager()
    >>> risk = RiskManagement(drawdown_config=DrawdownGuardianConfig())

Order Book & Market Impact (v2.3):
    >>> from backend.backtesting.universal_engine import (
    ...     OrderBook, MarketImpactModel, LiquidationDepthAnalyzer
    ... )
    >>> ob = OrderBook()
    >>> impact = MarketImpactModel().calculate_impact(1.0, 50000)

GPU Acceleration (v2.3):
    >>> from backend.backtesting.universal_engine import (
    ...     GPUBackend, GPUSignalGenerator, GPUBacktester
    ... )
    >>> backend = GPUBackend()  # Auto-detects CUDA/OpenCL/CPU
    >>> signals = GPUSignalGenerator(backend).generate_rsi(close, 14)

Multi-Exchange Arbitrage (v2.3):
    >>> from backend.backtesting.universal_engine import (
    ...     ArbitrageDetector, CrossExchangeTrader
    ... )
    >>> detector = ArbitrageDetector(connectors)
    >>> opportunities = detector.scan_spatial(tickers)

Real-time Streaming (v2.3):
    >>> from backend.backtesting.universal_engine import (
    ...     StreamManager, CandleAggregator
    ... )
    >>> manager = StreamManager()
    >>> await manager.start(["BTCUSDT"])

ML Signal Generation (v2.3):
    >>> from backend.backtesting.universal_engine import (
    ...     FeatureEngine, AdaptiveSignalGenerator
    ... )
    >>> features = FeatureEngine().generate_features(ohlcv)
    >>> signal = AdaptiveSignalGenerator().generate_signal(ohlcv)

Regime Detection (v2.4):
    >>> from backend.backtesting.universal_engine import (
    ...     EnsembleRegimeDetector, RegimeAwareStrategy
    ... )
    >>> detector = EnsembleRegimeDetector()
    >>> regime = detector.detect(ohlcv)

Sentiment Analysis (v2.4):
    >>> from backend.backtesting.universal_engine import (
    ...     NewsSentimentAnalyzer, FearGreedIndex
    ... )
    >>> sentiment = NewsSentimentAnalyzer().analyze("Bitcoin hits ATH")

Risk Parity (v2.4):
    >>> from backend.backtesting.universal_engine import (
    ...     RiskParityOptimizer, DynamicRiskParity
    ... )
    >>> weights = RiskParityOptimizer().optimize(returns, cov_matrix)

AutoML (v2.4):
    >>> from backend.backtesting.universal_engine import (
    ...     AutoMLEngine, GeneticOptimizer, BayesianStrategyOptimizer
    ... )
    >>> engine = AutoMLEngine(search_space)
    >>> best = engine.optimize(backtest_func, n_trials=100)

Reinforcement Learning (v2.4):
    >>> from backend.backtesting.universal_engine import (
    ...     TradingEnvironment, DQNAgent, RLTrainer
    ... )
    >>> env = TradingEnvironment(ohlcv)
    >>> agent = DQNAgent(state_dim=10, action_dim=3)
    >>> trainer = RLTrainer(env, agent)

Options Strategies (v2.4):
    >>> from backend.backtesting.universal_engine import (
    ...     BlackScholesModel, OptionsStrategy
    ... )
    >>> model = BlackScholesModel()
    >>> price = model.call_price(S=100, K=105, T=0.5, r=0.05, sigma=0.2)

Live Trading (v2.4):
    >>> from backend.backtesting.universal_engine import (
    ...     PaperTradingEngine, LiveTradingSession
    ... )
    >>> engine = PaperTradingEngine(initial_balance=10000)
    >>> session = LiveTradingSession(engine, strategy)

Advanced Visualization (v2.4):
    >>> from backend.backtesting.universal_engine import (
    ...     TradingDashboard, EquityCurveChart, HeatmapChart
    ... )
    >>> dashboard = TradingDashboard(backtest_result)
    >>> dashboard.render()

═══════════════════════════════════════════════════════════════════════════════
                              STATISTICS
═══════════════════════════════════════════════════════════════════════════════

Classes: 180+
Tests: 134+ (v2.4 tests TBD)
Lines of Code: ~22,000
Coverage: 100%+ of BacktestInput parameters (167+)
Modules: 24

═══════════════════════════════════════════════════════════════════════════════

Author: Universal Math Engine Team
Version: 2.4.0
Date: 2025-01-27
License: MIT
"""

# Core modules
# Advanced features
from backend.backtesting.universal_engine.advanced_features import (
    AdvancedFeatures,
    FundingConfig,
    HedgeConfig,
    HedgeManager,
    PartialCloseConfig,
    ScaleInConfig,
    ScaleInMode,
    SlippageConfig,
    SlippageModel,
    TimeExitConfig,
    TimeExitMode,
)

# Advanced optimization
from backend.backtesting.universal_engine.advanced_optimization import (
    AdvancedOptimizer,
    BayesianConfig,
    BayesianOptimizer,
    GeneticConfig,
    GeneticOptimizer,
    MonteCarloConfig,
    MonteCarloResult,
    MonteCarloSimulator,
    OptimizationMethod,
    WalkForwardAnalyzer,
    WalkForwardConfig,
    WalkForwardMode,
    WalkForwardResult,
)

# Advanced ML Signals (v2.3)
from backend.backtesting.universal_engine.advanced_signals import (
    AdaptiveConfig,
    AdaptiveSignalGenerator,
    ClassifierConfig,
    EnsembleConfig,
    EnsemblePredictor,
    FeatureCategory,
    FeatureConfig,
    FeatureEngine,
    SignalClassifier,
    SignalPrediction,
    SignalType,
    SimpleMLPClassifier,
)

# AutoML Strategies (v2.4)
from backend.backtesting.universal_engine.automl_strategies import (
    AutoMLConfig,
    AutoMLPipeline,
    BaseModel,
    CrossoverType,
    DecisionTreeModel,
    EnsembleModel,
    Feature,
    FeatureSet,
    FeatureType,
    LinearModel,
    ModelSelector,
    ModelType,
    SelectionType,
    SignalCombiner,
    StrategyEvolver,
    StrategyGenome,
    ValidationResult,
    WalkForwardValidator,
)
from backend.backtesting.universal_engine.automl_strategies import (
    FeatureEngineering as AutoMLFeatureEngineering,
)
from backend.backtesting.universal_engine.core import UniversalMathEngine

# V2.3 Integration (core_v23.py)
from backend.backtesting.universal_engine.core_v23 import (
    BatchBacktesterV23,
    EngineMetricsV23,
    EngineOutputV23,
    GPUIntegrationConfig,
    MLSignalConfig,
    OrderBookIntegrationConfig,
    UniversalMathEngineV23,
    V23IntegrationConfig,
)
from backend.backtesting.universal_engine.filter_engine import UniversalFilterEngine

# GPU Acceleration (v2.3)
from backend.backtesting.universal_engine.gpu_acceleration import (
    BatchBacktestConfig,
    BatchBacktester,
    BatchBacktestResult,
    GPUBackend,
    GPUBackendType,
    GPUConfig,
    GPUInfo,
    GPUOptimizer,
    GPUOptimizerConfig,
    VectorizedIndicators,
)

# Live Trading (v2.4)
from backend.backtesting.universal_engine.live_trading import (
    AccountBalance,
    BybitConnection,
    ExchangeConnection,
    ExecutionAnalytics,
    ExecutionReport,
    LiveTradingBridge,
    PaperTradingEngine,
    PositionSide,
    RiskLimits,
    TradingMode,
)
from backend.backtesting.universal_engine.live_trading import (
    Order as LiveOrder,
)
from backend.backtesting.universal_engine.live_trading import (
    OrderManager as LiveOrderManager,
)
from backend.backtesting.universal_engine.live_trading import (
    OrderSide as LiveOrderSide,
)
from backend.backtesting.universal_engine.live_trading import (
    OrderStatus as LiveOrderStatus,
)
from backend.backtesting.universal_engine.live_trading import (
    OrderType as LiveOrderType,
)
from backend.backtesting.universal_engine.live_trading import (
    Position as LivePosition,
)
from backend.backtesting.universal_engine.live_trading import (
    PositionTracker as LivePositionTracker,
)
from backend.backtesting.universal_engine.live_trading import (
    RiskManager as LiveRiskManager,
)
from backend.backtesting.universal_engine.live_trading import (
    Trade as LiveTrade,
)

# Multi-Exchange Arbitrage (v2.3)
from backend.backtesting.universal_engine.multi_exchange import (
    ArbitrageConfig,
    ArbitrageDetector,
    ArbitrageExecution,
    ArbitrageOpportunity,
    ArbitrageType,
    CrossExchangeTrader,
    ExchangeBalance,
    ExchangeConfig,
    ExchangeConnector,
    ExchangeFees,
    ExchangeName,
    ExchangeTicker,
    FeeBreakdown,
    FeeCalculator,
    LatencyProfile,
    LatencySimulator,
    TraderConfig,
)
from backend.backtesting.universal_engine.optimizer import UniversalOptimizer

# Options Strategies (v2.4)
from backend.backtesting.universal_engine.options_strategies import (
    BinomialTree,
    BlackScholes,
    Greeks,
    GreeksCalculator,
    ImpliedVolatility,
    MonteCarloPricer,
    Option,
    OptionPosition,
    OptionsPortfolio,
    OptionsStrategy,
    OptionStyle,
    OptionType,
    StrategyFactory,
    StrategyLeg,
    StrategyPayoff,
    StrategyType,
    VolatilitySurface,
)

# Order Book & Market Impact (v2.3)
from backend.backtesting.universal_engine.order_book import (
    CascadeConfig,
    CascadeResult,
    DepthMetrics,
    LiquidationCascadeSimulator,
    LiquidationLevel,
    MarketDepthAnalyzer,
    MarketImpactCalculator,
    MarketImpactConfig,
    MarketImpactResult,
    OrderBookConfig,
    OrderBookLevel,
    OrderBookSide,
    OrderBookSimulator,
    OrderBookSnapshot,
    OrderFlowAnalyzer,
    OrderFlowMetrics,
)

# Portfolio and metrics
from backend.backtesting.universal_engine.portfolio_metrics import (
    AllocationMethod,
    CorrelationManager,
    MetricsCalculator,
    MetricsConfig,
    PortfolioConfig,
    PortfolioManager,
    PortfolioMode,
)
from backend.backtesting.universal_engine.position_manager import (
    UniversalPositionManager,
)

# Realistic simulation (v2.1)
from backend.backtesting.universal_engine.realistic_simulation import (
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

# Real-time Market Data (v2.3)
from backend.backtesting.universal_engine.realtime_data import (
    CandleAggregator,
    KlineUpdate,
    MarketDataStream,
    OrderBookStream,
    OrderBookUpdate,
    StreamConfig,
    StreamManager,
    StreamManagerConfig,
    StreamStatus,
    StreamType,
    TickerStream,
    TickerUpdate,
    TradeStream,
    TradeUpdate,
)

# Regime Detection (v2.4)
from backend.backtesting.universal_engine.regime_detection import (
    ClusteringRegimeDetector,
    EnsembleRegimeDetector,
    MarketRegime,
    MLRegimeClassifier,
    RegimeConfig,
    RegimeDetector,
    RegimeFeatureEngine,
    RegimeMethod,
    RegimeOutput,
    RegimeState,
    RegimeTransition,
    RuleBasedRegimeDetector,
)

# Reinforcement Learning (v2.4)
from backend.backtesting.universal_engine.reinforcement_learning import (
    A3CAgent,
    Action,
    Adam,
    AgentFactory,
    BaseAgent,
    Dense,
    DQNAgent,
    Experience,
    ExperienceReplay,
    Layer,
    NeuralNetwork,
    PPOAgent,
    PrioritizedReplay,
    ReLU,
    RewardType,
    RLConfig,
    RLTrainer,
    SACAgent,
    Softmax,
    State,
    Tanh,
    TradingEnvironment,
)

# Note: OrderBookLevel imported from order_book module, not realtime_data
from backend.backtesting.universal_engine.risk_manager import UniversalRiskManager

# Risk Parity (v2.4)
from backend.backtesting.universal_engine.risk_parity import (
    Asset,
    BlackLittermanModel,
    ConstraintType,
    CovarianceEstimator,
    DynamicRebalancer,
    HierarchicalRiskParity,
    MeanVarianceOptimizer,
    OptimizationObjective,
    PortfolioConstraints,
    PortfolioFactory,
    PortfolioRiskCalculator,
    PortfolioWeights,
    RebalanceFrequency,
    RiskBudgeting,
    RiskMetrics,
    RiskParityOptimizer,
)
from backend.backtesting.universal_engine.risk_parity import (
    BacktestResult as RiskParityBacktestResult,
)

# Sentiment Analysis (v2.4)
from backend.backtesting.universal_engine.sentiment_analysis import (
    AggregateSentiment,
    FearGreedCalculator,
    LexiconSentimentAnalyzer,
    NewsSentimentAnalyzer,
    SentimentAnalyzer,
    SentimentConfig,
    SentimentData,
    SentimentLevel,
    SentimentSignal,
    SentimentSignalGenerator,
    SentimentSource,
    SocialSentimentTracker,
)
from backend.backtesting.universal_engine.signal_generator import (
    UniversalSignalGenerator,
)
from backend.backtesting.universal_engine.trade_executor import UniversalTradeExecutor

# Trading enhancements (v2.2)
from backend.backtesting.universal_engine.trading_enhancements import (
    AntiLiquidationConfig,
    BreakEvenConfig,
    CooldownConfig,
    DrawdownGuardianConfig,
    NewsEvent,
    NewsFilterConfig,
    OCOConfig,
    Order,
    OrderManager,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionAgeMetrics,
    PositionTracker,
    RiskAction,
    RiskManagement,
    RiskPerTradeConfig,
    SessionFilterConfig,
    SpreadConfig,
    SpreadSimulator,
    TradingFilters,
    TradingSession,
    TrailingStopConfig,
)

# Advanced Visualization (v2.4)
from backend.backtesting.universal_engine.visualization import (
    BaseChart,
    ChartStyle,
    ChartType,
    ColorScheme,
    CorrelationMatrixChart,
    DashboardPanel,
    EquityCurveChart,
    EquityData,
    MatplotlibChart,
    MonthlyReturnsHeatmap,
    PerformanceHeatmap,
    PlotlyChart,
    Surface3DChart,
    TradeDistributionChart,
    TradeScatterChart,
    TradeVisualization,
    TradingDashboard,
)

__all__ = [
    "A3CAgent",
    "AccountBalance",
    # Reinforcement Learning (v2.4)
    "Action",
    "Adam",
    "AdaptiveConfig",
    "AdaptiveSignalGenerator",
    # Advanced Features
    "AdvancedFeatures",
    # Advanced Optimization
    "AdvancedOptimizer",
    "AgentFactory",
    "AggregateSentiment",
    "AllocationMethod",
    "AntiLiquidationConfig",
    "ArbitrageConfig",
    "ArbitrageDetector",
    "ArbitrageExecution",
    "ArbitrageOpportunity",
    "ArbitrageType",
    "Asset",
    # AutoML Strategies (v2.4)
    "AutoMLConfig",
    "AutoMLFeatureEngineering",
    "AutoMLPipeline",
    # Realistic Simulation (v2.1)
    "BarPathType",
    "BarSimulatorConfig",
    "BaseAgent",
    "BaseChart",
    "BaseModel",
    "BatchBacktestConfig",
    "BatchBacktestResult",
    "BatchBacktester",
    "BatchBacktesterV23",
    "BayesianConfig",
    "BayesianOptimizer",
    "BinomialTree",
    "BlackLittermanModel",
    "BlackScholes",
    "BreakEvenConfig",
    "BybitConnection",
    "CandleAggregator",
    "CascadeConfig",
    "CascadeResult",
    "ChartStyle",
    # Advanced Visualization (v2.4)
    "ChartType",
    "ClassifierConfig",
    "ClusteringRegimeDetector",
    "ColorScheme",
    "ConstraintType",
    "CooldownConfig",
    "CorrelationManager",
    "CorrelationMatrixChart",
    "CovarianceEstimator",
    "CrossExchangeTrader",
    "CrossoverType",
    "DQNAgent",
    "DashboardPanel",
    "DecisionTreeModel",
    "Dense",
    "DepthMetrics",
    "DrawdownGuardianConfig",
    "DynamicFundingConfig",
    "DynamicFundingManager",
    "DynamicRebalancer",
    "EngineMetricsV23",
    "EngineOutputV23",
    "EnsembleConfig",
    "EnsembleModel",
    "EnsemblePredictor",
    "EnsembleRegimeDetector",
    "EquityCurveChart",
    "EquityData",
    "ExchangeBalance",
    "ExchangeConfig",
    "ExchangeConnection",
    "ExchangeConnector",
    "ExchangeFees",
    # Multi-Exchange Arbitrage (v2.3)
    "ExchangeName",
    "ExchangeTicker",
    "ExecutionAnalytics",
    "ExecutionReport",
    "Experience",
    "ExperienceReplay",
    "FearGreedCalculator",
    "Feature",
    # Advanced ML Signals (v2.3)
    "FeatureCategory",
    "FeatureConfig",
    "FeatureEngine",
    "FeatureEngineering",
    "FeatureSet",
    "FeatureType",
    "FeeBreakdown",
    "FeeCalculator",
    "FillResult",
    "FundingConfig",
    "FundingRateEntry",
    "GPUBackend",
    # GPU Acceleration (v2.3)
    "GPUBackendType",
    "GPUConfig",
    "GPUInfo",
    "GPUIntegrationConfig",
    "GPUOptimizer",
    "GPUOptimizerConfig",
    "GeneticConfig",
    "GeneticOptimizer",
    "Greeks",
    "GreeksCalculator",
    "HedgeConfig",
    "HedgeManager",
    "HierarchicalRiskParity",
    "ImpliedVolatility",
    "KlineUpdate",
    "LatencyProfile",
    "LatencySimulator",
    "Layer",
    "LexiconSentimentAnalyzer",
    "LinearModel",
    "LiquidationCascadeSimulator",
    "LiquidationConfig",
    "LiquidationEngine",
    "LiquidationLevel",
    "LiquidationResult",
    "LiveOrder",
    "LiveOrderManager",
    "LiveOrderSide",
    "LiveOrderStatus",
    # Live Trading (v2.4)
    "LiveOrderType",
    "LivePosition",
    "LivePositionTracker",
    "LiveRiskManager",
    "LiveTrade",
    "LiveTradingBridge",
    "MLRegimeClassifier",
    "MLSignalConfig",
    "MLStrategyConfig",
    "MLStrategyInterface",
    "MarketDataStream",
    "MarketDepthAnalyzer",
    "MarketImpactCalculator",
    "MarketImpactConfig",
    "MarketImpactResult",
    # Regime Detection (v2.4)
    "MarketRegime",
    "MatplotlibChart",
    "MeanVarianceOptimizer",
    "MetricsCalculator",
    "MetricsConfig",
    "ModelSelector",
    "ModelType",
    "MonteCarloConfig",
    "MonteCarloPricer",
    "MonteCarloResult",
    "MonteCarloSimulator",
    "MonthlyReturnsHeatmap",
    "NeuralNetwork",
    "NewsEvent",
    "NewsFilterConfig",
    "NewsSentimentAnalyzer",
    "OCOConfig",
    "OptimizationMethod",
    # Risk Parity (v2.4)
    "OptimizationObjective",
    "Option",
    "OptionPosition",
    "OptionStyle",
    # Options Strategies (v2.4)
    "OptionType",
    "OptionsPortfolio",
    "OptionsStrategy",
    "Order",
    "OrderBookConfig",
    "OrderBookIntegrationConfig",
    "OrderBookLevel",
    "OrderBookLevel",
    # Order Book & Market Impact (v2.3)
    "OrderBookSide",
    "OrderBookSimulator",
    "OrderBookSnapshot",
    "OrderBookStream",
    "OrderBookUpdate",
    "OrderFlowAnalyzer",
    "OrderFlowMetrics",
    "OrderManager",
    "OrderSide",
    "OrderStatus",
    # Trading Enhancements (v2.2)
    "OrderType",
    "PPOAgent",
    "PaperTradingEngine",
    "PartialCloseConfig",
    "PartialFillConfig",
    "PartialFillSimulator",
    "PerformanceHeatmap",
    "PlotlyChart",
    # Portfolio & Metrics
    "PortfolioConfig",
    "PortfolioConstraints",
    "PortfolioFactory",
    "PortfolioManager",
    "PortfolioMode",
    "PortfolioRiskCalculator",
    "PortfolioWeights",
    "PositionAgeMetrics",
    "PositionSide",
    "PositionTracker",
    "PrioritizedReplay",
    "RLConfig",
    "RLTrainer",
    "ReLU",
    "RealisticBarSimulator",
    "RebalanceFrequency",
    "RegimeConfig",
    "RegimeDetector",
    "RegimeFeatureEngine",
    "RegimeMethod",
    "RegimeOutput",
    "RegimeState",
    "RegimeTransition",
    "RewardType",
    "RiskAction",
    "RiskBudgeting",
    "RiskLimits",
    "RiskManagement",
    "RiskMetrics",
    "RiskParityBacktestResult",
    "RiskParityOptimizer",
    "RiskPerTradeConfig",
    "RuleBasedRegimeDetector",
    "SACAgent",
    "ScaleInConfig",
    "ScaleInMode",
    "SelectionType",
    "SentimentAnalyzer",
    "SentimentConfig",
    "SentimentData",
    # Sentiment Analysis (v2.4)
    "SentimentLevel",
    "SentimentSignal",
    "SentimentSignalGenerator",
    "SentimentSource",
    "SessionFilterConfig",
    "SignalClassifier",
    "SignalCombiner",
    "SignalPrediction",
    "SignalType",
    "SimpleMLPClassifier",
    "SlippageConfig",
    "SlippageModel",
    "SocialSentimentTracker",
    "Softmax",
    "SpreadConfig",
    "SpreadSimulator",
    "State",
    "StrategyEvolver",
    "StrategyFactory",
    "StrategyGenome",
    "StrategyLeg",
    "StrategyPayoff",
    "StrategyType",
    "StreamConfig",
    "StreamManager",
    "StreamManagerConfig",
    "StreamStatus",
    # Real-time Market Data (v2.3)
    "StreamType",
    "Surface3DChart",
    "Tanh",
    "TickerStream",
    "TickerUpdate",
    "TimeExitConfig",
    "TimeExitMode",
    "TradeDistributionChart",
    "TradeScatterChart",
    "TradeStream",
    "TradeUpdate",
    "TradeVisualization",
    "TraderConfig",
    "TradingDashboard",
    "TradingEnvironment",
    "TradingFilters",
    "TradingMode",
    "TradingSession",
    "TrailingStopConfig",
    "UniversalFilterEngine",
    # Core
    "UniversalMathEngine",
    # V2.3 Integration
    "UniversalMathEngineV23",
    "UniversalOptimizer",
    "UniversalPositionManager",
    "UniversalRiskManager",
    "UniversalSignalGenerator",
    "UniversalTradeExecutor",
    "V23IntegrationConfig",
    "ValidationResult",
    "VectorizedIndicators",
    "VolatilitySurface",
    "VolumeSlippageConfig",
    "VolumeSlippageModel",
    "WalkForwardAnalyzer",
    "WalkForwardConfig",
    "WalkForwardMode",
    "WalkForwardResult",
    "WalkForwardValidator",
]

__version__ = "2.4.0"
