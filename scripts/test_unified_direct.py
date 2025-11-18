"""
Прямой тест через unified_agent_interface
"""

import asyncio
import sys
sys.path.insert(0, ".")

from backend.agents.unified_agent_interface import (
    UnifiedAgentInterface,
    AgentRequest,
    AgentType,
    AgentChannel
)


async def test_unified_interface():
    """Тест напрямую через unified interface"""
    
    print("="*80)
    print("DIRECT UNIFIED INTERFACE TEST")
    print("="*80)
    print()
    
    interface = UnifiedAgentInterface()
    
    # Create request with file access enabled
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="test_tool_calling",
        prompt="Please use mcp_read_project_file to read the file 'README.md' and tell me what it contains.",
        context={
            "use_file_access": True
        }
    )
    
    print("Sending request with use_file_access=True")
    print("Expected: DeepSeek should call mcp_read_project_file tool")
    print()
    
    # Send request with DIRECT_API channel (tool calling supported)
    response = await interface.send_request(request, preferred_channel=AgentChannel.DIRECT_API)
    
    print("="*80)
    print("RESPONSE")
    print("="*80)
    print(f"Success: {response.success}")
    print(f"Channel: {response.channel}")
    print(f"Latency: {response.latency_ms}ms")
    print()
    print("Content:")
    print("-"*80)
    print(response.content)
    print("-"*80)
    
    if response.error:
        print()
        print(f"Error: {response.error}")


if __name__ == "__main__":
    asyncio.run(test_unified_interface())
