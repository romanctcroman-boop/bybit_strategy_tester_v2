"""
Unit tests for LiveChartSession and LiveChartSessionManager.

Tests cover:
  - Subscriber add/remove/has_subscribers
  - Fan-out delivery to all subscribers
  - Full-queue subscriber removal (back-pressure)
  - _on_ws_message parses and fans out tick/bar_closed events
  - Empty-volume ticks are skipped
  - LiveChartSessionManager.cleanup removes session when no subscribers remain
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.live_chart.session_manager import (
    LiveChartSession,
    LiveChartSessionManager,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(**kwargs) -> LiveChartSession:
    return LiveChartSession(
        session_id="test-session-id",
        symbol="BTCUSDT",
        interval="15",
        ws_client=MagicMock(),
        **kwargs,
    )


def _make_ws_message(confirm: bool = False, volume: float = 100.0):
    """Create a mock WebSocketMessage as returned by BybitWebSocketClient."""
    from backend.services.live_trading.bybit_websocket import WebSocketMessage

    return WebSocketMessage(
        topic="kline.15.BTCUSDT",
        data=[
            {
                "start":     1_700_000_000_000,
                "end":       1_700_000_900_000,
                "interval":  "15",
                "open":      "30000",
                "high":      "30100",
                "low":       "29900",
                "close":     "30050",
                "volume":    str(volume),
                "turnover":  "3000000",
                "confirm":   confirm,
                "timestamp": 1_700_000_000_000,
            }
        ],
        timestamp=1_700_000_000_000,
        type="snapshot",
    )


# ---------------------------------------------------------------------------
# LiveChartSession — subscriber management
# ---------------------------------------------------------------------------

class TestLiveChartSessionSubscribers:
    def test_add_subscriber_returns_queue(self):
        session = _make_session()
        q = session.add_subscriber("sub1")
        assert isinstance(q, asyncio.Queue)

    def test_has_subscribers_true_after_add(self):
        session = _make_session()
        session.add_subscriber("sub1")
        assert session.has_subscribers is True

    def test_remove_subscriber_clears_has_subscribers(self):
        session = _make_session()
        session.add_subscriber("sub1")
        session.remove_subscriber("sub1")
        assert session.has_subscribers is False

    def test_remove_nonexistent_subscriber_is_safe(self):
        session = _make_session()
        session.remove_subscriber("ghost")  # should not raise


# ---------------------------------------------------------------------------
# LiveChartSession — fan-out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFanOut:
    async def test_fan_out_delivers_to_all_subscribers(self):
        session = _make_session()
        q1 = session.add_subscriber("sub1")
        q2 = session.add_subscriber("sub2")
        event = {"type": "tick", "candle": {"time": 100}}

        await session._fan_out(event)

        assert q1.qsize() == 1
        assert q2.qsize() == 1
        assert await q1.get() == event

    async def test_fan_out_removes_full_queue_subscriber(self):
        """Subscriber whose queue is full must be evicted (back-pressure protection)."""
        session = _make_session()
        q = session.add_subscriber("slow_sub")
        # Fill queue to maxsize
        for i in range(100):
            q.put_nowait({"i": i})

        # Next fan_out should detect full queue and remove slow_sub
        await session._fan_out({"type": "tick"})
        assert "slow_sub" not in session.subscribers

    async def test_fan_out_partial_eviction_keeps_fast_subscriber(self):
        """Fast subscriber must NOT be evicted when only slow one is full."""
        session = _make_session()
        q_fast = session.add_subscriber("fast")
        q_slow = session.add_subscriber("slow")
        # Fill only slow queue
        for i in range(100):
            q_slow.put_nowait({"i": i})

        await session._fan_out({"type": "tick", "candle": {}})

        assert "fast" in session.subscribers
        assert "slow" not in session.subscribers
        assert q_fast.qsize() == 1


# ---------------------------------------------------------------------------
# LiveChartSession — _on_ws_message callback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOnWsMessage:
    async def test_tick_event_emitted_for_unconfirmed_bar(self):
        session = _make_session()
        q = session.add_subscriber("sub1")

        await session._on_ws_message(_make_ws_message(confirm=False))

        assert q.qsize() == 1
        event = await q.get()
        assert event["type"] == "tick"
        assert event["confirm"] is False
        assert event["candle"]["close"] == 30050.0

    async def test_bar_closed_event_emitted_for_confirmed_bar(self):
        session = _make_session()
        q = session.add_subscriber("sub1")

        await session._on_ws_message(_make_ws_message(confirm=True))

        event = await q.get()
        assert event["type"] == "bar_closed"
        assert event["confirm"] is True

    async def test_empty_volume_tick_is_skipped(self):
        """D5.1 — zero-volume ticks must not be forwarded to subscribers."""
        session = _make_session()
        q = session.add_subscriber("sub1")

        await session._on_ws_message(_make_ws_message(confirm=False, volume=0.0))

        # Queue must remain empty
        assert q.qsize() == 0

    async def test_candle_time_converted_to_seconds(self):
        """WS gives ms timestamps; SSE client expects epoch seconds."""
        session = _make_session()
        q = session.add_subscriber("sub1")

        await session._on_ws_message(_make_ws_message(confirm=False))

        event = await q.get()
        assert event["candle"]["time"] == 1_700_000_000_000 // 1000


# ---------------------------------------------------------------------------
# LiveChartSessionManager
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLiveChartSessionManager:
    async def test_get_or_create_creates_session(self):
        manager = LiveChartSessionManager()

        mock_ws = AsyncMock()
        mock_ws.connect = AsyncMock()
        mock_ws.subscribe_klines = AsyncMock()
        mock_ws.register_callback = MagicMock()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=mock_ws,
        ):
            session = await manager.get_or_create("BTCUSDT", "15")

        assert session.symbol == "BTCUSDT"
        assert session.interval == "15"
        mock_ws.connect.assert_awaited_once()
        mock_ws.subscribe_klines.assert_awaited_once_with("BTCUSDT", "15")
        mock_ws.register_callback.assert_called_once()

    async def test_get_or_create_returns_existing_session(self):
        manager = LiveChartSessionManager()
        mock_ws = AsyncMock()
        mock_ws.connect = AsyncMock()
        mock_ws.subscribe_klines = AsyncMock()
        mock_ws.register_callback = MagicMock()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=mock_ws,
        ):
            s1 = await manager.get_or_create("BTCUSDT", "15")
            s2 = await manager.get_or_create("BTCUSDT", "15")

        assert s1 is s2
        # Only one WS connection should have been created
        assert mock_ws.connect.await_count == 1

    async def test_cleanup_removes_session_when_no_subscribers(self):
        manager = LiveChartSessionManager()
        mock_ws = AsyncMock()
        mock_ws.connect = AsyncMock()
        mock_ws.subscribe_klines = AsyncMock()
        mock_ws.register_callback = MagicMock()
        mock_ws.unregister_callback = MagicMock()
        mock_ws.disconnect = AsyncMock()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=mock_ws,
        ):
            session = await manager.get_or_create("BTCUSDT", "15")
            # No subscribers → cleanup should close WS and remove session
            await manager.cleanup("BTCUSDT", "15")

        assert manager.active_session_count == 0
        mock_ws.disconnect.assert_awaited_once()

    async def test_cleanup_keeps_session_when_has_subscribers(self):
        manager = LiveChartSessionManager()
        mock_ws = AsyncMock()
        mock_ws.connect = AsyncMock()
        mock_ws.subscribe_klines = AsyncMock()
        mock_ws.register_callback = MagicMock()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=mock_ws,
        ):
            session = await manager.get_or_create("BTCUSDT", "15")
            session.add_subscriber("active_browser")
            # Still has a subscriber — should NOT remove
            await manager.cleanup("BTCUSDT", "15")

        assert manager.active_session_count == 1
