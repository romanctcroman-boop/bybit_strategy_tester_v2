"""Test send_request directly"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.agents.unified_agent_interface import (
    get_agent_interface,
    AgentRequest,
    AgentType
)
from loguru import logger

async def test():
    logger.info("Initializing agent interface...")
    agent = get_agent_interface()
    
    logger.info("Creating request...")
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="test",
        prompt="Return JSON: {\"status\": \"OK\", \"message\": \"Test successful\"}",
        context={}
    )
    
    logger.info("Sending request...")
    response = await agent.send_request(request)
    
    if response.success:
        logger.info(f"✅ Success: {response.content[:200]}")
    else:
        logger.error(f"❌ Failed: {response.error}")
    
    logger.info("Test complete")
    return response

if __name__ == "__main__":
    logger.info("Starting test...")
    result = asyncio.run(test())
    logger.info(f"Result: {result.success}")
    logger.info("Done")
