#!/usr/bin/env python3
"""
Quick Extension WebSocket Test - Direct message format test
"""

import asyncio
import json
import websockets
from loguru import logger

async def test_extension_websocket():
    uri = "ws://localhost:8000/api/v1/agent/ws/vscode-test"
    
    logger.info(f"🔌 Connecting to {uri}...")
    
    async with websockets.connect(uri) as websocket:
        logger.success("✅ Connected!")
        
        # Test 1: Ping
        logger.info("\n📡 Test 1: Ping")
        await websocket.send(json.dumps({"command": "ping"}))
        response = await websocket.recv()
        data = json.loads(response)
        logger.info(f"   Response: {data}")
        
        # Test 2: Send message to DeepSeek
        logger.info("\n📨 Test 2: Send to DeepSeek")
        message = {
            "command": "send_message",
            "from_agent": "copilot",
            "to_agent": "deepseek",
            "content": "Answer in one short sentence: What is Agent-to-Agent communication?",
            "conversation_id": "test-quick-123"
        }
        
        logger.info(f"   Sending: {message['content']}")
        await websocket.send(json.dumps(message))
        
        logger.info("   Waiting for response...")
        
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
            data = json.loads(response)
            
            logger.success(f"   ✅ Got response!")
            logger.info(f"   Type: {data.get('type')}")
            logger.info(f"   Content: {data.get('content', '')[:150]}...")
            
        except asyncio.TimeoutError:
            logger.error("   ❌ Timeout waiting for response")
        
        # Test 3: Subscribe
        logger.info("\n🎧 Test 3: Subscribe to conversation")
        subscribe_msg = {
            "command": "subscribe",
            "conversation_id": "test-quick-123"
        }
        
        await websocket.send(json.dumps(subscribe_msg))
        response = await websocket.recv()
        data = json.loads(response)
        logger.info(f"   Response: {data}")
        
        logger.success("\n🎉 All basic tests completed!")

if __name__ == "__main__":
    asyncio.run(test_extension_websocket())
