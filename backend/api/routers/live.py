from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.config import CONFIG

router = APIRouter()

try:  # optional redis import; endpoint degrades gracefully if missing
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore


async def _pubsub_forward(
    ws: WebSocket,
    channel: str,
    pattern: bool = False,
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
) -> None:
    if Redis is None:
        await ws.send_json({"error": "redis-not-installed"})
        return
    redis = Redis.from_url(CONFIG.redis.url, encoding="utf-8", decode_responses=True)
    try:
        await ws.send_json({"status": "subscribed", "channel": channel, "url": CONFIG.redis.url})
        if pattern:
            psub = redis.pubsub()
            await psub.psubscribe(channel)
            async for msg in psub.listen():
                if msg.get("type") == "pmessage":
                    data_text = msg.get("data", "")
                    # optional server-side JSON filter
                    if symbol or interval:
                        try:
                            obj = json.loads(data_text)
                            if symbol and obj.get("symbol") and obj.get("symbol") != symbol:
                                continue
                            if interval and obj.get("interval") and obj.get("interval") != interval:
                                continue
                            await ws.send_text(json.dumps(obj))
                            continue
                        except Exception:
                            # if not json, forward raw
                            pass
                    await ws.send_text(data_text)
        else:
            psub = redis.pubsub()
            await psub.subscribe(channel)
            while True:
                msg = await psub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    data = msg.get("data")
                    if isinstance(data, (bytes, bytearray)):
                        data = data.decode("utf-8", errors="ignore")
                    # optional server-side JSON filter
                    if symbol or interval:
                        try:
                            obj = json.loads(data)
                            if symbol and obj.get("symbol") and obj.get("symbol") != symbol:
                                continue
                            if interval and obj.get("interval") and obj.get("interval") != interval:
                                continue
                            await ws.send_text(json.dumps(obj))
                            await asyncio.sleep(0.01)
                            continue
                        except Exception:
                            # forward raw if not json
                            pass
                    await ws.send_text(str(data))
                await asyncio.sleep(0.01)
    finally:
        try:
            await redis.close()
        except Exception:
            pass


@router.websocket("/live")
async def live(
    ws: WebSocket,
    channel: Optional[str] = Query(None),
    pattern: int = Query(0),
    symbol: Optional[str] = Query(None),
    interval: Optional[str] = Query(None),
):
    await ws.accept()
    try:
        chan = channel or CONFIG.redis.channel_ticks
        await _pubsub_forward(ws, chan, pattern=bool(pattern), symbol=symbol, interval=interval)
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await ws.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        await ws.close()


# Provide a root path alias so including this router under prefix "/ws" exposes ws://host/ws
@router.websocket("/")
async def live_root(
    ws: WebSocket,
    channel: Optional[str] = Query(None),
    pattern: int = Query(0),
    symbol: Optional[str] = Query(None),
    interval: Optional[str] = Query(None),
):
    await live(ws, channel=channel, pattern=pattern, symbol=symbol, interval=interval)
