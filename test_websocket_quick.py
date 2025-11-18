"""
Быстрый тест Agent-to-Agent WebSocket подключения
"""

import asyncio
import websockets
import json

async def test_websocket():
    """Тест WebSocket соединения с Agent-to-Agent API"""
    uri = "ws://localhost:8000/api/v1/agent/ws/test-client"
    
    print(f"🔌 Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            
            # Отправить ping
            ping_msg = {"command": "ping"}
            print(f"📤 Sending: {ping_msg}")
            await websocket.send(json.dumps(ping_msg))
            
            # Получить pong
            response = await websocket.recv()
            print(f"📥 Received: {response}")
            
            # Отправить сообщение агенту
            message = {
                "command": "send_message",
                "from_agent": "copilot",
                "to_agent": "deepseek",
                "content": "Привет! Это тест Agent-to-Agent системы. Ответь коротко: работает ли система?",
                "conversation_id": "test-123"
            }
            
            print(f"\n📤 Sending message to DeepSeek: {message['content'][:50]}...")
            await websocket.send(json.dumps(message))
            
            # Получить подтверждение
            response1 = await websocket.recv()
            print(f"📥 Confirmation: {response1}")
            
            # Подписаться на ответы
            subscribe_msg = {
                "command": "subscribe",
                "conversation_id": "test-123"
            }
            print(f"\n📡 Subscribing to conversation...")
            await websocket.send(json.dumps(subscribe_msg))
            
            # Ждать ответ от DeepSeek (таймаут 30 секунд)
            print("⏳ Waiting for DeepSeek response...")
            
            try:
                response2 = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                print(f"\n🤖 DeepSeek Response:")
                print("=" * 80)
                data = json.loads(response2)
                if data.get("type") == "message_response":
                    print(data.get("content", "No content"))
                else:
                    print(response2)
                print("=" * 80)
                
                print("\n✅ WebSocket test PASSED!")
                return True
                
            except asyncio.TimeoutError:
                print("\n⏰ Timeout waiting for response")
                return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Agent-to-Agent WebSocket Test\n")
    result = asyncio.run(test_websocket())
    
    if result:
        print("\n🎉 Test completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Backend is running ✅")
        print("   2. WebSocket connection works ✅")
        print("   3. Now test VS Code Extension (F5)")
    else:
        print("\n⚠️ Test failed. Check if backend is running on port 8000")
