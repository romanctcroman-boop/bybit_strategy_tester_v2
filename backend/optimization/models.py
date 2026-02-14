"""
Optimization Request/Response Models.

Pydantic models for optimization API endpoints.
Extracted from optimizations.py monolith for maintainability.
"""

from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# SYNC GRID SEARCH
# =============================================================================


class SyncOptimizationRequest(BaseModel):
    """Request for sync grid/random search optimization."""

    symbol: str = "BTCUSDT"
    interval: str = "30m"
    start_date: str = "2025-01-01"
    end_date: str = "2025-06-01"

    # Base strategy parameters
    strategy_type: str = "rsi"
    direction: str = "long"
    use_fixed_amount: bool = True
    fixed_amount: float = 100.0
    leverage: int = 10
    initial_capital: float = 10000.0
    commission: float = 0.0007  # 0.07% TradingView parity

    # RSI parameter ranges (lists of discrete values)
    rsi_period_range: list[int] = [7, 14, 21]
    rsi_overbought_range: list[int] = [70, 75, 80]
    rsi_oversold_range: list[int] = [20, 25, 30]

    # SMA Crossover parameter ranges
    sma_fast_period_range: list[int] | None = None
    sma_slow_period_range: list[int] | None = None

    # EMA Crossover parameter ranges
    ema_fast_period_range: list[int] | None = None
    ema_slow_period_range: list[int] | None = None

    # MACD parameter ranges
    macd_fast_period_range: list[int] | None = None
    macd_slow_period_range: list[int] | None = None
    macd_signal_period_range: list[int] | None = None

    # Bollinger Bands parameter ranges
    bb_period_range: list[int] | None = None
    bb_std_dev_range: list[float] | None = None

    # TP/SL ranges (percent values)
    stop_loss_range: list[float] = [10.0]
    take_profit_range: list[float] = [1.5]

    # Primary optimization metric (backwards compat)
    optimize_metric: str = "net_profit"

    # Multi-criteria selection
    selection_criteria: list[str] = ["net_profit", "max_drawdown"]

    # Engine selection
    engine_type: str = "auto"

    # Search method: grid | random
    search_method: str = "grid"

    # Max iterations for Random Search (0 = 10% of total)
    max_iterations: int = 0

    # max_trials — alias from frontend (maps to max_iterations)
    max_trials: int | None = None

    # Market type: linear | spot
    market_type: str = "linear"

    # Hybrid: validate best on FallbackV4
    validate_best_with_fallback: bool = False

    # Market Regime Filter
    market_regime_enabled: bool = False
    market_regime_filter: str = "not_volatile"
    market_regime_lookback: int = 50

    # === Optimization Config from Frontend ===
    workers: int | None = None
    timeout_seconds: int = 3600
    train_split: float = 1.0  # 1.0 = use all data (no split)
    early_stopping: bool = False
    early_stopping_patience: int = 20
    warm_start: bool = False
    prune_infeasible: bool = True
    random_seed: int | None = None

    # === Evaluation Criteria from Frontend ===
    constraints: list[dict] | None = None
    sort_order: list[dict] | None = None
    use_composite: bool = False
    weights: dict[str, float] | None = None


class OptimizationResult(BaseModel):
    """Single parameter combination result."""

    params: dict[str, Any]
    score: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int


class SmartRecommendation(BaseModel):
    """Single recommendation entry."""

    params: dict[str, Any] | None = None
    total_return: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    win_rate: float | None = None
    total_trades: int | None = None


class SmartRecommendations(BaseModel):
    """Smart recommendations from optimization."""

    best_balanced: SmartRecommendation | None = None
    best_conservative: SmartRecommendation | None = None
    best_aggressive: SmartRecommendation | None = None
    recommendation_text: str = ""


class SyncOptimizationResponse(BaseModel):
    """Response for sync grid/random/optuna optimization."""

    status: str
    total_combinations: int
    tested_combinations: int
    best_params: dict[str, Any]
    best_score: float
    best_metrics: dict[str, Any]
    top_results: list[dict[str, Any]]
    execution_time_seconds: float
    speed_combinations_per_sec: int | None = None
    num_workers: int | None = None
    smart_recommendations: SmartRecommendations | None = None
    validated_metrics: dict[str, Any] | None = None
    # Train/test split metrics (NEW)
    train_metrics: dict[str, Any] | None = None
    test_metrics: dict[str, Any] | None = None
    early_stopped: bool = False
    early_stopped_at: int | None = None


# =============================================================================
# OPTUNA BAYESIAN
# =============================================================================


class OptunaSyncRequest(SyncOptimizationRequest):
    """Optuna Bayesian optimization — extends grid-search request."""

    n_trials: int = Field(100, ge=10, le=500, description="Number of Optuna trials")
    sampler_type: str = Field("tpe", description="Optuna sampler: tpe, random, cmaes")
    n_jobs: int = Field(1, ge=1, le=8, description="Parallel trials")


# =============================================================================
# VECTORBT HIGH-PERFORMANCE
# =============================================================================


class VectorbtOptimizationRequest(BaseModel):
    """Request for VectorBT high-performance optimization."""

    symbol: str = "BTCUSDT"
    interval: str = "30m"
    start_date: str = "2025-01-01"
    end_date: str = "2025-06-01"

    direction: str = "long"
    leverage: int = 10
    initial_capital: float = 10000.0
    commission: float = 0.0007
    slippage: float = 0.0005
    position_size: float = 1.0

    rsi_period_range: list[int] = [7, 14, 21]
    rsi_overbought_range: list[int] = [70, 75, 80]
    rsi_oversold_range: list[int] = [20, 25, 30]
    stop_loss_range: list[float] = [5.0, 10.0, 15.0]
    take_profit_range: list[float] = [1.0, 2.0, 3.0]

    optimize_metric: str = "sharpe_ratio"
    weight_return: float = 0.4
    weight_drawdown: float = 0.3
    weight_sharpe: float = 0.2
    weight_win_rate: float = 0.1

    min_trades: int | None = None
    max_drawdown_limit: float | None = None
    min_profit_factor: float | None = None
    min_win_rate: float | None = None


class VectorbtOptimizationResponse(BaseModel):
    """Response from VectorBT optimization."""

    status: str
    total_combinations: int
    tested_combinations: int
    execution_time_seconds: float
    speed_combinations_per_sec: int | None = None
    num_workers: int | None = None
    best_params: dict[str, Any]
    best_score: float
    best_metrics: dict[str, Any]
    top_results: list[dict[str, Any]]
    performance_stats: dict[str, Any]
    smart_recommendations: SmartRecommendations | None = None
