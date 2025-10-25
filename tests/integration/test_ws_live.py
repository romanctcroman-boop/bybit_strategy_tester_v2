import asyncio
import json
from threading import Thread

from fastapi.testclient import TestClient

from backend.api.app import app


class FakePubSub:
    def __init__(self, queue):
        self._queue = queue
        self._pattern = None

    async def psubscribe(self, pattern):
        self._pattern = pattern

    async def subscribe(self, channel):
        self._pattern = channel

    async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
        # Simulate blocking wait with timeout
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def listen(self):
        while True:
            msg = await self._queue.get()
            yield msg


class FakeRedis:
    def __init__(self, queue):
        self._queue = queue

    @classmethod
    def from_url(cls, url, encoding="utf-8", decode_responses=True):
        # shared queue across instances
        if not hasattr(FakeRedis, "_shared_queue"):
            FakeRedis._shared_queue = asyncio.Queue()
        return cls(FakeRedis._shared_queue)

    def pubsub(self):
        return FakePubSub(self._queue)

    async def publish(self, channel, data):
        await self._queue.put({"type": "message", "channel": channel, "data": data})

    async def close(self):
        pass


def test_ws_live_receives_message(monkeypatch):
    # Patch redis.asyncio.Redis in the live router to our FakeRedis
    import backend.api.routers.live as live

    monkeypatch.setattr(live, "Redis", FakeRedis)

    client = TestClient(app)

    # Prepare a publisher coroutine to send a test message shortly after ws connect
    async def publisher():
        # wait a bit to allow ws to subscribe
        await asyncio.sleep(0.1)
        r = FakeRedis.from_url("redis://")
        await r.publish("bybit:ticks", json.dumps({"v": 1, "type": "test", "payload": 42}))

    # Run publisher in background event loop inside client websocket context
    with client.websocket_connect("/api/v1/live?channel=bybit:ticks") as ws:
        # Start publisher in a background thread with its own event loop
        t = Thread(target=lambda: asyncio.run(publisher()))
        t.start()
        try:
            msg = ws.receive_json()
            assert msg["status"] == "subscribed"
            # ignore status, read next
            msg2 = ws.receive_text()
            data = json.loads(msg2)
            assert data["type"] == "test"
            assert data["payload"] == 42
        finally:
            t.join(timeout=2)
