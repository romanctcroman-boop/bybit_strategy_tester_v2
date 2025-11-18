"""
API endpoints for Orchestrator Dashboard

Provides REST API for:
- Plugin management
- Priority statistics
- System status monitoring
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

# NOTE: prefix is set in app.py during include_router (prefix="/api/orchestrator")
router = APIRouter(tags=["orchestrator"])


# Note: Will be injected by main app
plugin_manager = None
task_queue = None


def set_dependencies(pm, tq):
    """Set plugin manager and task queue instances"""
    global plugin_manager, task_queue
    plugin_manager = pm
    task_queue = tq


@router.get("/plugins")
async def get_plugins() -> dict[str, Any]:
    """
    Get list of all loaded plugins
    
    Returns:
        {
            "success": true,
            "total_plugins": 4,
            "statistics": {...},
            "plugins": [...]
        }
    """
    try:
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin Manager not initialized")
        
        plugins = plugin_manager.list_plugins()
        stats = plugin_manager.get_statistics()
        
        return {
            "success": True,
            "total_plugins": len(plugins),
            "statistics": stats,
            "plugins": plugins
        }
        
    except Exception as e:
        logger.error(f"[get_plugins] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plugins/{plugin_name}/reload")
async def reload_plugin(plugin_name: str) -> dict[str, Any]:
    """
    Hot reload a specific plugin
    
    Args:
        plugin_name: Name of the plugin to reload
    
    Returns:
        {
            "success": true,
            "message": "Plugin reloaded successfully",
            "plugin_info": {...}
        }
    """
    try:
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin Manager not initialized")
        
        logger.info(f"[reload_plugin] Reloading plugin: {plugin_name}")
        
        await plugin_manager.reload_plugin(plugin_name)
        
        # Get updated plugin info
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        
        return {
            "success": True,
            "message": f"Plugin {plugin_name} reloaded successfully",
            "plugin_info": plugin_info
        }
        
    except Exception as e:
        logger.error(f"[reload_plugin] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plugins/{plugin_name}")
async def get_plugin_info(plugin_name: str) -> dict[str, Any]:
    """
    Get detailed information about a specific plugin
    
    Args:
        plugin_name: Name of the plugin
    
    Returns:
        {
            "success": true,
            "plugin_info": {...}
        }
    """
    try:
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin Manager not initialized")
        
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        
        if not plugin_info:
            raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")
        
        return {
            "success": True,
            "plugin_info": plugin_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[get_plugin_info] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/priority/statistics")
async def get_priority_statistics() -> dict[str, Any]:
    """
    Get priority system statistics
    
    Returns:
        {
            "success": true,
            "statistics": {...}
        }
    """
    try:
        if not task_queue:
            # Return placeholder until TaskQueue is integrated
            return {
                "success": True,
                "message": "TaskQueue integration pending",
                "statistics": {
                    "intelligent_prioritization": "enabled",
                    "features": {
                        "multi_factor_scoring": "8 factors",
                        "anti_starvation": "aging mechanism (300s threshold)",
                        "load_aware": "queue pressure multiplier (0.7x-1.2x)",
                        "user_tier_bonus": "FREE=0, BASIC=+2, PREMIUM=+5, ENTERPRISE=+10",
                        "success_rate_learning": "enabled",
                        "priority_caching": "60s TTL",
                        "background_monitoring": "30s interval"
                    }
                }
            }
        
        stats = await task_queue.get_priority_statistics()
        
        return {
            "success": True,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"[get_priority_statistics] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system-status")
async def get_system_status() -> dict[str, Any]:
    """
    Get comprehensive orchestrator system status
    
    Returns:
        {
            "success": true,
            "timestamp": "2025-11-15T...",
            "plugin_manager": {...},
            "priority_system": {...},
            "mcp_server": {...}
        }
    """
    try:
        from datetime import datetime
        
        plugin_stats = {}
        if plugin_manager:
            plugin_stats = plugin_manager.get_statistics()
        
        result = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "plugin_manager": {
                "initialized": plugin_manager is not None,
                "statistics": plugin_stats
            },
            "priority_system": {
                "intelligent_prioritization": "enabled",
                "features": [
                    "Multi-factor scoring (8 factors)",
                    "Anti-starvation mechanism",
                    "Load-aware scheduling",
                    "User tier bonuses",
                    "Success rate learning",
                    "Priority caching",
                    "Background monitoring"
                ]
            },
            "mcp_server": {
                "version": "2.0",
                "providers_ready": True,  # TODO: Get from actual provider status
                "deepseek_agent": True    # TODO: Get from actual agent status
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"[get_system_status] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
