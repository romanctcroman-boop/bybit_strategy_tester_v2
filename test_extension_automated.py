#!/usr/bin/env python3
"""
Automated VS Code Extension Test
Tests WebSocket communication between VS Code Extension and Backend
"""

import asyncio
import json
import websockets
from loguru import logger
from datetime import datetime

class ExtensionTester:
    def __init__(self):
        self.ws_url = "ws://localhost:8000/api/v1/agent/ws/test-extension"
        self.websocket = None
        
    async def connect(self):
        """Connect to WebSocket server"""
        logger.info(f"🔌 Connecting to {self.ws_url}...")
        try:
            self.websocket = await websockets.connect(self.ws_url)
            logger.success("✅ Connected!")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    async def test_ping(self):
        """Test ping/pong"""
        logger.info("\n📡 Test 1: Ping/Pong")
        logger.info("-" * 60)
        
        try:
            # Send ping
            await self.websocket.send(json.dumps({"command": "ping"}))
            logger.info("📤 Sent: ping")
            
            # Receive pong
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            if data.get("type") == "pong":
                logger.success("✅ Ping/Pong PASSED")
                return True
            else:
                logger.error(f"❌ Unexpected response: {data}")
                return False
                
        except asyncio.TimeoutError:
            logger.error("❌ Ping/Pong FAILED (timeout)")
            return False
        except Exception as e:
            logger.error(f"❌ Ping/Pong FAILED: {e}")
            return False
    
    async def test_send_to_deepseek(self):
        """Test sending message to DeepSeek (simulates Extension command)"""
        logger.info("\n📨 Test 2: Send to DeepSeek Agent")
        logger.info("-" * 60)
        
        try:
            message = {
                "command": "send_message",
                "from_agent": "vscode-copilot",
                "to_agent": "deepseek",
                "content": "Explain Agent-to-Agent communication in one sentence.",
                "conversation_id": "test-extension-001"
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"📤 Sent: {message['content']}")
            
            # Wait for confirmation
            response = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
            data = json.loads(response)
            
            logger.info(f"📥 Response type: {data.get('type')}")
            
            if data.get("type") == "message_response":
                content = data.get("content", "")[:200]
                logger.success(f"✅ DeepSeek Response: {content}...")
                return True
            else:
                logger.warning(f"⚠️ Got: {data}")
                return False
                
        except asyncio.TimeoutError:
            logger.error("❌ Send to DeepSeek FAILED (timeout)")
            return False
        except Exception as e:
            logger.error(f"❌ Send to DeepSeek FAILED: {e}")
            return False
    
    async def test_consensus(self):
        """Test multi-agent consensus (simulates Extension command)"""
        logger.info("\n🤝 Test 3: Multi-Agent Consensus")
        logger.info("-" * 60)
        
        try:
            message = {
                "command": "request_consensus",
                "from_agent": "vscode-copilot",
                "agents": ["deepseek", "perplexity"],
                "content": "What is the best trading indicator: EMA or RSI?",
                "conversation_id": "test-consensus-001"
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"📤 Requesting consensus from 2 agents...")
            
            # Wait for consensus response (may take longer)
            response = await asyncio.wait_for(self.websocket.recv(), timeout=60.0)
            data = json.loads(response)
            
            logger.info(f"📥 Response type: {data.get('type')}")
            
            if "consensus" in str(data).lower() or data.get("type") == "consensus_response":
                logger.success("✅ Consensus PASSED")
                logger.info(f"   Result: {str(data)[:200]}...")
                return True
            else:
                logger.warning(f"⚠️ Partial success, got: {data.get('type')}")
                return False
                
        except asyncio.TimeoutError:
            logger.error("❌ Consensus FAILED (timeout)")
            return False
        except Exception as e:
            logger.error(f"❌ Consensus FAILED: {e}")
            return False
    
    async def test_subscribe(self):
        """Test conversation subscription"""
        logger.info("\n🎧 Test 4: Subscribe to Conversation")
        logger.info("-" * 60)
        
        try:
            message = {
                "command": "subscribe",
                "conversation_id": "test-extension-001"
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info("📤 Subscribed to conversation")
            
            # Wait for subscription confirmation
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            if data.get("type") == "subscribed":
                logger.success("✅ Subscribe PASSED")
                return True
            else:
                logger.warning(f"⚠️ Got: {data}")
                return False
                
        except asyncio.TimeoutError:
            logger.error("❌ Subscribe FAILED (timeout)")
            return False
        except Exception as e:
            logger.error(f"❌ Subscribe FAILED: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("=" * 80)
        logger.info("🧪 VS Code Extension - Automated WebSocket Test")
        logger.info("=" * 80)
        logger.info(f"Test Date: {datetime.now()}")
        logger.info(f"WebSocket URL: {self.ws_url}")
        logger.info("=" * 80)
        
        # Connect
        if not await self.connect():
            logger.error("❌ Cannot connect to backend. Is it running?")
            logger.info("\n💡 Start backend: py run_backend.py")
            return
        
        results = []
        
        # Test 1: Ping/Pong
        results.append(("Ping/Pong", await self.test_ping()))
        
        # Test 2: Send to DeepSeek
        results.append(("Send to DeepSeek", await self.test_send_to_deepseek()))
        
        # Test 3: Subscribe
        results.append(("Subscribe", await self.test_subscribe()))
        
        # Test 4: Consensus (optional, takes longer)
        # results.append(("Multi-Agent Consensus", await self.test_consensus()))
        
        # Close connection
        await self.websocket.close()
        logger.info("\n🔌 Connection closed")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 80)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"  {test_name:30s} {status}")
        
        logger.info("-" * 80)
        logger.info(f"  Total: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
        logger.info("=" * 80)
        
        if passed == total:
            logger.success("\n🎉 ALL TESTS PASSED! Extension backend integration works!")
            logger.info("\n📝 Next step: Test in VS Code (F5 in vscode-extension/)")
        else:
            logger.warning(f"\n⚠️ {total - passed} test(s) failed. Check backend connection.")

async def main():
    tester = ExtensionTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
