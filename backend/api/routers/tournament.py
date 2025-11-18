"""
Tournament API Router

Quick Win #3: REST API endpoints for tournament management
Provides complete CRUD operations + live monitoring
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import json

from backend.services.tournament_orchestrator import (
    TournamentOrchestrator,
    StrategyEntry,
    TournamentConfig,
    TournamentResult,
    TournamentStatus
)
from backend.ml import StrategyOptimizer, MarketRegimeDetector
from pydantic import BaseModel, Field


# Request/Response Models
class StrategyEntryRequest(BaseModel):
    """Request model for strategy entry"""
    strategy_id: str
    strategy_name: str
    strategy_code: str
    initial_params: Dict[str, Any] = Field(default_factory=dict)
    param_space: Optional[Dict[str, Dict[str, Any]]] = None


class TournamentConfigRequest(BaseModel):
    """Request model for tournament configuration"""
    tournament_name: str
    enable_optimization: bool = True
    optimization_trials: int = 50
    optimization_timeout: Optional[float] = None
    max_workers: int = 5
    execution_timeout: int = 300
    detect_market_regime: bool = True
    regime_aware_scoring: bool = True
    scoring_weights: Optional[Dict[str, float]] = None
    enable_kb_logging: bool = True


class CreateTournamentRequest(BaseModel):
    """Request to create and start tournament"""
    config: TournamentConfigRequest
    strategies: List[StrategyEntryRequest]
    data: Dict[str, List[float]]  # OHLCV data as dict


class TournamentStatusResponse(BaseModel):
    """Response with tournament status"""
    tournament_id: str
    tournament_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration: float
    total_participants: int
    successful_backtests: int
    failed_backtests: int
    market_regime: Optional[str] = None
    optimization_time: float = 0.0
    execution_time: float = 0.0


class StrategyResultResponse(BaseModel):
    """Response with strategy result"""
    strategy_id: str
    strategy_name: str
    final_score: float
    rank: Optional[int] = None
    backtest_result: Optional[Dict[str, Any]] = None
    optimized_params: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0
    errors: List[str] = Field(default_factory=list)


class TournamentResultsResponse(BaseModel):
    """Complete tournament results"""
    status: TournamentStatusResponse
    winner: Optional[StrategyResultResponse] = None
    top_3: List[StrategyResultResponse] = Field(default_factory=list)
    all_participants: List[StrategyResultResponse] = Field(default_factory=list)


# Initialize router
router = APIRouter(prefix="/tournament", tags=["Tournament"])

# Global orchestrator (will be injected)
_orchestrator: Optional[TournamentOrchestrator] = None


def get_orchestrator() -> TournamentOrchestrator:
    """Get or create tournament orchestrator"""
    global _orchestrator
    
    if _orchestrator is None:
        # Initialize with default components
        _orchestrator = TournamentOrchestrator(
            optimizer=StrategyOptimizer(),
            regime_detector=MarketRegimeDetector()
            # sandbox, reasoning_storage, tournament_storage will be injected later
        )
    
    return _orchestrator


def set_orchestrator(orchestrator: TournamentOrchestrator):
    """Set custom orchestrator (for dependency injection)"""
    global _orchestrator
    _orchestrator = orchestrator


# Endpoints

@router.post("/create", response_model=TournamentStatusResponse)
async def create_tournament(
    request: CreateTournamentRequest,
    background_tasks: BackgroundTasks
) -> TournamentStatusResponse:
    """
    Create and start a new tournament
    
    **Process:**
    1. Validate strategies and configuration
    2. Start tournament in background
    3. Return tournament ID for status tracking
    
    **Args:**
    - config: Tournament configuration
    - strategies: List of strategies to compete
    - data: Historical market data (OHLCV)
    
    **Returns:**
    - Tournament status with ID for tracking
    """
    orchestrator = get_orchestrator()
    
    # Convert request models to internal models
    import pandas as pd
    
    strategies = [
        StrategyEntry(
            strategy_id=s.strategy_id,
            strategy_name=s.strategy_name,
            strategy_code=s.strategy_code,
            initial_params=s.initial_params,
            param_space=s.param_space
        )
        for s in request.strategies
    ]
    
    # Convert data dict to DataFrame
    df = pd.DataFrame(request.data)
    
    config = TournamentConfig(
        tournament_name=request.config.tournament_name,
        enable_optimization=request.config.enable_optimization,
        optimization_trials=request.config.optimization_trials,
        optimization_timeout=request.config.optimization_timeout,
        max_workers=request.config.max_workers,
        execution_timeout=request.config.execution_timeout,
        detect_market_regime=request.config.detect_market_regime,
        regime_aware_scoring=request.config.regime_aware_scoring,
        scoring_weights=request.config.scoring_weights or {},
        enable_kb_logging=request.config.enable_kb_logging
    )
    
    # Start tournament in background
    async def run_tournament_bg():
        try:
            await orchestrator.run_tournament(strategies, df, config)
        except Exception as e:
            # Log error but don't crash
            import logging
            logging.error(f"Tournament failed: {e}", exc_info=True)
    
    background_tasks.add_task(run_tournament_bg)
    
    # Return initial status
    tournament_id = f"tournament_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    return TournamentStatusResponse(
        tournament_id=tournament_id,
        tournament_name=config.tournament_name,
        status=TournamentStatus.PENDING.value,
        started_at=datetime.now(),
        total_duration=0.0,
        total_participants=len(strategies),
        successful_backtests=0,
        failed_backtests=0
    )


@router.get("/{tournament_id}/status", response_model=TournamentStatusResponse)
async def get_tournament_status(tournament_id: str) -> TournamentStatusResponse:
    """
    Get current tournament status
    
    **Args:**
    - tournament_id: Tournament ID from create endpoint
    
    **Returns:**
    - Current tournament status and progress
    
    **Status values:**
    - pending: Tournament created but not started
    - running: Tournament in progress
    - optimizing: Optimization phase
    - executing: Execution phase
    - completed: Tournament finished
    - failed: Tournament encountered error
    - cancelled: Tournament cancelled by user
    """
    orchestrator = get_orchestrator()
    result = orchestrator.get_tournament_status(tournament_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    
    return TournamentStatusResponse(
        tournament_id=result.tournament_id,
        tournament_name=result.tournament_name,
        status=result.status.value,
        started_at=result.started_at,
        completed_at=result.completed_at,
        total_duration=result.total_duration,
        total_participants=result.total_participants,
        successful_backtests=result.successful_backtests,
        failed_backtests=result.failed_backtests,
        market_regime=result.market_regime,
        optimization_time=result.optimization_time,
        execution_time=result.execution_time
    )


@router.get("/{tournament_id}/results", response_model=TournamentResultsResponse)
async def get_tournament_results(tournament_id: str) -> TournamentResultsResponse:
    """
    Get complete tournament results
    
    **Args:**
    - tournament_id: Tournament ID
    
    **Returns:**
    - Complete results including winner, rankings, and all participants
    
    **Note:**
    - Only available after tournament completion
    - Returns 404 if tournament not found
    - Returns 425 (Too Early) if tournament not completed
    """
    orchestrator = get_orchestrator()
    result = orchestrator.get_tournament_status(tournament_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    
    if result.status != TournamentStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Tournament not completed yet (status: {result.status.value})"
        )
    
    # Convert to response models
    def strategy_to_response(s: StrategyEntry) -> StrategyResultResponse:
        return StrategyResultResponse(
            strategy_id=s.strategy_id,
            strategy_name=s.strategy_name,
            final_score=s.final_score,
            rank=s.rank,
            backtest_result=s.backtest_result,
            optimized_params=s.optimized_params,
            execution_time=s.execution_time,
            errors=s.errors
        )
    
    status = TournamentStatusResponse(
        tournament_id=result.tournament_id,
        tournament_name=result.tournament_name,
        status=result.status.value,
        started_at=result.started_at,
        completed_at=result.completed_at,
        total_duration=result.total_duration,
        total_participants=result.total_participants,
        successful_backtests=result.successful_backtests,
        failed_backtests=result.failed_backtests,
        market_regime=result.market_regime,
        optimization_time=result.optimization_time,
        execution_time=result.execution_time
    )
    
    winner = strategy_to_response(result.winner) if result.winner else None
    top_3 = [strategy_to_response(s) for s in result.top_3]
    all_participants = [strategy_to_response(s) for s in result.participants]
    
    return TournamentResultsResponse(
        status=status,
        winner=winner,
        top_3=top_3,
        all_participants=all_participants
    )


@router.get("/{tournament_id}/live")
async def stream_tournament_progress(tournament_id: str):
    """
    Stream tournament progress in real-time (SSE)
    
    **Args:**
    - tournament_id: Tournament ID
    
    **Returns:**
    - Server-Sent Events (SSE) stream with progress updates
    
    **Event format:**
    ```json
    {
        "event": "status",
        "data": {
            "status": "running",
            "progress": 0.45,
            "message": "Optimizing strategy 3/10"
        }
    }
    ```
    """
    orchestrator = get_orchestrator()
    
    async def event_generator():
        """Generate SSE events"""
        last_status = None
        
        while True:
            result = orchestrator.get_tournament_status(tournament_id)
            
            if not result:
                yield f"data: {json.dumps({'error': 'Tournament not found'})}\n\n"
                break
            
            # Only send update if status changed
            current_status = result.status.value
            if current_status != last_status:
                event = {
                    "event": "status",
                    "data": {
                        "tournament_id": tournament_id,
                        "status": current_status,
                        "progress": result.successful_backtests / result.total_participants if result.total_participants > 0 else 0,
                        "successful": result.successful_backtests,
                        "total": result.total_participants,
                        "duration": result.total_duration
                    }
                }
                yield f"data: {json.dumps(event)}\n\n"
                last_status = current_status
            
            # Stop if completed or failed
            if result.status in [TournamentStatus.COMPLETED, TournamentStatus.FAILED, TournamentStatus.CANCELLED]:
                break
            
            await asyncio.sleep(1)  # Update every second
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/{tournament_id}/cancel")
async def cancel_tournament(tournament_id: str) -> Dict[str, str]:
    """
    Cancel running tournament
    
    **Args:**
    - tournament_id: Tournament ID
    
    **Returns:**
    - Success message
    
    **Note:**
    - Can only cancel running tournaments
    - Completed tournaments cannot be cancelled
    """
    orchestrator = get_orchestrator()
    
    success = await orchestrator.cancel_tournament(tournament_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Tournament {tournament_id} not found or already completed"
        )
    
    return {"message": f"Tournament {tournament_id} cancelled successfully"}


@router.get("/history", response_model=List[TournamentStatusResponse])
async def get_tournament_history(
    limit: int = Query(default=10, ge=1, le=100),
    status: Optional[str] = Query(default=None)
) -> List[TournamentStatusResponse]:
    """
    Get tournament history
    
    **Args:**
    - limit: Maximum number of tournaments to return (1-100)
    - status: Filter by status (optional)
    
    **Returns:**
    - List of past tournaments ordered by start time (newest first)
    """
    # TODO: Implement with tournament_storage
    # For now, return empty list
    return []


@router.get("/leaderboard", response_model=Dict[str, Any])
async def get_strategy_leaderboard(
    limit: int = Query(default=10, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get strategy leaderboard across all tournaments
    
    **Args:**
    - limit: Maximum number of strategies to return
    
    **Returns:**
    - Leaderboard with strategy rankings and statistics
    
    **Metrics:**
    - Total tournaments participated
    - Total wins
    - Win rate
    - Average score
    - Best score
    """
    # TODO: Implement with tournament_storage
    # For now, return placeholder
    return {
        "leaderboard": [],
        "total_strategies": 0,
        "total_tournaments": 0
    }


# Health check
@router.get("/health")
async def tournament_health() -> Dict[str, Any]:
    """
    Tournament system health check
    
    **Returns:**
    - System status and component availability
    """
    orchestrator = get_orchestrator()
    
    return {
        "status": "healthy",
        "components": {
            "orchestrator": orchestrator is not None,
            "optimizer": orchestrator.optimizer is not None if orchestrator else False,
            "regime_detector": orchestrator.regime_detector is not None if orchestrator else False,
            "sandbox": orchestrator.sandbox is not None if orchestrator else False
        },
        "timestamp": datetime.now().isoformat()
    }
