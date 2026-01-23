"""
Orchestrator module - Orchestrator Dashboard and Workflow Management
Provides centralized management and monitoring of strategies and agents
"""

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

__all__ = [
    "orchestrator_router",
    "get_orchestrator_status",
]


class OrchestratorStatus(BaseModel):
    """Status of the orchestrator system"""

    active_strategies: int = 0
    active_agents: int = 0
    system_health: str = "healthy"
    components: Dict[str, str] = {}


def get_orchestrator_status() -> OrchestratorStatus:
    """Get current orchestrator status"""
    return OrchestratorStatus(
        active_strategies=0,
        active_agents=0,
        system_health="healthy",
        components={
            "deepseek": "available",
            "perplexity": "available",
            "mcp_server": "available",
        },
    )


# Stub router for orchestrator endpoints
class OrchestratorRouter:
    """Stub orchestrator router"""

    def __init__(self):
        self.prefix = "/orchestrator"
        self.routes = []

    async def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status"""
        status = get_orchestrator_status()
        return status.dict()

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data"""
        return {
            "status": "operational",
            "timestamp": "2025-12-04T11:30:00Z",
            "components": [
                {"name": "deepseek", "status": "operational"},
                {"name": "perplexity", "status": "operational"},
                {"name": "mcp_server", "status": "operational"},
            ],
        }


# Create router instance
orchestrator_router = OrchestratorRouter()

# Create FastAPI router
router = APIRouter()


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Get orchestrator status"""
    return await orchestrator_router.get_status()


@router.get("/dashboard")
async def get_dashboard() -> Dict[str, Any]:
    """Get dashboard data"""
    return await orchestrator_router.get_dashboard_data()


__all__ = [
    "orchestrator_router",
    "router",
    "get_orchestrator_status",
]


def set_dependencies(plugin_manager=None, queue_adapter=None) -> None:
    """Set dependencies for orchestrator module (plugin-system compatibility stub).

    Accepts the plugin manager and an optional queue adapter. This is a minimal
    compatibility shim so the plugin system can inject dependencies without
    raising errors during app startup. If callers need these values, they can
    be read from the module-level objects in the future.
    """
    logger = __import__("logging").getLogger(__name__)
    logger.debug(
        "orchestrator.set_dependencies called (stub) plugin_manager=%s queue_adapter=%s",
        plugin_manager,
        queue_adapter,
    )
