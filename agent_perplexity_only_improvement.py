"""
🤖 PERPLEXITY-ONLY AUTONOMOUS SELF-IMPROVEMENT
================================================
Workaround for DeepSeek 500 errors - use only Perplexity via MCP.
Perplexity can handle all phases:
- Analysis (research + introspection)
- Proposal (concrete improvements)
- Review (self-validate)
- Implementation guidance (code suggestions)
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

async def perplexity_only_improvement():
    from backend.agents.unified_agent_interface import get_agent_interface
    from backend.agents.models import AgentRequest, AgentType
    
    agent = get_agent_interface()
    
    print("=" * 100)
    print("🤖 PERPLEXITY-ONLY AUTONOMOUS SELF-IMPROVEMENT")
    print("=" * 100)
    print(f"Started: {datetime.now().isoformat()}")
    print("Workaround: Using only Perplexity (DeepSeek API down)")
    print("=" * 100)
    
    results = {}
    
    # Phase 1: Analysis
    print("\n📊 PHASE 1: Self-Analysis via Perplexity")
    print("-" * 100)
    
    analysis_prompt = """🔬 AI AGENT SYSTEM SELF-ANALYSIS

Analyze the autonomous AI agent system in bybit_strategy_tester_v2 project:

CURRENT CAPABILITIES:
- Multi-agent orchestration (DeepSeek + Perplexity + Copilot)
- Multi-channel fallback (MCP Server → Direct API → Backup keys)
- Error handling with circuit breakers
- Health monitoring every 30s
- Dead letter queue for failed requests

ANALYSIS TASKS:
1. Rate current autonomy level (1-10):
   - Self-diagnosis capability
   - Self-healing after failures
   - Multi-agent coordination
   - Adaptive behavior

2. Identify TOP-3 improvements for maximum autonomy:
   - What exact component needs improvement
   - Current limitation
   - Proposed enhancement
   - Expected autonomy gain

3. Focus on areas that enable:
   - Automatic error recovery without human
   - Self-optimization based on performance
   - Consensus-based decision making
   - Learning from failures

Be thorough. No word limits."""

    request1 = AgentRequest(
        agent_type=AgentType.PERPLEXITY,
        task_type="research",
        prompt=analysis_prompt,
        code=None,
        context={"timeout_override": 600}  # 10 minutes
    )
    
    print("📤 Sending to Perplexity...")
    result1 = await agent.send_request(request1)
    
    print(f"✅ Success: {result1.success} | Channel: {result1.channel} | Latency: {result1.latency_ms:.0f}ms")
    
    if not result1.success:
        print(f"❌ Analysis failed: {result1.error}")
        print("Cannot proceed without analysis. Aborting.")
        return
    
    print(f"📄 Analysis (first 600 chars):\n{result1.content[:600]}...\n")
    results["analysis"] = result1.content
    
    # Phase 2: Concrete Proposal
    print("\n🎯 PHASE 2: Concrete Improvement Proposal")
    print("-" * 100)
    
    proposal_prompt = f"""💡 CONCRETE IMPROVEMENT PROPOSAL

Based on self-analysis:
{results['analysis'][:2000]}

CREATE ONE SPECIFIC, IMPLEMENTABLE IMPROVEMENT:

PROPOSAL TEMPLATE:
1. **Target Component**
   - File: backend/agents/unified_agent_interface.py (or other)
   - Function/Class: exact name
   - Lines: approximate range

2. **Current Problem**
   - What blocks autonomy now
   - Specific failure scenario
   - Impact quantified

3. **Proposed Solution**
   ```python
   # Exact code to implement
   def improved_functionality(...):
       \"\"\"Docstring explaining improvement\"\"\"
       # Implementation details
       pass
   ```

4. **Implementation Plan**
   - Step 1: Backup current code
   - Step 2: Add/modify lines X-Y
   - Step 3: Test with scenario Z
   - Step 4: Validate improvement

5. **Expected Benefits**
   - Autonomy: +X points (1-10 scale)
   - Reliability: fewer failures
   - Performance: measurable gain

Be EXTREMELY SPECIFIC with actual code."""

    request2 = AgentRequest(
        agent_type=AgentType.PERPLEXITY,
        task_type="research",
        prompt=proposal_prompt,
        code=None,
        context={"timeout_override": 600}
    )
    
    print("📤 Sending to Perplexity...")
    result2 = await agent.send_request(request2)
    
    print(f"✅ Success: {result2.success} | Channel: {result2.channel} | Latency: {result2.latency_ms:.0f}ms")
    
    if not result2.success:
        print(f"❌ Proposal failed: {result2.error}")
        print("Using analysis only for report.")
        results["proposal"] = f"FAILED: {result2.error}"
    else:
        print(f"📄 Proposal (first 800 chars):\n{result2.content[:800]}...\n")
        results["proposal"] = result2.content
    
    # Phase 3: Safety Review
    if result2.success:
        print("\n🔍 PHASE 3: Safety Review")
        print("-" * 100)
        
        review_prompt = f"""🛡️ SAFETY REVIEW

Proposal to implement:
{results['proposal'][:2000]}

REVIEW CHECKLIST:
1. **Safety**
   - Breaking changes? (yes/no + details)
   - Data loss risk? (yes/no)
   - Security concerns? (yes/no)

2. **Correctness**
   - Will the code work? (yes/no + why)
   - Edge cases handled? (list them)
   - Backward compatible? (yes/no)

3. **Testing**
   - What tests to run before deploy
   - What to monitor after deploy
   - Rollback procedure

4. **VERDICT**
   - SAFE TO IMPLEMENT: Yes ✅
   - NEEDS REVISION: Changes required ⚠️
   - DO NOT IMPLEMENT: Too risky ❌

Be critical. Better safe than sorry."""

        request3 = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="review",
            prompt=review_prompt,
            code=None,
            context={"timeout_override": 300}
        )
        
        print("📤 Sending to Perplexity...")
        result3 = await agent.send_request(request3)
        
        print(f"✅ Success: {result3.success} | Channel: {result3.channel} | Latency: {result3.latency_ms:.0f}ms")
        
        if result3.success:
            print(f"📄 Review (first 600 chars):\n{result3.content[:600]}...\n")
            results["review"] = result3.content
        else:
            print(f"❌ Review failed: {result3.error}")
            results["review"] = f"FAILED: {result3.error}"
    
    # Save report
    print("\n" + "=" * 100)
    print("💾 SAVING RESULTS")
    print("=" * 100)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "agent": "Perplexity-only (DeepSeek API down)",
        "results": results,
        "summary": {
            "phases_completed": len([r for r in results.values() if "FAILED" not in str(r)]),
            "phases_failed": len([r for r in results.values() if "FAILED" in str(r)]),
            "total_phases": len(results)
        }
    }
    
    report_path = project_root / f"AGENT_PERPLEXITY_ONLY_IMPROVEMENT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Report saved: {report_path.name}")
    print(f"\n📊 Summary:")
    print(f"   Completed: {report['summary']['phases_completed']}/{report['summary']['total_phases']}")
    print(f"   Failed: {report['summary']['phases_failed']}/{report['summary']['total_phases']}")
    
    print(f"\n🔑 Key Results:")
    if "analysis" in results and "FAILED" not in results["analysis"]:
        print(f"   ✅ Analysis complete ({len(results['analysis'])} chars)")
    if "proposal" in results and "FAILED" not in results["proposal"]:
        print(f"   ✅ Proposal complete ({len(results['proposal'])} chars)")
    if "review" in results and "FAILED" not in results["review"]:
        print(f"   ✅ Review complete ({len(results['review'])} chars)")
    
    print("\n" + "=" * 100)
    print("✅ PERPLEXITY-ONLY SELF-IMPROVEMENT COMPLETE")
    print("=" * 100)
    print(f"📄 Review report: {report_path.name}")
    print("💡 Next: Apply improvements manually after validating safety.")

if __name__ == "__main__":
    asyncio.run(perplexity_only_improvement())
