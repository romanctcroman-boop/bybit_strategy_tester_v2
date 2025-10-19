"""
Simple WebSocket publisher worker.
Starts WebSocketManager, subscribes to configured symbols/timeframes
and keeps publishing incoming messages to Redis channels.

Usage:
    python -m backend.workers.ws_publisher

This is intended for local dev/testing. In production use a process manager
and run this as a service inside Docker or a VM.
"""

import argparse
import signal
import sys
import logging
import time
import random
import json
import redis
try:
    from prometheus_client import Counter, Gauge, start_http_server
    PROMETHEUS_AVAILABLE = True
except Exception:
    PROMETHEUS_AVAILABLE = False
from backend.services.websocket_manager import WebSocketManager
from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ws_publisher")

# Configure symbols/timeframes to subscribe
SUBSCRIPTIONS = [
    ("BTCUSDT", "1"),
    ("ETHUSDT", "1"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fake', action='store_true', help='Run in fake/emulation mode (generate synthetic data)')
    parser.add_argument('--redis', default=None, help='Redis URL for streams (overrides settings)')
    parser.add_argument('--fake-rate', type=float, default=1.0, help='Seconds between fake publish batches (float)')
    args = parser.parse_args()

    USE_FAKE = args.fake or bool(getattr(settings, 'USE_FAKE', False))

    manager = WebSocketManager(testnet=settings.BYBIT_TESTNET)

    # Register simple callbacks to log (and WebSocketManager will publish to Redis)
    for symbol, interval in SUBSCRIPTIONS:
        manager.subscribe_kline(symbol, interval, lambda d, s=symbol, i=interval: logger.debug(f"KLINE {s} {i}: {len(d)} items"))
        manager.subscribe_trade(symbol, lambda d, s=symbol: logger.debug(f"TRADE {s}: {len(d)} items"))

    def _shutdown(*args):
        logger.info("Shutting down ws_publisher")
        manager.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Starting WebSocket publisher")
    manager.start()

    # Start Prometheus metrics server (if available)
    if PROMETHEUS_AVAILABLE:
        try:
            # metrics served on 0.0.0.0:8001 so Prometheus in Docker/host can scrape it
            start_http_server(8001, addr='0.0.0.0')
            logger.info("Prometheus metrics HTTP server started on 0.0.0.0:8001")
        except Exception as e:
            logger.error(f"Cannot start Prometheus HTTP server: {e}")

    # If fake mode requested, start generator that writes to Redis Streams
    redis_client = None
    fake_task = None
    fake_stop_event = None
    fake_rate = float(getattr(args, 'fake_rate', 1.0))

    if USE_FAKE:
        redis_url = args.redis or getattr(settings, 'REDIS_URL', None) or f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        try:
            redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            logger.info(f"Starting fake publisher -> Redis {redis_url}")
        except Exception as e:
            logger.error(f"Cannot connect to Redis for fake mode: {e}")
            redis_client = None

        if redis_client:
            # Prometheus metrics for fake mode (label by stream)
            if PROMETHEUS_AVAILABLE:
                XADD_COUNTER = Counter('bybit_xadd_total', 'Number of XADD operations performed', ['stream'])
                XADD_LAST = Gauge('bybit_xadd_last_timestamp', 'Last XADD unix timestamp (ms)', ['stream'])

            def fake_generator(stop_event: 'threading.Event'):
                """Generate synthetic candles and trades and XADD to streams."""
                base_prices = {s: 30000.0 + random.random() * 1000 for s, _ in SUBSCRIPTIONS}
                while not stop_event.is_set():
                    for sym, interval in SUBSCRIPTIONS:
                        now_ts = int(time.time() * 1000)
                        # create a small random walk
                        base = base_prices[sym]
                        o = base + random.uniform(-5, 5)
                        c = o + random.uniform(-3, 3)
                        h = max(o, c) + random.uniform(0, 2)
                        l = min(o, c) - random.uniform(0, 2)
                        v = round(random.uniform(0.1, 10.0), 6)

                        candle = {
                            'timestamp': now_ts,
                            'open': f"{o:.8f}",
                            'high': f"{h:.8f}",
                            'low': f"{l:.8f}",
                            'close': f"{c:.8f}",
                            'volume': f"{v}",
                            'confirm': False
                        }

                        payload = {
                            'type': 'update',
                            'subscription': 'candles',
                            'symbol': sym,
                            'timeframe': interval,
                            'candle': candle,
                            'received_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                        }

                        stream_key = f"stream:candles:{sym}:{interval}"
                        try:
                            # Use MAXLEN to limit stream growth (approximate trimming)
                            entry_id = redis_client.xadd(stream_key, {'payload': json.dumps(payload)}, maxlen=10000, approximate=True)
                            # Log at INFO so foreground runs display activity by default
                            logger.info(f"Fake XADD {stream_key} id={entry_id}")
                            if PROMETHEUS_AVAILABLE:
                                try:
                                    XADD_COUNTER.labels(stream=stream_key).inc()
                                    XADD_LAST.labels(stream=stream_key).set(int(time.time() * 1000))
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.error(f"Fake publish failed: {e}")

                    # advance base prices a bit
                    for s in base_prices:
                        base_prices[s] += random.uniform(-1, 1)

                    # sleep according to fake_rate in small increments to be responsive to shutdown
                    waited = 0.0
                    while waited < fake_rate and not stop_event.is_set():
                        time.sleep(0.1)
                        waited += 0.1

                    # occasional heartbeat so operator sees the process is alive
                    if int(time.time()) % max(30, int(fake_rate)) == 0:
                        logger.info("Fake publisher heartbeat: running")

        # Use a dedicated thread for the blocking fake generator to avoid
        # touching asyncio event loop (avoids DeprecationWarning on Python 3.10+)
        import threading
        fake_stop_event = threading.Event()
        fake_thread = threading.Thread(target=fake_generator, args=(fake_stop_event,), daemon=True)
        fake_thread.start()
        fake_task = fake_thread

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown()
    finally:
        if fake_task:
            try:
                # signal the fake generator to stop and wait briefly for thread exit
                if fake_stop_event:
                    fake_stop_event.set()
                if hasattr(fake_task, 'join'):
                    fake_task.join(timeout=2)
            except Exception:
                pass
        if redis_client:
            try:
                redis_client.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
