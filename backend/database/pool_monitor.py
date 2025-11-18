"""
Week 1, Day 3: Database Connection Pool Monitoring
Real-time monitoring and health checks for SQLAlchemy connection pool
"""

import logging
from typing import Dict, Any
from sqlalchemy import inspect
from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)


class ConnectionPoolMonitor:
    """
    Monitor and report on database connection pool health.
    
    Features:
    - Real-time pool statistics
    - Connection leak detection
    - Performance metrics
    - Health status checks
    """
    
    def __init__(self, engine):
        """
        Initialize pool monitor.
        
        Args:
            engine: SQLAlchemy engine with connection pool
        """
        self.engine = engine
        self.pool: Pool = engine.pool
    
    def get_pool_status(self) -> Dict[str, Any]:
        """
        Get current connection pool status.
        
        Returns:
            Dict with pool metrics:
            {
                "size": int,  # Total pool size
                "checked_in": int,  # Available connections
                "checked_out": int,  # In-use connections
                "overflow": int,  # Overflow connections
                "max_overflow": int,  # Max overflow allowed
                "timeout": float,  # Pool timeout
                "recycle": int,  # Recycle time
                "pre_ping": bool,  # Pre-ping enabled
                "health": str  # "healthy" | "warning" | "critical"
            }
        """
        pool = self.pool
        
        try:
            # Core pool metrics
            size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            overflow = pool.overflow()
            
            # Configuration
            max_overflow = getattr(pool, '_max_overflow', 0)
            timeout = getattr(pool, '_timeout', 30)
            recycle = getattr(pool, '_recycle', 3600)
            pre_ping = getattr(pool, '_pre_ping', False)
            
            # Calculate health status
            utilization = checked_out / (size + overflow) if (size + overflow) > 0 else 0
            
            if utilization > 0.9:
                health = "critical"  # >90% utilization
            elif utilization > 0.7:
                health = "warning"  # >70% utilization
            else:
                health = "healthy"
            
            return {
                "size": size,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "overflow": overflow,
                "max_overflow": max_overflow,
                "timeout": timeout,
                "recycle": recycle,
                "pre_ping": pre_ping,
                "utilization": round(utilization * 100, 2),
                "health": health,
                "total_capacity": size + max_overflow
            }
            
        except Exception as e:
            logger.error(f"Error getting pool status: {e}")
            return {
                "error": str(e),
                "health": "unknown"
            }
    
    def log_pool_status(self):
        """Log current pool status at INFO level"""
        status = self.get_pool_status()
        
        logger.info(
            f"DB Pool Status: {status['checked_out']}/{status['size']} in use, "
            f"{status['checked_in']} available, {status['overflow']} overflow, "
            f"utilization={status.get('utilization', 0)}%, health={status['health']}"
        )
    
    def check_connection_leaks(self, threshold: int = 10) -> bool:
        """
        Check for potential connection leaks.
        
        Args:
            threshold: Max seconds a connection should be checked out
            
        Returns:
            True if potential leak detected
        """
        status = self.get_pool_status()
        
        # If utilization is high and overflow is maxed out, potential leak
        if status['overflow'] >= status['max_overflow'] and status['utilization'] > 90:
            logger.warning(
                f"Potential connection leak detected! "
                f"Pool exhausted: {status['checked_out']} connections in use, "
                f"overflow maxed at {status['overflow']}"
            )
            return True
        
        return False
    
    def get_pool_statistics(self) -> Dict[str, Any]:
        """
        Get detailed pool statistics.
        
        Returns:
            Dict with detailed metrics
        """
        status = self.get_pool_status()
        
        # Calculate additional metrics
        total_connections = status['size'] + status['overflow']
        available_capacity = status['total_capacity'] - status['checked_out']
        
        return {
            **status,
            "total_connections": total_connections,
            "available_capacity": available_capacity,
            "is_healthy": status['health'] == "healthy",
            "needs_attention": status['health'] in ["warning", "critical"]
        }
    
    def is_pool_healthy(self) -> bool:
        """
        Check if pool is in healthy state.
        
        Returns:
            True if pool is healthy
        """
        status = self.get_pool_status()
        return status.get('health') == "healthy"
    
    def get_recommendations(self) -> list[str]:
        """
        Get recommendations based on current pool status.
        
        Returns:
            List of recommendation strings
        """
        status = self.get_pool_status()
        recommendations = []
        
        utilization = status.get('utilization', 0)
        
        if utilization > 90:
            recommendations.append(
                "CRITICAL: Pool utilization >90%. "
                "Consider increasing pool_size or max_overflow."
            )
        elif utilization > 70:
            recommendations.append(
                "WARNING: Pool utilization >70%. "
                "Monitor for potential bottlenecks."
            )
        
        if status['overflow'] > status['max_overflow'] * 0.8:
            recommendations.append(
                "Overflow connections frequently used. "
                "Consider increasing base pool_size."
            )
        
        if not status.get('pre_ping', False):
            recommendations.append(
                "SECURITY: pool_pre_ping is disabled. "
                "Enable to prevent stale connection errors."
            )
        
        if status.get('recycle', 0) > 7200:
            recommendations.append(
                "Long recycle time (>2h). "
                "Consider reducing to 3600s for better connection health."
            )
        
        if not recommendations:
            recommendations.append("Pool is healthy. No action needed.")
        
        return recommendations


def create_pool_monitor(engine):
    """
    Factory function to create pool monitor.
    
    Args:
        engine: SQLAlchemy engine
        
    Returns:
        ConnectionPoolMonitor instance
    """
    return ConnectionPoolMonitor(engine)


# Convenience function for quick health check
def check_pool_health(engine) -> bool:
    """
    Quick health check for connection pool.
    
    Args:
        engine: SQLAlchemy engine
        
    Returns:
        True if pool is healthy
    """
    monitor = ConnectionPoolMonitor(engine)
    return monitor.is_pool_healthy()


if __name__ == "__main__":
    # Example usage
    from backend.database import engine
    
    monitor = ConnectionPoolMonitor(engine)
    
    print("=" * 80)
    print("DATABASE CONNECTION POOL STATUS")
    print("=" * 80)
    
    status = monitor.get_pool_status()
    print(f"\nPool Size: {status['size']}")
    print(f"Checked Out: {status['checked_out']}")
    print(f"Checked In: {status['checked_in']}")
    print(f"Overflow: {status['overflow']}/{status['max_overflow']}")
    print(f"Utilization: {status.get('utilization', 0)}%")
    print(f"Health: {status['health']}")
    print(f"Pre-ping: {status.get('pre_ping', False)}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    for rec in monitor.get_recommendations():
        print(f"- {rec}")
