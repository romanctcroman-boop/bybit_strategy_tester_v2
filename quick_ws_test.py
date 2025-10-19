"""Quick WebSocket test"""
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/api/v1/live/ws/candles/BTCUSDT/1"
    
    try:
        async with websockets.connect(uri) as ws:
            print("[OK] Connected to WebSocket")
            
            # Get confirmation
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"[OK] Subscription confirmed: {data.get('message')}")
            
            # Get first update
            print("\nWaiting for updates...")
            for i in range(3):
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get('type') == 'update':
                    candle = data.get('candle', {})
                    print(f"  Update #{i+1}: Close={candle.get('close')}, Volume={candle.get('volume')}")
            
            print("\n[OK] WebSocket is working!")
            
    except Exception as e:
        print(f"[X] Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
