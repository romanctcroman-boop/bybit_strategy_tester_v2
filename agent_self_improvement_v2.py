"""
Autonomous Self-Improvement v2 - Enhanced with Recommendations
==============================================================
Improvements:
1. Increased timeout to 300s for complex tasks
2. Agent swap fallback (if DeepSeek fails, try Perplexity)
3. Parallel requests option (both agents, use fastest)
4. Reduced steps (3 instead of 5 to minimize failure cascade)
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

async def autonomous_self_improvement_v2():
    from backend.agents.unified_agent_interface import get_agent_interface
    from backend.agents.models import AgentRequest, AgentType
    
    agent = get_agent_interface()
    
    print("=" * 80)
    print("🤖 AUTONOMOUS SELF-IMPROVEMENT v2 (Enhanced)")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")
    print("Improvements:")
    print("  - 300s timeout (vs 120s)")
    print("  - Agent swap fallback")
    print("  - 3-step cycle (reduced cascade risk)")
    print("=" * 80)
    
    results = {}
    
    # ========================================================================
    # STEP 1: Analysis (DeepSeek primary, Perplexity fallback)
    # ========================================================================
    print("\n📊 STEP 1: System Analysis")
    print("-" * 80)
    
    analysis_prompt = """Analyze current agent system for self-improvement:

Rate (1-10):
1. Autonomy (work without human)
2. Self-healing (auto-fix errors)
3. Multi-agent synergy

TOP-1 improvement to boost autonomy.
Max 200 words."""

    # Try DeepSeek first
    print("Attempting DeepSeek...")
    deepseek_req = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="analyze",
        prompt=analysis_prompt,
        code=None,
        context={"timeout_override": 300}  # 5 minutes
    )
    
    result1 = await agent.send_request(deepseek_req)
    
    # Fallback to Perplexity if DeepSeek fails
    if not result1.success:
        print(f"❌ DeepSeek failed: {result1.error}")
        print("🔄 Falling back to Perplexity...")
        
        perplexity_req = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="research",
            prompt=analysis_prompt,
            code=None,
            context={"timeout_override": 300}
        )
        
        result1 = await agent.send_request(perplexity_req)
    
    print(f"Success: {result1.success} | Channel: {result1.channel}")
    if result1.success:
        print(f"Response: {result1.content[:300]}...")
        results["analysis"] = result1.content
    else:
        print(f"Error: {result1.error}")
        results["analysis"] = f"FAILED: {result1.error}"
        print("\n⚠️ Cannot proceed without analysis. Aborting.")
        return
    
    # ========================================================================
    # STEP 2: Parallel Proposal (both agents compete)
    # ========================================================================
    print("\n🎯 STEP 2: Improvement Proposal (Parallel)")
    print("-" * 80)
    
    proposal_prompt = f"""Based on analysis, propose ONE concrete improvement:

Analysis: {results['analysis'][:200]}

Specify:
- File/function to modify
- Exact code change
- Expected benefit

Max 200 words."""
    
    print("Sending to BOTH DeepSeek + Perplexity in parallel...")
    
    deepseek_proposal = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="review",
        prompt=proposal_prompt,
        code=None,
        context={"timeout_override": 300}
    )
    
    perplexity_proposal = AgentRequest(
        agent_type=AgentType.PERPLEXITY,
        task_type="review",
        prompt=proposal_prompt,
        code=None,
        context={"timeout_override": 300}
    )
    
    # Execute in parallel, return exceptions instead of raising
    ds_task = agent.send_request(deepseek_proposal)
    pp_task = agent.send_request(perplexity_proposal)
    
    parallel_results = await asyncio.gather(ds_task, pp_task, return_exceptions=True)
    
    # Process results
    deepseek_result = parallel_results[0] if not isinstance(parallel_results[0], Exception) else None
    perplexity_result = parallel_results[1] if not isinstance(parallel_results[1], Exception) else None
    
    print(f"\nDeepSeek: {'✅' if deepseek_result and deepseek_result.success else '❌'}")
    if deepseek_result and deepseek_result.success:
        print(f"  Response: {deepseek_result.content[:200]}...")
    
    print(f"Perplexity: {'✅' if perplexity_result and perplexity_result.success else '❌'}")
    if perplexity_result and perplexity_result.success:
        print(f"  Response: {perplexity_result.content[:200]}...")
    
    # Select best response
    best_proposal = None
    if deepseek_result and deepseek_result.success:
        best_proposal = deepseek_result
        results["proposal_source"] = "DeepSeek"
    elif perplexity_result and perplexity_result.success:
        best_proposal = perplexity_result
        results["proposal_source"] = "Perplexity"
    
    if best_proposal:
        results["proposal"] = best_proposal.content
        print(f"\n✅ Using proposal from: {results['proposal_source']}")
    else:
        print("\n❌ Both agents failed for proposal. Aborting.")
        results["proposal"] = "FAILED: All agents failed"
        return
    
    # ========================================================================
    # STEP 3: Consensus Decision (opposite agent reviews)
    # ========================================================================
    print("\n✅ STEP 3: Consensus Decision")
    print("-" * 80)
    
    # Use opposite agent for review (diversity)
    review_agent_type = AgentType.PERPLEXITY if results["proposal_source"] == "DeepSeek" else AgentType.DEEPSEEK
    
    decision_prompt = f"""Review this improvement proposal:

{results['proposal'][:300]}

Decision:
- Implement? (yes/no)
- Rationale (1 sentence)
- Risk level (low/medium/high)

Max 150 words."""
    
    print(f"Sending to {review_agent_type.value} for review...")
    
    decision_req = AgentRequest(
        agent_type=review_agent_type,
        task_type="analyze",
        prompt=decision_prompt,
        code=None,
        context={"timeout_override": 300}
    )
    
    result3 = await agent.send_request(decision_req)
    
    print(f"Success: {result3.success} | Channel: {result3.channel}")
    if result3.success:
        print(f"Decision: {result3.content[:300]}...")
        results["decision"] = result3.content
    else:
        print(f"Error: {result3.error}")
        results["decision"] = f"FAILED: {result3.error}"
    
    # ========================================================================
    # SAVE RESULTS
    # ========================================================================
    print("\n" + "=" * 80)
    print("💾 SAVING RESULTS")
    print("=" * 80)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "version": "v2_enhanced",
        "improvements": [
            "300s timeout",
            "Agent swap fallback",
            "Parallel proposal generation",
            "Reduced steps (3 instead of 5)"
        ],
        "results": results,
        "summary": {
            "total_steps": 3,
            "successful_steps": len([r for r in results.values() if "FAILED" not in str(r)]),
            "failed_steps": len([r for r in results.values() if "FAILED" in str(r)]),
            "proposal_source": results.get("proposal_source", "N/A")
        }
    }
    
    report_path = project_root / f"AGENT_SELF_IMPROVEMENT_V2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Report saved: {report_path.name}")
    print(f"\n📊 Summary:")
    print(f"   Successful steps: {report['summary']['successful_steps']}/3")
    print(f"   Failed steps: {report['summary']['failed_steps']}/3")
    print(f"   Proposal source: {report['summary']['proposal_source']}")
    
    # Print key insights
    print(f"\n🔑 Key Insights:")
    if "analysis" in results and "FAILED" not in results["analysis"]:
        print(f"   Analysis: {results['analysis'][:150]}...")
    if "proposal" in results and "FAILED" not in results["proposal"]:
        print(f"   Proposal: {results['proposal'][:150]}...")
    if "decision" in results and "FAILED" not in results["decision"]:
        print(f"   Decision: {results['decision'][:150]}...")
    
    print("\n" + "=" * 80)
    print("✅ AUTONOMOUS SELF-IMPROVEMENT v2 COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(autonomous_self_improvement_v2())
