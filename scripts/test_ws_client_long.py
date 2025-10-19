import asyncio
import websockets
import time
import json

URI = 'ws://127.0.0.1:8000/api/v1/live/ws/candles/BTCUSDT/1'
RUN_SECONDS = 300  # 5 minutes
RECV_TIMEOUT = 10
RECONNECT_DELAY = 2

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
                    try:
                        await listen_once(ws)
                    except Exception:
                        break
        except Exception as e:
            now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            print(f'[{now}] Connection error / reconnect: {e}')
        # avoid tight loop
        await asyncio.sleep(RECONNECT_DELAY)

if __name__ == '__main__':
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print('Interrupted')
