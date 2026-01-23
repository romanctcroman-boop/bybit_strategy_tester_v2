"""
Bybit Strategy Tester V2 - Reasoning API Router
===============================================
Purpose: REST API endpoints for reasoning traces and Knowledge Base
Endpoints:
    GET /reasoning/trace/{id} - Get reasoning trace by ID
    GET /reasoning/session/{session_id} - Get all traces for session
    GET /reasoning/search - Search reasoning traces
    GET /reasoning/strategy/{strategy_id}/evolution - Get strategy evolution
    GET /reasoning/stats/tokens - Get token usage statistics
    GET /reasoning/stats/agents - Get agent performance statistics
Author: Multi-Agent System (DeepSeek + Perplexity AI)
Created: 2025-11-01
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Agents & monitoring
from backend.agents.models import AgentType
from backend.agents.reasoning_ab_harness import ABTestConfig, ReasoningABHarness
from backend.database.session import get_db
from backend.monitoring import SelfLearningSignalPublisher
from backend.services.reasoning_storage import ReasoningStorageService

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/reasoning",
    tags=["reasoning", "knowledge-base"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    },
)


# ==============================================================================
# RESPONSE MODELS
# ==============================================================================


class ChainOfThoughtResponse(BaseModel):
    """Response model for chain-of-thought step"""

    id: str
    step_number: int
    thought_type: str
    content: str
    intermediate_conclusion: Optional[str]
    confidence_score: Optional[float]
    citations: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReasoningTraceResponse(BaseModel):
    """Response model for reasoning trace"""

    id: str
    session_id: str
    request_id: Optional[str]
    agent_type: str
    agent_model: Optional[str]
    task_type: str
    input_prompt: str
    reasoning_chain: Optional[dict]
    final_conclusion: Optional[str]
    tokens_used: Optional[int]
    processing_time: Optional[float]
    confidence_score: Optional[float]
    status: str
    created_at: datetime
    chain_of_thought_steps: Optional[List[ChainOfThoughtResponse]] = None

    model_config = {"from_attributes": True}


class StrategyEvolutionResponse(BaseModel):
    """Response model for strategy evolution"""

    id: str
    strategy_id: str
    strategy_name: str
    version: int
    changes_description: str
    performance_metrics: Optional[dict]
    performance_delta: Optional[dict]
    hypothesis: Optional[str]
    outcome: Optional[str]
    is_active: bool
    is_production: bool
    created_at: datetime
    activated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TokenUsageStatsResponse(BaseModel):
    """Response model for token usage statistics"""

    total_requests: int
    total_tokens: int
    avg_tokens: float
    total_cost: float
    avg_cost: float


class AgentPerformanceStatsResponse(BaseModel):
    """Response model for agent performance statistics"""

    total_requests: int
    successful_requests: int
    success_rate: float
    avg_processing_time: float
    avg_confidence: float


class ABTestAgentResponse(BaseModel):
    agent: str
    latency_ms: float
    quality_score: float
    success: bool
    content_preview: str


class ABTestResponse(BaseModel):
    prompt_id: str
    winner: str
    confidence: float
    judge_explanation: str
    baseline: ABTestAgentResponse
    challenger: ABTestAgentResponse
    metadata: dict


class ABTestRequest(BaseModel):
    prompt: str = Field(..., description="User prompt or tournament trace")
    baseline_agent: AgentType = Field(default=AgentType.DEEPSEEK)
    challenger_agent: AgentType = Field(default=AgentType.PERPLEXITY)
    task_type: str = Field(default="analyze")
    code: Optional[str] = Field(default=None)
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ==============================================================================
# ENDPOINTS
# ==============================================================================


@router.get(
    "/trace/{trace_id}",
    response_model=ReasoningTraceResponse,
    summary="Get reasoning trace by ID",
    description="Retrieve a specific reasoning trace with optional chain-of-thought steps",
)
async def get_reasoning_trace(
    trace_id: uuid.UUID,
    include_steps: bool = Query(True, description="Include chain-of-thought steps"),
    db: Session = Depends(get_db),
) -> ReasoningTraceResponse:
    """
    Get reasoning trace by ID.

    Example:
        GET /reasoning/trace/123e4567-e89b-12d3-a456-426614174000?include_steps=true
    """
    service = ReasoningStorageService(db)

    try:
        trace = await service.get_reasoning_trace(trace_id)

        if not trace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reasoning trace {trace_id} not found",
            )

        if include_steps:
            # Eager load chain-of-thought steps
            _ = trace.chain_of_thought_steps

        return ReasoningTraceResponse.from_orm(trace)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get reasoning trace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/session/{session_id}",
    response_model=List[ReasoningTraceResponse],
    summary="Get all reasoning traces for a session",
    description="Retrieve all reasoning traces for a given session ID",
)
async def get_reasoning_chain(
    session_id: str,
    include_steps: bool = Query(False, description="Include chain-of-thought steps"),
    db: Session = Depends(get_db),
) -> List[ReasoningTraceResponse]:
    """
    Get all reasoning traces for a session.

    Example:
        GET /reasoning/session/sess_123?include_steps=true
    """
    service = ReasoningStorageService(db)

    try:
        traces = await service.get_reasoning_chain(
            session_id, include_steps=include_steps
        )

        if not traces:
            return []

        return [ReasoningTraceResponse.from_orm(t) for t in traces]

    except Exception as e:
        logger.error(f"Failed to get reasoning chain: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/search",
    response_model=List[ReasoningTraceResponse],
    summary="Search reasoning traces",
    description="Search reasoning traces by various criteria",
)
async def search_reasoning_traces(
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
) -> List[ReasoningTraceResponse]:
    """
    Search reasoning traces.

    Example:
        GET /reasoning/search?task_type=code-generation&agent_type=deepseek&limit=50
    """
    service = ReasoningStorageService(db)

    try:
        if task_type:
            traces = await service.search_by_task_type(
                task_type, limit=limit, offset=offset
            )
        elif agent_type:
            traces = await service.search_by_agent(
                agent_type, limit=limit, offset=offset
            )
        elif start_date:
            traces = await service.search_by_date_range(
                start_date, end_date, limit=limit
            )
        elif status and status != "completed":
            traces = await service.search_failed_traces(limit=limit)
        else:
            # Default: recent traces
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=7)
            traces = await service.search_by_date_range(start, end, limit=limit)

        return [ReasoningTraceResponse.from_orm(t) for t in traces]

    except Exception as e:
        logger.error(f"Failed to search reasoning traces: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/strategy/{strategy_id}/evolution",
    response_model=List[StrategyEvolutionResponse],
    summary="Get strategy evolution history",
    description="Retrieve evolution history for a trading strategy",
)
async def get_strategy_evolution(
    strategy_id: str,
    include_inactive: bool = Query(False, description="Include inactive versions"),
    db: Session = Depends(get_db),
) -> List[StrategyEvolutionResponse]:
    """
    Get strategy evolution history.

    Example:
        GET /reasoning/strategy/ema_crossover/evolution?include_inactive=false
    """
    service = ReasoningStorageService(db)

    try:
        evolutions = await service.get_strategy_evolution(
            strategy_id, include_inactive=include_inactive
        )

        if not evolutions:
            return []

        return [StrategyEvolutionResponse.from_orm(e) for e in evolutions]

    except Exception as e:
        logger.error(f"Failed to get strategy evolution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/stats/tokens",
    response_model=TokenUsageStatsResponse,
    summary="Get token usage statistics",
    description="Get aggregated token usage and cost statistics",
)
async def get_token_usage_stats(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    db: Session = Depends(get_db),
) -> TokenUsageStatsResponse:
    """
    Get token usage statistics.

    Example:
        GET /reasoning/stats/tokens?agent_type=deepseek&start_date=2025-11-01T00:00:00
    """
    service = ReasoningStorageService(db)

    try:
        stats = await service.get_token_usage_stats(
            start_date=start_date, end_date=end_date, agent_type=agent_type
        )

        return TokenUsageStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get token usage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/stats/agents",
    response_model=AgentPerformanceStatsResponse,
    summary="Get agent performance statistics",
    description="Get aggregated agent performance metrics",
)
async def get_agent_performance_stats(
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    db: Session = Depends(get_db),
) -> AgentPerformanceStatsResponse:
    """
    Get agent performance statistics.

    Example:
        GET /reasoning/stats/agents?agent_type=perplexity
    """
    service = ReasoningStorageService(db)

    try:
        stats = await service.get_agent_performance_stats(agent_type=agent_type)

        return AgentPerformanceStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get agent performance stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/ab-test",
    response_model=ABTestResponse,
    summary="Run reasoning agent A/B duel",
    description="Execute baseline vs challenger agents on the same prompt and record telemetry",
)
async def run_reasoning_ab_test(
    request: ABTestRequest, db: Session = Depends(get_db)
) -> ABTestResponse:
    service = ReasoningStorageService(db)
    publisher = SelfLearningSignalPublisher(namespace="self_learning:reasoning_ab")
    harness = ReasoningABHarness(
        reasoning_storage=service,
        self_learning_publisher=publisher,
    )

    config = ABTestConfig(
        baseline_agent=request.baseline_agent,
        challenger_agent=request.challenger_agent,
        task_type=request.task_type,
        context=request.context,
        metadata=request.metadata,
    )

    try:
        result = await harness.run_test(
            prompt=request.prompt,
            code=request.code,
            context=request.context,
            config=config,
        )

        def serialize_trial(trial):
            content = trial.response.content or ""
            return ABTestAgentResponse(
                agent=trial.agent.value,
                latency_ms=trial.latency_ms,
                quality_score=trial.quality_score,
                success=trial.response.success,
                content_preview=content[:400],
            )

        return ABTestResponse(
            prompt_id=result.prompt_id,
            winner=result.winner,
            confidence=result.confidence,
            judge_explanation=result.judge_explanation,
            baseline=serialize_trial(result.baseline),
            challenger=serialize_trial(result.challenger),
            metadata=result.metadata,
        )
    except Exception as e:
        logger.error(f"Failed to run reasoning A/B harness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/chain-of-thought/{trace_id}",
    response_model=List[ChainOfThoughtResponse],
    summary="Get chain-of-thought steps",
    description="Get detailed chain-of-thought steps for a reasoning trace",
)
async def get_chain_of_thought(
    trace_id: uuid.UUID, db: Session = Depends(get_db)
) -> List[ChainOfThoughtResponse]:
    """
    Get chain-of-thought steps.

    Example:
        GET /reasoning/chain-of-thought/123e4567-e89b-12d3-a456-426614174000
    """
    service = ReasoningStorageService(db)

    try:
        steps = await service.get_chain_of_thought(trace_id)

        if not steps:
            return []

        return [ChainOfThoughtResponse.from_orm(s) for s in steps]

    except Exception as e:
        logger.error(f"Failed to get chain-of-thought: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# ==============================================================================
# HEALTH CHECK
# ==============================================================================


@router.get(
    "/health",
    summary="Knowledge Base health check",
    description="Check if Knowledge Base is operational",
)
async def health_check(db: Session = Depends(get_db)) -> dict:
    """
    Health check endpoint.

    Example:
        GET /reasoning/health
    """
    try:
        # Simple query to check DB connectivity
        service = ReasoningStorageService(db)
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=1)
        traces = await service.search_by_date_range(start, end, limit=1)

        return {
            "status": "healthy",
            "database": "connected",
            "recent_traces": len(traces),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
