"""Quick test of DeepSeek Code Agent"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.deepseek_code_agent.code_agent import (
    DeepSeekCodeAgent,
    CodeGenerationRequest
)

async def main():
    print("Testing DeepSeek Code Agent...")
    
    agent = DeepSeekCodeAgent()
    
    result = await agent.generate_code(
        CodeGenerationRequest(
            prompt="Create a simple hello world function in Python",
            language="python",
            style="quick",
            max_tokens=300
        )
    )
    
    print(f"\n{'='*80}")
    print(f"SUCCESS: {result['success']}")
    print(f"{'='*80}")
    
    if result['success']:
        print("\nGENERATED CODE:")
        print(result['code'])
        print(f"\nEXPLANATION:")
        print(result['explanation'][:200] + "...")
    else:
        print(f"\nERROR: {result.get('error')}")
    
    await agent.close()
    print("\nTest completed! ✅")

if __name__ == "__main__":
    asyncio.run(main())
