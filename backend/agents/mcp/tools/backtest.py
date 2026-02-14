"""
Backtest Execution Tools

Run backtests and retrieve metrics from the database.
Auto-registered with the global MCP tool registry on import.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from backend.agents.mcp.tool_registry import get_tool_registry

registry = get_tool_registry()


@registry.register(
    name="run_backtest",
    description=(
        "Run a strategy backtest and return key metrics. "
        "Uses FallbackEngineV4 (gold standard), commission=0.0007. "
        "Supported strategies: sma_crossover, rsi, macd, bollinger_bands, grid, dca, martingale."
    ),
    category="backtesting",
)
async def run_backtest(
    symbol: str = "BTCUSDT",
    interval: str = "15",
    strategy_type: str = "rsi",
    strategy_params: dict[str, Any] | None = None,
    start_date: str = "2025-06-01",
    end_date: str = "2025-07-01",
    initial_capital: float = 10000.0,
    leverage: float = 10.0,
    direction: str = "both",
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> dict[str, Any]:
    """
    Run a strategy backtest via BacktestService.

    Args:
        symbol: Trading pair (e.g. BTCUSDT, ETHUSDT)
        interval: Timeframe — one of: 1, 5, 15, 30, 60, 240, D, W, M
        strategy_type: Strategy name (sma_crossover, rsi, macd, bollinger_bands, etc.)
        strategy_params: Strategy-specific parameters
        start_date: Start date YYYY-MM-DD (not before 2025-01-01)
        end_date: End date YYYY-MM-DD
        initial_capital: Starting capital in USDT (100 - 100_000_000)
        leverage: Leverage 1-125x
        direction: "long", "short", or "both"
        stop_loss: Stop loss as fraction (e.g. 0.02 = 2%)
        take_profit: Take profit as fraction (e.g. 0.03 = 3%)

    Returns:
        Dict with metrics (sharpe, win_rate, total_return, etc.) and trade count
    """
    from datetime import datetime as dt

    try:
        from backend.backtesting.models import BacktestConfig, StrategyType
        from backend.backtesting.service import BacktestService

        # Validate strategy type
        valid_strategies = {e.value for e in StrategyType}
        if strategy_type not in valid_strategies:
            return {
                "error": f"Unknown strategy: {strategy_type}",
                "valid_strategies": sorted(valid_strategies),
            }

        # Validate interval
        valid_intervals = {"1", "5", "15", "30", "60", "240", "D", "W", "M"}
        if interval not in valid_intervals:
            return {"error": f"Invalid interval: {interval}", "valid": sorted(valid_intervals)}

        # Validate dates
        try:
            sd = dt.fromisoformat(start_date)
            ed = dt.fromisoformat(end_date)
        except ValueError as e:
            return {"error": f"Invalid date format: {e}. Use YYYY-MM-DD"}

        if sd >= ed:
            return {"error": "start_date must be before end_date"}

        # Validate capital / leverage bounds
        if not (100 <= initial_capital <= 100_000_000):
            return {"error": "initial_capital must be 100 — 100M"}
        if not (1 <= leverage <= 125):
            return {"error": "leverage must be 1 — 125"}

        config = BacktestConfig(
            symbol=symbol,
            interval=interval,
            start_date=sd,
            end_date=ed,
            strategy_type=strategy_type,
            strategy_params=strategy_params or {},
            initial_capital=initial_capital,
            leverage=leverage,
            direction=direction,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        service = BacktestService()

        # --- P2 Sandbox: timeout + memory guard ---
        import asyncio

        import psutil

        mem = psutil.virtual_memory()
        free_mb = mem.available / (1024 * 1024)
        if free_mb < 512:
            return {
                "error": f"Insufficient memory: {free_mb:.0f}MB free (min 512MB). "
                "Close other applications or reduce backtest scope.",
                "free_memory_mb": round(free_mb),
            }

        BACKTEST_TIMEOUT = 300  # seconds
        try:
            result = await asyncio.wait_for(
                service.run_backtest(config),
                timeout=BACKTEST_TIMEOUT,
            )
        except TimeoutError:
            return {
                "error": f"Backtest timed out after {BACKTEST_TIMEOUT}s. Try a shorter date range or simpler strategy.",
                "timeout_seconds": BACKTEST_TIMEOUT,
            }

        if result.error_message:
            return {"error": result.error_message, "status": str(result.status)}

        metrics = result.metrics
        if not metrics:
            return {"error": "Backtest completed but no metrics generated"}

        return {
            "status": "completed",
            "symbol": symbol,
            "interval": interval,
            "strategy": strategy_type,
            "strategy_params": strategy_params or {},
            "total_trades": metrics.total_trades,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "win_rate": round(metrics.win_rate, 2),
            "total_return_pct": round(metrics.total_return, 2),
            "final_capital": round(metrics.final_capital, 2),
            "max_drawdown_pct": round(metrics.max_drawdown, 2),
            "sharpe_ratio": round(metrics.sharpe_ratio, 4),
            "profit_factor": round(getattr(metrics, "profit_factor", 0), 4),
            "avg_trade_pct": round(getattr(metrics, "avg_trade", 0), 4),
            "commission_rate": 0.0007,
            "engine": "FallbackEngineV4",
        }

    except Exception as e:
        logger.error(f"run_backtest tool error: {e}")
        return {"error": str(e)}


@registry.register(
    name="get_backtest_metrics",
    description=(
        "Retrieve metrics for a completed backtest from the database by ID. "
        "Also supports listing recent backtests when called without an ID."
    ),
    category="backtesting",
)
async def get_backtest_metrics(
    backtest_id: int | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Get backtest results from the database.

    Args:
        backtest_id: Specific backtest ID to retrieve. If None, returns recent backtests.
        limit: Number of recent backtests to return (default: 10, max: 50)

    Returns:
        Metrics dict for a specific backtest, or list of recent backtests
    """
    import asyncio

    try:
        from backend.database import SessionLocal
        from backend.database.models import Backtest

        limit = min(limit, 50)

        def _query():
            db = SessionLocal()
            try:
                if backtest_id is not None:
                    bt = db.query(Backtest).filter(Backtest.id == backtest_id).first()
                    if not bt:
                        return {"error": f"Backtest {backtest_id} not found"}
                    return {
                        "id": bt.id,
                        "symbol": bt.symbol,
                        "interval": getattr(bt, "interval", "?"),
                        "strategy_type": getattr(bt, "strategy_type", "?"),
                        "status": getattr(bt, "status", "?"),
                        "total_trades": getattr(bt, "total_trades", 0),
                        "win_rate": float(getattr(bt, "win_rate", 0) or 0),
                        "total_return": float(getattr(bt, "total_return", 0) or 0),
                        "sharpe_ratio": float(getattr(bt, "sharpe_ratio", 0) or 0),
                        "max_drawdown": float(getattr(bt, "max_drawdown", 0) or 0),
                        "final_capital": float(getattr(bt, "final_capital", 0) or 0),
                        "created_at": str(getattr(bt, "created_at", "")),
                    }
                else:
                    backtests = db.query(Backtest).order_by(Backtest.id.desc()).limit(limit).all()
                    return {
                        "count": len(backtests),
                        "backtests": [
                            {
                                "id": bt.id,
                                "symbol": bt.symbol,
                                "strategy_type": getattr(bt, "strategy_type", "?"),
                                "status": getattr(bt, "status", "?"),
                                "total_trades": getattr(bt, "total_trades", 0),
                                "win_rate": float(getattr(bt, "win_rate", 0) or 0),
                                "total_return": float(getattr(bt, "total_return", 0) or 0),
                                "sharpe_ratio": float(getattr(bt, "sharpe_ratio", 0) or 0),
                                "created_at": str(getattr(bt, "created_at", "")),
                            }
                            for bt in backtests
                        ],
                    }
            finally:
                db.close()

        return await asyncio.to_thread(_query)

    except Exception as e:
        logger.error(f"get_backtest_metrics tool error: {e}")
        return {"error": str(e)}
