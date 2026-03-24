"""
Pydantic request/response models for the backtests router.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class RunFromStrategyRequest(BaseModel):
    """Request to run backtest from a saved strategy"""

    symbol: str | None = Field(default=None, description="Override strategy's symbol")
    interval: str | None = Field(default=None, description="Override strategy's timeframe")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    initial_capital: float | None = Field(default=None, ge=100, description="Override strategy's initial capital")
    position_size: float | None = Field(default=None, ge=0.01, le=1.0, description="Override position size")
    save_result: bool = Field(default=True, description="Save result to database and update strategy metrics")


class RunFromStrategyResponse(BaseModel):
    """Response from running backtest from strategy"""

    backtest_id: str
    strategy_id: str
    strategy_name: str
    status: str
    metrics: dict | None = None
    error_message: str | None = None
    saved_to_db: bool = False


class SaveOptimizationResultRequest(BaseModel):
    """Request to save optimization result as a backtest"""

    name: str = Field(..., description="Name for the backtest")
    strategy_id: str | None = Field(default=None, description="Link to parent strategy for metrics update")
    config: dict = Field(..., description="Backtest configuration")
    results: dict = Field(..., description="Performance metrics")
    status: str = Field(default="completed")
    metadata: dict | None = Field(default=None, description="Additional metadata")


class SaveOptimizationResultResponse(BaseModel):
    """Response after saving optimization result"""

    id: str
    name: str
    status: str
    created_at: str


class MTFBacktestRequest(BaseModel):
    """Request model for MTF backtest."""

    # Standard params
    symbol: str = Field(..., description="Trading pair (e.g., BTCUSDT)")
    interval: str = Field(..., description="LTF interval (e.g., 15m, 5m)")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(default=10000.0, ge=100)
    leverage: int = Field(default=10, ge=1, le=125)
    direction: str = Field(default="both", pattern="^(long|short|both)$")

    # Risk management
    stop_loss: float = Field(default=0.02, ge=0.001, le=0.5)
    take_profit: float = Field(default=0.03, ge=0.001, le=1.0)

    # Strategy params
    strategy_type: str = Field(default="rsi", description="Strategy: rsi, sma_crossover")
    strategy_params: dict = Field(default_factory=dict)

    # MTF params
    htf_interval: str = Field(default="60", description="HTF interval (e.g., 60, 240)")
    htf_filter_type: str = Field(default="sma", pattern="^(sma|ema)$")
    htf_filter_period: int = Field(default=200, ge=1, le=500)
    mtf_neutral_zone_pct: float = Field(default=0.0, ge=0.0, le=5.0)

    # BTC correlation (optional)
    use_btc_filter: bool = Field(default=False)
    btc_sma_period: int = Field(default=50, ge=1, le=200)

    # Advanced features (optional)
    trailing_stop_enabled: bool = Field(default=False)
    trailing_stop_activation: float = Field(default=0.01)
    trailing_stop_distance: float = Field(default=0.005)
    breakeven_enabled: bool = Field(default=False)
    dca_enabled: bool = Field(default=False)
    dca_safety_orders: int = Field(default=0, ge=0, le=10)


class MTFBacktestResponse(BaseModel):
    """Response model for MTF backtest."""

    backtest_id: str
    status: str
    is_valid: bool

    # Metrics
    total_trades: int
    filtered_trades: int  # Trades filtered by MTF
    net_profit: float
    total_return_pct: float
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float

    # MTF stats
    mtf_filter_type: str
    mtf_filter_period: int
    htf_interval: str
    long_signals_allowed: int
    short_signals_allowed: int
    long_signals_filtered: int
    short_signals_filtered: int

    # Comparison (MTF vs no MTF)
    baseline_trades: int | None = None
    baseline_pnl: float | None = None
    mtf_improvement_pct: float | None = None

    # Trades (limited)
    trades: list[dict] = Field(default_factory=list)

    # Equity curve
    equity_curve: dict | None = None
