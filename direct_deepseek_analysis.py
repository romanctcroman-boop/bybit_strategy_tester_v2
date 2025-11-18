#!/usr/bin/env python3
"""
Прямой вызов DeepSeek Agent для анализа FastAPI router проблемы
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.unified_agent_interface import (
    UnifiedAgentInterface,
    AgentRequest,
    AgentType
)
from loguru import logger

async def main():
    """Main entry point"""
    
    # Read problem description
    report_path = Path("DEEPSEEK_ANALYSIS_REQUEST.txt")
    if not report_path.exists():
        logger.error(f"❌ Report file not found: {report_path}")
        return
    
    problem_description = report_path.read_text(encoding="utf-8")
    
    logger.info("🤖 Initializing Unified Agent Interface...")
    agent = UnifiedAgentInterface()
    
    logger.info("📤 Sending request to DeepSeek Agent...")
    
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="debug_fastapi_router_404",
        prompt=problem_description,
        context={
            "focus": "performance",
            "urgency": "critical",
            "problem_type": "fastapi_routing"
        }
    )
    
    try:
        response = await agent.send_request(request)
        
        if response.get("success"):
            logger.success("\n✅ DeepSeek Response:")
            print("\n" + "=" * 80)
            print(response.get("content", response.get("response", "No content")))
            print("=" * 80 + "\n")
            
            # Save response
            output_path = Path("DEEPSEEK_ANALYSIS_RESPONSE.md")
            output_path.write_text(response.get("content", response.get("response", "")), encoding="utf-8")
            logger.info(f"💾 Response saved to: {output_path}")
        else:
            logger.error(f"❌ Request failed: {response.get('error')}")
    except Exception as e:
        logger.exception(f"❌ Error sending request: {e}")


if __name__ == "__main__":
    asyncio.run(main())
