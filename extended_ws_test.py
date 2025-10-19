"""Extended WebSocket test - 30 seconds"""
import asyncio
import websockets
import json
import time

async def test():
    uri = "ws://localhost:8000/api/v1/live/ws/candles/BTCUSDT/1"
    
    try:
        async with websockets.connect(uri) as ws:
            print("[OK] Connected to WebSocket")
            print(f"Time: {time.strftime('%H:%M:%S')}")
            
            # Get confirmation
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"[OK] {data.get('message')}")
            
            # Listen for 30 seconds
            print("\nListening for real-time updates (30 seconds)...")
            print("=" * 60)
            
            start_time = time.time()
            update_count = 0
            
            while time.time() - start_time < 30:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    
                    if data.get('type') == 'update':
                        update_count += 1
                        candle = data.get('candle', {})
                        timestamp = time.strftime('%H:%M:%S')
                        confirm_status = "✅ Closed" if candle.get('confirm') else "⏳ Ongoing"
                        
                        print(f"[{timestamp}] Update #{update_count}: "
                              f"Close={candle.get('close'):>10} | "
                              f"Volume={candle.get('volume'):>8} | "
                              f"{confirm_status}")
                              
                    elif data.get('type') == 'heartbeat':
                        print(f"[{time.strftime('%H:%M:%S')}] 💓 Heartbeat")
                        
                except asyncio.TimeoutError:
                    print(f"[{time.strftime('%H:%M:%S')}] ⏱️  No updates (timeout)")
            
            print("=" * 60)
            print(f"\n[OK] Test complete! Received {update_count} candle updates")
            
    except Exception as e:
        print(f"\n[X] Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
