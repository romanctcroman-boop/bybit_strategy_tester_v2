"""Capture one real message from Bybit public WebSocket and publish it to Redis.

Usage:
    .\.venv\Scripts\Activate.ps1
    python scripts\capture_and_publish.py --channel kline --symbol BTCUSDT --interval 1

This will subscribe to kline.1.BTCUSDT and publish first received message to Redis key `candles:BTCUSDT:1`.
"""
import asyncio
import json
import argparse
import os
import sys
import time
from datetime import datetime

import websockets
import redis

BYBIT_WS = 'wss://stream.bybit.com/v5/public/linear'


async def try_connect_and_publish(channel, symbol, interval, redis_url, open_timeout):
    """One attempt to connect to Bybit and publish first matching message."""
    async with websockets.connect(BYBIT_WS, open_timeout=open_timeout) as ws:
        # Build topic
        if channel == 'kline':
            topic = f'kline.{interval}.{symbol}'
        elif channel == 'trade':
            topic = f'publicTrade.{symbol}'
        else:
            topic = f'{channel}.{symbol}'

        sub_msg = {'op': 'subscribe', 'args': [topic]}
        await ws.send(json.dumps(sub_msg))
        print(f'Subscribed to {topic}')

        # Wait for messages
        while True:
            raw = await ws.recv()
            try:
                data = json.loads(raw)
            except Exception:
                print('Received non-JSON message:', raw)
                continue

            # Filter data messages containing topic
            if 'topic' in data and data['topic'] == topic:
                print('Received data message for', topic)
                # Prepare Redis channel name
                if channel == 'kline':
                    rchan = f'candles:{symbol}:{interval}'
                elif channel == 'trade':
                    rchan = f'trades:{symbol}'
                else:
                    rchan = topic.replace('.', ':')

                # Build payload - forward data as-is with received_at (ISO)
                payload = {
                    'type': 'update',
                    'subscription': 'candles' if channel == 'kline' else 'trades',
                    'symbol': symbol,
                    'timeframe': interval if channel == 'kline' else None,
                    'data': data.get('data'),
                    'received_at': datetime.utcnow().isoformat() + 'Z'
                }

                # Use redis sync client to XADD to stream for durable delivery
                r = redis.Redis.from_url(redis_url, decode_responses=True)
                stream_key = f'stream:{rchan}'
                entry_id = r.xadd(stream_key, {'payload': json.dumps(payload)})
                # Get approximate length (may be expensive for large streams) - use XLEN
                try:
                    length = r.xlen(stream_key)
                except Exception:
                    length = None
                print(f'XADD -> {stream_key} id={entry_id} len={length}')
                return entry_id


async def run_with_retries(channel, symbol, interval, redis_url, open_timeout, retries, backoff):
    attempt = 0
    while attempt <= retries:
        try:
            attempt += 1
            print(f'Attempt {attempt} of {retries + 1} (open_timeout={open_timeout}s)')
            result = await try_connect_and_publish(channel, symbol, interval, redis_url, open_timeout)
            return result
        except Exception as e:
            print(f'Attempt {attempt} failed: {e}')
            if attempt > retries:
                raise
            sleep = backoff * (2 ** (attempt - 1))
            print(f'Waiting {sleep}s before retrying...')
            time.sleep(sleep)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', default='kline')
    parser.add_argument('--symbol', default='BTCUSDT')
    parser.add_argument('--interval', default='1')
    parser.add_argument('--redis', default=os.environ.get('REDIS_URL') or 'redis://localhost:6379/0')
    parser.add_argument('--open-timeout', type=float, default=20.0, help='WebSocket open timeout in seconds')
    parser.add_argument('--retries', type=int, default=3, help='Number of retries on timeout')
    parser.add_argument('--backoff', type=float, default=2.0, help='Base backoff seconds (exponential)')
    args = parser.parse_args()

    try:
        asyncio.run(run_with_retries(args.channel, args.symbol, args.interval, args.redis, args.open_timeout, args.retries, args.backoff))
    except KeyboardInterrupt:
        print('Interrupted')
        sys.exit(0)
