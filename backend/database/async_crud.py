"""Асинхронный CRUD-слой для PostgreSQL с использованием SQLAlchemy ORM."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import desc

from backend.database.models import (
    Backtest,
    BacktestCreate,
    BacktestStatus,
    BacktestUpdate,
    Strategy,
    StrategyCreate,
    StrategyUpdate,
    Trade,
    TradeCreate,
    TradeUpdate,
)
from backend.models import Backtest as BacktestORM
from backend.models import Strategy as StrategyORM
from backend.models import Trade as TradeORM


def _decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _to_strategy_schema(obj: StrategyORM) -> Strategy:
    return Strategy.model_validate(obj, from_attributes=True)


def _to_backtest_schema(obj: BacktestORM) -> Backtest:
    return Backtest.model_validate(obj, from_attributes=True)


def _to_trade_schema(obj: TradeORM) -> Trade:
    return Trade.model_validate(obj, from_attributes=True)


async def _fetch_scalars(session: AsyncSession, stmt: Select) -> Iterable[Any]:
    result = await session.execute(stmt)
    return result.scalars()


async def create_strategy(session: AsyncSession, payload: StrategyCreate) -> Strategy:
    db_obj = StrategyORM(
        name=payload.name,
        description=payload.description,
        strategy_type=payload.strategy_type,
        config=payload.config or {},
        user_id=payload.user_id,
        is_active=True,
    )
    try:
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        logger.info("✅ Strategy created [id=%s]", db_obj.id)
        return _to_strategy_schema(db_obj)
    except IntegrityError as exc:
        await session.rollback()
        logger.error("❌ Strategy create failed: %s", exc)
        raise


async def get_strategy(session: AsyncSession, strategy_id: int) -> Optional[Strategy]:
    db_obj = await session.get(StrategyORM, strategy_id)
    if not db_obj:
        return None
    return _to_strategy_schema(db_obj)


async def get_strategies(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
) -> List[Strategy]:
    stmt = select(StrategyORM).order_by(desc(StrategyORM.created_at)).offset(skip).limit(limit)
    if is_active is not None:
        stmt = stmt.where(StrategyORM.is_active.is_(is_active))

    items = (await _fetch_scalars(session, stmt)).all()
    return [_to_strategy_schema(item) for item in items]


async def update_strategy(
    session: AsyncSession,
    strategy_id: int,
    payload: StrategyUpdate,
) -> Optional[Strategy]:
    db_obj = await session.get(StrategyORM, strategy_id)
    if not db_obj:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(db_obj, field, value)

    await session.commit()
    await session.refresh(db_obj)
    return _to_strategy_schema(db_obj)


async def delete_strategy(session: AsyncSession, strategy_id: int) -> bool:
    db_obj = await session.get(StrategyORM, strategy_id)
    if not db_obj:
        return False

    await session.delete(db_obj)
    await session.commit()
    return True


async def get_strategy_performance(
    session: AsyncSession,
    strategy_id: int,
) -> Dict[str, Optional[float]]:
    stmt = (
        select(
            func.count(BacktestORM.id).label("total_backtests"),
            func.avg(BacktestORM.total_return).label("avg_return"),
            func.avg(BacktestORM.sharpe_ratio).label("avg_sharpe"),
            func.avg(BacktestORM.win_rate).label("avg_win_rate"),
            func.max(BacktestORM.total_return).label("best_return"),
            func.min(BacktestORM.total_return).label("worst_return"),
            func.max(BacktestORM.created_at).label("last_backtest"),
        )
        .where(BacktestORM.strategy_id == strategy_id)
        .where(BacktestORM.status == "completed")
    )

    result = await session.execute(stmt)
    row = result.one()

    return {
        "strategy_id": strategy_id,
        "total_backtests": row.total_backtests or 0,
        "avg_return": _decimal_to_float(row.avg_return),
        "avg_sharpe": _decimal_to_float(row.avg_sharpe),
        "avg_win_rate": _decimal_to_float(row.avg_win_rate),
        "best_return": _decimal_to_float(row.best_return),
        "worst_return": _decimal_to_float(row.worst_return),
        "last_backtest": row.last_backtest,
    }


async def get_top_strategies(
    session: AsyncSession,
    *,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    stmt = (
        select(
            StrategyORM.id.label("strategy_id"),
            StrategyORM.name,
            func.avg(BacktestORM.total_return).label("avg_return"),
            func.avg(BacktestORM.sharpe_ratio).label("avg_sharpe"),
            func.count(BacktestORM.id).label("runs"),
        )
        .join(BacktestORM, BacktestORM.strategy_id == StrategyORM.id)
        .where(BacktestORM.status == "completed")
        .group_by(StrategyORM.id, StrategyORM.name)
        .order_by(desc(func.avg(BacktestORM.total_return)))
        .limit(limit)
    )

    result = await session.execute(stmt)
    items: List[Dict[str, Any]] = []
    for row in result:
        items.append(
            {
                "strategy_id": row.strategy_id,
                "strategy_name": row.name,
                "avg_return": _decimal_to_float(row.avg_return),
                "avg_sharpe": _decimal_to_float(row.avg_sharpe),
                "runs": row.runs,
            }
        )
    return items


async def create_backtest(session: AsyncSession, payload: BacktestCreate) -> Backtest:
    db_obj = BacktestORM(
        strategy_id=payload.strategy_id,
        user_id=payload.user_id,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        start_date=payload.start_date,
        end_date=payload.end_date,
        initial_capital=payload.initial_capital,
        leverage=payload.leverage,
        commission=payload.commission,
        config=payload.config or {},
        status=BacktestStatus.PENDING.value,
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return _to_backtest_schema(db_obj)


async def get_backtest(session: AsyncSession, backtest_id: int) -> Optional[Backtest]:
    db_obj = await session.get(BacktestORM, backtest_id)
    if not db_obj:
        return None
    return _to_backtest_schema(db_obj)


async def get_backtests(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    strategy_id: Optional[int] = None,
    status: Optional[BacktestStatus] = None,
) -> List[Backtest]:
    stmt = select(BacktestORM).order_by(desc(BacktestORM.created_at)).offset(skip).limit(limit)

    if strategy_id is not None:
        stmt = stmt.where(BacktestORM.strategy_id == strategy_id)
    if status is not None:
        stmt = stmt.where(BacktestORM.status == status.value)

    items = (await _fetch_scalars(session, stmt)).all()
    return [_to_backtest_schema(item) for item in items]


async def update_backtest(
    session: AsyncSession,
    backtest_id: int,
    payload: BacktestUpdate,
) -> Optional[Backtest]:
    db_obj = await session.get(BacktestORM, backtest_id)
    if not db_obj:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, BacktestStatus):
            value = value.value
        setattr(db_obj, field, value)

    await session.commit()
    await session.refresh(db_obj)
    return _to_backtest_schema(db_obj)


async def create_trade(session: AsyncSession, payload: TradeCreate) -> Trade:
    db_obj = TradeORM(
        backtest_id=payload.backtest_id,
        entry_time=payload.entry_time,
        side=payload.side.value,
        entry_price=payload.entry_price,
        quantity=payload.quantity,
        exit_time=payload.exit_time,
        exit_price=payload.exit_price,
        pnl=payload.pnl,
        return_pct=payload.return_pct,
        commission=payload.commission,
        status=(payload.status.value if payload.status else None),
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return _to_trade_schema(db_obj)


async def get_trades(
    session: AsyncSession,
    backtest_id: int,
    *,
    skip: int = 0,
    limit: int = 1000,
) -> List[Trade]:
    stmt = (
        select(TradeORM)
        .where(TradeORM.backtest_id == backtest_id)
        .order_by(TradeORM.entry_time)
        .offset(skip)
        .limit(limit)
    )

    items = (await _fetch_scalars(session, stmt)).all()
    return [_to_trade_schema(item) for item in items]


async def update_trade(
    session: AsyncSession,
    trade_id: int,
    payload: TradeUpdate,
) -> Optional[Trade]:
    db_obj = await session.get(TradeORM, trade_id)
    if not db_obj:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        if hasattr(value, "value"):
            value = value.value
        setattr(db_obj, field, value)

    await session.commit()
    await session.refresh(db_obj)
    return _to_trade_schema(db_obj)


async def get_recent_backtests(session: AsyncSession, *, limit: int = 20) -> List[Dict[str, Any]]:
    stmt = (
        select(
            BacktestORM.id,
            BacktestORM.created_at,
            BacktestORM.status,
            BacktestORM.total_return,
            BacktestORM.sharpe_ratio,
            StrategyORM.id.label("strategy_id"),
            StrategyORM.name.label("strategy_name"),
        )
        .join(StrategyORM, StrategyORM.id == BacktestORM.strategy_id)
        .order_by(desc(BacktestORM.created_at))
        .limit(limit)
    )

    result = await session.execute(stmt)
    items: List[Dict[str, Any]] = []
    for row in result:
        items.append(
            {
                "backtest_id": row.id,
                "created_at": row.created_at,
                "status": row.status,
                "total_return": _decimal_to_float(row.total_return),
                "sharpe_ratio": _decimal_to_float(row.sharpe_ratio),
                "strategy_id": row.strategy_id,
                "strategy_name": row.strategy_name,
            }
        )
    return items


async def get_results_summary(session: AsyncSession) -> Dict[str, Any]:
    totals_stmt = select(
        func.count(BacktestORM.id),
        func.count().filter(BacktestORM.status == "completed"),
        func.avg(BacktestORM.total_return),
        func.avg(BacktestORM.sharpe_ratio),
        func.max(BacktestORM.total_return),
    )
    totals = (await session.execute(totals_stmt)).one()

    best_stmt = (
        select(
            StrategyORM.id,
            StrategyORM.name,
            func.avg(BacktestORM.total_return).label("avg_return"),
        )
        .join(StrategyORM, StrategyORM.id == BacktestORM.strategy_id)
        .where(BacktestORM.status == "completed")
        .group_by(StrategyORM.id, StrategyORM.name)
        .order_by(desc(func.avg(BacktestORM.total_return)))
        .limit(1)
    )
    best_result = await session.execute(best_stmt)
    best = best_result.first()

    summary: Dict[str, Any] = {
        "total_backtests": totals[0] or 0,
        "completed_backtests": totals[1] or 0,
        "avg_return": _decimal_to_float(totals[2]),
        "avg_sharpe": _decimal_to_float(totals[3]),
        "best_return": _decimal_to_float(totals[4]),
    }

    if best:
        summary["best_strategy_id"] = best.id
        summary["best_strategy_name"] = best.name
        summary["best_strategy_avg_return"] = _decimal_to_float(best.avg_return)

    return summary
