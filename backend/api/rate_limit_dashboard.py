"""
Rate Limit Dashboard API

Provides endpoints for monitoring API key status, rate limits,
and usage patterns for both DeepSeek and Perplexity.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/rate-limits", tags=["Rate Limits"])


class KeyStatus(BaseModel):
    """Status of a single API key"""

    index: int
    agent: str
    status: str  # "active", "cooling", "disabled"
    success_count: int
    error_count: int
    rate_limit_count: int
    last_used: str | None
    cooling_until: str | None
    weight: float
    usable: bool


class RateLimitStats(BaseModel):
    """Rate limit statistics"""

    total_requests: int
    rate_limited_requests: int
    rate_limit_percentage: float
    last_rate_limit: str | None
    cooldown_events_today: int


class AgentPoolStatus(BaseModel):
    """Status of an agent's key pool"""

    agent: str
    total_keys: int
    usable_keys: int
    cooling_keys: int
    disabled_keys: int
    rate_limit_stats: RateLimitStats
    keys: list[KeyStatus]


class DashboardSummary(BaseModel):
    """Overall dashboard summary"""

    timestamp: str
    agents: dict[str, AgentPoolStatus]
    alerts: list[dict[str, Any]]


@router.get("/summary", response_model=DashboardSummary)
async def get_rate_limit_summary():
    """
    Get overall rate limit dashboard summary.

    Returns status of all API keys, rate limit statistics,
    and any active alerts.
    """
    try:
        from backend.agents.unified_agent_interface import (
            AgentType,
            UnifiedAgentInterface,
        )

        agent = UnifiedAgentInterface()

        agents_status = {}
        alerts = []

        for agent_type in [AgentType.DEEPSEEK, AgentType.PERPLEXITY]:
            pool_status = await _get_agent_pool_status(agent, agent_type)
            agents_status[agent_type.value] = pool_status

            # Check for alerts
            if pool_status.usable_keys == 0:
                alerts.append(
                    {
                        "level": "critical",
                        "agent": agent_type.value,
                        "message": f"No usable keys for {agent_type.value}!",
                    }
                )
            elif pool_status.cooling_keys > pool_status.usable_keys:
                alerts.append(
                    {
                        "level": "warning",
                        "agent": agent_type.value,
                        "message": f"More keys cooling than usable for {agent_type.value}",
                    }
                )

        return DashboardSummary(
            timestamp=datetime.now().isoformat(),
            agents=agents_status,
            alerts=alerts,
        )

    except Exception as e:
        logger.error(f"Failed to get rate limit summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_name}", response_model=AgentPoolStatus)
async def get_agent_status(agent_name: str):
    """
    Get detailed status for a specific agent's key pool.

    Args:
        agent_name: "deepseek" or "perplexity"
    """
    try:
        from backend.agents.unified_agent_interface import (
            AgentType,
            UnifiedAgentInterface,
        )

        agent_type = AgentType(agent_name.lower())
        agent = UnifiedAgentInterface()

        return await _get_agent_pool_status(agent, agent_type)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent name: {agent_name}. Use 'deepseek' or 'perplexity'",
        )
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/{agent_name}/reset-cooling")
async def reset_key_cooling(agent_name: str, key_index: int | None = None):
    """
    Reset cooling period for keys.

    Args:
        agent_name: "deepseek" or "perplexity"
        key_index: Optional specific key index. If None, resets all keys.
    """
    try:
        from backend.agents.unified_agent_interface import (
            AgentType,
            UnifiedAgentInterface,
        )

        agent_type = AgentType(agent_name.lower())
        agent = UnifiedAgentInterface()

        pool = agent.key_manager._key_pools.get(agent_type, [])
        reset_count = 0

        for key in pool:
            if key_index is None or key.index == key_index:
                if key.cooling_until and key.cooling_until > datetime.now().timestamp():
                    key.cooling_until = None
                    reset_count += 1

        logger.info(f"Reset cooling for {reset_count} keys ({agent_name})")

        return {
            "success": True,
            "agent": agent_name,
            "keys_reset": reset_count,
        }

    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid agent: {agent_name}")
    except Exception as e:
        logger.error(f"Failed to reset cooling: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rate-limit-events")
async def get_rate_limit_events(
    agent: str | None = None,
    limit: int = 50,
):
    """
    Get recent rate limit events.

    Args:
        agent: Optional filter by agent name
        limit: Maximum number of events to return
    """
    try:
        from backend.agents.unified_agent_interface import UnifiedAgentInterface

        agent_interface = UnifiedAgentInterface()

        # Get rate limit events from stats
        events = []

        # Access internal rate limit tracking if available
        if hasattr(agent_interface, "_rate_limit_events"):
            all_events = agent_interface._rate_limit_events
            if agent:
                events = [e for e in all_events if e.get("agent") == agent]
            else:
                events = all_events

        return {
            "events": events[-limit:],
            "total": len(events),
        }

    except Exception as e:
        logger.error(f"Failed to get rate limit events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def rate_limit_health_check():
    """
    Quick health check for rate limit monitoring.
    """
    try:
        from backend.agents.unified_agent_interface import (
            AgentType,
            UnifiedAgentInterface,
        )

        agent = UnifiedAgentInterface()

        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "agents": {},
        }

        for agent_type in [AgentType.DEEPSEEK, AgentType.PERPLEXITY]:
            pool = agent.key_manager._key_pools.get(agent_type, [])
            usable = sum(1 for k in pool if _is_key_usable(k))

            health["agents"][agent_type.value] = {
                "total": len(pool),
                "usable": usable,
                "status": "ok" if usable > 0 else "degraded",
            }

            if usable == 0:
                health["status"] = "degraded"

        return health

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def _get_agent_pool_status(agent, agent_type) -> AgentPoolStatus:
    """Get detailed status for an agent's key pool"""
    pool = agent.key_manager._key_pools.get(agent_type, [])

    keys_status = []
    usable = 0
    cooling = 0
    disabled = 0
    total_requests = 0
    rate_limited = 0

    for key in pool:
        status = "active"
        is_usable = True
        cooling_until_str = None

        if key.disabled:
            status = "disabled"
            disabled += 1
            is_usable = False
        elif key.cooling_until and key.cooling_until > datetime.now().timestamp():
            status = "cooling"
            cooling += 1
            is_usable = False
            cooling_until_str = datetime.fromtimestamp(key.cooling_until).isoformat()
        else:
            usable += 1

        total_requests += key.success_count + key.error_count
        rate_limited += key.rate_limit_count

        keys_status.append(
            KeyStatus(
                index=key.index,
                agent=agent_type.value,
                status=status,
                success_count=key.success_count,
                error_count=key.error_count,
                rate_limit_count=key.rate_limit_count,
                last_used=datetime.fromtimestamp(key.last_used).isoformat()
                if key.last_used
                else None,
                cooling_until=cooling_until_str,
                weight=key.get_weight() if hasattr(key, "get_weight") else 1.0,
                usable=is_usable,
            )
        )

    rate_limit_pct = (rate_limited / total_requests * 100) if total_requests > 0 else 0

    return AgentPoolStatus(
        agent=agent_type.value,
        total_keys=len(pool),
        usable_keys=usable,
        cooling_keys=cooling,
        disabled_keys=disabled,
        rate_limit_stats=RateLimitStats(
            total_requests=total_requests,
            rate_limited_requests=rate_limited,
            rate_limit_percentage=round(rate_limit_pct, 2),
            last_rate_limit=None,  # Would need to track this
            cooldown_events_today=cooling,
        ),
        keys=keys_status,
    )


def _is_key_usable(key) -> bool:
    """Check if a key is currently usable"""
    if key.disabled:
        return False
    if key.cooling_until and key.cooling_until > datetime.now().timestamp():
        return False
    return True
