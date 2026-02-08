"""
Redis-based Tick Aggregator Service

Subscribes to Redis trades and aggregates them into tick candles.
Publishes completed candles back to Redis for WebSocket servers.

Architecture:
    Redis "trades:{symbol}" → TickAggregatorService → Redis "candles:{symbol}:{ticks}"
"""

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass

import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Trade data from Redis."""

    timestamp: int
    price: float
    qty: float
    side: str
    trade_id: str

    @classmethod
    def from_dict(cls, data: dict) -> "Trade":
        return cls(
            timestamp=data["timestamp"],
            price=data["price"],
            qty=data["qty"],
            side=data["side"],
            trade_id=data["trade_id"],
        )


@dataclass
class TickCandle:
    """Aggregated tick candle."""

    tick_count: int
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: float
    sell_volume: float
    trade_count: int

    def to_dict(self) -> dict:
        return {
            "tick_count": self.tick_count,
            "open_time": self.open_time,
            "close_time": self.close_time,
            "time": self.open_time // 1000,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "buy_volume": self.buy_volume,
            "sell_volume": self.sell_volume,
            "trade_count": self.trade_count,
        }


class TickAggregator:
    """Aggregates trades into tick candles."""

    def __init__(self, ticks_per_bar: int = 100):
        self.ticks_per_bar = ticks_per_bar
        self.current_trades: list[Trade] = []
        self.completed_candles: deque[TickCandle] = deque(
            maxlen=500
        )  # Reduced for memory

        # Cached incremental values
        self._current_high = 0.0
        self._current_low = float("inf")
        self._current_buy_vol = 0.0
        self._current_sell_vol = 0.0

    def add_trade(self, trade: Trade) -> TickCandle | None:
        """Add trade and return candle if complete."""
        self.current_trades.append(trade)

        # Update incremental cache
        self._current_high = max(self._current_high, trade.price)
        self._current_low = min(self._current_low, trade.price)
        if trade.side == "Buy":
            self._current_buy_vol += trade.qty
        else:
            self._current_sell_vol += trade.qty

        # Check if candle is complete
        if len(self.current_trades) >= self.ticks_per_bar:
            candle = self._create_candle()

            # Reset
            self.current_trades.clear()
            self._current_high = 0.0
            self._current_low = float("inf")
            self._current_buy_vol = 0.0
            self._current_sell_vol = 0.0

            return candle

        return None

    def _create_candle(self) -> TickCandle:
        """Create candle from accumulated trades."""
        first_trade = self.current_trades[0]
        last_trade = self.current_trades[-1]

        return TickCandle(
            tick_count=self.ticks_per_bar,
            open_time=first_trade.timestamp,
            close_time=last_trade.timestamp,
            open=first_trade.price,
            high=self._current_high,
            low=self._current_low,
            close=last_trade.price,
            volume=self._current_buy_vol + self._current_sell_vol,
            buy_volume=self._current_buy_vol,
            sell_volume=self._current_sell_vol,
            trade_count=len(self.current_trades),
        )

    def get_current_candle_progress(self) -> dict | None:
        """Get current incomplete candle for progress tracking."""
        if not self.current_trades:
            return None

        return {
            "tick_count": self.ticks_per_bar,
            "current_ticks": len(self.current_trades),
            "progress_pct": (len(self.current_trades) / self.ticks_per_bar) * 100,
            "open_time": self.current_trades[0].timestamp,
            "time": self.current_trades[0].timestamp // 1000,
            "open": self.current_trades[0].price,
            "high": self._current_high,
            "low": self._current_low,
            "close": self.current_trades[-1].price,
            "volume": self._current_buy_vol + self._current_sell_vol,
            "is_complete": False,
        }


class TickAggregatorService:
    """
    Redis-based tick aggregator service.

    Subscribes to: "trades:{symbol}"
    Publishes to: "candles:{symbol}:{ticks}"
    """

    def __init__(
        self,
        symbol: str,
        ticks_per_bar: int,
        redis_url: str = "redis://localhost:6379",
    ):
        self.symbol = symbol
        self.ticks_per_bar = ticks_per_bar
        self.redis_url = redis_url

        self.redis_client: redis.Redis | None = None
        self.pubsub: redis.client.PubSub | None = None

        self.aggregator = TickAggregator(ticks_per_bar)

        self._running = False
        self._task: asyncio.Task | None = None

        # Stats
        self._stats = {
            "trades_received": 0,
            "candles_published": 0,
        }

    async def start(self):
        """Start aggregator service."""
        if self._running:
            logger.warning(f"Aggregator already running for {self.symbol}")
            return

        self._running = True

        # Connect to Redis
        self.redis_client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        logger.info(
            f"Started TickAggregator: {self.symbol}, {self.ticks_per_bar} ticks/bar"
        )

        # Start listening
        self._task = asyncio.create_task(self._listen_loop())

    async def stop(self):
        """Stop aggregator service."""
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

        logger.info(f"Stopped TickAggregator for {self.symbol}")

    async def _listen_loop(self):
        """Listen to Redis trades and aggregate."""
        self.pubsub = self.redis_client.pubsub()

        # Subscribe to trades channel
        channel = f"trades:{self.symbol}"
        await self.pubsub.subscribe(channel)
        logger.info(f"Subscribed to Redis channel: {channel}")

        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    await self._handle_trade_message(message["data"])
        except asyncio.CancelledError:
            pass

    async def _handle_trade_message(self, data: str):
        """Handle trade message from Redis."""
        try:
            trade_dict = json.loads(data)
            trade = Trade.from_dict(trade_dict)

            self._stats["trades_received"] += 1

            # Add to aggregator
            candle = self.aggregator.add_trade(trade)

            # Publish completed candle
            if candle:
                await self._publish_candle(candle)

        except Exception as e:
            logger.error(f"Error handling trade message: {e}")

    async def _publish_candle(self, candle: TickCandle):
        """Publish completed candle to Redis."""
        channel = f"candles:{self.symbol}:{self.ticks_per_bar}"
        message = json.dumps(candle.to_dict())

        await self.redis_client.publish(channel, message)

        self._stats["candles_published"] += 1

        if self._stats["candles_published"] % 10 == 0:
            logger.info(
                f"Aggregator {self.symbol}/{self.ticks_per_bar}: "
                f"{self._stats['candles_published']} candles published"
            )

    def get_stats(self) -> dict:
        """Get aggregator statistics."""
        return {
            "symbol": self.symbol,
            "ticks_per_bar": self.ticks_per_bar,
            "trades_received": self._stats["trades_received"],
            "candles_published": self._stats["candles_published"],
            "running": self._running,
        }
