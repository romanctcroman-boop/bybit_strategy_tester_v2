"""
Backtesting Models

Pydantic schemas for backtest configuration, results, and metrics.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrategyType(str, Enum):
    """Available strategy types"""

    SMA_CROSSOVER = "sma_crossover"
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER_BANDS = "bollinger_bands"
    # Pyramiding strategies
    GRID = "grid"
    DCA = "dca"
    MARTINGALE = "martingale"
    # Custom
    CUSTOM = "custom"
    ADVANCED = "advanced"


class OrderSide(str, Enum):
    """Order side"""

    BUY = "buy"
    SELL = "sell"


class BacktestStatus(str, Enum):
    """Backtest execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EngineType(str, Enum):
    """Backtest engine type selector

    All engines produce 100% identical results (bit-level parity).
    - AUTO: Automatically select best available (GPU > Numba > Fallback)
    - FALLBACK: FallbackEngineV2 - Pure Python, reference implementation
    - NUMBA: NumbaEngineV2 - JIT-compiled, faster
    - GPU: GPUEngineV2 - CUDA-accelerated, fastest on NVIDIA GPUs
    """

    AUTO = "auto"
    FALLBACK = "fallback"
    NUMBA = "numba"
    GPU = "gpu"


class BacktestConfig(BaseModel):
    """Configuration for a backtest run

    DeepSeek рекомендация: добавлена расширенная валидация параметров
    для предотвращения некорректных значений (position_size=1000, leverage=1000 и т.д.)
    """

    model_config = ConfigDict(use_enum_values=True)

    # Required fields
    symbol: str = Field(..., min_length=3, max_length=20, description="Trading symbol (e.g., BTCUSDT)")
    interval: str = Field(..., description="Candle interval (e.g., 1h, 4h, 1d)")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")

    # Strategy configuration
    strategy_type: StrategyType = Field(default=StrategyType.SMA_CROSSOVER)
    strategy_params: dict[str, Any] = Field(default_factory=dict)

    # Capital and risk settings
    initial_capital: float = Field(
        default=10000.0,
        ge=100,
        le=100_000_000,
        description="Initial capital (100 - 100M)",
    )
    position_size: float = Field(
        default=1.0,
        ge=0.01,
        le=1.0,
        description="Fraction of capital per trade (0.01-1.0)",
    )
    leverage: float = Field(default=1.0, ge=1.0, le=125.0, description="Leverage (1-125x, Bybit max)")

    # Trading direction: 'long', 'short', or 'both'
    direction: str = Field(
        default="both",
        description="Trading direction: 'long' (only longs), 'short' (only shorts), 'both'",
    )

    # Market type: 'spot' or 'linear' (perpetual futures)
    # SPOT = matches TradingView data exactly (for signal parity)
    # LINEAR = perpetual futures data (for live trading execution)
    market_type: str = Field(
        default="linear",
        description="Market data source: 'spot' (TradingView parity) or 'linear' (perpetual futures)",
    )

    # Days to block (0=Mon … 6=Sun). No new entries on these weekdays.
    no_trade_days: tuple[int, ...] = Field(
        default_factory=tuple,
        description="Weekdays to block (0=Mon, 6=Sun). Unchecked in UI = trade that day.",
    )

    # Pyramiding - max concurrent positions (TradingView: 0-99)
    # 0 or 1 = disabled (single position)
    # 2-99 = max entries in same direction
    pyramiding: int = Field(
        default=1,
        ge=0,
        le=99,
        description="Maximum number of concurrent entries in same direction (0-99, TV compatible)",
    )

    # ===== NEW: TradingView Pyramiding Mode =====
    # When True, opens ALL pyramiding positions immediately on reversal signal
    # (e.g. pyramiding=3 → opens 3 positions at once on each signal)
    # This matches TradingView behavior where it opens multiple positions on reversal
    tv_pyramiding_mode: bool = Field(
        default=False,
        description="TradingView pyramiding mode: open all pyramiding positions at once on reversal",
    )

    # ===== NEW: Risk-Free Rate (TradingView compatible) =====
    # Used for Sharpe/Sortino ratio calculation
    # TradingView default: 2% annual = 0.1667% monthly
    risk_free_rate: float = Field(
        default=0.02,
        ge=0.0,
        le=0.20,
        description="Annual risk-free rate for Sharpe/Sortino calculation (default: 2%)",
    )

    # Fees and slippage
    maker_fee: float = Field(default=0.0002, ge=0, le=0.01)  # 0.02% default
    taker_fee: float = Field(default=0.0004, ge=0, le=0.01)  # 0.04% default
    slippage: float = Field(default=0.0005, ge=0, le=0.05)  # max 5% slippage
    slippage_ticks: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Slippage in ticks (TradingView: adds to market/stop orders fill price)",
    )

    # Risk management
    stop_loss: Optional[float] = Field(default=None, ge=0.001, le=0.5, description="Stop loss percentage (0.1% - 50%)")
    take_profit: Optional[float] = Field(
        default=None,
        ge=0.001,
        le=1.0,
        description="Take profit percentage (0.1% - 100%)",
    )
    max_drawdown: Optional[float] = Field(default=None, ge=0.01, le=1.0, description="Max drawdown limit (1% - 100%)")

    # Trailing Stop (TradingView compatible)
    # trail_points: активация трейлинга когда прибыль достигает этого значения (в % от цены)
    # trail_offset: отступ от максимальной прибыли для стоп-лосса (в % от цены)
    trailing_stop_activation: Optional[float] = Field(
        default=None,
        ge=0.001,
        le=0.5,
        description="Trailing stop activation threshold (% from entry, like TradingView trail_points)",
    )
    trailing_stop_offset: Optional[float] = Field(
        default=None,
        ge=0.001,
        le=0.2,
        description="Trailing stop offset from peak (% from price, like TradingView trail_offset)",
    )

    # Partial exit (TradingView qty_percent)
    partial_exit_percent: Optional[float] = Field(
        default=None,
        ge=0.1,
        le=0.99,
        description="Partial exit percentage at TP (0.1 = 10% of position)",
    )

    # Limit/Stop entry orders (TradingView strategy.entry limit/stop)
    entry_limit_offset: Optional[float] = Field(
        default=None,
        ge=0.001,
        le=0.1,
        description="Limit order offset from signal price (% below for long, above for short)",
    )
    entry_stop_offset: Optional[float] = Field(
        default=None,
        ge=0.001,
        le=0.1,
        description="Stop order offset from signal price (% above for long, below for short)",
    )

    # ===== NEW: SL/TP Execution Settings (TradingView compatible) =====
    sl_priority: bool = Field(
        default=True,
        description="SL takes priority over TP when both triggered on same bar (default: True)",
    )
    trigger_on_entry_bar: bool = Field(
        default=False,
        description="Allow SL/TP to trigger on entry bar (TradingView default: False)",
    )

    # ===== NEW: Pyramiding Close Rule (TradingView compatible) =====
    close_rule: str = Field(
        default="ALL",
        description="How to close positions: 'FIFO' (first in first out), 'LIFO' (last in first out), 'ALL' (close all)",
    )

    # ===== NEW: Gap Handling (TradingView compatible) =====
    fill_orders_on_gap: bool = Field(
        default=True,
        description="Fill limit/stop orders on gap open (default: True)",
    )
    gap_slippage_mode: str = Field(
        default="open_price",
        description="Gap fill mode: 'open_price' (fill at open), 'order_price' (fill at order level if valid)",
    )

    # ===== NEW: OCA Groups (TradingView compatible) =====
    # OCA = One-Cancels-All
    oca_enabled: bool = Field(
        default=False,
        description="Enable OCA (One-Cancels-All) order groups",
    )
    oca_type: str = Field(
        default="none",
        description="OCA type: 'none', 'cancel' (cancel remaining orders), 'reduce' (reduce order sizes)",
    )

    # ===== NEW: Margin Settings (TradingView compatible) =====
    # margin_long / margin_short = % of position value that must be funded
    margin_long: float = Field(
        default=100.0,
        ge=1.0,
        le=100.0,
        description="Margin requirement for long positions (%, 100 = no margin)",
    )
    margin_short: float = Field(
        default=100.0,
        ge=1.0,
        le=100.0,
        description="Margin requirement for short positions (%, 100 = no margin)",
    )

    # ===== NEW: Trailing Stop Enhanced (TradingView compatible) =====
    # trail_price: absolute price at which trailing activates
    trail_price: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Trailing stop activation price (absolute value)",
    )
    # trail_points: ticks from entry for activation
    trail_points: Optional[int] = Field(
        default=None,
        ge=0,
        description="Trailing stop activation in ticks from entry",
    )
    # trail_offset: offset from peak in ticks
    trail_offset: Optional[int] = Field(
        default=None,
        ge=0,
        description="Trailing stop offset from peak (in ticks)",
    )

    # ===== NEW: Commission Types (TradingView compatible) =====
    commission_type: str = Field(
        default="percent",
        description="Commission type: 'percent', 'cash_per_contract', 'cash_per_order'",
    )
    commission_value: float = Field(
        default=0.0007,
        ge=0.0,
        description="Commission value (0.0007 = 0.07% for TradingView parity)",
    )

    # ===== NEW: Commission Calculation Base (TradingView) =====
    # TradingView calculates commission on margin, NOT on leveraged position value
    # This causes huge difference in results when leverage > 1
    # DEFAULT: True for TradingView-compatible results
    commission_on_margin: bool = Field(
        default=True,
        description="Calculate commission on margin only (TradingView style). "
        "If False, commission is calculated on full position value (realistic).",
    )

    # ===== NEW: Fill Orders on Standard OHLC (TradingView) =====
    # For Heikin Ashi charts - use real OHLC for fills
    fill_orders_on_standard_ohlc: bool = Field(
        default=False,
        description="Use standard OHLC prices for order fills on non-standard charts",
    )

    # ===== NEW: Backtest Fill Limits Assumption (TradingView) =====
    # Limit orders only fill if price exceeds limit by N ticks
    backtest_fill_limits_assumption: int = Field(
        default=0,
        ge=0,
        description="Ticks beyond limit price required for fill (0 = fill at limit)",
    )

    # ===== NEW: Bar Magnifier (TradingView Premium) =====
    # Uses lower timeframe data for precise intrabar order execution
    use_bar_magnifier: bool = Field(
        default=True,  # Enabled by default for precise SL/TP detection
        description="Use lower timeframe data for precise order fills (TradingView Premium)",
    )
    bar_magnifier_timeframe: Optional[str] = Field(
        default=None,
        description="Lower timeframe for bar magnifier (e.g., '1m' for 15m chart). Auto-selected if None.",
    )
    bar_magnifier_max_bars: int = Field(
        default=200000,
        ge=1000,
        le=500000,
        description="Maximum number of lower TF bars to use (TradingView limit: 200000)",
    )

    # ===== NEW: Intrabar OHLC Path Model =====
    # Path for generating pseudo-ticks from 1m bars
    intrabar_ohlc_path: str = Field(
        default="O-HL-heuristic",
        description=(
            "OHLC path model for intrabar simulation: "
            "'O-H-L-C' (conservative for short), "
            "'O-L-H-C' (conservative for long), "
            "'O-HL-heuristic' (TradingView-style, default), "
            "'conservative_long', 'conservative_short'"
        ),
    )
    intrabar_subticks: int = Field(
        default=1,  # 1 subtick = 7 points per 1m bar, good balance of accuracy and speed
        ge=0,
        le=10,
        description="Number of interpolated subticks between OHLC points (0 = only 4 points per 1m bar)",
    )

    # ===== NEW: Execution Modes (TradingView calc_on_every_tick) =====
    # Controls when strategy calculations occur
    execution_mode: str = Field(
        default="on_bar_close",
        description="Execution mode: 'on_bar_close' (default), 'on_each_tick' (realtime), 'on_order_fills' (after fills)",
    )
    calc_on_every_tick: bool = Field(
        default=False,
        description="Calculate strategy on every tick (real-time mode). More CPU intensive.",
    )
    process_orders_on_close: bool = Field(
        default=True,
        description="Process orders on bar close (default). False = process immediately.",
    )

    # ===== NEW: Start With Position (TradingView compatible) =====
    # TradingView behavior: if indicator state already signals a position at test start,
    # TV opens that position immediately. Our default is to wait for crossover.
    start_with_position: bool = Field(
        default=False,
        description="Open position immediately at test start if strategy signal is active "
        "(TradingView behavior). If False, wait for first crossover signal (default).",
    )

    # ===== NEW: Skip Initial Short (TradingView MACD compatibility) =====
    # TradingView MACD Strategy behavior: if the first signal in the date range is SHORT,
    # skip it and wait for the first LONG signal. This matches TV's behavior where
    # it doesn't open a short if there's no existing long position to close.
    skip_initial_short: bool = Field(
        default=False,
        description="Skip SHORT signals until the first LONG signal is received. "
        "This matches TradingView MACD Strategy behavior where shorts only close longs.",
    )

    # ===== NEW: Quick Reversal Tracking (TradingView compatibility) =====
    # TradingView counts quick reversals (position change within N bars) as separate trades
    # This affects trade count and win rate statistics
    count_quick_reversals: bool = Field(
        default=False,
        description="Count quick reversals (direction change within quick_reversal_bars) as separate trades. "
        "When True, matches TradingView trade counting logic.",
    )
    quick_reversal_bars: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Number of bars threshold for quick reversal detection. "
        "If position reverses within this many bars, it counts as 2 trades (close + open).",
    )

    # ===== NEW: Margin Call Settings (TradingView margin call simulation) =====
    # Simulates liquidation when margin requirements are not met
    margin_call_enabled: bool = Field(
        default=False,
        description="Enable margin call simulation (liquidation)",
    )
    margin_call_threshold: float = Field(
        default=100.0,
        ge=50.0,
        le=200.0,
        description="Margin call threshold % (100 = liquidation when margin used equals available)",
    )
    maintenance_margin: float = Field(
        default=50.0,
        ge=10.0,
        le=100.0,
        description="Maintenance margin % (below this = liquidation)",
    )

    # ===== DCA GRID SETTINGS (TradingView Multi DCA Strategy compatible) =====
    # Dollar-Cost Averaging Grid/Martingale strategy configuration
    dca_enabled: bool = Field(
        default=False,
        description="Enable DCA Grid/Martingale mode. When enabled, uses DCAEngine instead of standard engine.",
    )
    dca_direction: str = Field(
        default="both",
        description="DCA trading direction: 'long', 'short', or 'both'. "
        "Determines which direction(s) to build DCA grids.",
    )
    dca_order_count: int = Field(
        default=5,
        ge=2,
        le=15,
        description="Number of DCA grid orders (2-15). "
        "Each order level adds to the position at progressively worse prices.",
    )
    dca_grid_size_percent: float = Field(
        default=1.0,
        ge=0.1,
        le=50.0,
        description="Grid step size as percentage between DCA levels (0.1-50%). Distance between each averaging order.",
    )
    dca_martingale_coef: float = Field(
        default=1.5,
        ge=1.0,
        le=5.0,
        description="Martingale coefficient for position sizing (1.0 = no increase). "
        "Each DCA level multiplies size by this coefficient.",
    )
    dca_martingale_mode: str = Field(
        default="multiply_each",
        description="Martingale mode: 'multiply_each' (sequential multiplication), "
        "'multiply_total' (total position multiplier), 'progressive' (Fibonacci-like progression).",
    )
    dca_log_step_enabled: bool = Field(
        default=False,
        description="Enable logarithmic step distribution instead of linear. "
        "When True, grid levels are spaced logarithmically (tighter near entry, wider far).",
    )
    dca_log_step_coef: float = Field(
        default=1.2,
        ge=1.0,
        le=3.0,
        description="Logarithmic step coefficient (1.0-3.0). Higher values create more aggressive step widening.",
    )
    dca_drawdown_threshold: float = Field(
        default=30.0,
        ge=5.0,
        le=90.0,
        description="Maximum drawdown % before triggering safety close (5-90%). "
        "When account drawdown exceeds this, all positions are closed.",
    )
    dca_safety_close_enabled: bool = Field(
        default=True,
        description="Enable safety close mechanism. Closes all positions when drawdown threshold is exceeded.",
    )

    # ===== DCA MULTI-TP SETTINGS =====
    dca_multi_tp_enabled: bool = Field(
        default=False,
        description="Enable multi-level Take Profit for DCA positions. "
        "Allows partial exits at different profit levels.",
    )
    dca_tp1_percent: float = Field(
        default=0.5,
        ge=0.0,
        le=100.0,
        description="Take Profit level 1 - percentage from average entry price.",
    )
    dca_tp1_close_percent: float = Field(
        default=25.0,
        ge=0.0,
        le=100.0,
        description="TP1 - percentage of position to close (0-100%).",
    )
    dca_tp2_percent: float = Field(
        default=1.0,
        ge=0.0,
        le=100.0,
        description="Take Profit level 2 - percentage from average entry price.",
    )
    dca_tp2_close_percent: float = Field(
        default=25.0,
        ge=0.0,
        le=100.0,
        description="TP2 - percentage of position to close (0-100%).",
    )
    dca_tp3_percent: float = Field(
        default=2.0,
        ge=0.0,
        le=100.0,
        description="Take Profit level 3 - percentage from average entry price.",
    )
    dca_tp3_close_percent: float = Field(
        default=25.0,
        ge=0.0,
        le=100.0,
        description="TP3 - percentage of position to close (0-100%).",
    )
    dca_tp4_percent: float = Field(
        default=3.0,
        ge=0.0,
        le=100.0,
        description="Take Profit level 4 - percentage from average entry price (final exit).",
    )
    dca_tp4_close_percent: float = Field(
        default=25.0,
        ge=0.0,
        le=100.0,
        description="TP4 - percentage of position to close (0-100%).",
    )

    # ===== ENGINE SELECTION =====
    engine_type: str = Field(
        default="auto",
        description="Backtest engine to use: 'auto' (best available), 'fallback' (FallbackEngineV2), "
        "'numba' (NumbaEngineV2), 'gpu' (GPUEngineV2 with CUDA). All engines produce 100% identical results.",
    )
    force_fallback: bool = Field(
        default=False,
        description="DEPRECATED: Use engine_type='fallback' instead. "
        "Force fallback engine for 100% consistent results.",
    )

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        """Проверка поддерживаемых таймфреймов Bybit"""
        supported = [
            "1",
            "3",
            "5",
            "15",
            "30",
            "60",
            "120",
            "240",
            "360",
            "720",
            "D",
            "W",
            "M",
            "1m",
            "3m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "12h",
            "1d",
            "1w",
        ]
        if v not in supported:
            raise ValueError(f"Unsupported interval. Use: {supported}")
        return v

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        """Проверка направления торговли"""
        allowed = ["long", "short", "both"]
        if v.lower() not in allowed:
            raise ValueError(f"Direction must be one of: {allowed}")
        return v.lower()

    @field_validator("engine_type")
    @classmethod
    def validate_engine_type(cls, v: str) -> str:
        """Validate backtest engine type"""
        allowed = ["auto", "fallback", "numba", "gpu", "dca", "dca_grid"]
        if v.lower() not in allowed:
            raise ValueError(f"Engine type must be one of: {allowed}")
        return v.lower()

    @field_validator("dca_direction")
    @classmethod
    def validate_dca_direction(cls, v: str) -> str:
        """Validate DCA trading direction"""
        allowed = ["long", "short", "both"]
        if v.lower() not in allowed:
            raise ValueError(f"DCA direction must be one of: {allowed}")
        return v.lower()

    @field_validator("dca_martingale_mode")
    @classmethod
    def validate_dca_martingale_mode(cls, v: str) -> str:
        """Validate DCA martingale mode"""
        allowed = ["multiply_each", "multiply_total", "progressive"]
        if v.lower() not in allowed:
            raise ValueError(f"DCA martingale mode must be one of: {allowed}")
        return v.lower()

    @field_validator("market_type")
    @classmethod
    def validate_market_type(cls, v: str) -> str:
        """Validate market type (spot or linear)"""
        allowed = ["spot", "linear"]
        if v.lower() not in allowed:
            raise ValueError(f"Market type must be one of: {allowed}")
        return v.lower()

    @model_validator(mode="after")
    def validate_dates(self):
        """Проверка корректности дат (DeepSeek рекомендация)"""
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")

        # Максимум 2 года для бэктеста (разумный предел)
        max_duration = timedelta(days=730)
        if self.end_date - self.start_date > max_duration:
            raise ValueError("Maximum backtest duration is 2 years")

        # Не позволяем даты далеко в будущем (более 1 дня)
        # Разрешаем сегодняшнюю дату с учётом часовых поясов
        # Учитываем timezone-aware datetime (конвертируем в naive для сравнения)
        now = datetime.now()
        end_date_naive = self.end_date.replace(tzinfo=None) if self.end_date.tzinfo else self.end_date
        # Добавляем буфер 1 день для учёта часовых поясов
        if end_date_naive > now + timedelta(days=1):
            raise ValueError("end_date cannot be more than 1 day in the future")

        return self


class TradeRecord(BaseModel):
    """Single trade record with TradingView-compatible metrics"""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default="", description="Trade ID for identification")
    entry_time: datetime
    exit_time: datetime
    side: str  # "buy", "sell", "long", "short" - flexible for various engines
    entry_price: float
    exit_price: float
    size: float = 1.0  # Position size, default 1.0
    pnl: float
    pnl_pct: float = 0.0  # Optional with default
    fees: float = 0.0  # Optional with default
    duration_hours: float = 0.0  # Optional with default

    # ===== Trade Identification (TradingView compatible) =====
    entry_id: str = Field(default="", description="Entry order ID (TradingView strategy.entry id)")
    exit_id: str = Field(default="", description="Exit order ID (TradingView strategy.exit id)")
    entry_comment: str = Field(default="", description="Entry order comment")
    exit_comment: str = Field(
        default="",
        description="Exit comment: 'TP', 'SL', 'TRAIL', or custom (comment_profit/loss/trailing)",
    )

    # ===== Commission per trade =====
    commission: float = Field(default=0.0, description="Commission paid for this trade ($)")

    # ===== NEW: Per-trade risk metrics (TradingView compatible) =====
    max_runup: float = Field(default=0.0, description="Maximum unrealized profit during trade (%)")
    max_runup_value: float = Field(default=0.0, description="Maximum unrealized profit ($)")
    max_drawdown: float = Field(default=0.0, description="Maximum unrealized loss during trade (%)")
    max_drawdown_value: float = Field(default=0.0, description="Maximum unrealized loss ($)")

    # MAE/MFE (Maximum Adverse/Favorable Excursion)
    mae: float = Field(
        default=0.0,
        description="Maximum Adverse Excursion - worst drawdown from entry ($)",
    )
    mfe: float = Field(
        default=0.0,
        description="Maximum Favorable Excursion - best runup from entry ($)",
    )
    mae_pct: float = Field(
        default=0.0,
        description="Maximum Adverse Excursion as percentage (%)",
    )
    mfe_pct: float = Field(
        default=0.0,
        description="Maximum Favorable Excursion as percentage (%)",
    )

    # Bars in trade
    bars_in_trade: int = Field(default=0, description="Number of bars position was held")

    # Trade number
    trade_number: int = Field(default=0, description="Sequential trade number")

    # ===== NEW: Entry/Exit bar indices (TradingView) =====
    entry_bar_index: int = Field(default=0, description="Bar index at entry")
    exit_bar_index: int = Field(default=0, description="Bar index at exit")

    # ===== NEW: Profit/Loss percentage (TradingView compatible) =====
    profit_percent: float = Field(default=0.0, description="Profit/loss as percentage of entry price")


class PerformanceMetrics(BaseModel):
    """
    Performance metrics for a backtest.

    TradingView-compatible metrics with proper formulas:
    - Sharpe/Sortino use MONTHLY returns (as per TradingView docs)
    - Risk-free rate defaults to 2% annual (0.1667%/month)
    - Gross Profit/Loss exclude commissions
    - Net Profit includes commissions
    """

    # ===== ДЕНЕЖНЫЕ МЕТРИКИ (Performance Block) =====
    # Net Profit = sum(P&L) - sum(Commissions)
    net_profit: float = Field(default=0.0, description="Net profit in currency (after commissions)")
    net_profit_pct: float = Field(default=0.0, description="Net profit as percentage of initial capital")

    # Gross Profit/Loss (без комиссий, как в TradingView) - DUAL FORMAT
    gross_profit: float = Field(default=0.0, description="Sum of all winning trades P&L in $ (no commissions)")
    gross_profit_pct: float = Field(default=0.0, description="Gross profit as % of initial capital")
    gross_loss: float = Field(
        default=0.0,
        description="Sum of all losing trades P&L in $ (absolute value, no commissions)",
    )
    gross_loss_pct: float = Field(default=0.0, description="Gross loss as % of initial capital (positive value)")

    # Commissions
    total_commission: float = Field(default=0.0, description="Total commission paid")

    # Buy & Hold comparison
    buy_hold_return: float = Field(default=0.0, description="Buy & Hold return in currency")
    buy_hold_return_pct: float = Field(default=0.0, description="Buy & Hold return percentage")

    # Returns (legacy compatibility)
    total_return: float = Field(default=0.0, description="Total return percentage")
    annual_return: float = Field(default=0.0, description="Annualized return percentage")

    # ===== РИСК-МЕТРИКИ (Risk/Performance Ratios) =====
    # TradingView: Sharpe = (MeanMonthlyReturn - RFR) / StdMonthlyReturn
    sharpe_ratio: float = Field(default=0.0, description="Sharpe ratio (monthly returns, RFR=2%/year)")
    sortino_ratio: float = Field(default=0.0, description="Sortino ratio (monthly returns, downside deviation)")
    calmar_ratio: float = Field(default=0.0, description="Calmar ratio (annual return / max drawdown)")
    sqn: float = Field(default=0.0, description="System Quality Number (expectancy / stdev of trades)")

    # ===== ПРОСАДКА (Drawdown) - DUAL FORMAT =====
    max_drawdown: float = Field(default=0.0, description="Maximum drawdown percentage (peak-to-trough)")
    max_drawdown_value: float = Field(default=0.0, description="Maximum drawdown in currency ($)")
    avg_drawdown: float = Field(default=0.0, description="Average drawdown percentage")
    avg_drawdown_value: float = Field(default=0.0, description="Average drawdown in currency ($)")
    max_drawdown_duration_days: float = Field(default=0.0, description="Longest drawdown duration in days")
    max_runup: float = Field(default=0.0, description="Maximum run-up percentage")
    max_runup_value: float = Field(default=0.0, description="Maximum run-up in currency ($)")
    # TradingView: "Сред. рост капитала" - Average run-up
    avg_runup: float = Field(
        default=0.0,
        description="Average run-up percentage (TradingView: Сред. рост капитала)",
    )
    avg_runup_value: float = Field(default=0.0, description="Average run-up in currency ($)")

    # ===== СТАТИСТИКА СДЕЛОК (Trades Analysis) =====
    total_trades: int = Field(default=0, description="Total number of trades")
    quick_reversals: int = Field(
        default=0,
        description="Number of quick reversals (direction change within quick_reversal_bars). "
        "TradingView counts these as separate trades, so TV-style trade count = total_trades + quick_reversals",
    )
    winning_trades: int = Field(default=0, description="Number of winning trades")
    losing_trades: int = Field(default=0, description="Number of losing trades")
    win_rate: float = Field(default=0.0, description="Percent profitable (winning/total * 100)")

    # Profit/Loss per trade - DUAL FORMAT ($ and %)
    profit_factor: float = Field(default=0.0, description="Gross profit / Gross loss")
    avg_win: float = Field(default=0.0, description="Average winning trade percentage")
    avg_win_value: float = Field(default=0.0, description="Average winning trade in currency ($)")
    avg_loss: float = Field(default=0.0, description="Average losing trade percentage")
    avg_loss_value: float = Field(default=0.0, description="Average losing trade in currency ($)")
    avg_win_loss_ratio: float = Field(default=0.0, description="Ratio avg win / avg loss")
    largest_win: float = Field(default=0.0, description="Largest winning trade percentage")
    largest_win_value: float = Field(default=0.0, description="Largest winning trade in currency ($)")
    largest_loss: float = Field(default=0.0, description="Largest losing trade percentage (negative)")
    largest_loss_value: float = Field(default=0.0, description="Largest losing trade in currency ($)")

    # Average P&L - DUAL FORMAT
    avg_trade: float = Field(default=0.0, description="Average trade P&L percentage")
    avg_trade_value: float = Field(default=0.0, description="Average trade P&L in currency ($)")

    # Bars/Duration in trades
    avg_bars_in_trade: float = Field(default=0.0, description="Average number of bars per trade")
    avg_bars_in_winning: float = Field(default=0.0, description="Average bars in winning trades")
    avg_bars_in_losing: float = Field(default=0.0, description="Average bars in losing trades")

    # Exposure
    exposure_time: float = Field(default=0.0, description="Percentage of time in market")
    avg_trade_duration_hours: float = Field(default=0.0, description="Average trade duration in hours")

    # Max contracts (for position sizing analysis)
    max_contracts_held: float = Field(default=0.0, description="Maximum position size held")

    # ===== STREAK ANALYSIS (TradingView) =====
    max_consecutive_wins: int = Field(default=0, description="Maximum consecutive winning trades")
    max_consecutive_losses: int = Field(default=0, description="Maximum consecutive losing trades")

    # ===== ADVANCED RISK METRICS =====
    # Recovery Factor = Net Profit / Max Drawdown
    recovery_factor: float = Field(default=0.0, description="Recovery factor (net profit / max drawdown)")

    # Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss)
    expectancy: float = Field(default=0.0, description="Mathematical expectancy per trade (%)")
    expectancy_ratio: float = Field(default=0.0, description="Expectancy ratio (expectancy / avg loss)")

    # Best/Worst trade values (in currency $)
    best_trade: float = Field(default=0.0, description="Best (most profitable) trade P&L in $")
    worst_trade: float = Field(default=0.0, description="Worst (largest loss) trade P&L in $")

    # CAGR - Compound Annual Growth Rate
    cagr: float = Field(default=0.0, description="Compound Annual Growth Rate (%)")
    cagr_long: float = Field(default=0.0, description="CAGR for long trades only (%)")
    cagr_short: float = Field(default=0.0, description="CAGR for short trades only (%)")

    # Volatility
    volatility: float = Field(default=0.0, description="Annualized volatility of returns (%)")

    # Open P&L (if position still open at end) - DUAL FORMAT
    open_pnl: float = Field(default=0.0, description="Unrealized P&L from open positions ($)")
    open_pnl_pct: float = Field(default=0.0, description="Unrealized P&L as % of equity")

    # Ulcer Index (risk measure based on drawdown depth and duration)
    ulcer_index: float = Field(default=0.0, description="Ulcer Index - measures downside volatility")

    # ===== LONG/SHORT SEPARATE STATISTICS (TradingView) =====
    long_trades: int = Field(default=0, description="Number of long trades")
    short_trades: int = Field(default=0, description="Number of short trades")
    long_winning_trades: int = Field(default=0, description="Number of winning long trades")
    short_winning_trades: int = Field(default=0, description="Number of winning short trades")
    long_pnl: float = Field(default=0.0, description="Total P&L from long trades ($)")
    short_pnl: float = Field(default=0.0, description="Total P&L from short trades ($)")
    long_pnl_pct: float = Field(default=0.0, description="Long trades P&L as % of initial capital")
    short_pnl_pct: float = Field(default=0.0, description="Short trades P&L as % of initial capital")
    long_win_rate: float = Field(default=0.0, description="Win rate for long trades (%)")
    short_win_rate: float = Field(default=0.0, description="Win rate for short trades (%)")
    # Extended Long/Short metrics
    long_losing_trades: int = Field(default=0, description="Number of losing long trades")
    short_losing_trades: int = Field(default=0, description="Number of losing short trades")
    long_gross_profit: float = Field(default=0.0, description="Gross profit from long trades ($)")
    long_gross_profit_pct: float = Field(
        default=0.0, description="Gross profit from long trades as % of initial capital"
    )
    long_gross_loss: float = Field(default=0.0, description="Gross loss from long trades ($)")
    long_gross_loss_pct: float = Field(default=0.0, description="Gross loss from long trades as % of initial capital")
    long_net_profit: float = Field(default=0.0, description="Net profit from long trades ($)")
    long_profit_factor: float = Field(default=0.0, description="Profit factor for long trades")
    long_avg_win: float = Field(default=0.0, description="Average winning long trade ($)")
    long_avg_win_value: float = Field(default=0.0, description="Average winning long trade ($)")
    long_avg_win_pct: float = Field(default=0.0, description="Average winning long trade (%)")
    long_avg_loss: float = Field(default=0.0, description="Average losing long trade ($)")
    long_avg_loss_value: float = Field(default=0.0, description="Average losing long trade ($)")
    long_avg_loss_pct: float = Field(default=0.0, description="Average losing long trade (%)")
    long_avg_trade: float = Field(default=0.0, description="Average long trade ($)")
    long_avg_trade_value: float = Field(default=0.0, description="Average long trade ($)")
    long_avg_trade_pct: float = Field(default=0.0, description="Average long trade (%)")
    short_gross_profit: float = Field(default=0.0, description="Gross profit from short trades ($)")
    short_gross_profit_pct: float = Field(
        default=0.0,
        description="Gross profit from short trades as % of initial capital",
    )
    short_gross_loss: float = Field(default=0.0, description="Gross loss from short trades ($)")
    short_gross_loss_pct: float = Field(default=0.0, description="Gross loss from short trades as % of initial capital")
    short_net_profit: float = Field(default=0.0, description="Net profit from short trades ($)")
    short_profit_factor: float = Field(default=0.0, description="Profit factor for short trades")
    short_avg_win: float = Field(default=0.0, description="Average winning short trade ($)")
    short_avg_win_value: float = Field(default=0.0, description="Average winning short trade ($)")
    short_avg_win_pct: float = Field(default=0.0, description="Average winning short trade (%)")
    short_avg_loss: float = Field(default=0.0, description="Average losing short trade ($)")
    short_avg_loss_value: float = Field(default=0.0, description="Average losing short trade ($)")
    short_avg_loss_pct: float = Field(default=0.0, description="Average losing short trade (%)")
    short_avg_trade: float = Field(default=0.0, description="Average short trade ($)")
    short_avg_trade_value: float = Field(default=0.0, description="Average short trade ($)")
    short_avg_trade_pct: float = Field(default=0.0, description="Average short trade (%)")

    # ===== RECOVERY FACTOR LONG/SHORT =====
    recovery_long: float = Field(
        default=0.0,
        description="Recovery factor for long trades (long_net_profit / max_drawdown)",
    )
    recovery_short: float = Field(
        default=0.0,
        description="Recovery factor for short trades (short_net_profit / max_drawdown)",
    )

    # ===== INTRABAR METRICS (TradingView) =====
    max_drawdown_intrabar: float = Field(default=0.0, description="Maximum drawdown including intrabar movements (%)")
    max_drawdown_intrabar_value: float = Field(default=0.0, description="Maximum intrabar drawdown in currency ($)")
    max_runup_intrabar: float = Field(default=0.0, description="Maximum run-up including intrabar movements (%)")
    max_runup_intrabar_value: float = Field(default=0.0, description="Maximum intrabar run-up in currency ($)")

    # ===== ACCOUNT SIZE METRICS (TradingView) =====
    account_size_required: float = Field(default=0.0, description="Minimum account size required to trade strategy ($)")
    return_on_account_size: float = Field(default=0.0, description="Net profit / Account size required (%)")

    # ===== MARGIN METRICS (TradingView) =====
    avg_margin_used: float = Field(default=0.0, description="Average margin used during trades ($)")
    max_margin_used: float = Field(default=0.0, description="Maximum margin used ($)")
    margin_efficiency: float = Field(default=0.0, description="Net profit / Max margin used (%)")
    margin_calls: int = Field(default=0, description="Number of margin call events")

    # ===== DURATION METRICS (TradingView) =====
    avg_runup_duration_bars: float = Field(default=0.0, description="Average equity run-up duration in bars")
    avg_drawdown_duration_bars: float = Field(default=0.0, description="Average equity drawdown duration in bars")

    # ===== LARGEST TRADE AS % OF GROSS (TradingView) =====
    largest_win_pct_of_gross: float = Field(default=0.0, description="Largest win as % of gross profit")
    largest_loss_pct_of_gross: float = Field(default=0.0, description="Largest loss as % of gross loss")

    # ===== STRATEGY COMPARISON (TradingView) =====
    strategy_outperformance: float = Field(default=0.0, description="Strategy return - Buy & Hold return (%)")
    net_profit_to_largest_loss: float = Field(default=0.0, description="Net profit as multiple of largest loss")

    # ===== PNL DISTRIBUTION (TradingView Histogram) =====
    # Распределение P&L по сделкам для построения гистограммы
    pnl_distribution: list[dict] = Field(
        default_factory=list,
        description="P&L distribution histogram data: [{bin: '-2%', count: 5, type: 'loss'}, ...]",
    )
    avg_profit_pct: float = Field(default=0.0, description="Average profit % (only profitable trades)")
    avg_loss_pct: float = Field(default=0.0, description="Average loss % (only losing trades, negative value)")

    # ===== BREAKEVEN TRADES =====
    breakeven_trades: int = Field(default=0, description="Number of breakeven trades")

    # ===== SLIPPAGE (TradingView) =====
    total_slippage: float = Field(default=0.0, description="Total slippage paid across all trades ($)")

    # ===== CLOSED TRADES (TradingView distinguishes All/Closed) =====
    closed_trades: int = Field(default=0, description="Number of closed trades (excluding open positions)")

    # ===== AVG BARS IN TRADE - LONG/SHORT SEPARATE =====
    avg_bars_in_winning_long: float = Field(default=0.0, description="Average bars in winning long trades")
    avg_bars_in_winning_short: float = Field(default=0.0, description="Average bars in winning short trades")
    avg_bars_in_losing_long: float = Field(default=0.0, description="Average bars in losing long trades")
    avg_bars_in_losing_short: float = Field(default=0.0, description="Average bars in losing short trades")
    avg_bars_in_long: float = Field(default=0.0, description="Average bars in all long trades")
    avg_bars_in_short: float = Field(default=0.0, description="Average bars in all short trades")

    # ===== AVG TRADE P&L - LONG/SHORT SEPARATE =====
    avg_win_long: float = Field(default=0.0, description="Average winning long trade P&L ($)")
    avg_win_short: float = Field(default=0.0, description="Average winning short trade P&L ($)")
    avg_loss_long: float = Field(default=0.0, description="Average losing long trade P&L ($)")
    avg_loss_short: float = Field(default=0.0, description="Average losing short trade P&L ($)")
    avg_trade_long: float = Field(default=0.0, description="Average long trade P&L ($)")
    avg_trade_short: float = Field(default=0.0, description="Average short trade P&L ($)")

    # ===== BREAKEVEN TRADES - LONG/SHORT SEPARATE =====
    long_breakeven_trades: int = Field(default=0, description="Number of breakeven long trades")
    short_breakeven_trades: int = Field(default=0, description="Number of breakeven short trades")

    # ===== LARGEST WIN/LOSS - LONG/SHORT SEPARATE =====
    long_largest_win: float = Field(default=0.0, description="Largest winning long trade ($)")
    long_largest_loss: float = Field(default=0.0, description="Largest losing long trade ($)")
    short_largest_win: float = Field(default=0.0, description="Largest winning short trade ($)")
    short_largest_loss: float = Field(default=0.0, description="Largest losing short trade ($)")
    # Value variants (alias) for TradingView compatibility
    long_largest_win_value: float = Field(default=0.0, description="Largest winning long trade value ($)")
    long_largest_loss_value: float = Field(default=0.0, description="Largest losing long trade value ($)")
    short_largest_win_value: float = Field(default=0.0, description="Largest winning short trade value ($)")
    short_largest_loss_value: float = Field(default=0.0, description="Largest losing short trade value ($)")

    # ===== PAYOFF RATIO - LONG/SHORT SEPARATE =====
    long_payoff_ratio: float = Field(default=0.0, description="Payoff ratio for long trades (avg_win / avg_loss)")
    short_payoff_ratio: float = Field(default=0.0, description="Payoff ratio for short trades (avg_win / avg_loss)")

    # ===== COMMISSION - LONG/SHORT SEPARATE =====
    long_commission: float = Field(default=0.0, description="Total commission from long trades ($)")
    short_commission: float = Field(default=0.0, description="Total commission from short trades ($)")

    # ===== CONSECUTIVE WINS/LOSSES - LONG/SHORT SEPARATE =====
    long_max_consec_wins: int = Field(default=0, description="Max consecutive winning long trades")
    long_max_consec_losses: int = Field(default=0, description="Max consecutive losing long trades")
    short_max_consec_wins: int = Field(default=0, description="Max consecutive winning short trades")
    short_max_consec_losses: int = Field(default=0, description="Max consecutive losing short trades")

    # ===== MAX DD DURATION IN BARS =====
    max_drawdown_duration_bars: int = Field(default=0, description="Maximum drawdown duration in bars")

    # ===== NEW: SHARPE/SORTINO - LONG/SHORT SEPARATE (TradingView) =====
    sharpe_long: float = Field(default=0.0, description="Sharpe ratio for long trades only")
    sharpe_short: float = Field(default=0.0, description="Sharpe ratio for short trades only")
    sortino_long: float = Field(default=0.0, description="Sortino ratio for long trades only")
    sortino_short: float = Field(default=0.0, description="Sortino ratio for short trades only")
    calmar_long: float = Field(default=0.0, description="Calmar ratio for long trades only")
    calmar_short: float = Field(default=0.0, description="Calmar ratio for short trades only")

    # ===== NEW: EXPECTANCY - LONG/SHORT SEPARATE (TradingView) =====
    long_expectancy: float = Field(default=0.0, description="Expected payoff per long trade ($)")
    short_expectancy: float = Field(default=0.0, description="Expected payoff per short trade ($)")

    # ===== NEW: LARGEST WIN/LOSS PERCENT - LONG/SHORT (TradingView) =====
    long_largest_win_pct: float = Field(default=0.0, description="Largest winning long trade (%)")
    short_largest_win_pct: float = Field(default=0.0, description="Largest winning short trade (%)")
    long_largest_loss_pct: float = Field(default=0.0, description="Largest losing long trade (%)")
    short_largest_loss_pct: float = Field(default=0.0, description="Largest losing short trade (%)")

    # ===== NEW: LARGEST AS % OF GROSS - LONG/SHORT (TradingView) =====
    long_largest_win_pct_of_gross: float = Field(default=0.0, description="Largest long win as % of long gross profit")
    short_largest_win_pct_of_gross: float = Field(
        default=0.0, description="Largest short win as % of short gross profit"
    )
    long_largest_loss_pct_of_gross: float = Field(default=0.0, description="Largest long loss as % of long gross loss")
    short_largest_loss_pct_of_gross: float = Field(
        default=0.0, description="Largest short loss as % of short gross loss"
    )

    # ===== NEW: RETURN ON CAPITAL - LONG/SHORT (TradingView) =====
    long_return_on_capital: float = Field(default=0.0, description="Long net profit as % of initial capital")
    short_return_on_capital: float = Field(default=0.0, description="Short net profit as % of initial capital")

    # ===== NEW: RETURN ON ACCOUNT SIZE - LONG/SHORT (TradingView) =====
    long_return_on_account_size: float = Field(default=0.0, description="Long net profit / account size required (%)")
    short_return_on_account_size: float = Field(default=0.0, description="Short net profit / account size required (%)")

    # ===== NEW: NET PROFIT AS % OF LARGEST LOSS - LONG/SHORT (TradingView) =====
    long_net_profit_to_largest_loss: float = Field(default=0.0, description="Long net profit as % of largest long loss")
    short_net_profit_to_largest_loss: float = Field(
        default=0.0, description="Short net profit as % of largest short loss"
    )


class PeriodAnalysis(BaseModel):
    """Performance analysis for a specific period (month/year)"""

    period: str = Field(..., description="Period identifier (e.g., '2024-01', '2024')")
    start_date: datetime
    end_date: datetime
    net_profit: float = 0.0
    net_profit_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0


class EquityCurve(BaseModel):
    """Equity curve data with TradingView-compatible fields"""

    timestamps: list[datetime]
    equity: list[float]
    drawdown: list[float] = []
    returns: list[float] = []

    # ===== NEW: Buy & Hold equity series (TradingView) =====
    bh_equity: list[float] = Field(default_factory=list, description="Buy & Hold equity curve for comparison")
    bh_drawdown: list[float] = Field(default_factory=list, description="Buy & Hold drawdown curve")

    # ===== NEW: Periodic analysis (TradingView) =====
    monthly_analysis: list[PeriodAnalysis] = Field(default_factory=list, description="Performance breakdown by month")
    yearly_analysis: list[PeriodAnalysis] = Field(default_factory=list, description="Performance breakdown by year")

    # ===== NEW: Runup series =====
    runup: list[float] = Field(default_factory=list, description="Equity run-up series (%)")


class AnalysisWarningModel(BaseModel):
    """Single analysis warning (Pydantic model)"""

    code: str  # e.g., "LOOKAHEAD_001"
    level: str  # "info", "warning", "error", "critical"
    message: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


class StaticAnalysisResult(BaseModel):
    """Static analysis result for strategy code (TradingView compatible)"""

    has_lookahead_bias: bool = Field(default=False, description="Strategy uses future data in calculations")
    is_repainting: bool = Field(default=False, description="Indicator values change on historical bars")
    has_data_leakage: bool = Field(default=False, description="Train/test data contamination detected")

    # Detailed flags
    uses_future_data: bool = Field(default=False)
    uses_high_low_of_current_bar: bool = Field(default=False)
    uses_close_for_entry_on_same_bar: bool = Field(default=False)
    has_forward_fill: bool = Field(default=False)
    uses_request_security: bool = Field(default=False)

    warnings: list[AnalysisWarningModel] = Field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        """Check if strategy passed all checks"""
        return not (self.has_lookahead_bias or self.is_repainting or self.has_data_leakage)


class BacktestResult(BaseModel):
    """Complete backtest result"""

    model_config = ConfigDict(use_enum_values=True)

    # Identification
    id: str
    status: BacktestStatus
    created_at: datetime
    completed_at: Optional[datetime] = None

    # Configuration (copy for record)
    config: BacktestConfig

    # Results
    metrics: Optional[PerformanceMetrics] = None
    trades: list[TradeRecord] = Field(default_factory=list)
    equity_curve: Optional[EquityCurve] = None

    # Final state
    final_equity: Optional[float] = None
    final_pnl: Optional[float] = None
    final_pnl_pct: Optional[float] = None

    # ===== STATIC ANALYSIS FLAGS (TradingView compatible) =====
    static_analysis: Optional[StaticAnalysisResult] = Field(
        default=None,
        description="Static analysis result with lookahead/repaint detection",
    )

    # Quick access flags (also in static_analysis for detail)
    has_lookahead_bias: bool = Field(default=False, description="Strategy uses future data - UNRELIABLE RESULTS")
    is_repainting: bool = Field(
        default=False,
        description="Strategy repaints - historical signals may differ from live",
    )

    # Warnings list (summary)
    analysis_warnings: list[str] = Field(
        default_factory=list,
        description="List of warning messages from static analysis",
    )

    # Errors
    error_message: Optional[str] = None


class BacktestCreateRequest(BaseModel):
    """API request to create a backtest"""

    model_config = ConfigDict(use_enum_values=True)

    symbol: str = Field(..., min_length=1, max_length=20)
    # Accepts both Bybit native (1, 5, 15, 30, 60, 240, D, W, M) and
    # TradingView-style (1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w, 1M) intervals
    interval: str = Field(
        ..., pattern=r"^(1|3|5|15|30|60|120|240|360|720|D|W|M|1m|3m|5m|15m|30m|1h|2h|4h|6h|12h|1d|1w|1M)$"
    )
    start_date: datetime
    end_date: datetime
    strategy_type: StrategyType = StrategyType.SMA_CROSSOVER
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    initial_capital: float = Field(default=10000.0, ge=100, le=100_000_000)
    position_size: float = Field(default=1.0, ge=0.01, le=1.0)
    leverage: float = Field(default=1.0, ge=1.0, le=125.0)  # Bybit max leverage
    direction: str = Field(default="long", description="Trading direction: 'long', 'short', or 'both'")
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    save_to_db: bool = Field(default=True, description="Save backtest result to database")


class BacktestListResponse(BaseModel):
    """API response for listing backtests"""

    total: int
    items: list[BacktestResult]
    page: int = 1
    page_size: int = 20
