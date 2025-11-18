"""
AI Analysis Router - Perplexity AI integration via MCP Server
Provides AI-powered analysis of backtest results, optimization suggestions, and insights
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import httpx
import os
import logging

# Import secure key manager
from backend.security.key_manager import get_decrypted_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Analysis"])

# Perplexity API configuration (secure)
PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


class BacktestAnalysisRequest(BaseModel):
    """Request model for backtest analysis"""
    context: Dict[str, Any] = Field(..., description="Backtest context and metrics")
    query: str = Field(..., description="Analysis query for Perplexity AI")
    model: Optional[str] = Field("sonar", description="Perplexity model to use")


class AIAnalysisResponse(BaseModel):
    """Response model for AI analysis"""
    analysis: str = Field(..., description="AI-generated analysis")
    model: str = Field(..., description="Model used for analysis")
    tokens: Optional[int] = Field(None, description="Tokens used")


@router.post("/analyze-backtest", response_model=AIAnalysisResponse)
async def analyze_backtest(
    request: BacktestAnalysisRequest = Body(...)
) -> AIAnalysisResponse:
    """
    Analyze backtest results using Perplexity AI
    
    This endpoint sends backtest context and metrics to Perplexity AI
    and returns detailed analysis, insights, and recommendations.
    
    Args:
        request: Analysis request with context and query
        
    Returns:
        AI-generated analysis and recommendations
        
    Raises:
        HTTPException: If Perplexity API is unavailable or returns an error
    """
    if not PERPLEXITY_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Perplexity API key not configured. Set PERPLEXITY_API_KEY environment variable."
        )
    
    try:
        # Prepare request for Perplexity API
        payload = {
            "model": request.model or "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты эксперт по анализу торговых стратегий и алгоритмическому трейдингу. "
                        "Анализируй результаты бэктестов, выявляй сильные и слабые стороны, "
                        "предлагай конкретные рекомендации по оптимизации. "
                        "Используй профессиональную терминологию и давай структурированные ответы."
                    )
                },
                {
                    "role": "user",
                    "content": request.query
                }
            ],
            "max_tokens": 1500,
            "temperature": 0.2,  # Low temperature for consistent analysis
            "top_p": 0.9,
        }
        
        # Call Perplexity API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload
            )
            
            response.raise_for_status()
            data = response.json()
        
        # Extract analysis from response
        if "choices" not in data or len(data["choices"]) == 0:
            raise HTTPException(
                status_code=500,
                detail="Invalid response from Perplexity API"
            )
        
        analysis_text = data["choices"][0]["message"]["content"]
        tokens_used = data.get("usage", {}).get("total_tokens")
        
        logger.info(
            f"AI analysis completed for backtest {request.context.get('backtest_id')}, "
            f"tokens used: {tokens_used}"
        )
        
        return AIAnalysisResponse(
            analysis=analysis_text,
            model=request.model or "sonar",
            tokens=tokens_used
        )
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Perplexity API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Perplexity API error: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Request error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Perplexity API: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in AI analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during AI analysis: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Check AI analysis service health
    
    Returns status of Perplexity API configuration
    """
    return {
        "status": "ok" if PERPLEXITY_API_KEY else "degraded",
        "perplexity_configured": bool(PERPLEXITY_API_KEY),
        "message": "AI analysis service is operational" if PERPLEXITY_API_KEY 
                   else "Perplexity API key not configured"
    }
