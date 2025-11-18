"""Quick test for new DeepSeek Agent methods"""
import asyncio
from backend.agents.deepseek import DeepSeekAgent


async def main():
    async with DeepSeekAgent() as agent:
        print("🧪 Testing new explain_code method...")
        
        result = await agent.explain_code(
            code="def add(x, y): return x + y",
            focus="all",
            include_improvements=True
        )
        
        print(f"✅ Status: {result.status.value}")
        print(f"✅ Tokens: {result.tokens_used}")
        print(f"✅ Output: {len(result.code)} chars")
        print("\n" + "="*60)
        print(result.code[:200] + "..." if len(result.code) > 200 else result.code)
        print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
