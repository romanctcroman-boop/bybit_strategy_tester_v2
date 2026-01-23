"""
Tick Chart Service - Real-time tick data aggregation.

Provides:
1. WebSocket connection to Bybit publicTrade stream
2. Tick aggregation into OHLCV candles (N ticks per bar)
3. Real-time streaming to frontend via WebSocket
4. Historical tick data storage (optional)
"""

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Deque, Dict, List, Optional, Set

import websockets

from backend.core.expiring_cache import ExpiringSet
from backend.core.metrics import get_metrics

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Single trade (tick) from Bybit."""

    timestamp: int  # milliseconds
    price: float
    qty: float
    side: str  # "Buy" or "Sell"
    trade_id: str

    @classmethod
    def from_bybit(cls, data: dict) -> "Trade":
        """Parse trade from Bybit WebSocket message."""
        return cls(
            timestamp=int(data.get("T", 0)),
            price=float(data.get("p", 0)),
            qty=float(data.get("v", 0)),
            side=data.get("S", "Buy"),
            trade_id=data.get("i", ""),
        )


@dataclass
class TickCandle:
    """Aggregated candle from N ticks."""

    tick_count: int  # N ticks per candle
    open_time: int  # First tick timestamp
    close_time: int  # Last tick timestamp
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
            "time": self.open_time // 1000,  # For LightweightCharts (seconds)
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "buy_volume": self.buy_volume,
            "sell_volume": self.sell_volume,
            "trade_count": self.trade_count,
        }


@dataclass
class TickAggregator:
    """Aggregates trades into tick candles."""

    ticks_per_bar: int = 100
    current_trades: List[Trade] = field(default_factory=list)
    completed_candles: Deque[TickCandle] = field(
        default_factory=lambda: deque(maxlen=1000)
    )
    # Cached values for current candle (avoid recalculating on each get)
    _current_high: float = 0.0
    _current_low: float = float("inf")
    _current_buy_vol: float = 0.0
    _current_sell_vol: float = 0.0

    def add_trade(self, trade: Trade) -> Optional[TickCandle]:
        """
        Add a trade and return completed candle if threshold reached.

        Returns:
            TickCandle if N trades accumulated, None otherwise
        """
        # Performance check: warn if processing takes too long
        # start_perf = time.perf_counter()

        self.current_trades.append(trade)

        # Update cached values incrementally
        if trade.price > self._current_high:
            self._current_high = trade.price
        if trade.price < self._current_low:
            self._current_low = trade.price
        if trade.side == "Buy":
            self._current_buy_vol += trade.qty
        else:
            self._current_sell_vol += trade.qty

        if len(self.current_trades) >= self.ticks_per_bar:
            candle = self._create_candle()
            self._reset_current()
            self.completed_candles.append(candle)
            return candle

        return None

    def _reset_current(self):
        """Reset current candle state."""
        self.current_trades.clear()
        self._current_high = 0.0
        self._current_low = float("inf")
        self._current_buy_vol = 0.0
        self._current_sell_vol = 0.0

    def _create_candle(self) -> TickCandle:
        """Create OHLCV candle from accumulated trades."""
        return TickCandle(
            tick_count=self.ticks_per_bar,
            open_time=self.current_trades[0].timestamp,
            close_time=self.current_trades[-1].timestamp,
            open=self.current_trades[0].price,
            high=self._current_high,
            low=self._current_low,
            close=self.current_trades[-1].price,
            volume=self._current_buy_vol + self._current_sell_vol,
            buy_volume=self._current_buy_vol,
            sell_volume=self._current_sell_vol,
            trade_count=len(self.current_trades),
        )

    def get_current_candle(self) -> Optional[dict]:
        """Get current incomplete candle for real-time updates."""
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
            "buy_volume": self._current_buy_vol,
            "sell_volume": self._current_sell_vol,
            "is_complete": False,
        }

    def get_history(self, limit: int = 100) -> List[dict]:
        """Get completed candles history."""
        candles = list(self.completed_candles)[-limit:]
        return [c.to_dict() for c in candles]


class TickService:
    """
    Main tick service managing WebSocket connections and aggregators.

    Supports multiple symbols and tick intervals (10T, 50T, 100T, etc.)

    Scaling modes:
    - Direct mode: Each worker connects to Bybit (default, max ~700 connections)
    - Redis mode: Workers subscribe to Redis, 1 broadcaster connects to Bybit
                 (for 5000+ connections)
    """

    BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/spot"
    MAX_AGGREGATORS = 500  # Increased to handle 5000 concurrent connections

    def __init__(
        self, use_redis: bool = False, redis_url: str = "redis://localhost:6379"
    ):
        self._running = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._reconnect_delay = 5
        self._initial_reconnect_delay = 5
        self._max_reconnect_delay = 60
        self._reconnect_multiplier = 1.5

        # Redis mode for horizontal scaling
        self._use_redis = use_redis
        self._redis_url = redis_url
        self._redis_subscriber = None

        # Aggregators per symbol and tick count
        # Key: (symbol, ticks_per_bar), Value: TickAggregator
        self._aggregators: Dict[tuple, TickAggregator] = {}

        # OPTIMIZATION: Index for fast lookup by symbol
        # Instead of looping through all 500 aggregators for each trade,
        # we maintain a symbol-based index for O(1) lookup
        self._aggregators_by_symbol: Dict[
            str, List[tuple]
        ] = {}  # symbol -> [(symbol, ticks), ...]

        # Subscribed symbols
        self._subscribed_symbols: Set[str] = set()

        # Callbacks for new candles
        self._candle_callbacks: List[Callable[[str, int, TickCandle], None]] = []

        # Callbacks for trade updates (real-time)
        self._trade_callbacks: List[Callable[[str, Trade], None]] = []

        # Recent trades buffer per symbol
        self._recent_trades: Dict[str, Deque[Trade]] = {}

        # Trade deduplication - ExpiringSet with 60s TTL, max 100k trades
        # Prevents duplicate trades (e.g., reconnection, Redis retry)
        self._seen_trades = ExpiringSet(ttl_seconds=60.0, max_size=100000)

        # Stats
        self._stats = {
            "trades_received": 0,
            "trades_duplicates": 0,
            "candles_created": 0,
            "reconnects": 0,
            "last_trade_time": None,
        }

    def get_aggregator(self, symbol: str, ticks_per_bar: int) -> TickAggregator:
        """Get or create aggregator for symbol and tick count."""
        key = (symbol, ticks_per_bar)

        if key not in self._aggregators:
            # Check aggregator limit to prevent memory leak
            if len(self._aggregators) >= self.MAX_AGGREGATORS:
                # Find oldest unused aggregator (least candles completed)
                oldest_key = min(
                    self._aggregators.keys(),
                    key=lambda k: len(self._aggregators[k].completed_candles),
                )
                logger.warning(
                    f"Aggregator limit ({self.MAX_AGGREGATORS}) reached. "
                    f"Removing aggregator for {oldest_key}"
                )
                # Remove from index
                old_symbol = oldest_key[0]
                if old_symbol in self._aggregators_by_symbol:
                    self._aggregators_by_symbol[old_symbol].remove(oldest_key)
                    if not self._aggregators_by_symbol[old_symbol]:
                        del self._aggregators_by_symbol[old_symbol]

                del self._aggregators[oldest_key]

            self._aggregators[key] = TickAggregator(ticks_per_bar=ticks_per_bar)

            # Update symbol index for O(1) lookup
            if symbol not in self._aggregators_by_symbol:
                self._aggregators_by_symbol[symbol] = []
            self._aggregators_by_symbol[symbol].append(key)

            logger.info(
                f"Created new aggregator for {symbol} with {ticks_per_bar} ticks/bar"
            )

        return self._aggregators[key]

    async def start(self, symbols: List[str] = None):
        """Start the tick service."""
        if self._running:
            logger.warning("TickService already running")
            return

        symbols = symbols or ["BTCUSDT"]
        self._subscribed_symbols = set(symbols)
        self._running = True

        if self._use_redis:
            # Redis mode: Subscribe to Redis instead of Bybit
            logger.info(f"Starting TickService in REDIS mode for symbols: {symbols}")
            await self._start_redis_subscriber(symbols)
        else:
            # Direct mode: Connect to Bybit directly
            logger.info(f"Starting TickService in DIRECT mode for symbols: {symbols}")
            self._ws_task = asyncio.create_task(self._ws_loop())

    async def _start_redis_subscriber(self, symbols: List[str]):
        """Start Redis subscriber for horizontal scaling."""
        try:
            from backend.services.tick_redis_broadcaster import RedisTickSubscriber

            self._redis_subscriber = RedisTickSubscriber(
                redis_url=self._redis_url,
                symbols=symbols,
            )

            # Bridge Redis trades to our processing
            def on_redis_trade(symbol, trade):
                # Convert to our Trade type
                from backend.services.tick_service import Trade as LocalTrade

                local_trade = LocalTrade(
                    timestamp=trade.timestamp,
                    price=trade.price,
                    qty=trade.qty,
                    side=trade.side,
                    trade_id=trade.trade_id,
                )
                self._process_trade_sync(symbol, local_trade)

            self._redis_subscriber.add_trade_callback(on_redis_trade)
            await self._redis_subscriber.start()

            logger.info("Redis subscriber started successfully")

        except Exception as e:
            logger.error(f"Failed to start Redis subscriber: {e}")
            # Fallback to direct mode
            logger.info("Falling back to direct Bybit connection")
            self._use_redis = False
            self._ws_task = asyncio.create_task(self._ws_loop())

    async def stop(self):
        """Stop the tick service gracefully."""
        self._running = False
        logger.info("TickService stopping...")

        # Stop Redis subscriber if active
        if self._redis_subscriber:
            await self._redis_subscriber.stop()
            self._redis_subscriber = None

        if self._ws:
            await self._ws.close()

        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        logger.info("TickService stopped")

    async def graceful_shutdown(self, drain_timeout: float = 30.0):
        """
        Graceful shutdown with connection draining.

        1. Stop accepting new connections (set _running = False)
        2. Wait for existing connections to drain (up to drain_timeout)
        3. Force close remaining connections
        4. Clean up resources

        Args:
            drain_timeout: Maximum time to wait for connections to drain (seconds)
        """
        import time

        logger.info(f"Starting graceful shutdown (drain_timeout={drain_timeout}s)...")
        self._running = False

        # Give connections time to drain naturally
        start_time = time.time()
        drain_check_interval = 0.5  # Check every 500ms

        # Count active callbacks as proxy for active connections
        while (time.time() - start_time) < drain_timeout:
            active = len(self._trade_callbacks) + len(self._candle_callbacks)
            if active == 0:
                logger.info("All connections drained successfully")
                break
            logger.info(f"Waiting for {active} callbacks to drain...")
            await asyncio.sleep(drain_check_interval)

        remaining = len(self._trade_callbacks) + len(self._candle_callbacks)
        if remaining > 0:
            logger.warning(
                f"Force closing {remaining} remaining callbacks after timeout"
            )

        # Force stop
        await self.stop()
        logger.info("Graceful shutdown complete")

    async def _ws_loop(self):
        """Main WebSocket loop with auto-reconnect and exponential backoff."""
        while self._running:
            try:
                await self._connect_and_listen()
                # Successful connection - reset delay to initial value
                self._reconnect_delay = self._initial_reconnect_delay
                logger.info("Connection successful - reset reconnect delay")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self._stats["reconnects"] += 1

                # Exponential backoff: increase delay after each failure
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
                    trade = Trade.from_bybit(trade_data)
                    self._process_trade_sync(symbol, trade)

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _process_trade_sync(self, symbol: str, trade: Trade):
        """Process a single trade - synchronous, fast.

        OPTIMIZATION: Direct lookup instead of O(n) loop over all aggregators.
        Old: Loop all aggregators per trade (500 × 1360/s = 680k ops/s)
        New: Direct dict lookup by symbol O(1)

        DEDUPLICATION: Uses ExpiringSet to skip duplicates on reconnection.
        """
        t0 = time.perf_counter()

        # Check for duplicate trade (prevents double-counting on reconnection)
        trade_key = f"{symbol}:{trade.trade_id}"
        if not self._seen_trades.add(trade_key):
            # Duplicate trade, skip
            self._stats["trades_duplicates"] += 1
            return

        self._stats["trades_received"] += 1
        self._stats["last_trade_time"] = datetime.now(timezone.utc).isoformat()

        # Store in recent trades
        if symbol not in self._recent_trades:
            self._recent_trades[symbol] = deque(maxlen=1000)
        self._recent_trades[symbol].append(trade)

        # Record trade metric
        metrics = get_metrics()
        metrics.tick_trade_processed(symbol)

        # Notify trade callbacks (quick, non-blocking)
        for callback in self._trade_callbacks:
            try:
                callback(symbol, trade)
            except Exception:
                pass  # Ignore errors, don't slow down

        # OPTIMIZATION: Use symbol index for O(1) lookup
        # Old: for (sym, ticks), agg in aggregators.items(): O(n) = 680k ops/s
        # New: Direct lookup via index - O(1)
        if symbol in self._aggregators_by_symbol:
            for key in self._aggregators_by_symbol[symbol]:
                aggregator = self._aggregators[key]
                _, ticks_per_bar = key

                candle = aggregator.add_trade(trade)
                if candle:
                    self._stats["candles_created"] += 1
                    # Record candle creation metric
                    metrics.tick_candle_created(symbol, f"{ticks_per_bar}T")
                    # Notify candle callbacks
                    for callback in self._candle_callbacks:
                        try:
                            callback(symbol, ticks_per_bar, candle)
                        except Exception:
                            pass  # Ignore errors, don't slow down

        # Log slow processing (over 5ms is suspicious for a single trade)
        dt = time.perf_counter() - t0
        if dt > 0.005:
            logger.warning(f"Slow trade processing for {symbol}: {dt * 1000:.2f}ms")

        # Record processing latency
        metrics.tick_processing_latency(symbol, dt)

    def add_candle_callback(self, callback: Callable[[str, int, TickCandle], None]):
        """Register callback for new completed candles."""
        self._candle_callbacks.append(callback)

    def remove_candle_callback(self, callback: Callable[[str, int, TickCandle], None]):
        """Unregister callback for completed candles. Prevents memory leaks."""
        try:
            self._candle_callbacks.remove(callback)
        except ValueError:
            pass  # Callback not found, ignore

    def add_trade_callback(self, callback: Callable[[str, Trade], None]):
        """Register callback for real-time trades."""
        self._trade_callbacks.append(callback)

    def remove_trade_callback(self, callback: Callable[[str, Trade], None]):
        """Unregister callback for trades. Prevents memory leaks."""
        try:
            self._trade_callbacks.remove(callback)
        except ValueError:
            pass  # Callback not found, ignore

    def get_tick_candles(
        self, symbol: str, ticks_per_bar: int = 100, limit: int = 100
    ) -> List[dict]:
        """Get tick candles for symbol."""
        aggregator = self.get_aggregator(symbol, ticks_per_bar)
        return aggregator.get_history(limit)

    def get_current_candle(
        self, symbol: str, ticks_per_bar: int = 100
    ) -> Optional[dict]:
        """Get current incomplete candle."""
        aggregator = self.get_aggregator(symbol, ticks_per_bar)
        return aggregator.get_current_candle()

    def get_recent_trades(self, symbol: str, limit: int = 100) -> List[dict]:
        """Get recent trades for symbol."""
        trades = self._recent_trades.get(symbol, deque())
        return [
            {
                "timestamp": t.timestamp,
                "price": t.price,
                "qty": t.qty,
                "side": t.side,
                "trade_id": t.trade_id,
            }
            for t in list(trades)[-limit:]
        ]

    def get_stats(self) -> dict:
        """Get service statistics including callback counts for leak detection."""
        # Update Prometheus gauges
        metrics = get_metrics()
        metrics.tick_set_aggregators(len(self._aggregators))
        metrics.tick_set_callbacks("trade", len(self._trade_callbacks))
        metrics.tick_set_callbacks("candle", len(self._candle_callbacks))

        return {
            **self._stats,
            "running": self._running,
            "mode": "redis" if self._use_redis else "direct",
            "subscribed_symbols": list(self._subscribed_symbols),
            # Callback counts - useful for detecting memory leaks
            "trade_callbacks_count": len(self._trade_callbacks),
            "candle_callbacks_count": len(self._candle_callbacks),
            "aggregators_count": len(self._aggregators),
            "aggregators": [
                {
                    "symbol": s,
                    "ticks_per_bar": t,
                    "history_count": len(a.completed_candles),
                }
                for (s, t), a in self._aggregators.items()
            ],
            # Deduplication stats
            "deduplication": self._seen_trades.get_stats(),
        }

    def is_running(self) -> bool:
        """Check if tick service is running."""
        return self._running

    @property
    def use_redis(self) -> bool:
        """Check if Redis mode is enabled for horizontal scaling."""
        return self._use_redis


# Singleton instance
_tick_service: Optional[TickService] = None


def get_tick_service(use_redis: bool = None, redis_url: str = None) -> TickService:
    """Get the singleton TickService instance.

    Args:
        use_redis: Enable Redis mode for horizontal scaling (5000+ connections)
        redis_url: Redis connection URL

    For production scaling:
        1. Start Redis broadcaster: python -m backend.services.tick_redis_broadcaster
        2. Configure workers: get_tick_service(use_redis=True)
    """
    global _tick_service

    if _tick_service is None:
        # Check environment for Redis mode
        import os

        _use_redis = (
            use_redis
            if use_redis is not None
            else os.environ.get("TICK_USE_REDIS", "").lower() == "true"
        )
        _redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")

        _tick_service = TickService(use_redis=_use_redis, redis_url=_redis_url)

        if _use_redis:
            logger.info("TickService created in REDIS mode for horizontal scaling")
        else:
            logger.info("TickService created in DIRECT mode (single worker)")

    return _tick_service


def setup_signal_handlers():
    """
    Setup SIGTERM/SIGINT handlers for graceful shutdown.

    Call this from app startup to enable graceful shutdown on container termination.

    Usage:
        from backend.services.tick_service import setup_signal_handlers
        setup_signal_handlers()
    """
    import signal

    def handle_shutdown(signum, frame):
        signame = signal.Signals(signum).name
        logger.info(f"Received {signame}, initiating graceful shutdown...")

        service = get_tick_service()
        if service.is_running():
            # Create task for async shutdown
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(service.graceful_shutdown(drain_timeout=30.0))
                else:
                    loop.run_until_complete(
                        service.graceful_shutdown(drain_timeout=30.0)
                    )
            except Exception as e:
                logger.error(f"Error during graceful shutdown: {e}")

    # Register handlers (Windows doesn't have SIGTERM, use SIGINT)
    signal.signal(signal.SIGINT, handle_shutdown)
    try:
        signal.signal(signal.SIGTERM, handle_shutdown)
    except (ValueError, OSError):
        # SIGTERM not available on Windows in some contexts
        pass

    logger.info("Signal handlers registered for graceful shutdown")
