"""
MCP Reliability Orchestrator
Главный координатор всех компонентов reliability системы
Based on: Netflix Conductor, Kubernetes Operator, AWS Step Functions patterns
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from .mcp_auto_start import MCPAutoStartService
from .intelligent_fallback import IntelligentFallbackRouter, ConnectionMode
from .self_healing_monitor import SelfHealingMonitor
from .encryption_key_manager import EncryptionKeyManager


class MCPReliabilityOrchestrator:
    """
    Global singleton that orchestrates MCP reliability system
    Handles IDE lifecycle: startup → run → shutdown
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern (Google Borg style)"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # Initialize all components
        self.logger.info("🚀 Initializing MCP Reliability System...")
        
        # Component 1: Encryption Key Manager (load keys first)
        self.key_manager = EncryptionKeyManager(
            keys_file="encrypted_api_keys.json"
        )
        
        # Component 2: MCP Auto-Start Service
        self.auto_start = MCPAutoStartService(
            mcp_script_path="mcp-server/server.py"
        )
        
        # Component 3: Intelligent Fallback Router
        self.fallback_router = IntelligentFallbackRouter(
            mcp_url="http://localhost:3000"
        )
        
        # Component 4: Self-Healing Monitor
        self.monitor = SelfHealingMonitor(
            auto_start_service=self.auto_start,
            fallback_router=self.fallback_router
        )
        
        # State
        self.is_running = False
        self.monitor_task = None
        
        self._initialized = True
        self.logger.info("✅ MCP Reliability System initialized")
    
    def _setup_logging(self):
        """Setup comprehensive logging (ELK/Splunk compatible)"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    async def startup(self) -> bool:
        """
        Complete system startup sequence
        Called when IDE launches
        """
        self.logger.info("=" * 80)
        self.logger.info("🚀 MCP RELIABILITY SYSTEM STARTUP")
        self.logger.info("=" * 80)
        
        try:
            # Step 1: Load API keys from encrypted storage
            self.logger.info("📦 Step 1/4: Loading encrypted API keys...")
            keys_loaded = self.key_manager.load_keys_from_disk()
            
            if not keys_loaded:
                self.logger.warning("⚠️ No encrypted keys found, using empty pool")
            
            # Inject keys into fallback router
            for service in ["deepseek", "perplexity"]:
                keys = self.key_manager.get_keys(service)
                for key in keys:
                    self.fallback_router.add_api_key(service, key)
            
            # Step 2: Start MCP server
            self.logger.info("📦 Step 2/4: Starting MCP server...")
            mcp_started = self.auto_start.start_mcp_server()
            
            if not mcp_started:
                self.logger.warning("⚠️ MCP server failed to start, will use direct API mode")
                self.fallback_router.force_mode(ConnectionMode.DIRECT_API)
            
            # Step 3: Initialize fallback router
            self.logger.info("📦 Step 3/4: Initializing intelligent fallback router...")
            # Router already configured with keys
            
            # Step 4: Start self-healing monitor
            self.logger.info("📦 Step 4/4: Starting self-healing monitor...")
            self.monitor_task = asyncio.create_task(
                self.monitor.start_monitoring()
            )
            
            self.is_running = True
            
            self.logger.info("=" * 80)
            self.logger.info("✅ MCP RELIABILITY SYSTEM READY")
            self.logger.info("=" * 80)
            self._print_status()
            
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Startup failed: {e}")
            return False
    
    async def shutdown(self):
        """
        Graceful shutdown sequence
        Called when IDE closes
        """
        self.logger.info("=" * 80)
        self.logger.info("⏹️ MCP RELIABILITY SYSTEM SHUTDOWN")
        self.logger.info("=" * 80)
        
        try:
            # Step 1: Stop self-healing monitor
            self.logger.info("📦 Step 1/3: Stopping self-healing monitor...")
            self.monitor.stop_monitoring()
            
            if self.monitor_task:
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
            
            # Step 2: Save API keys (if modified)
            self.logger.info("📦 Step 2/3: Saving encrypted API keys...")
            self.key_manager.save_keys_to_disk()
            
            # Step 3: Stop MCP server
            self.logger.info("📦 Step 3/3: Stopping MCP server...")
            self.auto_start.stop_mcp_server()
            
            self.is_running = False
            
            self.logger.info("=" * 80)
            self.logger.info("✅ MCP RELIABILITY SYSTEM STOPPED")
            self.logger.info("=" * 80)
        
        except Exception as e:
            self.logger.error(f"❌ Shutdown error: {e}")
    
    async def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified request interface (abstracts MCP vs Direct API)
        Automatically handles failover and retry
        """
        return await self.fallback_router.send_request(request)
    
    def add_api_key(self, service: str, api_key: str):
        """Add API key and persist to encrypted storage"""
        self.key_manager.add_key_to_pool(service, api_key)
        self.fallback_router.add_api_key(service, api_key)
        self.key_manager.save_keys_to_disk()
    
    def get_status(self) -> Dict[str, Any]:
        """Get complete system status"""
        return {
            "system_running": self.is_running,
            "mcp_running": self.auto_start.is_running,
            "monitor_active": self.monitor.is_monitoring,
            "current_mode": self.fallback_router.current_mode.value,
            "circuit_breaker_open": self.fallback_router.circuit_open,
            "key_status": self.key_manager.get_key_status(),
            "health_status": self.monitor.get_health_status(),
            "router_metrics": self.fallback_router.get_metrics(),
            "monitor_metrics": self.monitor.get_metrics()
        }
    
    def _print_status(self):
        """Print current system status"""
        status = self.get_status()
        
        self.logger.info("")
        self.logger.info("📊 System Status:")
        self.logger.info(f"   MCP Server: {'🟢 Running' if status['mcp_running'] else '🔴 Stopped'}")
        self.logger.info(f"   Connection Mode: {status['current_mode']}")
        self.logger.info(f"   Circuit Breaker: {'🔴 OPEN' if status['circuit_breaker_open'] else '🟢 CLOSED'}")
        self.logger.info(f"   DeepSeek Keys: {status['key_status']['deepseek_keys']}")
        self.logger.info(f"   Perplexity Keys: {status['key_status']['perplexity_keys']}")
        self.logger.info(f"   Self-Healing: {'🟢 Active' if status['monitor_active'] else '🔴 Inactive'}")
        self.logger.info("")


# Global singleton instance
reliability_system = MCPReliabilityOrchestrator()


# IDE Lifecycle Hooks
async def on_ide_startup():
    """Hook: Called when IDE starts"""
    await reliability_system.startup()


async def on_ide_shutdown():
    """Hook: Called when IDE closes"""
    await reliability_system.shutdown()


# Convenience functions for external use
async def send_ai_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Send request through reliability system"""
    return await reliability_system.send_request(request)


def get_system_status() -> Dict[str, Any]:
    """Get current system status"""
    return reliability_system.get_status()
