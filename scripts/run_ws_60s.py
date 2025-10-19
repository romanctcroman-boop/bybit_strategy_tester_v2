import asyncio
import websockets
import time
import json

import sys

URI = 'ws://127.0.0.1:8000/api/v1/live/ws/candles/BTCUSDT/1'
# allow override via argv: python run_ws_60s.py 10
RUN_SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 60
RECV_TIMEOUT = 10
RECONNECT_DELAY = 1


async def listen_once(ws):
    try:
        msg = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        print(f'[{now}] MSG: {msg}')
    except asyncio.TimeoutError:
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        print(f'[{now}] Timeout waiting for message')
    except Exception as e:
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        print(f'[{now}] Receive error: {e}')
        raise


async def run():
    end_time = time.time() + RUN_SECONDS
    while time.time() < end_time:
        try:
            async with websockets.connect(URI) as ws:
                print(f'Connected to {URI}')
                # read until disconnect or time up
                while time.time() < end_time:
                    await listen_once(ws)
        except Exception as e:
            now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            print(f'[{now}] Connection error / reconnect: {e}')
        await asyncio.sleep(RECONNECT_DELAY)


if __name__ == '__main__':
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print('Interrupted')
