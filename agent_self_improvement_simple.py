"""
Simplified Autonomous Self-Improvement (MCP-only, short prompts)
================================================================
Agents work through MCP Server only to avoid API issues.
Short, focused prompts to prevent timeouts.
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

async def autonomous_self_improvement():
    from backend.agents.unified_agent_interface import get_agent_interface
    from backend.agents.models import AgentRequest, AgentType
    
    agent = get_agent_interface()
    
    print("=" * 80)
    print("🤖 AUTONOMOUS AGENT SELF-IMPROVEMENT (Simplified)")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")
    print("Using: MCP Server only, short focused prompts")
    print("=" * 80)
    
    results = {}
    
    # Step 1: DeepSeek - Quick capability assessment
    print("\n📊 STEP 1: DeepSeek Self-Assessment")
    print("-" * 80)
    
    deepseek_assess = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="analyze",
        prompt="""Rate current agent system capabilities (1-10):
1. Autonomy (work without human)
2. Self-diagnosis (detect own errors)
3. Self-healing (fix errors automatically)
4. Multi-agent collaboration
5. Project code access

List TOP-3 improvements needed for max autonomy.
Keep response under 300 words.""",
        code=None,
        context={}
    )
    
    print("Sending to DeepSeek...")
    result1 = await agent.send_request(deepseek_assess)
    print(f"Success: {result1.success} | Channel: {result1.channel}")
    if result1.success:
        print(f"Response preview: {result1.content[:400]}...")
        results["deepseek_assessment"] = result1.content
    else:
        print(f"Error: {result1.error}")
        results["deepseek_assessment"] = f"FAILED: {result1.error}"
    
    # Step 2: Perplexity - Best practices research
    print("\n🔬 STEP 2: Perplexity Best Practices")
    print("-" * 80)
    
    perplexity_research = AgentRequest(
        agent_type=AgentType.PERPLEXITY,
        task_type="research",
        prompt="""What are TOP-3 best practices for autonomous AI agents?
Focus on: self-improvement, error recovery, multi-agent collaboration.
Keep response under 300 words.""",
        code=None,
        context={}
    )
    
    print("Sending to Perplexity...")
    result2 = await agent.send_request(perplexity_research)
    print(f"Success: {result2.success} | Channel: {result2.channel}")
    if result2.success:
        print(f"Response preview: {result2.content[:400]}...")
        results["perplexity_research"] = result2.content
    else:
        print(f"Error: {result2.error}")
        results["perplexity_research"] = f"FAILED: {result2.error}"
    
    # Step 3: DeepSeek - Propose ONE concrete improvement
    print("\n🎯 STEP 3: DeepSeek Improvement Proposal")
    print("-" * 80)
    
    context_summary = f"""
Assessment: {results.get('deepseek_assessment', 'N/A')[:200]}
Best Practices: {results.get('perplexity_research', 'N/A')[:200]}
"""
    
    deepseek_propose = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="review",
        prompt=f"""Based on self-assessment and best practices, propose ONE specific improvement to implement NOW.

{context_summary}

Specify:
- What to improve (exact file/function)
- How (concrete code change)
- Why (expected benefit)

Keep response under 300 words.""",
        code=None,
        context={}
    )
    
    print("Sending to DeepSeek...")
    result3 = await agent.send_request(deepseek_propose)
    print(f"Success: {result3.success} | Channel: {result3.channel}")
    if result3.success:
        print(f"Response preview: {result3.content[:400]}...")
        results["deepseek_proposal"] = result3.content
    else:
        print(f"Error: {result3.error}")
        results["deepseek_proposal"] = f"FAILED: {result3.error}"
    
    # Step 4: Perplexity - Review proposal
    print("\n🔍 STEP 4: Perplexity Proposal Review")
    print("-" * 80)
    
    perplexity_review = AgentRequest(
        agent_type=AgentType.PERPLEXITY,
        task_type="review",
        prompt=f"""Review this improvement proposal for safety and effectiveness:

{results.get('deepseek_proposal', 'N/A')[:500]}

Answer:
- Safe to implement? (yes/no + reason)
- Will it improve autonomy? (yes/no + reason)
- Priority? (high/medium/low)

Keep response under 200 words.""",
        code=None,
        context={}
    )
    
    print("Sending to Perplexity...")
    result4 = await agent.send_request(perplexity_review)
    print(f"Success: {result4.success} | Channel: {result4.channel}")
    if result4.success:
        print(f"Response preview: {result4.content[:400]}...")
        results["perplexity_review"] = result4.content
    else:
        print(f"Error: {result4.error}")
        results["perplexity_review"] = f"FAILED: {result4.error}"
    
    # Step 5: DeepSeek - Final consensus
    print("\n✅ STEP 5: DeepSeek Consensus Decision")
    print("-" * 80)
    
    deepseek_consensus = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="analyze",
        prompt=f"""Based on proposal and Perplexity review, make final decision:

Proposal: {results.get('deepseek_proposal', 'N/A')[:300]}
Review: {results.get('perplexity_review', 'N/A')[:300]}

DECISION:
- Implement? (yes/no)
- Rationale (1 sentence)
- Next steps (if yes, what exactly to code)

Keep response under 200 words.""",
        code=None,
        context={}
    )
    
    print("Sending to DeepSeek...")
    result5 = await agent.send_request(deepseek_consensus)
    print(f"Success: {result5.success} | Channel: {result5.channel}")
    if result5.success:
        print(f"Response preview: {result5.content[:400]}...")
        results["deepseek_consensus"] = result5.content
    else:
        print(f"Error: {result5.error}")
        results["deepseek_consensus"] = f"FAILED: {result5.error}"
    
    # Save results
    print("\n" + "=" * 80)
    print("💾 SAVING RESULTS")
    print("=" * 80)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "status": "completed",
        "steps": results,
        "summary": {
            "deepseek_calls": 3,
            "perplexity_calls": 2,
            "successful_steps": len([r for r in results.values() if "FAILED" not in str(r)]),
            "failed_steps": len([r for r in results.values() if "FAILED" in str(r)])
        }
    }
    
    report_path = project_root / f"AGENT_SELF_IMPROVEMENT_SIMPLE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Report saved: {report_path.name}")
    print(f"\n📊 Summary:")
    print(f"   Successful steps: {report['summary']['successful_steps']}/5")
    print(f"   Failed steps: {report['summary']['failed_steps']}/5")
    
    # Print key insights
    print(f"\n🔑 Key Insights:")
    if "deepseek_assessment" in results and "FAILED" not in results["deepseek_assessment"]:
        print(f"   Assessment: {results['deepseek_assessment'][:150]}...")
    if "deepseek_consensus" in results and "FAILED" not in results["deepseek_consensus"]:
        print(f"   Decision: {results['deepseek_consensus'][:150]}...")
    
    print("\n" + "=" * 80)
    print("✅ AUTONOMOUS SELF-IMPROVEMENT SESSION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(autonomous_self_improvement())
