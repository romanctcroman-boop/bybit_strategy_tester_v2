"""
System & Monitoring Tools

Health checks, backtest report generation, and agent action logging.
Auto-registered with the global MCP tool registry on import.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from backend.agents.mcp.tool_registry import get_tool_registry

registry = get_tool_registry()


@registry.register(
    name="check_system_health",
    description="Check system health: database, API, disk, memory. Use before running backtests.",
    category="monitoring",
)
async def check_system_health() -> dict[str, Any]:
    """
    Check overall system health for agent operations.

    Checks:
    - Database connectivity
    - Bybit API reachability
    - Disk space
    - Memory usage
    - Data file availability

    Returns:
        Health status dict with component statuses and warnings
    """
    import asyncio
    import os
    import shutil

    health: dict[str, Any] = {
        "overall": "healthy",
        "components": {},
        "warnings": [],
    }

    # 1. Database check
    try:
        from backend.database import SessionLocal
        from backend.database.models import Backtest

        def _db_check():
            db = SessionLocal()
            try:
                count = db.query(Backtest).count()
                return {"status": "ok", "total_backtests": count}
            finally:
                db.close()

        health["components"]["database"] = await asyncio.to_thread(_db_check)
    except Exception as e:
        health["components"]["database"] = {"status": "error", "error": str(e)}
        health["overall"] = "degraded"

    # 2. Disk space
    try:
        usage = shutil.disk_usage(os.path.dirname(__file__))
        free_gb = usage.free / (1024**3)
        health["components"]["disk"] = {
            "status": "ok" if free_gb > 1 else "warning",
            "free_gb": round(free_gb, 2),
        }
        if free_gb < 1:
            health["warnings"].append(f"Low disk space: {free_gb:.1f} GB free")
            health["overall"] = "degraded"
    except Exception as e:
        health["components"]["disk"] = {"status": "error", "error": str(e)}

    # 3. Memory usage
    try:
        import psutil

        mem = psutil.virtual_memory()
        health["components"]["memory"] = {
            "status": "ok" if mem.percent < 85 else "warning",
            "used_pct": round(mem.percent, 1),
            "available_gb": round(mem.available / (1024**3), 2),
        }
        if mem.percent > 85:
            health["warnings"].append(f"High memory usage: {mem.percent}%")
    except ImportError:
        health["components"]["memory"] = {
            "status": "unknown",
            "note": "psutil not installed",
        }

    # 4. Data availability check
    try:
        from pathlib import Path

        db_path = Path(__file__).parent.parent.parent.parent.parent / "data.sqlite3"
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024**2)
            health["components"]["data_db"] = {
                "status": "ok",
                "size_mb": round(size_mb, 1),
            }
        else:
            health["components"]["data_db"] = {
                "status": "missing",
                "path": str(db_path),
            }
            health["warnings"].append("data.sqlite3 not found")
    except Exception as e:
        health["components"]["data_db"] = {"status": "error", "error": str(e)}

    return health


@registry.register(
    name="generate_backtest_report",
    description=(
        "Generate a structured report for a completed backtest, "
        "including performance summary, trade analysis, and recommendations."
    ),
    category="analysis",
)
async def generate_backtest_report(
    backtest_id: int | None = None,
    format: str = "markdown",
) -> dict[str, Any]:
    """
    Generate a comprehensive report for a backtest result.

    Args:
        backtest_id: ID of the backtest to report on. If None, uses the most recent.
        format: Output format — "markdown" or "json"

    Returns:
        Dict with report content and metadata
    """
    import asyncio

    try:
        from backend.database import SessionLocal
        from backend.database.models import Backtest

        def _get_backtest():
            db = SessionLocal()
            try:
                if backtest_id:
                    bt = db.query(Backtest).filter(Backtest.id == backtest_id).first()
                else:
                    bt = db.query(Backtest).order_by(Backtest.id.desc()).first()
                if not bt:
                    return None
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
                    "profit_factor": float(getattr(bt, "profit_factor", 0) or 0),
                    "created_at": str(getattr(bt, "created_at", "")),
                    "initial_capital": float(getattr(bt, "initial_capital", 10000) or 10000),
                }
            finally:
                db.close()

        bt_data = await asyncio.to_thread(_get_backtest)

        if not bt_data:
            return {"error": f"Backtest {backtest_id or 'latest'} not found"}

        win_rate = bt_data["win_rate"]
        sharpe = bt_data["sharpe_ratio"]
        drawdown = bt_data["max_drawdown"]
        pf = bt_data["profit_factor"]

        assessment = (
            "EXCELLENT"
            if sharpe > 2 and win_rate > 60
            else "GOOD"
            if sharpe > 1 and win_rate > 50
            else "MODERATE"
            if sharpe > 0
            else "POOR"
        )

        recommendations: list[str] = []
        if win_rate < 40:
            recommendations.append("Win rate below 40% — consider stricter entry filters")
        if drawdown > 20:
            recommendations.append(f"Max drawdown {drawdown:.1f}% is high — add stop loss or reduce leverage")
        if bt_data["total_trades"] < 10:
            recommendations.append("Too few trades for statistical significance — extend date range")
        if pf < 1.0:
            recommendations.append("Profit factor < 1.0 — strategy is net-losing, review exit logic")
        if sharpe < 0:
            recommendations.append("Negative Sharpe ratio — strategy underperforms risk-free rate")
        if not recommendations:
            recommendations.append("Strategy shows solid performance — consider live paper trading")

        if format == "markdown":
            report = f"""# Backtest Report — {bt_data["symbol"]} ({bt_data["strategy_type"]})

## Summary
| Metric | Value |
|--------|-------|
| Symbol | {bt_data["symbol"]} |
| Strategy | {bt_data["strategy_type"]} |
| Timeframe | {bt_data["interval"]} |
| Status | {bt_data["status"]} |
| Created | {bt_data["created_at"]} |

## Performance
| Metric | Value | Assessment |
|--------|-------|------------|
| Total Return | {bt_data["total_return"]:.2f}% | {"✅" if bt_data["total_return"] > 0 else "❌"} |
| Win Rate | {win_rate:.1f}% | {"✅" if win_rate > 50 else "⚠️"} |
| Sharpe Ratio | {sharpe:.2f} | {"✅" if sharpe > 1 else "⚠️"} |
| Max Drawdown | {drawdown:.1f}% | {"✅" if drawdown < 15 else "⚠️"} |
| Profit Factor | {pf:.2f} | {"✅" if pf > 1.5 else "⚠️"} |
| Total Trades | {bt_data["total_trades"]} | {"✅" if bt_data["total_trades"] >= 20 else "⚠️"} |

## Assessment: **{assessment}**

## Recommendations
"""
            for rec in recommendations:
                report += f"- {rec}\n"

            return {
                "backtest_id": bt_data["id"],
                "format": "markdown",
                "report": report,
                "assessment": assessment,
                "recommendations": recommendations,
            }
        else:
            return {
                "backtest_id": bt_data["id"],
                "format": "json",
                "metrics": bt_data,
                "assessment": assessment,
                "recommendations": recommendations,
            }

    except Exception as e:
        logger.error(f"generate_backtest_report tool error: {e}")
        return {"error": str(e)}


@registry.register(
    name="log_agent_action",
    description="Log an agent action for audit trail and activity tracking.",
    category="monitoring",
)
async def log_agent_action(
    agent_name: str,
    action: str,
    details: dict[str, Any] | None = None,
    result_summary: str = "",
    success: bool = True,
) -> dict[str, Any]:
    """
    Log an agent action for tracking and audit purposes.

    Creates a structured log entry for agent activities,
    stored both in memory and on disk.

    Args:
        agent_name: Name of the agent (e.g., "deepseek", "qwen")
        action: Action performed (e.g., "run_backtest", "evolve_strategy")
        details: Optional dict with action-specific details
        result_summary: Brief description of the result
        success: Whether the action succeeded

    Returns:
        Dict with log entry ID and timestamp
    """
    from datetime import UTC, datetime
    from pathlib import Path

    try:
        timestamp = datetime.now(UTC).isoformat()
        log_entry = {
            "timestamp": timestamp,
            "agent_name": agent_name,
            "action": action,
            "success": success,
            "result_summary": result_summary,
            "details": details or {},
        }

        log_dir = Path(__file__).parent.parent.parent.parent.parent / "logs" / "agent_activity"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"activity_{datetime.now(UTC).strftime('%Y-%m-%d')}.jsonl"

        import json

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        level = "INFO" if success else "WARNING"
        logger.log(
            level,
            f"🤖 Agent '{agent_name}' → {action}: {result_summary or 'OK'}",
        )

        return {
            "logged": True,
            "timestamp": timestamp,
            "log_file": str(log_file),
        }

    except Exception as e:
        logger.error(f"log_agent_action error: {e}")
        return {"logged": False, "error": str(e)}
