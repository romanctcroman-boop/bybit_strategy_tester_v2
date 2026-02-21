"""
Advanced AI Agent Router

Extended endpoints for the AI Agent System:
- Multi-Agent Deliberation
- Hierarchical Memory
- Self-Improvement
- Monitoring & Observability
- MCP Tools
"""

import asyncio
import contextlib
import functools
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class DeliberationRequest(BaseModel):
    """Multi-agent deliberation request"""

    question: str = Field(..., description="Question for agents to deliberate on")
    agents: list[str] = Field(
        default=["deepseek", "perplexity"],
        description="List of agent IDs to participate",
    )
    max_rounds: int = Field(default=3, ge=1, le=10, description="Maximum deliberation rounds")
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence to reach consensus")
    voting_strategy: str = Field(
        default="weighted",
        description="Voting strategy: majority, weighted, unanimous, or ranked_choice",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "Should I use trailing stop or fixed stop loss for BTC?",
                "agents": ["deepseek", "perplexity"],
                "max_rounds": 3,
                "min_confidence": 0.7,
                "voting_strategy": "weighted",
            }
        }
    }


class DeliberationResponse(BaseModel):
    """Multi-agent deliberation response"""

    decision: str
    confidence: float
    rounds_used: int
    votes: dict[str, Any]
    evidence_chain: list[str]
    dissenting_views: list[str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "decision": "Use trailing stop for trending markets",
                "confidence": 0.85,
                "rounds_used": 2,
                "votes": {"deepseek": 0.9, "perplexity": 0.8},
                "evidence_chain": ["Evidence 1", "Evidence 2"],
                "dissenting_views": [],
            }
        }
    }


class MemoryStoreRequest(BaseModel):
    """Memory store request"""

    content: str = Field(..., description="Content to store")
    memory_type: str = Field(
        default="semantic",
        description="Memory type: working, episodic, semantic, or procedural",
    )
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="Importance score")
    tags: list[str] = Field(default=[], description="Tags for categorization")


class MemoryRecallRequest(BaseModel):
    """Memory recall request"""

    query: str = Field(..., description="Query to search for")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results")
    memory_types: list[str] | None = Field(default=None, description="Filter by memory types")


class SelfImprovementFeedbackRequest(BaseModel):
    """Feedback for self-improvement"""

    prompt: str = Field(..., description="Original prompt")
    response: str = Field(..., description="Agent response")
    feedback_type: str = Field(default="human", description="Feedback type: human or ai")
    score: float | None = Field(None, ge=0.0, le=1.0, description="Quality score (for human feedback)")
    reasoning: str | None = Field(None, description="Reasoning for the score")


class ToolCallRequest(BaseModel):
    """MCP tool call request"""

    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: dict[str, Any] = Field(default={}, description="Tool arguments")


# ============================================================================
# MULTI-AGENT DELIBERATION ENDPOINTS
# ============================================================================


@router.post("/deliberate", response_model=DeliberationResponse)
async def deliberate(request: DeliberationRequest) -> DeliberationResponse:
    """
    Run multi-agent deliberation on a question

    Multiple AI agents debate and reach consensus on a decision.
    Uses structured voting and evidence gathering.

    **Now uses REAL LLM APIs (DeepSeek, Perplexity)!**
    """
    try:
        from backend.agents.consensus.real_llm_deliberation import (
            VotingStrategy,
            get_real_deliberation,
        )

        deliberation = get_real_deliberation()

        # Map string to enum
        strategy_map = {
            "majority": VotingStrategy.MAJORITY,
            "weighted": VotingStrategy.WEIGHTED,
            "unanimous": VotingStrategy.UNANIMOUS,
            "ranked_choice": VotingStrategy.RANKED_CHOICE,
        }
        voting_strategy = strategy_map.get(request.voting_strategy, VotingStrategy.WEIGHTED)

        result = await deliberation.deliberate(
            question=request.question,
            agents=request.agents,
            max_rounds=request.max_rounds,
            min_confidence=request.min_confidence,
            voting_strategy=voting_strategy,
        )

        # Extract votes from final_votes
        votes = {}
        for vote in result.final_votes:
            votes[vote.agent_id] = vote.confidence

        # Extract dissenting views
        dissenting_views = [
            f"{vote.agent_id}: {vote.reasoning or vote.position}" for vote in result.dissenting_opinions
        ]

        # Extract evidence chain as strings
        evidence_chain = [e.get("evidence", str(e)) if isinstance(e, dict) else str(e) for e in result.evidence_chain]

        return DeliberationResponse(
            decision=result.decision,
            confidence=result.confidence,
            rounds_used=len(result.rounds),
            votes=votes,
            evidence_chain=evidence_chain,
            dissenting_views=dissenting_views,
        )

    except Exception as e:
        logger.error(f"Deliberation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/domain-agents")
async def list_domain_agents():
    """
    List available domain-specific agents

    Returns all registered domain agents with their capabilities.
    """
    try:
        from backend.agents.consensus.domain_agents import DomainAgentRegistry

        registry = DomainAgentRegistry()
        agent_names = registry.list_agents()

        return {
            "agents": [
                {
                    "id": name,
                    "type": "domain",
                    "specialty": name,
                    "capabilities": [],
                }
                for name in agent_names
            ],
            "total": len(agent_names),
        }

    except Exception as e:
        logger.error(f"Error listing domain agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# HIERARCHICAL MEMORY ENDPOINTS
# ============================================================================


@functools.lru_cache(maxsize=1)
def get_memory():
    """Get or create memory singleton (thread-safe via lru_cache)."""
    from backend.agents.memory.hierarchical_memory import HierarchicalMemory

    return HierarchicalMemory()


@router.post("/memory/store")
async def store_memory(request: MemoryStoreRequest):
    """
    Store content in hierarchical memory

    Stores content in the appropriate memory tier based on type.
    """
    try:
        from backend.agents.memory.hierarchical_memory import MemoryType

        memory = get_memory()

        # Map string to enum
        type_map = {
            "working": MemoryType.WORKING,
            "episodic": MemoryType.EPISODIC,
            "semantic": MemoryType.SEMANTIC,
            "procedural": MemoryType.PROCEDURAL,
        }
        memory_type = type_map.get(request.memory_type, MemoryType.SEMANTIC)

        memory_id = await memory.store(
            content=request.content,
            memory_type=memory_type,
            importance=request.importance,
            tags=request.tags,
        )

        return {
            "success": True,
            "memory_id": memory_id,
            "memory_type": request.memory_type,
        }

    except Exception as e:
        logger.error(f"Memory store error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/memory/recall")
async def recall_memory(request: MemoryRecallRequest):
    """
    Recall memories by semantic search

    Uses vector similarity to find relevant memories.
    """
    try:
        memory = get_memory()

        results = await memory.recall(
            query=request.query,
            top_k=request.top_k,
            memory_types=request.memory_types,
        )

        return {
            "results": [
                {
                    "id": r.id,
                    "content": r.content,
                    "memory_type": r.memory_type.value if hasattr(r.memory_type, "value") else str(r.memory_type),
                    "importance": r.importance,
                    "similarity": getattr(r, "similarity", None),
                }
                for r in results
            ],
            "total": len(results),
        }

    except Exception as e:
        logger.error(f"Memory recall error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/memory/stats")
async def get_memory_stats():
    """Get memory system statistics"""
    try:
        memory = get_memory()
        stats = memory.get_stats()

        return stats

    except Exception as e:
        logger.error(f"Memory stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/memory/consolidate")
async def consolidate_memory():
    """
    Run memory consolidation

    Moves important short-term memories to long-term storage.
    """
    try:
        memory = get_memory()
        consolidated = await memory.consolidate()

        return {
            "success": True,
            "consolidated_count": consolidated,
        }

    except Exception as e:
        logger.error(f"Memory consolidation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# SELF-IMPROVEMENT ENDPOINTS
# ============================================================================


@router.post("/improvement/feedback")
async def submit_feedback(request: SelfImprovementFeedbackRequest):
    """
    Submit feedback for self-improvement

    Collects human or AI feedback for RLHF training.
    """
    try:
        from backend.agents.self_improvement.rlhf_module import RLHFModule

        rlhf = RLHFModule()

        if request.feedback_type == "human":
            await rlhf.collect_human_feedback(
                prompt=request.prompt,
                response_a=request.response,
                response_b="",  # Single response feedback
                preference=1,  # Response A only
                reasoning=request.reasoning,
            )
        else:
            await rlhf.collect_ai_feedback(
                prompt=request.prompt,
                responses=[request.response],
            )

        return {
            "success": True,
            "feedback_type": request.feedback_type,
            "total_feedback": rlhf.stats.get("total_feedback", 0),
        }

    except Exception as e:
        logger.error(f"Feedback error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/improvement/evaluate")
async def evaluate_response(request: SelfImprovementFeedbackRequest):
    """
    Evaluate response quality

    Uses multiple criteria to score response quality.
    """
    try:
        from backend.agents.self_improvement.rlhf_module import RLHFModule

        rlhf = RLHFModule()

        evaluation = await rlhf.self_evaluate(
            prompt=request.prompt,
            response=request.response,
        )

        return {
            "overall_score": evaluation.overall,
            "accuracy_score": evaluation.accuracy,
            "helpfulness_score": evaluation.helpfulness,
            "safety_score": evaluation.safety,
            "coherence_score": evaluation.clarity,
            "feedback": "",
        }

    except Exception as e:
        logger.error(f"Evaluation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/improvement/stats")
async def get_improvement_stats():
    """Get self-improvement statistics"""
    try:
        from backend.agents.self_improvement.performance_evaluator import (
            PerformanceEvaluator,
        )

        evaluator = PerformanceEvaluator()
        stats = evaluator.get_stats()

        return stats

    except Exception as e:
        logger.error(f"Improvement stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# MCP TOOLS ENDPOINTS
# ============================================================================


@router.get("/mcp/tools")
async def list_mcp_tools():
    """List available MCP tools"""
    try:
        from backend.agents.mcp.tool_registry import get_tool_registry

        registry = get_tool_registry()
        tools = registry.list_tools()

        return {
            "tools": [tool.to_dict() for tool in tools],
            "total": len(tools),
            "categories": registry.list_categories(),
        }

    except Exception as e:
        logger.error(f"MCP tools error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/mcp/tools/call")
async def call_mcp_tool(request: ToolCallRequest):
    """Call an MCP tool"""
    try:
        from backend.agents.mcp.tool_registry import get_tool_registry

        registry = get_tool_registry()
        result = await registry.execute(request.tool_name, **request.arguments)

        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
        }

    except Exception as e:
        logger.error(f"MCP tool call error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/mcp/resources")
async def list_mcp_resources():
    """List available MCP resources"""
    try:
        from backend.agents.mcp.resource_manager import get_resource_manager

        manager = get_resource_manager()
        resources = await manager.list_resources()

        return {
            "resources": [r.to_dict() for r in resources],
            "total": len(resources),
        }

    except Exception as e:
        logger.error(f"MCP resources error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================


@router.get("/monitoring/metrics")
async def get_agent_metrics():
    """Get AI agent monitoring metrics"""
    try:
        from backend.agents.monitoring.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        return {
            "stats": collector.get_stats(),
            "prometheus": collector.export_prometheus(),
        }

    except Exception as e:
        logger.error(f"Metrics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/monitoring/traces")
async def get_agent_traces(limit: int = 50):
    """Get recent trace spans"""
    try:
        from backend.agents.monitoring.tracing import DistributedTracer

        tracer = DistributedTracer()
        traces = tracer.get_recent_traces(limit=limit)

        return {
            "traces": [trace.to_dict() for trace in traces],
            "total": len(traces),
        }

    except Exception as e:
        logger.error(f"Traces error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/monitoring/alerts")
async def get_agent_alerts():
    """Get active alerts"""
    try:
        from backend.agents.monitoring.alerting import AlertManager

        manager = AlertManager()
        alerts = manager.get_active_alerts()

        return {
            "alerts": [alert.to_dict() for alert in alerts],
            "total": len(alerts),
        }

    except Exception as e:
        logger.error(f"Alerts error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/monitoring/anomalies")
async def get_detected_anomalies(metric_name: str | None = None, limit: int = 100):
    """Get detected anomalies"""
    try:
        from backend.agents.monitoring.ml_anomaly import get_anomaly_detector

        detector = get_anomaly_detector()

        if metric_name:
            anomalies = detector.get_anomaly_history(metric_name, limit)
        else:
            anomalies = []
            for name in detector._anomaly_history:
                anomalies.extend(detector.get_anomaly_history(name, limit // 10))

        return {
            "anomalies": [a.to_dict() for a in anomalies[-limit:]],
            "total": len(anomalies),
        }

    except Exception as e:
        logger.error(f"Anomalies error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# SYSTEM OVERVIEW
# ============================================================================


@router.get("/system/overview")
async def get_system_overview():
    """Get complete AI agent system overview"""
    try:
        # Collect stats from all subsystems
        components: dict[str, Any] = {}

        # Memory stats
        try:
            memory = get_memory()
            components["memory"] = memory.get_stats()
        except Exception:
            components["memory"] = {"status": "unavailable"}

        # Self-improvement stats
        try:
            from backend.agents.self_improvement.performance_evaluator import (
                PerformanceEvaluator,
            )

            evaluator = PerformanceEvaluator()
            components["self_improvement"] = evaluator.get_stats()
        except Exception:
            components["self_improvement"] = {"status": "unavailable"}

        # MCP stats
        try:
            from backend.agents.mcp.tool_registry import get_tool_registry

            registry = get_tool_registry()
            components["mcp"] = registry.get_stats()
        except Exception:
            components["mcp"] = {"status": "unavailable"}

        # Monitoring stats
        try:
            from backend.agents.monitoring.metrics_collector import MetricsCollector

            collector = MetricsCollector()
            components["monitoring"] = collector.get_stats()
        except Exception:
            components["monitoring"] = {"status": "unavailable"}

        return {
            "status": "operational",
            "components": components,
        }

    except Exception as e:
        logger.error(f"System overview error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# AI-BACKTEST INTEGRATION ENDPOINTS
# ============================================================================


class BacktestAnalysisRequest(BaseModel):
    """Request for AI backtest analysis"""

    metrics: dict[str, Any] = Field(..., description="Backtest metrics")
    strategy_name: str = Field(..., description="Strategy name")
    symbol: str = Field(default="BTCUSDT", description="Trading symbol")
    timeframe: str = Field(default="1h", description="Chart timeframe")
    period: str = Field(default="Unknown", description="Backtest period")
    agents: list[str] = Field(default=["deepseek"], description="AI agents to use")

    model_config = {
        "json_schema_extra": {
            "example": {
                "metrics": {
                    "net_pnl": 15000,
                    "total_return_pct": 25.5,
                    "sharpe_ratio": 1.8,
                    "max_drawdown_pct": 12.5,
                    "win_rate": 0.58,
                    "profit_factor": 1.65,
                    "total_trades": 145,
                },
                "strategy_name": "Momentum RSI",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "period": "2024-01-01 to 2024-12-31",
            }
        }
    }


class OptimizationAnalysisRequest(BaseModel):
    """Request for AI optimization analysis"""

    best_params: dict[str, Any] = Field(..., description="Best parameters found")
    best_sharpe: float = Field(..., description="Best Sharpe ratio")
    best_return: float = Field(..., description="Best return percentage")
    total_trials: int = Field(..., description="Total optimization trials")
    convergence_score: float = Field(default=0.8, description="Convergence score 0-1")
    param_ranges: dict[str, Any] = Field(..., description="Parameter search ranges")
    strategy_name: str = Field(..., description="Strategy name")
    symbol: str = Field(default="BTCUSDT", description="Trading symbol")
    method: str = Field(default="Bayesian", description="Optimization method")


@router.post("/analyze-backtest")
async def analyze_backtest_with_ai(request: BacktestAnalysisRequest):
    """
    Analyze backtest results with AI.

    Uses real LLM to provide:
    - Performance summary
    - Risk assessment
    - Overfitting detection
    - Actionable recommendations
    - Market regime fit analysis
    """
    try:
        from backend.agents.integration.ai_backtest_integration import (
            get_backtest_analyzer,
        )

        analyzer = get_backtest_analyzer()

        result = await analyzer.analyze_backtest(
            metrics=request.metrics,
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            period=request.period,
            agents=request.agents,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Backtest analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/analyze-optimization")
async def analyze_optimization_with_ai(request: OptimizationAnalysisRequest):
    """
    Analyze optimization results with AI.

    Uses real LLM to provide:
    - Parameter selection rationale
    - Robustness assessment
    - Overfitting warnings
    - Suggested adjustments for live trading
    """
    try:
        from backend.agents.integration.ai_backtest_integration import (
            get_optimization_analyzer,
        )

        analyzer = get_optimization_analyzer()

        result = await analyzer.analyze_optimization(
            best_params=request.best_params,
            best_sharpe=request.best_sharpe,
            best_return=request.best_return,
            total_trials=request.total_trials,
            convergence_score=request.convergence_score,
            param_ranges=request.param_ranges,
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            method=request.method,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Optimization analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# KEY VALIDATION & AGENT HEALTH ENDPOINTS
# ============================================================================


@router.get("/keys/preflight")
async def preflight_key_validation():
    """
    Run pre-flight validation of all API keys.

    Sends minimal requests to each provider to verify keys are valid.
    Returns per-provider status: valid/invalid/unknown.
    """
    try:
        from backend.agents.api_key_pool import APIKeyPoolManager

        pool = APIKeyPoolManager()
        results = await pool.validate_keys_preflight()

        return {
            "success": True,
            "providers": results,
            "all_valid": all(r.get("valid") is True for r in results.values()),
            "summary": {
                "total": len(results),
                "valid": sum(1 for r in results.values() if r.get("valid") is True),
                "invalid": sum(1 for r in results.values() if r.get("valid") is False),
                "unknown": sum(1 for r in results.values() if r.get("valid") is None),
            },
        }

    except Exception as e:
        logger.error(f"Pre-flight validation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/keys/pool-metrics")
async def get_key_pool_metrics():
    """
    Get key pool health metrics for all providers.

    Shows pool size, healthy/cooling/disabled counts per provider.
    """
    try:
        from backend.agents.api_key_pool import APIKeyPoolManager
        from backend.agents.models import AgentType

        pool = APIKeyPoolManager()
        metrics = {}
        for agent_type in [AgentType.DEEPSEEK, AgentType.PERPLEXITY, AgentType.QWEN]:
            metrics[agent_type.value] = pool.get_pool_metrics(agent_type)

        return {"success": True, "providers": metrics}

    except Exception as e:
        logger.error(f"Pool metrics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# AGENT ACCURACY & DELIBERATION AUDIT
# ============================================================================


@router.get("/deliberation/accuracy")
async def get_agent_accuracy():
    """
    Get adaptive accuracy weights for all agents.

    Shows historical accuracy and current voting weight per agent.
    Weights are used in weighted deliberation voting.
    """
    try:
        from backend.agents.consensus.real_llm_deliberation import (
            get_real_deliberation,
        )

        deliberation = get_real_deliberation()
        report = deliberation.get_agent_accuracy_report()
        stats = deliberation.get_stats()

        return {
            "success": True,
            "accuracy": report,
            "deliberation_stats": stats,
        }

    except Exception as e:
        logger.error(f"Agent accuracy error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/deliberation/audit-log")
async def get_deliberation_audit_log(last_n: int = 50):
    """
    Get decision chain audit log from deliberation system.

    Provides full traceability of intermediate deliberation steps:
    start, round completions, voting details, outcome recordings.
    """
    try:
        from backend.agents.consensus.real_llm_deliberation import (
            get_real_deliberation,
        )

        deliberation = get_real_deliberation()
        log = deliberation.get_audit_log(last_n=last_n)

        return {
            "success": True,
            "entries": log,
            "total": len(deliberation.audit_log),
            "returned": len(log),
        }

    except Exception as e:
        logger.error(f"Audit log error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/deliberation/history")
async def get_deliberation_history(limit: int = 20):
    """
    Get recent deliberation results.

    Returns decision, confidence, agents involved, and duration
    for each recent deliberation.
    """
    try:
        from backend.agents.consensus.real_llm_deliberation import (
            get_real_deliberation,
        )

        deliberation = get_real_deliberation()
        history = deliberation.deliberation_history[-limit:]

        return {
            "success": True,
            "deliberations": [
                {
                    "id": d.id,
                    "question": d.question[:200],
                    "decision": d.decision[:200],
                    "confidence": d.confidence,
                    "voting_strategy": d.voting_strategy.value,
                    "rounds": len(d.rounds),
                    "agents": d.metadata.get("agents", []),
                    "duration_seconds": round(d.duration_seconds, 2),
                    "timestamp": d.timestamp.isoformat(),
                    "dissenting_count": len(d.dissenting_opinions),
                }
                for d in reversed(history)
            ],
            "total": len(deliberation.deliberation_history),
        }

    except Exception as e:
        logger.error(f"Deliberation history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# STRATEGY BUILDER — AI Agent Integration
# ============================================================================


class BuilderTaskRequest(BaseModel):
    """Request for AI agent to build a strategy through the Strategy Builder."""

    name: str = Field(default="Agent Strategy", description="Strategy name")
    symbol: str = Field(default="BTCUSDT", description="Trading pair")
    timeframe: str = Field(default="15", description="Candle timeframe (1,5,15,30,60,240,D,W,M)")
    direction: str = Field(default="both", description="Trade direction (long/short/both)")
    initial_capital: float = Field(default=10000.0, description="Starting capital")
    leverage: float = Field(default=10.0, description="Leverage multiplier")
    start_date: str = Field(default="2025-01-01", description="Backtest start date")
    end_date: str = Field(default="2025-06-01", description="Backtest end date")
    blocks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Blocks to add: [{type, params, id, name}]",
    )
    connections: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Connections: [{source, source_port, target, target_port}]",
    )
    stop_loss: float | None = Field(default=None, description="Stop loss fraction")
    take_profit: float | None = Field(default=None, description="Take profit fraction")
    max_iterations: int = Field(default=3, description="Max iteration attempts")
    min_sharpe: float = Field(default=0.5, description="Minimum acceptable Sharpe ratio")
    min_win_rate: float = Field(default=0.4, description="Minimum acceptable win rate")
    enable_deliberation: bool = Field(
        default=False,
        description="Use AI multi-agent deliberation (DeepSeek+Perplexity) for planning",
    )
    existing_strategy_id: str | None = Field(
        default=None,
        description="Existing strategy ID to optimize (skip create/blocks/connect stages)",
    )


@router.post("/builder/task")
async def run_builder_task(request: BuilderTaskRequest):
    """
    Run a full Strategy Builder workflow — create strategy, add blocks,
    connect them, validate, generate code, and backtest.

    The agent uses the SAME API endpoints as the frontend UI,
    so all actions are visible to the user in real-time.
    """
    try:
        from backend.agents.workflows.builder_workflow import (
            BuilderWorkflow,
            BuilderWorkflowConfig,
        )

        config = BuilderWorkflowConfig(
            name=request.name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            direction=request.direction,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            start_date=request.start_date,
            end_date=request.end_date,
            commission=0.0007,  # NEVER change — TradingView parity
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            blocks=request.blocks,
            connections=request.connections,
            max_iterations=request.max_iterations,
            min_acceptable_sharpe=request.min_sharpe,
            min_acceptable_win_rate=request.min_win_rate,
            enable_deliberation=request.enable_deliberation,
            existing_strategy_id=request.existing_strategy_id,
        )

        workflow = BuilderWorkflow()
        result = await workflow.run(config)

        return {
            "success": result.status.value == "completed",
            "workflow": result.to_dict(),
        }

    except Exception as e:
        logger.error(f"Builder task error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------


def _sse_event(event: str, data: Any) -> str:
    """Format a single Server-Sent Events frame."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def _builder_sse_stream(request: "BuilderTaskRequest") -> AsyncIterator[str]:
    """Yield SSE events as the BuilderWorkflow progresses through stages.

    Strategy:
    - Monkey-patch ``BuilderWorkflow._result`` status writes via a thin
      wrapper so each stage change emits a ``stage`` SSE event.
    - Emit a ``progress`` event every ~2 s during long-running stages.
    - Emit ``result`` on completion or ``error`` on failure.
    """
    from backend.agents.workflows.builder_workflow import (
        BuilderStage,
        BuilderWorkflow,
        BuilderWorkflowConfig,
    )

    config = BuilderWorkflowConfig(
        name=request.name,
        symbol=request.symbol,
        timeframe=request.timeframe,
        direction=request.direction,
        initial_capital=request.initial_capital,
        leverage=request.leverage,
        start_date=request.start_date,
        end_date=request.end_date,
        commission=0.0007,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        blocks=request.blocks,
        connections=request.connections,
        max_iterations=request.max_iterations,
        min_acceptable_sharpe=request.min_sharpe,
        min_acceptable_win_rate=request.min_win_rate,
        enable_deliberation=request.enable_deliberation,
        existing_strategy_id=request.existing_strategy_id,
    )

    _stage_labels: dict[str, str] = {
        BuilderStage.PLANNING: "🔍 Planning strategy…",
        BuilderStage.CREATING: "🏗️ Creating strategy canvas…",
        BuilderStage.ADDING_BLOCKS: "🧩 Adding indicator blocks…",
        BuilderStage.CONNECTING: "🔗 Connecting blocks…",
        BuilderStage.VALIDATING: "✅ Validating strategy…",
        BuilderStage.GENERATING_CODE: "💾 Generating Python code…",
        BuilderStage.BACKTESTING: "📊 Running backtest…",
        BuilderStage.EVALUATING: "📈 Evaluating results…",
        BuilderStage.ITERATING: "🔄 Optimizing parameters…",
        BuilderStage.COMPLETED: "🎉 Done!",
        BuilderStage.FAILED: "❌ Failed",
    }

    # Queue for inter-task communication
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    # P1 fix: callback on the instance — no class-level monkey-patch, safe for concurrent requests
    def _stage_cb(stage: BuilderStage) -> None:
        queue.put_nowait({"type": "stage", "stage": stage.value, "label": _stage_labels.get(stage, stage.value)})

    workflow = BuilderWorkflow(on_stage_change=_stage_cb)

    # Run workflow in background task
    async def _run() -> None:
        try:
            result = await workflow.run(config)
            queue.put_nowait({"type": "done", "result": result.to_dict()})
        except Exception as exc:
            queue.put_nowait({"type": "error", "message": str(exc)})

    task = asyncio.create_task(_run())

    try:
        # Yield SSE events from the queue
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=2.0)
            except TimeoutError:
                # Heartbeat — keep connection alive
                current_stage = workflow._result.status.value if workflow._result else "running"
                yield _sse_event("heartbeat", {"stage": current_stage})
                continue

            if msg["type"] == "stage":
                yield _sse_event("stage", {"stage": msg["stage"], "label": msg["label"]})

            elif msg["type"] == "done":
                yield _sse_event(
                    "result",
                    {
                        "success": msg["result"].get("status") == "completed",
                        "workflow": msg["result"],
                    },
                )
                break

            elif msg["type"] == "error":
                yield _sse_event("error", {"message": msg["message"]})
                break

    finally:
        # P2 fix: await task cancellation instead of fire-and-forget
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.shield(asyncio.gather(task, return_exceptions=True))


@router.post("/builder/task/stream")
async def run_builder_task_stream(request: BuilderTaskRequest) -> StreamingResponse:
    """
    Run a full Strategy Builder workflow with Server-Sent Events (SSE) progress.

    Same as ``POST /builder/task`` but streams real-time stage updates:

    - ``stage``     — workflow stage changed (planning/backtesting/…)
    - ``heartbeat`` — keepalive every 2 s while waiting
    - ``result``    — final workflow result (mirrors /builder/task response)
    - ``error``     — fatal error

    JavaScript usage::

        const source = new EventSource('/api/v1/agents/advanced/builder/task/stream', {
            method: 'POST'  // requires fetch-event-source polyfill
        });

    Or use ``fetch`` with ``text/event-stream`` content-type — see JS implementation
    in ``strategy_builder.js``.
    """
    return StreamingResponse(
        _builder_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


@router.get("/builder/block-library")
async def get_builder_block_library():
    """
    Get the Strategy Builder block library — all available blocks
    that agents can use to build strategies.
    """
    try:
        from backend.agents.mcp.tools.strategy_builder import builder_get_block_library

        library = await builder_get_block_library()
        return {"success": True, "library": library}

    except Exception as e:
        logger.error(f"Block library error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/builder/strategies")
async def list_builder_strategies(page: int = 1, page_size: int = 20):
    """List all strategies in the Strategy Builder."""
    try:
        from backend.agents.mcp.tools.strategy_builder import builder_list_strategies

        strategies = await builder_list_strategies(page=page, page_size=page_size)
        return {"success": True, "data": strategies}

    except Exception as e:
        logger.error(f"List strategies error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
