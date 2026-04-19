"""Tests for backend.services.ws_scaling — WebSocket Scaling Service."""

import asyncio
import json

import pytest

from backend.services.ws_scaling import (
    BroadcastMessage,
    WSBroadcaster,
    get_ws_broadcaster,
)

# ============================================================================
# BroadcastMessage
# ============================================================================


class TestBroadcastMessage:
    """Tests for BroadcastMessage serialization."""

    def test_to_json_produces_valid_json(self):
        """Test JSON serialization."""
        msg = BroadcastMessage(
            channel="backtest:progress",
            data={"id": "abc", "pct": 75},
            sender_id="worker-1234",
        )
        raw = msg.to_json()
        parsed = json.loads(raw)
        assert parsed["channel"] == "backtest:progress"
        assert parsed["data"]["pct"] == 75
        assert parsed["timestamp"] > 0

    def test_from_json_roundtrip(self):
        """Test JSON round-trip."""
        original = BroadcastMessage(
            channel="alert:system",
            data={"level": "warning", "msg": "High CPU"},
            sender_id="w-1",
        )
        raw = original.to_json()
        restored = BroadcastMessage.from_json(raw)
        assert restored.channel == "alert:system"
        assert restored.data["level"] == "warning"
        assert restored.sender_id == "w-1"

    def test_from_json_bytes(self):
        """Test deserialization from bytes."""
        msg = BroadcastMessage(channel="test", data={"x": 1})
        raw_bytes = msg.to_json().encode("utf-8")
        restored = BroadcastMessage.from_json(raw_bytes)
        assert restored.channel == "test"

    def test_from_json_invalid_raises(self):
        """Test invalid JSON raises error."""
        with pytest.raises(json.JSONDecodeError):
            BroadcastMessage.from_json("not valid json{{{")


# ============================================================================
# WSBroadcaster (local fallback mode — no Redis)
# ============================================================================


class TestWSBroadcasterLocal:
    """Tests for WSBroadcaster in local (no Redis) fallback mode."""

    @pytest.mark.asyncio
    async def test_publish_with_no_subscribers(self):
        """Test publish returns 0 when no subscribers."""
        broadcaster = WSBroadcaster(redis_url="redis://invalid:9999")
        # Force local mode by ensuring Redis connect fails
        broadcaster._redis = None
        count = await broadcaster.publish("test:channel", {"key": "value"})
        assert count == 0

    @pytest.mark.asyncio
    async def test_publish_and_subscribe_local(self):
        """Test local pub/sub without Redis."""
        broadcaster = WSBroadcaster()
        # Force local mode
        broadcaster._redis = False  # Prevent Redis connection attempt

        received = []

        async def subscriber():
            async for msg in broadcaster.subscribe("test:chan"):
                received.append(msg)
                if len(received) >= 2:
                    break

        # Start subscriber in background
        sub_task = asyncio.create_task(subscriber())

        # Give subscriber time to register
        await asyncio.sleep(0.05)

        # Publish messages
        await broadcaster.publish("test:chan", {"n": 1})
        await broadcaster.publish("test:chan", {"n": 2})

        # Wait for subscriber to receive
        await asyncio.wait_for(sub_task, timeout=2.0)

        assert len(received) == 2
        assert received[0].data["n"] == 1
        assert received[1].data["n"] == 2

    @pytest.mark.asyncio
    async def test_close_clears_state(self):
        """Test close clears internal state."""
        broadcaster = WSBroadcaster()
        broadcaster._local_queues["test"] = [asyncio.Queue()]
        await broadcaster.close()
        assert broadcaster._local_queues == {}
        assert broadcaster._redis is None


# ============================================================================
# Module singleton
# ============================================================================


class TestGetWSBroadcaster:
    """Tests for get_ws_broadcaster singleton."""

    def test_returns_instance(self):
        """Test singleton returns WSBroadcaster."""
        import backend.services.ws_scaling as ws_mod

        # Reset singleton
        ws_mod._broadcaster = None
        b = get_ws_broadcaster()
        assert isinstance(b, WSBroadcaster)

    def test_same_instance(self):
        """Test singleton returns same instance."""
        import backend.services.ws_scaling as ws_mod

        ws_mod._broadcaster = None
        b1 = get_ws_broadcaster()
        b2 = get_ws_broadcaster()
        assert b1 is b2
