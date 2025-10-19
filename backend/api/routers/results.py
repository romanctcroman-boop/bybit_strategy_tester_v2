"""
API Router for Backtest Results Management

Endpoints for viewing backtest history and results from PostgreSQL.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import (
    Backtest,
    BacktestStatus,
    Trade,
    get_async_session,
    get_backtest,
    get_backtests,
    get_recent_backtests,
    get_results_summary,
    get_trades,
)

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/recent", response_model=List[dict])
async def get_recent_backtest_results(
    limit: int = Query(20, ge=1, le=100, description="Number of recent results to return"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get recent backtest results
    
    Args:
        limit: Number of results to return
    
    Returns:
        List of recent backtest results with strategy info
    """
    try:
        results = await get_recent_backtests(session, limit=limit)
        logger.info(f"📊 Retrieved {len(results)} recent backtests")
        return results
    except Exception as e:
        logger.error(f"❌ Failed to get recent backtests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent backtests: {str(e)}")


@router.get("/backtests", response_model=List[Backtest])
async def list_backtests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    status: Optional[BacktestStatus] = Query(None, description="Filter by status"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get list of backtests with filtering
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        strategy_id: Filter by strategy ID
        status: Filter by backtest status
    
    Returns:
        List of backtests
    """
    try:
        backtests = await get_backtests(
            session,
            skip=skip,
            limit=limit,
            strategy_id=strategy_id,
            status=status,
        )
        logger.info(f"📊 Retrieved {len(backtests)} backtests")
        return backtests
    except Exception as e:
        logger.error(f"❌ Failed to get backtests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get backtests: {str(e)}")


@router.get("/backtests/{backtest_id}", response_model=Backtest)
async def get_backtest_by_id(
    backtest_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get backtest by ID
    
    Args:
        backtest_id: Backtest ID
    
    Returns:
        Backtest details with results
    """
    try:
        backtest = await get_backtest(session, backtest_id)
        if not backtest:
            raise HTTPException(status_code=404, detail=f"Backtest {backtest_id} not found")
        
        logger.info(f"📋 Retrieved backtest: {backtest_id}")
        return backtest
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get backtest: {str(e)}")


@router.get("/backtests/{backtest_id}/trades", response_model=List[Trade])
async def get_backtest_trades(
    backtest_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get all trades for a backtest
    
    Args:
        backtest_id: Backtest ID
        skip: Number of trades to skip
        limit: Maximum number of trades to return
    
    Returns:
        List of trades
    """
    try:
        # Check if backtest exists
        backtest = await get_backtest(session, backtest_id)
        if not backtest:
            raise HTTPException(status_code=404, detail=f"Backtest {backtest_id} not found")
        
        trades = await get_trades(session, backtest_id, skip=skip, limit=limit)
        logger.info(f"📊 Retrieved {len(trades)} trades for backtest {backtest_id}")
        return trades
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get trades for backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get trades: {str(e)}")


@router.get("/summary", response_model=dict)
async def get_results_summary_endpoint(
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get summary statistics of all backtest results
    
    Returns:
        Summary statistics (total backtests, avg return, best strategy, etc.)
    """
    try:
        summary = await get_results_summary(session)
        logger.info("📊 Retrieved results summary")
        return summary
    except Exception as e:
        logger.error(f"❌ Failed to get results summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")
