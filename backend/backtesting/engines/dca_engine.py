"""
🎯 DCA ENGINE - Dollar Cost Averaging / Grid Trading Engine

Specialized engine for DCA and Grid trading strategies based on
TradingView Multi DCA Strategy [Dimkud] parameters.

Features:
- Grid order placement with configurable levels (3-15 orders)
- Martingale position sizing (1.0-1.8 coefficient)
- Logarithmic step distribution (0.8-1.4 coefficient)
- Dynamic Take Profit adjustment based on active orders
- Multiple Take Profits (TP1-TP4)
- Safety close on drawdown
- Signal memory system

Speed: ~1x (reference implementation, extends FallbackEngineV4)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)
import pandas as pd

from backend.backtesting.interfaces import (
    BacktestInput,
    BacktestMetrics,
    BacktestOutput,
    BaseBacktestEngine,
    ExitReason,
    TradeDirection,
    TradeRecord,
)


@dataclass
class DCAGridConfig:
    """Configuration for DCA Grid strategy."""

    # Grid settings
    enabled: bool = False
    direction: str = "long"  # long, short, both
    deposit: float = 10000.0  # Total deposit for the grid
    leverage: int = 1
    grid_size_percent: float = 10.0  # Total grid size as % of price
    order_count: int = 5  # Number of orders (3-15)

    # Order distribution
    first_order_percent: float = 10.0  # First order as % of deposit
    step_type: str = "linear"  # linear, logarithmic, custom

    # Martingale
    use_martingale: bool = True
    martingale_coefficient: float = 1.3  # 1.0-1.8
    martingale_mode: str = "multiply_each"  # multiply_each, multiply_total, progressive
    max_order_size: float = 0.0  # Max single order size (0 = no limit)
    max_total_position: float = 0.0  # Max total position (0 = no limit)

    # Logarithmic steps
    use_log_steps: bool = False
    log_coefficient: float = 1.1  # 0.8-1.4

    # Safety
    close_on_drawdown: bool = False
    drawdown_threshold_percent: float = 50.0
    drawdown_threshold_amount: float = 0.0

    # Dynamic TP
    dynamic_tp_enabled: bool = False
    dynamic_tp_trigger_orders: int = 3
    dynamic_tp_new_percent: float = 0.5
    dynamic_tp_decrease_per_order: float = 0.1
    dynamic_tp_min_percent: float = 0.2

    # Alerts
    first_order_alert_only: bool = True


@dataclass
class MultipleTakeProfit:
    """Configuration for multiple take profit levels."""

    enabled: bool = False
    tp_count: int = 4  # Number of TP levels (1-4)

    # TP levels (percent from average entry)
    tp1_percent: float = 1.0
    tp1_close_percent: float = 25.0  # Close 25% at TP1

    tp2_percent: float = 2.0
    tp2_close_percent: float = 25.0

    tp3_percent: float = 3.0
    tp3_close_percent: float = 25.0

    tp4_percent: float = 5.0
    tp4_close_percent: float = 25.0  # Close remaining

    close_remaining_at_last: bool = True


@dataclass
class CloseConditionsConfig:
    """Configuration for advanced close conditions (DCA Session 5.5)."""

    # RSI Close
    rsi_close_enable: bool = False
    rsi_close_length: int = 14
    rsi_close_only_profit: bool = True
    rsi_close_min_profit: float = 0.5
    rsi_close_reach_enable: bool = False
    rsi_close_reach_long_more: float = 70
    rsi_close_reach_long_less: float = 0
    rsi_close_reach_short_more: float = 100
    rsi_close_reach_short_less: float = 30
    rsi_close_cross_enable: bool = False
    rsi_close_cross_long_level: float = 70
    rsi_close_cross_short_level: float = 30

    # Stochastic Close
    stoch_close_enable: bool = False
    stoch_close_k_length: int = 14
    stoch_close_k_smooth: int = 1
    stoch_close_d_smooth: int = 3
    stoch_close_only_profit: bool = True
    stoch_close_min_profit: float = 0.5
    stoch_close_reach_enable: bool = False
    stoch_close_reach_long_more: float = 80
    stoch_close_reach_short_less: float = 20

    # Channel Close (Keltner/Bollinger)
    channel_close_enable: bool = False
    channel_close_type: str = "Keltner"  # Keltner, Bollinger
    channel_close_band: str = "Breakout"  # Breakout, Rebound
    channel_close_keltner_length: int = 20
    channel_close_keltner_mult: float = 2.0
    channel_close_bb_length: int = 20
    channel_close_bb_deviation: float = 2.0

    # Two MAs Close
    ma_close_enable: bool = False
    ma_close_only_profit: bool = True
    ma_close_min_profit: float = 0.5
    ma_close_ma1_length: int = 9
    ma_close_ma1_type: str = "EMA"
    ma_close_ma2_length: int = 21
    ma_close_ma2_type: str = "EMA"

    # PSAR Close
    psar_close_enable: bool = False
    psar_close_only_profit: bool = True
    psar_close_min_profit: float = 0.5
    psar_close_start: float = 0.02
    psar_close_increment: float = 0.02
    psar_close_maximum: float = 0.2

    # Time/Bars Close
    time_bars_close_enable: bool = False
    close_after_bars: int = 20
    close_only_profit: bool = True
    close_min_profit: float = 0.5
    close_max_bars: int = 100


@dataclass
class IndentOrderConfig:
    """Configuration for Indent Order (Limit Entry with Offset)."""

    enabled: bool = False
    show_lines: bool = True
    indent_percent: float = 0.1  # Entry offset as % of price
    cancel_after_bars: int = 10  # Cancel pending indent if not filled


@dataclass
class PendingIndentOrder:
    """Represents a pending indent (limit) order."""

    direction: str  # "long" or "short"
    signal_bar: int  # Bar when signal was generated
    signal_price: float  # Price at signal
    entry_price: float  # Limit price for entry
    expires_bar: int  # Bar when order expires
    filled: bool = False


@dataclass
class DCAOrder:
    """Represents a single DCA order in the grid."""

    level: int  # Order level (0 = first/base order)
    price: float  # Trigger price
    size_percent: float  # Size as % of deposit
    size_usd: float  # Size in USD
    size_coins: float  # Size in coins
    filled: bool = False
    fill_time: Optional[int] = None  # Bar index when filled
    fill_price: float = 0.0


@dataclass
class DCAPosition:
    """Represents the aggregate DCA position."""

    direction: str = ""  # "long" or "short"
    is_open: bool = False

    # Orders
    orders: List[DCAOrder] = field(default_factory=list)
    active_orders_count: int = 0

    # Position aggregates
    total_size_coins: float = 0.0
    total_cost_usd: float = 0.0
    average_entry_price: float = 0.0

    # Current state
    unrealized_pnl: float = 0.0
    unrealized_pnl_percent: float = 0.0
    max_favorable_excursion: float = 0.0  # MFE
    max_adverse_excursion: float = 0.0  # MAE

    # TP state
    tp_hit: List[bool] = field(default_factory=lambda: [False, False, False, False])
    remaining_size_percent: float = 100.0

    # Timing
    entry_bar: int = 0
    last_order_bar: int = 0


class DCAGridCalculator:
    """Calculator for DCA grid order placement."""

    @staticmethod
    def calculate_grid_orders(config: DCAGridConfig, base_price: float, direction: str) -> List[DCAOrder]:
        """
        Calculate DCA grid order levels and sizes.

        Args:
            config: DCA configuration
            base_price: Current price (base for grid calculation)
            direction: "long" or "short"

        Returns:
            List of DCAOrder objects
        """
        orders = []

        # Calculate step distances
        total_grid_size = base_price * (config.grid_size_percent / 100)

        if config.use_log_steps:
            steps = DCAGridCalculator._calculate_log_steps(config.order_count, config.log_coefficient)
        else:
            # Linear steps
            steps = DCAGridCalculator._calculate_linear_steps(config.order_count)

        # Calculate order sizes with martingale
        sizes = DCAGridCalculator._calculate_order_sizes(
            config.order_count,
            config.first_order_percent,
            config.martingale_coefficient if config.use_martingale else 1.0,
            config.martingale_mode,
        )

        # Normalize sizes to sum to 100%
        total_size = sum(sizes)
        sizes = [s * 100 / total_size for s in sizes]

        # Create orders
        cumulative_step = 0.0
        for i in range(config.order_count):
            # Calculate trigger price
            step_percent = steps[i] * (config.grid_size_percent / 100)
            cumulative_step += step_percent

            if direction == "long":
                # Long grid: orders below base price
                trigger_price = base_price * (1 - cumulative_step)
            else:
                # Short grid: orders above base price
                trigger_price = base_price * (1 + cumulative_step)

            # Calculate USD size
            size_usd = config.deposit * (sizes[i] / 100)
            if config.max_order_size > 0:
                size_usd = min(size_usd, config.max_order_size)

            # Apply leverage
            size_usd_leveraged = size_usd * config.leverage

            # Calculate coins
            size_coins = size_usd_leveraged / trigger_price if trigger_price > 0 else 0

            orders.append(
                DCAOrder(level=i, price=trigger_price, size_percent=sizes[i], size_usd=size_usd, size_coins=size_coins)
            )

        return orders

    @staticmethod
    def _calculate_linear_steps(order_count: int) -> List[float]:
        """Calculate linear step distribution."""
        if order_count <= 1:
            return [1.0]
        return [1.0 / order_count] * order_count

    @staticmethod
    def _calculate_log_steps(order_count: int, coefficient: float) -> List[float]:
        """
        Calculate logarithmic step distribution.

        coefficient < 1.0: Orders closer to entry (front-loaded)
        coefficient > 1.0: Orders more spread out (back-loaded)
        """
        if order_count <= 1:
            return [1.0]

        steps = []
        total = 0.0

        for i in range(order_count):
            step = coefficient**i
            steps.append(step)
            total += step

        # Normalize
        return [s / total for s in steps]

    @staticmethod
    def _calculate_order_sizes(
        order_count: int, first_order_percent: float, martingale_coef: float, mode: str
    ) -> List[float]:
        """
        Calculate order sizes with martingale.

        Modes:
        - multiply_each: Each order is coef times the previous
        - multiply_total: Each order is coef times the sum of previous
        - progressive: Linear increase
        """
        sizes = []

        if mode == "multiply_each":
            current = first_order_percent
            for i in range(order_count):
                sizes.append(current)
                current *= martingale_coef

        elif mode == "multiply_total":
            current = first_order_percent
            total = 0.0
            for i in range(order_count):
                sizes.append(current)
                total += current
                current = total * (martingale_coef - 1)
                if current < first_order_percent:
                    current = first_order_percent

        else:  # progressive
            for i in range(order_count):
                sizes.append(first_order_percent * (1 + i * (martingale_coef - 1)))

        return sizes


class DCAEngine(BaseBacktestEngine):
    """
    DCA/Grid Trading Backtest Engine.

    Implements sophisticated DCA and grid trading with:
    - Multiple grid levels
    - Martingale position sizing
    - Logarithmic step distribution
    - Dynamic take profit adjustment
    - Multiple TP levels with partial closes

    Supports two modes:
    1. run(BacktestInput) - Interface compliant method
    2. run_from_config(BacktestConfig, pd.DataFrame) - Direct config method
    """

    def __init__(self):
        self._name = "DCA Engine v1"
        self.version = "1.0.0"

        # Configuration
        self.grid_config = DCAGridConfig()
        self.multi_tp = MultipleTakeProfit()
        self.close_conditions = CloseConditionsConfig()
        self.indent_order = IndentOrderConfig()

        # Pending indent orders
        self.pending_indent: Optional[PendingIndentOrder] = None

        # State
        self.position = DCAPosition()
        self.equity_curve: List[float] = []
        self.trades: List[TradeRecord] = []

        # Indicator caches for close conditions
        self._rsi_cache: Optional[np.ndarray] = None
        self._stoch_k_cache: Optional[np.ndarray] = None
        self._stoch_d_cache: Optional[np.ndarray] = None
        self._ma1_cache: Optional[np.ndarray] = None
        self._ma2_cache: Optional[np.ndarray] = None
        self._psar_cache: Optional[np.ndarray] = None
        self._bb_upper_cache: Optional[np.ndarray] = None
        self._bb_lower_cache: Optional[np.ndarray] = None
        self._keltner_upper_cache: Optional[np.ndarray] = None
        self._keltner_lower_cache: Optional[np.ndarray] = None

        # Statistics
        self.total_signals = 0
        self.total_orders_filled = 0

    # ===== Abstract method implementations =====

    @property
    def name(self) -> str:
        """Engine name"""
        return self._name

    @property
    def supports_bar_magnifier(self) -> bool:
        """DCAEngine supports bar magnifier for more accurate fills"""
        return True

    @property
    def supports_parallel(self) -> bool:
        """DCAEngine supports parallel optimization"""
        return True

    def optimize(
        self,
        input_data: BacktestInput,
        param_ranges: Dict[str, List[Any]],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> List[Tuple[Dict[str, Any], BacktestOutput]]:
        """
        Optimize DCA parameters using grid search.

        Args:
            input_data: Base backtest input
            param_ranges: Parameter ranges to optimize
            metric: Metric to optimize (sharpe_ratio, profit_factor, etc.)
            top_n: Number of top results to return

        Returns:
            List of (params, result) tuples sorted by metric
        """
        import itertools

        results = []

        # Generate all parameter combinations
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())

        for combo in itertools.product(*param_values):
            params = dict(zip(param_names, combo))

            # Update input_data with new params
            test_input = BacktestInput(
                market_data=input_data.market_data,
                initial_capital=input_data.initial_capital,
                leverage=input_data.leverage,
                commission=input_data.commission,
                strategy_params={**input_data.strategy_params, **params},
            )

            # Run backtest
            output = self.run(test_input)

            # Get metric value
            metric_value = getattr(output.metrics, metric, 0.0) if output.metrics else 0.0

            results.append((params, output, metric_value))

        # Sort by metric (descending) and return top_n
        results.sort(key=lambda x: x[2], reverse=True)
        return [(r[0], r[1]) for r in results[:top_n]]

    def run(self, input_data: Any) -> Any:
        """
        Execute the DCA backtest.

        Supports both:
        - BacktestInput (interface) -> BacktestOutput
        - Tuple of (BacktestConfig, pd.DataFrame) -> BacktestResult
        """
        # Check if called with BacktestConfig and DataFrame (from BacktestService)
        if hasattr(input_data, "dca_enabled"):
            # This is BacktestConfig - need DataFrame as second arg
            raise ValueError("DCAEngine.run() called with BacktestConfig. Use run_from_config(config, ohlcv) instead.")

        start_time = time.time()

        # Extract parameters
        self._configure_from_input(input_data)

        # Get data
        df = input_data.market_data
        if df is None or df.empty:
            return self._empty_result("No market data")

        # Initialize
        initial_capital = input_data.initial_capital
        equity = initial_capital
        self.equity_curve = [equity]
        self.trades = []
        self.position = DCAPosition()

        # Pre-calculate indicator caches for close conditions
        self._precompute_close_condition_indicators(df)

        # Generate signals if strategy is provided
        signals = self._generate_signals(input_data, df)

        # Main loop
        for i in range(1, len(df)):
            current_bar = df.iloc[i]
            prev_bar = df.iloc[i - 1]

            high = float(current_bar.get("high", current_bar.get("close", 0)))
            low = float(current_bar.get("low", current_bar.get("close", 0)))
            close = float(current_bar.get("close", 0))

            # Check for DCA order fills
            if self.position.is_open:
                equity = self._process_open_position(i, high, low, close, equity)

            # Check pending indent order fill
            elif self.pending_indent is not None:
                equity = self._check_indent_order_fill(i, high, low, close, equity)

            # Check for new entry signal
            elif signals[i] != 0:
                direction = "long" if signals[i] > 0 else "short"
                
                if self.indent_order.enabled:
                    # Create pending indent order instead of immediate entry
                    self._create_indent_order(i, close, direction)
                else:
                    # Immediate entry
                    self._open_dca_position(i, close, direction)
                    
                self.total_signals += 1

            # Update equity curve
            self.equity_curve.append(equity)

        # Close any remaining position
        if self.position.is_open:
            equity = self._close_position(len(df) - 1, float(df.iloc[-1]["close"]), ExitReason.END_OF_DATA)

        # Calculate metrics
        execution_time = time.time() - start_time
        metrics = self._calculate_metrics(initial_capital, equity)

        return BacktestOutput(
            trades=self.trades,
            metrics=metrics,
            equity_curve=self.equity_curve,
            execution_time_ms=execution_time * 1000,
            engine_used=self.name,
            parameters_used=input_data.strategy_params,
        )

    def _configure_from_input(self, input_data: BacktestInput) -> None:
        """Configure engine from input parameters."""
        params = input_data.strategy_params or {}

        # Grid settings
        grid = params.get("dca_grid", {})
        if grid:
            self.grid_config.enabled = grid.get("enabled", False)
            self.grid_config.direction = grid.get("direction", "long")
            self.grid_config.deposit = input_data.initial_capital
            self.grid_config.leverage = input_data.leverage or 1
            self.grid_config.grid_size_percent = grid.get("grid_size_percent", 10.0)
            self.grid_config.order_count = grid.get("order_count", 5)
            self.grid_config.use_martingale = grid.get("use_martingale", True)
            self.grid_config.martingale_coefficient = grid.get("martingale_coefficient", 1.3)
            self.grid_config.use_log_steps = grid.get("use_log_steps", False)
            self.grid_config.log_coefficient = grid.get("log_coefficient", 1.1)

        # Multi-TP settings
        multi_tp = params.get("multi_tp", {})
        if multi_tp:
            self.multi_tp.enabled = multi_tp.get("enabled", False)
            self.multi_tp.tp1_percent = multi_tp.get("tp1_percent", 1.0)
            self.multi_tp.tp1_close_percent = multi_tp.get("tp1_close_percent", 25.0)
            self.multi_tp.tp2_percent = multi_tp.get("tp2_percent", 2.0)
            self.multi_tp.tp2_close_percent = multi_tp.get("tp2_close_percent", 25.0)
            self.multi_tp.tp3_percent = multi_tp.get("tp3_percent", 3.0)
            self.multi_tp.tp3_close_percent = multi_tp.get("tp3_close_percent", 25.0)
            self.multi_tp.tp4_percent = multi_tp.get("tp4_percent", 5.0)
            self.multi_tp.tp4_close_percent = multi_tp.get("tp4_close_percent", 25.0)

    def _configure_from_config(self, config: Any) -> None:
        """
        Configure engine from BacktestConfig (Pydantic model).

        Args:
            config: BacktestConfig with DCA-specific fields
        """
        # Grid settings from BacktestConfig
        self.grid_config.enabled = getattr(config, "dca_enabled", False)
        self.grid_config.direction = getattr(config, "dca_direction", "long")
        self.grid_config.deposit = getattr(config, "initial_capital", 10000.0)
        self.grid_config.leverage = getattr(config, "leverage", 1)
        self.grid_config.grid_size_percent = getattr(config, "dca_grid_size_percent", 10.0)
        self.grid_config.order_count = getattr(config, "dca_order_count", 5)
        self.grid_config.use_martingale = getattr(config, "dca_martingale_coef", 1.0) > 1.0
        self.grid_config.martingale_coefficient = getattr(config, "dca_martingale_coef", 1.0)
        self.grid_config.martingale_mode = getattr(config, "dca_martingale_mode", "multiply_each")
        self.grid_config.use_log_steps = getattr(config, "dca_log_step_enabled", False)
        self.grid_config.log_coefficient = getattr(config, "dca_log_step_coef", 1.1)
        self.grid_config.close_on_drawdown = getattr(config, "dca_safety_close_enabled", True)
        self.grid_config.drawdown_threshold_percent = getattr(config, "dca_drawdown_threshold", 30.0)

        # Multi-TP settings from BacktestConfig
        self.multi_tp.enabled = getattr(config, "dca_multi_tp_enabled", False)
        self.multi_tp.tp1_percent = getattr(config, "dca_tp1_percent", 0.5)
        self.multi_tp.tp1_close_percent = getattr(config, "dca_tp1_close_percent", 25.0)
        self.multi_tp.tp2_percent = getattr(config, "dca_tp2_percent", 1.0)
        self.multi_tp.tp2_close_percent = getattr(config, "dca_tp2_close_percent", 25.0)
        self.multi_tp.tp3_percent = getattr(config, "dca_tp3_percent", 2.0)
        self.multi_tp.tp3_close_percent = getattr(config, "dca_tp3_close_percent", 25.0)
        self.multi_tp.tp4_percent = getattr(config, "dca_tp4_percent", 3.0)
        self.multi_tp.tp4_close_percent = getattr(config, "dca_tp4_close_percent", 25.0)

        # Close Conditions and Indent Order from strategy_params (Strategy Builder graph)
        params = getattr(config, "strategy_params", None) or {}
        close_conditions_params = params.get("close_conditions", {})
        if close_conditions_params:
            cc = self.close_conditions
            for key, value in close_conditions_params.items():
                if hasattr(cc, key):
                    setattr(cc, key, value)

        indent_order_params = params.get("indent_order", {})
        if indent_order_params:
            io = self.indent_order
            for key, value in indent_order_params.items():
                if hasattr(io, key):
                    setattr(io, key, value)

    def run_from_config(self, config: Any, ohlcv: pd.DataFrame) -> Any:
        """
        Run DCA backtest from BacktestConfig (Pydantic model).

        This is the primary method when called from BacktestService.

        Args:
            config: BacktestConfig with DCA-specific fields
            ohlcv: DataFrame with OHLCV data

        Returns:
            BacktestResult compatible object
        """
        import uuid
        from datetime import datetime

        from backend.backtesting.models import (
            BacktestResult,
            BacktestStatus,
            EquityCurve,
            PerformanceMetrics,
        )
        from backend.backtesting.models import (
            TradeRecord as ModelTradeRecord,
        )

        start_time = time.time()
        backtest_id = str(uuid.uuid4())

        # Configure from BacktestConfig
        self._configure_from_config(config)

        # Get data
        if ohlcv is None or ohlcv.empty:
            return BacktestResult(
                id=backtest_id,
                status=BacktestStatus.FAILED,
                created_at=datetime.utcnow(),
                config=config,
                error_message="No market data for DCA backtest",
            )

        # Initialize
        initial_capital = getattr(config, "initial_capital", 10000.0)
        equity = initial_capital
        self.equity_curve = [equity]
        self.trades = []
        self.position = DCAPosition()

        # Pre-calculate indicator caches for close conditions
        self._precompute_close_condition_indicators(ohlcv)

        # Generate signals using strategy from config
        signals = self._generate_signals_from_config(config, ohlcv)

        # Main loop
        for i in range(1, len(ohlcv)):
            current_bar = ohlcv.iloc[i]

            high = float(current_bar.get("high", current_bar.get("close", 0)))
            low = float(current_bar.get("low", current_bar.get("close", 0)))
            close = float(current_bar.get("close", 0))

            # Check for DCA order fills
            if self.position.is_open:
                equity = self._process_open_position(i, high, low, close, equity)

            # Check pending indent order fill (when using run_from_config)
            elif self.pending_indent is not None:
                equity = self._check_indent_order_fill(i, high, low, close, equity)

            # Check for new entry signal
            elif signals[i] != 0:
                direction = "long" if signals[i] > 0 else "short"

                # Respect dca_direction setting
                dca_direction = self.grid_config.direction
                if dca_direction == "both" or dca_direction == direction:
                    if self.indent_order.enabled:
                        self._create_indent_order(i, close, direction)
                    else:
                        self._open_dca_position(i, close, direction)
                    self.total_signals += 1

            # Update equity curve
            self.equity_curve.append(equity)

        # Close any remaining position
        if self.position.is_open:
            equity = self._close_position(len(ohlcv) - 1, float(ohlcv.iloc[-1]["close"]), ExitReason.END_OF_DATA)

        # Calculate metrics
        execution_time = time.time() - start_time

        # Convert trades to model format
        model_trades = self._convert_trades_to_model(ohlcv)

        # Build result
        metrics = self._build_performance_metrics(initial_capital, equity, model_trades)

        return BacktestResult(
            id=backtest_id,
            status=BacktestStatus.COMPLETED,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            config=config,
            trades=model_trades,
            metrics=metrics,
            equity_curve=EquityCurve(
                timestamps=[ohlcv.index[i].to_pydatetime() for i in range(min(len(ohlcv.index), len(self.equity_curve)))],
                equity=self.equity_curve,
            ),
            final_equity=equity,
            final_pnl=equity - initial_capital,
            final_pnl_pct=(equity - initial_capital) / initial_capital * 100,
            execution_time_ms=execution_time * 1000,
            engine_used=self.name,
        )

    def _generate_signals_from_config(self, config: Any, df: pd.DataFrame) -> np.ndarray:
        """Generate trading signals based on strategy from BacktestConfig.

        Returns:
            np.ndarray: Signal array where:
                - 1 = long entry
                - -1 = short entry
                - 0 = no signal
        """
        signals = np.zeros(len(df))

        strategy_type = getattr(config, "strategy_type", "rsi")
        strategy_params = getattr(config, "strategy_params", {}) or {}

        # Try to use registered strategy
        try:
            from backend.backtesting.strategies import SignalResult, get_strategy

            strategy = get_strategy(strategy_type, strategy_params)
            result = strategy.generate_signals(df)

            # Handle SignalResult object
            if isinstance(result, SignalResult):
                # Convert SignalResult to signal array
                # 1 for long entry, -1 for short entry, 0 for no signal
                for i in range(len(df)):
                    if result.entries.iloc[i]:
                        signals[i] = 1
                    elif result.short_entries.iloc[i]:
                        signals[i] = -1
                return signals
            elif isinstance(result, np.ndarray):
                return result
            else:
                # Fallback - try to use as-is
                return np.asarray(result)
        except Exception as e:
            logger.debug("Universal engine signal conversion failed, using fallback: %s", e)

        # Fallback to built-in RSI
        if strategy_type == "rsi":
            signals = self._generate_rsi_signals(df, strategy_params)

        return signals

    def _convert_trades_to_model(self, ohlcv: pd.DataFrame) -> List:
        """Convert internal trades to BacktestModel TradeRecord format."""
        from backend.backtesting.models import TradeRecord as ModelTradeRecord

        model_trades = []
        for i, trade in enumerate(self.trades):
            # Get timestamps from bar indices
            entry_time = ohlcv.index[min(trade.entry_bar_idx, len(ohlcv) - 1)]
            exit_time = ohlcv.index[min(trade.exit_bar_idx, len(ohlcv) - 1)]

            model_trades.append(
                ModelTradeRecord(
                    id=f"dca_{i + 1}",
                    entry_time=entry_time,
                    exit_time=exit_time,
                    side=trade.direction.value if hasattr(trade.direction, "value") else str(trade.direction),
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    size=trade.position_size,
                    pnl=trade.pnl,
                    pnl_pct=trade.pnl_pct,
                    commission=trade.commission,
                    mfe=trade.mfe,
                    mae=trade.mae,
                    mfe_pct=trade.mfe_pct,
                    mae_pct=trade.mae_pct,
                    bars_in_trade=trade.bars_held,
                    trade_number=i + 1,
                    entry_bar_index=trade.entry_bar_idx,
                    exit_bar_index=trade.exit_bar_idx,
                    exit_comment=trade.exit_reason.value if hasattr(trade.exit_reason, "value") else "close",
                )
            )

        return model_trades

    def _build_performance_metrics(self, initial_capital: float, final_equity: float, trades: List) -> Any:
        """Build PerformanceMetrics from trades."""
        from backend.backtesting.models import PerformanceMetrics

        total_trades = len(trades)
        if total_trades == 0:
            return PerformanceMetrics()

        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]

        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))

        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

        net_profit = final_equity - initial_capital
        net_profit_pct = net_profit / initial_capital * 100

        # Calculate max drawdown from equity curve
        max_dd = 0.0
        peak = initial_capital
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            net_profit=net_profit,
            net_profit_pct=net_profit_pct,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            max_drawdown=max_dd,
            avg_trade_pnl=net_profit / total_trades if total_trades > 0 else 0,
            avg_winning_trade=gross_profit / len(winning_trades) if winning_trades else 0,
            avg_losing_trade=gross_loss / len(losing_trades) if losing_trades else 0,
        )

    def _generate_signals(self, input_data: BacktestInput, df: pd.DataFrame) -> np.ndarray:
        """Generate trading signals based on strategy."""
        signals = np.zeros(len(df))

        # Use strategy signals if provided
        if hasattr(input_data, "signals") and input_data.signals is not None:
            return input_data.signals

        # Default: Simple RSI strategy for demonstration
        params = input_data.strategy_params or {}
        strategy_type = params.get("strategy_type", "rsi")

        if strategy_type == "rsi":
            signals = self._generate_rsi_signals(df, params)

        return signals

    def _generate_rsi_signals(self, df: pd.DataFrame, params: Dict) -> np.ndarray:
        """Generate RSI-based signals."""
        signals = np.zeros(len(df))

        period = params.get("period", 14)
        overbought = params.get("overbought", 70)
        oversold = params.get("oversold", 30)

        close = df["close"].values

        # Calculate RSI
        delta = np.diff(close, prepend=close[0])
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)

        # Use EMA for smoothing
        alpha = 1.0 / period
        avg_gain = np.zeros(len(close))
        avg_loss = np.zeros(len(close))

        avg_gain[period] = np.mean(gain[1 : period + 1])
        avg_loss[period] = np.mean(loss[1 : period + 1])

        for i in range(period + 1, len(close)):
            avg_gain[i] = alpha * gain[i] + (1 - alpha) * avg_gain[i - 1]
            avg_loss[i] = alpha * loss[i] + (1 - alpha) * avg_loss[i - 1]

        rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100)
        rsi = 100 - (100 / (1 + rs))

        # Generate signals
        for i in range(period + 1, len(df)):
            if rsi[i - 1] < oversold and rsi[i] >= oversold:
                signals[i] = 1  # Long signal
            elif rsi[i - 1] > overbought and rsi[i] <= overbought:
                signals[i] = -1  # Short signal

        return signals

    def _open_dca_position(self, bar_index: int, price: float, direction: str) -> None:
        """Open a new DCA position with grid orders."""
        # Calculate grid orders
        orders = DCAGridCalculator.calculate_grid_orders(self.grid_config, price, direction)

        # Fill the first order immediately
        orders[0].filled = True
        orders[0].fill_time = bar_index
        orders[0].fill_price = price

        # Initialize position
        self.position = DCAPosition(
            direction=direction,
            is_open=True,
            orders=orders,
            active_orders_count=1,
            total_size_coins=orders[0].size_coins,
            total_cost_usd=orders[0].size_usd,
            average_entry_price=price,
            entry_bar=bar_index,
            last_order_bar=bar_index,
        )

        self.total_orders_filled += 1

    def _process_open_position(self, bar_index: int, high: float, low: float, close: float, equity: float) -> float:
        """Process open position: check for DCA fills, TPs, SL."""

        # Check for new DCA order fills
        for order in self.position.orders:
            if not order.filled:
                if self._should_fill_order(order, high, low):
                    self._fill_dca_order(order, bar_index)

        # Update position state
        self._update_position_state(close)

        # Check safety close (drawdown)
        if self._should_safety_close():
            return self._close_position(bar_index, close, ExitReason.STOP_LOSS)

        # Check Close Conditions (Session 5.5)
        close_reason = self._check_close_conditions(bar_index, close)
        if close_reason is not None:
            return self._close_position(bar_index, close, close_reason)

        # Check Take Profits
        if self.multi_tp.enabled:
            result = self._check_multi_tp(bar_index, high, low, close)
            if result is not None:
                equity = result
        else:
            # Single TP check
            if self._check_single_tp(high, low):
                return self._close_position(bar_index, close, ExitReason.TAKE_PROFIT)

        # Update equity with unrealized PnL
        return equity + self.position.unrealized_pnl

    def _should_fill_order(self, order: DCAOrder, high: float, low: float) -> bool:
        """Check if a DCA order should be filled."""
        if self.position.direction == "long":
            return low <= order.price
        else:
            return high >= order.price

    def _fill_dca_order(self, order: DCAOrder, bar_index: int) -> None:
        """Fill a DCA order and update position."""
        order.filled = True
        order.fill_time = bar_index
        order.fill_price = order.price

        # Update position
        old_cost = self.position.total_cost_usd
        old_coins = self.position.total_size_coins

        self.position.total_cost_usd += order.size_usd
        self.position.total_size_coins += order.size_coins
        self.position.active_orders_count += 1
        self.position.last_order_bar = bar_index

        # Recalculate average entry
        if self.position.total_size_coins > 0:
            self.position.average_entry_price = self.position.total_cost_usd / self.position.total_size_coins

        self.total_orders_filled += 1

    def _update_position_state(self, current_price: float) -> None:
        """Update position PnL and statistics."""
        if not self.position.is_open:
            return

        # Calculate unrealized PnL
        if self.position.direction == "long":
            price_diff = current_price - self.position.average_entry_price
        else:
            price_diff = self.position.average_entry_price - current_price

        self.position.unrealized_pnl = price_diff * self.position.total_size_coins

        if self.position.total_cost_usd > 0:
            self.position.unrealized_pnl_percent = self.position.unrealized_pnl / self.position.total_cost_usd * 100

        # Update MFE/MAE
        if self.position.unrealized_pnl > self.position.max_favorable_excursion:
            self.position.max_favorable_excursion = self.position.unrealized_pnl
        if self.position.unrealized_pnl < -self.position.max_adverse_excursion:
            self.position.max_adverse_excursion = abs(self.position.unrealized_pnl)

    def _should_safety_close(self) -> bool:
        """Check if we should close due to drawdown."""
        if not self.grid_config.close_on_drawdown:
            return False

        drawdown = -self.position.unrealized_pnl

        # Check percentage threshold
        if self.grid_config.drawdown_threshold_percent > 0:
            drawdown_percent = drawdown / self.position.total_cost_usd * 100
            if drawdown_percent >= self.grid_config.drawdown_threshold_percent:
                return True

        # Check absolute threshold
        if self.grid_config.drawdown_threshold_amount > 0:
            if drawdown >= self.grid_config.drawdown_threshold_amount:
                return True

        return False

    def _check_single_tp(self, high: float, low: float) -> bool:
        """Check single take profit (default 2%)."""
        tp_percent = 0.02  # 2% default

        if self.position.direction == "long":
            tp_price = self.position.average_entry_price * (1 + tp_percent)
            return high >= tp_price
        else:
            tp_price = self.position.average_entry_price * (1 - tp_percent)
            return low <= tp_price

    def _check_multi_tp(self, bar_index: int, high: float, low: float, close: float) -> Optional[float]:
        """Check multi-level take profits and execute partial closes."""
        # Not implemented yet - placeholder
        return None

    # =========================================================================
    # CLOSE CONDITIONS (Session 5.5)
    # =========================================================================

    def _check_close_conditions(self, bar_index: int, close: float) -> Optional[ExitReason]:
        """
        Check all enabled close conditions.

        Returns ExitReason if any condition triggers, None otherwise.
        """
        cc = self.close_conditions

        # Check profit filter
        profit_percent = self.position.unrealized_pnl_percent

        # Time/Bars Close
        if cc.time_bars_close_enable:
            bars_in_trade = bar_index - self.position.entry_bar
            if bars_in_trade >= cc.close_after_bars:
                if not cc.close_only_profit or profit_percent >= cc.close_min_profit:
                    return ExitReason.TIME_EXIT
            # Force close at max bars
            if bars_in_trade >= cc.close_max_bars:
                return ExitReason.TIME_EXIT

        # RSI Close
        if cc.rsi_close_enable and self._rsi_cache is not None:
            if self._check_rsi_close(bar_index, profit_percent):
                return ExitReason.SIGNAL_EXIT

        # Stochastic Close
        if cc.stoch_close_enable and self._stoch_k_cache is not None:
            if self._check_stoch_close(bar_index, profit_percent):
                return ExitReason.SIGNAL_EXIT

        # Channel Close
        if cc.channel_close_enable:
            if self._check_channel_close(bar_index, close, profit_percent):
                return ExitReason.SIGNAL_EXIT

        # MA Close
        if cc.ma_close_enable and self._ma1_cache is not None and self._ma2_cache is not None:
            if self._check_ma_close(bar_index, profit_percent):
                return ExitReason.SIGNAL_EXIT

        # PSAR Close
        if cc.psar_close_enable and self._psar_cache is not None:
            if self._check_psar_close(bar_index, close, profit_percent):
                return ExitReason.SIGNAL_EXIT

        return None

    def _check_rsi_close(self, bar_index: int, profit_percent: float) -> bool:
        """Check RSI close conditions."""
        cc = self.close_conditions

        # Profit filter
        if cc.rsi_close_only_profit and profit_percent < cc.rsi_close_min_profit:
            return False

        rsi = self._rsi_cache[bar_index] if bar_index < len(self._rsi_cache) else 50
        prev_rsi = self._rsi_cache[bar_index - 1] if bar_index > 0 and bar_index - 1 < len(self._rsi_cache) else 50

        if self.position.direction == "long":
            # Reach mode
            if cc.rsi_close_reach_enable:
                if rsi > cc.rsi_close_reach_long_more or rsi < cc.rsi_close_reach_long_less:
                    return True
            # Cross mode
            if cc.rsi_close_cross_enable:
                if prev_rsi >= cc.rsi_close_cross_long_level and rsi < cc.rsi_close_cross_long_level:
                    return True
        else:  # short
            if cc.rsi_close_reach_enable:
                if rsi > cc.rsi_close_reach_short_more or rsi < cc.rsi_close_reach_short_less:
                    return True
            if cc.rsi_close_cross_enable:
                if prev_rsi <= cc.rsi_close_cross_short_level and rsi > cc.rsi_close_cross_short_level:
                    return True

        return False

    def _check_stoch_close(self, bar_index: int, profit_percent: float) -> bool:
        """Check Stochastic close conditions."""
        cc = self.close_conditions

        if cc.stoch_close_only_profit and profit_percent < cc.stoch_close_min_profit:
            return False

        stoch_k = self._stoch_k_cache[bar_index] if bar_index < len(self._stoch_k_cache) else 50

        if self.position.direction == "long":
            if cc.stoch_close_reach_enable and stoch_k > cc.stoch_close_reach_long_more:
                return True
        else:
            if cc.stoch_close_reach_enable and stoch_k < cc.stoch_close_reach_short_less:
                return True

        return False

    def _check_channel_close(self, bar_index: int, close: float, profit_percent: float) -> bool:
        """Check Keltner/Bollinger channel close conditions."""
        cc = self.close_conditions

        if cc.channel_close_type == "Keltner":
            upper = self._keltner_upper_cache[bar_index] if self._keltner_upper_cache is not None and bar_index < len(self._keltner_upper_cache) else float('inf')
            lower = self._keltner_lower_cache[bar_index] if self._keltner_lower_cache is not None and bar_index < len(self._keltner_lower_cache) else 0
        else:  # Bollinger
            upper = self._bb_upper_cache[bar_index] if self._bb_upper_cache is not None and bar_index < len(self._bb_upper_cache) else float('inf')
            lower = self._bb_lower_cache[bar_index] if self._bb_lower_cache is not None and bar_index < len(self._bb_lower_cache) else 0

        if cc.channel_close_band == "Breakout":
            if self.position.direction == "long":
                return close >= upper
            else:
                return close <= lower
        else:  # Rebound
            if self.position.direction == "long":
                return close <= lower
            else:
                return close >= upper

    def _check_ma_close(self, bar_index: int, profit_percent: float) -> bool:
        """Check Two MAs cross close conditions."""
        cc = self.close_conditions

        if cc.ma_close_only_profit and profit_percent < cc.ma_close_min_profit:
            return False

        ma1 = self._ma1_cache[bar_index] if bar_index < len(self._ma1_cache) else 0
        ma2 = self._ma2_cache[bar_index] if bar_index < len(self._ma2_cache) else 0
        prev_ma1 = self._ma1_cache[bar_index - 1] if bar_index > 0 and bar_index - 1 < len(self._ma1_cache) else 0
        prev_ma2 = self._ma2_cache[bar_index - 1] if bar_index > 0 and bar_index - 1 < len(self._ma2_cache) else 0

        if self.position.direction == "long":
            # Close long when fast MA crosses below slow MA
            if prev_ma1 >= prev_ma2 and ma1 < ma2:
                return True
        else:
            # Close short when fast MA crosses above slow MA
            if prev_ma1 <= prev_ma2 and ma1 > ma2:
                return True

        return False

    def _check_psar_close(self, bar_index: int, close: float, profit_percent: float) -> bool:
        """Check Parabolic SAR close conditions."""
        cc = self.close_conditions

        if cc.psar_close_only_profit and profit_percent < cc.psar_close_min_profit:
            return False

        psar = self._psar_cache[bar_index] if bar_index < len(self._psar_cache) else 0

        if self.position.direction == "long":
            # Close long when price crosses below PSAR
            return close < psar
        else:
            # Close short when price crosses above PSAR
            return close > psar

    def _precompute_close_condition_indicators(self, df: pd.DataFrame) -> None:
        """Pre-compute all indicators needed for close conditions."""
        cc = self.close_conditions
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        # RSI
        if cc.rsi_close_enable:
            self._rsi_cache = self._calculate_rsi(close, cc.rsi_close_length)

        # Stochastic
        if cc.stoch_close_enable:
            self._stoch_k_cache, self._stoch_d_cache = self._calculate_stochastic(
                high, low, close, cc.stoch_close_k_length, cc.stoch_close_k_smooth, cc.stoch_close_d_smooth
            )

        # Moving Averages
        if cc.ma_close_enable:
            self._ma1_cache = self._calculate_ma(close, cc.ma_close_ma1_length, cc.ma_close_ma1_type)
            self._ma2_cache = self._calculate_ma(close, cc.ma_close_ma2_length, cc.ma_close_ma2_type)

        # Channels
        if cc.channel_close_enable:
            if cc.channel_close_type == "Keltner":
                self._keltner_upper_cache, self._keltner_lower_cache = self._calculate_keltner(
                    high, low, close, cc.channel_close_keltner_length, cc.channel_close_keltner_mult
                )
            else:
                self._bb_upper_cache, self._bb_lower_cache = self._calculate_bollinger(
                    close, cc.channel_close_bb_length, cc.channel_close_bb_deviation
                )

        # PSAR
        if cc.psar_close_enable:
            self._psar_cache = self._calculate_psar(high, low, cc.psar_close_start, cc.psar_close_increment, cc.psar_close_maximum)

    def _calculate_rsi(self, close: np.ndarray, period: int) -> np.ndarray:
        """Calculate RSI indicator."""
        delta = np.diff(close, prepend=close[0])
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)

        avg_gain = np.zeros_like(close)
        avg_loss = np.zeros_like(close)

        # Initial SMA
        if len(close) > period:
            avg_gain[period] = np.mean(gains[1:period + 1])
            avg_loss[period] = np.mean(losses[1:period + 1])

            # EMA-style smoothing
            for i in range(period + 1, len(close)):
                avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
                avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_stochastic(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                               k_period: int, k_smooth: int, d_smooth: int) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate Stochastic %K and %D."""
        stoch_k = np.zeros_like(close)
        for i in range(k_period - 1, len(close)):
            highest_high = np.max(high[i - k_period + 1:i + 1])
            lowest_low = np.min(low[i - k_period + 1:i + 1])
            if highest_high != lowest_low:
                stoch_k[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)
            else:
                stoch_k[i] = 50

        # Smooth %K
        if k_smooth > 1:
            stoch_k = self._sma(stoch_k, k_smooth)

        # %D is SMA of %K
        stoch_d = self._sma(stoch_k, d_smooth)

        return stoch_k, stoch_d

    def _calculate_ma(self, data: np.ndarray, period: int, ma_type: str) -> np.ndarray:
        """Calculate moving average of specified type."""
        if ma_type == "SMA":
            return self._sma(data, period)
        elif ma_type == "EMA":
            return self._ema(data, period)
        elif ma_type == "WMA":
            return self._wma(data, period)
        else:
            return self._ema(data, period)  # Default to EMA

    def _calculate_keltner(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                           period: int, mult: float) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate Keltner Channel."""
        basis = self._ema(close, period)
        tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
        atr = self._ema(tr, period)
        upper = basis + mult * atr
        lower = basis - mult * atr
        return upper, lower

    def _calculate_bollinger(self, close: np.ndarray, period: int, deviation: float) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate Bollinger Bands."""
        basis = self._sma(close, period)
        std = np.zeros_like(close)
        for i in range(period - 1, len(close)):
            std[i] = np.std(close[i - period + 1:i + 1])
        upper = basis + deviation * std
        lower = basis - deviation * std
        return upper, lower

    def _calculate_psar(self, high: np.ndarray, low: np.ndarray, start: float, increment: float, maximum: float) -> np.ndarray:
        """Calculate Parabolic SAR."""
        length = len(high)
        psar = np.zeros(length)
        af = start
        ep = low[0]
        is_long = True
        psar[0] = high[0]

        for i in range(1, length):
            if is_long:
                psar[i] = psar[i - 1] + af * (ep - psar[i - 1])
                psar[i] = min(psar[i], low[i - 1])
                if i > 1:
                    psar[i] = min(psar[i], low[i - 2])

                if low[i] < psar[i]:
                    is_long = False
                    psar[i] = ep
                    ep = low[i]
                    af = start
                else:
                    if high[i] > ep:
                        ep = high[i]
                        af = min(af + increment, maximum)
            else:
                psar[i] = psar[i - 1] + af * (ep - psar[i - 1])
                psar[i] = max(psar[i], high[i - 1])
                if i > 1:
                    psar[i] = max(psar[i], high[i - 2])

                if high[i] > psar[i]:
                    is_long = True
                    psar[i] = ep
                    ep = high[i]
                    af = start
                else:
                    if low[i] < ep:
                        ep = low[i]
                        af = min(af + increment, maximum)

        return psar

    def _sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average."""
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            result[i] = np.mean(data[i - period + 1:i + 1])
        return result

    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average."""
        result = np.zeros_like(data)
        multiplier = 2 / (period + 1)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
        return result

    def _wma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Weighted Moving Average."""
        result = np.zeros_like(data)
        weights = np.arange(1, period + 1)
        weight_sum = weights.sum()
        for i in range(period - 1, len(data)):
            result[i] = np.sum(data[i - period + 1:i + 1] * weights) / weight_sum
        return result

    # =========================================================================
    # INDENT ORDER (Session 5.5)
    # =========================================================================

    def _create_indent_order(self, bar_index: int, price: float, direction: str) -> None:
        """
        Create a pending indent (limit) order.
        
        Args:
            bar_index: Current bar index
            price: Current price (signal price)
            direction: "long" or "short"
        """
        indent_pct = self.indent_order.indent_percent / 100
        
        if direction == "long":
            # For long: indent below current price
            entry_price = price * (1 - indent_pct)
        else:
            # For short: indent above current price
            entry_price = price * (1 + indent_pct)
        
        self.pending_indent = PendingIndentOrder(
            direction=direction,
            signal_bar=bar_index,
            signal_price=price,
            entry_price=entry_price,
            expires_bar=bar_index + self.indent_order.cancel_after_bars,
            filled=False
        )

    def _check_indent_order_fill(self, bar_index: int, high: float, low: float, 
                                  close: float, equity: float) -> float:
        """
        Check if pending indent order should be filled or cancelled.
        
        Returns updated equity.
        """
        if self.pending_indent is None:
            return equity
        
        indent = self.pending_indent
        
        # Check expiration
        if bar_index >= indent.expires_bar:
            self.pending_indent = None
            return equity
        
        # Check fill
        filled = False
        if indent.direction == "long":
            # Long indent fills when low reaches entry price
            if low <= indent.entry_price:
                filled = True
        else:
            # Short indent fills when high reaches entry price
            if high >= indent.entry_price:
                filled = True
        
        if filled:
            indent.filled = True
            self._open_dca_position(bar_index, indent.entry_price, indent.direction)
            self.pending_indent = None
        
        return equity

    def _close_position(self, bar_index: int, close_price: float, reason: ExitReason) -> float:
        """Close position and record trade."""
        if not self.position.is_open:
            return 0.0

        # Calculate final PnL
        if self.position.direction == "long":
            pnl = (close_price - self.position.average_entry_price) * self.position.total_size_coins
        else:
            pnl = (self.position.average_entry_price - close_price) * self.position.total_size_coins

        # Record trade
        trade = TradeRecord(
            entry_time=self.position.entry_bar,
            exit_time=bar_index,
            entry_price=self.position.average_entry_price,
            exit_price=close_price,
            direction=TradeDirection.LONG if self.position.direction == "long" else TradeDirection.SHORT,
            position_size=self.position.total_size_coins,
            pnl=pnl,
            pnl_percent=(pnl / self.position.total_cost_usd * 100) if self.position.total_cost_usd > 0 else 0,
            exit_reason=reason,
            mfe=self.position.max_favorable_excursion,
            mae=self.position.max_adverse_excursion,
        )
        self.trades.append(trade)

        # Reset position
        equity_after = self.position.total_cost_usd + pnl
        self.position = DCAPosition()

        return equity_after

    def _calculate_metrics(self, initial_capital: float, final_equity: float) -> BacktestMetrics:
        """Calculate backtest performance metrics."""
        if not self.trades:
            return BacktestMetrics(
                total_trades=0,
                win_rate=0.0,
                profit_factor=1.0,
                total_return=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                avg_trade_pnl=0.0,
                avg_trade_pnl_percent=0.0,
            )

        # Calculate basic metrics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0

        total_return = (final_equity - initial_capital) / initial_capital * 100

        # Calculate drawdown from equity curve
        equity_array = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdowns = (running_max - equity_array) / running_max
        max_drawdown = np.max(drawdowns) * 100

        # Simple Sharpe approximation
        if len(self.equity_curve) > 1:
            returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
            if len(returns) > 0 and np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        avg_pnl = np.mean([t.pnl for t in self.trades])
        avg_pnl_pct = np.mean([t.pnl_percent for t in self.trades])

        return BacktestMetrics(
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            avg_trade_pnl=avg_pnl,
            avg_trade_pnl_percent=avg_pnl_pct,
        )

    def _empty_result(self, reason: str) -> BacktestOutput:
        """Return empty result with error message."""
        return BacktestOutput(
            trades=[],
            metrics=BacktestMetrics(
                total_trades=0,
                win_rate=0.0,
                profit_factor=1.0,
                total_return=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                avg_trade_pnl=0.0,
                avg_trade_pnl_percent=0.0,
            ),
            equity_curve=[],
            execution_time_ms=0,
            engine_used=self.name,
            parameters_used={},
            error=reason,
        )
