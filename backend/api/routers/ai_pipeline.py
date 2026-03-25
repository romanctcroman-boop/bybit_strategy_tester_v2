"""
AI Strategy Pipeline API Router.

Endpoints for the new LLM-powered strategy generation pipeline:
- POST /generate — Generate strategy with AI agents
- POST /generate-and-backtest — Generate + backtest in one call
- POST /analyze-market — Analyze market context
- POST /improve-strategy — Improve existing strategy with walk-forward
- GET /agents — List available LLM agents
- GET /pipeline/{pipeline_id}/status — Pipeline job status
- GET /pipeline/{pipeline_id}/result — Pipeline job result
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel, Field

from backend.services.distributed_lock import get_distributed_lock

# In-memory pipeline job store (lightweight — no DB needed)
# Eviction: max 200 entries, stale jobs removed after 1 hour.
_pipeline_jobs: dict[str, dict[str, Any]] = {}
_PIPELINE_JOBS_MAX = 200
_PIPELINE_JOB_TTL_SECONDS = 3600  # 1 hour

# P2-4: per-pipeline event queues for WebSocket streaming
# Populated by POST /generate-stream; consumed by WS /stream/{pipeline_id}
_pipeline_queues: dict[str, asyncio.Queue] = {}


def _evict_stale_jobs() -> None:
    """Remove jobs older than TTL and enforce max size.

    Also cleans up any orphaned WebSocket queues whose job has been evicted
    (e.g. /generate-stream was called but no WS client ever connected).
    """
    now = datetime.now(UTC)
    stale_ids = []
    for jid, job in _pipeline_jobs.items():
        created_raw = job.get("created_at")
        if created_raw is None:
            continue
        try:
            created = datetime.fromisoformat(str(created_raw))
            if (now - created).total_seconds() > _PIPELINE_JOB_TTL_SECONDS:
                stale_ids.append(jid)
        except (ValueError, TypeError):
            stale_ids.append(jid)  # malformed — evict
    for jid in stale_ids:
        _pipeline_jobs.pop(jid, None)
        _pipeline_queues.pop(jid, None)  # clean up orphaned WS queue if any

    # If still over limit, remove oldest first
    if len(_pipeline_jobs) > _PIPELINE_JOBS_MAX:
        sorted_ids = sorted(
            _pipeline_jobs,
            key=lambda k: _pipeline_jobs[k].get("created_at", "0"),
        )
        for jid in sorted_ids[: len(_pipeline_jobs) - _PIPELINE_JOBS_MAX]:
            _pipeline_jobs.pop(jid, None)
            _pipeline_queues.pop(jid, None)  # clean up orphaned WS queue if any


router = APIRouter(
    prefix="/ai-pipeline",
    tags=["AI Strategy Pipeline"],
    responses={
        400: {"description": "Invalid parameters"},
        404: {"description": "Pipeline job not found"},
        500: {"description": "Internal server error"},
    },
)


# =============================================================================
# REQUEST / RESPONSE MODELS
# =============================================================================


class GenerateRequest(BaseModel):
    """Request to generate a trading strategy via AI pipeline."""

    symbol: str = Field("BTCUSDT", description="Trading pair")
    timeframe: str = Field("15", description="Candle interval (1, 5, 15, 30, 60, 240, D, W, M)")
    agents: list[str] = Field(
        default_factory=lambda: ["deepseek"],
        description="LLM agents to query: deepseek, qwen, perplexity",
    )
    run_backtest: bool = Field(False, description="Run backtest on generated strategy")
    enable_walk_forward: bool = Field(False, description="Run walk-forward validation after backtest")
    initial_capital: float = Field(10000, ge=100, le=100_000_000, description="Starting capital")
    leverage: int = Field(1, ge=1, le=125, description="Trading leverage")
    start_date: str = Field("2025-01-01", description="Data start date (YYYY-MM-DD)")
    end_date: str = Field("2025-06-01", description="Data end date (YYYY-MM-DD)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "agents": ["deepseek", "qwen"],
                "run_backtest": True,
                "enable_walk_forward": False,
                "initial_capital": 10000,
                "leverage": 10,
                "start_date": "2025-01-01",
                "end_date": "2025-03-01",
            }
        }
    }


class StrategyResponse(BaseModel):
    """Generated strategy response."""

    strategy_name: str
    strategy_type: str
    strategy_params: dict[str, Any]
    description: str = ""
    signals_count: int = 0
    quality_score: float = 0.0
    agent: str = ""


class PipelineResponse(BaseModel):
    """Full pipeline execution response."""

    success: bool
    pipeline_id: str = ""
    strategy: StrategyResponse | None = None
    backtest_metrics: dict[str, Any] = Field(default_factory=dict)
    walk_forward: dict[str, Any] = Field(default_factory=dict)
    proposals_count: int = 0
    consensus_summary: str = ""
    stages: list[dict[str, Any]] = Field(default_factory=list)
    total_duration_ms: float = 0.0
    timestamp: str = ""


class AgentInfo(BaseModel):
    """Information about an available LLM agent."""

    name: str
    provider: str
    specialization: str
    available: bool = False


class AnalyzeMarketRequest(BaseModel):
    """Request to analyze market context."""

    symbol: str = Field("BTCUSDT", description="Trading pair")
    timeframe: str = Field("15", description="Candle interval")
    start_date: str = Field("2025-01-01", description="Data start date (YYYY-MM-DD)")
    end_date: str = Field("2025-06-01", description="Data end date (YYYY-MM-DD)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "start_date": "2025-01-01",
                "end_date": "2025-03-01",
            }
        }
    }


class MarketAnalysisResponse(BaseModel):
    """Market analysis result."""

    symbol: str
    timeframe: str
    market_regime: str = ""
    trend_direction: str = ""
    volatility_level: str = ""
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)
    recommended_strategies: list[str] = Field(default_factory=list)
    context_summary: str = ""
    candles_analyzed: int = 0


class ImproveStrategyRequest(BaseModel):
    """Request to improve an existing strategy via walk-forward."""

    symbol: str = Field("BTCUSDT", description="Trading pair")
    timeframe: str = Field("15", description="Candle interval")
    strategy_type: str = Field(..., description="Engine strategy type (rsi, macd, ema_crossover, etc.)")
    strategy_params: dict[str, Any] = Field(default_factory=dict, description="Current strategy parameters")
    start_date: str = Field("2025-01-01", description="Data start date (YYYY-MM-DD)")
    end_date: str = Field("2025-06-01", description="Data end date (YYYY-MM-DD)")
    initial_capital: float = Field(10000, ge=100, description="Starting capital")
    direction: str = Field("both", description="Trade direction: long, short, both")
    wf_splits: int = Field(5, ge=2, le=20, description="Walk-forward splits")
    wf_train_ratio: float = Field(0.7, ge=0.5, le=0.9, description="Train/test ratio")
    optimization_metric: str = Field("sharpe", description="Metric to optimize")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "strategy_type": "rsi",
                "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
                "initial_capital": 10000,
                "wf_splits": 5,
                "optimization_metric": "sharpe",
            }
        }
    }


class ImproveStrategyResponse(BaseModel):
    """Strategy improvement result."""

    success: bool
    original_params: dict[str, Any] = Field(default_factory=dict)
    recommended_params: dict[str, Any] = Field(default_factory=dict)
    confidence_level: str = ""
    overfit_score: float = 0.0
    consistency_ratio: float = 0.0
    parameter_stability: float = 0.0
    walk_forward_details: dict[str, Any] = Field(default_factory=dict)


class PipelineStatusResponse(BaseModel):
    """Pipeline job status."""

    pipeline_id: str
    status: str  # queued, running, completed, failed
    progress_pct: float = 0.0
    current_stage: str = ""
    created_at: str = ""
    completed_at: str | None = None


class PipelineResultResponse(BaseModel):
    """Pipeline job result (when completed)."""

    pipeline_id: str
    status: str
    result: PipelineResponse | None = None
    error: str | None = None


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/generate", response_model=PipelineResponse)
async def generate_strategy(request: GenerateRequest) -> PipelineResponse:
    """
    Generate a trading strategy using AI agents.

    Runs the full pipeline:
    1. Analyze market context from OHLCV data
    2. Generate strategy proposals from LLM agents
    3. Parse and validate responses
    4. Select best strategy (consensus if multiple agents)
    5. Optionally backtest the result
    6. Optionally run walk-forward validation

    **Agents**: deepseek (quantitative), qwen (technical), perplexity (market research)
    """
    try:
        # Distributed lock: prevent duplicate pipeline runs for same symbol/timeframe
        lock = get_distributed_lock()
        lock_key = f"pipeline:{request.symbol}:{request.timeframe}"

        try:
            async with lock.acquire(lock_key, ttl=600, max_retries=3):
                return await _execute_pipeline(request)
        except TimeoutError:
            raise HTTPException(
                status_code=429,
                detail=f"Pipeline for {request.symbol}/{request.timeframe} is already running. Try again later.",
            )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error in generate: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")


async def _execute_pipeline(request: GenerateRequest) -> PipelineResponse:
    """Execute the pipeline (called under distributed lock)."""
    from backend.agents.strategy_controller import StrategyController

    # Load OHLCV data
    df = await _load_ohlcv_data(
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    # Create pipeline job (evict stale entries first)
    _evict_stale_jobs()
    pipeline_id = str(uuid.uuid4())[:12]
    _pipeline_jobs[pipeline_id] = {
        "status": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "current_stage": "context_analysis",
    }

    controller = StrategyController()
    result = await controller.generate_strategy(
        symbol=request.symbol,
        timeframe=request.timeframe,
        df=df,
        agents=request.agents,
        run_backtest=request.run_backtest,
        enable_walk_forward=request.enable_walk_forward,
        backtest_config={
            "initial_capital": request.initial_capital,
            "leverage": request.leverage,
        },
    )

    # Build response
    strategy_resp = None
    if result.strategy:
        strategy_resp = StrategyResponse(
            strategy_name=result.strategy.strategy_name,
            strategy_type=result.strategy.get_strategy_type_for_engine(),
            strategy_params=result.strategy.get_engine_params(),
            description=result.strategy.description,
            signals_count=len(result.strategy.signals),
            quality_score=result.validation.quality_score if result.validation else 0,
            agent=result.strategy.agent_metadata.agent_name if result.strategy.agent_metadata else "",
        )

    pipeline_response = PipelineResponse(
        success=result.success,
        pipeline_id=pipeline_id,
        strategy=strategy_resp,
        backtest_metrics=result.backtest_metrics,
        walk_forward=result.walk_forward,
        proposals_count=len(result.proposals),
        consensus_summary=result.consensus_summary,
        stages=[
            {
                "stage": s.stage.value,
                "success": s.success,
                "duration_ms": round(s.duration_ms, 1),
                "error": s.error,
            }
            for s in result.stages
        ],
        total_duration_ms=round(result.total_duration_ms, 1),
        timestamp=result.timestamp.isoformat(),
    )

    # Store result for later retrieval
    _pipeline_jobs[pipeline_id] = {
        "status": "completed" if result.success else "failed",
        "created_at": _pipeline_jobs[pipeline_id]["created_at"],
        "completed_at": datetime.now(UTC).isoformat(),
        "current_stage": result.final_stage.value,
        "result": pipeline_response.model_dump(),
    }

    return pipeline_response


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents() -> list[AgentInfo]:
    """
    List available LLM agents for strategy generation.

    Each agent has a different specialization:
    - **deepseek**: Quantitative analyst, conservative approach
    - **qwen**: Technical analyst, moderate risk
    - **perplexity**: Market researcher with web search
    """
    agents = [
        AgentInfo(
            name="deepseek",
            provider="DeepSeek",
            specialization="Quantitative analysis, conservative strategies",
            available=_check_agent_available("deepseek"),
        ),
        AgentInfo(
            name="qwen",
            provider="Alibaba Qwen",
            specialization="Technical analysis, moderate risk",
            available=_check_agent_available("qwen"),
        ),
        AgentInfo(
            name="perplexity",
            provider="Perplexity AI",
            specialization="Market research with real-time web search",
            available=_check_agent_available("perplexity"),
        ),
    ]
    return agents


@router.post("/analyze-market", response_model=MarketAnalysisResponse)
async def analyze_market(request: AnalyzeMarketRequest) -> MarketAnalysisResponse:
    """
    Analyze market context for a symbol and timeframe.

    Returns market regime, trend direction, volatility, key levels,
    and recommended strategy types. Useful for understanding market
    conditions before generating a strategy.
    """
    try:
        from backend.agents.prompts.context_builder import MarketContextBuilder

        df = await _load_ohlcv_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        builder = MarketContextBuilder()
        context = builder.build_context(request.symbol, request.timeframe, df)

        # Derive volatility level from real ATR% field
        if context.atr_pct >= 3.0:
            volatility = "high"
        elif context.atr_pct >= 1.0:
            volatility = "medium"
        else:
            volatility = "low"

        # Derive strategy recommendations from market regime
        regime_strategies: dict[str, list[str]] = {
            "trending_up": ["ema_crossover", "macd", "supertrend"],
            "trending_down": ["ema_crossover", "macd", "supertrend"],
            "ranging": ["rsi", "bollinger", "stochastic"],
            "volatile": ["bollinger", "rsi", "stochastic"],
        }
        recommended = regime_strategies.get(context.market_regime, ["rsi", "macd"])

        return MarketAnalysisResponse(
            symbol=request.symbol,
            timeframe=request.timeframe,
            market_regime=context.market_regime,
            trend_direction=context.trend_direction,
            volatility_level=volatility,
            support_levels=context.support_levels,
            resistance_levels=context.resistance_levels,
            recommended_strategies=recommended,
            context_summary=context.indicators_summary or str(context),
            candles_analyzed=len(df),
        )

    except ValueError as e:
        logger.warning(f"Market analysis error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Market analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.post("/improve-strategy", response_model=ImproveStrategyResponse)
async def improve_strategy(request: ImproveStrategyRequest) -> ImproveStrategyResponse:
    """
    Improve an existing strategy using walk-forward optimization.

    Takes current strategy parameters and runs walk-forward validation
    to find robust parameter combinations. Returns recommended parameters,
    overfitting assessment, and confidence level.
    """
    try:
        from backend.agents.integration.walk_forward_bridge import WalkForwardBridge
        from backend.agents.prompts.response_parser import (
            OptimizationHints,
            Signal,
            StrategyDefinition,
        )

        # Load OHLCV data
        df = await _load_ohlcv_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        # Build a StrategyDefinition from the request params
        strategy = StrategyDefinition(
            strategy_name=f"Optimizing {request.strategy_type}",
            description="Strategy created for walk-forward optimization",
            signals=[
                Signal(
                    id="opt_signal_1",
                    type=request.strategy_type,
                    params=request.strategy_params,
                    weight=1.0,
                )
            ],
            optimization_hints=OptimizationHints(
                parameters_to_optimize=list(request.strategy_params.keys()),
                primary_objective=request.optimization_metric,
            ),
        )

        # Run walk-forward
        bridge = WalkForwardBridge(
            n_splits=request.wf_splits,
            train_ratio=request.wf_train_ratio,
        )
        wf_result = await bridge.run_walk_forward_async(
            strategy=strategy,
            df=df,
            symbol=request.symbol,
            timeframe=request.timeframe,
            initial_capital=request.initial_capital,
            direction=request.direction,
            metric=request.optimization_metric,
        )

        return ImproveStrategyResponse(
            success=True,
            original_params=request.strategy_params,
            recommended_params=wf_result.recommended_params,
            confidence_level=wf_result.confidence_level,
            overfit_score=round(wf_result.overfit_score, 4),
            consistency_ratio=round(wf_result.consistency_ratio, 4),
            parameter_stability=round(wf_result.parameter_stability, 4),
            walk_forward_details=wf_result.to_dict(),
        )

    except ValueError as e:
        logger.warning(f"Strategy improvement error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Strategy improvement failed: {e}")
        raise HTTPException(status_code=500, detail=f"Improvement failed: {e}")


@router.get("/pipeline/{pipeline_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(pipeline_id: str) -> PipelineStatusResponse:
    """
    Get the status of a pipeline job.

    Returns current stage, progress percentage, and timing information.
    Pipeline IDs are returned from the POST /generate endpoint.
    """
    _evict_stale_jobs()
    job = _pipeline_jobs.get(pipeline_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")

    # Calculate progress based on stage
    stage_progress = {
        "context_analysis": 15,
        "strategy_generation": 40,
        "consensus": 55,
        "backtest": 75,
        "evaluation": 85,
        "walk_forward": 95,
        "complete": 100,
        "failed": 100,
    }
    current_stage = job.get("current_stage", "")
    progress = stage_progress.get(current_stage, 0)

    return PipelineStatusResponse(
        pipeline_id=pipeline_id,
        status=job.get("status", "unknown"),
        progress_pct=float(progress),
        current_stage=current_stage,
        created_at=job.get("created_at", ""),
        completed_at=job.get("completed_at"),
    )


@router.get("/pipeline/{pipeline_id}/result", response_model=PipelineResultResponse)
async def get_pipeline_result(pipeline_id: str) -> PipelineResultResponse:
    """
    Get the result of a completed pipeline job.

    Returns the full pipeline result including strategy, backtest metrics,
    and walk-forward data. Only available for completed or failed jobs.
    """
    _evict_stale_jobs()
    job = _pipeline_jobs.get(pipeline_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")

    status = job.get("status", "unknown")
    if status == "running":
        raise HTTPException(status_code=400, detail="Pipeline is still running")

    result_data = job.get("result")
    pipeline_resp = PipelineResponse(**result_data) if result_data else None

    return PipelineResultResponse(
        pipeline_id=pipeline_id,
        status=status,
        result=pipeline_resp,
        error=job.get("error"),
    )


# =============================================================================
# P2-4: Async streaming pipeline (background task + WebSocket)
# =============================================================================


class StreamGenerateRequest(BaseModel):
    """Request for async streaming strategy generation (P2-4)."""

    symbol: str = Field("BTCUSDT", description="Trading pair")
    timeframe: str = Field("15", description="Candle interval")
    agents: list[str] = Field(default_factory=lambda: ["deepseek"])
    run_backtest: bool = Field(False)
    run_debate: bool = Field(True)
    initial_capital: float = Field(10000, ge=100)
    leverage: int = Field(1, ge=1, le=125)
    start_date: str = Field("2025-01-01")
    end_date: str = Field("2025-06-01")
    pipeline_timeout: float = Field(300.0, ge=10.0, le=600.0)


class StreamJobResponse(BaseModel):
    """Returned immediately from POST /generate-stream."""

    pipeline_id: str
    ws_url: str
    message: str = "Pipeline started. Connect to ws_url to stream events."


@router.post("/generate-stream", response_model=StreamJobResponse)
async def generate_strategy_stream(request: StreamGenerateRequest) -> StreamJobResponse:
    """
    Start async strategy generation and return a pipeline_id for WebSocket streaming.

    **P2-4**: Node completion events are streamed in real-time via WebSocket.

    Workflow:
    1. POST /ai-pipeline/generate-stream → get `pipeline_id`
    2. Connect to `ws://host/ai-pipeline/stream/{pipeline_id}`
    3. Receive JSON events: `{"node": "analyze_market", "status": "completed", ...}`
    4. Final event has `"status": "done"` with the full result

    Events shape::

        {"node": "analyze_market", "status": "completed", "iteration": 1, "errors": 0}
        ...
        {"status": "done", "success": true, "pipeline_id": "...", "result": {...}}
    """
    _evict_stale_jobs()
    pipeline_id = str(uuid.uuid4())[:12]

    from backend.agents.langgraph_orchestrator import make_pipeline_event_queue

    queue, event_fn = make_pipeline_event_queue()
    _pipeline_queues[pipeline_id] = queue

    _pipeline_jobs[pipeline_id] = {
        "status": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "current_stage": "starting",
        "stream_request": request.model_dump(),
    }

    async def _run_pipeline_bg() -> None:
        """Background coroutine: runs pipeline, feeds events into queue."""
        try:
            from backend.agents.trading_strategy_graph import run_strategy_pipeline

            df = await _load_ohlcv_data(
                symbol=request.symbol,
                timeframe=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
            )

            state = await run_strategy_pipeline(
                symbol=request.symbol,
                timeframe=request.timeframe,
                df=df,
                agents=request.agents,
                run_backtest=request.run_backtest,
                run_debate=request.run_debate,
                initial_capital=request.initial_capital,
                leverage=request.leverage,
                pipeline_timeout=request.pipeline_timeout,
                event_fn=event_fn,
            )

            report = state.get_result("report") or {}
            _pipeline_jobs[pipeline_id].update(
                {
                    "status": "completed",
                    "completed_at": datetime.now(UTC).isoformat(),
                    "current_stage": "report",
                    "result": report,
                }
            )
            await queue.put(
                {
                    "status": "done",
                    "success": len(state.errors) == 0,
                    "pipeline_id": pipeline_id,
                    "errors": state.errors,
                    "llm_call_count": state.llm_call_count,
                    "total_cost_usd": round(state.total_cost_usd, 6),
                    "result": report,
                }
            )
        except Exception as exc:
            logger.error(f"[StreamPipeline] {pipeline_id} failed: {exc}")
            _pipeline_jobs[pipeline_id].update(
                {"status": "failed", "error": str(exc), "completed_at": datetime.now(UTC).isoformat()}
            )
            await queue.put({"status": "done", "success": False, "error": str(exc), "pipeline_id": pipeline_id})

    asyncio.create_task(_run_pipeline_bg())

    return StreamJobResponse(
        pipeline_id=pipeline_id,
        ws_url=f"/ai-pipeline/stream/{pipeline_id}",
    )


@router.websocket("/stream/{pipeline_id}")
async def stream_pipeline_events(websocket: WebSocket, pipeline_id: str) -> None:
    """
    WebSocket endpoint for streaming pipeline node events (P2-4).

    Connects to a running pipeline job and receives a JSON event for each
    completed node.  The connection closes automatically when the pipeline
    finishes (event with ``"status": "done"``).

    Usage::

        ws = new WebSocket("ws://localhost:8000/ai-pipeline/stream/<pipeline_id>")
        ws.onmessage = (e) => console.log(JSON.parse(e.data))

    Each event::

        {"node": "analyze_market", "status": "completed", "iteration": 1, ...}

    Final event::

        {"status": "done", "success": true/false, "result": {...}}
    """
    queue = _pipeline_queues.get(pipeline_id)
    if queue is None:
        await websocket.accept()
        await websocket.send_json({"error": f"Pipeline '{pipeline_id}' not found or already completed"})
        await websocket.close(code=1008)
        return

    await websocket.accept()
    logger.info(f"[WS] Client connected to pipeline stream: {pipeline_id}")

    try:
        while True:
            try:
                # Wait up to 30s for next event to avoid holding connection forever
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"status": "heartbeat", "pipeline_id": pipeline_id})
                continue

            await websocket.send_json(event)

            if event.get("status") == "done":
                # Pipeline finished — clean up queue and close
                _pipeline_queues.pop(pipeline_id, None)
                logger.info(f"[WS] Pipeline {pipeline_id} done — closing stream")
                break

    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected from pipeline stream: {pipeline_id}")
        _pipeline_queues.pop(pipeline_id, None)
    except Exception as exc:
        logger.error(f"[WS] Stream error for {pipeline_id}: {exc}")
        _pipeline_queues.pop(pipeline_id, None)
        with contextlib.suppress(Exception):
            await websocket.send_json({"status": "error", "error": str(exc)})
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()


# =============================================================================
# P2-3: HITL (Human-in-the-Loop) endpoints
# =============================================================================


class HITLGenerateRequest(BaseModel):
    """Request for HITL-enabled strategy generation (P2-3)."""

    symbol: str = Field("BTCUSDT")
    timeframe: str = Field("15")
    agents: list[str] = Field(default_factory=lambda: ["deepseek"])
    run_backtest: bool = Field(True)
    initial_capital: float = Field(10000, ge=100)
    leverage: int = Field(1, ge=1, le=125)
    start_date: str = Field("2025-01-01")
    end_date: str = Field("2025-06-01")
    pipeline_timeout: float = Field(300.0, ge=10.0)


class HITLStatusResponse(BaseModel):
    """HITL pending status for a pipeline job."""

    pipeline_id: str
    hitl_pending: bool
    hitl_payload: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class HITLApproveResponse(BaseModel):
    """Result of approving a HITL-paused pipeline."""

    pipeline_id: str
    status: str
    message: str
    result: dict[str, Any] = Field(default_factory=dict)


@router.post("/generate-hitl", response_model=HITLStatusResponse)
async def generate_strategy_hitl(request: HITLGenerateRequest) -> HITLStatusResponse:
    """
    Generate strategy with Human-in-the-Loop checkpoint before memory update (P2-3).

    The pipeline pauses after ML validation and before memory_update.
    Returns `hitl_pending=True` with a `hitl_payload` summary for human review.

    To resume: call ``POST /ai-pipeline/pipeline/{pipeline_id}/hitl/approve``.

    Workflow::

        POST /ai-pipeline/generate-hitl → {hitl_pending: true, hitl_payload: {...}}
        # Human reviews strategy quality in hitl_payload
        POST /ai-pipeline/pipeline/{id}/hitl/approve → pipeline resumes
    """
    _evict_stale_jobs()
    pipeline_id = str(uuid.uuid4())[:12]
    _pipeline_jobs[pipeline_id] = {
        "status": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "hitl_request": request.model_dump(),
    }

    try:
        from backend.agents.trading_strategy_graph import run_strategy_pipeline

        df = await _load_ohlcv_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        state = await run_strategy_pipeline(
            symbol=request.symbol,
            timeframe=request.timeframe,
            df=df,
            agents=request.agents,
            run_backtest=request.run_backtest,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            pipeline_timeout=request.pipeline_timeout,
            hitl_enabled=True,
            hitl_approved=False,
        )

        hitl_pending = bool(state.context.get("hitl_pending", False))
        hitl_payload = state.context.get("hitl_payload", {})

        _pipeline_jobs[pipeline_id].update(
            {
                "status": "hitl_pending" if hitl_pending else "completed",
                "hitl_pending": hitl_pending,
                "hitl_payload": hitl_payload,
                # Persist enough context to re-run the approval path
                "_partial_state_session_id": state.session_id,
                "_partial_results_keys": list(state.results.keys()),
                "completed_at": datetime.now(UTC).isoformat() if not hitl_pending else None,
            }
        )

        return HITLStatusResponse(
            pipeline_id=pipeline_id,
            hitl_pending=hitl_pending,
            hitl_payload=hitl_payload,
            message=(
                f"Pipeline paused for human review. "
                f"POST /ai-pipeline/pipeline/{pipeline_id}/hitl/approve to continue."
                if hitl_pending
                else "Pipeline completed without HITL pause."
            ),
        )

    except Exception as exc:
        _pipeline_jobs[pipeline_id].update({"status": "failed", "error": str(exc)})
        logger.error(f"[HITL generate] {pipeline_id} failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pipeline/{pipeline_id}/hitl", response_model=HITLStatusResponse)
async def get_hitl_status(pipeline_id: str) -> HITLStatusResponse:
    """
    Check HITL pending status for a pipeline job (P2-3).

    Returns whether the pipeline is paused awaiting human approval,
    and the strategy summary payload for review.
    """
    _evict_stale_jobs()
    job = _pipeline_jobs.get(pipeline_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")

    return HITLStatusResponse(
        pipeline_id=pipeline_id,
        hitl_pending=bool(job.get("hitl_pending", False)),
        hitl_payload=job.get("hitl_payload", {}),
        message=(
            "Pipeline is paused. POST /approve to resume."
            if job.get("hitl_pending")
            else f"Pipeline status: {job.get('status', 'unknown')}"
        ),
    )


@router.post("/pipeline/{pipeline_id}/hitl/approve", response_model=HITLApproveResponse)
async def approve_hitl_pipeline(pipeline_id: str) -> HITLApproveResponse:
    """
    Approve a HITL-paused pipeline and resume from memory_update (P2-3).

    Re-runs the pipeline from scratch with ``hitl_approved=True`` so the
    HITLCheckNode passes straight through to memory_update → reflection → report.

    Returns the final pipeline report on completion.
    """
    _evict_stale_jobs()
    job = _pipeline_jobs.get(pipeline_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")

    if not job.get("hitl_pending"):
        return HITLApproveResponse(
            pipeline_id=pipeline_id,
            status=job.get("status", "unknown"),
            message="Pipeline is not in HITL-pending state.",
        )

    original_request = job.get("hitl_request", {})
    if not original_request:
        raise HTTPException(status_code=400, detail="Original request not stored — cannot resume.")

    try:
        from backend.agents.trading_strategy_graph import run_strategy_pipeline

        symbol = original_request.get("symbol")
        timeframe = original_request.get("timeframe")
        if not symbol or not timeframe:
            raise HTTPException(
                status_code=400,
                detail="Stored request is missing symbol or timeframe — cannot resume.",
            )

        df = await _load_ohlcv_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=original_request.get("start_date", "2025-01-01"),
            end_date=original_request.get("end_date", "2025-06-01"),
        )

        state = await run_strategy_pipeline(
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            agents=original_request.get("agents", ["deepseek"]),
            run_backtest=original_request.get("run_backtest", True),
            initial_capital=original_request.get("initial_capital", 10000),
            leverage=original_request.get("leverage", 1),
            pipeline_timeout=original_request.get("pipeline_timeout", 300.0),
            hitl_enabled=True,
            hitl_approved=True,  # ← human approved
        )

        report = state.get_result("report") or {}
        _pipeline_jobs[pipeline_id].update(
            {
                "status": "completed",
                "hitl_pending": False,
                "completed_at": datetime.now(UTC).isoformat(),
                "result": report,
            }
        )

        logger.info(f"[HITL approve] Pipeline {pipeline_id} resumed and completed")
        return HITLApproveResponse(
            pipeline_id=pipeline_id,
            status="completed",
            message="Pipeline resumed and completed after human approval.",
            result=report,
        )

    except Exception as exc:
        _pipeline_jobs[pipeline_id].update({"status": "failed", "error": str(exc)})
        logger.error(f"[HITL approve] {pipeline_id} failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# ANALYZE EXISTING STRATEGY (seed_graph mode)
# =============================================================================


class AnalyzeStrategyRequest(BaseModel):
    """Request to analyze an existing Strategy Builder strategy with AI agents."""

    strategy_id: int | None = Field(None, description="DB id of saved strategy (loads graph from DB)")
    strategy_graph: dict[str, Any] | None = Field(None, description="Raw strategy_graph dict (blocks+connections)")
    symbol: str = Field("BTCUSDT", description="Trading pair for backtest")
    timeframe: str = Field("15", description="Candle interval")
    agents: list[str] = Field(default_factory=lambda: ["deepseek"])
    run_debate: bool = Field(True, description="Run multi-agent debate on results")
    initial_capital: float = Field(10000, ge=100)
    leverage: int = Field(1, ge=1, le=125)
    start_date: str = Field("2025-01-01")
    end_date: str = Field("2025-06-01")
    pipeline_timeout: float = Field(300.0, ge=10.0, le=600.0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "strategy_id": 42,
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "agents": ["deepseek", "qwen"],
                "run_debate": True,
                "start_date": "2025-01-01",
                "end_date": "2025-04-01",
            }
        }
    }


class AnalyzeStrategyResponse(BaseModel):
    """Result of AI agent analysis on an existing strategy."""

    success: bool
    pipeline_id: str
    strategy_name: str = ""
    backtest_metrics: dict[str, Any] = Field(default_factory=dict)
    regime: str = ""
    agent_verdict: str = ""  # summary from report node
    refinement_applied: bool = False
    errors: list[dict[str, Any]] = Field(default_factory=list)
    report: dict[str, Any] = Field(default_factory=dict)


@router.post("/analyze-strategy", response_model=AnalyzeStrategyResponse)
async def analyze_existing_strategy(request: AnalyzeStrategyRequest) -> AnalyzeStrategyResponse:
    """
    Analyze an existing Strategy Builder strategy with AI agents.

    **Seed-graph mode**: skips LLM strategy generation and runs the pipeline
    directly on your existing blocks+connections graph:

    1. analyze_market — load OHLCV, build market context
    2. regime_classifier — classify current market regime
    3. backtest — run your strategy via StrategyBuilderAdapter (all 40+ block types)
    4. backtest_analysis — diagnose failures (no_signal, direction_mismatch, low_sharpe…)
    5. debate (optional) — agents argue whether the strategy is viable
    6. walk-forward validation — overfitting gate
    7. optimize + ml_validation — auto-tune parameters
    8. report — final verdict, recommended changes

    Provide either `strategy_id` (loads saved strategy from DB) or
    `strategy_graph` (raw blocks+connections dict).
    """
    # --- resolve strategy_graph ---
    graph: dict[str, Any] | None = request.strategy_graph
    strategy_name = "Existing Strategy"

    if graph is None and request.strategy_id is not None:
        # Load strategy graph from DB
        try:
            import asyncio as _asyncio

            from backend.database.session import get_session

            def _load_strategy() -> dict[str, Any] | None:
                with get_session() as session:
                    from backend.database.models.strategy import Strategy as StrategyModel

                    row = session.get(StrategyModel, request.strategy_id)
                    if row is None:
                        return None
                    return {
                        "name": row.name,
                        "blocks": row.builder_blocks or [],
                        "connections": row.builder_connections or [],
                        "interval": row.timeframe or request.timeframe,
                    }

            loaded = await _asyncio.to_thread(_load_strategy)
            if loaded is None:
                raise HTTPException(status_code=404, detail=f"Strategy {request.strategy_id} not found")
            graph = loaded
            strategy_name = graph.get("name", strategy_name)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[analyze-strategy] DB load failed: {exc}")
            raise HTTPException(status_code=500, detail=f"Failed to load strategy: {exc}")

    if graph is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either strategy_id or strategy_graph.",
        )

    if not graph.get("blocks"):
        raise HTTPException(status_code=400, detail="Strategy has no blocks — cannot analyse.")

    strategy_name = graph.get("name", strategy_name)

    # --- run pipeline in seed_graph mode ---
    _evict_stale_jobs()
    pipeline_id = str(uuid.uuid4())[:12]
    _pipeline_jobs[pipeline_id] = {
        "status": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "seed_strategy": strategy_name,
    }

    try:
        from backend.agents.trading_strategy_graph import run_strategy_pipeline

        df = await _load_ohlcv_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        state = await run_strategy_pipeline(
            symbol=request.symbol,
            timeframe=request.timeframe,
            df=df,
            agents=request.agents,
            run_backtest=True,          # always backtest in analysis mode
            run_debate=request.run_debate,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            pipeline_timeout=request.pipeline_timeout,
            seed_graph=graph,
        )

        report = state.get_result("report") or {}
        backtest = state.get_result("backtest") or {}
        metrics = backtest.get("metrics", {})
        regime_result = state.get_result("regime_classifier") or {}
        regime = regime_result.get("regime", "unknown")

        refinement_applied = state.context.get("refinement_iteration", 0) > 0

        _pipeline_jobs[pipeline_id].update(
            {
                "status": "completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "result": report,
            }
        )

        return AnalyzeStrategyResponse(
            success=len(state.errors) == 0,
            pipeline_id=pipeline_id,
            strategy_name=strategy_name,
            backtest_metrics=metrics,
            regime=regime,
            agent_verdict=report.get("summary", report.get("recommendation", "")),
            refinement_applied=refinement_applied,
            errors=state.errors,
            report=report,
        )

    except HTTPException:
        raise
    except Exception as exc:
        _pipeline_jobs[pipeline_id].update({"status": "failed", "error": str(exc)})
        logger.error(f"[analyze-strategy] {pipeline_id} failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# HELPERS
# =============================================================================


async def _load_ohlcv_data(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Load OHLCV data from the database."""
    import asyncio

    from backend.database.repository.kline_repository import KlineRepository
    from backend.database.session import get_session

    def _fetch() -> pd.DataFrame:
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)
        with get_session() as session:
            repo = KlineRepository(session)
            klines = repo.get_klines(
                symbol=symbol,
                interval=timeframe,
                start_time=start_ts,
                end_time=end_ts,
                limit=100_000,
                ascending=True,
            )
            if not klines:
                return pd.DataFrame()
            records = [
                {
                    "open_time": k.open_time,
                    "open": float(k.open_price),
                    "high": float(k.high_price),
                    "low": float(k.low_price),
                    "close": float(k.close_price),
                    "volume": float(k.volume),
                }
                for k in klines
            ]
            return pd.DataFrame(records)

    df = await asyncio.to_thread(_fetch)

    if df is None or df.empty:
        raise ValueError(f"No OHLCV data for {symbol} {timeframe} from {start_date} to {end_date}")

    return df


def _check_agent_available(agent_name: str) -> bool:
    """Check if an LLM agent has a valid API key."""
    try:
        from backend.security.key_manager import get_key_manager

        km = get_key_manager()
        key_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "qwen": "QWEN_API_KEY",
            "perplexity": "PERPLEXITY_API_KEY",
        }
        key_name = key_map.get(agent_name)
        if not key_name:
            return False
        key = km.get_decrypted_key(key_name)
        return bool(key)
    except Exception:
        return False
