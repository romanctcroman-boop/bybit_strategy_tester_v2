"""
📊 Multi-Symbol Portfolio API Router

REST API for portfolio optimization and analysis:
- POST /portfolio/optimize - Run portfolio optimization
- GET /portfolio/correlation - Get correlation matrix
- GET /portfolio/efficient-frontier - Get efficient frontier
- POST /portfolio/risk-parity - Risk parity allocation

Example request:
```json
{
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "timeframe": "1h",
  "start_date": "2025-01-01",
  "end_date": "2025-01-31",
  "strategy_type": "rsi",
  "strategy_params": {"period": 14},
  "rebalance_frequency": "monthly"
}
```
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.backtesting.strategies import RSIStrategy
from backend.services.data_service import DataService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Portfolio Optimization"])

# Configuration constants
MAX_SYMBOLS = 20
MAX_DATE_RANGE_DAYS = 365
MAX_EFFICIENT_FRONTIER_POINTS = 100


class PortfolioOptimizationRequest(BaseModel):
    """Request for portfolio optimization"""

    symbols: list[str] = Field(..., description="List of symbols", max_length=MAX_SYMBOLS)
    timeframe: str = Field(default="1h", description="Candlestick timeframe")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")

    strategy_type: str = Field(default="rsi", description="Strategy type")
    strategy_params: dict[str, Any] = Field(default_factory=dict)

    # Portfolio config
    weights: dict[str, float] | None = Field(default=None)
    rebalance_frequency: str = Field(default="monthly")
    initial_capital: float = Field(default=10000.0)
    commission: float = Field(default=0.0007)

    # Optimization method
    method: str = Field(default="risk_parity", description="risk_parity, sharpe, min_volatility")

    @classmethod
    def validate_dates(cls, values):
        """Validate date range"""
        start = values.get('start_date')
        end = values.get('end_date')
        if start and end:
            start_date = datetime.strptime(start, '%Y-%m-%d')
            end_date = datetime.strptime(end, '%Y-%m-%d')
            if (end_date - start_date).days > MAX_DATE_RANGE_DAYS:
                raise ValueError(f"Date range cannot exceed {MAX_DATE_RANGE_DAYS} days")
        return values


class PortfolioOptimizationResponse(BaseModel):
    """Response for portfolio optimization"""

    success: bool
    metrics: dict[str, float]
    weights: dict[str, float]
    symbol_results: dict[str, dict[str, Any]]
    correlation_matrix: dict[str, dict[str, float]]
    diversification_ratio: float
    execution_time: float


class CorrelationRequest(BaseModel):
    """Request for correlation analysis"""

    symbols: list[str] = Field(..., description="List of symbols", max_length=MAX_SYMBOLS)
    timeframe: str = Field(default="1h")
    start_date: str
    end_date: str
    window: int = Field(default=30, description="Rolling window")


class CorrelationResponse(BaseModel):
    """Correlation analysis response"""

    correlation_matrix: dict[str, dict[str, float]]
    rolling_correlations: dict[str, list[float]]
    cointegration_pairs: list[dict[str, Any]]
    diversification_ratio: float
    low_corr_pairs: list[dict[str, Any]]
    high_corr_pairs: list[dict[str, Any]]


class RiskParityRequest(BaseModel):
    """Risk parity allocation request"""

    symbols: list[str] = Field(..., max_length=MAX_SYMBOLS)
    timeframe: str = Field(default="1h")
    start_date: str
    end_date: str
    method: str = Field(default="risk_parity")
    max_weight: float = Field(default=0.4)
    min_weight: float = Field(default=0.0)


class RiskParityResponse(BaseModel):
    """Risk parity allocation response"""

    weights: dict[str, float]
    risk_contributions: dict[str, float]
    total_risk: float
    diversification_ratio: float
    method: str


class EfficientFrontierRequest(BaseModel):
    """Efficient frontier request"""

    symbols: list[str] = Field(..., max_length=MAX_SYMBOLS)
    timeframe: str = Field(default="1h")
    start_date: str
    end_date: str
    n_points: int = Field(default=50, le=MAX_EFFICIENT_FRONTIER_POINTS)


class EfficientFrontierResponse(BaseModel):
    """Efficient frontier response"""

    volatilities: list[float]
    returns: list[float]
    sharpe_ratios: list[float]
    weights: list[dict[str, float]]


@router.post("/optimize", response_model=PortfolioOptimizationResponse)
async def optimize_portfolio(request: PortfolioOptimizationRequest):
    """
    Run portfolio optimization.

    Optimizes weights across multiple symbols using:
    - Risk parity
    - Sharpe ratio maximization
    - Minimum volatility
    """
    start_time = datetime.now()

    try:
        # Load data
        data_service = DataService()
        data_dict = {}

        for symbol in request.symbols:
            data = data_service.load_ohlcv(
                symbol=symbol,
                timeframe=request.timeframe,
                start=request.start_date,
                end=request.end_date,
            )

            if data.empty:
                raise HTTPException(status_code=400, detail=f"No data for {symbol}")

            data_dict[symbol] = data

        # Import portfolio engine
        from backend.backtesting.portfolio import (
            PortfolioBacktestEngine,
            PortfolioConfig,
            RiskParityAllocator,
        )

        # Run portfolio backtest
        engine = PortfolioBacktestEngine()

        config = PortfolioConfig(
            symbols=request.symbols,
            weights=request.weights,
            rebalance_frequency=request.rebalance_frequency,
            initial_capital=request.initial_capital,
            commission=request.commission,
        )

        # Get strategy class (currently only RSIStrategy is supported)
        strategy_class = RSIStrategy

        result = engine.run(
            strategy_class=strategy_class,
            data_dict=data_dict,
            config=config,
            strategy_params=request.strategy_params,
        )

        # Risk parity optimization
        returns_dict = {symbol: data_dict[symbol]["close"].pct_change().dropna() for symbol in request.symbols}

        allocator = RiskParityAllocator(
            max_weight=0.4,
            min_weight=0.05,
        )

        rp_result = allocator.allocate(
            returns=pd.DataFrame(returns_dict),
            method=request.method,
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        return PortfolioOptimizationResponse(
            success=True,
            metrics=result.metrics,
            weights=rp_result.weights,
            symbol_results={
                symbol: {
                    "sharpe": res.metrics.get("sharpe_ratio", 0),
                    "return": res.metrics.get("total_return", 0),
                    "trades": len(res.trades),
                }
                for symbol, res in result.symbol_results.items()
            },
            correlation_matrix=result.correlation_matrix.to_dict(),
            diversification_ratio=rp_result.diversification_ratio,
            execution_time=execution_time,
        )

    except Exception as e:
        logger.error(f"Portfolio optimization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correlation", response_model=CorrelationResponse)
async def get_correlation_analysis(request: CorrelationRequest):
    """
    Get correlation analysis for symbols.

    Returns correlation matrix, rolling correlations, and cointegration tests.
    """
    try:
        # Load data
        data_service = DataService()
        price_dict = {}

        for symbol in request.symbols:
            data = data_service.load_ohlcv(
                symbol=symbol,
                timeframe=request.timeframe,
                start=request.start_date,
                end=request.end_date,
            )

            if data.empty:
                raise HTTPException(status_code=400, detail=f"No data for {symbol}")

            price_dict[symbol] = data["close"]

        # Correlation analysis
        from backend.backtesting.portfolio import CorrelationAnalysis

        analyzer = CorrelationAnalysis(window=request.window)
        result = analyzer.calculate_all(price_dict)

        # Low/high correlation pairs
        low_pairs = analyzer.get_low_correlation_pairs(result.correlation_matrix, threshold=0.5)
        high_pairs = analyzer.get_high_correlation_pairs(result.correlation_matrix, threshold=0.7)

        # Cointegration pairs
        coint_pairs = []
        if result.cointegration_tests:
            for pair, p_value in result.cointegration_tests.items():
                coint_pairs.append(
                    {
                        "pair": pair,
                        "p_value": p_value,
                        "is_cointegrated": p_value < 0.05,
                    }
                )

        # Rolling correlations (convert to list)
        rolling_corrs = {}
        for pair, series in (result.rolling_correlations or {}).items():
            rolling_corrs[pair] = series.dropna().tolist()[-100:]  # Last 100 values

        return CorrelationResponse(
            correlation_matrix=result.correlation_matrix.to_dict(),
            rolling_correlations=rolling_corrs,
            cointegration_pairs=coint_pairs,
            diversification_ratio=result.diversification_ratio,
            low_corr_pairs=[{"symbol1": p[0], "symbol2": p[1], "correlation": p[2]} for p in low_pairs[:10]],
            high_corr_pairs=[{"symbol1": p[0], "symbol2": p[1], "correlation": p[2]} for p in high_pairs[:10]],
        )

    except Exception as e:
        logger.error(f"Correlation analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk-parity", response_model=RiskParityResponse)
async def get_risk_parity(request: RiskParityRequest):
    """
    Get risk parity allocation.
    """
    try:
        # Load data
        data_service = DataService()
        returns_dict = {}

        for symbol in request.symbols:
            data = data_service.load_ohlcv(
                symbol=symbol,
                timeframe=request.timeframe,
                start=request.start_date,
                end=request.end_date,
            )

            if data.empty:
                raise HTTPException(status_code=400, detail=f"No data for {symbol}")

            returns_dict[symbol] = data["close"].pct_change().dropna()

        # Risk parity
        from backend.backtesting.portfolio import RiskParityAllocator

        allocator = RiskParityAllocator(
            max_weight=request.max_weight,
            min_weight=request.min_weight,
        )

        result = allocator.allocate(
            returns=pd.DataFrame(returns_dict),
            method=request.method,
        )

        return RiskParityResponse(
            weights=result.weights,
            risk_contributions=result.risk_contributions,
            total_risk=result.total_risk,
            diversification_ratio=result.diversification_ratio,
            method=request.method,
        )

    except Exception as e:
        logger.error(f"Risk parity failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/efficient-frontier", response_model=EfficientFrontierResponse)
async def get_efficient_frontier(request: EfficientFrontierRequest):
    """
    Get efficient frontier.

    Returns portfolio points along the efficient frontier.
    """
    try:
        # Load data
        data_service = DataService()
        returns_dict = {}

        for symbol in request.symbols:
            data = data_service.load_ohlcv(
                symbol=symbol,
                timeframe=request.timeframe,
                start=request.start_date,
                end=request.end_date,
            )

            if data.empty:
                raise HTTPException(status_code=400, detail=f"No data for {symbol}")

            returns_dict[symbol] = data["close"].pct_change().dropna()

        # Efficient frontier
        from backend.backtesting.portfolio import RiskParityAllocator

        allocator = RiskParityAllocator()

        volatilities, returns, weights_list = allocator.efficient_frontier(
            returns=pd.DataFrame(returns_dict),
            n_points=request.n_points,
        )

        # Sharpe ratios
        risk_free_rate = 0.0
        sharpe_ratios = [
            (ret - risk_free_rate) / vol if vol > 0 else 0 for ret, vol in zip(returns, volatilities, strict=False)
        ]

        return EfficientFrontierResponse(
            volatilities=volatilities,
            returns=returns,
            sharpe_ratios=sharpe_ratios,
            weights=weights_list,
        )

    except Exception as e:
        logger.error(f"Efficient frontier failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
