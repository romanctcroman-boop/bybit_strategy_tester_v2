"""
MCP Auto-Start Service
Автоматический запуск MCP server при старте IDE с retry logic и health validation
Based on: DeepSeek + Perplexity recommendations (Netflix, AWS, Google SRE best practices)
"""

import subprocess
import time
import threading
import httpx
from typing import Optional
import logging
from pathlib import Path


class MCPAutoStartService:
    """Automatic MCP server startup with retry and health validation"""
    
    def __init__(self, mcp_script_path: Optional[str] = None):
        self.mcp_process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.startup_attempts = 0
        self.max_startup_attempts = 3
        self.mcp_script_path = mcp_script_path or "mcp-server/server.py"
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def start_mcp_server(self) -> bool:
        """Start MCP server with exponential backoff retry logic"""
        for attempt in range(self.max_startup_attempts):
            try:
                self.logger.info(f"🚀 Starting MCP server (attempt {attempt + 1}/{self.max_startup_attempts})")
                
                # Start MCP server process
                self.mcp_process = subprocess.Popen(
                    ['python', self.mcp_script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=str(Path(__file__).parent.parent)
                )
                
                # Wait for server to be ready
                if self._wait_for_ready(timeout=15):
                    self.is_running = True
                    self.startup_attempts = 0
                    self.logger.info("✅ MCP server started successfully")
                    return True
                else:
                    self.logger.warning(f"⚠️ MCP server did not become ready within timeout")
                    self._cleanup_failed_process()
                
            except Exception as e:
                self.logger.error(f"❌ MCP startup attempt {attempt + 1} failed: {e}")
                self._cleanup_failed_process()
            
            # Exponential backoff between attempts
            if attempt < self.max_startup_attempts - 1:
                backoff_time = 2 ** attempt
                self.logger.info(f"⏳ Waiting {backoff_time}s before retry...")
                time.sleep(backoff_time)
        
        self.logger.error("💥 MCP server failed to start after all attempts")
        return False
    
    def _wait_for_ready(self, timeout: int = 15) -> bool:
        """Wait for MCP server to be ready with health checks"""
        start_time = time.time()
        check_interval = 1
        
        self.logger.info(f"⏳ Waiting for MCP server to be ready (timeout: {timeout}s)...")
        
        while time.time() - start_time < timeout:
            # Check if process is still alive
            if self.mcp_process and self.mcp_process.poll() is not None:
                self.logger.error("❌ MCP process terminated during startup")
                return False
            
            # Try HTTP health check
            try:
                with httpx.Client(timeout=2.0) as client:
                    response = client.get("http://localhost:3000/health")
                    if response.status_code == 200:
                        self.logger.info("✅ MCP server health check passed")
                        return True
            except Exception:
                # Server not ready yet, continue waiting
                pass
            
            time.sleep(check_interval)
        
        self.logger.warning(f"⏱️ Health check timeout after {timeout}s")
        return False
    
    def _cleanup_failed_process(self):
        """Clean up failed process"""
        if self.mcp_process:
            try:
                self.mcp_process.terminate()
                self.mcp_process.wait(timeout=5)
            except:
                try:
                    self.mcp_process.kill()
                except:
                    pass
            self.mcp_process = None
    
    def stop_mcp_server(self):
        """Gracefully stop MCP server"""
        if self.mcp_process:
            self.logger.info("🛑 Stopping MCP server...")
            
            # Try graceful termination first
            self.mcp_process.terminate()
            
            try:
                self.mcp_process.wait(timeout=10)
                self.logger.info("✅ MCP server stopped gracefully")
            except subprocess.TimeoutExpired:
                self.logger.warning("⚠️ MCP server did not stop gracefully, forcing kill")
                self.mcp_process.kill()
                self.mcp_process.wait()
            
            self.mcp_process = None
            self.is_running = False
    
    def is_alive(self) -> bool:
        """Check if MCP process is alive"""
        if not self.mcp_process:
            return False
        return self.mcp_process.poll() is None
    
    def restart_server(self) -> bool:
        """Restart MCP server"""
        self.logger.info("🔄 Restarting MCP server...")
        self.stop_mcp_server()
        time.sleep(2)  # Brief pause
        return self.start_mcp_server()
