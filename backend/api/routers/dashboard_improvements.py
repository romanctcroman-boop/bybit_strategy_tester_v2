"""
Dashboard Improvements API - Milestone 4.4

Additional endpoints for:
- Portfolio history with persistent storage
- Dynamic AI recommendations
- Real-time P&L streaming
- Strategy performance leaderboard
"""

import asyncio
import contextlib
import random
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.database.models import Backtest, BacktestStatus, Strategy
from backend.utils.time import utc_now

router = APIRouter(prefix="/dashboard", tags=["Dashboard Improvements"])


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        logger.error(f"Failed to create DB session: {e}")
        db.close()
        raise


# ==============================================================================
# Portfolio History Models
# ==============================================================================


class PortfolioDataPoint(BaseModel):
    """Single portfolio data point"""

    timestamp: datetime
    equity: float
    pnl: float
    pnl_pct: float
    drawdown: float
    positions_count: int


class PortfolioHistoryResponse(BaseModel):
    """Portfolio history response"""

    period: str
    data_points: list[PortfolioDataPoint]
    summary: dict[str, Any]


# ==============================================================================
# Portfolio History Endpoint
# ==============================================================================


@router.get("/portfolio/history")
async def get_portfolio_history(
    period: str = Query("7d", description="Period: 1d, 7d, 30d, 90d, all"),
    resolution: str = Query("1h", description="Resolution: 15m, 1h, 4h, 1d"),
) -> PortfolioHistoryResponse:
    """
    📈 Portfolio performance history

    Returns historical portfolio equity curve and P&L data.
    Data is aggregated based on completed backtests and their results.

    Args:
        period: Time period for history (1d, 7d, 30d, 90d, all)
        resolution: Data point resolution (15m, 1h, 4h, 1d)

    Returns:
        Portfolio history with equity curve and summary metrics

    Example:
        GET /dashboard/portfolio/history?period=7d&resolution=1h
        {
            "period": "7d",
            "data_points": [
                {
                    "timestamp": "2025-12-05T00:00:00Z",
                    "equity": 100000,
                    "pnl": 0,
                    "pnl_pct": 0,
                    "drawdown": 0,
                    "positions_count": 0
                },
                ...
            ],
            "summary": {
                "initial_equity": 100000,
                "final_equity": 112500,
                "total_return": 12.5,
                "max_drawdown": -5.2,
                "sharpe_ratio": 1.85,
                "win_rate": 0.62
            }
        }
    """
    db = get_db()

    try:
        # Calculate time window
        now = utc_now()
        period_map = {
            "1d": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90),
            "all": timedelta(days=365),
        }
        delta = period_map.get(period, timedelta(days=7))
        start_time = now - delta

        # Resolution mapping (in minutes)
        resolution_map = {
            "15m": 15,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
        }
        res_minutes = resolution_map.get(resolution, 60)

        # Query completed backtests in the period
        backtests = (
            db.query(Backtest)
            .filter(
                and_(
                    Backtest.status == BacktestStatus.COMPLETED,
                    Backtest.completed_at >= start_time,
                )
            )
            .order_by(Backtest.completed_at)
            .all()
        )

        # Generate portfolio data points
        data_points = []
        initial_equity = 100000.0  # Simulated starting equity
        current_equity = initial_equity
        max_equity = initial_equity

        # Group backtests by time buckets
        time_buckets = {}
        for bt in backtests:
            # Round to resolution bucket
            bucket_time = bt.completed_at.replace(
                minute=(bt.completed_at.minute // res_minutes) * res_minutes,
                second=0,
                microsecond=0,
            )
            if bucket_time not in time_buckets:
                time_buckets[bucket_time] = []
            time_buckets[bucket_time].append(bt)

        # If no data, generate synthetic data points for visualization
        if not time_buckets:
            # Generate demo data
            num_points = int(delta.total_seconds() / (res_minutes * 60))
            num_points = min(num_points, 200)  # Limit points

            for i in range(num_points):
                point_time = start_time + timedelta(minutes=res_minutes * i)

                # Simulate random walk
                change = random.gauss(0.001, 0.005) * current_equity
                current_equity += change
                max_equity = max(max_equity, current_equity)

                pnl = current_equity - initial_equity
                pnl_pct = (pnl / initial_equity) * 100
                drawdown = ((max_equity - current_equity) / max_equity) * 100

                data_points.append(
                    PortfolioDataPoint(
                        timestamp=point_time,
                        equity=round(current_equity, 2),
                        pnl=round(pnl, 2),
                        pnl_pct=round(pnl_pct, 2),
                        drawdown=round(drawdown, 2),
                        positions_count=random.randint(0, 5),
                    )
                )
        else:
            # Generate points from real backtest data
            sorted_times = sorted(time_buckets.keys())
            cumulative_return = 0

            for bucket_time in sorted_times:
                bucket_backtests = time_buckets[bucket_time]

                # Aggregate returns from backtests in this bucket
                for bt in bucket_backtests:
                    ret = bt.total_return or 0
                    cumulative_return += ret
                    current_equity = initial_equity * (1 + cumulative_return / 100)

                max_equity = max(max_equity, current_equity)
                pnl = current_equity - initial_equity
                pnl_pct = (pnl / initial_equity) * 100
                drawdown = ((max_equity - current_equity) / max_equity) * 100

                data_points.append(
                    PortfolioDataPoint(
                        timestamp=bucket_time,
                        equity=round(current_equity, 2),
                        pnl=round(pnl, 2),
                        pnl_pct=round(pnl_pct, 2),
                        drawdown=round(drawdown, 2),
                        positions_count=len(bucket_backtests),
                    )
                )

        # Calculate summary metrics
        final_equity = data_points[-1].equity if data_points else initial_equity
        total_return = ((final_equity - initial_equity) / initial_equity) * 100
        max_drawdown = max([dp.drawdown for dp in data_points]) if data_points else 0

        # Calculate average metrics from backtests
        all_sharpes = [bt.sharpe_ratio for bt in backtests if bt.sharpe_ratio]
        all_win_rates = [bt.win_rate for bt in backtests if bt.win_rate]

        avg_sharpe = sum(all_sharpes) / len(all_sharpes) if all_sharpes else 0
        avg_win_rate = sum(all_win_rates) / len(all_win_rates) if all_win_rates else 0

        return PortfolioHistoryResponse(
            period=period,
            data_points=data_points,
            summary={
                "initial_equity": initial_equity,
                "final_equity": round(final_equity, 2),
                "total_return": round(total_return, 2),
                "max_drawdown": round(max_drawdown, 2),
                "sharpe_ratio": round(avg_sharpe, 2),
                "win_rate": round(avg_win_rate, 3),
                "total_backtests": len(backtests),
            },
        )

    except Exception as e:
        logger.error(f"Failed to get portfolio history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve portfolio history: {e!s}")
    finally:
        db.close()


# ==============================================================================
# AI Recommendations
# ==============================================================================


class AIRecommendation(BaseModel):
    """AI recommendation item"""

    id: str
    type: str = Field(description="optimization, risk, opportunity, alert")
    title: str
    description: str
    priority: str = Field(description="high, medium, low")
    confidence: float = Field(ge=0, le=1)
    action: str | None = None
    metadata: dict[str, Any] = {}


class AIRecommendationsResponse(BaseModel):
    """AI recommendations response"""

    recommendations: list[AIRecommendation]
    generated_at: datetime
    model: str


@router.get("/ai/recommendations")
async def get_ai_recommendations(
    limit: int = Query(5, ge=1, le=20, description="Number of recommendations"),
    include_types: str | None = Query(None, description="Filter by types: optimization,risk,opportunity,alert"),
) -> AIRecommendationsResponse:
    """
    🤖 AI-powered trading recommendations

    Generates intelligent recommendations based on:
    - Recent backtest performance
    - Strategy patterns
    - Market conditions (when available)
    - Risk metrics

    Args:
        limit: Maximum number of recommendations
        include_types: Comma-separated types to include

    Returns:
        List of AI recommendations with confidence scores

    Example:
        GET /dashboard/ai/recommendations?limit=5
        {
            "recommendations": [
                {
                    "id": "rec_001",
                    "type": "optimization",
                    "title": "Optimize RSI parameters",
                    "description": "Your RSI strategy could improve by adjusting...",
                    "priority": "high",
                    "confidence": 0.85,
                    "action": "/strategies/42/optimize"
                }
            ],
            "generated_at": "2025-12-12T14:30:00Z",
            "model": "rule-based-v1"
        }
    """
    db = get_db()

    try:
        recommendations = []

        # Parse type filter
        type_filter = None
        if include_types:
            type_filter = [t.strip() for t in include_types.split(",")]

        # ===== Rule-based recommendations from data analysis =====

        # 1. Check for underperforming strategies
        low_performers = (
            db.query(Strategy)
            .join(Backtest)
            .filter(Backtest.status == BacktestStatus.COMPLETED)
            .group_by(Strategy.id)
            .having(func.avg(Backtest.sharpe_ratio) < 0.5)
            .limit(3)
            .all()
        )

        for strat in low_performers:
            if type_filter and "optimization" not in type_filter:
                continue
            recommendations.append(
                AIRecommendation(
                    id=f"opt_{strat.id}",
                    type="optimization",
                    title=f"Optimize {strat.name}",
                    description=f"Strategy '{strat.name}' has a low average Sharpe ratio. "
                    f"Consider running parameter optimization or reviewing entry/exit conditions.",
                    priority="high",
                    confidence=0.82,
                    action=f"/strategies/{strat.id}/optimize",
                    metadata={"strategy_id": strat.id},
                )
            )

        # 2. Check for high drawdown strategies
        high_dd_backtests = (
            db.query(Backtest)
            .filter(
                and_(
                    Backtest.status == BacktestStatus.COMPLETED,
                    Backtest.max_drawdown < -20,  # More than 20% drawdown
                )
            )
            .order_by(Backtest.max_drawdown)
            .limit(3)
            .all()
        )

        for bt in high_dd_backtests:
            if type_filter and "risk" not in type_filter:
                continue
            recommendations.append(
                AIRecommendation(
                    id=f"risk_{bt.id}",
                    type="risk",
                    title="High drawdown detected",
                    description=f"Backtest on {bt.symbol} showed {abs(bt.max_drawdown):.1f}% drawdown. "
                    f"Consider adding stop-loss or reducing position size.",
                    priority="high",
                    confidence=0.90,
                    action=f"/backtests/{bt.id}",
                    metadata={"backtest_id": bt.id, "max_drawdown": bt.max_drawdown},
                )
            )

        # 3. Find winning patterns (opportunities)
        top_performers = (
            db.query(Backtest)
            .filter(
                and_(
                    Backtest.status == BacktestStatus.COMPLETED,
                    Backtest.sharpe_ratio > 2.0,
                    Backtest.total_return > 10,
                )
            )
            .order_by(desc(Backtest.sharpe_ratio))
            .limit(3)
            .all()
        )

        for bt in top_performers:
            if type_filter and "opportunity" not in type_filter:
                continue
            strat_name = bt.strategy.name if bt.strategy else "Unknown"
            recommendations.append(
                AIRecommendation(
                    id=f"opp_{bt.id}",
                    type="opportunity",
                    title=f"Strong performance on {bt.symbol}",
                    description=f"Strategy '{strat_name}' achieved {bt.total_return:.1f}% return "
                    f"with Sharpe {bt.sharpe_ratio:.2f}. Consider scaling this approach.",
                    priority="medium",
                    confidence=0.75,
                    action=f"/strategies/{bt.strategy_id}",
                    metadata={"strategy_id": bt.strategy_id, "symbol": bt.symbol},
                )
            )

        # 4. Check for failed backtests (alerts)
        recent_failures = (
            db.query(Backtest)
            .filter(
                and_(
                    Backtest.status == BacktestStatus.FAILED,
                    Backtest.created_at >= utc_now() - timedelta(days=1),
                )
            )
            .count()
        )

        if recent_failures > 0 and (not type_filter or "alert" in type_filter):
            recommendations.append(
                AIRecommendation(
                    id="alert_failures",
                    type="alert",
                    title=f"{recent_failures} failed backtests today",
                    description="Some backtests failed in the last 24 hours. "
                    "Check logs for data quality or strategy errors.",
                    priority="medium" if recent_failures < 5 else "high",
                    confidence=0.95,
                    action="/backtests?status=failed",
                    metadata={"failure_count": recent_failures},
                )
            )

        # 5. Suggest diversification if concentrated
        symbol_counts = (
            db.query(Backtest.symbol, func.count(Backtest.id))
            .filter(Backtest.status == BacktestStatus.COMPLETED)
            .group_by(Backtest.symbol)
            .all()
        )

        if symbol_counts:
            total = sum(c for _, c in symbol_counts)
            for symbol, count in symbol_counts:
                concentration = count / total if total > 0 else 0
                if concentration > 0.6 and (not type_filter or "risk" in type_filter):  # More than 60% on one symbol
                    recommendations.append(
                        AIRecommendation(
                            id=f"div_{symbol}",
                            type="risk",
                            title="Portfolio concentration warning",
                            description=f"{concentration * 100:.0f}% of backtests are on {symbol}. "
                            f"Consider diversifying to other trading pairs.",
                            priority="medium",
                            confidence=0.80,
                            metadata={
                                "symbol": symbol,
                                "concentration": concentration,
                            },
                        )
                    )

        # Limit and sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.priority, 1))
        recommendations = recommendations[:limit]

        return AIRecommendationsResponse(
            recommendations=recommendations,
            generated_at=utc_now(),
            model="rule-based-v1",
        )

    except Exception as e:
        logger.error(f"Failed to generate AI recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {e!s}")
    finally:
        db.close()


# ==============================================================================
# Strategy Leaderboard
# ==============================================================================


class LeaderboardEntry(BaseModel):
    """Leaderboard entry"""

    rank: int
    strategy_id: str  # UUID string
    strategy_name: str
    strategy_type: str | None
    total_backtests: int
    avg_return: float
    avg_sharpe: float
    avg_win_rate: float
    best_return: float
    worst_drawdown: float
    last_run: datetime | None
    trend: str = Field(description="up, down, stable")


class LeaderboardResponse(BaseModel):
    """Strategy leaderboard response"""

    period: str
    metric: str
    entries: list[LeaderboardEntry]
    updated_at: datetime


@router.get("/strategies/leaderboard")
async def get_strategy_leaderboard(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, all"),
    metric: str = Query("sharpe", description="Ranking metric: sharpe, return, win_rate, consistency"),
    limit: int = Query(10, ge=1, le=50, description="Number of entries"),
) -> LeaderboardResponse:
    """
    🏆 Strategy Performance Leaderboard

    Ranks strategies by performance across multiple metrics.
    Includes trend indicators based on recent vs historical performance.

    Args:
        period: Time period for ranking
        metric: Primary ranking metric
        limit: Number of top strategies

    Returns:
        Ranked list of strategies with comprehensive metrics

    Example:
        GET /dashboard/strategies/leaderboard?period=30d&metric=sharpe&limit=10
    """
    db = get_db()

    try:
        # Time filter
        now = utc_now()
        period_map = {
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90),
            "all": None,
        }
        delta = period_map.get(period)
        time_filter = (now - delta) if delta else None

        # First try: query via Strategy JOIN (for backtests linked to strategies)
        strategy_query = (
            db.query(
                Strategy.id,
                Strategy.name,
                Strategy.strategy_type,
                func.count(Backtest.id).label("total_backtests"),
                func.avg(Backtest.total_return).label("avg_return"),
                func.avg(Backtest.sharpe_ratio).label("avg_sharpe"),
                func.avg(Backtest.win_rate).label("avg_win_rate"),
                func.max(Backtest.total_return).label("best_return"),
                func.min(Backtest.max_drawdown).label("worst_drawdown"),
                func.max(Backtest.completed_at).label("last_run"),
            )
            .join(Backtest, Strategy.id == Backtest.strategy_id)
            .filter(
                Backtest.status == BacktestStatus.COMPLETED,
                Backtest.total_trades > 0,
            )
        )

        if time_filter:
            strategy_query = strategy_query.filter(Backtest.completed_at >= time_filter)

        strategy_query = strategy_query.group_by(Strategy.id)

        # Order by selected metric
        metric_columns = {
            "sharpe": "avg_sharpe",
            "return": "avg_return",
            "win_rate": "avg_win_rate",
            "consistency": "total_backtests",
        }
        order_col = metric_columns.get(metric, "avg_sharpe")

        results = strategy_query.order_by(desc(order_col)).limit(limit).all()

        # Fallback: if no Strategy-linked backtests, group by strategy_type
        if not results:
            fallback_query = db.query(
                Backtest.strategy_type.label("strategy_type"),
                func.count(Backtest.id).label("total_backtests"),
                func.avg(Backtest.total_return).label("avg_return"),
                func.avg(Backtest.sharpe_ratio).label("avg_sharpe"),
                func.avg(Backtest.win_rate).label("avg_win_rate"),
                func.max(Backtest.total_return).label("best_return"),
                func.min(Backtest.max_drawdown).label("worst_drawdown"),
                func.max(Backtest.completed_at).label("last_run"),
            ).filter(
                Backtest.status == BacktestStatus.COMPLETED,
                Backtest.total_trades > 0,
                Backtest.strategy_type.isnot(None),
            )

            if time_filter:
                fallback_query = fallback_query.filter(Backtest.completed_at >= time_filter)

            fallback_query = fallback_query.group_by(Backtest.strategy_type)
            fallback_results = fallback_query.order_by(desc(order_col)).limit(limit).all()

            entries = []
            for rank, row in enumerate(fallback_results, 1):
                st = row.strategy_type or "unknown"
                # Trend from recent 7d vs overall
                trend = "stable"
                if delta and delta > timedelta(days=7):
                    recent_avg = (
                        db.query(func.avg(Backtest.sharpe_ratio))
                        .filter(
                            Backtest.strategy_type == st,
                            Backtest.status == BacktestStatus.COMPLETED,
                            Backtest.completed_at >= now - timedelta(days=7),
                        )
                        .scalar()
                    )
                    if recent_avg and row.avg_sharpe:
                        if recent_avg > float(row.avg_sharpe) * 1.1:
                            trend = "up"
                        elif recent_avg < float(row.avg_sharpe) * 0.9:
                            trend = "down"

                entries.append(
                    LeaderboardEntry(
                        rank=rank,
                        strategy_id=st,
                        strategy_name=st.replace("_", " ").title(),
                        strategy_type=st,
                        total_backtests=row.total_backtests,
                        avg_return=round(float(row.avg_return or 0), 2),
                        avg_sharpe=round(float(row.avg_sharpe or 0), 2),
                        avg_win_rate=round(float(row.avg_win_rate or 0), 3),
                        best_return=round(float(row.best_return or 0), 2),
                        worst_drawdown=round(float(row.worst_drawdown or 0), 2),
                        last_run=row.last_run,
                        trend=trend,
                    )
                )

            return LeaderboardResponse(period=period, metric=metric, entries=entries, updated_at=utc_now())

        # Strategy-linked path (original logic)
        entries = []
        for rank, row in enumerate(results, 1):
            trend = "stable"
            if delta and delta > timedelta(days=7):
                recent_avg = (
                    db.query(func.avg(Backtest.sharpe_ratio))
                    .filter(
                        and_(
                            Backtest.strategy_id == row.id,
                            Backtest.status == BacktestStatus.COMPLETED,
                            Backtest.completed_at >= now - timedelta(days=7),
                        )
                    )
                    .scalar()
                )

                if recent_avg and row.avg_sharpe:
                    if recent_avg > row.avg_sharpe * 1.1:
                        trend = "up"
                    elif recent_avg < row.avg_sharpe * 0.9:
                        trend = "down"

            entries.append(
                LeaderboardEntry(
                    rank=rank,
                    strategy_id=row.id,
                    strategy_name=row.name,
                    strategy_type=row.strategy_type.value if row.strategy_type else None,
                    total_backtests=row.total_backtests,
                    avg_return=round(row.avg_return or 0, 2),
                    avg_sharpe=round(row.avg_sharpe or 0, 2),
                    avg_win_rate=round(row.avg_win_rate or 0, 3),
                    best_return=round(row.best_return or 0, 2),
                    worst_drawdown=round(row.worst_drawdown or 0, 2),
                    last_run=row.last_run,
                    trend=trend,
                )
            )

        return LeaderboardResponse(period=period, metric=metric, entries=entries, updated_at=utc_now())

    except Exception as e:
        logger.error(f"Failed to get strategy leaderboard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve leaderboard: {e!s}")
    finally:
        db.close()


# ==============================================================================
# Real-time P&L WebSocket
# ==============================================================================


class PnLConnectionManager:
    """Manage WebSocket connections for P&L streaming"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"💰 P&L WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"💰 P&L WebSocket disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast_pnl(self, data: dict):
        """Broadcast P&L update to all clients"""
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_json(data)
            except Exception:
                disconnected.append(conn)
        for conn in disconnected:
            self.disconnect(conn)


pnl_ws_manager = PnLConnectionManager()


@router.websocket("/ws/pnl")
async def pnl_websocket(websocket: WebSocket):
    """
    💰 Real-time P&L WebSocket

    Streams live P&L updates every 5 seconds.

    Connect: ws://localhost:8000/api/v1/dashboard/ws/pnl

    Message format:
    {
        "type": "pnl_update",
        "data": {
            "total_equity": 112500.50,
            "unrealized_pnl": 1250.25,
            "realized_pnl_today": 3500.00,
            "pnl_pct": 2.5,
            "positions": [
                {"symbol": "BTCUSDT", "pnl": 850.00, "pnl_pct": 1.2}
            ]
        },
        "timestamp": "2025-12-12T14:30:00Z"
    }
    """
    await pnl_ws_manager.connect(websocket)

    try:
        # Send initial data
        await websocket.send_json(
            {
                "type": "connected",
                "message": "P&L WebSocket connected",
                "timestamp": utc_now().isoformat(),
            }
        )

        # Start streaming task
        stream_task = asyncio.create_task(_stream_pnl_updates(websocket))

        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")

                if action == "ping":
                    await websocket.send_json({"type": "pong"})
                elif action == "subscribe":
                    # Could handle subscription to specific symbols
                    pass
        except WebSocketDisconnect:
            logger.info("P&L WebSocket client disconnected")
        finally:
            stream_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stream_task
    except Exception as e:
        logger.error(f"P&L WebSocket error: {e}")
    finally:
        pnl_ws_manager.disconnect(websocket)


async def _stream_pnl_updates(websocket: WebSocket):
    """Stream P&L updates every 5 seconds"""
    # Simulated base values (in production, would query actual positions)
    base_equity = 100000.0

    try:
        while True:
            await asyncio.sleep(5)

            # Simulate P&L changes
            pnl_change = random.gauss(0, 0.002) * base_equity
            equity = base_equity + pnl_change
            pnl_pct = (pnl_change / base_equity) * 100

            # Simulated positions
            positions = [
                {
                    "symbol": "BTCUSDT",
                    "pnl": round(pnl_change * 0.5, 2),
                    "pnl_pct": round(pnl_pct * 0.5, 2),
                },
                {
                    "symbol": "ETHUSDT",
                    "pnl": round(pnl_change * 0.3, 2),
                    "pnl_pct": round(pnl_pct * 0.3, 2),
                },
                {
                    "symbol": "SOLUSDT",
                    "pnl": round(pnl_change * 0.2, 2),
                    "pnl_pct": round(pnl_pct * 0.2, 2),
                },
            ]

            update = {
                "type": "pnl_update",
                "data": {
                    "total_equity": round(equity, 2),
                    "unrealized_pnl": round(pnl_change, 2),
                    "realized_pnl_today": round(random.uniform(100, 1000), 2),
                    "pnl_pct": round(pnl_pct, 3),
                    "positions": positions,
                },
                "timestamp": utc_now().isoformat(),
            }

            await websocket.send_json(update)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error in P&L streaming: {e}")


# ==============================================================================
# Alias endpoints for frontend compatibility
# ==============================================================================


@router.get("/ai-recommendations")
async def get_ai_recommendations_alias(
    limit: int = Query(5, ge=1, le=20, description="Number of recommendations"),
    include_types: str | None = Query(None, description="Filter by types: optimization,risk,opportunity,alert"),
) -> AIRecommendationsResponse:
    """Alias for /ai/recommendations for frontend compatibility"""
    return await get_ai_recommendations(limit=limit, include_types=include_types)


@router.get("/strategy-leaderboard")
async def get_strategy_leaderboard_alias(
    period: str = Query("7d", description="Period: 7d, 30d, 90d, all"),
    metric: str = Query("sharpe", description="Sort metric: sharpe, return, win_rate"),
    limit: int = Query(10, ge=1, le=50, description="Number of entries"),
) -> LeaderboardResponse:
    """Alias for /strategies/leaderboard for frontend compatibility"""
    return await get_strategy_leaderboard(period=period, metric=metric, limit=limit)


@router.get("/market/tickers")
async def get_market_tickers(
    top: int = Query(6, ge=1, le=50, description="Number of top coins by volume"),
    symbols: str = Query(
        None,
        description="Optional: Comma-separated list of specific symbols. If not provided, returns top N by volume.",
    ),
) -> dict[str, Any]:
    """
    📊 Real-time market tickers from Bybit - Dynamic Top by Volume

    Returns top N cryptocurrencies sorted by 24h trading volume.
    If specific symbols provided, returns only those.

    Returns:
        List of ticker data with real prices from Bybit API, sorted by volume
    """
    from backend.services.adapters.bybit import BybitAdapter

    adapter = BybitAdapter()

    # Metadata for known coins (icons and colors)
    metadata = {
        "BTCUSDT": {"name": "Bitcoin", "icon": "₿", "color": "#F7931A"},
        "ETHUSDT": {"name": "Ethereum", "icon": "Ξ", "color": "#627EEA"},
        "SOLUSDT": {"name": "Solana", "icon": "◎", "color": "#00FFA3"},
        "BNBUSDT": {"name": "BNB", "icon": "◆", "color": "#F3BA2F"},
        "XRPUSDT": {"name": "XRP", "icon": "✕", "color": "#23292F"},
        "ADAUSDT": {"name": "Cardano", "icon": "₳", "color": "#0033AD"},
        "DOGEUSDT": {"name": "Dogecoin", "icon": "Ð", "color": "#C2A633"},
        "AVAXUSDT": {"name": "Avalanche", "icon": "A", "color": "#E84142"},
        "DOTUSDT": {"name": "Polkadot", "icon": "●", "color": "#E6007A"},
        "LINKUSDT": {"name": "Chainlink", "icon": "⬡", "color": "#375BD2"},
        "MATICUSDT": {"name": "Polygon", "icon": "⬡", "color": "#8247E5"},
        "LTCUSDT": {"name": "Litecoin", "icon": "Ł", "color": "#BFBBBB"},
        "SHIBUSDT": {"name": "Shiba Inu", "icon": "🐕", "color": "#FFA409"},
        "TRXUSDT": {"name": "TRON", "icon": "◈", "color": "#FF0013"},
        "ATOMUSDT": {"name": "Cosmos", "icon": "⚛", "color": "#2E3148"},
        "UNIUSDT": {"name": "Uniswap", "icon": "🦄", "color": "#FF007A"},
        "APTUSDT": {"name": "Aptos", "icon": "A", "color": "#4CD7D0"},
        "ARBUSDT": {"name": "Arbitrum", "icon": "A", "color": "#28A0F0"},
        "OPUSDT": {"name": "Optimism", "icon": "O", "color": "#FF0420"},
        "NEARUSDT": {"name": "NEAR", "icon": "N", "color": "#00C08B"},
        "SUIUSDT": {"name": "Sui", "icon": "S", "color": "#6FBCF0"},
        "PEPEUSDT": {"name": "Pepe", "icon": "🐸", "color": "#00A651"},
        "WIFUSDT": {"name": "dogwifhat", "icon": "🎩", "color": "#C9A86C"},
        "FETUSDT": {"name": "Fetch.ai", "icon": "F", "color": "#1D2951"},
        "INJUSDT": {"name": "Injective", "icon": "I", "color": "#00F2FE"},
        "RENDERUSDT": {"name": "Render", "icon": "R", "color": "#00BFFF"},
        "AAVEUSDT": {"name": "Aave", "icon": "👻", "color": "#B6509E"},
    }

    try:
        if symbols:
            # If specific symbols requested
            symbol_list = [s.strip().upper() for s in symbols.split(",")]
            tickers = adapter.get_tickers(symbols=symbol_list)
        else:
            # Get ALL tickers and sort by volume (dynamic top)
            tickers = adapter.get_tickers(symbols=None)

            # Filter only USDT pairs and sort by turnover (volume in USD)
            tickers = [t for t in tickers if t.get("symbol", "").endswith("USDT")]
            tickers.sort(key=lambda x: float(x.get("turnover_24h") or 0), reverse=True)

            # Take top N
            tickers = tickers[:top]

        result = []
        for ticker in tickers:
            sym = ticker.get("symbol", "")
            # Generate default metadata for unknown coins
            default_name = sym.replace("USDT", "")
            meta = metadata.get(
                sym,
                {
                    "name": default_name,
                    "icon": default_name[0] if default_name else "•",
                    "color": "#888888",
                },
            )
            result.append(
                {
                    "symbol": sym,
                    "name": meta["name"],
                    "icon": meta["icon"],
                    "color": meta["color"],
                    "price": ticker.get("price"),
                    "change": ticker.get("change_24h", 0),
                    "volume_24h": ticker.get("volume_24h"),
                    "turnover_24h": ticker.get("turnover_24h"),
                    "high_24h": ticker.get("high_24h"),
                    "low_24h": ticker.get("low_24h"),
                }
            )

        return {
            "success": True,
            "tickers": result,
            "count": len(result),
            "sorted_by": "turnover_24h" if not symbols else "requested",
            "timestamp": utc_now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to fetch market tickers: {e}")
        return {
            "success": False,
            "error": str(e),
            "tickers": [],
            "timestamp": utc_now().isoformat(),
        }


@router.get("/pnl/current")
async def get_current_pnl() -> dict[str, Any]:
    """
    💰 Current P&L snapshot

    Returns current portfolio P&L status (simulated data for demo).

    Returns:
        Current P&L data with positions breakdown
    """
    base_equity = 100000.0
    pnl_change = random.gauss(0, 0.002) * base_equity
    equity = base_equity + pnl_change
    pnl_pct = (pnl_change / base_equity) * 100

    positions = [
        {
            "symbol": "BTCUSDT",
            "side": "long",
            "size": 0.5,
            "entry_price": 42150.0,
            "current_price": 42150.0 + random.uniform(-100, 100),
            "pnl": round(pnl_change * 0.5, 2),
            "pnl_pct": round(pnl_pct * 0.5, 2),
        },
        {
            "symbol": "ETHUSDT",
            "side": "long",
            "size": 5.0,
            "entry_price": 2280.0,
            "current_price": 2280.0 + random.uniform(-10, 10),
            "pnl": round(pnl_change * 0.3, 2),
            "pnl_pct": round(pnl_pct * 0.3, 2),
        },
        {
            "symbol": "SOLUSDT",
            "side": "short",
            "size": 20.0,
            "entry_price": 108.5,
            "current_price": 108.5 + random.uniform(-2, 2),
            "pnl": round(pnl_change * 0.2, 2),
            "pnl_pct": round(pnl_pct * 0.2, 2),
        },
    ]

    today_pnl = round(random.uniform(100, 1000), 2)
    week_pnl = round(random.uniform(-2000, 5000), 2)
    month_pnl = round(random.uniform(-5000, 15000), 2)

    # Generate hourly P&L sparkline (last 24 data points)
    hourly_pnl = []
    cumulative = 0.0
    for _ in range(24):
        cumulative += random.gauss(0, 50)
        hourly_pnl.append(round(cumulative, 2))

    return {
        "total_equity": round(equity, 2),
        "unrealized_pnl": round(pnl_change, 2),
        "realized_pnl_today": today_pnl,
        "pnl_pct": round(pnl_pct, 3),
        "positions": positions,
        # Keys expected by frontend JS
        "current_pnl": round(pnl_change, 2),
        "today_pnl": today_pnl,
        "week_pnl": week_pnl,
        "month_pnl": month_pnl,
        "open_positions": len(positions),
        "hourly_pnl": hourly_pnl,
        "timestamp": utc_now().isoformat(),
    }


# ============================================================================
# MARKETDATA WEBSOCKET
# ============================================================================


class MarketDataConnectionManager:
    """Manage WebSocket connections for market data streaming"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"📊 MarketData WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"📊 MarketData WebSocket disconnected. Remaining: {len(self.active_connections)}")


marketdata_ws_manager = MarketDataConnectionManager()


@router.websocket("/ws/marketdata")
async def marketdata_websocket(websocket: WebSocket):
    """
    📊 Real-time Market Data WebSocket

    Streams simulated market data for chart visualization.

    Connect: ws://localhost:8000/api/v1/dashboard/ws/marketdata

    Message format:
    {
        "type": "ticker",
        "data": {
            "symbol": "BTCUSDT",
            "price": 42500.50,
            "change_24h": 2.5,
            "volume_24h": 1234567890,
            "high_24h": 43000.0,
            "low_24h": 41500.0
        },
        "timestamp": "2025-12-14T10:30:00Z"
    }
    """
    await marketdata_ws_manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "message": "MarketData WebSocket connected",
                "timestamp": utc_now().isoformat(),
            }
        )

        # Start streaming task
        stream_task = asyncio.create_task(_stream_marketdata(websocket))

        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")

                if action == "ping":
                    await websocket.send_json({"type": "pong"})
                elif action == "subscribe":
                    symbol = data.get("symbol", "BTCUSDT")
                    await websocket.send_json(
                        {
                            "type": "subscribed",
                            "symbol": symbol,
                            "timestamp": utc_now().isoformat(),
                        }
                    )
        except WebSocketDisconnect:
            logger.info("MarketData WebSocket client disconnected")
        finally:
            stream_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stream_task
    except Exception as e:
        logger.error(f"MarketData WebSocket error: {e}")
    finally:
        marketdata_ws_manager.disconnect(websocket)


async def _stream_marketdata(websocket: WebSocket):
    """Stream real market data from Bybit API every 3 seconds"""
    from backend.services.adapters.bybit import BybitAdapter

    # Symbols to stream
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    adapter = BybitAdapter()

    try:
        while True:
            await asyncio.sleep(3)

            try:
                # Fetch real tickers from Bybit API
                tickers = adapter.get_tickers(symbols=symbols)

                for ticker in tickers:
                    if ticker.get("price") is not None:
                        await websocket.send_json(
                            {
                                "type": "ticker",
                                "data": {
                                    "symbol": ticker.get("symbol"),
                                    "price": ticker.get("price"),
                                    "change_24h": round(ticker.get("change_24h", 0), 2),
                                    "volume_24h": int(ticker.get("volume_24h", 0) or 0),
                                    "high_24h": ticker.get("high_24h"),
                                    "low_24h": ticker.get("low_24h"),
                                },
                                "timestamp": utc_now().isoformat(),
                            }
                        )
            except Exception as e:
                logger.warning(f"Failed to fetch real market data, using fallback: {e}")
                # Fallback to static prices if API fails
                fallback_prices = {
                    "BTCUSDT": 97500.0,
                    "ETHUSDT": 3650.0,
                    "SOLUSDT": 220.0,
                    "BNBUSDT": 695.0,
                    "XRPUSDT": 2.35,
                }
                for symbol, price in fallback_prices.items():
                    await websocket.send_json(
                        {
                            "type": "ticker",
                            "data": {
                                "symbol": symbol,
                                "price": price,
                                "change_24h": 0,
                                "volume_24h": 0,
                                "high_24h": price * 1.02,
                                "low_24h": price * 0.98,
                            },
                            "timestamp": utc_now().isoformat(),
                        }
                    )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"MarketData stream error: {e}")
