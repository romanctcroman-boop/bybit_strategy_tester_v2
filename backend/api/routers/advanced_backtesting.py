"""
Advanced Backtesting API Router

Provides endpoints for:
- Advanced backtest execution with realistic simulation
- Portfolio backtesting
- Slippage configuration
- Analytics and metrics
- Benchmark comparison

Usage:
    from backend.api.routers.advanced_backtesting import router
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.advanced_backtesting.analytics import (
    analyze_backtest,
)
from backend.services.advanced_backtesting.engine import (
    AdvancedBacktestEngine,
    BacktestConfig,
)
from backend.services.advanced_backtesting.metrics import (
    calculate_metrics,
)
from backend.services.advanced_backtesting.portfolio import (
    AllocationMethod,
    AssetAllocation,
    PortfolioBacktester,
    RebalanceFrequency,
    RebalanceStrategy,
)
from backend.services.advanced_backtesting.slippage import (
    create_slippage_model,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/advanced-backtest", tags=["advanced-backtesting"])


# ============== Request/Response Models ==============


class SlippageConfig(BaseModel):
    """Slippage model configuration."""

    model_type: str = Field(
        default="composite",
        description="Type: fixed, volume_impact, volatility, order_book, composite, adaptive",
    )
    impact_factor: float = Field(default=0.1, ge=0, le=1)
    min_slippage: float = Field(default=0.0001, ge=0)
    max_slippage: float = Field(default=0.05, ge=0, le=0.5)


class AdvancedBacktestRequest(BaseModel):
    """Request for advanced backtest."""

    # Data
    symbol: str = Field(..., description="Trading pair symbol")
    candles: list[dict[str, Any]] = Field(..., description="Candle data")

    # Strategy
    strategy_config: dict[str, Any] = Field(
        default_factory=dict, description="Strategy configuration parameters"
    )

    # Capital & Leverage
    initial_capital: float = Field(default=10000.0, gt=0)
    leverage: float = Field(default=1.0, ge=1, le=125)
    max_position_size: float = Field(default=1.0, gt=0, le=1)

    # Fees
    maker_fee: float = Field(default=0.0002, ge=0, le=0.01)
    taker_fee: float = Field(default=0.0006, ge=0, le=0.01)

    # Slippage
    slippage_config: Optional[SlippageConfig] = None

    # Execution
    fill_model: str = Field(
        default="realistic", description="Fill model: instant, realistic, pessimistic"
    )
    partial_fills: bool = Field(default=True)

    # Risk
    max_drawdown_limit: float = Field(default=0.25, ge=0, le=1)
    daily_loss_limit: float = Field(default=0.05, ge=0, le=1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "candles": [
                    {
                        "open": 50000,
                        "high": 51000,
                        "low": 49000,
                        "close": 50500,
                        "volume": 1000,
                    }
                ],
                "initial_capital": 10000,
                "leverage": 1,
                "slippage_config": {"model_type": "composite", "impact_factor": 0.1},
            }
        }
    }


class AdvancedBacktestResponse(BaseModel):
    """Response from advanced backtest."""

    status: str
    config: dict[str, Any]
    performance: dict[str, Any]
    trades: dict[str, Any]
    costs: dict[str, Any]
    equity_curve: list[float] = Field(default_factory=list)
    all_trades: list[dict[str, Any]] = Field(default_factory=list)
    duration_seconds: float


class PortfolioBacktestRequest(BaseModel):
    """Request for portfolio backtest."""

    # Data for each asset
    asset_data: dict[str, list[dict[str, Any]]] = Field(
        ..., description="Dictionary mapping asset symbols to candle lists"
    )

    # Allocation
    allocation_method: str = Field(
        default="equal_weight",
        description="Method: equal_weight, risk_parity, momentum, min_variance",
    )
    custom_weights: Optional[dict[str, float]] = Field(
        default=None, description="Custom weights if allocation_method is custom"
    )

    # Rebalancing
    rebalance_frequency: str = Field(
        default="monthly",
        description="Frequency: daily, weekly, monthly, quarterly, threshold, never",
    )
    rebalance_threshold: float = Field(
        default=0.05,
        ge=0,
        le=0.5,
        description="Threshold for threshold-based rebalancing",
    )

    # Capital
    initial_capital: float = Field(default=10000.0, gt=0)
    commission: float = Field(default=0.0006, ge=0, le=0.01)

    model_config = {
        "json_schema_extra": {
            "example": {
                "asset_data": {
                    "BTCUSDT": [{"close": 50000, "volume": 1000}],
                    "ETHUSDT": [{"close": 3000, "volume": 5000}],
                },
                "allocation_method": "risk_parity",
                "rebalance_frequency": "monthly",
                "initial_capital": 10000,
            }
        }
    }


class PortfolioBacktestResponse(BaseModel):
    """Response from portfolio backtest."""

    status: str
    config: dict[str, Any]
    performance: dict[str, Any]
    allocation: dict[str, Any]
    correlation: dict[str, Any]
    rebalance_events: list[dict[str, Any]] = Field(default_factory=list)
    equity_curve: list[float] = Field(default_factory=list)
    duration_seconds: float


class AnalyzeBacktestRequest(BaseModel):
    """Request for backtest analysis."""

    backtest_results: dict[str, Any] = Field(
        ..., description="Backtest results to analyze"
    )


class AnalyzeBacktestResponse(BaseModel):
    """Response from backtest analysis."""

    summary: dict[str, Any]
    trade_analysis: dict[str, Any]
    performance_attribution: dict[str, Any]
    drawdown_analysis: dict[str, Any]
    generated_at: str


class MetricsRequest(BaseModel):
    """Request for metrics calculation."""

    equity_curve: list[float] = Field(..., description="Portfolio value series")
    trades: Optional[list[dict[str, Any]]] = Field(default=None)
    benchmark_returns: Optional[list[float]] = Field(
        default=None, description="Benchmark return series for comparison"
    )
    benchmark_name: str = Field(default="Benchmark")


class MetricsResponse(BaseModel):
    """Response from metrics calculation."""

    risk_adjusted: dict[str, Any]
    rolling: dict[str, Any]
    trade_metrics: dict[str, Any]
    benchmark_comparison: Optional[dict[str, Any]] = None
    calculated_at: str


class SlippageEstimateRequest(BaseModel):
    """Request for slippage estimation."""

    price: float = Field(..., gt=0)
    order_size: float = Field(..., gt=0)
    side: str = Field(..., description="buy or sell")
    volume: float = Field(default=1_000_000, gt=0)
    volatility: float = Field(default=0.02, ge=0, le=1)
    slippage_config: Optional[SlippageConfig] = None


class SlippageEstimateResponse(BaseModel):
    """Response from slippage estimation."""

    slippage_pct: float
    slippage_amount: float
    execution_price: float
    original_price: float
    model_type: str
    components: dict[str, float]


# ============== API Endpoints ==============


@router.post("/run", response_model=AdvancedBacktestResponse)
async def run_advanced_backtest(
    request: AdvancedBacktestRequest,
) -> AdvancedBacktestResponse:
    """
    Run advanced backtest with realistic simulation.

    Features:
    - Configurable slippage models
    - Realistic fill simulation
    - Position and risk management
    - Detailed trade analytics
    """
    try:
        # Create slippage model
        slippage_config = request.slippage_config or SlippageConfig()
        slippage_model = create_slippage_model(
            model_type=slippage_config.model_type,
            impact_factor=slippage_config.impact_factor,
            min_slippage=slippage_config.min_slippage,
            max_slippage=slippage_config.max_slippage,
        )

        # Create engine config
        config = BacktestConfig(
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            max_position_size=request.max_position_size,
            maker_fee=request.maker_fee,
            taker_fee=request.taker_fee,
            slippage_model=slippage_model,
            fill_model=request.fill_model,
            partial_fills=request.partial_fills,
            max_drawdown_limit=request.max_drawdown_limit,
            daily_loss_limit=request.daily_loss_limit,
        )

        # Create engine
        engine = AdvancedBacktestEngine(config)

        # Define simple strategy runner from config
        def strategy_func(candle: dict, state: dict) -> Optional[dict]:
            """Simple strategy based on config signals."""
            strategy_config = request.strategy_config

            # Check for signal in config (for testing)
            if "signals" in strategy_config:
                idx = candle.get("index", 0)
                signals = strategy_config.get("signals", [])
                if idx < len(signals):
                    return signals[idx]

            # Default: no signal
            return None

        # Add index to candles
        for i, candle in enumerate(request.candles):
            candle["index"] = i
            candle["symbol"] = request.symbol

        # Run backtest
        results = engine.run(request.candles, strategy_func, request.strategy_config)

        return AdvancedBacktestResponse(
            status=results.get("status", "completed"),
            config=results.get("config", {}),
            performance=results.get("performance", {}),
            trades=results.get("trades", {}),
            costs=results.get("costs", {}),
            equity_curve=results.get("equity_curve", [])[-1000:],  # Limit size
            all_trades=results.get("all_trades", [])[-100:],  # Last 100 trades
            duration_seconds=results.get("duration_seconds", 0),
        )

    except Exception as e:
        logger.error(f"Advanced backtest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio", response_model=PortfolioBacktestResponse)
async def run_portfolio_backtest_endpoint(
    request: PortfolioBacktestRequest,
) -> PortfolioBacktestResponse:
    """
    Run multi-asset portfolio backtest.

    Features:
    - Multiple allocation methods
    - Automatic rebalancing
    - Correlation analysis
    - Risk metrics
    """
    try:
        # Create backtester
        assets = list(request.asset_data.keys())
        backtester = PortfolioBacktester(
            assets=assets,
            initial_capital=request.initial_capital,
            commission=request.commission,
        )

        # Create allocation
        allocation = AssetAllocation(
            method=AllocationMethod(request.allocation_method),
        )

        # Use custom weights if provided
        if request.custom_weights and request.allocation_method == "custom":
            allocation.weights = request.custom_weights
            allocation.method = AllocationMethod.CUSTOM

        # Create rebalance strategy
        rebalance = RebalanceStrategy(
            frequency=RebalanceFrequency(request.rebalance_frequency),
            threshold=request.rebalance_threshold,
        )

        # Run backtest
        results = backtester.run(request.asset_data, allocation, rebalance)

        return PortfolioBacktestResponse(
            status=results.get("status", "completed"),
            config=results.get("config", {}),
            performance=results.get("performance", {}),
            allocation=results.get("allocation", {}),
            correlation=results.get("correlation", {}),
            rebalance_events=results.get("rebalance_events", [])[-50:],
            equity_curve=results.get("equity_curve", [])[-1000:],
            duration_seconds=results.get("duration_seconds", 0),
        )

    except Exception as e:
        logger.error(f"Portfolio backtest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=AnalyzeBacktestResponse)
async def analyze_backtest_endpoint(
    request: AnalyzeBacktestRequest,
) -> AnalyzeBacktestResponse:
    """
    Analyze backtest results.

    Provides:
    - Trade analysis and statistics
    - Performance attribution
    - Drawdown analysis
    - Risk metrics
    """
    try:
        report = analyze_backtest(request.backtest_results)

        return AnalyzeBacktestResponse(
            summary=report.get("summary", {}),
            trade_analysis=report.get("trade_analysis", {}),
            performance_attribution=report.get("performance_attribution", {}),
            drawdown_analysis=report.get("drawdown_analysis", {}),
            generated_at=report.get(
                "generated_at", datetime.now(timezone.utc).isoformat()
            ),
        )

    except Exception as e:
        logger.error(f"Backtest analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics", response_model=MetricsResponse)
async def calculate_metrics_endpoint(
    request: MetricsRequest,
) -> MetricsResponse:
    """
    Calculate comprehensive performance metrics.

    Provides:
    - Risk-adjusted metrics (Sharpe, Sortino, etc.)
    - Rolling metrics
    - Trade metrics
    - Benchmark comparison
    """
    try:
        result = calculate_metrics(
            equity_curve=request.equity_curve,
            trades=request.trades,
            benchmark_returns=request.benchmark_returns,
            benchmark_name=request.benchmark_name,
        )

        return MetricsResponse(
            risk_adjusted=result.get("risk_adjusted", {}),
            rolling=result.get("rolling", {}),
            trade_metrics=result.get("trade_metrics", {}),
            benchmark_comparison=result.get("benchmark_comparison"),
            calculated_at=result.get(
                "calculated_at", datetime.now(timezone.utc).isoformat()
            ),
        )

    except Exception as e:
        logger.error(f"Metrics calculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slippage/estimate", response_model=SlippageEstimateResponse)
async def estimate_slippage(
    request: SlippageEstimateRequest,
) -> SlippageEstimateResponse:
    """
    Estimate slippage for an order.

    Useful for:
    - Pre-trade analysis
    - Order optimization
    - Cost estimation
    """
    try:
        slippage_config = request.slippage_config or SlippageConfig()
        model = create_slippage_model(
            model_type=slippage_config.model_type,
            impact_factor=slippage_config.impact_factor,
            min_slippage=slippage_config.min_slippage,
            max_slippage=slippage_config.max_slippage,
        )

        result = model.calculate(
            price=request.price,
            order_size=request.order_size,
            side=request.side,
            volume=request.volume,
            volatility=request.volatility,
        )

        return SlippageEstimateResponse(
            slippage_pct=round(result.slippage_pct * 100, 4),
            slippage_amount=round(result.slippage_amount, 8),
            execution_price=round(result.execution_price, 8),
            original_price=request.price,
            model_type=result.model_type.value,
            components={k: round(v * 100, 4) for k, v in result.components.items()},
        )

    except Exception as e:
        logger.error(f"Slippage estimation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slippage/models")
async def list_slippage_models() -> dict[str, Any]:
    """List available slippage models."""
    return {
        "models": [
            {
                "type": "fixed",
                "description": "Fixed percentage slippage",
                "parameters": ["slippage_pct"],
            },
            {
                "type": "volume_impact",
                "description": "Slippage based on order size relative to volume",
                "parameters": ["impact_factor", "min_slippage", "max_slippage"],
            },
            {
                "type": "volatility",
                "description": "Slippage scales with market volatility",
                "parameters": ["base_slippage", "volatility_multiplier"],
            },
            {
                "type": "order_book",
                "description": "Simulates order book depth impact",
                "parameters": ["spread_multiplier", "depth_factor"],
            },
            {
                "type": "composite",
                "description": "Combines multiple slippage factors",
                "parameters": ["model weights"],
            },
            {
                "type": "adaptive",
                "description": "Dynamically adjusts based on conditions",
                "parameters": ["time_multipliers", "regime_multipliers"],
            },
        ],
        "default": "composite",
    }


@router.get("/allocation/methods")
async def list_allocation_methods() -> dict[str, Any]:
    """List available portfolio allocation methods."""
    return {
        "methods": [
            {
                "id": "equal_weight",
                "name": "Equal Weight",
                "description": "Allocate equally to all assets",
            },
            {
                "id": "risk_parity",
                "name": "Risk Parity",
                "description": "Weight inversely by volatility",
            },
            {
                "id": "momentum",
                "name": "Momentum",
                "description": "Weight by recent performance",
            },
            {
                "id": "min_variance",
                "name": "Minimum Variance",
                "description": "Minimize portfolio variance",
            },
            {
                "id": "max_sharpe",
                "name": "Maximum Sharpe",
                "description": "Maximize risk-adjusted returns",
            },
            {
                "id": "custom",
                "name": "Custom Weights",
                "description": "User-defined weights",
            },
        ],
        "default": "equal_weight",
    }


@router.get("/rebalance/frequencies")
async def list_rebalance_frequencies() -> dict[str, Any]:
    """List available rebalancing frequencies."""
    return {
        "frequencies": [
            {"id": "daily", "name": "Daily", "interval_bars": 1},
            {"id": "weekly", "name": "Weekly", "interval_bars": 7},
            {"id": "monthly", "name": "Monthly", "interval_bars": 30},
            {"id": "quarterly", "name": "Quarterly", "interval_bars": 90},
            {
                "id": "threshold",
                "name": "Threshold-based",
                "description": "Rebalance when drift exceeds threshold",
            },
            {"id": "never", "name": "Never", "description": "Buy and hold"},
        ],
        "default": "monthly",
    }


@router.get("/fill-models")
async def list_fill_models() -> dict[str, Any]:
    """List available order fill models."""
    return {
        "models": [
            {
                "id": "instant",
                "name": "Instant Fill",
                "description": "Orders fill immediately at current price",
            },
            {
                "id": "realistic",
                "name": "Realistic Fill",
                "description": "Simulates market impact and partial fills",
            },
            {
                "id": "pessimistic",
                "name": "Pessimistic Fill",
                "description": "Conservative fill assumptions",
            },
        ],
        "default": "realistic",
    }


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "advanced-backtesting",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
