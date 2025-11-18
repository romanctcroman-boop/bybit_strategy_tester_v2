"""
Minimal Celery app wiring.

Environment variables:
- CELERY_BROKER_URL (default: memory:// for local/tests)
- CELERY_RESULT_BACKEND (default: rpc://)
- CELERY_EAGER ("1"/"0") run tasks inline for dev/tests (default: 0)
- CELERY_TASK_DEFAULT_QUEUE (default: "default")
- CELERY_ACKS_LATE ("1"/"0", default: 1) — require explicit ack after task execution
- CELERY_PREFETCH_MULTIPLIER (int, default: 4)
- CELERY_TASK_DEFAULT_RETRY_DELAY (seconds, default: 5)
- CELERY_TASK_MAX_RETRIES (int, default: 3)
"""

import os

from celery import Celery

broker_url = os.environ.get("CELERY_BROKER_URL", "memory://")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "rpc://")

celery_app = Celery("bybit_strategy_tester_v2", broker=broker_url, backend=result_backend)


# Reasonable defaults for local dev/tests
def _get_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    try:
        return int(v) if v is not None else default
    except Exception:
        return default


celery_app.conf.update(
    # Execution mode
    task_always_eager=_get_bool("CELERY_EAGER", False),
    # Queues & routing
    task_default_queue=os.environ.get("CELERY_TASK_DEFAULT_QUEUE", "default"),
    # Reliability & flow control
    task_acks_late=_get_bool("CELERY_ACKS_LATE", True),
    worker_prefetch_multiplier=_get_int("CELERY_PREFETCH_MULTIPLIER", 4),
    # Retries
    task_default_retry_delay=_get_int("CELERY_TASK_DEFAULT_RETRY_DELAY", 5),
    task_max_retries=_get_int("CELERY_TASK_MAX_RETRIES", 3),
    # Simple global rate limit example (opt-out per task)
    task_annotations={"*": {"rate_limit": "100/s"}},
)

__all__ = ["celery_app"]
