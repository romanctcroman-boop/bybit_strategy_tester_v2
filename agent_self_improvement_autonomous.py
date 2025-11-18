"""
Autonomous Agent Self-Improvement Cycle
========================================
Multi-agent collaboration for self-improvement with direct code access.

Process:
1. DeepSeek: Analyze current agent capabilities + weaknesses
2. Perplexity: Research best practices + industry standards
3. DeepSeek + Perplexity: Consensus on improvements
4. DeepSeek: Implement improvements
5. Perplexity: Validate implementation
6. Repeat until optimal autonomy achieved

Agents have direct file access via use_file_access=True
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

class AgentSelfImprovementCycle:
    def __init__(self):
        from backend.agents.unified_agent_interface import get_agent_interface
        from backend.agents.models import AgentType
        
        self.agent = get_agent_interface()
        self.AgentType = AgentType
        self.cycle_number = 0
        self.improvements_log: List[Dict[str, Any]] = []
        self.max_cycles = 5  # Safety limit
        
    async def run_autonomous_cycle(self):
        """Run complete autonomous self-improvement cycle"""
        print("=" * 100)
        print("🤖 AUTONOMOUS AGENT SELF-IMPROVEMENT CYCLE")
        print("=" * 100)
        print(f"Started: {datetime.now().isoformat()}")
        print(f"Max cycles: {self.max_cycles}")
        print(f"Agents: DeepSeek (analysis + implementation), Perplexity (research + validation)")
        print("=" * 100)
        
        for cycle in range(1, self.max_cycles + 1):
            self.cycle_number = cycle
            print(f"\n{'=' * 100}")
            print(f"🔄 CYCLE {cycle}/{self.max_cycles}")
            print(f"{'=' * 100}")
            
            # Phase 1: DeepSeek analyzes current state
            analysis = await self.phase1_deepseek_analyze()
            if not analysis["success"]:
                print(f"❌ Cycle {cycle} aborted: Analysis failed")
                break
            
            # Phase 2: Perplexity researches best practices
            research = await self.phase2_perplexity_research(analysis)
            if not research["success"]:
                print(f"⚠️ Cycle {cycle}: Research failed, using analysis only")
            
            # Phase 3: Consensus discussion
            consensus = await self.phase3_consensus_discussion(analysis, research)
            if not consensus["success"] or not consensus["improvements_needed"]:
                print(f"✅ Cycle {cycle}: No further improvements needed - CONVERGENCE ACHIEVED")
                break
            
            # Phase 4: DeepSeek implements improvements
            implementation = await self.phase4_deepseek_implement(consensus)
            if not implementation["success"]:
                print(f"❌ Cycle {cycle}: Implementation failed")
                break
            
            # Phase 5: Perplexity validates
            validation = await self.phase5_perplexity_validate(implementation)
            
            # Log cycle results
            self.improvements_log.append({
                "cycle": cycle,
                "timestamp": datetime.now().isoformat(),
                "analysis": analysis,
                "research": research,
                "consensus": consensus,
                "implementation": implementation,
                "validation": validation
            })
            
            # Check if validation passed
            if validation["success"] and validation.get("approved", False):
                print(f"✅ Cycle {cycle}: Validation PASSED")
            else:
                print(f"⚠️ Cycle {cycle}: Validation issues detected")
            
            # Brief pause between cycles
            await asyncio.sleep(2)
        
        # Generate final report
        await self.generate_final_report()
        
        print(f"\n{'=' * 100}")
        print("🎉 AUTONOMOUS SELF-IMPROVEMENT COMPLETE")
        print(f"{'=' * 100}")
        print(f"Total cycles: {len(self.improvements_log)}")
        print(f"Ended: {datetime.now().isoformat()}")
    
    async def phase1_deepseek_analyze(self) -> Dict[str, Any]:
        """Phase 1: DeepSeek analyzes current agent capabilities"""
        print(f"\n{'─' * 100}")
        print(f"📊 PHASE 1: DeepSeek Analysis (Cycle {self.cycle_number})")
        print(f"{'─' * 100}")
        
        from backend.agents.models import AgentRequest
        
        prompt = f"""🔍 AUTONOMOUS SELF-IMPROVEMENT ANALYSIS - Cycle {self.cycle_number}

Проанализируй СОБСТВЕННЫЕ возможности агентской системы через прямой доступ к коду.

Задачи:
1. Прочитай backend/agents/unified_agent_interface.py
2. Прочитай backend/agents/models.py  
3. Прочитай backend/agents/agent_to_agent_communicator.py
4. Оцени текущие возможности:
   - Автономность (способность работать без человека)
   - Самодиагностика (обнаружение собственных ошибок)
   - Самовосстановление (исправление ошибок автоматически)
   - Коллаборация (эффективность работы DeepSeek + Perplexity)
   - Доступ к проекту (использование file_access, code execution)

5. Определи TOP-3 слабости, которые мешают максимальной автономии

Верни JSON:
{{
  "current_capabilities": {{
    "autonomy_level": "low|medium|high",
    "self_diagnosis": "poor|fair|good|excellent",
    "self_healing": "none|basic|advanced",
    "collaboration_quality": "poor|fair|good|excellent",
    "project_access": "limited|partial|full"
  }},
  "weaknesses": [
    {{"issue": "...", "impact": "high|medium|low", "example": "..."}}
  ],
  "improvement_opportunities": [
    {{"area": "...", "benefit": "...", "feasibility": "easy|medium|hard"}}
  ]
}}

ВАЖНО: Используй use_file_access=True для чтения реального кода!
"""
        
        request = AgentRequest(
            agent_type=self.AgentType.DEEPSEEK,
            task_type="analyze",
            prompt=prompt,
            code=None,
            context={"use_file_access": True}  # Enable direct file access
        )
        
        print("📤 Sending analysis request to DeepSeek...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Response received (channel: {result.channel})")
        print(f"📝 Content length: {len(result.content)} chars")
        
        if result.success:
            print(f"Preview:\n{result.content[:500]}...")
            return {
                "success": True,
                "content": result.content,
                "channel": str(result.channel)
            }
        else:
            print(f"❌ Error: {result.error}")
            return {
                "success": False,
                "error": result.error
            }
    
    async def phase2_perplexity_research(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 2: Perplexity researches best practices"""
        print(f"\n{'─' * 100}")
        print(f"🔬 PHASE 2: Perplexity Research (Cycle {self.cycle_number})")
        print(f"{'─' * 100}")
        
        from backend.agents.models import AgentRequest
        
        analysis_summary = analysis.get("content", "")[:1000]  # First 1000 chars
        
        prompt = f"""🔬 AUTONOMOUS AGENT BEST PRACTICES RESEARCH

На основе анализа DeepSeek, исследуй best practices для максимальной автономии AI агентов.

DeepSeek Analysis Summary:
{analysis_summary}

Исследуй:
1. Autonomous AI agent patterns (self-improvement, self-healing)
2. Multi-agent collaboration frameworks (consensus, conflict resolution)
3. AI code generation best practices (safety, validation)
4. Error recovery patterns for production AI systems
5. Monitoring & observability for autonomous agents

Верни JSON:
{{
  "best_practices": [
    {{"pattern": "...", "description": "...", "source": "..."}}
  ],
  "applicable_to_us": [
    {{"practice": "...", "how_to_apply": "...", "expected_benefit": "..."}}
  ],
  "risks": [
    {{"risk": "...", "mitigation": "..."}}
  ]
}}
"""
        
        request = AgentRequest(
            agent_type=self.AgentType.PERPLEXITY,
            task_type="research",
            prompt=prompt,
            code=None,
            context={}
        )
        
        print("📤 Sending research request to Perplexity...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Response received (channel: {result.channel})")
        print(f"📝 Content length: {len(result.content)} chars")
        
        if result.success:
            print(f"Preview:\n{result.content[:500]}...")
            return {
                "success": True,
                "content": result.content,
                "channel": str(result.channel)
            }
        else:
            print(f"❌ Error: {result.error}")
            return {
                "success": False,
                "error": result.error
            }
    
    async def phase3_consensus_discussion(self, analysis: Dict[str, Any], research: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 3: Agents discuss and reach consensus"""
        print(f"\n{'─' * 100}")
        print(f"🤝 PHASE 3: Consensus Discussion (Cycle {self.cycle_number})")
        print(f"{'─' * 100}")
        
        from backend.agents.models import AgentRequest
        
        # Round 1: DeepSeek proposes improvements
        print("\n🔵 DeepSeek: Proposing improvements...")
        deepseek_proposal = await self._deepseek_propose(analysis, research)
        
        # Round 2: Perplexity reviews proposal
        print("\n🟣 Perplexity: Reviewing proposal...")
        perplexity_review = await self._perplexity_review(deepseek_proposal)
        
        # Round 3: DeepSeek finalizes consensus
        print("\n🔵 DeepSeek: Finalizing consensus...")
        final_consensus = await self._deepseek_finalize(deepseek_proposal, perplexity_review)
        
        return final_consensus
    
    async def _deepseek_propose(self, analysis: Dict[str, Any], research: Dict[str, Any]) -> Dict[str, Any]:
        """DeepSeek proposes improvements based on analysis + research"""
        from backend.agents.models import AgentRequest
        
        prompt = f"""🎯 PROPOSE IMPROVEMENTS (Consensus Round 1)

На основе своего анализа и исследований Perplexity, предложи конкретные улучшения.

Analysis: {analysis.get('content', '')[:800]}
Research: {research.get('content', '')[:800]}

Предложи ТОП-3 улучшения для текущего цикла:
1. Что улучшить (конкретный файл, функция, класс)
2. Как улучшить (код changes, новые методы)
3. Зачем (ожидаемый эффект на автономность)

Верни JSON:
{{
  "proposed_improvements": [
    {{
      "id": 1,
      "target": "file:function",
      "change_type": "add|modify|refactor",
      "description": "...",
      "code_snippet": "...",
      "expected_benefit": "...",
      "risk_level": "low|medium|high"
    }}
  ],
  "priority_order": [1, 2, 3],
  "justification": "..."
}}
"""
        
        request = AgentRequest(
            agent_type=self.AgentType.DEEPSEEK,
            task_type="review",
            prompt=prompt,
            code=None,
            context={"use_file_access": True}
        )
        
        result = await self.agent.send_request(request)
        return {
            "success": result.success,
            "content": result.content,
            "error": result.error if not result.success else None
        }
    
    async def _perplexity_review(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Perplexity reviews DeepSeek's proposal"""
        from backend.agents.models import AgentRequest
        
        prompt = f"""🔍 REVIEW PROPOSAL (Consensus Round 2)

DeepSeek предложил улучшения. Оцени их с точки зрения:
1. Безопасность (не сломают ли существующий код)
2. Эффективность (действительно ли повысят автономность)
3. Приоритет (что внедрить первым)

Proposal: {proposal.get('content', '')[:1000]}

Верни JSON:
{{
  "approved": true|false,
  "concerns": [
    {{"improvement_id": 1, "concern": "...", "severity": "critical|major|minor"}}
  ],
  "recommendations": [
    {{"improvement_id": 1, "recommendation": "...", "alternative": "..."}}
  ],
  "prioritization": [1, 3, 2],  // Preferred order
  "overall_verdict": "approve_all|approve_partial|reject"
}}
"""
        
        request = AgentRequest(
            agent_type=self.AgentType.PERPLEXITY,
            task_type="review",
            prompt=prompt,
            code=None,
            context={}
        )
        
        result = await self.agent.send_request(request)
        return {
            "success": result.success,
            "content": result.content,
            "error": result.error if not result.success else None
        }
    
    async def _deepseek_finalize(self, proposal: Dict[str, Any], review: Dict[str, Any]) -> Dict[str, Any]:
        """DeepSeek finalizes consensus based on Perplexity feedback"""
        from backend.agents.models import AgentRequest
        
        prompt = f"""✅ FINALIZE CONSENSUS (Consensus Round 3)

На основе своего предложения и отзыва Perplexity, финализируй план улучшений.

My Proposal: {proposal.get('content', '')[:800]}
Perplexity Review: {review.get('content', '')[:800]}

Учти замечания Perplexity и создай финальный план для этого цикла.

Верни JSON:
{{
  "improvements_needed": true|false,
  "final_improvements": [
    {{
      "target": "...",
      "action": "...",
      "code": "...",
      "rationale": "..."
    }}
  ],
  "consensus_achieved": true|false,
  "cycle_goal": "..."
}}
"""
        
        request = AgentRequest(
            agent_type=self.AgentType.DEEPSEEK,
            task_type="analyze",
            prompt=prompt,
            code=None,
            context={}
        )
        
        result = await self.agent.send_request(request)
        
        # Parse response to determine if improvements needed
        improvements_needed = True
        if result.success and "improvements_needed" in result.content.lower():
            if "false" in result.content.lower():
                improvements_needed = False
        
        return {
            "success": result.success,
            "improvements_needed": improvements_needed,
            "content": result.content,
            "error": result.error if not result.success else None
        }
    
    async def phase4_deepseek_implement(self, consensus: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 4: DeepSeek implements agreed improvements"""
        print(f"\n{'─' * 100}")
        print(f"⚙️ PHASE 4: DeepSeek Implementation (Cycle {self.cycle_number})")
        print(f"{'─' * 100}")
        
        from backend.agents.models import AgentRequest
        
        prompt = f"""⚙️ IMPLEMENT IMPROVEMENTS (Execution Phase)

Consensus достигнут. Внедри согласованные улучшения.

Consensus: {consensus.get('content', '')[:1000]}

ЗАДАЧА:
1. Используй file_access для чтения текущего кода
2. Внедри согласованные изменения
3. Создай новые методы/функции если нужно
4. Верни diff или описание изменений

ВАЖНО: Используй use_file_access=True для работы с реальным кодом!

Верни JSON:
{{
  "implemented": true|false,
  "changes": [
    {{
      "file": "...",
      "type": "modified|created",
      "summary": "...",
      "code_preview": "..."
    }}
  ],
  "tests_needed": ["..."],
  "rollback_plan": "..."
}}
"""
        
        request = AgentRequest(
            agent_type=self.AgentType.DEEPSEEK,
            task_type="fix",
            prompt=prompt,
            code=None,
            context={"use_file_access": True}
        )
        
        print("📤 Sending implementation request to DeepSeek...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Response received (channel: {result.channel})")
        print(f"📝 Content length: {len(result.content)} chars")
        
        if result.success:
            print(f"Preview:\n{result.content[:500]}...")
            return {
                "success": True,
                "content": result.content,
                "channel": str(result.channel)
            }
        else:
            print(f"❌ Error: {result.error}")
            return {
                "success": False,
                "error": result.error
            }
    
    async def phase5_perplexity_validate(self, implementation: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 5: Perplexity validates implementation"""
        print(f"\n{'─' * 100}")
        print(f"✅ PHASE 5: Perplexity Validation (Cycle {self.cycle_number})")
        print(f"{'─' * 100}")
        
        from backend.agents.models import AgentRequest
        
        prompt = f"""✅ VALIDATE IMPLEMENTATION

DeepSeek внедрил улучшения. Валидируй их корректность.

Implementation: {implementation.get('content', '')[:1000]}

Проверь:
1. Безопасность (не сломан ли код)
2. Соответствие best practices
3. Достижение цели (улучшилась ли автономность)

Верни JSON:
{{
  "approved": true|false,
  "issues_found": [
    {{"severity": "critical|major|minor", "description": "..."}}
  ],
  "recommendations": ["..."],
  "autonomy_improvement": "significant|moderate|minimal|none"
}}
"""
        
        request = AgentRequest(
            agent_type=self.AgentType.PERPLEXITY,
            task_type="review",
            prompt=prompt,
            code=None,
            context={}
        )
        
        print("📤 Sending validation request to Perplexity...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Response received (channel: {result.channel})")
        print(f"📝 Content length: {len(result.content)} chars")
        
        if result.success:
            print(f"Preview:\n{result.content[:500]}...")
            
            # Parse approval
            approved = "approved" in result.content.lower() and "true" in result.content.lower()
            
            return {
                "success": True,
                "approved": approved,
                "content": result.content,
                "channel": str(result.channel)
            }
        else:
            print(f"❌ Error: {result.error}")
            return {
                "success": False,
                "approved": False,
                "error": result.error
            }
    
    async def generate_final_report(self):
        """Generate comprehensive final report"""
        print(f"\n{'=' * 100}")
        print("📊 GENERATING FINAL REPORT")
        print(f"{'=' * 100}")
        
        report_path = project_root / f"AGENT_SELF_IMPROVEMENT_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            "session": {
                "started": datetime.now().isoformat(),
                "total_cycles": len(self.improvements_log),
                "max_cycles": self.max_cycles
            },
            "cycles": self.improvements_log,
            "summary": {
                "successful_cycles": len([c for c in self.improvements_log if c.get("validation", {}).get("approved", False)]),
                "failed_cycles": len([c for c in self.improvements_log if not c.get("validation", {}).get("approved", False)]),
                "convergence_achieved": self.cycle_number < self.max_cycles
            }
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Report saved: {report_path}")
        print(f"\n📈 Summary:")
        print(f"   Total cycles: {report['summary']['successful_cycles'] + report['summary']['failed_cycles']}")
        print(f"   Successful: {report['summary']['successful_cycles']}")
        print(f"   Failed: {report['summary']['failed_cycles']}")
        print(f"   Convergence: {'✅ Yes' if report['summary']['convergence_achieved'] else '❌ No (reached max cycles)'}")

async def main():
    """Entry point for autonomous self-improvement"""
    cycle = AgentSelfImprovementCycle()
    await cycle.run_autonomous_cycle()

if __name__ == "__main__":
    asyncio.run(main())
