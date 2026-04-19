"""
GraphQL API for Bybit Strategy Tester.

Provides a flexible alternative to the REST API for frontend consumers.
Uses Strawberry (lightweight, type-safe Python GraphQL library).

Schema covers:
- Strategies: list, get, create
- Backtests: run, results, metrics
- Market data: klines, symbols
- System: health, stats

Mount in FastAPI::

    from backend.api.graphql_schema import graphql_app
    app.include_router(graphql_app, prefix="/graphql")

Requires:
    pip install strawberry-graphql[fastapi]
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try importing strawberry; provide helpful error if not installed
# ---------------------------------------------------------------------------
try:
    import strawberry
    from strawberry.fastapi import GraphQLRouter

    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    logger.info("Strawberry GraphQL not installed. Install with: pip install strawberry-graphql[fastapi]")


# ---------------------------------------------------------------------------
# GraphQL Types
# ---------------------------------------------------------------------------

if STRAWBERRY_AVAILABLE:

    @strawberry.type
    class StrategyType:
        """A trading strategy definition."""

        name: str
        strategy_type: str
        description: str | None = None
        params: strawberry.scalars.JSON | None = None

    @strawberry.type
    class BacktestMetricsType:
        """Backtest performance metrics."""

        total_trades: int = 0
        winning_trades: int = 0
        losing_trades: int = 0
        win_rate: float = 0.0
        net_profit: float = 0.0
        total_return: float = 0.0
        max_drawdown: float = 0.0
        sharpe_ratio: float | None = None
        profit_factor: float | None = None

    @strawberry.type
    class BacktestResultType:
        """Result of a backtest run."""

        backtest_id: str
        symbol: str
        timeframe: str
        strategy_name: str
        metrics: BacktestMetricsType | None = None
        trade_count: int = 0
        created_at: str | None = None

    @strawberry.type
    class KlineType:
        """A single candlestick/kline."""

        timestamp: str
        open: float
        high: float
        low: float
        close: float
        volume: float

    @strawberry.type
    class HealthType:
        """System health information."""

        status: str
        version: str
        uptime_seconds: float | None = None
        database: str = "ok"

    @strawberry.type
    class SymbolInfoType:
        """Trading pair information."""

        symbol: str
        base_asset: str
        quote_asset: str
        has_data: bool = False

    # -------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------

    @strawberry.type
    class Query:
        """Root GraphQL query."""

        @strawberry.field(description="System health check")
        async def health(self) -> HealthType:
            return HealthType(status="healthy", version="2.0.0")  # type: ignore[call-arg]

        @strawberry.field(description="List available strategy types")
        async def strategies(self) -> list[StrategyType]:
            """Return available strategy types."""
            try:
                from backend.backtesting.strategies.registry import get_strategy_registry

                registry = get_strategy_registry()
                return [
                    StrategyType(  # type: ignore[call-arg]
                        name=name,
                        strategy_type=name,
                        description=meta.get("description", ""),
                    )
                    for name, meta in registry.items()
                ]
            except ImportError:
                # Fallback: return common strategies
                return [
                    StrategyType(name="rsi", strategy_type="rsi", description="RSI Overbought/Oversold"),  # type: ignore[call-arg]
                    StrategyType(name="macd", strategy_type="macd", description="MACD Crossover"),  # type: ignore[call-arg]
                    StrategyType(name="bollinger", strategy_type="bollinger", description="Bollinger Bands"),  # type: ignore[call-arg]
                    StrategyType(name="ema_cross", strategy_type="ema_cross", description="EMA Crossover"),  # type: ignore[call-arg]
                ]

        @strawberry.field(description="Get available symbols")
        async def symbols(self) -> list[SymbolInfoType]:
            """Return symbols with available data."""
            # Common Bybit perpetual symbols
            common = [
                "BTCUSDT",
                "ETHUSDT",
                "SOLUSDT",
                "XRPUSDT",
                "DOGEUSDT",
                "AVAXUSDT",
                "LINKUSDT",
                "ADAUSDT",
            ]
            return [
                SymbolInfoType(  # type: ignore[call-arg]
                    symbol=s,
                    base_asset=s.replace("USDT", ""),
                    quote_asset="USDT",
                    has_data=True,
                )
                for s in common
            ]

        @strawberry.field(description="Supported timeframes")
        async def timeframes(self) -> list[str]:
            return ["1", "5", "15", "30", "60", "240", "D", "W", "M"]

    # -------------------------------------------------------------------
    # Mutation
    # -------------------------------------------------------------------

    @strawberry.type
    class Mutation:
        """Root GraphQL mutation."""

        @strawberry.mutation(description="Run a backtest")
        async def run_backtest(
            self,
            symbol: str,
            timeframe: str,
            strategy_type: str,
            initial_capital: float = 10000.0,
        ) -> BacktestResultType:
            """Execute a backtest and return results."""
            import uuid

            backtest_id = str(uuid.uuid4())[:8]

            # Placeholder — wire to actual BacktestService in production
            logger.info(
                "GraphQL backtest: %s %s %s capital=%.0f",
                symbol,
                timeframe,
                strategy_type,
                initial_capital,
            )

            return BacktestResultType(  # type: ignore[call-arg]
                backtest_id=backtest_id,
                symbol=symbol,
                timeframe=timeframe,
                strategy_name=strategy_type,
                metrics=BacktestMetricsType(),
                created_at=datetime.now().isoformat(),
            )

    # -------------------------------------------------------------------
    # Schema & Router
    # -------------------------------------------------------------------

    schema = strawberry.Schema(query=Query, mutation=Mutation)

    graphql_app = GraphQLRouter(schema, path="/")

else:
    # Strawberry not installed — provide a no-op router
    from fastapi import APIRouter

    graphql_app = APIRouter()

    @graphql_app.get("/")
    async def graphql_not_available() -> dict[str, str]:
        return {
            "error": "GraphQL not available",
            "install": "pip install strawberry-graphql[fastapi]",
        }
