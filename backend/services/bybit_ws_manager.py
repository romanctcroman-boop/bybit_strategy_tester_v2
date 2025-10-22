"""Bybit WebSocket manager.

Responsibilities:
- Connect to Bybit public websocket (v5)
- Subscribe to trades/klines for configured symbols/intervals
- Normalize payloads to a stable JSON schema (v=1)
- Publish to Redis channels (ticks/klines)

Notes:
- Minimal implementation using 'websockets' and asyncio Redis.
- Production hardening (re-auth, backoff, resubscribe) is sketched with retries.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Iterable, List, Optional

try:
    # We'll publish to Redis using asyncio client
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore

logger = logging.getLogger(__name__)

# Optional Prometheus metrics
try:  # pragma: no cover
    from prometheus_client import Counter

    WS_CONNECTS = Counter("bybit_ws_connects_total", "WS successful connections")
    WS_RECONNECTS = Counter("bybit_ws_reconnects_total", "WS reconnect attempts")
    WS_MESSAGES = Counter("bybit_ws_messages_total", "WS messages received")
    WS_PINGS = Counter("bybit_ws_pings_total", "WS ping frames received")
    WS_PUBLISHED = Counter(
        "bybit_ws_published_total",
        "Messages published to Redis",
        labelnames=("type",),
    )
    WS_ERRORS = Counter("bybit_ws_errors_total", "WS errors")
except Exception:  # pragma: no cover
    WS_CONNECTS = WS_RECONNECTS = WS_MESSAGES = WS_PINGS = WS_PUBLISHED = WS_ERRORS = None  # type: ignore

BYBIT_PUBLIC_WS = "wss://stream.bybit.com/v5/public/linear"


class BybitWsManager:
    def __init__(self, redis: Optional["Redis"], channel_ticks: str, channel_klines: str):
        self._redis = redis
        self._chan_ticks = channel_ticks
        self._chan_klines = channel_klines
        self._task: Optional[asyncio.Task] = None
        self._closed = asyncio.Event()
        self._subs: List[str] = []

    async def start(
        self, symbols: Iterable[str] = ("BTCUSDT",), intervals: Iterable[str] = ("1",)
    ) -> None:
        """Start background loop: connect, subscribe, consume, publish to Redis."""
        if self._task and not self._task.done():
            return
        self._closed.clear()
        self._task = asyncio.create_task(self._run(symbols, intervals))

    async def stop(self) -> None:
        self._closed.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except Exception:
                pass

    async def _run(self, symbols: Iterable[str], intervals: Iterable[str]) -> None:
        try:
            import websockets
        except Exception:
            logger.error("websockets package not installed; BybitWsManager disabled")
            return

        subs: List[str] = []
        for sym in symbols:
            subs.append(f"publicTrade.{sym}")
        for iv in intervals:
            for sym in symbols:
                subs.append(f"kline.{iv}.{sym}")
        self._subs = subs

        backoff = 1.0
        while not self._closed.is_set():
            try:
                async with websockets.connect(
                    BYBIT_PUBLIC_WS, ping_interval=20, ping_timeout=20
                ) as ws:
                    if WS_CONNECTS:
                        WS_CONNECTS.inc()
                    await self._subscribe(ws, subs)
                    backoff = 1.0
                    while not self._closed.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        # Fast-path ping/pong handling
                        try:
                            _txt = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
                            msg = json.loads(_txt)
                        except Exception:
                            msg = None
                        if msg and isinstance(msg, dict) and msg.get("op") == "ping":
                            if WS_PINGS:
                                WS_PINGS.inc()
                            try:
                                await ws.send(json.dumps({"op": "pong"}))
                            except Exception:
                                pass
                            continue
                        if WS_MESSAGES:
                            WS_MESSAGES.inc()
                        await self._handle_message(raw)
            except asyncio.TimeoutError:
                logger.info("WS recv timeout; reconnecting")
                if WS_RECONNECTS:
                    WS_RECONNECTS.inc()
            except Exception as e:
                logger.warning(f"WS error: {e}; reconnecting in {backoff:.1f}s")
                if WS_ERRORS:
                    WS_ERRORS.inc()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.8, 20.0)

    async def _subscribe(self, ws, subs: List[str]) -> None:
        msg = {"op": "subscribe", "args": subs}
        await ws.send(json.dumps(msg))

    async def _handle_message(self, raw: str | bytes) -> None:
        try:
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="ignore")
            obj = json.loads(raw)
        except Exception:
            return
        # Ping/Pong and non-data messages
        if obj.get("op") == "pong" or obj.get("retCode") is not None:
            return
        topic = obj.get("topic")
        if not topic:
            return
        data = obj.get("data")
        if not data:
            return
        # Normalize trades
        if topic.startswith("publicTrade."):
            symbol = topic.split(".", 1)[1]
            for t in data:
                payload = {
                    "v": 1,
                    "type": "trade",
                    "source": "bybit",
                    "symbol": symbol,
                    "ts_ms": int(t.get("T")),
                    "price": float(t.get("p")),
                    "qty": float(t.get("v")),
                    "side": t.get("S").lower() if t.get("S") else None,
                }
                await self._publish_json(self._chan_ticks, payload)
                if WS_PUBLISHED:
                    WS_PUBLISHED.labels(type="trade").inc()
            return
        # Normalize kline
        if topic.startswith("kline."):
            parts = topic.split(".")  # kline, iv, symbol
            if len(parts) >= 3:
                interval = parts[1]
                symbol = parts[2]
            else:
                interval = None
                symbol = None
            for k in data:
                payload = {
                    "v": 1,
                    "type": "kline",
                    "source": "bybit",
                    "symbol": symbol,
                    "interval": interval,
                    "open_time": int(k.get("start")),
                    "open": float(k.get("open")),
                    "high": float(k.get("high")),
                    "low": float(k.get("low")),
                    "close": float(k.get("close")),
                    "volume": float(k.get("volume")) if k.get("volume") is not None else None,
                    "turnover": float(k.get("turnover")) if k.get("turnover") is not None else None,
                }
                await self._publish_json(self._chan_klines, payload)
                if WS_PUBLISHED:
                    WS_PUBLISHED.labels(type="kline").inc()

    async def _publish_json(self, channel: str, payload: dict) -> None:
        if not self._redis:
            return
        try:
            await self._redis.publish(channel, json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"Redis publish failed: {e}")
