"""
Monte Carlo Simulation API Router.

Provides endpoints for:
- Running Monte Carlo analysis on backtests
- Getting probability distributions
- Risk metric calculations
- Kelly Criterion calculations
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.backtesting.position_sizing import (
    KellyCalculator,
    MonteCarloAnalyzer,
    TradeResult,
)
from backend.services.monte_carlo import MonteCarloSimulator, run_monte_carlo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monte-carlo", tags=["monte-carlo"])


class MonteCarloRequest(BaseModel):
    """Request model for Monte Carlo simulation."""

    backtest_results: dict[str, Any] = Field(
        ...,
        description="Backtest results dictionary containing trades or returns",
    )
    n_simulations: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Number of simulations to run (100-100000)",
    )
    initial_capital: float = Field(
        default=10000.0,
        gt=0,
        description="Initial capital for the simulation",
    )
    benchmark_return: float = Field(
        default=0.0,
        description="Benchmark return to compare against (e.g., 0.10 for 10%)",
    )
    method: str = Field(
        default="permutation",
        description="Simulation method: permutation, bootstrap, or block_bootstrap",
    )


class MonteCarloResponse(BaseModel):
    """Response model for Monte Carlo simulation."""

    n_simulations: int
    method: str
    simulation_time_ms: float
    original: dict[str, float]
    statistics: dict[str, float]
    risk_metrics: dict[str, float]
    probabilities: dict[str, float]
    confidence_intervals: dict[str, list[float]]
    scenarios: dict[str, float]


class ProbabilityRequest(BaseModel):
    """Request for probability calculation."""

    backtest_results: dict[str, Any]
    target_return: float = Field(
        ...,
        description="Target return to calculate probability for (e.g., 0.20 for 20%)",
    )
    n_simulations: int = Field(default=10000, ge=100, le=100000)


class ProbabilityResponse(BaseModel):
    """Response for probability calculation."""

    target_return_pct: float
    probability_pct: float
    n_simulations: int
    method: str


class RiskMetricsRequest(BaseModel):
    """Request for risk metrics calculation."""

    backtest_results: dict[str, Any]
    confidence_level: float = Field(
        default=0.95,
        ge=0.5,
        le=0.99,
        description="Confidence level for VaR/CVaR (0.5-0.99)",
    )
    n_simulations: int = Field(default=10000, ge=100, le=100000)


class RiskMetricsResponse(BaseModel):
    """Response for risk metrics."""

    confidence_level_pct: float
    value_at_risk_pct: float
    conditional_var_pct: float
    max_drawdown_percentile_pct: float
    worst_case_return_pct: float
    n_simulations: int


@router.post("/analyze", response_model=MonteCarloResponse)
async def run_monte_carlo_analysis(request: MonteCarloRequest) -> MonteCarloResponse:
    """
    Run Monte Carlo simulation on backtest results.

    Performs statistical analysis by shuffling trade sequences or
    bootstrapping returns to estimate:
    - Return distribution statistics
    - Risk metrics (VaR, CVaR)
    - Probability of achieving targets
    - Confidence intervals
    """
    try:
        # Validate method
        valid_methods = ["permutation", "bootstrap", "block_bootstrap"]
        if request.method not in valid_methods:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid method: {request.method}. Must be one of: {valid_methods}",
            )

        simulator = MonteCarloSimulator(n_simulations=request.n_simulations)
        result = simulator.analyze_strategy(
            backtest_results=request.backtest_results,
            initial_capital=request.initial_capital,
            benchmark_return=request.benchmark_return,
            method=request.method,
        )

        return MonteCarloResponse(**result.to_dict())

    except Exception as e:
        logger.exception("Monte Carlo simulation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/probability", response_model=ProbabilityResponse)
async def calculate_probability(request: ProbabilityRequest) -> ProbabilityResponse:
    """
    Calculate the probability of achieving a target return.

    Uses Monte Carlo simulation to estimate the likelihood
    of the strategy achieving at least the specified return.
    """
    try:
        simulator = MonteCarloSimulator(n_simulations=request.n_simulations)
        result = simulator.analyze_strategy(
            backtest_results=request.backtest_results,
            method="permutation",
        )

        probability = result.probability_of_return(request.target_return)

        return ProbabilityResponse(
            target_return_pct=round(request.target_return * 100, 2),
            probability_pct=round(probability * 100, 2),
            n_simulations=request.n_simulations,
            method="permutation",
        )

    except Exception as e:
        logger.exception("Probability calculation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk-metrics", response_model=RiskMetricsResponse)
async def calculate_risk_metrics(request: RiskMetricsRequest) -> RiskMetricsResponse:
    """
    Calculate risk metrics using Monte Carlo simulation.

    Returns:
    - Value at Risk (VaR): Maximum expected loss at confidence level
    - Conditional VaR (CVaR): Expected loss beyond VaR
    - Max drawdown percentile
    - Worst case scenario
    """
    try:
        simulator = MonteCarloSimulator(n_simulations=request.n_simulations)
        result = simulator.analyze_strategy(
            backtest_results=request.backtest_results,
            method="permutation",
        )

        # Calculate VaR at requested confidence level
        var_percentile = (1 - request.confidence_level) * 100
        var = result.return_percentile(var_percentile)

        # CVaR is average of returns below VaR
        returns_below_var = result.simulated_returns[result.simulated_returns <= var]
        cvar = float(returns_below_var.mean()) if len(returns_below_var) > 0 else var

        # Max drawdown at confidence level
        dd_percentile = result.drawdown_percentile(request.confidence_level * 100)

        return RiskMetricsResponse(
            confidence_level_pct=round(request.confidence_level * 100, 1),
            value_at_risk_pct=round(var * 100, 2),
            conditional_var_pct=round(cvar * 100, 2),
            max_drawdown_percentile_pct=round(dd_percentile * 100, 2),
            worst_case_return_pct=round(result.worst_case_return * 100, 2),
            n_simulations=request.n_simulations,
        )

    except Exception as e:
        logger.exception("Risk metrics calculation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/methods")
async def list_methods() -> dict:
    """
    List available Monte Carlo simulation methods.
    """
    return {
        "methods": [
            {
                "name": "permutation",
                "description": "Randomly shuffle trade sequence to test path-dependency. Best for testing if order of trades matters.",
                "use_case": "General robustness testing",
            },
            {
                "name": "bootstrap",
                "description": "Sample trades with replacement. Generates new possible trade sequences.",
                "use_case": "Estimating confidence intervals",
            },
            {
                "name": "block_bootstrap",
                "description": "Sample blocks of consecutive trades to preserve some time-series structure.",
                "use_case": "When trades have temporal correlation",
            },
        ]
    }


@router.post("/quick-analysis")
async def quick_analysis(
    backtest_id: Optional[int] = None,
    total_return: float = Query(
        ..., description="Total return as decimal (e.g., 0.25 for 25%)"
    ),
    total_trades: int = Query(..., ge=1, description="Total number of trades"),
    win_rate: float = Query(..., ge=0, le=1, description="Win rate as decimal (0-1)"),
    avg_win: float = Query(default=0.02, description="Average winning trade return"),
    avg_loss: float = Query(default=-0.01, description="Average losing trade return"),
    max_drawdown: float = Query(
        default=-0.1, description="Maximum drawdown as decimal"
    ),
    n_simulations: int = Query(default=5000, ge=100, le=50000),
) -> dict:
    """
    Quick Monte Carlo analysis from summary statistics.

    Use this when you only have aggregate backtest metrics,
    not individual trade data.
    """
    try:
        # Construct backtest results from parameters
        backtest_results = {
            "total_return": total_return,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "winning_trades": int(total_trades * win_rate),
            "losing_trades": total_trades - int(total_trades * win_rate),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": 0,  # Will be estimated
        }

        result = run_monte_carlo(
            backtest_results=backtest_results,
            n_simulations=n_simulations,
            method="parametric",
        )

        if backtest_id:
            result["backtest_id"] = backtest_id

        return result

    except Exception as e:
        logger.exception("Quick analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Kelly Criterion Endpoints
# ============================================================================


class KellyRequest(BaseModel):
    """Request model for Kelly Criterion calculation."""

    trades: list[dict[str, Any]] = Field(
        ...,
        description="List of trades with pnl, entry_price, exit_price, size",
    )
    taker_fee: float = Field(
        default=0.0007,
        ge=0,
        le=0.01,
        description="Taker fee rate (default 0.07% for Bybit)",
    )
    min_trades: int = Field(
        default=50,
        ge=10,
        description="Minimum trades for Kelly calculation",
    )
    lookback_trades: int = Field(
        default=100,
        ge=20,
        description="Number of recent trades to consider",
    )
    use_exponential_weights: bool = Field(
        default=True,
        description="Weight recent trades more heavily",
    )
    decay_factor: float = Field(
        default=0.95,
        ge=0.8,
        le=0.99,
        description="Decay factor for exponential weights",
    )
    kelly_fraction: float = Field(
        default=0.5,
        ge=0.1,
        le=1.0,
        description="Fraction of Kelly to use (0.5 = Half-Kelly)",
    )


class KellyResponse(BaseModel):
    """Response model for Kelly calculation."""

    kelly_fraction: Optional[float] = Field(
        None, description="Recommended position size as fraction of capital"
    )
    full_kelly: Optional[float] = Field(
        None, description="Full Kelly value (use with caution)"
    )
    half_kelly: Optional[float] = Field(
        None, description="Half-Kelly value (recommended)"
    )
    win_rate: Optional[float] = Field(None, description="Win rate of analyzed trades")
    win_loss_ratio: Optional[float] = Field(
        None, description="Average win / average loss ratio"
    )
    avg_win: Optional[float] = Field(None, description="Average winning trade PnL")
    avg_loss: Optional[float] = Field(None, description="Average losing trade PnL")
    trades_analyzed: int = Field(..., description="Number of trades analyzed")
    sufficient_data: bool = Field(..., description="Whether enough data for Kelly")
    recommendation: str = Field(..., description="Position sizing recommendation")


@router.post("/kelly", response_model=KellyResponse)
async def calculate_kelly(request: KellyRequest) -> KellyResponse:
    """
    Calculate optimal position size using enhanced Kelly Criterion.

    Features:
    - Fee-adjusted PnL calculation
    - Exponential weighting (recent trades matter more)
    - Half-Kelly for safety
    - Detailed statistics
    """
    try:
        # Convert trades to TradeResult objects
        trade_results = []
        for t in request.trades:
            trade_results.append(
                TradeResult(
                    pnl=t.get("pnl", 0),
                    entry_price=t.get("entry_price", 0),
                    exit_price=t.get("exit_price", 0),
                    size=t.get("size", t.get("quantity", 1)),
                    entry_fee=t.get("entry_fee", 0),
                    exit_fee=t.get("exit_fee", 0),
                )
            )

        calculator = KellyCalculator(
            min_trades=request.min_trades,
            lookback_trades=request.lookback_trades,
            use_exponential_weights=request.use_exponential_weights,
            decay_factor=request.decay_factor,
            kelly_fraction=request.kelly_fraction,
        )

        stats = calculator.get_kelly_stats(trade_results, request.taker_fee)

        # Generate recommendation
        if not stats["sufficient_data"]:
            recommendation = (
                f"Insufficient data: {stats['trades_analyzed']} trades, "
                f"need at least {request.min_trades}. Use fixed 5-10% position size."
            )
        elif stats["kelly_fraction"] and stats["kelly_fraction"] < 0.05:
            recommendation = (
                "Low Kelly suggests poor edge. Consider smaller positions (2-5%) "
                "or review strategy parameters."
            )
        elif stats["kelly_fraction"] and stats["kelly_fraction"] > 0.20:
            recommendation = (
                f"High Kelly ({stats['kelly_fraction']:.1%}). Strong edge detected. "
                f"Use Half-Kelly ({stats['half_kelly']:.1%}) for safety."
            )
        else:
            recommendation = (
                f"Moderate Kelly ({stats['kelly_fraction']:.1%}). "
                f"Recommended position size: {stats['kelly_fraction']:.1%} of capital."
            )

        return KellyResponse(
            kelly_fraction=stats["kelly_fraction"],
            full_kelly=stats.get("full_kelly"),
            half_kelly=stats.get("half_kelly"),
            win_rate=stats.get("win_rate"),
            win_loss_ratio=stats.get("win_loss_ratio"),
            avg_win=stats.get("avg_win"),
            avg_loss=stats.get("avg_loss"),
            trades_analyzed=stats["trades_analyzed"],
            sufficient_data=stats["sufficient_data"],
            recommendation=recommendation,
        )

    except Exception as e:
        logger.exception("Kelly calculation failed")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Enhanced Monte Carlo (from position_sizing module)
# ============================================================================


class EnhancedMCRequest(BaseModel):
    """Request for enhanced Monte Carlo simulation."""

    trades: list[dict[str, Any]] = Field(
        ...,
        description="List of trades with pnl field",
    )
    initial_capital: float = Field(
        default=10000.0,
        gt=0,
        description="Initial capital for simulation",
    )
    n_simulations: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Number of simulations",
    )
    target_return: float = Field(
        default=0.5,
        description="Target return for probability calculation (0.5 = 50%)",
    )
    max_drawdown_limit: float = Field(
        default=0.3,
        ge=0.1,
        le=0.9,
        description="Max drawdown limit for risk of ruin (0.3 = 30%)",
    )
    confidence_level: float = Field(
        default=0.95,
        ge=0.8,
        le=0.99,
        description="Confidence level for intervals",
    )


class EnhancedMCResponse(BaseModel):
    """Response for enhanced Monte Carlo simulation."""

    n_simulations: int
    trades_count: int
    initial_capital: float
    confidence_level: float
    # Return statistics
    return_mean: float
    return_median: float
    return_std: float
    return_ci_lower: float
    return_ci_upper: float
    return_5th_percentile: float
    return_95th_percentile: float
    # Drawdown statistics
    max_drawdown_mean: float
    max_drawdown_median: float
    max_drawdown_ci_lower: float
    max_drawdown_ci_upper: float
    max_drawdown_worst: float
    # Sharpe statistics
    sharpe_mean: float
    sharpe_median: float
    sharpe_ci_lower: float
    sharpe_ci_upper: float
    # Win rate statistics
    win_rate_mean: float
    win_rate_ci_lower: float
    win_rate_ci_upper: float
    # Probability metrics
    probability_of_profit: float
    probability_of_target: float
    risk_of_ruin: float
    # Risk metrics
    var_95: float
    cvar_95: float


@router.post("/enhanced-analysis", response_model=EnhancedMCResponse)
async def enhanced_monte_carlo(request: EnhancedMCRequest) -> EnhancedMCResponse:
    """
    Run enhanced Monte Carlo simulation with detailed statistics.

    This endpoint uses bootstrap resampling to estimate:
    - Confidence intervals for returns, drawdown, Sharpe ratio
    - Probability of achieving target returns
    - Risk of ruin probability
    - VaR and CVaR metrics
    """
    try:
        # Convert trades to TradeResult objects
        trade_results = []
        for t in request.trades:
            trade_results.append(
                TradeResult(
                    pnl=t.get("pnl", 0),
                    entry_price=t.get("entry_price", 1),
                    exit_price=t.get("exit_price", 1),
                    size=t.get("size", t.get("quantity", 1)),
                )
            )

        analyzer = MonteCarloAnalyzer(
            n_simulations=request.n_simulations,
            confidence_level=request.confidence_level,
        )

        result = analyzer.run_simulation(
            trades=trade_results,
            initial_capital=request.initial_capital,
            target_return=request.target_return,
            max_drawdown_limit=request.max_drawdown_limit,
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return EnhancedMCResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Enhanced Monte Carlo simulation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-kelly")
async def quick_kelly_from_stats(
    win_rate: float = Query(..., ge=0, le=1, description="Win rate as decimal (0-1)"),
    avg_win: float = Query(..., gt=0, description="Average winning trade amount"),
    avg_loss: float = Query(
        ..., gt=0, description="Average losing trade amount (positive)"
    ),
    kelly_fraction: float = Query(
        default=0.5, ge=0.1, le=1.0, description="Kelly fraction"
    ),
) -> dict:
    """
    Quick Kelly calculation from summary statistics.

    Use this when you have win rate and average win/loss
    but not individual trade data.
    """
    try:
        # Kelly Formula: K = W - (1-W)/R
        # W = win rate, R = avg_win/avg_loss
        win_loss_ratio = avg_win / avg_loss
        full_kelly = win_rate - (1 - win_rate) / win_loss_ratio
        adjusted_kelly = full_kelly * kelly_fraction

        # Clamp values
        full_kelly = max(0, min(full_kelly, 1.0))
        adjusted_kelly = max(0, min(adjusted_kelly, 0.5))

        return {
            "full_kelly": round(full_kelly, 4),
            "half_kelly": round(full_kelly * 0.5, 4),
            "adjusted_kelly": round(adjusted_kelly, 4),
            "kelly_fraction_used": kelly_fraction,
            "win_rate": win_rate,
            "win_loss_ratio": round(win_loss_ratio, 4),
            "edge": round((win_rate * win_loss_ratio) - (1 - win_rate), 4),
            "recommendation": (
                "Negative edge - avoid trading"
                if full_kelly <= 0
                else f"Recommended position: {adjusted_kelly:.1%} of capital"
            ),
        }

    except Exception as e:
        logger.exception("Quick Kelly calculation failed")
        raise HTTPException(status_code=500, detail=str(e))
