#!/usr/bin/env python3
"""
CLI Tool: Send to DeepSeek Agent
Simulates VS Code Extension "Send to DeepSeek Agent" command
"""

import asyncio
import json
import sys
import websockets
from loguru import logger
from datetime import datetime

async def send_to_deepseek_cli(message: str):
    """Send message to DeepSeek Agent via WebSocket"""
    uri = "ws://localhost:8000/api/v1/agent/ws/cli-copilot"
    
    logger.info("🔌 Connecting to Agent backend...")
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.success("✅ Connected!")
            
            # Create message payload
            payload = {
                "command": "send_message",
                "from_agent": "copilot",
                "to_agent": "deepseek",
                "content": message,
                "conversation_id": f"cli-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            }
            
            logger.info(f"\n📤 Sending to DeepSeek Agent:")
            logger.info(f"   '{message[:100]}{'...' if len(message) > 100 else ''}'")
            logger.info(f"\n⏳ Waiting for response...")
            
            # Send message
            await websocket.send(json.dumps(payload))
            
            # Wait for response
            start_time = datetime.now()
            response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
            duration = (datetime.now() - start_time).total_seconds()
            
            data = json.loads(response)
            
            if data.get("type") == "message_response":
                content = data.get("content", "")
                
                logger.success(f"\n✅ DeepSeek Response ({duration:.2f}s):")
                print("\n" + "=" * 80)
                print(content)
                print("=" * 80 + "\n")
                
                return True
            else:
                logger.warning(f"⚠️ Unexpected response: {data}")
                return False
                
    except asyncio.TimeoutError:
        logger.error("❌ Timeout: No response from DeepSeek (30s)")
        logger.info("💡 Backend might be slow or not running")
        return False
    except websockets.exceptions.ConnectionRefusedError:
        logger.error("❌ Connection refused: Backend not running")
        logger.info("💡 Start backend: py run_backend.py")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

async def interactive_mode():
    """Interactive CLI mode"""
    print("\n" + "=" * 80)
    print("🤖 DeepSeek Agent - Interactive Mode")
    print("=" * 80)
    print("Type your message and press Enter")
    print("Type 'exit' or 'quit' to stop")
    print("=" * 80 + "\n")
    
    while True:
        try:
            print("📝 Your message: ", end="", flush=True)
            message = input().strip()
            
            if not message:
                continue
            
            if message.lower() in ['exit', 'quit', 'q']:
                logger.info("\n👋 Goodbye!")
                break
            
            await send_to_deepseek_cli(message)
            
        except KeyboardInterrupt:
            logger.info("\n\n👋 Interrupted. Goodbye!")
            break
        except EOFError:
            break

async def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        # Single message mode
        message = " ".join(sys.argv[1:])
        await send_to_deepseek_cli(message)
    else:
        # Interactive mode
        await interactive_mode()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
