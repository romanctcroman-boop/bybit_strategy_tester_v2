"""
Self-Healing Monitor
Автоматическое восстановление при падении MCP server
Based on: Kubernetes Liveness Probes, Google Borg Rescheduling, AWS Auto Scaling
"""

import asyncio
import time
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime


class SelfHealingMonitor:
    """Monitors MCP health and auto-restarts on failure"""
    
    def __init__(self, auto_start_service, fallback_router):
        self.auto_start = auto_start_service
        self.fallback = fallback_router
        
        # Configuration (Kubernetes liveness probe pattern)
        self.check_interval = 30  # Check every 30 seconds
        self.max_restart_attempts = 3
        self.restart_cooldown = 120  # 2 minutes between restart attempts
        
        # State
        self.is_monitoring = False
        self.consecutive_failures = 0
        self.last_restart_time = 0
        
        # Metrics
        self.metrics = {
            "total_checks": 0,
            "health_checks_passed": 0,
            "health_checks_failed": 0,
            "auto_restarts": 0,
            "restart_failures": 0,
            "uptime_start": None,
            "last_failure_time": None
        }
        
        self.logger = logging.getLogger(__name__)
    
    async def start_monitoring(self):
        """Start continuous health monitoring (Google Borg pattern)"""
        self.logger.info("🔍 Starting self-healing monitor...")
        self.is_monitoring = True
        self.metrics["uptime_start"] = datetime.now()
        
        while self.is_monitoring:
            try:
                await self._health_check_cycle()
            except Exception as e:
                self.logger.error(f"❌ Monitor error: {e}")
            
            await asyncio.sleep(self.check_interval)
    
    async def _health_check_cycle(self):
        """Single health check cycle with auto-recovery"""
        self.metrics["total_checks"] += 1
        
        # Check MCP health
        is_healthy = await self._check_mcp_health()
        
        if is_healthy:
            self.consecutive_failures = 0
            self.metrics["health_checks_passed"] += 1
            
            # Try to recover fallback router if needed
            await self.fallback.check_health_and_recover()
            
        else:
            self.consecutive_failures += 1
            self.metrics["health_checks_failed"] += 1
            self.metrics["last_failure_time"] = datetime.now()
            
            self.logger.warning(
                f"⚠️ Health check failed "
                f"({self.consecutive_failures} consecutive failures)"
            )
            
            # Trigger auto-restart after 3 consecutive failures
            if self.consecutive_failures >= 3:
                await self._attempt_auto_restart()
    
    async def _check_mcp_health(self) -> bool:
        """Check if MCP server is healthy"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.fallback.mcp_url}/health"
                )
                
                if response.status_code == 200:
                    return True
        
        except Exception as e:
            self.logger.debug(f"Health check failed: {e}")
        
        return False
    
    async def _attempt_auto_restart(self):
        """Attempt to restart MCP server (AWS Auto Scaling pattern)"""
        
        # Check cooldown period
        time_since_restart = time.time() - self.last_restart_time
        
        if time_since_restart < self.restart_cooldown:
            remaining = self.restart_cooldown - time_since_restart
            self.logger.warning(
                f"⏸️ Restart cooldown active "
                f"({remaining:.0f}s remaining)"
            )
            return
        
        # Check max restart attempts
        if self.metrics["auto_restarts"] >= self.max_restart_attempts:
            self.logger.error(
                f"🛑 Max restart attempts ({self.max_restart_attempts}) "
                f"reached, escalating to direct API mode"
            )
            # Force fallback router to direct API mode
            from intelligent_fallback import ConnectionMode
            self.fallback.force_mode(ConnectionMode.DIRECT_API)
            return
        
        self.logger.info("🔄 Attempting auto-restart of MCP server...")
        
        # Stop existing MCP process
        self.auto_start.stop_mcp_server()
        await asyncio.sleep(2)  # Wait for cleanup
        
        # Attempt restart
        success = self.auto_start.start_mcp_server()
        
        self.last_restart_time = time.time()
        
        if success:
            self.logger.info("✅ MCP server restarted successfully")
            self.metrics["auto_restarts"] += 1
            self.consecutive_failures = 0
        else:
            self.logger.error("❌ Failed to restart MCP server")
            self.metrics["restart_failures"] += 1
    
    def stop_monitoring(self):
        """Stop health monitoring"""
        self.logger.info("⏹️ Stopping self-healing monitor...")
        self.is_monitoring = False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get monitoring metrics"""
        uptime = None
        if self.metrics["uptime_start"]:
            uptime = (datetime.now() - self.metrics["uptime_start"]).total_seconds()
        
        return {
            **self.metrics,
            "uptime_seconds": uptime,
            "consecutive_failures": self.consecutive_failures,
            "is_monitoring": self.is_monitoring
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        metrics = self.get_metrics()
        
        total_checks = metrics["total_checks"]
        passed = metrics["health_checks_passed"]
        
        health_percentage = (passed / total_checks * 100) if total_checks > 0 else 0
        
        return {
            "status": "healthy" if self.consecutive_failures == 0 else "unhealthy",
            "consecutive_failures": self.consecutive_failures,
            "health_percentage": round(health_percentage, 2),
            "uptime_seconds": metrics["uptime_seconds"],
            "auto_restarts": metrics["auto_restarts"]
        }
