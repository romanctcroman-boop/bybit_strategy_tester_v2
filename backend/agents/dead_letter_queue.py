"""Simple Dead Letter Queue (DLQ) shim used by agent code.

Provides a minimal async-compatible in-memory/file-backed queue with a small API:
- DLQMessage dataclass
- DLQPriority enum
- get_dlq() -> DLQ instance with async enqueue(message) method

This is intentionally lightweight and safe for application startup.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DLQPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class DLQMessage:
    message_id: str
    agent_type: str
    content: str
    context: dict[str, Any]
    error: str
    priority: DLQPriority = DLQPriority.NORMAL
    correlation_id: str | None = None


class _DLQ:
    def __init__(self, storage: Path | None = None):
        self._storage = storage or (Path.cwd() / "logs" / "dlq.jsonl")
        self._storage.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def enqueue(self, message: DLQMessage) -> bool:
        """Enqueue the message to a JSONL file (append)."""
        record = {
            "message_id": message.message_id,
            "agent_type": message.agent_type,
            "content": message.content,
            "context": message.context,
            "error": message.error,
            "priority": message.priority.value,
            "correlation_id": message.correlation_id,
        }

        async with self._lock:
            try:
                # Write synchronously inside lock to avoid concurrency issues
                with open(self._storage, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                logger.info(f"DLQ: enqueued message {message.message_id}")
                return True
            except Exception as e:
                logger.exception(f"DLQ: failed to enqueue message: {e}")
                return False


_dlq_instance: _DLQ | None = None


def get_dlq() -> _DLQ:
    global _dlq_instance
    if _dlq_instance is None:
        _dlq_instance = _DLQ()
    return _dlq_instance


__all__ = ["DLQMessage", "DLQPriority", "get_dlq"]
