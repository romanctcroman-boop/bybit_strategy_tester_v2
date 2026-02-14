"""
AI Agents Router
Endpoints for interacting with AI agents (DeepSeek and Perplexity).
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.circuit_breaker_manager import CircuitBreakerManager
from backend.agents.unified_agent_interface import UnifiedAgentInterface

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize global instances
_agent_interface: UnifiedAgentInterface | None = None
_circuit_breaker_manager: CircuitBreakerManager | None = None


def get_agent_interface() -> UnifiedAgentInterface:
    """Get or create UnifiedAgentInterface singleton"""
    global _agent_interface
    if _agent_interface is None:
        _agent_interface = UnifiedAgentInterface()
    return _agent_interface


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get or create CircuitBreakerManager singleton"""
    global _circuit_breaker_manager
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    return _circuit_breaker_manager


# Request/Response Models
class AgentQueryRequest(BaseModel):
    """Agent query request"""

    prompt: str = Field(..., description="The prompt/question for the AI agent")
    model: str | None = Field(None, description="Specific model to use (optional)")
    temperature: float | None = Field(0.7, ge=0.0, le=2.0, description="Temperature for response generation")
    max_tokens: int | None = Field(2000, ge=1, le=32000, description="Maximum tokens in response")

    model_config = {
        "json_schema_extra": {
            "example": {
                "prompt": "Analyze the current market trend for BTC/USDT",
                "model": "deepseek-chat",
                "temperature": 0.7,
                "max_tokens": 1000,
            }
        }
    }


class AgentQueryResponse(BaseModel):
    """Agent query response"""

    response: str = Field(..., description="The AI agent's response")
    model_used: str = Field(..., description="The model that was used")
    tokens_used: int | None = Field(None, description="Number of tokens used (if available)")
    latency_ms: float | None = Field(None, description="Response latency in milliseconds")
    api_key_id: str | None = Field(None, description="API key ID used (for debugging)")
    from_cache: bool | None = Field(False, description="Whether the response came from cache")

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "Based on the current market data, BTC/USDT shows...",
                "model_used": "deepseek-chat",
                "tokens_used": 150,
                "latency_ms": 1250.5,
                "api_key_id": "key_123",
            }
        }
    }


class AgentStatsResponse(BaseModel):
    """Agent statistics response"""

    deepseek: dict[str, Any] = Field(..., description="DeepSeek agent statistics")
    perplexity: dict[str, Any] = Field(..., description="Perplexity agent statistics")
    circuit_breakers: dict[str, Any] = Field(..., description="Circuit breaker status")

    model_config = {
        "json_schema_extra": {
            "example": {
                "deepseek": {
                    "total_keys": 8,
                    "healthy_keys": 7,
                    "total_requests": 1234,
                    "total_errors": 5,
                },
                "perplexity": {
                    "total_keys": 4,
                    "healthy_keys": 4,
                    "total_requests": 567,
                    "total_errors": 1,
                },
                "circuit_breakers": {
                    "deepseek_api": "CLOSED",
                    "perplexity_api": "CLOSED",
                },
            }
        }
    }


@router.get("/stats", response_model=AgentStatsResponse)
async def get_agent_stats() -> AgentStatsResponse:
    """
    Get AI agent statistics

    Returns statistics about DeepSeek and Perplexity agents including:
    - Number of API keys (total and healthy)
    - Request counts
    - Error counts
    - Circuit breaker status
    """
    try:
        agent_interface = get_agent_interface()
        circuit_manager = get_circuit_breaker_manager()

        # Get agent stats (NOT async)
        stats = agent_interface.get_stats()  # Get circuit breaker status
        cb_status = {}
        for name in ["deepseek_api", "perplexity_api"]:
            breaker = circuit_manager.breakers.get(name)
            if breaker:
                cb_status[name] = breaker.state.value
            else:
                cb_status[name] = "UNKNOWN"

        return AgentStatsResponse(
            deepseek=stats.get("deepseek", {}),
            perplexity=stats.get("perplexity", {}),
            circuit_breakers=cb_status,
        )

    except Exception as e:
        logger.error(f"Error getting agent stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get agent stats: {e!s}")


@router.post("/query/deepseek", response_model=AgentQueryResponse)
async def query_deepseek(request: AgentQueryRequest) -> AgentQueryResponse:
    """
    Query DeepSeek AI agent

    Send a prompt to the DeepSeek AI agent and get a response.

    - **prompt**: The question or prompt for the AI
    - **model**: Specific DeepSeek model to use (default: deepseek-chat)
    - **temperature**: Response randomness (0.0 = deterministic, 2.0 = very random)
    - **max_tokens**: Maximum length of response
    """
    try:
        agent_interface = get_agent_interface()

        # Query DeepSeek
        result = await agent_interface.query_deepseek(
            prompt=request.prompt,
            model=request.model or "deepseek-chat",
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        return AgentQueryResponse(
            response=result.get("response", ""),
            model_used=result.get("model", "deepseek-chat"),
            tokens_used=result.get("tokens_used"),
            latency_ms=result.get("latency_ms"),
            api_key_id=result.get("api_key_id"),
            from_cache=result.get("from_cache", False),
        )

    except Exception as e:
        logger.error(f"Error querying DeepSeek: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query DeepSeek: {e!s}")


@router.post("/query/perplexity", response_model=AgentQueryResponse)
async def query_perplexity(request: AgentQueryRequest) -> AgentQueryResponse:
    """
    Query Perplexity AI agent

    Send a prompt to the Perplexity AI agent and get a response.

    - **prompt**: The question or prompt for the AI
    - **model**: Specific Perplexity model to use (default: llama-3.1-sonar-small-128k-online)
    - **temperature**: Response randomness (0.0 = deterministic, 2.0 = very random)
    - **max_tokens**: Maximum length of response
    """
    try:
        agent_interface = get_agent_interface()

        # Query Perplexity
        result = await agent_interface.query_perplexity(
            prompt=request.prompt,
            model=request.model or "llama-3.1-sonar-small-128k-online",
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        return AgentQueryResponse(
            response=result.get("response", ""),
            model_used=result.get("model", "llama-3.1-sonar-small-128k-online"),
            tokens_used=result.get("tokens_used"),
            latency_ms=result.get("latency_ms"),
            api_key_id=result.get("api_key_id"),
            from_cache=result.get("from_cache", False),
        )

    except Exception as e:
        logger.error(f"Error querying Perplexity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query Perplexity: {e!s}")


@router.post("/query/auto", response_model=AgentQueryResponse)
async def query_auto(request: AgentQueryRequest) -> AgentQueryResponse:
    """
    Auto-select and query best available AI agent

    Automatically selects the best available agent (DeepSeek or Perplexity)
    based on health status and circuit breaker state.

    - **prompt**: The question or prompt for the AI
    - **temperature**: Response randomness (0.0 = deterministic, 2.0 = very random)
    - **max_tokens**: Maximum length of response
    """
    try:
        agent_interface = get_agent_interface()

        # Try DeepSeek first, fall back to Perplexity
        try:
            result = await agent_interface.query_deepseek(
                prompt=request.prompt,
                model=request.model or "deepseek-chat",
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            return AgentQueryResponse(
                response=result.get("response", ""),
                model_used=f"deepseek:{result.get('model', 'deepseek-chat')}",
                tokens_used=result.get("tokens_used"),
                latency_ms=result.get("latency_ms"),
                api_key_id=result.get("api_key_id"),
                from_cache=result.get("from_cache", False),
            )

        except Exception as deepseek_error:
            logger.warning(f"DeepSeek failed, trying Perplexity: {deepseek_error}")

            # Fall back to Perplexity
            result = await agent_interface.query_perplexity(
                prompt=request.prompt,
                model=request.model or "llama-3.1-sonar-small-128k-online",
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            return AgentQueryResponse(
                response=result.get("response", ""),
                model_used=f"perplexity:{result.get('model', 'llama-3.1-sonar-small-128k-online')}",
                tokens_used=result.get("tokens_used"),
                latency_ms=result.get("latency_ms"),
                api_key_id=result.get("api_key_id"),
                from_cache=result.get("from_cache", False),
            )

    except Exception as e:
        logger.error(f"Error in auto query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"All agents failed: {e!s}")


@router.get("/cache/stats", response_model=dict[str, Any])
async def get_cache_stats() -> dict[str, Any]:
    """
    Get AI cache statistics

    Returns cache performance metrics:
    - enabled: Whether caching is active
    - redis_connected: Redis connection status
    - hits: Number of cache hits
    - misses: Number of cache misses
    - hit_rate_percent: Cache hit rate percentage
    - total_requests: Total cached requests
    """
    try:
        from backend.core.ai_cache import get_cache_manager

        cache_manager = get_cache_manager()
        stats = cache_manager.get_stats()

        return stats

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {e!s}")


@router.post("/cache/clear")
async def clear_cache() -> dict[str, Any]:
    """
    Clear all cached AI responses

    Returns:
        Number of cache entries cleared
    """
    try:
        from backend.core.ai_cache import get_cache_manager

        cache_manager = get_cache_manager()
        cleared_count = cache_manager.clear_all()

        return {
            "success": True,
            "cleared_count": cleared_count,
            "message": f"Cleared {cleared_count} cache entries",
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {e!s}")


# ============================================================================
# ML + AI INTEGRATION ENDPOINTS
# ============================================================================


class FeatureSuggestionRequest(BaseModel):
    """Request for AI feature suggestions"""

    objective: str = Field(..., description="What to predict (e.g., 'price direction')")
    asset: str = Field("BTC/USDT", description="Trading pair")
    timeframe: str = Field("1h", description="Candle timeframe")
    max_features: int = Field(10, ge=1, le=50, description="Maximum features to suggest")


class FeatureCodeRequest(BaseModel):
    """Request for feature code generation"""

    feature_name: str = Field(..., description="Indicator name (e.g., 'RSI')")
    parameters: dict[str, Any] = Field(..., description="Indicator parameters")
    data_format: str = Field(
        "pandas DataFrame with OHLCV columns",
        description="Input data format description",
    )


class StrategyRequest(BaseModel):
    """Request for complete strategy generation"""

    objective: str = Field(..., description="Strategy objective")
    asset: str = Field("BTC/USDT", description="Trading pair")
    timeframe: str = Field("1h", description="Candle timeframe")
    risk_tolerance: str = Field("medium", description="Risk level: low/medium/high")


@router.post("/ml/suggest-features", summary="AI Feature Suggestions")
async def suggest_features(request: FeatureSuggestionRequest):
    """
    Ask AI to suggest technical indicators for trading strategy

    Uses AI agents to recommend relevant features based on objective.
    """
    try:
        from backend.ml.ai_feature_engineer import AIFeatureEngineer

        engineer = AIFeatureEngineer()

        result = await engineer.suggest_features(
            objective=request.objective,
            asset=request.asset,
            timeframe=request.timeframe,
            max_features=request.max_features,
        )

        return result

    except Exception as e:
        logger.error(f"Error suggesting features: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to suggest features: {e!s}")


@router.post("/ml/generate-code", summary="AI Code Generation")
async def generate_feature_code(request: FeatureCodeRequest):
    """
    Ask AI to generate Python code for calculating a feature

    Returns executable code for the requested indicator.
    """
    try:
        from backend.ml.ai_feature_engineer import AIFeatureEngineer

        engineer = AIFeatureEngineer()

        result = await engineer.generate_feature_code(
            feature_name=request.feature_name,
            parameters=request.parameters,
            data_format=request.data_format,
        )

        return result

    except Exception as e:
        logger.error(f"Error generating code: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate code: {e!s}")


@router.post("/ml/design-strategy", summary="AI Strategy Design")
async def design_strategy(request: StrategyRequest):
    """
    Ask AI to design a complete trading strategy

    Returns comprehensive strategy with entry/exit rules, features, risk management.
    """
    try:
        from backend.ml.ai_feature_engineer import AIFeatureEngineer

        engineer = AIFeatureEngineer()

        result = await engineer.suggest_complete_strategy(
            objective=request.objective,
            asset=request.asset,
            timeframe=request.timeframe,
            risk_tolerance=request.risk_tolerance,
        )

        return result

    except Exception as e:
        logger.error(f"Error designing strategy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to design strategy: {e!s}")


# ============================================================================
# BACKTEST EXECUTOR ENDPOINTS (ML + Backtest Integration)
# ============================================================================


class BacktestExecutorRequest(BaseModel):
    """Request for AI backtest execution"""

    objective: str = Field(..., description="Trading objective")
    asset: str = Field("BTC/USDT", description="Trading pair")
    timeframe: str = Field("1h", description="Candle timeframe")
    risk_tolerance: str = Field("medium", description="Risk level: low/medium/high")
    start_date: str = Field(..., description="Backtest start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Backtest end date (YYYY-MM-DD)")
    initial_capital: float = Field(10000.0, ge=100, description="Initial capital")
    num_variations: int = Field(1, ge=1, le=5, description="Number of strategy variations")


@router.post("/backtest/ai-generate-strategy", summary="AI Generate Backtest Strategy")
async def generate_backtest_strategy(request: StrategyRequest):
    """
    Generate AI strategy for backtesting

    Creates a complete trading strategy with entry/exit rules, features, and risk management.
    """
    try:
        from backend.ml.ai_backtest_executor import AIBacktestExecutor

        executor = AIBacktestExecutor()

        strategy = await executor.generate_ai_strategy(
            objective=request.objective,
            asset=request.asset,
            timeframe=request.timeframe,
            risk_tolerance=request.risk_tolerance,
        )

        return {
            "name": strategy.name,
            "asset": strategy.asset,
            "timeframe": strategy.timeframe,
            "features": strategy.features,
            "entry_long": strategy.entry_long,
            "entry_short": strategy.entry_short,
            "risk_per_trade": strategy.risk_per_trade,
        }

    except Exception as e:
        logger.error(f"Error generating backtest strategy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate strategy: {e!s}")


@router.post("/backtest/ai-execute-series", summary="AI Execute Backtest Series")
async def execute_backtest_series(request: BacktestExecutorRequest):
    """
    Execute series of AI-generated backtest configurations

    Runs multiple variations of AI strategy with different parameters.
    Results include complete backtest configs ready for execution.
    """
    try:
        from backend.ml.ai_backtest_executor import AIBacktestExecutor

        executor = AIBacktestExecutor()

        results = await executor.execute_ai_backtest_series(
            objective=request.objective,
            asset=request.asset,
            timeframe=request.timeframe,
            risk_tolerance=request.risk_tolerance,
            start_date=request.start_date,
            end_date=request.end_date,
            num_variations=request.num_variations,
        )

        return {
            "configurations_ready": len(results),
            "results": results,
            "total_strategies": len(executor.ai_strategies),
        }

    except Exception as e:
        logger.error(f"Error executing backtest series: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute backtest series: {e!s}")


@router.post("/backtest/ai-analyze", summary="AI Analyze Backtest Results")
async def analyze_backtest_results_endpoint(results: list[dict[str, Any]] = []):
    """
    Ask AI to analyze backtest results and recommend best strategy

    Evaluates multiple backtest results and provides AI-driven recommendations.
    """
    try:
        from backend.ml.ai_backtest_executor import AIBacktestExecutor

        executor = AIBacktestExecutor()

        analysis = await executor.analyze_backtest_results(results)

        return {
            "analysis": analysis,
            "results_analyzed": len(results),
        }

    except Exception as e:
        logger.error(f"Error analyzing results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze results: {e!s}")


# ============================================================================
# AGENT DASHBOARD ENDPOINTS
# Added 2026-02-12 per Agent Ecosystem Audit — Dashboard Integration
# ============================================================================


class WorkflowStartRequest(BaseModel):
    """Request model for starting an autonomous workflow."""

    symbol: str = Field("BTCUSDT", description="Trading pair")
    interval: str = Field("15", description="Timeframe")
    strategy_type: str = Field("rsi", description="Fallback strategy")
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    start_date: str = Field("2025-06-01", description="Start date YYYY-MM-DD")
    end_date: str = Field("2025-07-01", description="End date YYYY-MM-DD")
    initial_capital: float = Field(10000.0, ge=100, le=100_000_000)
    leverage: float = Field(10.0, ge=1, le=125)
    direction: str = Field("both")
    evolution_enabled: bool = Field(True, description="Run AI evolution phase")
    max_generations: int = Field(3, ge=1, le=10)
    save_to_memory: bool = Field(True)


@router.post(
    "/dashboard/workflow/start",
    summary="Start Autonomous Backtesting Workflow",
)
async def dashboard_start_workflow(request: WorkflowStartRequest) -> dict[str, Any]:
    """
    Launch an autonomous backtesting pipeline.

    Steps: fetch data → evolve strategy → backtest → report → learn.
    Returns immediately with a workflow_id for status polling.
    """
    import asyncio

    try:
        from backend.agents.workflows.autonomous_backtesting import (
            AutonomousBacktestingWorkflow,
            WorkflowConfig,
        )

        config = WorkflowConfig(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            direction=request.direction,
            evolution_enabled=request.evolution_enabled,
            max_generations=request.max_generations,
            fallback_strategy_type=request.strategy_type,
            fallback_strategy_params=request.strategy_params,
            save_to_memory=request.save_to_memory,
        )

        workflow = AutonomousBacktestingWorkflow()

        # Start the workflow in the background (non-blocking)
        _bg_task = asyncio.create_task(workflow.run(config))
        _bg_task.add_done_callback(lambda t: None)  # prevent GC

        # Wait briefly for the workflow_id to be assigned
        await asyncio.sleep(0.1)

        return {
            "success": True,
            "workflow_id": workflow._workflow_id,
            "message": "Workflow started — poll /dashboard/workflow/status for updates",
        }

    except Exception as e:
        logger.error(f"Failed to start workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/dashboard/workflow/status/{workflow_id}",
    summary="Get Workflow Status",
)
async def dashboard_workflow_status(workflow_id: str) -> dict[str, Any]:
    """Get real-time status of an active workflow."""
    from backend.agents.workflows.autonomous_backtesting import (
        AutonomousBacktestingWorkflow,
    )

    status = AutonomousBacktestingWorkflow.get_status(workflow_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    return {"success": True, **status.to_dict()}


@router.get(
    "/dashboard/workflow/active",
    summary="List Active Workflows",
)
async def dashboard_active_workflows() -> dict[str, Any]:
    """List all currently active autonomous workflows."""
    from backend.agents.workflows.autonomous_backtesting import (
        AutonomousBacktestingWorkflow,
    )

    return {
        "success": True,
        "workflows": AutonomousBacktestingWorkflow.list_active(),
    }


@router.get(
    "/dashboard/patterns",
    summary="Get Strategy Patterns",
)
async def dashboard_patterns(
    limit: int = 500,
    profitable_only: bool = False,
    min_samples: int = 3,
) -> dict[str, Any]:
    """
    Extract strategy patterns from backtest history.

    Returns winning strategy types, optimal timeframes, and insights.
    """
    try:
        from backend.agents.self_improvement.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(
            min_samples=min_samples,
            profitable_only=profitable_only,
        )
        result = await extractor.extract(limit=limit)

        return {"success": True, **result.to_dict()}

    except Exception as e:
        logger.error(f"Pattern extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/dashboard/scheduler/tasks",
    summary="List Scheduler Tasks",
)
async def dashboard_scheduler_tasks() -> dict[str, Any]:
    """List all scheduled tasks and their status."""
    try:
        return {
            "success": True,
            "message": "Scheduler API ready — start scheduler via /dashboard/scheduler/start",
            "tasks": [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/dashboard/paper-trading/sessions",
    summary="List Paper Trading Sessions",
)
async def dashboard_paper_sessions() -> dict[str, Any]:
    """List all paper trading sessions (active and completed)."""
    try:
        from backend.agents.trading.paper_trader import AgentPaperTrader

        return {
            "success": True,
            "sessions": AgentPaperTrader.list_sessions(),
            "active_count": len(AgentPaperTrader.list_active()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PaperTradingStartRequest(BaseModel):
    """Request to start a paper trading session."""

    symbol: str = Field("BTCUSDT")
    strategy_type: str = Field("rsi")
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    initial_balance: float = Field(10000.0, ge=100)
    leverage: float = Field(1.0, ge=1, le=125)
    duration_minutes: float = Field(60.0, ge=0)
    position_size_pct: float = Field(5.0, ge=0.1, le=100)


@router.post(
    "/dashboard/paper-trading/start",
    summary="Start Paper Trading Session",
)
async def dashboard_start_paper_trading(
    request: PaperTradingStartRequest,
) -> dict[str, Any]:
    """
    Start a paper-trading session with live Bybit data.

    The session runs in the background and can be stopped via
    /dashboard/paper-trading/stop/{session_id}.
    """
    try:
        from backend.agents.trading.paper_trader import AgentPaperTrader

        trader = AgentPaperTrader()
        session = await trader.start_session(
            symbol=request.symbol,
            strategy_type=request.strategy_type,
            strategy_params=request.strategy_params,
            initial_balance=request.initial_balance,
            leverage=request.leverage,
            duration_minutes=request.duration_minutes,
            position_size_pct=request.position_size_pct,
        )

        return {
            "success": True,
            "session_id": session.session_id,
            "message": "Paper trading started",
        }
    except Exception as e:
        logger.error(f"Failed to start paper trading: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/dashboard/paper-trading/stop/{session_id}",
    summary="Stop Paper Trading Session",
)
async def dashboard_stop_paper_trading(session_id: str) -> dict[str, Any]:
    """Stop an active paper trading session."""
    try:
        from backend.agents.trading.paper_trader import AgentPaperTrader

        trader = AgentPaperTrader()
        session = await trader.stop_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        return {"success": True, **session.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/dashboard/activity-log",
    summary="Get Agent Activity Log",
)
async def dashboard_activity_log(
    date: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Get agent activity log entries.

    Args:
        date: Date in YYYY-MM-DD format (default: today)
        limit: Max entries to return
    """
    import json
    from datetime import UTC, datetime
    from pathlib import Path

    try:
        log_dir = Path(__file__).parent.parent.parent.parent / "logs" / "agent_activity"
        if not log_dir.exists():
            return {"success": True, "entries": [], "count": 0}

        target_date = date or datetime.now(UTC).strftime("%Y-%m-%d")
        log_file = log_dir / f"activity_{target_date}.jsonl"

        if not log_file.exists():
            return {"success": True, "entries": [], "count": 0, "date": target_date}

        entries = []
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Most recent first, limit
        entries.reverse()
        entries = entries[:limit]

        return {
            "success": True,
            "entries": entries,
            "count": len(entries),
            "date": target_date,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AGENT AUTONOMY ENDPOINTS
# Added 2026-02-11 per Agent Ecosystem Audit (P0)
# ============================================================================


class AgentBacktestRequest(BaseModel):
    """Request model for agent-driven backtest execution."""

    symbol: str = Field("BTCUSDT", description="Trading pair (e.g. BTCUSDT)")
    interval: str = Field("15", description="Timeframe: 1, 5, 15, 30, 60, 240, D, W, M")
    strategy_type: str = Field(..., description="Strategy name (rsi, macd, sma_crossover, etc.)")
    strategy_params: dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")
    start_date: str = Field("2025-06-01", description="Start date YYYY-MM-DD")
    end_date: str = Field("2025-07-01", description="End date YYYY-MM-DD")
    initial_capital: float = Field(10000.0, ge=100, le=100_000_000, description="Starting capital USDT")
    leverage: float = Field(10.0, ge=1, le=125, description="Leverage multiplier")
    direction: str = Field("both", description="Trade direction: long, short, both")
    stop_loss: float | None = Field(None, ge=0.001, le=0.5, description="Stop loss fraction")
    take_profit: float | None = Field(None, ge=0.001, le=1.0, description="Take profit fraction")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "interval": "15",
                "strategy_type": "rsi",
                "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
                "start_date": "2025-06-01",
                "end_date": "2025-07-01",
                "initial_capital": 10000,
                "leverage": 10,
                "direction": "both",
            }
        }
    }


class AgentBacktestResponse(BaseModel):
    """Response model for agent backtest results."""

    success: bool
    status: str
    symbol: str
    strategy: str
    total_trades: int = 0
    win_rate: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    final_capital: float = 0.0
    profit_factor: float = 0.0
    engine: str = "FallbackEngineV4"
    commission_rate: float = 0.0007
    error: str | None = None


class AgentToolListResponse(BaseModel):
    """Response listing available agent tools."""

    total_tools: int
    categories: dict[str, int]
    tools: list[dict[str, Any]]


@router.post(
    "/actions/run-backtest",
    response_model=AgentBacktestResponse,
    summary="Agent-Driven Backtest Execution",
)
async def agent_run_backtest(request: AgentBacktestRequest) -> AgentBacktestResponse:
    """
    Execute a backtest via the agent MCP tool pipeline.

    This endpoint is designed for AI agents to programmatically trigger
    backtests with full parameter control. Uses FallbackEngineV4 engine
    and commission=0.0007 (TradingView parity).

    - **symbol**: Trading pair
    - **strategy_type**: Strategy name
    - **strategy_params**: Strategy-specific parameters
    """
    try:
        from backend.agents.mcp.trading_tools import run_backtest

        result = await run_backtest(
            symbol=request.symbol,
            interval=request.interval,
            strategy_type=request.strategy_type,
            strategy_params=request.strategy_params,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            direction=request.direction,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
        )

        if "error" in result:
            return AgentBacktestResponse(
                success=False,
                status="error",
                symbol=request.symbol,
                strategy=request.strategy_type,
                error=result["error"],
            )

        return AgentBacktestResponse(
            success=True,
            status=result.get("status", "completed"),
            symbol=result.get("symbol", request.symbol),
            strategy=result.get("strategy", request.strategy_type),
            total_trades=result.get("total_trades", 0),
            win_rate=result.get("win_rate", 0.0),
            total_return_pct=result.get("total_return_pct", 0.0),
            sharpe_ratio=result.get("sharpe_ratio", 0.0),
            max_drawdown_pct=result.get("max_drawdown_pct", 0.0),
            final_capital=result.get("final_capital", 0.0),
            profit_factor=result.get("profit_factor", 0.0),
            engine=result.get("engine", "FallbackEngineV4"),
            commission_rate=result.get("commission_rate", 0.0007),
        )

    except Exception as e:
        logger.error(f"Agent backtest failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent backtest failed: {e!s}")


@router.get(
    "/actions/backtest-history",
    summary="Agent Backtest History",
)
async def agent_backtest_history(limit: int = 10) -> dict[str, Any]:
    """
    Retrieve recent backtest results for agent analysis.

    - **limit**: Number of recent backtests to return (max 50)

    Returns a list of recent backtests with their key metrics.
    """
    try:
        from backend.agents.mcp.trading_tools import get_backtest_metrics

        result = await get_backtest_metrics(backtest_id=None, limit=min(limit, 50))

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching backtest history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch backtest history: {e!s}")


@router.get(
    "/actions/strategies",
    summary="List Available Strategies",
)
async def agent_list_strategies() -> dict[str, Any]:
    """
    List all available backtesting strategies with their default parameters.

    Returns strategy names, descriptions, and default parameter sets.
    """
    try:
        from backend.agents.mcp.trading_tools import list_strategies

        result = await list_strategies()

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing strategies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list strategies: {e!s}")


@router.post(
    "/actions/validate-strategy",
    summary="Validate Strategy Parameters",
)
async def agent_validate_strategy(
    strategy_type: str,
    strategy_params: dict[str, Any] | None = None,
    leverage: float = 1.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> dict[str, Any]:
    """
    Validate strategy parameters and risk settings before running a backtest.

    Returns validation results with errors, warnings, and suggested fixes.
    """
    try:
        from backend.agents.mcp.trading_tools import validate_strategy

        result = await validate_strategy(
            strategy_type=strategy_type,
            strategy_params=strategy_params or {},
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        return {"success": True, **result}

    except Exception as e:
        logger.error(f"Error validating strategy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to validate strategy: {e!s}")


@router.get(
    "/actions/system-health",
    summary="Agent System Health Check",
)
async def agent_system_health() -> dict[str, Any]:
    """
    Check system health for agent operations.

    Verifies database, disk, memory, and data availability.
    """
    try:
        from backend.agents.mcp.trading_tools import check_system_health

        result = await check_system_health()

        return {"success": True, **result}

    except Exception as e:
        logger.error(f"Error checking system health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check system health: {e!s}")


@router.get(
    "/actions/tools",
    response_model=AgentToolListResponse,
    summary="List Available Agent Tools",
)
async def agent_list_tools() -> AgentToolListResponse:
    """
    List all registered MCP tools available to agents.

    Returns tool names, descriptions, categories, and parameter info.
    """
    try:
        from backend.agents.mcp.tool_registry import registry

        all_tools = registry.list_tools()
        categories: dict[str, int] = {}

        tools_list = []
        for tool in all_tools:
            cat = getattr(tool, "category", "uncategorized")
            categories[cat] = categories.get(cat, 0) + 1
            tools_list.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "category": cat,
                    "parameters": [
                        {"name": p.name, "type": str(p.type), "required": p.required}
                        for p in getattr(tool, "parameters", [])
                    ],
                }
            )

        return AgentToolListResponse(
            total_tools=len(tools_list),
            categories=categories,
            tools=tools_list,
        )

    except Exception as e:
        logger.error(f"Error listing tools: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {e!s}")
