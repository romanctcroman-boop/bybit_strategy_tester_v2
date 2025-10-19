import asyncio
import websockets
import json
import time

URL = 'ws://127.0.0.1:8000/api/v1/live/ws/candles/BTCUSDT/1'

async def run():
    async with websockets.connect(URL) as ws:
        print('connected')
        # read initial confirmation
        msg = await ws.recv()
        print('initial:', msg[:200])
        start = time.time()
        count = 0
        while time.time() - start < 60:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                count += 1
                if count % 10 == 0:
                    print(f"received {count} messages")
            except asyncio.TimeoutError:
                # no messages in 5s
                pass
        print('done; total=', count)

if __name__ == '__main__':
    asyncio.run(run())
