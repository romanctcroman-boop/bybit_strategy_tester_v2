"""
AI Agents Router
Endpoints for interacting with AI agents (DeepSeek and Perplexity).
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.circuit_breaker_manager import CircuitBreakerManager
from backend.agents.unified_agent_interface import UnifiedAgentInterface

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize global instances
_agent_interface: Optional[UnifiedAgentInterface] = None
_circuit_breaker_manager: Optional[CircuitBreakerManager] = None


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
    model: Optional[str] = Field(None, description="Specific model to use (optional)")
    temperature: Optional[float] = Field(
        0.7, ge=0.0, le=2.0, description="Temperature for response generation"
    )
    max_tokens: Optional[int] = Field(
        2000, ge=1, le=32000, description="Maximum tokens in response"
    )

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
    tokens_used: Optional[int] = Field(
        None, description="Number of tokens used (if available)"
    )
    latency_ms: Optional[float] = Field(
        None, description="Response latency in milliseconds"
    )
    api_key_id: Optional[str] = Field(
        None, description="API key ID used (for debugging)"
    )
    from_cache: Optional[bool] = Field(
        False, description="Whether the response came from cache"
    )

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

    deepseek: Dict[str, Any] = Field(..., description="DeepSeek agent statistics")
    perplexity: Dict[str, Any] = Field(..., description="Perplexity agent statistics")
    circuit_breakers: Dict[str, Any] = Field(..., description="Circuit breaker status")

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
        raise HTTPException(
            status_code=500, detail=f"Failed to get agent stats: {str(e)}"
        )


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
        raise HTTPException(
            status_code=500, detail=f"Failed to query DeepSeek: {str(e)}"
        )


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
        raise HTTPException(
            status_code=500, detail=f"Failed to query Perplexity: {str(e)}"
        )


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
        raise HTTPException(status_code=500, detail=f"All agents failed: {str(e)}")


@router.get("/cache/stats", response_model=Dict[str, Any])
async def get_cache_stats() -> Dict[str, Any]:
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
        raise HTTPException(
            status_code=500, detail=f"Failed to get cache stats: {str(e)}"
        )


@router.post("/cache/clear")
async def clear_cache() -> Dict[str, Any]:
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
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


# ============================================================================
# ML + AI INTEGRATION ENDPOINTS
# ============================================================================


class FeatureSuggestionRequest(BaseModel):
    """Request for AI feature suggestions"""

    objective: str = Field(..., description="What to predict (e.g., 'price direction')")
    asset: str = Field("BTC/USDT", description="Trading pair")
    timeframe: str = Field("1h", description="Candle timeframe")
    max_features: int = Field(
        10, ge=1, le=50, description="Maximum features to suggest"
    )


class FeatureCodeRequest(BaseModel):
    """Request for feature code generation"""

    feature_name: str = Field(..., description="Indicator name (e.g., 'RSI')")
    parameters: Dict[str, Any] = Field(..., description="Indicator parameters")
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
        raise HTTPException(
            status_code=500, detail=f"Failed to suggest features: {str(e)}"
        )


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
        raise HTTPException(
            status_code=500, detail=f"Failed to generate code: {str(e)}"
        )


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
        raise HTTPException(
            status_code=500, detail=f"Failed to design strategy: {str(e)}"
        )


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
    num_variations: int = Field(
        1, ge=1, le=5, description="Number of strategy variations"
    )


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
        raise HTTPException(
            status_code=500, detail=f"Failed to generate strategy: {str(e)}"
        )


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
        raise HTTPException(
            status_code=500, detail=f"Failed to execute backtest series: {str(e)}"
        )


@router.post("/backtest/ai-analyze", summary="AI Analyze Backtest Results")
async def analyze_backtest_results_endpoint(results: List[Dict[str, Any]] = []):
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
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze results: {str(e)}"
        )
