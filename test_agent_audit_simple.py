"""Simplified agent audit - shorter prompts, less context"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

async def simplified_audit():
    from backend.agents.unified_agent_interface import get_agent_interface
    from backend.agents.models import AgentRequest, AgentType
    
    agent = get_agent_interface()
    
    print("=" * 80)
    print("SIMPLIFIED AGENT AUDIT: MCP Bridge Improvements")
    print("=" * 80)
    
    # Короткий код для review
    code_sample = """
# MCP Bridge: Duration measurement fix
import time
start_time = time.perf_counter()  # MOVED BEFORE try
try:
    result = await tool_obj(**arguments)
    duration = time.perf_counter() - start_time
    MCP_BRIDGE_DURATION.labels(tool=name, success="true").observe(duration)
except Exception as e:
    duration = time.perf_counter() - start_time  # ACCURATE now
    MCP_BRIDGE_DURATION.labels(tool=name, success="false").observe(duration)

# Histogram buckets (microsecond precision)
buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, inf)

# Validation schema
TOOL_SCHEMAS = {
    "tool_name": {
        "required": ["param1"],
        "optional": ["param2"],
        "types": {"param1": str, "param2": int}
    }
}

# Structured error
@dataclass
class StructuredError:
    error_type: str
    message: str
    stage: str
    retryable: bool
    correlation_id: Optional[str] = None
"""
    
    # Test 1: DeepSeek short review
    print("\n1️⃣ DeepSeek: Quick code correctness check")
    print("-" * 80)
    
    deepseek_request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="review",
        prompt=f"""Review this MCP bridge code. Check:
1. Is start_time placement correct for accurate duration?
2. Are histogram buckets sufficient (microsecond to 30s)?
3. Is StructuredError model complete?

Code:
{code_sample}

Rate 1-10 and list any bugs.""",
        code=None,
        context={}
    )
    
    print("Sending to DeepSeek...")
    deepseek_result = await agent.send_request(deepseek_request)
    
    print(f"Success: {deepseek_result.success}")
    print(f"Channel: {deepseek_result.channel}")
    print(f"Response length: {len(deepseek_result.content)} chars")
    if deepseek_result.success:
        print(f"Content preview:\n{deepseek_result.content[:500]}")
    else:
        print(f"Error: {deepseek_result.error}")
    
    # Test 2: Perplexity short research
    print("\n" + "=" * 80)
    print("2️⃣ Perplexity: Best practice quick check")
    print("-" * 80)
    
    perplexity_request = AgentRequest(
        agent_type=AgentType.PERPLEXITY,
        task_type="research",
        prompt="""Are these patterns correct for observability?
1. Prometheus histogram buckets: 0.001s to 30s for API latency
2. Measuring time.perf_counter() before try block for accuracy
3. Structured errors with: error_type, stage, retryable fields

Brief yes/no + 1-2 sentence rationale.""",
        code=None,
        context={}
    )
    
    print("Sending to Perplexity...")
    perplexity_result = await agent.send_request(perplexity_request)
    
    print(f"Success: {perplexity_result.success}")
    print(f"Channel: {perplexity_result.channel}")
    print(f"Response length: {len(perplexity_result.content)} chars")
    if perplexity_result.success:
        print(f"Content preview:\n{perplexity_result.content[:500]}")
    else:
        print(f"Error: {perplexity_result.error}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"DeepSeek: {'✅ OK' if deepseek_result.success else '❌ FAILED'}")
    print(f"Perplexity: {'✅ OK' if perplexity_result.success else '❌ FAILED'}")
    
    if deepseek_result.success or perplexity_result.success:
        print("\n✅ At least one agent successfully reviewed the implementation")
    else:
        print("\n⚠️ Both agents failed - API issues detected")
    
    return {
        "deepseek": deepseek_result,
        "perplexity": perplexity_result
    }

if __name__ == "__main__":
    asyncio.run(simplified_audit())
