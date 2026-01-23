"""
Redis-based Trade Publisher Service

This service connects to Bybit WebSocket and publishes trades to Redis Pub/Sub.
Replaces singleton TickService for distributed architecture.

Architecture:
    Bybit WebSocket → TradePublisher → Redis Pub/Sub → Multiple Aggregators
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Set

import redis.asyncio as redis
import websockets

logger = logging.getLogger(__name__)


class TradePublisher:
    """
    Publishes trades from Bybit to Redis Pub/Sub.

    Single instance connects to Bybit, publishes to Redis channels:
    - "trades:{symbol}" - raw trade data for aggregators
    - "trades:stats" - statistics and health metrics

    This enables horizontal scaling:
    - Multiple aggregator processes can subscribe
    - Multiple WebSocket servers can serve clients
    - Decoupled architecture for better fault tolerance
    """

    BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/spot"

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None

        self._running = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_task: Optional[asyncio.Task] = None

        # Reconnection settings
        self._reconnect_delay = 5
        self._initial_reconnect_delay = 5
        self._max_reconnect_delay = 60
        self._reconnect_multiplier = 1.5

        # Subscribed symbols
        self._subscribed_symbols: Set[str] = set()

        # Statistics
        self._stats = {
            "trades_published": 0,
            "reconnects": 0,
            "last_trade_time": None,
            "uptime_start": None,
        }

    async def connect_redis(self):
        """Connect to Redis."""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
            logger.info(f"Connected to Redis: {self.redis_url}")

    async def start(self, symbols: list[str]):
        """Start the trade publisher."""
        if self._running:
            logger.warning("TradePublisher already running")
            return

        self._subscribed_symbols = set(symbols)
        self._running = True
        self._stats["uptime_start"] = datetime.now(timezone.utc).isoformat()

        await self.connect_redis()

        logger.info(f"Starting TradePublisher for symbols: {symbols}")
        self._ws_task = asyncio.create_task(self._ws_loop())

    async def stop(self):
        """Stop the trade publisher."""
        self._running = False

        if self._ws:
            await self._ws.close()

        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        if self.redis_client:
            await self.redis_client.close()

        logger.info("TradePublisher stopped")

    async def _ws_loop(self):
        """Main WebSocket loop with auto-reconnect."""
        while self._running:
            try:
                await self._connect_and_listen()
                # Successful connection - reset delay
                self._reconnect_delay = self._initial_reconnect_delay
                logger.info("Connection successful - reset reconnect delay")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self._stats["reconnects"] += 1

                # Exponential backoff
                self._reconnect_delay = min(
                    self._max_reconnect_delay,
                    self._reconnect_delay * self._reconnect_multiplier,
                )

            if self._running:
                logger.info(
                    f"Reconnecting in {self._reconnect_delay:.1f}s "
                    f"(attempt #{self._stats['reconnects']})..."
                )
                await asyncio.sleep(self._reconnect_delay)

    async def _connect_and_listen(self):
        """Connect to Bybit and listen for trades."""
        logger.info(f"Connecting to Bybit WebSocket: {self.BYBIT_WS_URL}")

        async with websockets.connect(
            self.BYBIT_WS_URL,
            ping_interval=30,
            ping_timeout=30,
            close_timeout=10,
        ) as ws:
            self._ws = ws

            # Subscribe to trade streams
            subscribe_msg = {
                "op": "subscribe",
                "args": [
                    f"publicTrade.{symbol}" for symbol in self._subscribed_symbols
                ],
            }
            await ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to: {subscribe_msg['args']}")

            # Listen for messages
            async for message in ws:
                await self._handle_message(message)

    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)

            # Check for trade data
            topic = data.get("topic", "")
            if topic.startswith("publicTrade."):
                symbol = topic.replace("publicTrade.", "")
                trades_data = data.get("data", [])

                for trade_data in trades_data:
                    await self._publish_trade(symbol, trade_data)

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def _publish_trade(self, symbol: str, trade_data: dict):
        """
        Publish trade to Redis Pub/Sub.

        Publishes to channel: "trades:{symbol}"
        Message format: JSON with timestamp, price, qty, side, trade_id
        """
        t0 = time.perf_counter()

        # Prepare trade message
        trade_msg = {
            "symbol": symbol,
            "timestamp": int(trade_data.get("T", 0)),
            "price": float(trade_data.get("p", 0)),
            "qty": float(trade_data.get("v", 0)),
            "side": trade_data.get("S", "Buy"),
            "trade_id": trade_data.get("i", ""),
        }

        # Publish to Redis
        channel = f"trades:{symbol}"
        await self.redis_client.publish(channel, json.dumps(trade_msg))

        self._stats["trades_published"] += 1
        self._stats["last_trade_time"] = datetime.now(timezone.utc).isoformat()

        # Log slow publishing (>5ms is suspicious)
        elapsed = (time.perf_counter() - t0) * 1000
        if elapsed > 5:
            logger.warning(f"Slow Redis publish: {elapsed:.2f}ms for {symbol}")

        # Publish stats every 1000 trades
        if self._stats["trades_published"] % 1000 == 0:
            await self._publish_stats()

    async def _publish_stats(self):
        """Publish statistics to Redis."""
        stats_msg = {
            "trades_published": self._stats["trades_published"],
            "reconnects": self._stats["reconnects"],
            "last_trade_time": self._stats["last_trade_time"],
            "uptime_start": self._stats["uptime_start"],
            "subscribed_symbols": list(self._subscribed_symbols),
        }
        await self.redis_client.publish("trades:stats", json.dumps(stats_msg))

    def get_stats(self) -> dict:
        """Get current statistics."""
        return {
            "running": self._running,
            "trades_published": self._stats["trades_published"],
            "reconnects": self._stats["reconnects"],
            "last_trade_time": self._stats["last_trade_time"],
            "subscribed_symbols": list(self._subscribed_symbols),
        }

    def is_running(self) -> bool:
        """Check if publisher is running."""
        return self._running


# Singleton instance
_trade_publisher: Optional[TradePublisher] = None


def get_trade_publisher(redis_url: str = "redis://localhost:6379") -> TradePublisher:
    """Get or create TradePublisher singleton."""
    global _trade_publisher
    if _trade_publisher is None:
        _trade_publisher = TradePublisher(redis_url)
    return _trade_publisher
