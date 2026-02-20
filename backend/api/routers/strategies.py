"""
Strategies Router
Full CRUD endpoints for managing trading strategies.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from sqlalchemy.orm import Session

from backend.api.schemas import (
    ParameterMeta,
    StrategyCreate,
    StrategyDefaultParameters,
    StrategyListResponse,
    StrategyResponse,
    StrategyUpdate,
)
from backend.database import get_db
from backend.database.models import Strategy, StrategyStatus, StrategyType

logger = logging.getLogger(__name__)
router = APIRouter()


def _strategy_to_response(strategy: Strategy) -> StrategyResponse:
    """Convert SQLAlchemy Strategy model to StrategyResponse.

    Uses explicit casts for SQLAlchemy ``Column`` descriptors so that
    Mypy sees plain Python types matching the Pydantic model fields.
    """
    st_type: str = cast(StrategyType, strategy.strategy_type).value if strategy.strategy_type else "custom"
    st_status: str = cast(StrategyStatus, strategy.status).value if strategy.status else "draft"
    params: dict[str, Any] = cast("dict[str, Any]", strategy.parameters) or {}
    tag_list: list[str] = cast("list[str]", strategy.tags) or []

    return StrategyResponse(
        id=cast(str, strategy.id),
        name=cast(str, strategy.name),
        description=cast("str | None", strategy.description),
        strategy_type=st_type,
        status=st_status,
        parameters=params,
        symbol=cast("str | None", strategy.symbol),
        timeframe=cast("str | None", strategy.timeframe),
        initial_capital=cast("float | None", strategy.initial_capital),
        position_size=cast("float | None", strategy.position_size),
        stop_loss_pct=cast("float | None", strategy.stop_loss_pct),
        take_profit_pct=cast("float | None", strategy.take_profit_pct),
        max_drawdown_pct=cast("float | None", strategy.max_drawdown_pct),
        total_return=cast("float | None", strategy.total_return),
        sharpe_ratio=cast("float | None", strategy.sharpe_ratio),
        win_rate=cast("float | None", strategy.win_rate),
        total_trades=cast("int | None", strategy.total_trades),
        backtest_count=cast("int | None", strategy.backtest_count),
        created_at=cast("datetime | None", strategy.created_at),
        updated_at=cast("datetime | None", strategy.updated_at),
        last_backtest_at=cast("datetime | None", strategy.last_backtest_at),
        tags=tag_list,
        version=cast(int, strategy.version),
        is_active=cast(StrategyStatus, strategy.status) != StrategyStatus.ARCHIVED,
        config=params,
    )


@router.get("/", response_model=StrategyListResponse)
async def list_strategies(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
    strategy_type: str | None = Query(None, description="Filter by strategy type"),
    search: str | None = Query(None, max_length=100, description="Search by name"),
    db: Session = Depends(get_db),
):
    """
    List all strategies with pagination and filtering.

    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    - **status**: Filter by status (draft, active, paused, archived)
    - **strategy_type**: Filter by strategy type
    - **search**: Search by strategy name
    """
    try:
        # Build query
        query = db.query(Strategy).filter(Strategy.is_deleted.is_(False))

        # Apply filters
        if status:
            try:
                status_enum = StrategyStatus(status)
                query = query.filter(Strategy.status == status_enum)
            except ValueError:
                pass  # Ignore invalid status filter

        if strategy_type:
            try:
                type_enum = StrategyType(strategy_type)
                query = query.filter(Strategy.strategy_type == type_enum)
            except ValueError:
                pass  # Ignore invalid type filter

        if search:
            query = query.filter(Strategy.name.ilike(f"%{search}%"))

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        strategies = query.order_by(Strategy.created_at.desc()).offset(offset).limit(page_size).all()

        # Convert to response
        items = [_strategy_to_response(s) for s in strategies]

        return StrategyListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list strategies: {e!s}",
        )


@router.get("/types", response_model=list[StrategyDefaultParameters])
async def get_strategy_types():
    """
    Get list of available strategy types with their default parameters
    and optimization metadata (min, max, step) for each parameter.
    """
    strategy_types = [
        StrategyDefaultParameters(
            strategy_type="sma_crossover",
            parameters={"fast_period": 10, "slow_period": 30},
            parameters_meta={
                "fast_period": ParameterMeta(
                    default=10,
                    min=2,
                    max=200,
                    step=1,
                    param_type="int",
                    description="Fast SMA period",
                ),
                "slow_period": ParameterMeta(
                    default=30,
                    min=5,
                    max=500,
                    step=5,
                    param_type="int",
                    description="Slow SMA period",
                ),
            },
            description="Simple Moving Average Crossover - Buy when fast SMA crosses above slow SMA",
        ),
        StrategyDefaultParameters(
            strategy_type="rsi",
            parameters={"period": 14, "overbought": 70, "oversold": 30},
            parameters_meta={
                "period": ParameterMeta(
                    default=14,
                    min=2,
                    max=50,
                    step=1,
                    param_type="int",
                    description="RSI period (recommended 7-21)",
                ),
                "overbought": ParameterMeta(
                    default=70,
                    min=50,
                    max=95,
                    step=5,
                    param_type="int",
                    description="Overbought threshold",
                ),
                "oversold": ParameterMeta(
                    default=30,
                    min=5,
                    max=50,
                    step=5,
                    param_type="int",
                    description="Oversold threshold",
                ),
            },
            description="RSI Strategy - Buy when oversold, sell when overbought",
        ),
        StrategyDefaultParameters(
            strategy_type="macd",
            parameters={"fast_period": 12, "slow_period": 26, "signal_period": 9},
            parameters_meta={
                "fast_period": ParameterMeta(
                    default=12,
                    min=2,
                    max=50,
                    step=1,
                    param_type="int",
                    description="MACD fast EMA period",
                ),
                "slow_period": ParameterMeta(
                    default=26,
                    min=10,
                    max=100,
                    step=2,
                    param_type="int",
                    description="MACD slow EMA period",
                ),
                "signal_period": ParameterMeta(
                    default=9,
                    min=2,
                    max=30,
                    step=1,
                    param_type="int",
                    description="MACD signal line period",
                ),
            },
            description="MACD Strategy - Buy on MACD/Signal crossover",
        ),
        StrategyDefaultParameters(
            strategy_type="bollinger_bands",
            parameters={"period": 20, "std_dev": 2.0},
            parameters_meta={
                "period": ParameterMeta(
                    default=20,
                    min=5,
                    max=100,
                    step=5,
                    param_type="int",
                    description="Bollinger Bands period",
                ),
                "std_dev": ParameterMeta(
                    default=2.0,
                    min=0.5,
                    max=5.0,
                    step=0.25,
                    param_type="float",
                    description="Standard deviation multiplier",
                ),
            },
            description="Bollinger Bands - Buy at lower band, sell at upper band",
        ),
        StrategyDefaultParameters(
            strategy_type="bollinger_rsi",
            parameters={
                "bb_period": 20,
                "bb_std": 2.0,
                "rsi_period": 14,
                "rsi_overbought": 70,
                "rsi_oversold": 30,
            },
            parameters_meta={
                "bb_period": ParameterMeta(
                    default=20,
                    min=5,
                    max=100,
                    step=5,
                    param_type="int",
                    description="Bollinger Bands period",
                ),
                "bb_std": ParameterMeta(
                    default=2.0,
                    min=0.5,
                    max=5.0,
                    step=0.25,
                    param_type="float",
                    description="BB std deviation",
                ),
                "rsi_period": ParameterMeta(
                    default=14,
                    min=2,
                    max=50,
                    step=1,
                    param_type="int",
                    description="RSI period",
                ),
                "rsi_overbought": ParameterMeta(
                    default=70,
                    min=50,
                    max=95,
                    step=5,
                    param_type="int",
                    description="RSI overbought",
                ),
                "rsi_oversold": ParameterMeta(
                    default=30,
                    min=5,
                    max=50,
                    step=5,
                    param_type="int",
                    description="RSI oversold",
                ),
            },
            description="Combined Bollinger Bands and RSI strategy",
        ),
        StrategyDefaultParameters(
            strategy_type="custom",
            parameters={},
            parameters_meta={},  # Custom strategies define their own params
            description="Custom strategy with user-defined parameters (supports any range including negative)",
        ),
    ]
    return strategy_types


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    db: Session = Depends(get_db),
):
    """
    Get a specific strategy by ID.
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.is_deleted.is_(False)).first()

    if not strategy:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with id '{strategy_id}' not found",
        )

    return _strategy_to_response(strategy)


@router.post("/", response_model=StrategyResponse, status_code=http_status.HTTP_201_CREATED)
async def create_strategy(
    strategy_data: StrategyCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Create a new trading strategy.

    - **name**: Strategy name (required)
    - **strategy_type**: Type of strategy (sma_crossover, rsi, macd, bollinger_bands, custom)
    - **parameters**: Strategy-specific parameters
    - **symbol**: Trading symbol (e.g., BTCUSDT)
    - **timeframe**: Timeframe for analysis (e.g., 1h, 4h, 1d)
    """
    try:
        # Map enum to database enum
        try:
            db_strategy_type = StrategyType(strategy_data.strategy_type.value)
        except ValueError:
            db_strategy_type = StrategyType.CUSTOM

        # =========================================================================
        # VALIDATION: DCA strategy is uni-directional
        # =========================================================================
        if db_strategy_type == StrategyType.DCA:
            direction = (strategy_data.parameters or {}).get("_direction", "both")
            if direction == "both":
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="Стратегия DCA работает только в одном направлении. Выберите 'long' или 'short'.",
                )

        # Get default parameters if not provided
        parameters = strategy_data.parameters
        if not parameters:
            parameters = Strategy.get_default_parameters(db_strategy_type)

        # Create strategy
        strategy = Strategy(
            id=str(uuid.uuid4()),
            name=strategy_data.name,
            description=strategy_data.description,
            strategy_type=db_strategy_type,
            status=StrategyStatus.DRAFT,
            parameters=parameters,
            symbol=strategy_data.symbol,
            timeframe=strategy_data.timeframe,
            initial_capital=strategy_data.initial_capital,
            position_size=strategy_data.position_size,
            stop_loss_pct=strategy_data.stop_loss_pct,
            take_profit_pct=strategy_data.take_profit_pct,
            max_drawdown_pct=strategy_data.max_drawdown_pct,
            tags=strategy_data.tags or [],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        db.add(strategy)
        db.commit()
        db.refresh(strategy)

        logger.info(f"Created strategy: {strategy.id} - {strategy.name}")
        response.headers["Location"] = f"/api/v1/strategies/{strategy.id}"
        return _strategy_to_response(strategy)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating strategy: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create strategy: {e!s}",
        )


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: str,
    strategy_data: StrategyUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing strategy.

    Only provided fields will be updated.
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.is_deleted.is_(False)).first()

    if not strategy:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with id '{strategy_id}' not found",
        )

    try:
        # Update fields if provided
        update_data = strategy_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if value is not None:
                if field == "strategy_type":
                    try:
                        setattr(
                            strategy,
                            field,
                            StrategyType(value.value if hasattr(value, "value") else value),
                        )
                    except ValueError:
                        setattr(strategy, field, StrategyType.CUSTOM)
                elif field == "status":
                    with contextlib.suppress(ValueError):
                        setattr(
                            strategy,
                            field,
                            StrategyStatus(value.value if hasattr(value, "value") else value),
                        )
                elif field not in ("is_active", "config"):  # Skip legacy fields
                    setattr(strategy, field, value)

        # =========================================================================
        # VALIDATION: DCA strategy is uni-directional
        # =========================================================================
        if strategy.strategy_type == StrategyType.DCA:
            _raw = strategy.parameters
            params: dict[str, Any] = _raw if isinstance(_raw, dict) else {}
            direction = params.get("_direction", "both")
            if direction == "both":
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="Стратегия DCA работает только в одном направлении. Выберите 'long' или 'short'.",
                )

        strategy.updated_at = datetime.now(UTC)  # type: ignore[assignment]
        strategy.version += 1  # type: ignore[assignment]

        db.commit()
        db.refresh(strategy)

        logger.info(f"Updated strategy: {strategy.id}")
        return _strategy_to_response(strategy)

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating strategy: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update strategy: {e!s}",
        )


@router.delete("/{strategy_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: str,
    permanent: bool = Query(False, description="Permanently delete instead of soft delete"),
    db: Session = Depends(get_db),
):
    """
    Delete a strategy.

    - **permanent**: If True, permanently delete. Otherwise, soft delete (archive).
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()

    if not strategy:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with id '{strategy_id}' not found",
        )

    try:
        if permanent:
            db.delete(strategy)
            logger.info(f"Permanently deleted strategy: {strategy_id}")
        else:
            strategy.is_deleted = True  # type: ignore[assignment]
            strategy.deleted_at = datetime.now(UTC)  # type: ignore[assignment]
            strategy.status = StrategyStatus.ARCHIVED  # type: ignore[assignment]
            logger.info(f"Soft deleted strategy: {strategy_id}")

        db.commit()
        return None

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting strategy: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete strategy: {e!s}",
        )


@router.post(
    "/{strategy_id}/duplicate",
    response_model=StrategyResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def duplicate_strategy(
    strategy_id: str,
    new_name: str | None = Query(None, description="Name for the duplicated strategy"),
    db: Session = Depends(get_db),
):
    """
    Duplicate an existing strategy.

    Creates a copy of the strategy with a new ID and optional new name.
    """
    original = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.is_deleted.is_(False)).first()

    if not original:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with id '{strategy_id}' not found",
        )

    try:
        # Create duplicate
        duplicate = Strategy(
            id=str(uuid.uuid4()),
            name=new_name or f"{original.name} (Copy)",
            description=original.description,
            strategy_type=original.strategy_type,
            status=StrategyStatus.DRAFT,
            parameters=original.parameters.copy() if original.parameters else {},
            symbol=original.symbol,
            timeframe=original.timeframe,
            initial_capital=original.initial_capital,
            position_size=original.position_size,
            stop_loss_pct=original.stop_loss_pct,
            take_profit_pct=original.take_profit_pct,
            max_drawdown_pct=original.max_drawdown_pct,
            tags=original.tags.copy() if original.tags else [],
            user_id=original.user_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        db.add(duplicate)
        db.commit()
        db.refresh(duplicate)

        logger.info(f"Duplicated strategy {strategy_id} -> {duplicate.id}")
        return _strategy_to_response(duplicate)

    except Exception as e:
        db.rollback()
        logger.error(f"Error duplicating strategy: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to duplicate strategy: {e!s}",
        )


@router.post("/{strategy_id}/activate", response_model=StrategyResponse)
async def activate_strategy(
    strategy_id: str,
    db: Session = Depends(get_db),
):
    """
    Activate a strategy (set status to ACTIVE).
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.is_deleted.is_(False)).first()

    if not strategy:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with id '{strategy_id}' not found",
        )

    strategy.status = StrategyStatus.ACTIVE  # type: ignore[assignment]
    strategy.updated_at = datetime.now(UTC)  # type: ignore[assignment]

    db.commit()
    db.refresh(strategy)

    logger.info(f"Activated strategy: {strategy_id}")
    return _strategy_to_response(strategy)


@router.post("/{strategy_id}/pause", response_model=StrategyResponse)
async def pause_strategy(
    strategy_id: str,
    db: Session = Depends(get_db),
):
    """
    Pause a strategy (set status to PAUSED).
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.is_deleted.is_(False)).first()

    if not strategy:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with id '{strategy_id}' not found",
        )

    strategy.status = StrategyStatus.PAUSED  # type: ignore[assignment]
    strategy.updated_at = datetime.now(UTC)  # type: ignore[assignment]

    db.commit()
    db.refresh(strategy)

    logger.info(f"Paused strategy: {strategy_id}")
    return _strategy_to_response(strategy)
