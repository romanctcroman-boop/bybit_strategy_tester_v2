"""
MCP Reliability Auto-Start System
Автоматическая система надёжности для MCP сервера

Components:
- MCPAutoStartService: Auto-start MCP with retry and health checks
- IntelligentFallbackRouter: Circuit breaker + MCP/Direct API failover
- SelfHealingMonitor: 30s health checks + auto-restart
- EncryptionKeyManager: AES-256 encrypted API key storage
- MCPReliabilityOrchestrator: Main coordinator (singleton)

Usage:
    from reliability_auto_system import on_ide_startup, on_ide_shutdown, send_ai_request
    
    # In your IDE startup hook:
    await on_ide_startup()
    
    # Send requests (automatically handles failover):
    result = await send_ai_request({
        "service": "deepseek",
        "query": "Analyze this trading strategy..."
    })
    
    # In your IDE shutdown hook:
    await on_ide_shutdown()
"""

from .mcp_auto_start import MCPAutoStartService
from .intelligent_fallback import IntelligentFallbackRouter, ConnectionMode
from .self_healing_monitor import SelfHealingMonitor
from .encryption_key_manager import EncryptionKeyManager
from .mcp_reliability_orchestrator import (
    MCPReliabilityOrchestrator,
    reliability_system,
    on_ide_startup,
    on_ide_shutdown,
    send_ai_request,
    get_system_status
)

__all__ = [
    'MCPAutoStartService',
    'IntelligentFallbackRouter',
    'ConnectionMode',
    'SelfHealingMonitor',
    'EncryptionKeyManager',
    'MCPReliabilityOrchestrator',
    'reliability_system',
    'on_ide_startup',
    'on_ide_shutdown',
    'send_ai_request',
    'get_system_status'
]

__version__ = '1.0.0'
