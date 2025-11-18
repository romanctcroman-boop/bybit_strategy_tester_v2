"""
Dashboard API endpoints for real-time trading metrics.

Provides mock data when backend services are unavailable.
"""
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/dashboard/kpi")
async def get_dashboard_kpi() -> Dict:
    """
    Get Key Performance Indicators for trading dashboard.
    
    Returns:
        Dict with totalPnL, winRate, activeBots, sharpeRatio (camelCase for frontend)
    """
    # Mock data for now - will be replaced with real metrics from orchestrator
    return {
        "totalPnL": 12450.75,  # ✅ Fixed: camelCase with capital L
        "totalTrades": 247,
        "winRate": 62.50,
        "activeBots": 3,
        "sharpeRatio": 1.85,
        "avgTradeReturn": 2.3,  # ✅ Added: frontend expects this field
        "timestamp": datetime.now().isoformat()
    }


@router.get("/api/dashboard/activity")
async def get_recent_activity() -> List[Dict]:
    """
    Get recent trading activity feed.
    
    Returns:
        List of recent activity items (backtests, optimizations, bot starts)
    """
    # Mock recent activity data
    now = datetime.now()
    
    activities = [
        {
            "id": 1,
            "type": "backtest_completed",
            "title": "Backtest completed",
            "description": "SR Mean Reversion (5m)",
            "timestamp": (now - timedelta(minutes=5)).isoformat(),
            "status": "success"
        },
        {
            "id": 2,
            "type": "optimization_running",
            "title": "Optimization running",
            "description": "CatBoost optimizer",
            "timestamp": (now - timedelta(minutes=15)).isoformat(),
            "status": "running"
        },
        {
            "id": 3,
            "type": "bot_started",
            "title": "Bot started",
            "description": "EMA Crossover",
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "status": "success"
        }
    ]
    
    return activities


@router.get("/api/dashboard/stats")
async def get_dashboard_stats() -> Dict:
    """
    Get detailed dashboard statistics.
    
    Returns:
        Dict with performance metrics, equity curve data, etc.
    """
    return {
        "performance": {
            "totalReturn": 24.5,
            "monthlyReturn": 3.2,
            "maxDrawdown": -8.3,
            "winningDays": 18,
            "losingDays": 7
        },
        "portfolio": {
            "totalValue": 112450.75,
            "cash": 45200.00,
            "positions": 67250.75
        },
        "timestamp": datetime.now().isoformat()
    }
