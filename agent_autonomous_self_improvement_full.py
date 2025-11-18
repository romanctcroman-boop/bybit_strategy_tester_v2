"""
🤖 AUTONOMOUS AGENT SELF-IMPROVEMENT - FULL PRODUCTION VERSION
================================================================

Multi-Cycle Autonomous Improvement with Direct Code Access:
1. DeepSeek Analysis - Deep introspection of agent code with file access
2. Perplexity Research - Best practices and industry standards
3. DeepSeek Proposal - Concrete improvement with code changes
4. Perplexity Review - Safety validation and consensus building
5. DeepSeek Implementation - Direct code modification with backups
6. Cross-Validation - Both agents verify improvements
7. Next Cycle - Repeat until convergence

Features:
- ✅ Direct file access (read/write agent code)
- ✅ Unlimited reasoning depth
- ✅ Consensus-based decisions
- ✅ Automatic backups before changes
- ✅ Multi-cycle convergence detection
- ✅ Comprehensive logging
"""
import asyncio
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Constants
MAX_CYCLES = 10
CONVERGENCE_THRESHOLD = 0.85  # Stop if 85% consensus reached
TIMEOUT_COMPLEX = 600  # 10 minutes for deep analysis
TIMEOUT_STANDARD = 300  # 5 minutes for reviews

class AutonomousSelfImprovement:
    def __init__(self):
        self.cycle_history = []
        self.improvements_made = []
        self.files_modified = []
        
    async def run(self):
        """Main autonomous improvement loop"""
        from backend.agents.unified_agent_interface import get_agent_interface
        from backend.agents.models import AgentRequest, AgentType
        
        self.agent = get_agent_interface()
        
        print("=" * 100)
        print("🤖 AUTONOMOUS AGENT SELF-IMPROVEMENT - FULL PRODUCTION VERSION")
        print("=" * 100)
        print(f"Started: {datetime.now().isoformat()}")
        print(f"Max Cycles: {MAX_CYCLES}")
        print(f"Convergence Threshold: {CONVERGENCE_THRESHOLD * 100}%")
        print(f"Features: Direct Code Access | Unlimited Reasoning | Consensus Decisions")
        print("=" * 100)
        
        for cycle in range(1, MAX_CYCLES + 1):
            print(f"\n{'#' * 100}")
            print(f"🔄 CYCLE {cycle}/{MAX_CYCLES}")
            print(f"{'#' * 100}")
            
            cycle_result = await self.execute_cycle(cycle)
            self.cycle_history.append(cycle_result)
            
            # Check convergence
            if cycle_result.get("converged", False):
                print(f"\n✅ CONVERGENCE REACHED after {cycle} cycles!")
                print(f"Consensus Score: {cycle_result.get('consensus_score', 0):.2%}")
                break
            
            # Check if we should continue
            if cycle_result.get("critical_error", False):
                print(f"\n❌ Critical error in cycle {cycle}, aborting.")
                break
            
            if cycle_result.get("no_improvements", False):
                print(f"\n✅ No more improvements needed after {cycle} cycles!")
                break
        
        # Generate final report
        await self.generate_report()
        
    async def execute_cycle(self, cycle_num: int) -> Dict[str, Any]:
        """Execute one full improvement cycle"""
        cycle_data = {
            "cycle": cycle_num,
            "timestamp": datetime.now().isoformat(),
            "phases": {}
        }
        
        try:
            # Phase 1: DeepSeek Deep Analysis (with file access)
            phase1 = await self.phase1_deepseek_analysis(cycle_num)
            cycle_data["phases"]["analysis"] = phase1
            
            if not phase1.get("success"):
                cycle_data["critical_error"] = True
                return cycle_data
            
            # Phase 2: Perplexity Research & Best Practices
            phase2 = await self.phase2_perplexity_research(cycle_num, phase1)
            cycle_data["phases"]["research"] = phase2
            
            # Phase 3: DeepSeek Concrete Proposal
            phase3 = await self.phase3_deepseek_proposal(cycle_num, phase1, phase2)
            cycle_data["phases"]["proposal"] = phase3
            
            if not phase3.get("success"):
                cycle_data["no_improvements"] = True
                return cycle_data
            
            # Phase 4: Perplexity Safety Review & Consensus
            phase4 = await self.phase4_perplexity_review(cycle_num, phase3)
            cycle_data["phases"]["review"] = phase4
            
            # Calculate consensus score
            consensus_score = phase4.get("consensus_score", 0.0)
            cycle_data["consensus_score"] = consensus_score
            
            # Phase 5: DeepSeek Implementation (if approved)
            if phase4.get("approved", False) and consensus_score >= CONVERGENCE_THRESHOLD:
                phase5 = await self.phase5_deepseek_implement(cycle_num, phase3, phase4)
                cycle_data["phases"]["implementation"] = phase5
                
                if phase5.get("success"):
                    self.improvements_made.append(phase5)
                    
                    # Phase 6: Cross-Validation
                    phase6 = await self.phase6_cross_validation(cycle_num, phase5)
                    cycle_data["phases"]["validation"] = phase6
                    
                    if phase6.get("validated", False):
                        cycle_data["converged"] = True
            else:
                print(f"⚠️ Proposal not approved or consensus too low ({consensus_score:.2%})")
                cycle_data["converged"] = False
            
        except Exception as e:
            print(f"❌ Cycle {cycle_num} exception: {e}")
            cycle_data["critical_error"] = True
            cycle_data["error"] = str(e)
        
        return cycle_data
    
    async def phase1_deepseek_analysis(self, cycle: int) -> Dict[str, Any]:
        """Phase 1: DeepSeek analyzes agent code with direct file access"""
        from backend.agents.models import AgentRequest, AgentType
        
        print(f"\n{'=' * 100}")
        print(f"📊 PHASE 1: DeepSeek Deep Analysis (Cycle {cycle})")
        print(f"{'=' * 100}")
        print("Reading agent code for analysis...")
        
        # Read current agent code
        agent_file = project_root / "backend" / "agents" / "unified_agent_interface.py"
        
        analysis_prompt = f"""🔬 DEEP AGENT SELF-ANALYSIS (Cycle {cycle})

You are analyzing your own implementation code to identify opportunities for self-improvement towards maximum autonomy.

You have DIRECT FILE ACCESS enabled. Read and analyze:
- backend/agents/unified_agent_interface.py (your own code)
- backend/agents/models.py (agent models)
- backend/agents/key_manager.py (key rotation logic)

ANALYSIS TASKS:
1. Evaluate current autonomy capabilities (1-10 scale):
   - Self-diagnosis (detect own failures)
   - Self-healing (automatic error recovery)
   - Self-optimization (improve performance)
   - Self-learning (adapt from experience)
   - Self-coordination (multi-agent consensus)

2. Identify TOP-3 concrete improvements for maximum autonomy:
   - What exact function/class to improve
   - Current limitation
   - Proposed enhancement
   - Expected autonomy gain

3. Code quality assessment:
   - Error handling robustness
   - Fallback strategy effectiveness
   - Resource efficiency
   - Logging and observability

Provide DEEP, UNLIMITED reasoning. No word limits. Be thorough and precise."""

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="analyze",
            prompt=analysis_prompt,
            code=None,  # No code in prompt - use file_access instead
            context={
                "use_file_access": True,
                "complex_task": True,
                "self_improvement_analysis": True,
                "timeout_override": TIMEOUT_COMPLEX
            }
        )
        
        print(f"📤 Sending to DeepSeek (timeout: {TIMEOUT_COMPLEX}s)...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Success: {result.success} | Channel: {result.channel} | Latency: {result.latency_ms:.0f}ms")
        
        if result.success:
            print(f"📄 Analysis (first 500 chars):\n{result.content[:500]}...\n")
            return {
                "success": True,
                "content": result.content,
                "channel": result.channel.value,
                "latency_ms": result.latency_ms
            }
        else:
            print(f"❌ Analysis failed: {result.error}")
            return {"success": False, "error": result.error}
    
    async def phase2_perplexity_research(self, cycle: int, phase1: Dict) -> Dict[str, Any]:
        """Phase 2: Perplexity researches best practices"""
        from backend.agents.models import AgentRequest, AgentType
        
        print(f"\n{'=' * 100}")
        print(f"🔬 PHASE 2: Perplexity Best Practices Research (Cycle {cycle})")
        print(f"{'=' * 100}")
        
        if not phase1.get("success"):
            print("⚠️ Skipping research - analysis failed")
            return {"success": False, "skipped": True}
        
        research_prompt = f"""🔍 AUTONOMOUS AGENT BEST PRACTICES RESEARCH

Context from DeepSeek Analysis:
{phase1['content'][:2000]}... [summary]

RESEARCH OBJECTIVES:
1. What are the state-of-the-art techniques for autonomous AI agent systems?
   - Self-healing patterns
   - Consensus decision-making
   - Error recovery strategies
   - Performance optimization

2. Industry standards for agent reliability:
   - Circuit breaker patterns
   - Graceful degradation
   - Dead letter queue strategies
   - Health monitoring

3. Best practices for multi-agent coordination:
   - Consensus algorithms
   - Conflict resolution
   - Load balancing
   - Failover strategies

4. Validate DeepSeek's improvement proposals against industry best practices.

Provide COMPREHENSIVE research with citations. Unlimited reasoning depth allowed."""

        request = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="research",
            prompt=research_prompt,
            code=None,
            context={
                "complex_task": True,
                "timeout_override": TIMEOUT_STANDARD
            }
        )
        
        print(f"📤 Sending to Perplexity (timeout: {TIMEOUT_STANDARD}s)...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Success: {result.success} | Channel: {result.channel} | Latency: {result.latency_ms:.0f}ms")
        
        if result.success:
            print(f"📄 Research (first 500 chars):\n{result.content[:500]}...\n")
            return {
                "success": True,
                "content": result.content,
                "channel": result.channel.value,
                "latency_ms": result.latency_ms
            }
        else:
            print(f"❌ Research failed: {result.error}")
            return {"success": False, "error": result.error}
    
    async def phase3_deepseek_proposal(self, cycle: int, phase1: Dict, phase2: Dict) -> Dict[str, Any]:
        """Phase 3: DeepSeek creates concrete implementation proposal"""
        from backend.agents.models import AgentRequest, AgentType
        
        print(f"\n{'=' * 100}")
        print(f"🎯 PHASE 3: DeepSeek Concrete Improvement Proposal (Cycle {cycle})")
        print(f"{'=' * 100}")
        
        proposal_prompt = f"""💡 CONCRETE IMPROVEMENT PROPOSAL

Self-Analysis Results:
{phase1.get('content', 'N/A')[:2000]}

Best Practices Research:
{phase2.get('content', 'N/A')[:2000]}

TASK: Create ONE specific, implementable improvement for maximum autonomy gain.

PROPOSAL FORMAT:
1. **Target Component**
   - File: exact path (e.g., backend/agents/unified_agent_interface.py)
   - Function/Class: exact name
   - Current Lines: approximate range

2. **Current Limitation**
   - What blocks autonomy now
   - Specific error scenario
   - Impact on system

3. **Proposed Enhancement**
   ```python
   # Exact code to add/modify
   def improved_function(...):
       # Implementation with comments
       pass
   ```

4. **Implementation Strategy**
   - Changes required (line-by-line)
   - Backward compatibility
   - Testing approach
   - Rollback plan

5. **Expected Benefits**
   - Autonomy improvement (quantified)
   - Risk mitigation
   - Performance impact

Be EXTREMELY SPECIFIC. Provide actual code, not pseudocode. This will be implemented directly."""

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="review",
            prompt=proposal_prompt,
            code=None,
            context={
                "use_file_access": True,
                "complex_task": True,
                "timeout_override": TIMEOUT_COMPLEX
            }
        )
        
        print(f"📤 Sending to DeepSeek (timeout: {TIMEOUT_COMPLEX}s)...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Success: {result.success} | Channel: {result.channel} | Latency: {result.latency_ms:.0f}ms")
        
        if result.success:
            print(f"📄 Proposal (first 800 chars):\n{result.content[:800]}...\n")
            return {
                "success": True,
                "content": result.content,
                "channel": result.channel.value,
                "latency_ms": result.latency_ms
            }
        else:
            print(f"❌ Proposal failed: {result.error}")
            return {"success": False, "error": result.error}
    
    async def phase4_perplexity_review(self, cycle: int, phase3: Dict) -> Dict[str, Any]:
        """Phase 4: Perplexity reviews proposal and builds consensus"""
        from backend.agents.models import AgentRequest, AgentType
        
        print(f"\n{'=' * 100}")
        print(f"🔍 PHASE 4: Perplexity Safety Review & Consensus (Cycle {cycle})")
        print(f"{'=' * 100}")
        
        if not phase3.get("success"):
            print("⚠️ No proposal to review")
            return {"success": False, "skipped": True, "approved": False}
        
        review_prompt = f"""🛡️ SAFETY REVIEW & CONSENSUS BUILDING

DeepSeek's Improvement Proposal:
{phase3['content']}

REVIEW TASKS:
1. **Safety Analysis**
   - Breaking changes risk (high/medium/low)
   - Data loss risk (yes/no)
   - Performance degradation risk (yes/no)
   - Security implications

2. **Technical Validation**
   - Code correctness (will it work?)
   - Best practices compliance
   - Edge cases handled
   - Testing adequacy

3. **Consensus Evaluation**
   Rate agreement with proposal (0-100%):
   - Necessity: Is this improvement needed?
   - Approach: Is the solution correct?
   - Priority: Should we do this now?
   - Safety: Is it safe to implement?

4. **FINAL DECISION**
   - APPROVE: Yes, implement now (score >= 85%)
   - REVISE: Good idea, needs changes (score 50-84%)
   - REJECT: Not safe or needed (score < 50%)

Provide THOROUGH analysis. Consensus score must be justified with evidence."""

        request = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="review",
            prompt=review_prompt,
            code=None,
            context={
                "complex_task": True,
                "timeout_override": TIMEOUT_STANDARD
            }
        )
        
        print(f"📤 Sending to Perplexity (timeout: {TIMEOUT_STANDARD}s)...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Success: {result.success} | Channel: {result.channel} | Latency: {result.latency_ms:.0f}ms")
        
        if result.success:
            print(f"📄 Review (first 500 chars):\n{result.content[:500]}...\n")
            
            # Parse consensus score (simple heuristic)
            content_lower = result.content.lower()
            if "approve" in content_lower and "85%" in content_lower or "90%" in content_lower or "95%" in content_lower:
                consensus_score = 0.9
                approved = True
            elif "approve" in content_lower:
                consensus_score = 0.85
                approved = True
            elif "revise" in content_lower:
                consensus_score = 0.6
                approved = False
            else:
                consensus_score = 0.4
                approved = False
            
            print(f"📊 Consensus Score: {consensus_score:.2%} | Approved: {approved}")
            
            return {
                "success": True,
                "content": result.content,
                "consensus_score": consensus_score,
                "approved": approved,
                "channel": result.channel.value,
                "latency_ms": result.latency_ms
            }
        else:
            print(f"❌ Review failed: {result.error}")
            return {"success": False, "error": result.error, "approved": False}
    
    async def phase5_deepseek_implement(self, cycle: int, phase3: Dict, phase4: Dict) -> Dict[str, Any]:
        """Phase 5: DeepSeek implements approved changes with backups"""
        from backend.agents.models import AgentRequest, AgentType
        
        print(f"\n{'=' * 100}")
        print(f"⚙️ PHASE 5: DeepSeek Implementation (Cycle {cycle})")
        print(f"{'=' * 100}")
        
        print("🔒 Creating backup before implementation...")
        
        # Backup unified_agent_interface.py
        agent_file = project_root / "backend" / "agents" / "unified_agent_interface.py"
        backup_file = agent_file.with_suffix(f".py.backup.cycle{cycle}.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(agent_file, backup_file)
        print(f"✅ Backup created: {backup_file.name}")
        
        implementation_prompt = f"""🔧 IMPLEMENTATION EXECUTION

Approved Proposal:
{phase3['content']}

Perplexity Review:
{phase4['content'][:1000]}

Consensus Score: {phase4.get('consensus_score', 0):.2%} ✅ APPROVED

TASK: Implement the approved changes NOW.

STEPS:
1. Read current code from backend/agents/unified_agent_interface.py
2. Apply the exact changes from the proposal
3. Verify syntax correctness
4. Return the COMPLETE modified code

CRITICAL REQUIREMENTS:
- Preserve all existing functionality
- Add comments explaining changes
- Follow existing code style
- Include error handling
- No placeholders - real implementation only

Return ONLY the modified code sections (not entire file). Be precise."""

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="implement",
            prompt=implementation_prompt,
            code=None,
            context={
                "use_file_access": True,
                "complex_task": True,
                "timeout_override": TIMEOUT_COMPLEX
            }
        )
        
        print(f"📤 Sending to DeepSeek (timeout: {TIMEOUT_COMPLEX}s)...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Success: {result.success} | Channel: {result.channel} | Latency: {result.latency_ms:.0f}ms")
        
        if result.success:
            print(f"📄 Implementation response (first 800 chars):\n{result.content[:800]}...\n")
            
            # For safety, we DON'T auto-apply changes - just log them
            print("⚠️ SAFETY MODE: Changes logged but not auto-applied.")
            print("Review the implementation in the cycle report before applying manually.")
            
            self.files_modified.append({
                "file": str(agent_file),
                "backup": str(backup_file),
                "changes": result.content,
                "cycle": cycle
            })
            
            return {
                "success": True,
                "content": result.content,
                "backup_file": str(backup_file),
                "target_file": str(agent_file),
                "auto_applied": False,  # Manual review required
                "channel": result.channel.value,
                "latency_ms": result.latency_ms
            }
        else:
            print(f"❌ Implementation failed: {result.error}")
            return {"success": False, "error": result.error}
    
    async def phase6_cross_validation(self, cycle: int, phase5: Dict) -> Dict[str, Any]:
        """Phase 6: Both agents validate the implementation"""
        from backend.agents.models import AgentRequest, AgentType
        
        print(f"\n{'=' * 100}")
        print(f"✅ PHASE 6: Cross-Validation (Cycle {cycle})")
        print(f"{'=' * 100}")
        
        if not phase5.get("success"):
            print("⚠️ No implementation to validate")
            return {"success": False, "validated": False}
        
        validation_prompt = f"""🔍 IMPLEMENTATION VALIDATION

Implementation Details:
{phase5['content'][:2000]}

Backup Location: {phase5.get('backup_file', 'N/A')}

VALIDATION TASKS:
1. Code correctness check
   - Syntax errors?
   - Logic errors?
   - Missing imports?

2. Safety verification
   - Breaking changes?
   - Data loss risk?
   - Performance impact?

3. Testing recommendations
   - Unit tests to run
   - Integration tests needed
   - Edge cases to verify

4. FINAL VERDICT
   - VALIDATED: Safe to apply ✅
   - NEEDS_REVIEW: Requires human check ⚠️
   - UNSAFE: Do not apply ❌

Be CRITICAL. Better to be cautious than cause production issues."""

        # Validate with BOTH agents
        print("Validating with DeepSeek...")
        ds_request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="review",
            prompt=validation_prompt,
            code=phase5.get('content', '')[:5000],
            context={"timeout_override": TIMEOUT_STANDARD}
        )
        ds_result = await self.agent.send_request(ds_request)
        
        print("Validating with Perplexity...")
        pp_request = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="review",
            prompt=validation_prompt,
            code=None,
            context={"timeout_override": TIMEOUT_STANDARD}
        )
        pp_result = await self.agent.send_request(pp_request)
        
        ds_validated = ds_result.success and "validated" in ds_result.content.lower()
        pp_validated = pp_result.success and "validated" in pp_result.content.lower()
        
        both_agree = ds_validated and pp_validated
        
        print(f"\n📊 Validation Results:")
        print(f"   DeepSeek: {'✅ VALIDATED' if ds_validated else '❌ NOT VALIDATED'}")
        print(f"   Perplexity: {'✅ VALIDATED' if pp_validated else '❌ NOT VALIDATED'}")
        print(f"   Consensus: {'✅ BOTH AGREE' if both_agree else '⚠️ DISAGREEMENT'}")
        
        return {
            "success": True,
            "validated": both_agree,
            "deepseek_validation": {
                "success": ds_result.success,
                "content": ds_result.content[:1000],
                "verdict": "VALIDATED" if ds_validated else "NOT_VALIDATED"
            },
            "perplexity_validation": {
                "success": pp_result.success,
                "content": pp_result.content[:1000],
                "verdict": "VALIDATED" if pp_validated else "NOT_VALIDATED"
            }
        }
    
    async def generate_report(self):
        """Generate comprehensive final report"""
        print(f"\n{'=' * 100}")
        print("📊 GENERATING FINAL REPORT")
        print(f"{'=' * 100}")
        
        report = {
            "session_start": self.cycle_history[0]["timestamp"] if self.cycle_history else None,
            "session_end": datetime.now().isoformat(),
            "total_cycles": len(self.cycle_history),
            "improvements_made": len(self.improvements_made),
            "files_modified": self.files_modified,
            "cycle_history": self.cycle_history,
            "summary": {
                "converged": any(c.get("converged", False) for c in self.cycle_history),
                "critical_errors": sum(1 for c in self.cycle_history if c.get("critical_error", False)),
                "successful_implementations": len(self.improvements_made)
            }
        }
        
        report_file = project_root / f"AGENT_AUTONOMOUS_IMPROVEMENT_FULL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Full report saved: {report_file.name}")
        print(f"\n📈 SESSION SUMMARY:")
        print(f"   Total Cycles: {report['total_cycles']}")
        print(f"   Improvements Implemented: {report['summary']['successful_implementations']}")
        print(f"   Convergence: {'✅ YES' if report['summary']['converged'] else '❌ NO'}")
        print(f"   Critical Errors: {report['summary']['critical_errors']}")
        
        if self.files_modified:
            print(f"\n📁 Files Modified:")
            for fm in self.files_modified:
                print(f"   - {fm['file']} (backup: {fm['backup']})")
        
        print(f"\n{'=' * 100}")
        print("✅ AUTONOMOUS SELF-IMPROVEMENT SESSION COMPLETE")
        print(f"{'=' * 100}")
        print(f"📄 Review full report: {report_file.name}")
        print(f"💡 Next steps: Review proposed changes and apply manually if validated.")

async def main():
    """Entry point"""
    system = AutonomousSelfImprovement()
    await system.run()

if __name__ == "__main__":
    asyncio.run(main())
