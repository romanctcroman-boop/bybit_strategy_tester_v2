"""
Redis Trade Broadcaster for Horizontal Scaling

Architecture for 5000+ WebSocket connections:

1. Single Bybit Listener (1 process):
   Bybit WS → Redis Pub/Sub "trades:{symbol}"

2. Multiple Uvicorn Workers (N processes):
   Redis "trades:{symbol}" → TickAggregator → WebSocket clients

This separates concerns:
- Only 1 connection to Bybit (rate limit friendly)
- Each worker handles ~800 connections
- 8 workers = 6400+ connections capacity

Usage:
    # Start broadcaster (separate process)
    python -m backend.services.tick_redis_broadcaster

    # Workers subscribe via:
    from backend.services.tick_redis_broadcaster import RedisTickSubscriber
    subscriber = RedisTickSubscriber(redis_url)
    await subscriber.start()
"""

import asyncio
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import redis.asyncio as redis
import websockets

from backend.core.metrics import get_metrics

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Trade from Bybit."""

    timestamp: int
    price: float
    qty: float
    side: str
    trade_id: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "price": self.price,
            "qty": self.qty,
            "side": self.side,
            "trade_id": self.trade_id,
        }

    @classmethod
    def from_bybit(cls, data: dict) -> "Trade":
        return cls(
            timestamp=int(data.get("T", 0)),
            price=float(data.get("p", 0)),
            qty=float(data.get("v", 0)),
            side=data.get("S", "Buy"),
            trade_id=data.get("i", ""),
        )


class RedisTradeBroadcaster:
    """
    Connects to Bybit and broadcasts trades to Redis.

    Run as a separate process - only 1 instance needed.
    """

    BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/spot"

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        symbols: list[str] = None,
    ):
        self.redis_url = redis_url
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT"]

        self.redis_client: redis.Redis | None = None
        self._running = False
        self._ws = None

        # Stats
        self._stats = {
            "trades_broadcast": 0,
            "reconnects": 0,
            "started_at": None,
        }

        # Reconnect settings
        self._reconnect_delay = 5
        self._max_reconnect_delay = 60

    async def start(self):
        """Start broadcaster."""
        self._running = True
        self._stats["started_at"] = datetime.now(UTC).isoformat()

        # Connect to Redis
        self.redis_client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        logger.info(f"RedisTradeBroadcaster started for: {self.symbols}")

        # Main loop with auto-reconnect
        while self._running:
            try:
                await self._connect_and_listen()
                self._reconnect_delay = 5  # Reset on success
            except Exception as e:
                logger.error(f"Bybit WS error: {e}")
                self._stats["reconnects"] += 1

                # Exponential backoff
                self._reconnect_delay = min(
                    self._max_reconnect_delay, self._reconnect_delay * 1.5
                )

            if self._running:
                logger.info(f"Reconnecting in {self._reconnect_delay:.1f}s...")
                await asyncio.sleep(self._reconnect_delay)

    async def stop(self):
        """Stop broadcaster."""
        self._running = False

        if self._ws:
            await self._ws.close()

        if self.redis_client:
            await self.redis_client.close()

        logger.info("RedisTradeBroadcaster stopped")

    async def _connect_and_listen(self):
        """Connect to Bybit and broadcast trades."""
        logger.info(f"Connecting to Bybit: {self.BYBIT_WS_URL}")

        async with websockets.connect(
            self.BYBIT_WS_URL,
            ping_interval=30,
            ping_timeout=30,
        ) as ws:
            self._ws = ws

            # Subscribe to trade streams
            subscribe_msg = {
                "op": "subscribe",
                "args": [f"publicTrade.{symbol}" for symbol in self.symbols],
            }
            await ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to: {subscribe_msg['args']}")

            # Listen and broadcast
            async for message in ws:
                await self._handle_message(message)

    async def _handle_message(self, message: str):
        """Handle Bybit message and broadcast to Redis."""
        try:
            data = json.loads(message)

            topic = data.get("topic", "")
            if topic.startswith("publicTrade."):
                symbol = topic.replace("publicTrade.", "")
                trades_data = data.get("data", [])

                # Batch publish for efficiency
                if trades_data:
                    pipe = self.redis_client.pipeline()
                    metrics = get_metrics()

                    for trade_data in trades_data:
                        trade = Trade.from_bybit(trade_data)
                        channel = f"trades:{symbol}"
                        pipe.publish(channel, json.dumps(trade.to_dict()))
                        self._stats["trades_broadcast"] += 1
                        metrics.tick_redis_message("publish")

                    await pipe.execute()

                    # Log periodically
                    if self._stats["trades_broadcast"] % 1000 == 0:
                        logger.info(
                            f"Broadcast {self._stats['trades_broadcast']} trades"
                        )

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def get_stats(self) -> dict:
        """Get broadcaster statistics."""
        return {
            **self._stats,
            "running": self._running,
            "symbols": self.symbols,
        }


class RedisTickSubscriber:
    """
    Subscribes to Redis trades and provides callbacks.

    Use in Uvicorn workers instead of direct Bybit connection.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        symbols: list[str] = None,
    ):
        self.redis_url = redis_url
        self.symbols = symbols or ["BTCUSDT"]

        self.redis_client: redis.Redis | None = None
        self.pubsub = None

        self._running = False
        self._task: asyncio.Task | None = None

        # Callbacks
        self._trade_callbacks: list[Callable[[str, Trade], None]] = []

        # Stats
        self._stats = {
            "trades_received": 0,
        }

    async def start(self):
        """Start subscribing to Redis trades."""
        if self._running:
            return

        self._running = True

        # Connect to Redis
        self.redis_client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        self.pubsub = self.redis_client.pubsub()

        # Subscribe to channels
        channels = [f"trades:{symbol}" for symbol in self.symbols]
        for channel in channels:
            await self.pubsub.subscribe(channel)

        logger.info(f"RedisTickSubscriber subscribed to: {channels}")

        # Start listen loop
        self._task = asyncio.create_task(self._listen_loop())

    async def stop(self):
        """Stop subscriber."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()

        if self.redis_client:
            await self.redis_client.close()

        logger.info("RedisTickSubscriber stopped")

    async def _listen_loop(self):
        """Listen to Redis and invoke callbacks."""
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    symbol = channel.replace("trades:", "")

                    try:
                        trade_data = json.loads(message["data"])
                        trade = Trade(
                            timestamp=trade_data["timestamp"],
                            price=trade_data["price"],
                            qty=trade_data["qty"],
                            side=trade_data["side"],
                            trade_id=trade_data["trade_id"],
                        )

                        self._stats["trades_received"] += 1

                        # Record Redis subscribe metric
                        get_metrics().tick_redis_message("subscribe")

                        # Invoke callbacks
                        for callback in self._trade_callbacks:
                            try:
                                callback(symbol, trade)
                            except Exception:
                                pass  # Isolate callback errors

                    except Exception as e:
                        logger.error(f"Error parsing trade: {e}")

        except asyncio.CancelledError:
            pass

    def add_trade_callback(self, callback: Callable[[str, Trade], None]):
        """Register callback for trades."""
        self._trade_callbacks.append(callback)

    def remove_trade_callback(self, callback: Callable[[str, Trade], None]):
        """Remove callback."""
        try:
            self._trade_callbacks.remove(callback)
        except ValueError:
            pass

    def get_stats(self) -> dict:
        """Get subscriber statistics."""
        return {
            **self._stats,
            "running": self._running,
            "symbols": self.symbols,
            "callbacks_count": len(self._trade_callbacks),
        }


# =============================================================================
# CLI Entry Point - Run as standalone broadcaster
# =============================================================================


async def main():
    """Run broadcaster as standalone process."""
    import signal

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    symbols = os.environ.get("TICK_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")

    broadcaster = RedisTradeBroadcaster(
        redis_url=redis_url,
        symbols=symbols,
    )

    # Handle shutdown
    loop = asyncio.get_running_loop()

    def shutdown():
        asyncio.create_task(broadcaster.stop())

    # Note: signal handling differs on Windows
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, shutdown)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass

    try:
        await broadcaster.start()
    except KeyboardInterrupt:
        await broadcaster.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
