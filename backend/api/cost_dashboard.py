# -*- coding: utf-8 -*-
"""
Cost Dashboard API

Endpoints for viewing and managing API cost tracking.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.monitoring.cost_tracker import get_cost_tracker

router = APIRouter(prefix="/api/v1/costs", tags=["Cost Dashboard"])


class CostSummaryResponse(BaseModel):
    """Cost summary response model"""

    total_cost_usd: float
    total_tokens: int
    total_requests: int
    by_agent: dict[str, float]
    period_start: str
    period_end: str


class DailyBreakdownItem(BaseModel):
    """Daily cost breakdown item"""

    date: str
    total_cost: float
    requests: int
    tokens: int
    deepseek: float
    perplexity: float


class CostRecordResponse(BaseModel):
    """Single cost record"""

    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    reasoning_tokens: int
    cost_usd: float
    timestamp: float
    session_id: str | None
    task_type: str | None


@router.get("/summary", response_model=CostSummaryResponse)
async def get_cost_summary(
    period: str = Query(
        "today",
        description="Period: 'today', 'yesterday', 'hour', 'week', 'all'",
    ),
    session_id: str | None = Query(None, description="Optional session ID"),
):
    """
    Get cost summary for a period.

    - **period**: Time period to summarize
    - **session_id**: Optional session ID for session-specific costs
    """
    tracker = get_cost_tracker()
    summary = tracker.get_summary(period=period, session_id=session_id)

    return CostSummaryResponse(
        total_cost_usd=round(summary.total_cost_usd, 6),
        total_tokens=summary.total_tokens,
        total_requests=summary.total_requests,
        by_agent={k: round(v, 6) for k, v in summary.by_agent.items()},
        period_start=summary.period_start,
        period_end=summary.period_end,
    )


@router.get("/daily", response_model=list[DailyBreakdownItem])
async def get_daily_breakdown(
    days: int = Query(7, ge=1, le=90, description="Number of days to show"),
):
    """
    Get daily cost breakdown for the last N days.

    - **days**: Number of days to retrieve (1-90)
    """
    tracker = get_cost_tracker()
    breakdown = tracker.get_daily_breakdown(days=days)

    return [
        DailyBreakdownItem(
            date=item["date"],
            total_cost=round(item["total_cost"], 6),
            requests=item["requests"],
            tokens=item["tokens"],
            deepseek=round(item["deepseek"], 6),
            perplexity=round(item["perplexity"], 6),
        )
        for item in breakdown
    ]


@router.get("/recent", response_model=list[CostRecordResponse])
async def get_recent_records(
    limit: int = Query(50, ge=1, le=500, description="Number of records to show"),
):
    """
    Get recent cost records.

    - **limit**: Maximum number of records to return (1-500)
    """
    tracker = get_cost_tracker()
    records = tracker.get_recent_records(limit=limit)

    return [
        CostRecordResponse(
            agent=r.get("agent", "unknown"),
            model=r.get("model", "unknown"),
            prompt_tokens=r.get("prompt_tokens", 0),
            completion_tokens=r.get("completion_tokens", 0),
            total_tokens=r.get("total_tokens", 0),
            reasoning_tokens=r.get("reasoning_tokens", 0),
            cost_usd=r.get("cost_usd", 0),
            timestamp=r.get("timestamp", 0),
            session_id=r.get("session_id"),
            task_type=r.get("task_type"),
        )
        for r in records
    ]


@router.get("/dashboard")
async def get_dashboard():
    """
    Get complete dashboard data in one call.

    Returns summary for today, yesterday, and all-time,
    plus daily breakdown for the last 7 days.
    """
    tracker = get_cost_tracker()

    today = tracker.get_summary(period="today")
    yesterday = tracker.get_summary(period="yesterday")
    hour = tracker.get_summary(period="hour")
    all_time = tracker.get_summary(period="all")
    daily = tracker.get_daily_breakdown(days=7)

    return {
        "current_hour": {
            "cost_usd": round(hour.total_cost_usd, 4),
            "requests": hour.total_requests,
        },
        "today": {
            "cost_usd": round(today.total_cost_usd, 4),
            "tokens": today.total_tokens,
            "requests": today.total_requests,
            "by_agent": {k: round(v, 4) for k, v in today.by_agent.items()},
        },
        "yesterday": {
            "cost_usd": round(yesterday.total_cost_usd, 4),
            "requests": yesterday.total_requests,
        },
        "all_time": {
            "cost_usd": round(all_time.total_cost_usd, 4),
            "tokens": all_time.total_tokens,
            "requests": all_time.total_requests,
            "by_agent": {k: round(v, 4) for k, v in all_time.by_agent.items()},
        },
        "daily_breakdown": [
            {
                "date": item["date"],
                "cost": round(item["total_cost"], 4),
                "requests": item["requests"],
            }
            for item in daily
        ],
        "alerts": {
            "hourly_threshold": tracker.HOURLY_ALERT_THRESHOLD,
            "daily_threshold": tracker.DAILY_ALERT_THRESHOLD,
        },
    }


@router.delete("/session/{session_id}")
async def reset_session_costs(session_id: str):
    """
    Reset costs for a specific session.

    - **session_id**: Session ID to reset
    """
    tracker = get_cost_tracker()
    tracker.reset_session(session_id)
    return {"message": f"Session {session_id} costs reset"}
