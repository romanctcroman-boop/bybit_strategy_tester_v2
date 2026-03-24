"""
Validate DCA backtest pipeline payload for frontend rendering.

Checks:
1) Strategy Builder backtest endpoint executes for a saved strategy.
2) Response contains DCA trade fields required by chart rendering.
3) Response contains metrics fields required by metrics table/cards.

Usage:
    py -3.14 scripts/validate_dca_pipeline.py --strategy-name "DCA-RSI-3"
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Force local project SQLite when DATABASE_URL is not set.
# This avoids accidental in-memory DB initialization during app bootstrap.
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{(Path(__file__).resolve().parents[1] / 'data.sqlite3').as_posix()}",
)

# Ensure local workspace package is used (not a site-packages shadow copy).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.database import SessionLocal
from backend.database.models.strategy import Strategy, StrategyStatus

FRONTEND_DCA_TRADE_FIELDS = {
    "entry_time",
    "exit_time",
    "side",
    "entry_price",
    "exit_price",
    "pnl",
    "pnl_pct",
    "trade_number",
    "dca_orders_filled",
    "dca_levels",
    "dca_grid_prices",
    "dca_avg_entry_price",
    "dca_total_size_usd",
    "tp_price",
    "sl_price",
}

FRONTEND_METRIC_FIELDS = {
    "total_return",
    "win_rate",
    "profit_factor",
    "sharpe_ratio",
    "total_trades",
    "max_drawdown",
    "net_profit",
    "net_profit_pct",
    "gross_profit",
    "gross_loss",
    "avg_win",
    "avg_loss",
    "largest_win",
    "largest_loss",
    "avg_bars_in_trade",
    "recovery_factor",
    "expectancy",
    "sortino_ratio",
    "calmar_ratio",
    "max_consecutive_wins",
    "max_consecutive_losses",
}


@dataclass
class ValidationResult:
    ok: bool
    backtest_id: str | None
    status: str | None
    trades_total: int
    dca_trades: int
    filled_levels_total: int
    planned_grid_levels_total: int
    missing_trade_fields: set[str]
    missing_metric_fields: set[str]


def _select_strategy_id(strategy_name: str) -> str:
    db = SessionLocal()
    try:
        rows = (
            db.query(Strategy)
            .filter(
                Strategy.name == strategy_name,
                Strategy.is_builder_strategy == True,  # noqa: E712
                Strategy.is_deleted == False,  # noqa: E712
                Strategy.status != StrategyStatus.ARCHIVED,
            )
            .order_by(Strategy.updated_at.desc())
            .all()
        )
        if not rows:
            raise RuntimeError(f"Builder strategy '{strategy_name}' not found")
        return str(rows[0].id)
    finally:
        db.close()


def run_validation(
    strategy_id: str,
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    market_type: str,
    direction: str,
) -> ValidationResult:
    payload: dict[str, Any] = {
        "symbol": symbol,
        "interval": interval,
        "start_date": start_date,
        "end_date": end_date,
        "market_type": market_type,
        "direction": direction,
        "initial_capital": 10000,
        "position_size": 1.0,
        "position_size_type": "percent",
        "commission": 0.0007,
        "slippage": 0.0,
        "leverage": 10,
        "pyramiding": 10,
        # Force DCA engine path during validation to avoid ambiguous auto-selection.
        "dca_enabled": True,
    }

    with TestClient(app) as client:
        response = client.post(f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest", json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Backtest failed: {response.status_code} {response.text[:500]}")
        body = response.json()

    trades = body.get("trades") or []
    metrics = body.get("metrics") or {}

    dca_trades = [
        t
        for t in trades
        if (t.get("dca_orders_filled") or 0) > 0 or (t.get("dca_levels") or []) or (t.get("dca_grid_prices") or [])
    ]

    missing_trade_fields: set[str] = set()
    if dca_trades:
        sample_trade_fields = set(dca_trades[0].keys())
        missing_trade_fields = FRONTEND_DCA_TRADE_FIELDS - sample_trade_fields

    missing_metric_fields = FRONTEND_METRIC_FIELDS - set(metrics.keys())

    filled_levels_total = sum(len(t.get("dca_levels") or []) for t in dca_trades)
    planned_grid_levels_total = sum(len(t.get("dca_grid_prices") or []) for t in dca_trades)

    ok = (
        body.get("status") == "completed"
        and len(trades) > 0
        and len(dca_trades) > 0
        and not missing_trade_fields
        and not missing_metric_fields
    )

    return ValidationResult(
        ok=ok,
        backtest_id=body.get("backtest_id"),
        status=body.get("status"),
        trades_total=len(trades),
        dca_trades=len(dca_trades),
        filled_levels_total=filled_levels_total,
        planned_grid_levels_total=planned_grid_levels_total,
        missing_trade_fields=missing_trade_fields,
        missing_metric_fields=missing_metric_fields,
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate DCA backtest payload for frontend charts/metrics.")
    p.add_argument("--strategy-id", default=None, help="Builder strategy id (takes priority over --strategy-name)")
    p.add_argument("--strategy-name", default="DCA-RSI-3", help="Builder strategy name in DB")
    p.add_argument("--symbol", default="ETHUSDT")
    p.add_argument("--interval", default="30")
    p.add_argument("--start-date", default="2026-02-01T00:00:00")
    p.add_argument("--end-date", default="2026-03-01T00:00:00")
    p.add_argument("--market-type", default="linear", choices=["linear", "spot"])
    p.add_argument("--direction", default="long", choices=["long", "short", "both"])
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    strategy_id = args.strategy_id or _select_strategy_id(args.strategy_name)
    result = run_validation(
        strategy_id=strategy_id,
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start_date,
        end_date=args.end_date,
        market_type=args.market_type,
        direction=args.direction,
    )

    print(f"timestamp: {datetime.now(UTC).isoformat()}")
    print(f"strategy_id: {strategy_id}")
    print(f"backtest_id: {result.backtest_id}")
    print(f"status: {result.status}")
    print(f"trades_total: {result.trades_total}")
    print(f"dca_trades: {result.dca_trades}")
    print(f"filled_levels_total: {result.filled_levels_total}")
    print(f"planned_grid_levels_total: {result.planned_grid_levels_total}")
    print(f"missing_trade_fields: {sorted(result.missing_trade_fields)}")
    print(f"missing_metric_fields: {sorted(result.missing_metric_fields)}")
    print(f"ok: {result.ok}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
