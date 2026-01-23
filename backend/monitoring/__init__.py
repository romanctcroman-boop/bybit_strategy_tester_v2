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
from backend.monitoring.self_learning_signal_service import (
    SelfLearningSignalPublisher,
)

__all__ = [
    # Agent metrics
    "AgentMetricsCollector",
    "AgentMetric",
    "AgentPerformance",
    "MetricType",
    "get_metrics_collector",
    "record_agent_call",
    "get_agent_performance",
    "get_all_agents_performance",
    "SelfLearningSignalPublisher",
    # Database monitoring
    "DatabaseMonitor",
    "DatabaseHealth",
    "ComponentHealth",
    "HealthStatus",
    "AlertThreshold",
    "create_health_router",
]
