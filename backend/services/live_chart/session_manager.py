"""
Live Chart Session Manager.

Manages Bybit WebSocket connections for real-time chart streaming.
Fan-out: одно WS соединение на (symbol, interval) → N SSE клиентов.

Ключевые принципы (ТЗ v1.1, D1.2):
- Использует существующий BybitWebSocketClient.register_callback() — никакого
  нового callback API создавать не нужно (D1.1 подтверждает существование).
- parse_kline_message() принимает WebSocketMessage — не dict.
- При отсутствии подписчиков WS закрывается автоматически (D5).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from uuid import uuid4

from backend.services.live_trading.bybit_websocket import (
    BybitWebSocketClient,
    WebSocketMessage,
    parse_kline_message,
)

logger = logging.getLogger(__name__)

# Максимальный размер очереди на одного SSE-подписчика.
# При переполнении медленный подписчик отключается.
# 1000 тиков ≈ 16+ минут при 1 тике/сек — достаточно для переключения вкладок
# без потери подписки (frontend держит SSE живым через _liveChartPaused).
_SUBSCRIBER_QUEUE_MAXSIZE = 1000


@dataclass
class LiveChartSession:
    """
    Одна активная сессия стриминга (symbol × interval).

    Содержит WS-клиент и реестр SSE-подписчиков (asyncio.Queue).
    Метод _on_ws_message регистрируется как callback в BybitWebSocketClient.
    """

    session_id: str
    symbol: str
    interval: str
    ws_client: BybitWebSocketClient
    # Очереди SSE подписчиков: {subscriber_id → asyncio.Queue}
    subscribers: dict[str, asyncio.Queue] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Subscriber management
    # ------------------------------------------------------------------

    def add_subscriber(self, sub_id: str) -> asyncio.Queue:
        """Добавить подписчика и вернуть его очередь."""
        q: asyncio.Queue = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_MAXSIZE)
        self.subscribers[sub_id] = q
        logger.debug("[LiveChart] Subscriber added: %s (session %s)", sub_id, self.session_id)
        return q

    def remove_subscriber(self, sub_id: str) -> None:
        """Удалить подписчика."""
        self.subscribers.pop(sub_id, None)
        logger.debug("[LiveChart] Subscriber removed: %s (session %s)", sub_id, self.session_id)

    @property
    def has_subscribers(self) -> bool:
        return bool(self.subscribers)

    # ------------------------------------------------------------------
    # Fan-out: WS callback → N SSE queues
    # ------------------------------------------------------------------

    async def _fan_out(self, event: dict) -> None:
        """Рассылка события всем подписчикам. Удаляет «медленные» (переполненные) очереди."""
        dead: list[str] = []
        for sub_id, q in self.subscribers.items():
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "[LiveChart] Queue full for subscriber %s — dropping event and disconnecting",
                    sub_id,
                )
                dead.append(sub_id)
        for sub_id in dead:
            self.remove_subscriber(sub_id)

    async def _on_ws_message(self, message: WebSocketMessage) -> None:
        """
        Callback для BybitWebSocketClient.register_callback().

        Принимает WebSocketMessage (не dict!) — см. D1.2 исправление ТЗ.
        Парсит kline-сообщение и рассылает событие подписчикам.
        """
        try:
            bars = parse_kline_message(message)
        except Exception as exc:
            logger.error("[LiveChart] Failed to parse kline message: %s", exc)
            return

        for bar in bars:
            event: dict = {
                "type": "bar_closed" if bar.get("confirm") else "tick",
                "candle": {
                    "time": int(bar["start"] / 1000),  # мс → секунды для LightweightCharts
                    "open": float(bar["open"]),
                    "high": float(bar["high"]),
                    "low": float(bar["low"]),
                    "close": float(bar["close"]),
                    "volume": float(bar.get("volume", 0)),
                },
                "confirm": bar.get("confirm", False),
            }
            await self._fan_out(event)


class LiveChartSessionManager:
    """
    Синглтон-реестр активных LiveChartSession.

    Fan-out: один WS на (symbol, interval) → N SSE клиентов.
    Использует asyncio.Lock для безопасного создания/удаления сессий.

    ВАЖНО (D5): LIVE_CHART_MANAGER — in-memory синглтон.
    При uvicorn --workers > 1 каждый воркер имеет свой экземпляр.
    Для локальной разработки (1 воркер) — всё работает корректно.
    В production с несколькими воркерами требуется Redis pub/sub.
    """

    def __init__(self) -> None:
        # Ключ: f"{symbol}:{interval}"
        self._sessions: dict[str, LiveChartSession] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, symbol: str, interval: str) -> LiveChartSession:
        """
        Получить существующую или создать новую сессию.

        Если сессия для (symbol, interval) уже существует — возвращает её
        (fan-out к существующему WS). Иначе создаёт новый WS и регистрирует callback.
        """
        key = f"{symbol}:{interval}"

        # Fast path — session already exists (no I/O, just dict lookup)
        async with self._lock:
            if key in self._sessions:
                return self._sessions[key]

        # Slow path — create WS connection OUTSIDE the lock to avoid blocking
        # other coroutines during network I/O (asyncio.Lock is not re-entrant).
        ws_client = BybitWebSocketClient()
        connected = await ws_client.connect()
        if not connected:
            raise RuntimeError(f"[LiveChart] Failed to connect WebSocket for {key}")

        await ws_client.subscribe_klines(symbol, interval)

        session = LiveChartSession(
            session_id=str(uuid4()),
            symbol=symbol,
            interval=interval,
            ws_client=ws_client,
        )
        topic = f"kline.{interval}.{symbol}"
        ws_client.register_callback(topic, session._on_ws_message)

        # Re-acquire lock to insert — check again for race (two concurrent callers)
        async with self._lock:
            if key not in self._sessions:
                self._sessions[key] = session
                logger.info("[LiveChart] New session created: %s (id=%s)", key, session.session_id)
            else:
                # Another coroutine won the race — discard ours, use existing
                ws_client.unregister_callback(topic, session._on_ws_message)
                with contextlib.suppress(Exception):
                    await ws_client.disconnect()
                logger.debug("[LiveChart] Race resolved for %s — using existing session", key)

            return self._sessions[key]

    async def cleanup(self, symbol: str, interval: str) -> None:
        """
        Закрыть WS-соединение и удалить сессию, если подписчиков не осталось.

        Вызывать после remove_subscriber() в finally-блоке SSE-генератора.
        """
        key = f"{symbol}:{interval}"
        async with self._lock:
            session = self._sessions.get(key)
            if session and not session.has_subscribers:
                topic = f"kline.{interval}.{symbol}"
                session.ws_client.unregister_callback(topic, session._on_ws_message)
                try:
                    await session.ws_client.disconnect()
                except Exception as exc:
                    logger.warning("[LiveChart] Error disconnecting WS for %s: %s", key, exc)
                del self._sessions[key]
                logger.info("[LiveChart] Session closed (no subscribers): %s", key)

    async def shutdown_all(self) -> None:
        """
        Закрыть все активные WS-соединения.

        Вызывается из lifespan on_shutdown.
        """
        async with self._lock:
            keys = list(self._sessions.keys())

        for key in keys:
            async with self._lock:
                session = self._sessions.get(key)
                if session:
                    try:
                        await session.ws_client.disconnect()
                    except Exception as exc:
                        logger.warning("[LiveChart] Error during shutdown for %s: %s", key, exc)
                    self._sessions.pop(key, None)

        logger.info("[LiveChart] All sessions closed (%d total)", len(keys))

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

    def get_active_sessions(self) -> list[dict]:
        """Вернуть список активных сессий (для мониторинга)."""
        return [
            {
                "key": f"{s.symbol}:{s.interval}",
                "session_id": s.session_id,
                "symbol": s.symbol,
                "interval": s.interval,
                "subscriber_count": len(s.subscribers),
            }
            for s in self._sessions.values()
        ]


# ---------------------------------------------------------------------------
# Синглтон — импортировать в роутер и lifespan
# ---------------------------------------------------------------------------
LIVE_CHART_MANAGER = LiveChartSessionManager()
