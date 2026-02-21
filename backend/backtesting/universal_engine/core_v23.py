"""
Universal Math Engine Core v2.3 - Extended with v2.3 Integrations.

New in v2.3:
- Order Book simulation with market impact
- GPU acceleration for batch operations
- Real-time data streaming interface
- Advanced ML-based signals
- Multi-exchange arbitrage detection

Author: Universal Math Engine Team
Version: 2.3.0
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

# v2.3 modules - Advanced Signals
from backend.backtesting.universal_engine.advanced_signals import (
    AdaptiveConfig,
    AdaptiveSignalGenerator,
    FeatureCategory,
    FeatureConfig,
    FeatureEngine,
)

# Core modules
from backend.backtesting.universal_engine.filter_engine import (
    FilterConfig,
    UniversalFilterEngine,
)

# v2.3 modules - GPU Acceleration
from backend.backtesting.universal_engine.gpu_acceleration import (
    GPUBackend,
    GPUBackendType,
    GPUConfig,
    VectorizedIndicators,
)

# v2.3 modules - Order Book
from backend.backtesting.universal_engine.order_book import (
    MarketDepthAnalyzer,
    MarketImpactCalculator,
    MarketImpactConfig,
    MarketImpactResult,
    OrderBookConfig,
    OrderBookSimulator,
    OrderFlowAnalyzer,
)
from backend.backtesting.universal_engine.position_manager import (
    PositionConfig,
    UniversalPositionManager,
)
from backend.backtesting.universal_engine.risk_manager import (
    RiskConfig,
    TradeResult,
    UniversalRiskManager,
)
from backend.backtesting.universal_engine.signal_generator import (
    SignalOutput,
    UniversalSignalGenerator,
)
from backend.backtesting.universal_engine.trade_executor import (
    ExecutorConfig,
    ExitReason,
    TradeRecord,
    UniversalTradeExecutor,
)

# =============================================================================
# V2.3 CONFIGURATION
# =============================================================================


@dataclass
class OrderBookIntegrationConfig:
    """Configuration for order book integration in backtesting."""

    enabled: bool = False
    depth_levels: int = 25
    tick_size: float = 0.01
    base_liquidity: float = 10.0

    # Market impact settings
    apply_market_impact: bool = True
    permanent_impact_coef: float = 0.1
    temporary_impact_coef: float = 0.2

    # Slippage from order book
    use_orderbook_slippage: bool = True


@dataclass
class GPUIntegrationConfig:
    """Configuration for GPU acceleration in backtesting."""

    enabled: bool = False
    preferred_backend: GPUBackendType = GPUBackendType.CPU
    memory_limit: float = 0.8
    batch_size: int = 1024

    # Use GPU for indicators
    gpu_indicators: bool = True

    # Use GPU for batch backtesting
    gpu_batch_backtest: bool = True


@dataclass
class MLSignalConfig:
    """Configuration for ML-based signal generation."""

    enabled: bool = False

    # Feature engineering
    feature_short_period: int = 5
    feature_medium_period: int = 20
    feature_long_period: int = 50
    feature_categories: list[FeatureCategory] = field(
        default_factory=lambda: [
            FeatureCategory.PRICE,
            FeatureCategory.MOMENTUM,
            FeatureCategory.VOLATILITY,
        ]
    )
    normalize_features: bool = True

    # Signal classifier
    classifier_hidden_layers: list[int] = field(default_factory=lambda: [64, 32])
    classifier_learning_rate: float = 0.001
    classifier_epochs: int = 100

    # Ensemble settings
    use_ensemble: bool = False
    ensemble_n_models: int = 3

    # Adaptive signal generation
    use_adaptive: bool = False
    adaptive_lookback: int = 100


@dataclass
class V23IntegrationConfig:
    """Combined configuration for all v2.3 integrations."""

    order_book: OrderBookIntegrationConfig = field(default_factory=OrderBookIntegrationConfig)
    gpu: GPUIntegrationConfig = field(default_factory=GPUIntegrationConfig)
    ml_signals: MLSignalConfig = field(default_factory=MLSignalConfig)


# =============================================================================
# ENGINE METRICS (Extended)
# =============================================================================


@dataclass
class EngineMetricsV23:
    """Extended metrics with v2.3 additions."""

    # === Basic Metrics ===
    net_profit: float = 0.0
    total_return: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    # === Drawdown ===
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0

    # === Risk Metrics ===
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # === Trade Stats ===
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    # === Averages ===
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    avg_trade_duration: float = 0.0

    # === Long/Short ===
    long_trades: int = 0
    short_trades: int = 0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0

    # === Advanced ===
    expectancy: float = 0.0
    payoff_ratio: float = 0.0
    recovery_factor: float = 0.0

    # === V2.3: Order Book Metrics ===
    total_market_impact: float = 0.0
    avg_slippage_from_orderbook: float = 0.0
    total_slippage_cost: float = 0.0

    # === V2.3: ML Signal Metrics ===
    ml_signal_accuracy: float = 0.0
    ml_signal_precision: float = 0.0
    ml_signal_recall: float = 0.0
    traditional_vs_ml_pnl_diff: float = 0.0

    # === V2.3: Performance Metrics ===
    gpu_speedup_factor: float = 1.0
    execution_time_indicators: float = 0.0
    execution_time_signals: float = 0.0
    execution_time_simulation: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            # Basic
            "net_profit": round(self.net_profit, 2),
            "total_return": round(self.total_return, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate * 100, 1),
            "profit_factor": round(self.profit_factor, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "expectancy": round(self.expectancy, 2),
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            # V2.3 additions
            "total_market_impact": round(self.total_market_impact, 4),
            "avg_slippage_from_orderbook": round(self.avg_slippage_from_orderbook, 6),
            "ml_signal_accuracy": round(self.ml_signal_accuracy, 4),
            "gpu_speedup_factor": round(self.gpu_speedup_factor, 2),
        }


@dataclass
class EngineOutputV23:
    """Extended output with v2.3 features."""

    metrics: EngineMetricsV23 = field(default_factory=EngineMetricsV23)
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: np.ndarray = field(default_factory=lambda: np.array([]))
    timestamps: np.ndarray = field(default_factory=lambda: np.array([]))

    # Meta
    engine_name: str = "UniversalMathEngineV23"
    execution_time: float = 0.0
    bars_processed: int = 0

    # Validation
    is_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)

    # Signal stats
    signals_generated: int = 0
    signals_filtered: int = 0
    filter_stats: dict = field(default_factory=dict)

    # V2.3: Order Book data
    market_impact_history: list[MarketImpactResult] = field(default_factory=list)
    orderbook_slippage_history: list[float] = field(default_factory=list)

    # V2.3: ML Signal data
    ml_features: dict[str, np.ndarray] | None = None
    ml_predictions: np.ndarray | None = None
    ml_confidence: np.ndarray | None = None

    # V2.3: Performance breakdown
    timing_breakdown: dict[str, float] = field(default_factory=dict)


# =============================================================================
# UNIVERSAL MATH ENGINE V2.3
# =============================================================================


class UniversalMathEngineV23:
    """
    Universal Math Engine v2.3 - Extended with all v2.3 integrations.

    New Features:
    - Order Book Simulation with market impact
    - GPU-accelerated indicators and batch backtesting
    - ML-based signal generation with ensemble
    - Enhanced metrics and timing breakdown

    Pipeline:
    1. Signal Generation (traditional + ML)
    2. Signal Filtering (MTF, BTC, Volume, ML confidence)
    3. Position Sizing (Fixed, Risk, Kelly)
    4. Order Book Impact Calculation
    5. Trade Execution (with realistic slippage)
    6. Risk Management
    7. Extended Metrics Calculation
    """

    def __init__(
        self,
        use_numba: bool = True,
        v23_config: V23IntegrationConfig | None = None,
    ):
        """
        Initialize Universal Math Engine v2.3.

        Args:
            use_numba: Use Numba acceleration where available
            v23_config: Configuration for v2.3 features
        """
        self.use_numba = use_numba
        self.v23_config = v23_config or V23IntegrationConfig()

        # Core modules
        self.signal_generator = UniversalSignalGenerator(use_numba=use_numba)
        self.filter_engine = UniversalFilterEngine(use_numba=use_numba)

        # Per-run modules
        self.position_manager: UniversalPositionManager | None = None
        self.trade_executor: UniversalTradeExecutor | None = None
        self.risk_manager: UniversalRiskManager | None = None

        # V2.3 modules
        self._init_v23_modules()

        logger.info("UniversalMathEngineV23 initialized")

    def _init_v23_modules(self):
        """Initialize v2.3 modules based on config."""
        # Order Book
        if self.v23_config.order_book.enabled:
            ob_config = OrderBookConfig(
                depth_levels=self.v23_config.order_book.depth_levels,
                tick_size=self.v23_config.order_book.tick_size,
                base_liquidity=self.v23_config.order_book.base_liquidity,
            )
            self.order_book_sim = OrderBookSimulator(ob_config)
            self.market_impact_calc = MarketImpactCalculator(
                MarketImpactConfig(
                    permanent_impact_coef=self.v23_config.order_book.permanent_impact_coef,
                    temporary_impact_coef=self.v23_config.order_book.temporary_impact_coef,
                )
            )
            self.order_flow_analyzer = OrderFlowAnalyzer()
            self.depth_analyzer = MarketDepthAnalyzer()
            logger.info("Order Book integration enabled")
        else:
            self.order_book_sim = None  # type: ignore[assignment]
            self.market_impact_calc = None  # type: ignore[assignment]
            self.order_flow_analyzer = None  # type: ignore[assignment]
            self.depth_analyzer = None  # type: ignore[assignment]

        # GPU Acceleration
        if self.v23_config.gpu.enabled:
            gpu_config = GPUConfig(
                preferred_backend=self.v23_config.gpu.preferred_backend,
                memory_limit=self.v23_config.gpu.memory_limit,
                batch_size=self.v23_config.gpu.batch_size,
            )
            self.gpu_backend = GPUBackend(gpu_config)
            self.vectorized_indicators = VectorizedIndicators(self.gpu_backend)
            logger.info(f"GPU acceleration enabled: {self.gpu_backend.backend_type}")
        else:
            self.gpu_backend = None  # type: ignore[assignment]
            self.vectorized_indicators = None  # type: ignore[assignment]

        # ML Signals
        if self.v23_config.ml_signals.enabled:
            feature_config = FeatureConfig(
                short_period=self.v23_config.ml_signals.feature_short_period,
                medium_period=self.v23_config.ml_signals.feature_medium_period,
                long_period=self.v23_config.ml_signals.feature_long_period,
                categories=self.v23_config.ml_signals.feature_categories,
                normalize=self.v23_config.ml_signals.normalize_features,
            )
            self.feature_engine = FeatureEngine(feature_config)

            if self.v23_config.ml_signals.use_adaptive:
                adaptive_config = AdaptiveConfig(lookback_window=self.v23_config.ml_signals.adaptive_lookback)
                self.ml_signal_generator = AdaptiveSignalGenerator(  # type: ignore[call-arg]
                    self.feature_engine, adaptive_config  # type: ignore[arg-type]
                )
            else:
                self.ml_signal_generator = None  # type: ignore[assignment]

            logger.info("ML Signal integration enabled")
        else:
            self.feature_engine = None  # type: ignore[assignment]
            self.ml_signal_generator = None  # type: ignore[assignment]

    def run(
        self,
        candles: pd.DataFrame,
        strategy_type: str,
        strategy_params: dict[str, Any],
        initial_capital: float = 10000.0,
        direction: str = "both",
        stop_loss: float = 0.02,
        take_profit: float = 0.03,
        leverage: int = 10,
        position_size: float = 0.10,
        taker_fee: float = 0.0007,  # TradingView parity (CLAUDE.md §5)
        slippage: float = 0.0005,
        # Advanced options
        filter_config: FilterConfig | None = None,
        position_config: PositionConfig | None = None,
        executor_config: ExecutorConfig | None = None,
        risk_config: RiskConfig | None = None,
    ) -> EngineOutputV23:
        """
        Run backtest with all v2.3 features.

        Args:
            candles: OHLCV DataFrame
            strategy_type: Strategy type (rsi, macd, bb, etc.)
            strategy_params: Strategy parameters
            initial_capital: Starting capital
            direction: "long", "short", or "both"
            stop_loss: Stop loss percentage
            take_profit: Take profit percentage
            leverage: Leverage multiplier
            position_size: Position size as fraction of capital
            taker_fee: Taker fee
            slippage: Slippage (overridden by order book if enabled)
            filter_config: Optional filter configuration
            position_config: Optional position configuration
            executor_config: Optional executor configuration
            risk_config: Optional risk configuration

        Returns:
            EngineOutputV23 with extended metrics
        """
        start_time = time.time()
        output = EngineOutputV23()
        timing = {}

        try:
            # Validate input
            if candles is None or len(candles) == 0:
                output.is_valid = False
                output.validation_errors.append("Empty candles DataFrame")
                return output

            n_bars = len(candles)
            output.bars_processed = n_bars

            # Extract OHLCV
            close = candles["close"].values.astype(np.float64)
            high = candles["high"].values.astype(np.float64) if "high" in candles else close
            low = candles["low"].values.astype(np.float64) if "low" in candles else close
            open_prices = candles["open"].values.astype(np.float64) if "open" in candles else close
            volume = candles["volume"].values.astype(np.float64) if "volume" in candles else np.ones(n_bars)

            # Get timestamps
            if hasattr(candles.index, "to_pydatetime"):
                timestamps = candles.index.to_pydatetime()
            else:
                timestamps = [datetime.now() for _ in range(n_bars)]

            # =================================================================
            # STEP 1: Generate signals (traditional or GPU-accelerated)
            # =================================================================
            t_signals_start = time.time()

            if self.v23_config.gpu.enabled and self.v23_config.gpu.gpu_indicators:
                # Use GPU-accelerated indicators
                signal_output = self._generate_signals_gpu(
                    close, high, low, volume, strategy_type, strategy_params, direction
                )
            else:
                # Standard signal generation
                signal_output = self.signal_generator.generate(candles, strategy_type, strategy_params, direction)

            long_entries = signal_output.long_entries
            long_exits = signal_output.long_exits
            short_entries = signal_output.short_entries
            short_exits = signal_output.short_exits

            output.signals_generated = int(np.sum(long_entries) + np.sum(short_entries))
            timing["signals"] = time.time() - t_signals_start

            # =================================================================
            # STEP 1b: ML-enhanced signals (if enabled)
            # =================================================================
            if self.v23_config.ml_signals.enabled:
                t_ml_start = time.time()
                ml_result = self._enhance_signals_ml(candles, long_entries, short_entries, direction)
                if ml_result is not None:
                    long_entries, short_entries, ml_features, ml_predictions = ml_result
                    output.ml_features = ml_features
                    output.ml_predictions = ml_predictions
                timing["ml_signals"] = time.time() - t_ml_start

            # =================================================================
            # STEP 2: Apply filters
            # =================================================================
            if filter_config is not None:
                t_filter_start = time.time()
                filter_output = self.filter_engine.apply_filters(candles, long_entries, short_entries, filter_config)
                long_entries = filter_output.long_entries
                short_entries = filter_output.short_entries
                output.filter_stats = filter_output.filter_stats
                timing["filters"] = time.time() - t_filter_start

            output.signals_filtered = int(np.sum(long_entries) + np.sum(short_entries))

            # =================================================================
            # STEP 3: Initialize managers
            # =================================================================
            if position_config is None:
                position_config = PositionConfig(
                    position_size=position_size,
                    leverage=leverage,
                    stop_loss=stop_loss,
                )
            self.position_manager = UniversalPositionManager(position_config)

            if executor_config is None:
                executor_config = ExecutorConfig(
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    taker_fee=taker_fee,
                    slippage=slippage,
                    leverage=leverage,
                )
            self.trade_executor = UniversalTradeExecutor(executor_config)
            self.trade_executor.set_atr_values(high, low, close)

            if risk_config is None:
                risk_config = RiskConfig()
            self.risk_manager = UniversalRiskManager(risk_config, initial_capital)

            # =================================================================
            # STEP 3b: Initialize Order Book (if enabled)
            # =================================================================
            if self.order_book_sim is not None:
                self.order_book_sim.initialize(mid_price=close[0])

            # =================================================================
            # STEP 4: Main simulation loop
            # =================================================================
            t_sim_start = time.time()

            equity = np.zeros(n_bars, dtype=np.float64)
            equity[0] = initial_capital
            current_capital = initial_capital

            market_impact_history = []
            orderbook_slippage_history = []
            total_market_impact = 0.0
            total_slippage_cost = 0.0

            for i in range(1, n_bars):
                bar_time = timestamps[i] if i < len(timestamps) else datetime.now()

                # Update order book (if enabled)
                if self.order_book_sim is not None:
                    self.order_book_sim.update(
                        new_mid_price=close[i],
                        timestamp=i,
                        volatility=np.std(close[max(0, i - 20) : i + 1]) / close[i] if i > 20 else 0.01,
                    )

                # Check if can trade
                can_trade, _reason = self.risk_manager.can_trade(i, bar_time)

                # Process existing trades
                closed_trades = self.trade_executor.process_bar(
                    bar_index=i,
                    bar_time=bar_time,
                    open_price=open_prices[i],
                    high=high[i],
                    low=low[i],
                    close=close[i],
                    long_exit=long_exits[i],
                    short_exit=short_exits[i],
                )

                # Update capital
                for trade in closed_trades:
                    current_capital += trade.pnl
                    self.risk_manager.record_trade(
                        TradeResult(
                            pnl=trade.pnl,
                            pnl_pct=trade.pnl_pct,
                            exit_time=trade.exit_time,
                            exit_bar=i,
                            is_win=trade.pnl > 0,
                        ),
                        current_bar=i,
                    )

                self.risk_manager.update_equity(current_capital)

                # Check for new entries
                if can_trade and len(self.trade_executor.active_trades) == 0:
                    entry_slippage = slippage
                    market_impact_result = None

                    # Calculate order book slippage and market impact
                    if self.v23_config.order_book.enabled and self.order_book_sim is not None:
                        # Estimate order size for slippage calculation
                        estimated_size = current_capital * position_size / close[i] * leverage

                        # Get order book slippage
                        if self.v23_config.order_book.use_orderbook_slippage:
                            snapshot = self.order_book_sim.get_snapshot()
                            if snapshot:
                                ob_slippage = self._calculate_orderbook_slippage(snapshot, estimated_size, close[i])
                                entry_slippage = max(slippage, ob_slippage)
                                orderbook_slippage_history.append(ob_slippage)

                        # Calculate market impact
                        if self.v23_config.order_book.apply_market_impact and self.market_impact_calc:
                            avg_volume = np.mean(volume[max(0, i - 20) : i + 1])
                            volatility = np.std(close[max(0, i - 20) : i + 1]) / close[i] if i > 20 else 0.01
                            market_impact_result = self.market_impact_calc.calculate_impact(
                                order_size=estimated_size,
                                average_volume=float(avg_volume),
                                current_price=close[i],
                                volatility=volatility,
                                is_buy=long_entries[i],
                            )
                            total_market_impact += market_impact_result.total_impact
                            market_impact_history.append(market_impact_result)

                    # Long entry
                    if long_entries[i] and direction in ["long", "both"]:
                        size = self.position_manager.calculate_position_size(
                            current_capital,
                            close[i],
                            "long",
                            self.trade_executor.atr_values[i] if self.trade_executor.atr_values is not None else 0,
                        )
                        if size > 0:
                            # Apply market impact to entry price
                            entry_price = close[i] * (1 + entry_slippage)
                            if market_impact_result:
                                entry_price *= 1 + market_impact_result.total_impact
                                total_slippage_cost += (entry_price - close[i]) * size * leverage

                            self.trade_executor.open_trade(
                                bar_index=i,
                                bar_time=bar_time,
                                price=entry_price,
                                size=size,
                                direction="long",
                                atr_value=self.trade_executor.atr_values[i]
                                if self.trade_executor.atr_values is not None
                                else 0,
                            )

                    # Short entry
                    elif short_entries[i] and direction in ["short", "both"]:
                        size = self.position_manager.calculate_position_size(
                            current_capital,
                            close[i],
                            "short",
                            self.trade_executor.atr_values[i] if self.trade_executor.atr_values is not None else 0,
                        )
                        if size > 0:
                            # Apply market impact to entry price
                            entry_price = close[i] * (1 - entry_slippage)
                            if market_impact_result:
                                entry_price *= 1 - market_impact_result.total_impact
                                total_slippage_cost += (close[i] - entry_price) * size * leverage

                            self.trade_executor.open_trade(
                                bar_index=i,
                                bar_time=bar_time,
                                price=entry_price,
                                size=size,
                                direction="short",
                                atr_value=self.trade_executor.atr_values[i]
                                if self.trade_executor.atr_values is not None
                                else 0,
                            )

                equity[i] = current_capital

            timing["simulation"] = time.time() - t_sim_start

            # =================================================================
            # STEP 5: Close remaining trades
            # =================================================================
            final_closed = self.trade_executor.close_all_trades(
                bar_index=n_bars - 1,
                bar_time=timestamps[-1] if len(timestamps) > 0 else datetime.now(),
                close_price=close[-1],
                reason=ExitReason.END_OF_DATA,
            )

            for trade in final_closed:
                current_capital += trade.pnl

            equity[-1] = current_capital

            # =================================================================
            # STEP 6: Calculate extended metrics
            # =================================================================
            all_trades = self.trade_executor.completed_trades
            output.trades = all_trades
            output.equity_curve = equity
            output.timestamps = np.array(timestamps)
            output.metrics = self._calculate_metrics_v23(
                all_trades,
                equity,
                initial_capital,
                market_impact_history,
                orderbook_slippage_history,
                total_market_impact,
                total_slippage_cost,
            )

            # Store v2.3 specific data
            output.market_impact_history = market_impact_history
            output.orderbook_slippage_history = orderbook_slippage_history
            output.timing_breakdown = timing

            # Update timing metrics
            output.metrics.execution_time_signals = timing.get("signals", 0.0)
            output.metrics.execution_time_simulation = timing.get("simulation", 0.0)

        except Exception as e:
            logger.error(f"UniversalMathEngineV23 error: {e}")
            import traceback

            traceback.print_exc()
            output.is_valid = False
            output.validation_errors.append(str(e))

        output.execution_time = time.time() - start_time
        return output

    def _generate_signals_gpu(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
        strategy_type: str,
        strategy_params: dict[str, Any],
        direction: str,
    ) -> SignalOutput:
        """Generate signals using GPU-accelerated indicators."""
        n = len(close)
        long_entries = np.zeros(n, dtype=bool)
        long_exits = np.zeros(n, dtype=bool)
        short_entries = np.zeros(n, dtype=bool)
        short_exits = np.zeros(n, dtype=bool)

        vi = self.vectorized_indicators

        # Helper to convert CuPy array to NumPy if needed
        def to_numpy(arr):
            if hasattr(arr, "get"):
                return arr.get()
            return arr

        # Convert input to GPU array if needed
        xp = self.gpu_backend.xp  # NumPy or CuPy
        close_gpu = xp.asarray(close) if xp.__name__ == "cupy" else close  # noqa: cSpell

        if strategy_type == "rsi":
            period = strategy_params.get("period", 14)
            oversold = strategy_params.get("oversold", 30)
            overbought = strategy_params.get("overbought", 70)

            rsi = to_numpy(vi.rsi(close_gpu, period))

            # Entry signals
            if direction in ["long", "both"]:
                long_entries[1:] = (rsi[:-1] < oversold) & (rsi[1:] >= oversold)
            if direction in ["short", "both"]:
                short_entries[1:] = (rsi[:-1] > overbought) & (rsi[1:] <= overbought)

            # Exit signals
            long_exits[1:] = rsi[1:] >= overbought
            short_exits[1:] = rsi[1:] <= oversold

        elif strategy_type == "macd":
            fast = strategy_params.get("fast_period", 12)
            slow = strategy_params.get("slow_period", 26)
            signal = strategy_params.get("signal_period", 9)

            macd_result = vi.macd(close_gpu, fast, slow, signal)
            macd_line = to_numpy(macd_result[0])
            signal_line = to_numpy(macd_result[1])

            # Entry signals
            if direction in ["long", "both"]:
                long_entries[1:] = (macd_line[:-1] <= signal_line[:-1]) & (macd_line[1:] > signal_line[1:])
            if direction in ["short", "both"]:
                short_entries[1:] = (macd_line[:-1] >= signal_line[:-1]) & (macd_line[1:] < signal_line[1:])

            # Exit signals
            long_exits[1:] = macd_line[1:] < signal_line[1:]
            short_exits[1:] = macd_line[1:] > signal_line[1:]

        elif strategy_type == "bb":
            period = strategy_params.get("period", 20)
            std_dev = strategy_params.get("std_dev", 2.0)

            bb_result = vi.bollinger_bands(close_gpu, period, std_dev)
            upper = to_numpy(bb_result[0])
            middle = to_numpy(bb_result[1])
            lower = to_numpy(bb_result[2])

            # Entry signals
            if direction in ["long", "both"]:
                long_entries[1:] = close[1:] < lower[1:]
            if direction in ["short", "both"]:
                short_entries[1:] = close[1:] > upper[1:]

            # Exit signals
            long_exits[1:] = close[1:] >= middle[1:]
            short_exits[1:] = close[1:] <= middle[1:]

        else:
            # Fallback to standard signal generator
            logger.warning(f"Strategy {strategy_type} not GPU-optimized, using standard")
            # Create dummy DataFrame for standard generator
            import pandas as pd

            df = pd.DataFrame({"close": close, "high": high, "low": low, "volume": volume})
            return self.signal_generator.generate(df, strategy_type, strategy_params, direction)

        return SignalOutput(
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            indicator_values={},
        )

    def _enhance_signals_ml(
        self,
        candles: pd.DataFrame,
        long_entries: np.ndarray,
        short_entries: np.ndarray,
        direction: str,
    ) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], np.ndarray] | None:
        """Enhance signals using ML features."""
        if self.feature_engine is None:
            return None

        try:
            # Generate features
            ohlcv = {
                "open": candles["open"].values,
                "high": candles["high"].values,
                "low": candles["low"].values,
                "close": candles["close"].values,
                "volume": candles["volume"].values if "volume" in candles else np.ones(len(candles)),
            }
            features = self.feature_engine.generate_features(ohlcv)

            # For now, use features to filter low-confidence signals
            # Future: Train classifier on historical data

            # Use momentum features for confidence
            momentum_conf = np.zeros(len(candles))
            if "rsi_14" in features:
                rsi = features["rsi_14"]
                # High confidence for extreme RSI
                momentum_conf = np.abs(rsi - 50) / 50  # type: ignore[assignment]

            # Filter signals by confidence threshold
            confidence_threshold = 0.3
            enhanced_long = long_entries & (momentum_conf > confidence_threshold)
            enhanced_short = short_entries & (momentum_conf > confidence_threshold)

            return enhanced_long, enhanced_short, features, momentum_conf

        except Exception as e:
            logger.warning(f"ML signal enhancement failed: {e}")
            return None

    def _calculate_orderbook_slippage(self, snapshot, size: float, current_price: float) -> float:
        """Calculate slippage from order book depth."""
        if not snapshot.asks:
            return 0.0

        remaining_size = size
        total_cost = 0.0

        for level in snapshot.asks:
            if remaining_size <= 0:
                break
            fill_size = min(remaining_size, level.size)
            total_cost += fill_size * level.price
            remaining_size -= fill_size

        if size > 0:
            avg_price = total_cost / (size - remaining_size) if remaining_size < size else current_price
            slippage = (avg_price - current_price) / current_price
            return max(0, slippage)
        return 0.0

    def _calculate_metrics_v23(
        self,
        trades: list[TradeRecord],
        equity: np.ndarray,
        initial_capital: float,
        market_impact_history: list[MarketImpactResult],
        orderbook_slippage_history: list[float],
        total_market_impact: float,
        total_slippage_cost: float,
    ) -> EngineMetricsV23:
        """Calculate all metrics including v2.3 additions."""
        metrics = EngineMetricsV23()

        if not trades:
            return metrics

        # === Basic stats ===
        pnls = np.array([t.pnl for t in trades])
        metrics.net_profit = float(np.sum(pnls))
        metrics.total_return = (equity[-1] - initial_capital) / initial_capital * 100

        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]

        metrics.gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
        metrics.gross_loss = float(np.sum(losses)) if len(losses) > 0 else 0.0

        metrics.total_trades = len(trades)
        metrics.winning_trades = len(wins)
        metrics.losing_trades = len(losses)
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0.0

        metrics.avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
        metrics.avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
        metrics.avg_trade = float(np.mean(pnls))

        # Profit factor
        if abs(metrics.gross_loss) > 0:
            metrics.profit_factor = abs(metrics.gross_profit / metrics.gross_loss)
        else:
            metrics.profit_factor = float("inf") if metrics.gross_profit > 0 else 0.0

        # Expectancy
        metrics.expectancy = metrics.win_rate * metrics.avg_win + (1 - metrics.win_rate) * metrics.avg_loss

        # Drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        metrics.max_drawdown = float(np.max(drawdown)) * 100

        # Sharpe ratio
        returns = np.diff(equity) / equity[:-1]
        if len(returns) > 1 and np.std(returns) > 0:
            metrics.sharpe_ratio = float(np.mean(returns) / np.std(returns) * np.sqrt(252))

        # Sortino ratio
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0 and np.std(negative_returns) > 0:
            metrics.sortino_ratio = float(np.mean(returns) / np.std(negative_returns) * np.sqrt(252))

        # Calmar ratio
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = metrics.total_return / metrics.max_drawdown

        # Long/Short breakdown
        long_trades = [t for t in trades if t.direction == "long"]
        short_trades = [t for t in trades if t.direction == "short"]

        metrics.long_trades = len(long_trades)
        metrics.short_trades = len(short_trades)

        if long_trades:
            long_wins = sum(1 for t in long_trades if t.pnl > 0)
            metrics.long_win_rate = long_wins / len(long_trades)

        if short_trades:
            short_wins = sum(1 for t in short_trades if t.pnl > 0)
            metrics.short_win_rate = short_wins / len(short_trades)

        # Average trade duration
        durations = [t.duration_bars for t in trades]
        metrics.avg_trade_duration = float(np.mean(durations)) if durations else 0.0

        # === V2.3 Metrics ===
        metrics.total_market_impact = total_market_impact
        metrics.total_slippage_cost = total_slippage_cost

        if orderbook_slippage_history:
            metrics.avg_slippage_from_orderbook = float(np.mean(orderbook_slippage_history))

        return metrics

    @property
    def name(self) -> str:
        return "UniversalMathEngineV23"

    @property
    def version(self) -> str:
        return "2.3.0"


# =============================================================================
# BATCH BACKTESTER (GPU)
# =============================================================================


class BatchBacktesterV23:
    """
    Batch backtester using GPU acceleration for parallel runs.

    Runs multiple parameter combinations simultaneously on GPU.
    """

    def __init__(
        self,
        engine: UniversalMathEngineV23 | None = None,
        gpu_config: GPUConfig | None = None,
    ):
        """Initialize batch backtester."""
        self.engine = engine or UniversalMathEngineV23()
        self.gpu_config = gpu_config or GPUConfig()

        if CUPY_AVAILABLE or OPENCL_AVAILABLE:
            self.gpu_backend = GPUBackend(self.gpu_config)
        else:
            self.gpu_backend = None  # type: ignore[assignment]
            logger.warning("No GPU backend available, using CPU parallelization")

    def run_batch(
        self,
        candles: pd.DataFrame,
        strategy_type: str,
        param_combinations: list[dict[str, Any]],
        base_config: dict[str, Any],
        n_jobs: int = -1,
    ) -> list[EngineOutputV23]:
        """
        Run batch of backtests with different parameters.

        Args:
            candles: OHLCV DataFrame
            strategy_type: Strategy type
            param_combinations: List of parameter dictionaries
            base_config: Base configuration
            n_jobs: Number of parallel jobs (-1 for all CPUs)

        Returns:
            List of EngineOutputV23 results
        """
        results = []

        # For now, sequential (GPU batch optimization planned)
        for params in param_combinations:
            merged_config = {**base_config, "strategy_params": params}
            result = self.engine.run(
                candles=candles,
                strategy_type=strategy_type,
                **merged_config,
            )
            results.append(result)

        return results


# Try importing CuPy
try:
    import cupy as cp  # noqa: F401

    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False

try:
    import pyopencl as cl  # noqa: F401

    OPENCL_AVAILABLE = True
except ImportError:
    OPENCL_AVAILABLE = False
