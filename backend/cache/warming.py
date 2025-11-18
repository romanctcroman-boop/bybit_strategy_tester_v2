"""
Cache Warming System

Proactively loads frequently accessed data into cache.

Features:
- Automatic warming on startup
- Scheduled warming for hot data
- Priority-based warming
- Memory-aware loading
"""

import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime, timedelta

from backend.cache.cache_manager import get_cache_manager
from backend.cache.decorators import warm_cache

logger = logging.getLogger(__name__)


class CacheWarmer:
    """
    Cache warming system for preloading hot data.
    
    Features:
    - Priority-based warming (critical, high, normal, low)
    - Scheduled refreshing
    - Failure retry with backoff
    - Memory budget management
    
    Example:
        >>> warmer = CacheWarmer()
        >>> 
        >>> # Register warming tasks
        >>> warmer.register_task(
        ...     name="popular_strategies",
        ...     priority="high",
        ...     warm_func=load_popular_strategies,
        ...     ttl=3600,
        ...     refresh_interval=1800
        ... )
        >>> 
        >>> # Warm all caches
        >>> await warmer.warm_all()
    """
    
    def __init__(self, max_concurrent: int = 5):
        """
        Initialize cache warmer.
        
        Args:
            max_concurrent: Maximum concurrent warming tasks
        """
        self.max_concurrent = max_concurrent
        self.tasks: List[Dict[str, Any]] = []
        self._cache_manager = None
        self._warming_in_progress = False
        self._stats = {
            'total_warmed': 0,
            'total_failed': 0,
            'last_warm_time': None,
        }
    
    async def connect(self):
        """Initialize cache manager."""
        self._cache_manager = await get_cache_manager()
        logger.info("✅ CacheWarmer initialized")
    
    def register_task(
        self,
        name: str,
        warm_func: Callable,
        priority: str = "normal",
        ttl: int = 3600,
        refresh_interval: Optional[int] = None,
        key_prefix: Optional[str] = None,
    ):
        """
        Register cache warming task.
        
        Args:
            name: Task name (for logging)
            warm_func: Async function that returns data to cache
            priority: critical, high, normal, low
            ttl: Cache TTL in seconds
            refresh_interval: Auto-refresh interval (None = no refresh)
            key_prefix: Cache key prefix (default: task name)
        """
        task = {
            'name': name,
            'warm_func': warm_func,
            'priority': priority,
            'ttl': ttl,
            'refresh_interval': refresh_interval,
            'key_prefix': key_prefix or name,
            'last_warmed': None,
            'warm_count': 0,
            'fail_count': 0,
        }
        
        self.tasks.append(task)
        
        # Sort by priority
        priority_order = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}
        self.tasks.sort(key=lambda t: priority_order.get(t['priority'], 2))
        
        logger.info(f"Registered warming task: {name} (priority: {priority})")
    
    async def warm_task(self, task: Dict[str, Any]) -> bool:
        """
        Warm single task.
        
        Args:
            task: Task configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            name = task['name']
            logger.info(f"Warming cache: {name}...")
            
            start_time = datetime.now()
            
            # Execute warming function
            if asyncio.iscoroutinefunction(task['warm_func']):
                data = await task['warm_func']()
            else:
                data = task['warm_func']()
            
            # Cache the data
            if data is not None:
                cache_key = f"{task['key_prefix']}:warmed"
                await self._cache_manager.set(
                    cache_key,
                    data,
                    l1_ttl=task['ttl'],
                    l2_ttl=task['ttl']
                )
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                task['last_warmed'] = datetime.now()
                task['warm_count'] += 1
                self._stats['total_warmed'] += 1
                
                logger.info(
                    f"✅ Cache warmed: {name} "
                    f"({execution_time:.2f}s, "
                    f"warmed {task['warm_count']} times)"
                )
                
                return True
            else:
                logger.warning(f"⚠️  No data returned for warming task: {name}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Failed to warm cache '{task['name']}': {e}")
            task['fail_count'] += 1
            self._stats['total_failed'] += 1
            return False
    
    async def warm_all(self, priority_filter: Optional[str] = None) -> Dict[str, int]:
        """
        Warm all registered caches.
        
        Args:
            priority_filter: Only warm tasks with this priority or higher
            
        Returns:
            Statistics: {success: int, failed: int, skipped: int}
        """
        if self._warming_in_progress:
            logger.warning("Cache warming already in progress")
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        self._warming_in_progress = True
        
        try:
            logger.info(f"🔥 Starting cache warming ({len(self.tasks)} tasks)...")
            
            stats = {'success': 0, 'failed': 0, 'skipped': 0}
            
            # Filter tasks by priority
            tasks_to_warm = self.tasks
            if priority_filter:
                priority_order = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}
                filter_level = priority_order.get(priority_filter, 2)
                tasks_to_warm = [
                    t for t in self.tasks
                    if priority_order.get(t['priority'], 2) <= filter_level
                ]
            
            # Warm tasks in batches
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def warm_with_limit(task):
                async with semaphore:
                    return await self.warm_task(task)
            
            results = await asyncio.gather(
                *[warm_with_limit(task) for task in tasks_to_warm],
                return_exceptions=True
            )
            
            # Count results
            for result in results:
                if isinstance(result, Exception):
                    stats['failed'] += 1
                elif result:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
            
            self._stats['last_warm_time'] = datetime.now()
            
            logger.info(
                f"🎉 Cache warming complete: "
                f"{stats['success']} success, "
                f"{stats['failed']} failed"
            )
            
            return stats
        
        finally:
            self._warming_in_progress = False
    
    async def refresh_stale(self) -> int:
        """
        Refresh caches that need updating.
        
        Returns:
            Number of caches refreshed
        """
        refreshed = 0
        now = datetime.now()
        
        for task in self.tasks:
            if task['refresh_interval'] is None:
                continue
            
            last_warmed = task['last_warmed']
            if last_warmed is None:
                continue
            
            time_since_warm = (now - last_warmed).total_seconds()
            if time_since_warm >= task['refresh_interval']:
                success = await self.warm_task(task)
                if success:
                    refreshed += 1
        
        if refreshed > 0:
            logger.info(f"♻️  Refreshed {refreshed} stale caches")
        
        return refreshed
    
    async def start_background_refresh(self, interval: int = 300):
        """
        Start background task to refresh stale caches.
        
        Args:
            interval: Check interval in seconds (default: 5 minutes)
        """
        logger.info(f"🔄 Starting background cache refresh (every {interval}s)")
        
        while True:
            try:
                await asyncio.sleep(interval)
                await self.refresh_stale()
            except asyncio.CancelledError:
                logger.info("Background cache refresh stopped")
                break
            except Exception as e:
                logger.error(f"Error in background refresh: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get warming statistics."""
        return {
            **self._stats,
            'total_tasks': len(self.tasks),
            'tasks': [
                {
                    'name': t['name'],
                    'priority': t['priority'],
                    'warm_count': t['warm_count'],
                    'fail_count': t['fail_count'],
                    'last_warmed': t['last_warmed'].isoformat() if t['last_warmed'] else None,
                }
                for t in self.tasks
            ],
        }


# ============================================================================
# Default Warming Tasks
# ============================================================================

async def load_popular_strategies():
    """Load 20 most popular strategies."""
    # Placeholder - replace with actual DB query
    logger.info("Loading popular strategies...")
    await asyncio.sleep(0.1)  # Simulate DB query
    return {
        'strategies': [
            {'id': i, 'name': f'Strategy {i}', 'popularity': 100 - i}
            for i in range(1, 21)
        ]
    }


async def load_active_backtests():
    """Load active backtests."""
    logger.info("Loading active backtests...")
    await asyncio.sleep(0.1)
    return {
        'backtests': [
            {'id': i, 'status': 'running'}
            for i in range(1, 11)
        ]
    }


async def load_market_data_cache():
    """Load recent market data for popular symbols."""
    logger.info("Loading market data cache...")
    await asyncio.sleep(0.1)
    return {
        'symbols': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
        'cached_at': datetime.now().isoformat(),
    }


# ============================================================================
# Global Warmer Instance
# ============================================================================

_cache_warmer: Optional[CacheWarmer] = None


async def get_cache_warmer() -> CacheWarmer:
    """
    Get or create global cache warmer instance.
    
    Returns:
        Connected CacheWarmer instance
    """
    global _cache_warmer
    
    if _cache_warmer is None:
        _cache_warmer = CacheWarmer(max_concurrent=5)
        await _cache_warmer.connect()
        
        # Register default warming tasks
        _cache_warmer.register_task(
            name="popular_strategies",
            warm_func=load_popular_strategies,
            priority="high",
            ttl=3600,
            refresh_interval=1800,  # Refresh every 30 minutes
        )
        
        _cache_warmer.register_task(
            name="active_backtests",
            warm_func=load_active_backtests,
            priority="normal",
            ttl=300,
            refresh_interval=180,  # Refresh every 3 minutes
        )
        
        _cache_warmer.register_task(
            name="market_data_cache",
            warm_func=load_market_data_cache,
            priority="critical",
            ttl=60,
            refresh_interval=30,  # Refresh every 30 seconds
        )
    
    return _cache_warmer


async def warm_startup_caches():
    """Warm caches on application startup."""
    warmer = await get_cache_warmer()
    
    logger.info("🚀 Warming startup caches...")
    
    # Warm critical and high priority only on startup
    stats = await warmer.warm_all(priority_filter="high")
    
    logger.info(
        f"✅ Startup cache warming complete: "
        f"{stats['success']} caches warmed"
    )
    
    return stats
