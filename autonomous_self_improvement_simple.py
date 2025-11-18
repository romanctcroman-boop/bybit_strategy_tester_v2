"""
🤖 Simplified Autonomous Self-Improvement Orchestrator
======================================================

Single-agent (DeepSeek only) for faster iteration:
- Analyze current agent system
- Identify improvements
- Implement changes
- Test and verify
- Repeat

Focus: SPEED + AUTONOMY (skip Perplexity for now)
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
from backend.agents.unified_agent_interface import (
    get_agent_interface,
    AgentRequest,
    AgentType
)

class SimpleAutonomousOrchestrator:
    """Simplified orchestrator using DeepSeek only"""
    
    def __init__(self):
        self.agent = get_agent_interface()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = project_root / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.session_log: List[Dict[str, Any]] = []
        
        logger.info(f"🤖 Simple Autonomous Session {self.session_id} started")
    
    async def analyze_current_system(self) -> Dict[str, Any]:
        """DeepSeek analyzes current agent system"""
        logger.info("=" * 80)
        logger.info("Phase 1: System Analysis")
        logger.info("=" * 80)
        
        analysis_prompt = """
Analyze the current AI agent system for autonomy improvements.

Current System:
- UnifiedAgentInterface: 8 DeepSeek + 8 Perplexity keys, auto-rotation
- Circuit breakers: 3 registered (deepseek_api, perplexity_api, mcp_server)
- Health monitoring: 30s interval with auto-recovery
- Phase 1 complete: Basic self-healing infrastructure

Task: Find the TOP 1 most impactful improvement for maximum autonomy.

Return JSON:
{
  "current_autonomy_score": 0-10,
  "top_improvement": {
    "title": "Brief title",
    "description": "What needs to be done",
    "impact": "Why this maximizes autonomy",
    "implementation_steps": [
      "Step 1",
      "Step 2",
      ...
    ],
    "files_to_modify": ["file1.py", "file2.py"],
    "estimated_lines": 50-500
  },
  "expected_autonomy_score_after": 0-10
}

Focus on:
1. Error recovery gaps
2. Decision-making bottlenecks
3. Human intervention points
4. Monitoring/alerting gaps
"""
        
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="analyze",
            prompt=analysis_prompt,
            context={"focus": "top_1_improvement"}
        )
        
        logger.info("🔍 DeepSeek analyzing system...")
        response = await self.agent.send_request(request)
        
        if not response.success:
            logger.error(f"❌ Analysis failed: {response.error}")
            return {"success": False, "error": response.error}
        
        logger.info(f"✅ Analysis complete: {len(response.content)} chars")
        self.session_log.append({
            "phase": "analysis",
            "content": response.content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Try to parse JSON
        try:
            analysis_data = json.loads(response.content)
            return {"success": True, "data": analysis_data}
        except json.JSONDecodeError:
            # If not JSON, extract from markdown code block
            if "```json" in response.content:
                json_str = response.content.split("```json")[1].split("```")[0].strip()
                analysis_data = json.loads(json_str)
                return {"success": True, "data": analysis_data}
            else:
                logger.warning("⚠️ Response not JSON, using raw text")
                return {"success": True, "data": {"raw": response.content}}
    
    async def generate_implementation(self, improvement: Dict[str, Any]) -> Dict[str, Any]:
        """DeepSeek generates implementation code"""
        logger.info("=" * 80)
        logger.info("Phase 2: Implementation Generation")
        logger.info("=" * 80)
        
        impl_prompt = f"""
Generate Python code to implement this improvement:

Improvement:
{json.dumps(improvement, indent=2)}

Requirements:
1. Generate complete, working Python code
2. Include all imports and type hints
3. Add comprehensive docstrings
4. Follow existing code style (loguru for logging, async/await)
5. Include error handling
6. Make it production-ready

Return Python code wrapped in ```python blocks.
Include inline comments explaining key decisions.
"""
        
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="code_generation",
            prompt=impl_prompt,
            context={"improvement": improvement}
        )
        
        logger.info("💻 DeepSeek generating implementation...")
        response = await self.agent.send_request(request)
        
        if not response.success:
            logger.error(f"❌ Implementation generation failed: {response.error}")
            return {"success": False, "error": response.error}
        
        logger.info(f"✅ Implementation generated: {len(response.content)} chars")
        self.session_log.append({
            "phase": "implementation",
            "content": response.content,
            "timestamp": datetime.now().isoformat()
        })
        
        return {"success": True, "code": response.content}
    
    async def verify_implementation(self, code: str, improvement: Dict[str, Any]) -> Dict[str, Any]:
        """DeepSeek verifies generated code"""
        logger.info("=" * 80)
        logger.info("Phase 3: Verification")
        logger.info("=" * 80)
        
        verify_prompt = f"""
Review this generated code for production readiness:

Improvement Goal:
{improvement.get('title', 'Unknown')}

Generated Code:
{code[:2000]}...

Verification Tasks:
1. Check for syntax errors
2. Verify all imports are available
3. Check error handling completeness
4. Verify async/await usage
5. Check for security issues
6. Verify integration with existing code

Return JSON:
{{
  "ready_for_production": true/false,
  "issues_found": [
    {{"severity": "HIGH/MEDIUM/LOW", "description": "Issue description", "fix": "How to fix"}}
  ],
  "suggestions": ["Suggestion 1", "Suggestion 2", ...],
  "confidence_score": 0-10
}}
"""
        
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="code_review",
            prompt=verify_prompt,
            context={"code": code}
        )
        
        logger.info("🔍 DeepSeek verifying implementation...")
        response = await self.agent.send_request(request)
        
        if not response.success:
            logger.error(f"❌ Verification failed: {response.error}")
            return {"success": False, "error": response.error}
        
        logger.info(f"✅ Verification complete: {len(response.content)} chars")
        self.session_log.append({
            "phase": "verification",
            "content": response.content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Try to parse JSON
        try:
            verification_data = json.loads(response.content)
            return {"success": True, "data": verification_data}
        except json.JSONDecodeError:
            if "```json" in response.content:
                json_str = response.content.split("```json")[1].split("```")[0].strip()
                verification_data = json.loads(json_str)
                return {"success": True, "data": verification_data}
            else:
                return {"success": True, "data": {"raw": response.content}}
    
    async def run_cycle(self):
        """Run one complete improvement cycle"""
        logger.info("🚀 Starting Simple Autonomous Improvement Cycle")
        logger.info(f"📊 Session: {self.session_id}")
        logger.info("")
        
        try:
            # Phase 1: Analyze
            analysis_result = await self.analyze_current_system()
            if not analysis_result["success"]:
                logger.error("❌ Analysis failed, aborting")
                return
            
            improvement = analysis_result["data"].get("top_improvement")
            if not improvement:
                logger.warning("⚠️ No improvement identified")
                improvement = analysis_result["data"]  # Use raw data
            
            logger.info(f"📌 Top Improvement: {improvement.get('title', 'Unknown')}")
            
            # Phase 2: Generate Implementation
            impl_result = await self.generate_implementation(improvement)
            if not impl_result["success"]:
                logger.error("❌ Implementation generation failed, aborting")
                return
            
            code = impl_result["code"]
            logger.info(f"📝 Implementation generated: {len(code)} chars")
            
            # Phase 3: Verify
            verify_result = await self.verify_implementation(code, improvement)
            if not verify_result["success"]:
                logger.error("❌ Verification failed, aborting")
                return
            
            verification = verify_result["data"]
            ready = verification.get("ready_for_production", False)
            confidence = verification.get("confidence_score", 0)
            
            logger.info(f"✅ Verification complete: ready={ready}, confidence={confidence}/10")
            
            # Save results
            self._save_session()
            
            logger.info("=" * 80)
            logger.info("🎉 CYCLE COMPLETE")
            logger.info("=" * 80)
            logger.info(f"📄 Session log: {self.log_dir / f'{self.session_id}_session.json'}")
            
        except Exception as e:
            logger.error(f"💥 Cycle error: {type(e).__name__}: {e}")
            logger.exception(e)
            raise
    
    def _save_session(self):
        """Save session log to file"""
        filename = self.log_dir / f"{self.session_id}_session.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": self.session_id,
                "timestamp": datetime.now().isoformat(),
                "phases": len(self.session_log),
                "log": self.session_log
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Session saved: {filename}")


async def main():
    """Main entry point"""
    try:
        orchestrator = SimpleAutonomousOrchestrator()
        await orchestrator.run_cycle()
    except KeyboardInterrupt:
        logger.warning("⚠️ Interrupted by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {type(e).__name__}: {e}")
        logger.exception(e)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutdown complete")
    except Exception as e:
        logger.error(f"💥 Process terminating with error: {e}")
        sys.exit(1)
