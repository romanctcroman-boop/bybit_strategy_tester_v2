"""
Circuit Breaker Telemetry
Собирает и возвращает телеметрию о состоянии circuit breakers для всех агентов
"""

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def get_agent_breaker_snapshot() -> dict[str, Any]:
    """
    Получить snapshot состояния circuit breakers для всех агентов

    Returns:
        Словарь с состоянием всех circuit breakers:
        {
            "timestamp": "2025-12-04T12:00:00Z",
            "breakers": {
                "deepseek_api": {
                    "state": "closed",
                    "failure_count": 0,
                    "success_count": 42,
                    "last_failure_time": None
                },
                ...
            },
            "summary": {
                "total_breakers": 3,
                "open_breakers": 0,
                "healthy_breakers": 3
            }
        }
    """
    try:
        # Импортируем circuit manager
        from backend.agents.circuit_breaker_manager import get_circuit_manager

        circuit_manager = get_circuit_manager()
        status = circuit_manager.get_status()

        # Подсчет summary
        total_breakers = len(status)
        open_breakers = sum(1 for b in status.values() if b.get("state") == "open")
        healthy_breakers = sum(1 for b in status.values() if b.get("state") == "closed")

        snapshot = {
            "timestamp": datetime.now(UTC).isoformat(),
            "breakers": status,
            "summary": {
                "total_breakers": total_breakers,
                "open_breakers": open_breakers,
                "healthy_breakers": healthy_breakers,
                "degraded_breakers": total_breakers - open_breakers - healthy_breakers,
            },
        }

        return snapshot

    except Exception as e:
        logger.error(f"Failed to get circuit breaker snapshot: {e}", exc_info=True)
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "breakers": {},
            "summary": {
                "total_breakers": 0,
                "open_breakers": 0,
                "healthy_breakers": 0,
                "degraded_breakers": 0,
            },
            "error": str(e),
        }


def get_breaker_history(breaker_name: str, limit: int = 100) -> list[dict[str, Any]]:
    """
    Получить историю состояний circuit breaker

    Args:
        breaker_name: Имя breaker (например, "deepseek_api")
        limit: Максимальное количество записей

    Returns:
        Список записей истории состояний
    """
    try:
        import json

        import redis

        redis_client = redis.Redis(
            host="localhost", port=6379, db=0, decode_responses=True
        )
        history_key = f"breaker:history:{breaker_name}"

        # Get last N entries from Redis list
        raw_entries = redis_client.lrange(history_key, 0, limit - 1)

        history = []
        for entry in raw_entries:
            try:
                history.append(json.loads(entry))
            except json.JSONDecodeError:
                continue

        return history

    except ImportError:
        logger.debug("Redis not available for history tracking")
        return []
    except redis.ConnectionError:
        logger.debug("Redis connection failed for history tracking")
        return []
    except Exception as e:
        logger.warning(f"Failed to get breaker history: {e}")
        return []


def record_breaker_event(breaker_name: str, event_type: str, state: str, **metadata):
    """
    Record a circuit breaker event to history

    Args:
        breaker_name: Name of the breaker
        event_type: Type of event (state_change, failure, recovery)
        state: Current state of breaker
        **metadata: Additional event metadata
    """
    try:
        import json

        import redis

        redis_client = redis.Redis(
            host="localhost", port=6379, db=0, decode_responses=True
        )
        history_key = f"breaker:history:{breaker_name}"

        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "breaker": breaker_name,
            "event_type": event_type,
            "state": state,
            **metadata,
        }

        # Push to Redis list (newest first)
        redis_client.lpush(history_key, json.dumps(event))

        # Trim to keep only last 1000 events
        redis_client.ltrim(history_key, 0, 999)

        logger.debug(f"Recorded breaker event: {breaker_name} - {event_type}")

    except ImportError:
        pass  # Redis not available
    except redis.ConnectionError:
        pass  # Redis not connected
    except Exception as e:
        logger.warning(f"Failed to record breaker event: {e}")


def get_breaker_metrics(breaker_name: str) -> dict[str, Any]:
    """
    Получить детальные метрики для конкретного breaker

    Args:
        breaker_name: Имя breaker

    Returns:
        Детальные метрики breaker
    """
    try:
        from backend.agents.circuit_breaker_manager import get_circuit_manager

        circuit_manager = get_circuit_manager()

        if breaker_name not in circuit_manager.breakers:
            return {"error": f"Breaker '{breaker_name}' not found"}

        breaker = circuit_manager.breakers[breaker_name]

        return {
            "name": breaker_name,
            "state": breaker.state.value,
            "failure_count": breaker.failure_count,
            "success_count": breaker.success_count,
            "failure_threshold": breaker.failure_threshold,
            "recovery_timeout": breaker.recovery_timeout,
            "last_failure_time": breaker.last_failure_time.isoformat()
            if breaker.last_failure_time
            else None,
        }

    except Exception as e:
        logger.error(f"Failed to get breaker metrics for '{breaker_name}': {e}")
        return {"error": str(e)}


def reset_breaker(breaker_name: str) -> dict[str, Any]:
    """
    Сбросить состояние circuit breaker (вручную закрыть)

    Args:
        breaker_name: Имя breaker

    Returns:
        Результат операции
    """
    try:
        from backend.agents.circuit_breaker_manager import (
            CircuitState,
            get_circuit_manager,
        )

        circuit_manager = get_circuit_manager()

        if breaker_name not in circuit_manager.breakers:
            return {"success": False, "error": f"Breaker '{breaker_name}' not found"}

        breaker = circuit_manager.breakers[breaker_name]
        breaker.state = CircuitState.CLOSED
        breaker.failure_count = 0

        logger.info(f"✅ Circuit breaker '{breaker_name}' manually reset")

        return {
            "success": True,
            "breaker_name": breaker_name,
            "new_state": "closed",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to reset breaker '{breaker_name}': {e}")
        return {"success": False, "error": str(e)}


def reset_all_breakers() -> dict[str, Any]:
    """
    Сбросить все circuit breakers

    Returns:
        Результат операции
    """
    try:
        from backend.agents.circuit_breaker_manager import get_circuit_manager

        circuit_manager = get_circuit_manager()
        circuit_manager.reset_all()

        logger.info("✅ All circuit breakers reset")

        return {
            "success": True,
            "breakers_reset": len(circuit_manager.breakers),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to reset all breakers: {e}")
        return {"success": False, "error": str(e)}


__all__ = [
    "get_agent_breaker_snapshot",
    "get_breaker_history",
    "get_breaker_metrics",
    "reset_all_breakers",
    "reset_breaker",
]
