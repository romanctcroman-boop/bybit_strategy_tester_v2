"""
API Router for Strategy Management

Endpoints for CRUD operations on strategies stored in PostgreSQL.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import (
    Strategy,
    StrategyCreate,
    StrategyUpdate,
    create_strategy,
    delete_strategy,
    get_async_session,
    get_strategies,
    get_strategy,
    get_strategy_performance,
    get_top_strategies,
    update_strategy,
)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.post("/", response_model=Strategy, status_code=201)
async def create_new_strategy(
    strategy: StrategyCreate,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a new strategy
    
    Args:
        strategy: Strategy data (name, type, config, etc.)
    
    Returns:
        Created strategy with ID
    """
    try:
        result = await create_strategy(session, strategy)
        logger.info(f"✅ Strategy created: {result.id} - {result.name}")
        return result
    except Exception as e:
        logger.error(f"❌ Failed to create strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create strategy: {str(e)}")


@router.get("/", response_model=List[Strategy])
async def list_strategies(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get list of all strategies
    
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        is_active: Filter by active status
    
    Returns:
        List of strategies
    """
    try:
        strategies = await get_strategies(
            session,
            skip=skip,
            limit=limit,
            is_active=is_active,
        )
        logger.info(f"📊 Retrieved {len(strategies)} strategies")
        return strategies
    except Exception as e:
        logger.error(f"❌ Failed to get strategies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get strategies: {str(e)}")


@router.get("/top", response_model=List[dict])
async def get_top_performing_strategies(
    limit: int = Query(10, ge=1, le=50, description="Number of top strategies to return"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get top performing strategies based on average return
    
    Args:
        limit: Number of top strategies to return
    
    Returns:
        List of strategies with performance metrics
    """
    try:
        top = await get_top_strategies(session, limit=limit)
        logger.info(f"🏆 Retrieved top {len(top)} strategies")
        return top
    except Exception as e:
        logger.error(f"❌ Failed to get top strategies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get top strategies: {str(e)}")


@router.get("/{strategy_id}", response_model=Strategy)
async def get_strategy_by_id(
    strategy_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get strategy by ID
    
    Args:
        strategy_id: Strategy ID
    
    Returns:
        Strategy details
    """
    try:
        strategy = await get_strategy(session, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        logger.info(f"📋 Retrieved strategy: {strategy_id} - {strategy.name}")
        return strategy
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get strategy {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get strategy: {str(e)}")


@router.get("/{strategy_id}/performance", response_model=dict)
async def get_strategy_performance_metrics(
    strategy_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get performance statistics for a strategy
    
    Args:
        strategy_id: Strategy ID
    
    Returns:
        Performance metrics (avg return, sharpe, win rate, etc.)
    """
    try:
        # Check if strategy exists
        strategy = await get_strategy(session, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        performance = await get_strategy_performance(session, strategy_id)
        logger.info(f"📊 Retrieved performance for strategy: {strategy_id}")
        return performance
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get performance for strategy {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance: {str(e)}")


@router.put("/{strategy_id}", response_model=Strategy)
async def update_existing_strategy(
    strategy_id: int,
    strategy: StrategyUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update strategy
    
    Args:
        strategy_id: Strategy ID
        strategy: Updated strategy data
    
    Returns:
        Updated strategy
    """
    try:
        result = await update_strategy(session, strategy_id, strategy)
        if not result:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        logger.info(f"✅ Strategy updated: {strategy_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update strategy {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update strategy: {str(e)}")


@router.delete("/{strategy_id}", status_code=204)
async def delete_existing_strategy(
    strategy_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Delete strategy
    
    Args:
        strategy_id: Strategy ID
    """
    try:
        success = await delete_strategy(session, strategy_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        logger.info(f"🗑️  Strategy deleted: {strategy_id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete strategy {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete strategy: {str(e)}")
