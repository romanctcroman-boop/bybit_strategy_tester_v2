"""
WebSocket Scaling Service — Redis Pub/Sub for Multi-Instance Deployment.

Provides a high-level broadcast channel for real-time updates across
multiple Uvicorn workers/processes. Builds on top of the existing
``tick_redis_broadcaster.py`` for trade data, and extends it to handle:

- Backtest progress updates
- Strategy generation notifications
- System alerts and health broadcasts
- Pipeline job status changes

Architecture::

    Worker 1 ──┐                     ┌── Client A
    Worker 2 ──┤ ← Redis Pub/Sub → ──┤── Client B
    Worker 3 ──┘   (channels)        └── Client C

Usage::

    from backend.services.ws_scaling import WSBroadcaster

    broadcaster = WSBroadcaster()
    await broadcaster.publish("backtest:progress", {"id": "abc", "pct": 75})
    # All workers receive and forward to their connected WebSocket clients

    async for message in broadcaster.subscribe("backtest:*"):
        await websocket.send_json(message)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Default channel prefix for all broadcast messages
_CHANNEL_PREFIX = "bybit:ws:"

# Supported broadcast channels
CHANNELS = {
    "backtest:progress": "Backtest progress updates (pct, stage)",
    "backtest:complete": "Backtest completed with summary metrics",
    "pipeline:status": "AI pipeline job status changes",
    "strategy:generated": "New strategy generated notification",
    "alert:system": "System-wide alerts (health, errors)",
    "market:update": "Market data updates (aggregated)",
}


@dataclass
class BroadcastMessage:
    """A message published to the broadcast channel."""

    channel: str
    data: dict[str, Any]
    sender_id: str = ""
    timestamp: float = 0.0

    def to_json(self) -> str:
        """Serialize to JSON string."""
        import time

        return json.dumps(
            {
                "channel": self.channel,
                "data": self.data,
                "sender_id": self.sender_id,
                "timestamp": self.timestamp or time.time(),
            }
        )

    @classmethod
    def from_json(cls, raw: str | bytes) -> BroadcastMessage:
        """Deserialize from JSON string."""
        payload = json.loads(raw)
        return cls(
            channel=payload.get("channel", ""),
            data=payload.get("data", {}),
            sender_id=payload.get("sender_id", ""),
            timestamp=payload.get("timestamp", 0),
        )


class WSBroadcaster:
    """
    Redis Pub/Sub broadcaster for multi-worker WebSocket delivery.

    Publishes messages to Redis channels so ALL Uvicorn workers can
    forward them to their locally connected WebSocket clients.

    Falls back to in-process asyncio.Queue when Redis is unavailable.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url: str = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._redis: Any = None
        self._pubsub: Any = None
        self._local_queues: dict[str, list[asyncio.Queue]] = {}
        self._worker_id = f"worker-{os.getpid()}"

    async def _get_redis(self):
        """Lazy-connect to Redis."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = await aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                )
                await self._redis.ping()
                logger.info("WSBroadcaster connected to Redis: %s", self._redis_url)
            except Exception as e:
                logger.warning("WSBroadcaster Redis unavailable (%s), using local queues", e)
                self._redis = None
        return self._redis

    async def publish(self, channel: str, data: dict[str, Any]) -> int:
        """
        Publish a message to a broadcast channel.

        Args:
            channel: Channel name (e.g., "backtest:progress").
            data: Message payload dict.

        Returns:
            Number of subscribers that received the message.
        """
        msg = BroadcastMessage(
            channel=channel,
            data=data,
            sender_id=self._worker_id,
        )

        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                full_channel = f"{_CHANNEL_PREFIX}{channel}"
                count = await redis_client.publish(full_channel, msg.to_json())
                logger.debug("Published to %s (%d subscribers)", full_channel, count)
                return count
            except Exception as e:
                logger.warning("Redis publish error: %s, falling back to local", e)

        # Local fallback: deliver to in-process subscribers
        queues = self._local_queues.get(channel, [])
        for q in queues:
            await q.put(msg)
        return len(queues)

    async def subscribe(self, channel: str) -> AsyncIterator[BroadcastMessage]:
        """
        Subscribe to a broadcast channel and yield messages.

        Args:
            channel: Channel name or pattern (e.g., "backtest:*").

        Yields:
            BroadcastMessage instances as they arrive.
        """
        redis_client = await self._get_redis()

        if redis_client is not None:
            try:
                pubsub = redis_client.pubsub()
                full_channel = f"{_CHANNEL_PREFIX}{channel}"

                if "*" in channel:
                    await pubsub.psubscribe(full_channel)
                else:
                    await pubsub.subscribe(full_channel)

                logger.info("Subscribed to %s", full_channel)

                async for raw_msg in pubsub.listen():
                    if raw_msg["type"] in ("message", "pmessage"):
                        try:
                            yield BroadcastMessage.from_json(raw_msg["data"])
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning("Invalid broadcast message: %s", e)
                return
            except Exception as e:
                logger.warning("Redis subscribe error: %s, using local queue", e)

        # Local fallback
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._local_queues.setdefault(channel, []).append(queue)
        try:
            while True:
                msg = await queue.get()
                yield msg
        finally:
            self._local_queues.get(channel, []).remove(queue)

    async def close(self) -> None:
        """Close Redis connection and clean up."""
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis:
            await self._redis.close()
            self._redis = None
        self._local_queues.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_broadcaster: WSBroadcaster | None = None


def get_ws_broadcaster() -> WSBroadcaster:
    """Get or create the global WSBroadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = WSBroadcaster()
    return _broadcaster
