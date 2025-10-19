"""
Live Data WebSocket Router

FastAPI WebSocket endpoints for real-time data streaming to frontend clients.
Subscribes to Redis Pub/Sub channels and forwards data via WebSocket.

Endpoints:
    - GET /ws/candles/{symbol}/{timeframe} - Real-time candle updates
    - GET /ws/trades/{symbol}             - Real-time trades stream
    - GET /ws/ticker/{symbol}             - Real-time ticker updates
"""

import asyncio
import json
import os
import socket
import uuid
import redis.asyncio as aioredis
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path
from fastapi.responses import JSONResponse
from loguru import logger

from backend.core.config import settings
from backend.models.websocket_schemas import (
    WebSocketSubscription,
    SubscriptionResponse,
    WebSocketError,
    HeartbeatMessage,
)
from backend.models.websocket_schemas import (
    CandleUpdate,
    TradeUpdate,
    TickerUpdate,
)
try:
    from prometheus_client import Counter as PromCounter, Gauge as PromGauge, generate_latest
    PROM_AVAILABLE = True
except Exception:
    PROM_AVAILABLE = False


router = APIRouter(prefix="/live", tags=["Live Data"])

# Stream consumer infrastructure
STREAM_GROUP = getattr(__name__, 'STREAM_GROUP', 'live_group')
STREAM_SUBSCRIBERS = {}  # stream_key -> set of WebSocket
STREAM_WORKERS = {}  # stream_key -> {'task': Task, 'client': aioredis.Redis, 'consumer': str}
# Pending/claim configuration
STREAM_CLAIM_IDLE_MS = getattr(__name__, 'STREAM_CLAIM_IDLE_MS', getattr(__name__, 'STREAM_CLAIM_IDLE_MS', 60_000))
STREAM_PENDING_CHECK_INTERVAL = getattr(__name__, 'STREAM_PENDING_CHECK_INTERVAL', getattr(__name__, 'STREAM_PENDING_CHECK_INTERVAL', 30))
STREAM_CLAIM_BATCH = getattr(__name__, 'STREAM_CLAIM_BATCH', 10)
STREAM_CLAIM_BACKOFF = getattr(__name__, 'STREAM_CLAIM_BACKOFF', 1)

# Prometheus metrics (if available)
if PROM_AVAILABLE:
    XREAD_COUNTER = PromCounter('bybit_xread_total', 'Number of XREADGROUP operations', ['stream'])
    XACK_COUNTER = PromCounter('bybit_xack_total', 'Number of XACK operations', ['stream'])
    STREAM_XLEN = PromGauge('bybit_stream_xlen', 'Length of a Redis stream', ['stream'])
    PENDING_GAUGE = PromGauge('bybit_pending_count', 'Number of pending entries in consumer group', ['stream'])


# ============================================================================
# REDIS PUB/SUB CONNECTION
# ============================================================================

async def get_redis_client():
    """
    Create async Redis client for Streams
    Returns the aioredis client instance.
    """
    redis_client = await aioredis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
        encoding="utf-8",
        decode_responses=True
    )
    return redis_client


# Mount /metrics endpoint on router if prometheus_client available
if PROM_AVAILABLE:
    from fastapi import Response

    @router.get('/metrics')
    async def metrics():
        data = generate_latest()
        return Response(content=data, media_type='text/plain; version=0.0.4')


def _parse_xpending_item(item):
    """Parse a single XPENDING item into (entry_id, owner, idle_ms).

    Accepts multiple shapes returned by redis/xpending variations:
    - list/tuple: [id, consumer, idle, deliveries]
    - dict-like: {'id': id, 'consumer': consumer, 'idle': idle}

    Raises ValueError on unexpected shapes.
    """
    if not item:
        raise ValueError('empty item')

    # list/tuple shapes
    if isinstance(item, (list, tuple)):
        # entry id
        entry_id = item[0].decode() if isinstance(item[0], bytes) else item[0]
        # owner/consumer
        owner = None
        if len(item) > 1:
            owner = item[1].decode() if isinstance(item[1], bytes) else item[1]
        # idle (ms)
        idle_ms = 0
        if len(item) > 2:
            try:
                idle_ms = int(item[2])
            except Exception:
                if isinstance(item[2], bytes):
                    idle_ms = int(item[2].decode())
                else:
                    idle_ms = int(str(item[2]))
        return entry_id, owner, idle_ms

    # dict-like shapes
    if isinstance(item, dict):
        entry_id = item.get('id') or item.get(b'id')
        owner = item.get('consumer') or item.get(b'consumer')
        idle = item.get('idle') if 'idle' in item else item.get(b'idle', 0)
        if isinstance(entry_id, bytes):
            entry_id = entry_id.decode()
        if isinstance(owner, bytes):
            owner = owner.decode()
        if isinstance(idle, bytes):
            idle_ms = int(idle.decode())
        else:
            idle_ms = int(idle)
        return entry_id, owner, idle_ms

    raise ValueError(f'unexpected XPENDING item shape: {type(item)}')


def _prepare_outgoing_payload(stream_key: str, data: dict):
    """Validate outgoing payload with Pydantic schemas when possible.

    Returns a serializable object (dict) to send to WebSocket clients.
    On validation failure returns original data and logs a debug message.
    """
    try:
        # Candles
        if stream_key.startswith('stream:candles:'):
            validated = CandleUpdate.model_validate(data)
            return validated.model_dump(mode='json')

        # Trades
        if stream_key.startswith('stream:trades:'):
            validated = TradeUpdate.model_validate(data)
            return validated.model_dump(mode='json')

        # Ticker
        if stream_key.startswith('stream:ticker:'):
            validated = TickerUpdate.model_validate(data)
            return validated.model_dump(mode='json')

    except Exception as e:
        try:
            logger.debug(f"Validation failed for stream {stream_key}: {e} data_sample={repr(data)[:1000]}")
        except Exception:
            logger.debug(f"Validation failed for stream {stream_key}: {e}")

        # Strict policy: return None to indicate invalid payload
        return None


def _build_validation_error(stream_key: str, original_data: dict, error_message: str):
    """Create a WebSocketError payload to notify subscribers about validation failure."""
    try:
        err = WebSocketError(
            error_code="INVALID_PAYLOAD",
            error_message=error_message,
            details={
                "stream": stream_key,
                "sample": repr(original_data)[:500]
            }
        )
        return err.model_dump(mode='json')
    except Exception:
        # Fallback minimal error
        return {"type": "error", "error_code": "INVALID_PAYLOAD", "error_message": str(error_message)}


async def _ensure_stream_worker(stream_key: str):
    """Ensure there's a background consumer task for a stream_key.

    The worker uses XGROUP/XREADGROUP to read new entries and fan-out to subscribers.
    """
    if stream_key in STREAM_WORKERS:
        return

    redis_client = await get_redis_client()
    group_name = STREAM_GROUP
    consumer_name = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

    # Try to create consumer group (ignore BUSYGROUP)
    try:
        await redis_client.execute_command('XGROUP', 'CREATE', stream_key, group_name, '$', 'MKSTREAM')
    except Exception as e:
        # BUSYGROUP means group exists
        if 'BUSYGROUP' not in str(e).upper():
            # Non-fatal: log and continue
            logger.debug(f"XGROUP create warning for {stream_key}: {e}")

    async def _worker():
        logger.info(f"Starting stream worker for {stream_key} group={group_name} consumer={consumer_name}")
        try:
            while True:
                try:
                    # BLOCK for 5000 ms
                    resp = await redis_client.execute_command('XREADGROUP', 'GROUP', group_name, consumer_name, 'COUNT', 10, 'BLOCK', 5000, 'STREAMS', stream_key, '>')
                    if PROM_AVAILABLE:
                        try:
                            XREAD_COUNTER.labels(stream=stream_key).inc()
                        except Exception:
                            pass
                    if not resp:
                        continue

                    # resp format: [[b'stream_key', [[b'id', [b'payload', b'{...}']]]]] or similar
                    for stream_entry in resp:
                        # stream_entry is [stream_name, entries]
                        try:
                            entries = stream_entry[1]
                        except Exception:
                            entries = []

                        for entry in entries:
                            try:
                                entry_id = entry[0].decode() if isinstance(entry[0], bytes) else entry[0]
                                fields = entry[1]
                                # fields is list like [b'payload', b'{...}'] or kv pairs
                                payload_raw = None
                                if isinstance(fields, list):
                                    # convert list to dict
                                    it = iter(fields)
                                    d = {}
                                    for k in it:
                                        try:
                                            v = next(it)
                                        except StopIteration:
                                            v = b''
                                        k_s = k.decode() if isinstance(k, bytes) else k
                                        v_s = v.decode() if isinstance(v, bytes) else v
                                        d[k_s] = v_s
                                    payload_raw = d.get('payload')
                                elif isinstance(fields, dict):
                                    payload_raw = fields.get('payload')

                                if payload_raw:
                                    try:
                                        data = json.loads(payload_raw)
                                    except Exception:
                                        data = {'raw': payload_raw}

                                    # Prepare and validate outgoing payload
                                    outgoing = _prepare_outgoing_payload(stream_key, data)

                                    # If payload invalid, drop silently (do not forward to clients)
                                    if outgoing is None:
                                        # strict drop policy: just log and continue
                                        try:
                                            logger.debug(f"Dropping invalid payload for {stream_key} data_sample={repr(data)[:500]}")
                                        except Exception:
                                            pass
                                        continue

                                    # Fan-out to subscribers
                                    subs = STREAM_SUBSCRIBERS.get(stream_key, set()).copy()
                                    for ws in list(subs):
                                        try:
                                            await ws.send_json(outgoing)
                                        except Exception:
                                            # remove dead websocket
                                            try:
                                                STREAM_SUBSCRIBERS[stream_key].remove(ws)
                                            except Exception:
                                                pass

                                # Acknowledge
                                try:
                                    await redis_client.execute_command('XACK', stream_key, group_name, entry_id)
                                    if PROM_AVAILABLE:
                                        try:
                                            XACK_COUNTER.labels(stream=stream_key).inc()
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                            except Exception as e:
                                logger.error(f"Error handling stream entry: {e}")

                except Exception as inner:
                    logger.error(f"Stream worker error for {stream_key}: {inner}")
                    await asyncio.sleep(1)
        finally:
            # cleanup
            try:
                await redis_client.close()
            except Exception:
                pass
            STREAM_WORKERS.pop(stream_key, None)
            logger.info(f"Stopped stream worker for {stream_key}")

    async def _pending_scavenger():
        """Periodically inspect PEL and claim stale messages.

        Simpler, safer flow:
        - XPENDING to list recent pending entries
        - For each entry, if idle >= threshold and owned by another consumer -> XCLAIM
        - Process claimed entries (fan-out + XACK)
        """
        logger.info(f"Starting pending scavenger for {stream_key} (claim_idle_ms={STREAM_CLAIM_IDLE_MS})")
        try:
            while True:
                # list pending entries (small window)
                try:
                    # Use high-level helper when available to get a predictable structure
                    try:
                        resp = await redis_client.xpending(stream_key, group_name, '-', '+', 50)
                    except Exception:
                        # fallback to raw execute_command if xpending not supported
                        resp = await redis_client.execute_command('XPENDING', stream_key, group_name, '-', '+', 50)
                except Exception as e:
                    # Log the full exception and pause; sometimes redis client returns unexpected types
                    logger.debug(f"XPENDING failed for {stream_key}: {e} (type={type(e)})")
                    await asyncio.sleep(STREAM_PENDING_CHECK_INTERVAL)
                    continue

                if not resp:
                    # update XLEN/PENDING gauges even when no pending entries
                    if PROM_AVAILABLE:
                        try:
                            try:
                                xlen = await redis_client.execute_command('XLEN', stream_key)
                            except Exception:
                                xlen = 0
                            STREAM_XLEN.labels(stream=stream_key).set(int(xlen))
                        except Exception:
                            pass
                    await asyncio.sleep(STREAM_PENDING_CHECK_INTERVAL)
                    continue

                claimed_this_cycle = 0
                for item in resp:
                    # Parse item defensively using helper
                    try:
                        entry_id, owner, idle_ms = _parse_xpending_item(item)
                    except Exception as e:
                        try:
                            logger.debug(f"XPENDING parse failed for {stream_key}: {e} item={repr(item)} resp_sample={repr(resp)[:1000]}")
                        except Exception:
                            logger.debug(f"XPENDING parse failed for {stream_key}: {e} (and failed to repr resp)")
                        continue

                    if idle_ms < STREAM_CLAIM_IDLE_MS or owner == consumer_name:
                        continue

                    # Respect batch limit to avoid claiming too many entries at once
                    if claimed_this_cycle >= STREAM_CLAIM_BATCH:
                        # small backoff to avoid hot-looping
                        await asyncio.sleep(STREAM_CLAIM_BACKOFF)
                        break

                    # Try to claim this entry
                    try:
                        claimed = await redis_client.execute_command('XCLAIM', stream_key, group_name, consumer_name, STREAM_CLAIM_IDLE_MS, entry_id)
                    except Exception as e:
                        logger.debug(f"XCLAIM failed for {entry_id} on {stream_key}: {e}")
                        continue

                    if not claimed:
                        continue

                    claimed_this_cycle += 1

                    # Process claimed entries
                    for centry in claimed:
                        try:
                            cid = centry[0].decode() if isinstance(centry[0], bytes) else centry[0]
                            fields = centry[1]
                            payload_raw = None
                            if isinstance(fields, list):
                                it = iter(fields)
                                d = {}
                                for k in it:
                                    try:
                                        v = next(it)
                                    except StopIteration:
                                        v = b''
                                    k_s = k.decode() if isinstance(k, bytes) else k
                                    v_s = v.decode() if isinstance(v, bytes) else v
                                    d[k_s] = v_s
                                payload_raw = d.get('payload')
                            elif isinstance(fields, dict):
                                payload_raw = fields.get('payload')

                            if payload_raw:
                                try:
                                    data = json.loads(payload_raw)
                                except Exception:
                                    data = {'raw': payload_raw}

                                outgoing = _prepare_outgoing_payload(stream_key, data)

                                if outgoing is None:
                                    try:
                                        logger.debug(f"Dropping invalid claimed payload for {stream_key} data_sample={repr(data)[:500]}")
                                    except Exception:
                                        pass
                                    continue

                                subs = STREAM_SUBSCRIBERS.get(stream_key, set()).copy()
                                for ws in list(subs):
                                    try:
                                        await ws.send_json(outgoing)
                                    except Exception:
                                        try:
                                            STREAM_SUBSCRIBERS[stream_key].remove(ws)
                                        except Exception:
                                            pass

                            # Acknowledge claimed entry
                            try:
                                await redis_client.execute_command('XACK', stream_key, group_name, cid)
                            except Exception:
                                pass
                        except Exception as e:
                            logger.error(f"Error processing claimed entry: {e}")

                    # update XLEN and pending count after processing
                    if PROM_AVAILABLE:
                        try:
                            try:
                                xlen = await redis_client.execute_command('XLEN', stream_key)
                            except Exception:
                                xlen = 0
                            STREAM_XLEN.labels(stream=stream_key).set(int(xlen))
                        except Exception:
                            pass

                await asyncio.sleep(STREAM_PENDING_CHECK_INTERVAL)
        finally:
            logger.info(f"Stopped pending scavenger for {stream_key}")

    # Start the main worker task
    task = asyncio.create_task(_worker())

    # Start the pending-scavenger task
    scavenger_task = asyncio.create_task(_pending_scavenger())

    # store both tasks (worker + scavenger) so cleanup can cancel both
    STREAM_WORKERS[stream_key] = {
        'task': task,
        'client': redis_client,
        'consumer': consumer_name,
        'scavenger': scavenger_task,
    }


# ============================================================================
# WEBSOCKET CANDLES ENDPOINT
# ============================================================================

@router.websocket("/ws/candles/{symbol}/{timeframe}")
async def websocket_candles(
    websocket: WebSocket,
    symbol: str = Path(..., description="Trading pair (BTCUSDT)"),
    timeframe: str = Path(..., description="Timeframe (1, 5, 15, 60, D)")
):
    """
    WebSocket endpoint для real-time свечей (candles/klines)
    
    **Как использовать:**
    
    1. Подключиться к WebSocket:
       ```javascript
       const ws = new WebSocket('ws://localhost:8000/api/v1/live/ws/candles/BTCUSDT/1');
       ```
    
    2. Получать real-time обновления:
       ```javascript
       ws.onmessage = (event) => {
           const data = JSON.parse(event.data);
           console.log('Candle update:', data);
       };
       ```
    
    **Формат сообщения:**
    ```json
    {
        "type": "update",
        "subscription": "candles",
        "symbol": "BTCUSDT",
        "timeframe": "1",
        "candle": {
            "timestamp": 1697520000000,
            "open": "28350.50",
            "high": "28365.00",
            "low": "28340.00",
            "close": "28355.25",
            "volume": "125.345",
            "confirm": false
        },
        "received_at": "2024-10-17T10:00:00.123456Z"
    }
    ```
    
    **Heartbeat:**
    Каждые 30 секунд отправляется heartbeat для поддержания соединения:
    ```json
    {
        "type": "heartbeat",
        "timestamp": "2024-10-17T10:00:00Z"
    }
    ```
    
    **Требования:**
    - Redis должен быть запущен
    - Bybit WebSocket Worker должен быть активен
    - Symbol должен быть в верхнем регистре (BTCUSDT, ETHUSDT)
    - Timeframe: 1, 3, 5, 15, 30, 60, 120, 240, D, W, M
    """
    
    # Validate and format inputs
    symbol = symbol.upper()
    
    # Accept connection
    await websocket.accept()
    
    logger.info(f"🔌 WebSocket connected: {symbol} {timeframe}m")
    
    # Create Redis client
    redis_client = None
    
    try:
        # Connect to Redis (validate connectivity)
        redis_client = await get_redis_client()
        await redis_client.ping()

        # Stream key used by publisher
        channel = f"candles:{symbol}:{timeframe}"
        stream_key = f"stream:{channel}"

        logger.info(f"📡 Listening Redis stream: {stream_key}")

        # Send confirmation message
        confirmation = SubscriptionResponse(
            success=True,
            message=f"Subscribed to {symbol} candles ({timeframe}m)",
            subscription=WebSocketSubscription(
                action="subscribe",
                type="candles",
                symbol=symbol,
                timeframe=timeframe
            )
        )

        await websocket.send_json(confirmation.model_dump(mode='json'))

        # Register websocket in subscribers set
        subs = STREAM_SUBSCRIBERS.setdefault(stream_key, set())
        subs.add(websocket)

        # Ensure background worker exists
        await _ensure_stream_worker(stream_key)

        # Heartbeat task
        async def send_heartbeat():
            while True:
                try:
                    await asyncio.sleep(30)
                    heartbeat = HeartbeatMessage()
                    await websocket.send_json(heartbeat.model_dump(mode='json'))
                except Exception:
                    break

        heartbeat_task = asyncio.create_task(send_heartbeat())
        
        # Wait for client disconnect or errors
        try:
            while True:
                # Keep connection alive and handle client messages
                data = await websocket.receive_text()
                
                # Client can send ping messages
                if data == "ping":
                    await websocket.send_text("pong")
                    
        except WebSocketDisconnect:
            logger.info(f"🔌 WebSocket disconnected: {symbol} {timeframe}m")
        
        finally:
            # Cancel heartbeat and remove subscriber
            heartbeat_task.cancel()
            try:
                STREAM_SUBSCRIBERS.get(stream_key, set()).discard(websocket)
            except Exception:
                pass
            
    except Exception as e:
        logger.error(f"❌ WebSocket error for {symbol} {timeframe}m: {e}")
        
        # Send error message to client
        error_msg = WebSocketError(
            error_code="INTERNAL_ERROR",
            error_message=str(e)
        )
        
        try:
            await websocket.send_json(error_msg.model_dump(mode='json'))
        except:
            pass
        
    finally:
        # Clean up
        # nothing to unsubscribe for streams
        
        if redis_client:
            await redis_client.close()
        
        logger.info(f"✅ Cleanup completed for {symbol} {timeframe}m")


# ============================================================================
# WEBSOCKET TRADES ENDPOINT
# ============================================================================

@router.websocket("/ws/trades/{symbol}")
async def websocket_trades(
    websocket: WebSocket,
    symbol: str = Path(..., description="Trading pair (BTCUSDT)")
):
    """
    WebSocket endpoint для real-time сделок (trades)
    
    **Использование:**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/live/ws/trades/BTCUSDT');
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Trade:', data);
    };
    ```
    
    **Формат сообщения:**
    ```json
    {
        "type": "update",
        "subscription": "trades",
        "symbol": "BTCUSDT",
        "trades": [
            {
                "timestamp": 1697520000000,
                "side": "Buy",
                "price": "28355.50",
                "size": "0.125",
                "trade_id": "abc123"
            }
        ],
        "received_at": "2024-10-17T10:00:00.123456Z"
    }
    ```
    """
    
    symbol = symbol.upper()
    await websocket.accept()
    
    logger.info(f"🔌 WebSocket connected (trades): {symbol}")
    
    redis_client = None
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        channel = f"trades:{symbol}"
        stream_key = f"stream:{channel}"

        logger.info(f"📡 Registering trades subscriber for: {stream_key}")

        await websocket.send_json({
            "success": True,
            "message": f"Subscribed to {symbol} trades"
        })

        subs = STREAM_SUBSCRIBERS.setdefault(stream_key, set())
        subs.add(websocket)
        await _ensure_stream_worker(stream_key)

        # Heartbeat
        async def send_heartbeat_t():
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_json({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()})
                except Exception:
                    break

        heartbeat_task = asyncio.create_task(send_heartbeat_t())

        try:
            while True:
                data = await websocket.receive_text()
                if data == 'ping':
                    await websocket.send_text('pong')
        except WebSocketDisconnect:
            logger.info(f"🔌 WebSocket disconnected (trades): {symbol}")
        finally:
            heartbeat_task.cancel()
            try:
                STREAM_SUBSCRIBERS.get(stream_key, set()).discard(websocket)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"❌ WebSocket error (trades) for {symbol}: {e}")
    finally:
        if redis_client:
            try:
                await redis_client.close()
            except Exception:
                pass
        logger.info(f"✅ Cleanup completed (trades) for {symbol}")


# ============================================================================
# WEBSOCKET TICKER ENDPOINT
# ============================================================================

@router.websocket("/ws/ticker/{symbol}")
async def websocket_ticker(
    websocket: WebSocket,
    symbol: str = Path(..., description="Trading pair (BTCUSDT)")
):
    """
    WebSocket endpoint для real-time тикера (24h statistics)
    
    **Использование:**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/live/ws/ticker/BTCUSDT');
    ```
    
    **Формат сообщения:**
    ```json
    {
        "type": "update",
        "subscription": "ticker",
        "ticker": {
            "symbol": "BTCUSDT",
            "last_price": "28355.50",
            "high_price_24h": "29000.00",
            "low_price_24h": "27800.00",
            "volume_24h": "12543.567",
            "price_24h_pcnt": "2.35"
        },
        "received_at": "2024-10-17T10:00:00Z"
    }
    ```
    """
    
    symbol = symbol.upper()
    await websocket.accept()
    
    logger.info(f"🔌 WebSocket connected (ticker): {symbol}")
    
    redis_client = None
    try:
        redis_client = await get_redis_client()
        channel = f"ticker:{symbol}"
        stream_key = f"stream:{channel}"

        logger.info(f"📡 Registering ticker subscriber for: {stream_key}")

        await websocket.send_json({
            "success": True,
            "message": f"Subscribed to {symbol} ticker"
        })

        subs = STREAM_SUBSCRIBERS.setdefault(stream_key, set())
        subs.add(websocket)
        await _ensure_stream_worker(stream_key)

        # Heartbeat
        async def send_heartbeat_t():
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_json({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()})
                except Exception:
                    break

        heartbeat_task = asyncio.create_task(send_heartbeat_t())

        try:
            while True:
                data = await websocket.receive_text()
                if data == 'ping':
                    await websocket.send_text('pong')
        except WebSocketDisconnect:
            logger.info(f"🔌 WebSocket disconnected (ticker): {symbol}")
        finally:
            heartbeat_task.cancel()
            try:
                STREAM_SUBSCRIBERS.get(stream_key, set()).discard(websocket)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"❌ WebSocket error (ticker) for {symbol}: {e}")
    finally:
        if redis_client:
            await redis_client.close()
        logger.info(f"✅ Cleanup completed (ticker) for {symbol}")


# ============================================================================
# REST API - ACTIVE CHANNELS
# ============================================================================

@router.get("/channels", response_class=JSONResponse)
async def get_active_channels():
    """
    Получить список активных Redis Pub/Sub каналов
    
    **Использование:**
    ```bash
    curl http://localhost:8000/api/v1/live/channels
    ```
    
    **Ответ:**
    ```json
    {
        "success": true,
        "channels": [
            "candles:BTCUSDT:1",
            "candles:BTCUSDT:5",
            "candles:ETHUSDT:1",
            "trades:BTCUSDT",
            "ticker:BTCUSDT"
        ],
        "count": 5
    }
    ```
    """
    
    try:
        # Connect to Redis
        redis_client = await aioredis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            decode_responses=True
        )
        
        # Get Stream keys (pattern: stream:*)
        keys = await redis_client.keys('stream:*')
        # Normalize back to channel names
        channels = [k.replace('stream:', '') for k in keys]

        await redis_client.close()

        return {
            "success": True,
            "channels": channels,
            "count": len(channels)
        }
        
    except Exception as e:
        logger.error(f"Error getting active channels: {e}")
        return {
            "success": False,
            "error": str(e),
            "channels": [],
            "count": 0
        }


@router.get("/health", response_class=JSONResponse)
async def health_check():
    """
    Health check endpoint
    
    Проверяет:
    - Redis доступность
    - Активные каналы
    
    **Использование:**
    ```bash
    curl http://localhost:8000/api/v1/live/health
    ```
    """
    
    try:
        # Check Redis connection
        redis_client = await aioredis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            decode_responses=True
        )
        
        await redis_client.ping()
        
        # Get stream key count
        keys = await redis_client.keys('stream:*')
        await redis_client.close()
        
        return {
            "status": "healthy",
            "redis": "connected",
            "active_streams": len(keys),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "redis": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
