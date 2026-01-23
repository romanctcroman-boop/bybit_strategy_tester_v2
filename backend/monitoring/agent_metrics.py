"""
Agent Metrics & Monitoring System
Система мониторинга производительности и качества агентов

Based on agent self-improvement recommendations:
- Метрики времени отклика агентов
- Успешность/неудачи коммуникаций
- Tool calling usage stats
- Guardrail metrics (корректность, следование инструкциям)
"""

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import redis.asyncio as redis
from loguru import logger

# When this module imports successfully, consumers like the unified agent
# interface expect a "metrics_enabled" flag to exist. Expose it here so
# "from backend.monitoring.agent_metrics import metrics_enabled" works.
metrics_enabled = True


class MetricType(Enum):
    """Типы метрик"""

    RESPONSE_TIME = "response_time"  # Время отклика агента (ms)
    SUCCESS_RATE = "success_rate"  # Успешность коммуникации
    TOOL_CALLING = "tool_calling"  # Использование tool calling
    CORRECTNESS = "correctness"  # Корректность ответов
    INSTRUCTION_FOLLOWING = "instruction_following"  # Следование инструкциям
    CONFIDENCE = "confidence"  # Уровень уверенности
    TOKEN_USAGE = "token_usage"  # Использование токенов
    ERROR_RATE = "error_rate"  # Частота ошибок


@dataclass
class AgentMetric:
    """Метрика агента"""

    agent_name: str
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["metric_type"] = self.metric_type.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMetric":
        data["metric_type"] = MetricType(data["metric_type"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class AgentPerformance:
    """Сводка производительности агента"""

    agent_name: str
    period_start: datetime
    period_end: datetime

    # Response time metrics
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0

    # Success metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0

    # Tool calling metrics
    tool_calls_made: int = 0
    tool_calls_successful: int = 0
    tool_call_success_rate: float = 0.0
    avg_iterations_per_request: float = 0.0

    # Quality metrics
    avg_confidence_score: float = 0.0
    total_tokens_used: int = 0
    avg_tokens_per_request: float = 0.0

    # Error analysis
    error_breakdown: dict[str, int] = field(default_factory=dict)
    most_common_error: str | None = None


class AgentMetricsCollector:
    """Коллектор метрик агентов"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis_client: redis.Redis | None = None

        # In-memory cache для быстрого доступа
        self._metrics_cache: dict[str, list[AgentMetric]] = defaultdict(list)
        self._cache_max_size = 1000

    async def _get_redis(self) -> redis.Redis:
        """Получить Redis клиент"""
        if self._redis_client is None:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis_client

    async def record_metric(self, metric: AgentMetric) -> None:
        """Записать метрику"""
        try:
            # Save to Redis
            redis_client = await self._get_redis()
            key = f"metrics:{metric.agent_name}:{metric.metric_type.value}"

            logger.debug(f"📝 Writing to Redis: key={key}")

            result = await redis_client.zadd(
                key, {json.dumps(metric.to_dict()): metric.timestamp.timestamp()}
            )

            logger.debug(f"✅ Redis zadd result: {result}")

            # Set expiration (30 days)
            await redis_client.expire(key, 30 * 24 * 3600)

            # Add to cache
            self._metrics_cache[metric.agent_name].append(metric)

            # Trim cache if too large
            if len(self._metrics_cache[metric.agent_name]) > self._cache_max_size:
                self._metrics_cache[metric.agent_name] = self._metrics_cache[
                    metric.agent_name
                ][-self._cache_max_size :]

            logger.debug(
                f"📊 Recorded metric: {metric.agent_name} - {metric.metric_type.value} = {metric.value}"
            )

        except Exception as e:
            logger.error(
                f"❌ Failed to record metric to Redis: {type(e).__name__}: {e}",
                exc_info=True,
            )

    async def record_response_time(
        self,
        agent_name: str,
        response_time_ms: float,
        success: bool,
        context: dict[str, Any] = None,
    ) -> None:
        """Записать время отклика"""
        await self.record_metric(
            AgentMetric(
                agent_name=agent_name,
                metric_type=MetricType.RESPONSE_TIME,
                value=response_time_ms,
                context={**(context or {}), "success": success},
            )
        )

        # Also record success/failure
        await self.record_metric(
            AgentMetric(
                agent_name=agent_name,
                metric_type=MetricType.SUCCESS_RATE,
                value=1.0 if success else 0.0,
                context=context or {},
            )
        )

    async def record_tool_calling(
        self,
        agent_name: str,
        tool_name: str,
        iterations: int,
        success: bool,
        context: dict[str, Any] = None,
    ) -> None:
        """Записать использование tool calling"""
        await self.record_metric(
            AgentMetric(
                agent_name=agent_name,
                metric_type=MetricType.TOOL_CALLING,
                value=float(iterations),
                context={
                    **(context or {}),
                    "tool_name": tool_name,
                    "success": success,
                    "iterations": iterations,
                },
            )
        )

    async def record_error(
        self,
        agent_name: str,
        error_type: str,
        error_message: str,
        context: dict[str, Any] = None,
    ) -> None:
        """Записать ошибку"""
        await self.record_metric(
            AgentMetric(
                agent_name=agent_name,
                metric_type=MetricType.ERROR_RATE,
                value=1.0,
                context={
                    **(context or {}),
                    "error_type": error_type,
                    "error_message": error_message[:200],  # Truncate
                },
            )
        )

    async def get_performance_summary(
        self, agent_name: str, period_hours: int = 24
    ) -> AgentPerformance:
        """
        Получить сводку производительности агента за период

        Args:
            agent_name: Имя агента
            period_hours: Период в часах

        Returns:
            AgentPerformance сводка
        """
        # Ensure Redis connection is available (used by _get_metrics_in_period)
        await self._get_redis()

        end_time = datetime.now()
        start_time = end_time - timedelta(hours=period_hours)

        performance = AgentPerformance(
            agent_name=agent_name, period_start=start_time, period_end=end_time
        )

        # Get response time metrics
        response_times = await self._get_metrics_in_period(
            agent_name, MetricType.RESPONSE_TIME, start_time, end_time
        )

        if response_times:
            values = [m.value for m in response_times]
            values.sort()

            performance.avg_response_time_ms = sum(values) / len(values)
            performance.min_response_time_ms = min(values)
            performance.max_response_time_ms = max(values)
            performance.p95_response_time_ms = (
                values[int(len(values) * 0.95)] if len(values) > 0 else 0.0
            )

        # Get success metrics
        success_metrics = await self._get_metrics_in_period(
            agent_name, MetricType.SUCCESS_RATE, start_time, end_time
        )

        if success_metrics:
            performance.total_requests = len(success_metrics)
            performance.successful_requests = sum(
                1 for m in success_metrics if m.value > 0.5
            )
            performance.failed_requests = (
                performance.total_requests - performance.successful_requests
            )
            performance.success_rate = (
                performance.successful_requests / performance.total_requests
                if performance.total_requests > 0
                else 0.0
            )

        # Get tool calling metrics
        tool_metrics = await self._get_metrics_in_period(
            agent_name, MetricType.TOOL_CALLING, start_time, end_time
        )

        if tool_metrics:
            performance.tool_calls_made = len(tool_metrics)
            performance.tool_calls_successful = sum(
                1 for m in tool_metrics if m.context.get("success", False)
            )
            performance.tool_call_success_rate = (
                performance.tool_calls_successful / performance.tool_calls_made
                if performance.tool_calls_made > 0
                else 0.0
            )

            iterations = [m.context.get("iterations", 1) for m in tool_metrics]
            performance.avg_iterations_per_request = (
                sum(iterations) / len(iterations) if iterations else 0.0
            )

        # Get error metrics
        error_metrics = await self._get_metrics_in_period(
            agent_name, MetricType.ERROR_RATE, start_time, end_time
        )

        if error_metrics:
            error_types = defaultdict(int)
            for m in error_metrics:
                error_type = m.context.get("error_type", "unknown")
                error_types[error_type] += 1

            performance.error_breakdown = dict(error_types)
            performance.most_common_error = (
                max(error_types, key=error_types.get) if error_types else None
            )

        return performance

    async def _get_metrics_in_period(
        self,
        agent_name: str,
        metric_type: MetricType,
        start_time: datetime,
        end_time: datetime,
    ) -> list[AgentMetric]:
        """Получить метрики за период"""
        redis_client = await self._get_redis()
        key = f"metrics:{agent_name}:{metric_type.value}"

        # Query Redis with time range
        results = await redis_client.zrangebyscore(
            key, start_time.timestamp(), end_time.timestamp()
        )

        metrics = []
        for result in results:
            try:
                data = json.loads(result)
                metrics.append(AgentMetric.from_dict(data))
            except Exception as e:
                logger.warning(f"Failed to parse metric: {e}")

        return metrics

    async def get_all_agents_summary(
        self, period_hours: int = 24
    ) -> dict[str, AgentPerformance]:
        """Получить сводку по всем агентам"""
        redis_client = await self._get_redis()

        # Find all agent names from metric keys
        keys = await redis_client.keys("metrics:*")
        agent_names = set()

        for key in keys:
            # Format: metrics:agent_name:metric_type
            parts = key.split(":")
            if len(parts) >= 2:
                agent_names.add(parts[1])

        summaries = {}
        for agent_name in agent_names:
            summaries[agent_name] = await self.get_performance_summary(
                agent_name, period_hours
            )

        return summaries

    async def close(self):
        """Закрыть соединения"""
        if self._redis_client:
            await self._redis_client.close()


# Global instance
_metrics_collector: AgentMetricsCollector | None = None


def get_metrics_collector() -> AgentMetricsCollector:
    """Получить глобальный экземпляр коллектора метрик"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = AgentMetricsCollector()
    return _metrics_collector


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def record_agent_call(
    agent_name: str,
    response_time_ms: float,
    success: bool,
    error: str | None = None,
    tool_calls: int | None = None,
    iterations: int | None = None,
    context: dict[str, Any] = None,
):
    """
    Convenience function для записи полного вызова агента

    Args:
        agent_name: Имя агента
        response_time_ms: Время отклика в миллисекундах
        success: Успешность вызова
        error: Сообщение об ошибке (если есть)
        tool_calls: Количество tool calls (если есть)
        iterations: Количество итераций (если есть)
        context: Дополнительный контекст
    """
    logger.info(
        f"📊 Recording metrics: agent={agent_name}, success={success}, time={response_time_ms:.2f}ms"
    )

    try:
        collector = get_metrics_collector()
        logger.debug(f"📊 Got metrics collector: {collector}")

        # Record response time and success
        await collector.record_response_time(
            agent_name=agent_name,
            response_time_ms=response_time_ms,
            success=success,
            context=context,
        )
        logger.info(f"✅ Metrics recorded successfully for {agent_name}")
    except Exception as e:
        logger.error(
            f"❌ Failed to record metrics: {type(e).__name__}: {e}", exc_info=True
        )

    # Record tool calling if applicable
    if tool_calls and iterations:
        await collector.record_tool_calling(
            agent_name=agent_name,
            tool_name=context.get("tool_name", "unknown") if context else "unknown",
            iterations=iterations,
            success=success,
            context=context,
        )

    # Record error if applicable
    if not success and error:
        await collector.record_error(
            agent_name=agent_name,
            error_type=type(error).__name__
            if isinstance(error, Exception)
            else "error",
            error_message=str(error),
            context=context,
        )


async def get_agent_performance(agent_name: str, hours: int = 24) -> AgentPerformance:
    """Получить производительность агента"""
    collector = get_metrics_collector()
    return await collector.get_performance_summary(agent_name, hours)


async def get_all_agents_performance(hours: int = 24) -> dict[str, AgentPerformance]:
    """Получить производительность всех агентов"""
    collector = get_metrics_collector()
    return await collector.get_all_agents_summary(hours)


def get_agent_metrics() -> dict[str, Any]:
    """
    Синхронная версия для получения текущих метрик агентов
    Используется в тестах
    """
    collector = get_metrics_collector()

    # Return basic metrics structure
    return {
        "total_calls": 0,  # Would need async to get real count
        "metrics_enabled": metrics_enabled,
        "collector_initialized": collector is not None,
        "last_update": datetime.now().isoformat(),
        "note": "Use async get_agent_performance() for detailed metrics",
    }
