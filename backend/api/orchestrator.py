"""
Orchestrator module - Orchestrator Dashboard and Workflow Management
Provides centralized management and monitoring of strategies and agents
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend.agents.base_config import DEEPSEEK_AVAILABLE, MCP_DISABLED, PERPLEXITY_AVAILABLE

__all__ = [
    "get_orchestrator_status",
    "orchestrator_router",
]


class OrchestratorStatus(BaseModel):
    """Status of the orchestrator system"""

    active_strategies: int = 0
    active_agents: int = 0
    system_health: str = "healthy"
    components: dict[str, str] = {}


def get_orchestrator_status() -> OrchestratorStatus:
    """Get current orchestrator status derived from runtime flags.

    Component availability is resolved at call-time from ``base_config``
    constants, which are themselves derived from environment variables
    (``DEEPSEEK_API_KEY``, ``PERPLEXITY_API_KEY``, ``MCP_DISABLED``).
    This means the response reflects actual configuration rather than
    a hardcoded stub.
    """
    return OrchestratorStatus(
        active_strategies=0,
        active_agents=0,
        system_health="healthy",
        components={
            "deepseek": "available" if DEEPSEEK_AVAILABLE else "unavailable",
            "perplexity": "available" if PERPLEXITY_AVAILABLE else "unavailable",
            "mcp_server": "disabled" if MCP_DISABLED else "available",
        },
    )


# Stub router for orchestrator endpoints
class OrchestratorRouter:
    """Stub orchestrator router"""

    def __init__(self):
        self.prefix = "/orchestrator"
        self.routes = []

    async def get_status(self) -> dict[str, Any]:
        """Get orchestrator status"""
        status = get_orchestrator_status()
        return status.model_dump()

    async def get_dashboard_data(self) -> dict[str, Any]:
        """Get dashboard data with live component status."""
        import datetime

        return {
            "status": "operational",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "components": [
                {
                    "name": "deepseek",
                    "status": "operational" if DEEPSEEK_AVAILABLE else "unavailable",
                },
                {
                    "name": "perplexity",
                    "status": "operational" if PERPLEXITY_AVAILABLE else "unavailable",
                },
                {
                    "name": "mcp_server",
                    "status": "disabled" if MCP_DISABLED else "operational",
                },
            ],
        }


# Create router instance
orchestrator_router = OrchestratorRouter()

# Create FastAPI router
router = APIRouter()


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Get orchestrator status"""
    return await orchestrator_router.get_status()


@router.get("/dashboard")
async def get_dashboard() -> dict[str, Any]:
    """Get dashboard data"""
    return await orchestrator_router.get_dashboard_data()


__all__ = [
    "get_orchestrator_status",
    "orchestrator_router",
    "router",
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
