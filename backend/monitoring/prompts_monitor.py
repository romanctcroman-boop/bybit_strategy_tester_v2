"""
Prompts Monitoring Service

Provides monitoring and metrics for AI prompt system:
- Prompt validation stats
- Logging statistics
- Cache performance
- Cost tracking
- Temperature adaptation metrics

Usage:
    from backend.monitoring.prompts_monitor import PromptsMonitor
    monitor = PromptsMonitor()
    stats = monitor.get_dashboard()
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    log_db_path: str = "data/prompt_logs.db"
    cache_db_path: str = "data/prompt_cache.db"
    retention_days: int = 30
    refresh_interval_sec: int = 60


@dataclass
class DashboardMetrics:
    """Dashboard metrics snapshot."""
    timestamp: str
    period_hours: int
    
    # Prompt validation
    total_prompts: int = 0
    validated_prompts: int = 0
    failed_validations: int = 0
    validation_success_rate: float = 0.0
    injection_attempts_blocked: int = 0
    
    # Prompt logging
    total_logged: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_duration_ms: float = 0.0
    
    # Cache performance
    cache_size: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    
    # Temperature adaptation
    avg_temperature: float = 0.3
    min_temperature: float = 0.1
    max_temperature: float = 1.0
    
    # Compression
    prompts_compressed: int = 0
    tokens_saved: int = 0
    compression_ratio: float = 0.0
    
    # Agent breakdown
    by_agent: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Task breakdown
    by_task: dict[str, dict[str, Any]] = field(default_factory=dict)


class PromptsMonitor:
    """
    Monitoring service for AI prompt system.
    
    Provides:
    - Real-time metrics dashboard
    - Historical statistics
    - Cost tracking
    - Performance analysis
    
    Example:
        monitor = PromptsMonitor()
        dashboard = monitor.get_dashboard(period_hours=24)
        print(f"Validation success rate: {dashboard.validation_success_rate:.0%}")
    """
    
    def __init__(self, config: MonitoringConfig | None = None):
        """
        Initialize monitoring service.
        
        Args:
            config: Monitoring configuration
        """
        self.config = config or MonitoringConfig()
        self._prompt_logger = None
        self._cache = None
        
        # Metrics cache
        self._last_refresh: float = 0
        self._cached_metrics: DashboardMetrics | None = None
        
        logger.info("📊 PromptsMonitor initialized")
    
    def get_dashboard(self, period_hours: int = 24) -> DashboardMetrics:
        """
        Get monitoring dashboard.
        
        Args:
            period_hours: Period for statistics (default: 24 hours)
        
        Returns:
            DashboardMetrics with current statistics
        """
        # Check cache
        now = time.time()
        if (
            self._cached_metrics and
            self._cached_metrics.period_hours == period_hours and
            (now - self._last_refresh) < self.config.refresh_interval_sec
        ):
            return self._cached_metrics
        
        # Refresh metrics
        metrics = self._collect_metrics(period_hours)
        self._cached_metrics = metrics
        self._last_refresh = now
        
        return metrics
    
    def get_validation_stats(self, period_hours: int = 24) -> dict[str, Any]:
        """
        Get validation statistics.
        
        Args:
            period_hours: Period for statistics
        
        Returns:
            Validation stats dict
        """
        try:
            from backend.agents.prompts import PromptLogger
            prompt_logger = PromptLogger(db_path=self.config.log_db_path)
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(hours=period_hours)
            
            logs = prompt_logger.search_logs(
                start_date=start_date,
                end_date=end_date,
                limit=10000
            )
            
            total = len(logs)
            success = sum(1 for log in logs if log.success)
            failed = total - success
            
            # Count injection attempts (failed validations with specific errors)
            injection_attempts = sum(
                1 for log in logs
                if log.error_message and "Injection" in log.error_message
            )
            
            return {
                "total_prompts": total,
                "validated": total,
                "success": success,
                "failed": failed,
                "success_rate": success / total if total > 0 else 0.0,
                "injection_attempts_blocked": injection_attempts,
                "period_hours": period_hours,
            }
        except Exception as e:
            logger.error(f"Failed to get validation stats: {e}")
            return {
                "total_prompts": 0,
                "validated": 0,
                "success": 0,
                "failed": 0,
                "success_rate": 0.0,
                "injection_attempts_blocked": 0,
                "error": str(e),
            }
    
    def get_logging_stats(self, period_hours: int = 24) -> dict[str, Any]:
        """
        Get logging statistics.
        
        Args:
            period_hours: Period for statistics
        
        Returns:
            Logging stats dict
        """
        try:
            from backend.agents.prompts import PromptLogger
            prompt_logger = PromptLogger(db_path=self.config.log_db_path)
            
            stats = prompt_logger.get_stats(days=period_hours // 24 + 1)
            
            return {
                "total_logged": stats.get("total_requests", 0),
                "total_tokens": stats.get("total_tokens", 0),
                "total_cost_usd": stats.get("total_cost_usd", 0.0),
                "avg_duration_ms": stats.get("avg_duration_ms", 0.0),
                "success_rate": stats.get("success_rate", 0.0),
                "by_agent": stats.get("by_agent", {}),
                "by_task": stats.get("by_task", {}),
                "period_hours": period_hours,
            }
        except Exception as e:
            logger.error(f"Failed to get logging stats: {e}")
            return {
                "total_logged": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "avg_duration_ms": 0.0,
                "success_rate": 0.0,
                "error": str(e),
            }
    
    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Cache stats dict
        """
        try:
            from backend.agents.prompts import ContextCache
            cache = ContextCache()
            
            stats = cache.get_stats()
            
            return {
                "cache_size": stats.get("size", 0),
                "max_size": stats.get("max_size", 1000),
                "cache_hits": stats.get("hits", 0),
                "cache_misses": stats.get("misses", 0),
                "cache_hit_rate": stats.get("hit_rate", 0.0),
                "expiring_soon": stats.get("expiring_soon", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "cache_size": 0,
                "max_size": 1000,
                "cache_hits": 0,
                "cache_misses": 0,
                "cache_hit_rate": 0.0,
                "error": str(e),
            }
    
    def get_cost_breakdown(self, period_hours: int = 24) -> dict[str, Any]:
        """
        Get cost breakdown by agent and task.
        
        Args:
            period_hours: Period for statistics
        
        Returns:
            Cost breakdown dict
        """
        try:
            from backend.agents.prompts import PromptLogger
            prompt_logger = PromptLogger(db_path=self.config.log_db_path)
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(hours=period_hours)
            
            logs = prompt_logger.search_logs(
                start_date=start_date,
                end_date=end_date,
                limit=10000
            )
            
            # Group by agent
            by_agent: dict[str, dict[str, Any]] = {}
            for log in logs:
                agent = log.agent_type
                if agent not in by_agent:
                    by_agent[agent] = {
                        "count": 0,
                        "tokens": 0,
                        "cost": 0.0,
                    }
                by_agent[agent]["count"] += 1
                by_agent[agent]["tokens"] += log.tokens_used or 0
                by_agent[agent]["cost"] += log.cost_usd or 0.0
            
            # Group by task
            by_task: dict[str, dict[str, Any]] = {}
            for log in logs:
                task = log.task_type
                if task not in by_task:
                    by_task[task] = {
                        "count": 0,
                        "tokens": 0,
                        "cost": 0.0,
                    }
                by_task[task]["count"] += 1
                by_task[task]["tokens"] += log.tokens_used or 0
                by_task[task]["cost"] += log.cost_usd or 0.0
            
            return {
                "total_cost_usd": sum(a["cost"] for a in by_agent.values()),
                "by_agent": by_agent,
                "by_task": by_task,
                "period_hours": period_hours,
                "projected_monthly_cost": sum(a["cost"] for a in by_agent.values()) * (720 / period_hours),
            }
        except Exception as e:
            logger.error(f"Failed to get cost breakdown: {e}")
            return {
                "total_cost_usd": 0.0,
                "by_agent": {},
                "by_task": {},
                "error": str(e),
            }
    
    def get_performance_trends(self, period_hours: int = 24, intervals: int = 24) -> dict[str, Any]:
        """
        Get performance trends over time.
        
        Args:
            period_hours: Total period (default: 24 hours)
            intervals: Number of intervals (default: 24 = hourly)
        
        Returns:
            Trends dict with time series
        """
        try:
            from backend.agents.prompts import PromptLogger
            prompt_logger = PromptLogger(db_path=self.config.log_db_path)
            
            interval_hours = period_hours / intervals
            trends: list[dict[str, Any]] = []
            
            for i in range(intervals):
                end_date = datetime.utcnow() - timedelta(hours=i * interval_hours)
                start_date = end_date - timedelta(hours=interval_hours)
                
                logs = prompt_logger.search_logs(
                    start_date=start_date,
                    end_date=end_date,
                    limit=1000
                )
                
                trends.append({
                    "timestamp": start_date.isoformat(),
                    "count": len(logs),
                    "avg_duration_ms": sum(l.duration_ms or 0 for l in logs) / len(logs) if logs else 0,
                    "total_tokens": sum(l.tokens_used or 0 for l in logs),
                    "total_cost": sum(l.cost_usd or 0 for l in logs),
                })
            
            return {
                "trends": list(reversed(trends)),
                "period_hours": period_hours,
                "intervals": intervals,
            }
        except Exception as e:
            logger.error(f"Failed to get performance trends: {e}")
            return {
                "trends": [],
                "error": str(e),
            }
    
    def _collect_metrics(self, period_hours: int) -> DashboardMetrics:
        """Collect all metrics into dashboard."""
        validation = self.get_validation_stats(period_hours)
        logging_stats = self.get_logging_stats(period_hours)
        cache = self.get_cache_stats()
        cost = self.get_cost_breakdown(period_hours)
        
        return DashboardMetrics(
            timestamp=datetime.utcnow().isoformat(),
            period_hours=period_hours,
            
            # Validation
            total_prompts=validation.get("total_prompts", 0),
            validated_prompts=validation.get("validated", 0),
            failed_validations=validation.get("failed", 0),
            validation_success_rate=validation.get("success_rate", 0.0),
            injection_attempts_blocked=validation.get("injection_attempts_blocked", 0),
            
            # Logging
            total_logged=logging_stats.get("total_logged", 0),
            total_tokens=logging_stats.get("total_tokens", 0),
            total_cost_usd=logging_stats.get("total_cost_usd", 0.0),
            avg_duration_ms=logging_stats.get("avg_duration_ms", 0.0),
            
            # Cache
            cache_size=cache.get("cache_size", 0),
            cache_hits=cache.get("cache_hits", 0),
            cache_misses=cache.get("cache_misses", 0),
            cache_hit_rate=cache.get("cache_hit_rate", 0.0),
            
            # Cost breakdown
            by_agent=cost.get("by_agent", {}),
            by_task=cost.get("by_task", {}),
        )
    
    def export_dashboard(self, output_path: str, period_hours: int = 24) -> str:
        """
        Export dashboard to JSON file.
        
        Args:
            output_path: Output file path
            period_hours: Period for statistics
        
        Returns:
            Path to exported file
        """
        metrics = self.get_dashboard(period_hours)
        
        data = {
            "timestamp": metrics.timestamp,
            "period_hours": metrics.period_hours,
            "validation": {
                "total_prompts": metrics.total_prompts,
                "validated_prompts": metrics.validated_prompts,
                "failed_validations": metrics.failed_validations,
                "validation_success_rate": metrics.validation_success_rate,
                "injection_attempts_blocked": metrics.injection_attempts_blocked,
            },
            "logging": {
                "total_logged": metrics.total_logged,
                "total_tokens": metrics.total_tokens,
                "total_cost_usd": metrics.total_cost_usd,
                "avg_duration_ms": metrics.avg_duration_ms,
            },
            "cache": {
                "cache_size": metrics.cache_size,
                "cache_hits": metrics.cache_hits,
                "cache_misses": metrics.cache_misses,
                "cache_hit_rate": metrics.cache_hit_rate,
            },
            "by_agent": metrics.by_agent,
            "by_task": metrics.by_task,
        }
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📊 Dashboard exported to {output_path}")
        
        return output_path
