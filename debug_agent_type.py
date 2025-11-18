"""Debug agent_type comparison"""
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.agents.unified_agent_interface import get_agent_interface
from backend.agents.models import AgentType

agent = get_agent_interface()

# Test with different inputs
test_type = AgentType.DEEPSEEK
print(f"test_type = {test_type}")
print(f"test_type type = {type(test_type)}")
print(f"AgentType.DEEPSEEK type = {type(AgentType.DEEPSEEK)}")
print(f"test_type == AgentType.DEEPSEEK: {test_type == AgentType.DEEPSEEK}")
print(f"test_type is AgentType.DEEPSEEK: {test_type is AgentType.DEEPSEEK}")

# Call function with debug
def debug_get_api_url(agent_type):
    print(f"\nInside function:")
    print(f"  agent_type = {agent_type}")
    print(f"  type(agent_type) = {type(agent_type)}")
    print(f"  AgentType.DEEPSEEK = {AgentType.DEEPSEEK}")
    print(f"  agent_type == AgentType.DEEPSEEK: {agent_type == AgentType.DEEPSEEK}")
    
    if agent_type == AgentType.DEEPSEEK:
        print("  Branch: DeepSeek")
        return "https://api.deepseek.com/v1/chat/completions"
    else:
        print("  Branch: else (Perplexity)")
        return "https://api.perplexity.ai/chat/completions"

result = debug_get_api_url(AgentType.DEEPSEEK)
print(f"\nResult: {result}")
