"""
Walk-Forward Optimization API Router.

Provides endpoints for:
- Running walk-forward validation on strategies
- Getting robustness analysis
- Parameter optimization recommendations
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.walk_forward import WalkForwardOptimizer, simple_strategy_runner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/walk-forward", tags=["walk-forward"])


class WalkForwardRequest(BaseModel):
    """Request model for walk-forward optimization."""

    candles: list[dict[str, Any]] = Field(
        ...,
        description="List of candle dictionaries with open_time, open, high, low, close, volume",
        min_length=100,
    )
    param_grid: dict[str, list[Any]] = Field(
        ...,
        description="Parameter grid to optimize (e.g., {'lookback': [10, 20, 30]})",
    )
    n_splits: int = Field(
        default=5,
        ge=2,
        le=20,
        description="Number of walk-forward windows",
    )
    train_ratio: float = Field(
        default=0.7,
        ge=0.5,
        le=0.9,
        description="Ratio of data for training in each window",
    )
    initial_capital: float = Field(
        default=10000.0,
        gt=0,
        description="Initial capital for backtesting",
    )
    optimization_metric: str = Field(
        default="sharpe",
        description="Metric to optimize: 'return', 'sharpe', or 'calmar'",
    )


class WindowResult(BaseModel):
    """Single window result."""

    window_id: int
    train_period: dict[str, str | None]
    test_period: dict[str, str | None]
    train_metrics: dict[str, float]
    test_metrics: dict[str, float]
    best_params: dict[str, Any]
    degradation: dict[str, float]


class WalkForwardResponse(BaseModel):
    """Response model for walk-forward optimization."""

    config: dict[str, Any]
    aggregate_metrics: dict[str, dict[str, float]]
    robustness: dict[str, float]
    recommendation: dict[str, Any]
    windows: list[dict[str, Any]]
    optimization_time_ms: float


class QuickValidationRequest(BaseModel):
    """Quick validation request using summary data."""

    train_returns: list[float] = Field(
        ...,
        description="Training period returns per window",
        min_length=2,
    )
    test_returns: list[float] = Field(
        ...,
        description="Testing period returns per window (same length as train)",
        min_length=2,
    )
    param_sets: list[dict[str, Any]] = Field(
        default=[],
        description="Optional: best params for each window",
    )


class ValidationMetrics(BaseModel):
    """Validation metrics response."""

    n_windows: int
    avg_train_return_pct: float
    avg_test_return_pct: float
    consistency_ratio_pct: float
    overfit_score: float
    confidence: str
    recommendation: str


@router.post("/optimize", response_model=WalkForwardResponse)
async def run_walk_forward_optimization(
    request: WalkForwardRequest,
) -> WalkForwardResponse:
    """
    Run walk-forward optimization on strategy.

    Splits data into multiple train/test windows, optimizes parameters
    on training data, and validates on out-of-sample test data.

    Use this to:
    - Detect overfitting
    - Find robust parameters
    - Validate strategy across different market conditions
    """
    try:
        optimizer = WalkForwardOptimizer(
            n_splits=request.n_splits,
            train_ratio=request.train_ratio,
        )

        # Use simple strategy runner for now
        # In production, this would use actual strategy classes
        result = optimizer.optimize(
            data=request.candles,
            strategy_runner=simple_strategy_runner,
            param_grid=request.param_grid,
            initial_capital=request.initial_capital,
            metric=request.optimization_metric,
        )

        return WalkForwardResponse(**result.to_dict())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Walk-forward optimization failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-validate", response_model=ValidationMetrics)
async def quick_validation(request: QuickValidationRequest) -> ValidationMetrics:
    """
    Quick validation from pre-computed train/test returns.

    Use this when you already have walk-forward results from
    external backtesting and want robustness analysis.
    """
    try:
        if len(request.train_returns) != len(request.test_returns):
            raise HTTPException(
                status_code=400,
                detail="train_returns and test_returns must have same length",
            )

        n = len(request.train_returns)

        # Calculate metrics
        avg_train = sum(request.train_returns) / n
        avg_test = sum(request.test_returns) / n

        # Consistency: positive test returns
        positive_tests = sum(1 for r in request.test_returns if r > 0)
        consistency = positive_tests / n

        # Average degradation
        degradations = []
        for train, test in zip(request.train_returns, request.test_returns):
            if train != 0:
                degradations.append(test / train - 1)
        avg_deg = sum(degradations) / len(degradations) if degradations else 0

        # Overfit score
        overfit = min(
            1.0,
            max(
                0.0,
                0.5 * (1 - consistency)
                + 0.3 * min(1.0, abs(avg_deg))
                + 0.2 * (1 if avg_test < 0 else 0),
            ),
        )

        # Confidence and recommendation
        if overfit < 0.2 and consistency >= 0.8:
            confidence = "high"
            rec = "Strategy shows consistent out-of-sample performance. Safe to deploy with recommended parameters."
        elif overfit < 0.4 and consistency >= 0.6:
            confidence = "medium"
            rec = "Strategy shows moderate robustness. Consider additional validation before live trading."
        else:
            confidence = "low"
            rec = "Strategy shows signs of overfitting. Review parameters and consider simplification."

        return ValidationMetrics(
            n_windows=n,
            avg_train_return_pct=round(avg_train * 100, 2),
            avg_test_return_pct=round(avg_test * 100, 2),
            consistency_ratio_pct=round(consistency * 100, 2),
            overfit_score=round(overfit, 3),
            confidence=confidence,
            recommendation=rec,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Quick validation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_default_config() -> dict:
    """
    Get default walk-forward configuration and guidelines.
    """
    return {
        "defaults": {
            "n_splits": 5,
            "train_ratio": 0.7,
            "gap_periods": 0,
            "optimization_metric": "sharpe",
        },
        "guidelines": {
            "minimum_data": "At least 100 candles per window recommended",
            "n_splits_recommendation": "5-10 splits for daily data, 3-5 for intraday",
            "train_ratio_recommendation": "0.6-0.8 depending on data availability",
            "interpretation": {
                "consistency_ratio": "> 80% = Good, 60-80% = Moderate, < 60% = Poor",
                "overfit_score": "< 0.2 = Low risk, 0.2-0.4 = Moderate, > 0.4 = High risk",
                "degradation": "< 20% normal, 20-50% concerning, > 50% likely overfit",
            },
        },
        "supported_metrics": [
            {"name": "return", "description": "Total return"},
            {"name": "sharpe", "description": "Sharpe ratio (risk-adjusted)"},
            {"name": "calmar", "description": "Return / Max Drawdown"},
        ],
    }


@router.post("/analyze-robustness")
async def analyze_robustness(
    train_sharpe: float = Query(..., description="Training Sharpe ratio"),
    test_sharpe: float = Query(..., description="Test Sharpe ratio"),
    train_return: float = Query(..., description="Training return (decimal)"),
    test_return: float = Query(..., description="Test return (decimal)"),
    n_windows: int = Query(default=5, ge=1, description="Number of windows tested"),
    positive_windows: int = Query(
        ..., ge=0, description="Windows with positive test return"
    ),
) -> dict:
    """
    Quick robustness analysis from summary statistics.
    """
    if positive_windows > n_windows:
        raise HTTPException(
            status_code=400,
            detail="positive_windows cannot exceed n_windows",
        )

    consistency = positive_windows / n_windows

    sharpe_deg = (test_sharpe / train_sharpe - 1) if train_sharpe != 0 else 0
    return_deg = (test_return / train_return - 1) if train_return != 0 else 0

    overfit_score = min(
        1.0,
        max(
            0.0,
            0.4 * (1 - consistency)
            + 0.3 * min(1.0, abs(return_deg))
            + 0.3 * min(1.0, abs(sharpe_deg)),
        ),
    )

    if overfit_score < 0.2:
        assessment = "Excellent - Low overfitting risk"
        color = "green"
    elif overfit_score < 0.4:
        assessment = "Good - Moderate overfitting risk"
        color = "yellow"
    elif overfit_score < 0.6:
        assessment = "Fair - Elevated overfitting risk"
        color = "orange"
    else:
        assessment = "Poor - High overfitting risk"
        color = "red"

    return {
        "metrics": {
            "consistency_ratio_pct": round(consistency * 100, 2),
            "sharpe_degradation_pct": round(sharpe_deg * 100, 2),
            "return_degradation_pct": round(return_deg * 100, 2),
            "overfit_score": round(overfit_score, 3),
        },
        "assessment": {
            "text": assessment,
            "color": color,
            "score": round((1 - overfit_score) * 100, 1),  # 0-100, higher is better
        },
        "recommendations": [
            "Increase training period if overfit score > 0.4",
            "Simplify strategy if parameters are unstable",
            "Add more walk-forward windows for better validation",
        ]
        if overfit_score > 0.3
        else [
            "Strategy appears robust",
            "Monitor live performance against test metrics",
        ],
    }
