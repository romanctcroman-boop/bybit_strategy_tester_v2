import asyncio
import websockets

URI = 'ws://127.0.0.1:8000/api/v1/live/ws/candles/BTCUSDT/1'

async def run():
    try:
        async with websockets.connect(URI) as ws:
            print('Connected to', URI)
            # receive a few messages (or timeout)
            for i in range(10):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    print(f'MSG[{i}]:', msg)
                except asyncio.TimeoutError:
                    print('Timeout waiting for message')
                    break
    except Exception as e:
        print('Client error:', e)

if __name__ == '__main__':
    asyncio.run(run())
