"""
Monte Carlo Simulation API Router.

Provides endpoints for:
- Running Monte Carlo analysis on backtests
- Getting probability distributions
- Risk metric calculations
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

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
