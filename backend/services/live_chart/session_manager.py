"""
Live Chart Session Manager.

Manages Bybit WebSocket connections for real-time chart streaming.

Fan-out: one WS connection per (symbol, interval) → N SSE subscribers.
Each SSE subscriber gets its own asyncio.Queue for event delivery.

Usage:
    from backend.services.live_chart.session_manager import LIVE_CHART_MANAGER

    # In SSE endpoint:
    session = await LIVE_CHART_MANAGER.get_or_create("BTCUSDT", "15")
    queue = session.add_subscriber(session_id)
    # ... stream from queue ...
    session.remove_subscriber(session_id)
    await LIVE_CHART_MANAGER.cleanup("BTCUSDT", "15")
"""

import asyncio
import logging
from dataclasses import dataclass, field
from uuid import uuid4

from backend.services.live_trading.bybit_websocket import (
    BybitWebSocketClient,
    WebSocketMessage,
    parse_kline_message,
)

logger = logging.getLogger(__name__)

# Maximum SSE queue size per subscriber — drop events if browser is too slow
_QUEUE_MAX_SIZE = 100


@dataclass
class LiveChartSession:
    """
    One active streaming session for a (symbol × interval) pair.

    A single BybitWebSocketClient is shared across all SSE subscribers
    for the same symbol+interval to avoid duplicate WS connections.
    """

    session_id: str
    symbol: str
    interval: str
    ws_client: BybitWebSocketClient
    # SSE subscriber queues: {subscriber_id → asyncio.Queue}
    subscribers: dict[str, asyncio.Queue] = field(default_factory=dict)

    def add_subscriber(self, sub_id: str) -> asyncio.Queue:
        """Register a new SSE subscriber and return its event queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX_SIZE)
        self.subscribers[sub_id] = q
        logger.debug("[LiveChart] Subscriber %s added to %s:%s", sub_id, self.symbol, self.interval)
        return q

    def remove_subscriber(self, sub_id: str) -> None:
        """Unregister an SSE subscriber."""
        self.subscribers.pop(sub_id, None)
        logger.debug("[LiveChart] Subscriber %s removed from %s:%s", sub_id, self.symbol, self.interval)

    @property
    def has_subscribers(self) -> bool:
        """True when at least one SSE client is connected."""
        return bool(self.subscribers)

    async def _fan_out(self, event: dict) -> None:
        """
        Deliver an event to all registered SSE subscribers.

        If a subscriber's queue is full (browser too slow / stale connection),
        it is silently removed from the registry — the next SSE reconnect will
        re-register it.
        """
        dead: list[str] = []
        for sub_id, q in list(self.subscribers.items()):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "[LiveChart] Queue full for subscriber %s on %s:%s — dropping and disconnecting",
                    sub_id,
                    self.symbol,
                    self.interval,
                )
                dead.append(sub_id)
        for sub_id in dead:
            self.remove_subscriber(sub_id)

    async def _on_ws_message(self, message: WebSocketMessage) -> None:
        """
        Callback registered with BybitWebSocketClient.register_callback().

        Converts a WebSocketMessage (kline topic) into tick/bar_closed events
        and fans them out to all SSE subscribers.

        D1.2: message is WebSocketMessage, not dict — use parse_kline_message(message).
        """
        try:
            bars = parse_kline_message(message)
        except Exception as exc:
            logger.error("[LiveChart] Failed to parse kline message for %s:%s — %s", self.symbol, self.interval, exc)
            return

        for bar in bars:
            # Skip zero-volume bars (Bybit sometimes sends ticks with no trades)
            if bar.get("volume", 0) == 0 and not bar.get("confirm", False):
                logger.debug(
                    "[LiveChart] Skipping empty tick (volume=0) for %s:%s at t=%s",
                    self.symbol,
                    self.interval,
                    bar.get("start"),
                )
                continue

            event: dict = {
                "type": "bar_closed" if bar["confirm"] else "tick",
                "candle": {
                    "time": int(bar["start"] / 1000),  # ms → seconds for LightweightCharts
                    "open": bar["open"],
                    "high": bar["high"],
                    "low": bar["low"],
                    "close": bar["close"],
                    "volume": bar["volume"],
                },
                "confirm": bar["confirm"],
            }
            await self._fan_out(event)


class LiveChartSessionManager:
    """
    Singleton registry of active LiveChartSession objects.

    One WS connection per (symbol, interval) regardless of how many browsers
    are watching the same chart.  Sessions are closed automatically once the
    last SSE subscriber disconnects.
    """

    def __init__(self) -> None:
        # Key: "{symbol}:{interval}"
        self._sessions: dict[str, LiveChartSession] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, symbol: str, interval: str) -> LiveChartSession:
        """
        Return an existing session or create a new one (opens WS to Bybit).

        Note: kline data is PUBLIC — no api_key / api_secret required.
        """
        key = f"{symbol}:{interval}"
        async with self._lock:
            if key not in self._sessions:
                ws_client = BybitWebSocketClient()
                await ws_client.connect()
                await ws_client.subscribe_klines(symbol, interval)

                session = LiveChartSession(
                    session_id=str(uuid4()),
                    symbol=symbol,
                    interval=interval,
                    ws_client=ws_client,
                )

                # Register per-topic callback — D1.1: use existing register_callback API
                topic = f"kline.{interval}.{symbol}"
                ws_client.register_callback(topic, session._on_ws_message)

                self._sessions[key] = session
                logger.info("[LiveChart] New WS session created for %s", key)

            return self._sessions[key]

    async def cleanup(self, symbol: str, interval: str) -> None:
        """
        Close the WS connection for a (symbol, interval) pair if no subscribers remain.

        Call this in the SSE generator's finally block after removing the subscriber.
        """
        key = f"{symbol}:{interval}"
        async with self._lock:
            session = self._sessions.get(key)
            if session and not session.has_subscribers:
                topic = f"kline.{interval}.{symbol}"
                try:
                    session.ws_client.unregister_callback(topic, session._on_ws_message)
                    await session.ws_client.disconnect()
                except Exception as exc:
                    logger.warning("[LiveChart] Error closing WS for %s: %s", key, exc)
                del self._sessions[key]
                logger.info("[LiveChart] WS session closed (no subscribers): %s", key)

    async def shutdown_all(self) -> None:
        """
        Close all active sessions — called from application lifespan shutdown.
        """
        async with self._lock:
            keys = list(self._sessions.keys())
        for key in keys:
            symbol, interval = key.split(":", 1)
            await self.cleanup(symbol, interval)
        logger.info("[LiveChart] All sessions shut down")

    @property
    def active_session_count(self) -> int:
        """Number of currently active WS sessions."""
        return len(self._sessions)


# Module-level singleton — import this in the SSE router and lifespan
LIVE_CHART_MANAGER = LiveChartSessionManager()
