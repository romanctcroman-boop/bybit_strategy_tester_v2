"""
Performance Metrics Dashboard API - Quick Win #1

Real-time system performance metrics for monitoring dashboard.
Provides aggregated stats for backtests, strategies, and system health.
"""

import asyncio
import contextlib
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy import and_, desc, func, text
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.database.models import Backtest, BacktestStatus, Strategy, StrategyStatus
from backend.database.models.optimization import Optimization, OptimizationStatus
from backend.monitoring.breaker_telemetry import get_agent_breaker_snapshot
from backend.utils.time import utc_now

router = APIRouter(prefix="/dashboard", tags=["Dashboard Metrics"])


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        logger.error(f"Failed to create DB session: {e}")
        db.close()
        raise


@router.get("/metrics/summary")
async def get_metrics_summary(
    period: str = Query("24h", description="Period: 1h, 24h, 7d, 30d, all"),
) -> dict[str, Any]:
    """
    📊 Real-time system performance summary

    Returns aggregated metrics for monitoring dashboard:
    - Total backtests (running, completed, failed)
    - Active strategies count
    - Optimization tasks status
    - System health indicators

    Args:
        period: Time period for metrics (1h, 24h, 7d, 30d, all)

    Returns:
        Dict with summary metrics

    Example:
        GET /dashboard/metrics/summary?period=24h
        {
            "period": "24h",
            "timestamp": "2025-11-14T12:00:00Z",
            "backtests": {
                "total": 1523,
                "completed": 1420,
                "running": 12,
                "failed": 91,
                "success_rate": 0.940
            },
            "strategies": {
                "total": 45,
                "active": 38
            },
            "optimizations": {
                "total": 234,
                "running": 3,
                "completed": 220
            },
            "performance": {
                "avg_backtest_duration_sec": 45.2,
                "total_trades_analyzed": 125430
            }
        }
    """
    db = get_db()

    try:
        # Calculate time window
        now = utc_now()
        time_filter = _get_time_filter(period, now)

        # Backtest metrics
        backtest_query = db.query(Backtest)
        if time_filter:
            backtest_query = backtest_query.filter(Backtest.created_at >= time_filter)

        total_backtests = backtest_query.count()
        completed_backtests = backtest_query.filter(Backtest.status == BacktestStatus.COMPLETED).count()
        running_backtests = backtest_query.filter(Backtest.status == BacktestStatus.RUNNING).count()
        failed_backtests = backtest_query.filter(Backtest.status == BacktestStatus.FAILED).count()

        success_rate = completed_backtests / total_backtests if total_backtests > 0 else 0.0

        # Strategy metrics
        strategy_query = db.query(Strategy)
        total_strategies = strategy_query.count()
        active_strategies = strategy_query.filter(Strategy.status == StrategyStatus.ACTIVE).count()

        # Performance metrics - average backtest duration
        avg_duration = (
            db.query(func.avg(Backtest.execution_time_ms))
            .filter(
                and_(
                    Backtest.status == BacktestStatus.COMPLETED,
                    Backtest.execution_time_ms.isnot(None),
                )
            )
            .scalar()
        )

        # Total trades from completed backtests (sum of total_trades column)
        total_trades = (
            db.query(func.sum(Backtest.total_trades)).filter(Backtest.status == BacktestStatus.COMPLETED).scalar() or 0
        )

        # Optimization metrics
        total_optimizations = db.query(Optimization).count()
        running_optimizations = db.query(Optimization).filter(Optimization.status == OptimizationStatus.RUNNING).count()
        completed_optimizations = (
            db.query(Optimization).filter(Optimization.status == OptimizationStatus.COMPLETED).count()
        )

        # Calculate duration in seconds for frontend
        avg_duration_sec = (avg_duration or 0) / 1000.0

        return {
            "period": period,
            "timestamp": now.isoformat(),
            "backtests": {
                "total": total_backtests,
                "completed": completed_backtests,
                "running": running_backtests,
                "failed": failed_backtests,
                "success_rate": round(success_rate, 3),
            },
            "strategies": {"total": total_strategies, "active": active_strategies},
            "optimizations": {
                "total": total_optimizations,
                "running": running_optimizations,
                "completed": completed_optimizations,
            },
            "performance": {
                "avg_backtest_duration_ms": round(avg_duration or 0, 2),
                "avg_backtest_duration_sec": round(avg_duration_sec, 1),
                "total_trades_analyzed": int(total_trades),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")
    finally:
        db.close()


@router.get("/metrics/top-performers")
async def get_top_performers(
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    metric: str = Query(
        "sharpe_ratio",
        description="Metric to rank by: sharpe_ratio, total_return, win_rate",
    ),
) -> dict[str, Any]:
    """
    🏆 Top performing backtests by selected metric

    Returns best performing backtests ranked by chosen metric.

    Args:
        limit: Number of top results (1-50)
        metric: Ranking metric (sharpe_ratio, total_return, win_rate)

    Returns:
        List of top performers with key metrics

    Example:
        GET /dashboard/metrics/top-performers?limit=5&metric=sharpe_ratio
        {
            "metric": "sharpe_ratio",
            "top_performers": [
                {
                    "id": 1523,
                    "strategy_name": "Bollinger Mean Reversion",
                    "symbol": "BTCUSDT",
                    "sharpe_ratio": 2.45,
                    "total_return": 18.5,
                    "win_rate": 0.68,
                    "completed_at": "2025-11-14T10:30:00Z"
                },
                ...
            ]
        }
    """
    db = get_db()

    try:
        # Validate metric
        valid_metrics = ["sharpe_ratio", "total_return", "win_rate"]
        if metric not in valid_metrics:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric. Must be one of: {', '.join(valid_metrics)}",
            )

        # Query top performers
        metric_column = getattr(Backtest, metric)

        query = (
            db.query(Backtest)
            .join(Strategy)
            .filter(
                and_(
                    Backtest.status == BacktestStatus.COMPLETED,
                    metric_column.isnot(None),
                )
            )
            .order_by(desc(metric_column))
            .limit(limit)
        )

        results = query.all()

        top_performers = []
        for bt in results:
            top_performers.append(
                {
                    "id": bt.id,
                    "strategy_name": bt.strategy.name if bt.strategy else "Unknown",
                    "symbol": bt.symbol,
                    "timeframe": bt.timeframe,
                    "sharpe_ratio": round(bt.sharpe_ratio or 0, 2),
                    "total_return": round(bt.total_return or 0, 2),
                    "win_rate": round(bt.win_rate or 0, 3),
                    "max_drawdown": round(bt.max_drawdown or 0, 2),
                    "total_trades": bt.total_trades,
                    "completed_at": bt.completed_at.isoformat() if bt.completed_at else None,
                }
            )

        return {
            "metric": metric,
            "limit": limit,
            "count": len(top_performers),
            "top_performers": top_performers,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get top performers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve top performers: {str(e)}")
    finally:
        db.close()


@router.get("/metrics/strategy/{strategy_id}")
async def get_strategy_metrics(
    strategy_id: int,
    period: str = Query("30d", description="Period: 7d, 30d, 90d, all"),
) -> dict[str, Any]:
    """
    📈 Detailed metrics for specific strategy

    Returns comprehensive performance metrics for a single strategy.

    Args:
        strategy_id: Strategy ID
        period: Time period for metrics

    Returns:
        Strategy performance statistics

    Example:
        GET /dashboard/metrics/strategy/42?period=30d
        {
            "strategy_id": 42,
            "strategy_name": "RSI Mean Reversion",
            "period": "30d",
            "backtests": {
                "total": 156,
                "avg_sharpe": 1.45,
                "avg_return": 12.3,
                "avg_win_rate": 0.62
            },
            "best_backtest": {...},
            "recent_activity": [...]
        }
    """
    db = get_db()

    try:
        # Get strategy
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Calculate time window
        now = utc_now()
        time_filter = _get_time_filter(period, now)

        # Query backtests for this strategy
        backtest_query = db.query(Backtest).filter(
            and_(
                Backtest.strategy_id == strategy_id,
                Backtest.status == BacktestStatus.COMPLETED,
            )
        )
        if time_filter:
            backtest_query = backtest_query.filter(Backtest.created_at >= time_filter)

        backtests = backtest_query.all()

        if not backtests:
            return {
                "strategy_id": strategy_id,
                "strategy_name": strategy.name,
                "period": period,
                "message": "No completed backtests in this period",
            }

        # Calculate aggregated metrics
        avg_sharpe = sum(bt.sharpe_ratio or 0 for bt in backtests) / len(backtests)
        avg_return = sum(bt.total_return or 0 for bt in backtests) / len(backtests)
        avg_win_rate = sum(bt.win_rate or 0 for bt in backtests) / len(backtests)
        avg_max_dd = sum(bt.max_drawdown or 0 for bt in backtests) / len(backtests)

        # Best backtest by Sharpe ratio
        best_bt = max(backtests, key=lambda x: x.sharpe_ratio or 0)

        # Recent activity (last 5 backtests)
        recent = sorted(backtests, key=lambda x: x.created_at, reverse=True)[:5]

        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy.name,
            "strategy_type": strategy.strategy_type,
            "is_active": strategy.status == StrategyStatus.ACTIVE,
            "period": period,
            "backtests": {
                "total": len(backtests),
                "avg_sharpe": round(avg_sharpe, 2),
                "avg_return": round(avg_return, 2),
                "avg_win_rate": round(avg_win_rate, 3),
                "avg_max_drawdown": round(avg_max_dd, 2),
            },
            "best_backtest": {
                "id": best_bt.id,
                "symbol": best_bt.symbol,
                "sharpe_ratio": round(best_bt.sharpe_ratio or 0, 2),
                "total_return": round(best_bt.total_return or 0, 2),
                "completed_at": best_bt.completed_at.isoformat() if best_bt.completed_at else None,
            },
            "recent_activity": [
                {
                    "id": bt.id,
                    "symbol": bt.symbol,
                    "sharpe_ratio": round(bt.sharpe_ratio or 0, 2),
                    "total_return": round(bt.total_return or 0, 2),
                    "created_at": bt.created_at.isoformat(),
                }
                for bt in recent
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get strategy metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve strategy metrics: {str(e)}")
    finally:
        db.close()


@router.get("/metrics/system-health")
async def get_system_health() -> dict[str, Any]:
    """
    🏥 System health check with key indicators

    Returns:
        System health status and diagnostics

    Example:
        GET /dashboard/metrics/system-health
        {
            "status": "healthy",
            "database": {
                "connected": true,
                "response_time_ms": 5.2
            },
            "queue": {
                "pending_tasks": 12,
                "active_workers": 4
            },
            "disk": {
                "database_size_mb": 1024.5
            }
        }
    """
    db = get_db()

    try:
        agent_snapshot = get_agent_breaker_snapshot()

        # Database health check
        start_time = utc_now()
        db.execute(text("SELECT 1"))
        response_time = (utc_now() - start_time).total_seconds() * 1000

        # Count pending backtests
        pending_backtests = (
            db.query(Backtest).filter(Backtest.status.in_([BacktestStatus.PENDING, BacktestStatus.RUNNING])).count()
        )

        # Database size (approximate) - use file size for SQLite or try pg_database_size for PostgreSQL
        try:
            import os

            db_size_mb = os.path.getsize("data.sqlite3") / (1024 * 1024)
        except Exception:
            db_size_mb = 0

        # Active workers (approximation based on running backtests)
        active_workers = min(pending_backtests, 10)  # Assume max 10 workers

        return {
            "status": "healthy",
            "timestamp": utc_now().isoformat(),
            "database": {
                "connected": True,
                "response_time_ms": round(response_time, 2),
            },
            "queue": {
                "pending_tasks": pending_backtests,
                "active_workers": active_workers,
            },
            "disk": {"database_size_mb": round(db_size_mb, 2)},
            "agents": agent_snapshot,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": utc_now().isoformat(),
            "error": str(e),
            "agents": get_agent_breaker_snapshot(),
        }
    finally:
        db.close()


def _get_time_filter(period: str, now: datetime) -> datetime | None:
    """Helper to calculate time filter based on period"""
    period_map = {
        "1h": timedelta(hours=1),
        "24h": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None,
    }

    delta = period_map.get(period)
    return (now - delta) if delta else None


# ============================================================================
# WebSocket for Real-time Dashboard Updates
# ============================================================================


class DashboardConnectionManager:
    """Manage WebSocket connections for dashboard real-time updates"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"📊 Dashboard WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"📊 Dashboard WebSocket disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        """Send data to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)

        # Cleanup disconnected
        for conn in disconnected:
            self.disconnect(conn)


dashboard_ws_manager = DashboardConnectionManager()


@router.websocket("/ws")
async def dashboard_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.

    Connect: ws://localhost:8000/api/v1/dashboard/ws

    The server will send periodic updates with metrics data.

    Message format sent by server:
    {
        "type": "metrics_update",
        "data": {
            "backtests": {...},
            "strategies": {...},
            "performance": {...}
        },
        "timestamp": "2025-12-11T12:00:00Z"
    }

    Client can send:
    {
        "action": "ping"
    }

    Server responds:
    {
        "type": "pong"
    }
    """
    await dashboard_ws_manager.connect(websocket)

    try:
        # Send initial data immediately
        try:
            from backend.utils.time import utc_now

            initial_data = {
                "type": "connected",
                "message": "Dashboard WebSocket connected",
                "timestamp": utc_now().isoformat(),
            }
            # Check if websocket is still connected before sending
            if websocket.client_state.name == "CONNECTED":
                await websocket.send_json(initial_data)
        except Exception as e:
            logger.warning(f"Could not send initial data (client may have disconnected): {e}")

        # Start background task for periodic updates
        update_task = asyncio.create_task(_send_periodic_updates(websocket))

        try:
            while True:
                # Receive messages from client
                data = await websocket.receive_json()
                action = data.get("action")

                if action == "ping":
                    await websocket.send_json({"type": "pong"})
                elif action == "refresh":
                    # Send immediate metrics update on demand
                    await _send_metrics_update(websocket)
        except WebSocketDisconnect:
            logger.info("Dashboard WebSocket client disconnected normally")
        finally:
            update_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await update_task
    except WebSocketDisconnect:
        logger.debug("Dashboard WebSocket disconnected during setup")
    except Exception as e:
        logger.warning(f"Dashboard WebSocket error: {e}")
    finally:
        dashboard_ws_manager.disconnect(websocket)


async def _send_periodic_updates(websocket: WebSocket):
    """Send metrics updates every 30 seconds"""
    try:
        while True:
            await asyncio.sleep(30)  # Update every 30 seconds
            await _send_metrics_update(websocket)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error in periodic update: {e}")


async def _send_metrics_update(websocket: WebSocket):
    """Fetch and send current metrics"""
    try:
        from backend.utils.time import utc_now

        db = get_db()
        try:
            now = utc_now()
            time_filter = _get_time_filter("24h", now)

            # Backtest metrics
            backtest_query = db.query(Backtest)
            if time_filter:
                backtest_query = backtest_query.filter(Backtest.created_at >= time_filter)

            total = backtest_query.count()
            completed = backtest_query.filter(Backtest.status == BacktestStatus.COMPLETED).count()
            running = backtest_query.filter(Backtest.status == BacktestStatus.RUNNING).count()
            failed = backtest_query.filter(Backtest.status == BacktestStatus.FAILED).count()

            # Strategy metrics
            total_strategies = db.query(Strategy).count()
            active_strategies = db.query(Strategy).filter(Strategy.status == StrategyStatus.ACTIVE).count()

            update_data = {
                "type": "metrics_update",
                "data": {
                    "backtests": {
                        "total": total,
                        "completed": completed,
                        "running": running,
                        "failed": failed,
                        "success_rate": round(completed / total, 3) if total > 0 else 0.0,
                    },
                    "strategies": {
                        "total": total_strategies,
                        "active": active_strategies,
                    },
                },
                "timestamp": now.isoformat(),
            }

            await websocket.send_json(update_data)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error sending metrics update: {e}")
