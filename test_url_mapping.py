"""Тест _get_api_url функции"""
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.agents.unified_agent_interface import get_agent_interface
from backend.agents.models import AgentType

agent = get_agent_interface()

print("Testing _get_api_url:")
print(f"  DeepSeek: {agent._get_api_url(AgentType.DEEPSEEK)}")
print(f"  Perplexity: {agent._get_api_url(AgentType.PERPLEXITY)}")

assert agent._get_api_url(AgentType.DEEPSEEK) == "https://api.deepseek.com/v1/chat/completions"
assert agent._get_api_url(AgentType.PERPLEXITY) == "https://api.perplexity.ai/chat/completions"

print("✅ _get_api_url works correctly!")
