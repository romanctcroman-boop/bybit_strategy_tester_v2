"""
Unit tests for LiveChartSession and LiveChartSessionManager.

Covers:
- Session creation / subscriber management
- Fan-out to multiple SSE queues
- Slow subscriber eviction on QueueFull
- WS message parsing and routing (open bar vs closed bar)
- Session cleanup on 0 subscribers
- shutdown_all disconnects all WS clients
- active_session_count / get_active_sessions
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_ws_client() -> MagicMock:
    """Mock BybitWebSocketClient."""
    ws = MagicMock()
    ws.connect = AsyncMock(return_value=True)
    ws.disconnect = AsyncMock()
    ws.subscribe_klines = AsyncMock()
    ws.unsubscribe_klines = AsyncMock()
    ws.register_callback = MagicMock()
    ws.unregister_callback = MagicMock()
    return ws


def _make_ws_message(confirm: bool = True) -> MagicMock:
    """Mock WebSocketMessage for a kline update."""
    msg = MagicMock()
    return msg


def _make_kline_data(confirm: bool = True) -> list[dict]:
    """Sample parsed kline data."""
    return [
        {
            "start": 1_700_000_000_000,
            "end": 1_700_000_900_000,
            "interval": "15",
            "open": 50000.0,
            "high": 50200.0,
            "low": 49900.0,
            "close": 50100.0,
            "volume": 123.45,
            "confirm": confirm,
        }
    ]


@pytest.fixture
def session():
    """Build a LiveChartSession with a mock WS client."""
    from backend.services.live_chart.session_manager import LiveChartSession

    ws = _make_ws_client()
    return LiveChartSession(
        session_id="test-session",
        symbol="BTCUSDT",
        interval="15",
        ws_client=ws,
    )


# ---------------------------------------------------------------------------
# Tests: subscriber management
# ---------------------------------------------------------------------------


class TestLiveChartSessionSubscribers:
    """Subscriber add/remove logic."""

    def test_add_subscriber_returns_queue(self, session):
        """add_subscriber returns an asyncio.Queue."""
        q = session.add_subscriber("sub-1")
        assert isinstance(q, asyncio.Queue)

    def test_add_subscriber_stored(self, session):
        """Added subscriber is stored in session.subscribers."""
        session.add_subscriber("sub-1")
        assert "sub-1" in session.subscribers

    def test_remove_subscriber(self, session):
        """remove_subscriber removes entry from subscribers dict."""
        session.add_subscriber("sub-1")
        session.remove_subscriber("sub-1")
        assert "sub-1" not in session.subscribers

    def test_remove_nonexistent_subscriber_no_error(self, session):
        """Removing a non-existent subscriber does not raise."""
        session.remove_subscriber("ghost")  # Should not raise

    def test_has_subscribers_true(self, session):
        """has_subscribers is True when there are subscribers."""
        session.add_subscriber("sub-1")
        assert session.has_subscribers is True

    def test_has_subscribers_false(self, session):
        """has_subscribers is False when there are no subscribers."""
        assert session.has_subscribers is False

    def test_multiple_subscribers(self, session):
        """Multiple subscribers can be added."""
        session.add_subscriber("sub-1")
        session.add_subscriber("sub-2")
        session.add_subscriber("sub-3")
        assert len(session.subscribers) == 3


# ---------------------------------------------------------------------------
# Tests: fan-out
# ---------------------------------------------------------------------------


class TestLiveChartSessionFanOut:
    """Fan-out: WS event → all subscriber queues."""

    @pytest.mark.asyncio
    async def test_fan_out_delivers_to_all_subscribers(self, session):
        """Event is delivered to all subscriber queues."""
        q1 = session.add_subscriber("sub-1")
        q2 = session.add_subscriber("sub-2")

        event = {"type": "tick", "candle": {"close": 50100.0}}
        await session._fan_out(event)

        assert q1.get_nowait() == event
        assert q2.get_nowait() == event

    @pytest.mark.asyncio
    async def test_fan_out_evicts_full_queue(self, session):
        """Subscriber with full queue is evicted (slow subscriber)."""
        # Add a subscriber with maxsize=1 and fill it
        q = session.add_subscriber("slow-sub")

        # Fill the queue manually (bypass queue maxsize with direct put)
        # Simulate QueueFull by patching put_nowait
        original_put = q.put_nowait
        call_count = 0

        def put_that_fails_second_time(item):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise asyncio.QueueFull
            original_put(item)

        q.put_nowait = put_that_fails_second_time

        # First fan-out succeeds
        await session._fan_out({"type": "tick"})
        # Second fan-out causes QueueFull → subscriber is evicted
        await session._fan_out({"type": "tick"})

        assert "slow-sub" not in session.subscribers

    @pytest.mark.asyncio
    async def test_fan_out_empty_subscribers_no_error(self, session):
        """Fan-out with no subscribers does not raise."""
        await session._fan_out({"type": "heartbeat"})  # Should not raise


# ---------------------------------------------------------------------------
# Tests: WS message routing
# ---------------------------------------------------------------------------


class TestLiveChartSessionWsMessage:
    """_on_ws_message: parse and fan-out kline events."""

    @pytest.mark.asyncio
    async def test_open_bar_tick_event(self, session):
        """Unconfirmed bar (confirm=False) produces 'tick' event."""
        q = session.add_subscriber("sub-1")
        klines = _make_kline_data(confirm=False)

        with patch(
            "backend.services.live_chart.session_manager.parse_kline_message",
            return_value=klines,
        ):
            msg = _make_ws_message(confirm=False)
            await session._on_ws_message(msg)

        event = q.get_nowait()
        assert event["type"] == "tick"

    @pytest.mark.asyncio
    async def test_closed_bar_event(self, session):
        """Confirmed bar (confirm=True) produces 'bar_closed' event."""
        q = session.add_subscriber("sub-1")
        klines = _make_kline_data(confirm=True)

        with patch(
            "backend.services.live_chart.session_manager.parse_kline_message",
            return_value=klines,
        ):
            msg = _make_ws_message(confirm=True)
            await session._on_ws_message(msg)

        event = q.get_nowait()
        assert event["type"] == "bar_closed"

    @pytest.mark.asyncio
    async def test_candle_fields_normalized(self, session):
        """Event candle contains time in seconds (not ms)."""
        q = session.add_subscriber("sub-1")
        klines = _make_kline_data(confirm=False)

        with patch(
            "backend.services.live_chart.session_manager.parse_kline_message",
            return_value=klines,
        ):
            await session._on_ws_message(_make_ws_message())

        event = q.get_nowait()
        candle = event["candle"]
        # start=1_700_000_000_000 ms → 1_700_000_000 s
        assert candle["time"] == 1_700_000_000
        assert candle["open"] == 50000.0
        assert candle["close"] == 50100.0

    @pytest.mark.asyncio
    async def test_parse_error_does_not_propagate(self, session):
        """If parse_kline_message raises, no exception leaves _on_ws_message."""
        with patch(
            "backend.services.live_chart.session_manager.parse_kline_message",
            side_effect=RuntimeError("bad message"),
        ):
            await session._on_ws_message(_make_ws_message())  # Should not raise

    @pytest.mark.asyncio
    async def test_empty_klines_list_no_event(self, session):
        """Empty list from parse_kline_message results in no event queued."""
        q = session.add_subscriber("sub-1")

        with patch(
            "backend.services.live_chart.session_manager.parse_kline_message",
            return_value=[],
        ):
            await session._on_ws_message(_make_ws_message())

        assert q.empty()


# ---------------------------------------------------------------------------
# Tests: LiveChartSessionManager
# ---------------------------------------------------------------------------


class TestLiveChartSessionManager:
    """Session lifecycle: get_or_create, cleanup, shutdown_all."""

    @pytest.mark.asyncio
    async def test_get_or_create_returns_session(self):
        """get_or_create returns a LiveChartSession."""
        from backend.services.live_chart.session_manager import LiveChartSessionManager

        manager = LiveChartSessionManager()
        ws = _make_ws_client()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=ws,
        ):
            session = await manager.get_or_create("BTCUSDT", "15")

        assert session is not None
        assert session.symbol == "BTCUSDT"
        assert session.interval == "15"

    @pytest.mark.asyncio
    async def test_get_or_create_same_key_returns_same_session(self):
        """Same symbol/interval returns same session instance."""
        from backend.services.live_chart.session_manager import LiveChartSessionManager

        manager = LiveChartSessionManager()
        ws = _make_ws_client()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=ws,
        ):
            s1 = await manager.get_or_create("BTCUSDT", "15")
            s2 = await manager.get_or_create("BTCUSDT", "15")

        assert s1 is s2

    @pytest.mark.asyncio
    async def test_get_or_create_different_keys_different_sessions(self):
        """Different symbols/intervals get different sessions."""
        from backend.services.live_chart.session_manager import LiveChartSessionManager

        manager = LiveChartSessionManager()
        ws = _make_ws_client()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=ws,
        ):
            s1 = await manager.get_or_create("BTCUSDT", "15")
            s2 = await manager.get_or_create("ETHUSDT", "60")

        assert s1 is not s2

    @pytest.mark.asyncio
    async def test_cleanup_removes_session(self):
        """cleanup() removes session from registry."""
        from backend.services.live_chart.session_manager import LiveChartSessionManager

        manager = LiveChartSessionManager()
        ws = _make_ws_client()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=ws,
        ):
            await manager.get_or_create("BTCUSDT", "15")
            assert manager.active_session_count == 1

            await manager.cleanup("BTCUSDT", "15")
            assert manager.active_session_count == 0

    @pytest.mark.asyncio
    async def test_cleanup_calls_ws_disconnect(self):
        """cleanup() disconnects the WS client."""
        from backend.services.live_chart.session_manager import LiveChartSessionManager

        manager = LiveChartSessionManager()
        ws = _make_ws_client()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=ws,
        ):
            await manager.get_or_create("BTCUSDT", "15")
            await manager.cleanup("BTCUSDT", "15")

        ws.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_all_clears_all_sessions(self):
        """shutdown_all disconnects all WS clients and clears registry."""
        from backend.services.live_chart.session_manager import LiveChartSessionManager

        manager = LiveChartSessionManager()
        ws1 = _make_ws_client()
        ws2 = _make_ws_client()
        ws_iter = iter([ws1, ws2])

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            side_effect=lambda **kw: next(ws_iter),
        ):
            await manager.get_or_create("BTCUSDT", "15")
            await manager.get_or_create("ETHUSDT", "60")
            assert manager.active_session_count == 2

            await manager.shutdown_all()
            assert manager.active_session_count == 0

        ws1.disconnect.assert_called_once()
        ws2.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_active_session_count(self):
        """active_session_count reflects number of active sessions."""
        from backend.services.live_chart.session_manager import LiveChartSessionManager

        manager = LiveChartSessionManager()
        assert manager.active_session_count == 0

        ws = _make_ws_client()
        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=ws,
        ):
            await manager.get_or_create("BTCUSDT", "15")
            assert manager.active_session_count == 1

    @pytest.mark.asyncio
    async def test_get_active_sessions_structure(self):
        """get_active_sessions returns list of dicts with symbol/interval."""
        from backend.services.live_chart.session_manager import LiveChartSessionManager

        manager = LiveChartSessionManager()
        ws = _make_ws_client()

        with patch(
            "backend.services.live_chart.session_manager.BybitWebSocketClient",
            return_value=ws,
        ):
            await manager.get_or_create("BTCUSDT", "15")
            sessions = manager.get_active_sessions()

        assert isinstance(sessions, list)
        assert len(sessions) == 1
        assert sessions[0]["symbol"] == "BTCUSDT"
        assert sessions[0]["interval"] == "15"
