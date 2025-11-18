#!/usr/bin/env python3
"""
Health check endpoint for MCP Server production deployment.
Checks database connectivity, Redis connectivity, and overall system health.
"""

import asyncio
import sys
from typing import Dict, Any
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import httpx

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class HealthChecker:
    """Comprehensive health checking for MCP server components."""
    
    def __init__(self) -> None:
        self.db_url = "postgresql+asyncpg://mcp_user:${DB_PASSWORD}@postgres:5432/mcp_db"
        self.redis_url = "redis://:${REDIS_PASSWORD}@redis:6379/0"
        self.engine = None
        self.redis_client = None
        
    async def setup(self) -> None:
        """Initialize database and Redis connections."""
        try:
            self.engine = create_async_engine(self.db_url, pool_pre_ping=True)
            self.redis_client = redis.from_url(
                self.redis_url, 
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
        except Exception as e:
            logger.error(f"Failed to initialize health checker: {e}")
            raise
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and basic operations."""
        try:
            async with AsyncSession(self.engine) as session:
                # Test basic query
                result = await session.execute(text("SELECT 1"))
                row = result.scalar()
                
                # Check connection pool status
                pool = self.engine.pool
                status = {
                    "status": "healthy",
                    "connection_test": "passed",
                    "pool_size": pool.size() if hasattr(pool, 'size') else "unknown",
                    "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else "unknown"
                }
                return status
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity and basic operations."""
        try:
            # Test connection and basic operations
            await self.redis_client.ping()
            
            # Test read/write
            test_key = "health_check_test"
            test_value = "ok"
            await self.redis_client.set(test_key, test_value, ex=10)
            retrieved = await self.redis_client.get(test_key)
            
            status = {
                "status": "healthy" if retrieved == test_value else "unhealthy",
                "ping": "success",
                "read_write_test": "passed" if retrieved == test_value else "failed"
            }
            return status
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (2**30)
            
            status = {
                "status": "healthy" if free_gb > 1 else "warning",
                "free_gb": free_gb,
                "free_percent": round((free / total) * 100, 1)
            }
            return status
            
        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return {
                "status": "unknown",
                "error": str(e)
            }
    
    async def check_memory_usage(self) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            
            status = {
                "status": "healthy" if memory.percent < 90 else "warning",
                "used_percent": memory.percent,
                "available_gb": round(memory.available / (1024**3), 1)
            }
            return status
            
        except Exception as e:
            logger.error(f"Memory check failed: {e}")
            return {
                "status": "unknown",
                "error": str(e)
            }
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of all components."""
        try:
            await self.setup()
            
            checks = {
                "database": await self.check_database(),
                "redis": await self.check_redis(),
                "disk_space": await self.check_disk_space(),
                "memory": await self.check_memory_usage(),
            }
            
            # Determine overall status
            overall_status = "healthy"
            for check_name, result in checks.items():
                if result.get("status") == "unhealthy":
                    overall_status = "unhealthy"
                    break
                elif result.get("status") == "warning" and overall_status == "healthy":
                    overall_status = "warning"
            
            health_report = {
                "status": overall_status,
                "timestamp": asyncio.get_event_loop().time(),
                "checks": checks
            }
            
            return health_report
            
        except Exception as e:
            logger.error(f"Comprehensive health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": f"Health check initialization failed: {e}"
            }
        finally:
            # Cleanup connections
            if self.engine:
                await self.engine.dispose()
            if self.redis_client:
                await self.redis_client.close()

async def main() -> None:
    """Main health check execution."""
    checker = HealthChecker()
    
    try:
        health_report = await checker.comprehensive_health_check()
        
        # Print JSON output for HTTP response
        import json
        print(json.dumps(health_report, indent=2))
        
        # Exit with appropriate code
        sys.exit(0 if health_report["status"] == "healthy" else 1)
        
    except Exception as e:
        logger.error(f"Health check execution failed: {e}")
        error_report = {
            "status": "unhealthy",
            "error": str(e)
        }
        print(json.dumps(error_report))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())