"""
Backend Monitoring Module
Мониторинг производительности и метрики агентов
"""

from backend.monitoring.agent_metrics import (
    AgentMetric,
    AgentMetricsCollector,
    AgentPerformance,
    MetricType,
    get_agent_performance,
    get_all_agents_performance,
    get_metrics_collector,
    record_agent_call,
)
from backend.monitoring.db_monitor import (
    AlertThreshold,
    ComponentHealth,
    DatabaseHealth,
    DatabaseMonitor,
    HealthStatus,
    create_health_router,
)
from backend.monitoring.health_checks import (
    HealthChecker,
    HealthCheckResult,
    SystemHealthReport,
    get_health_checker,
    run_health_check,
)
from backend.monitoring.health_checks import HealthStatus as ComprehensiveHealthStatus
from backend.monitoring.self_learning_signal_service import (
    SelfLearningSignalPublisher,
)

__all__ = [
    "AgentMetric",
    # Agent metrics
    "AgentMetricsCollector",
    "AgentPerformance",
    "AlertThreshold",
    "ComponentHealth",
    "ComprehensiveHealthStatus",
    "DatabaseHealth",
    # Database monitoring
    "DatabaseMonitor",
    "HealthCheckResult",
    # Comprehensive health checks
    "HealthChecker",
    "HealthStatus",
    "MetricType",
    "SelfLearningSignalPublisher",
    "SystemHealthReport",
    "create_health_router",
    "get_agent_performance",
    "get_all_agents_performance",
    "get_health_checker",
    "get_metrics_collector",
    "record_agent_call",
    "run_health_check",
]
