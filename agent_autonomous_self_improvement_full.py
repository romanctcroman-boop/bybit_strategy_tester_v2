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
import uuid
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

from backend.agents.agent_memory import AgentMemoryManager
from backend.agents.edit_safety import (
    capture_file_metadata,
    capture_system_health_snapshot,
    compute_file_checksum,
    validate_python_file,
)
from backend.agents.code_editing.file_direct_editor import FileDirectEditor
from backend.agents.code_editing.phase5_direct_editor import Phase5DirectEditor
from backend.agents.file_operation_controller import FileOperationController
from backend.agents.agent_to_agent_communicator import (
    get_communicator,
    AgentMessage as CommunicatorMessage,
    MessageType as CommunicatorMessageType,
    CommunicationPattern,
)
from backend.agents.patch_utils import (
    apply_marker_patches,
    apply_unified_diff,
    extract_code_blocks,
)
from backend.agents.health_monitor import FileOperationStrategy, get_health_monitor
from backend.agents.prompt_streamer import (
    HierarchicalPromptManager,
    PromptSegmentRegistry,
    PromptOverflowError,
)

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Constants
MAX_CYCLES = 10
CONVERGENCE_THRESHOLD = 0.99  # Require ~100% consensus
TIMEOUT_COMPLEX = 600  # 10 minutes for deep analysis
TIMEOUT_STANDARD = 300  # 5 minutes for reviews
CONSENSUS_MAX_TURNS = 8
CONSENSUS_HISTORY_SNIPPET = 4
CONSENSUS_APPROVAL_KEYWORDS = (
    "approved",
    "approve",
    "validated",
    "safe to implement",
    "готово",
    "можно применять",
)
CONSENSUS_BLOCKER_KEYWORDS = (
    "reject",
    "unsafe",
    "rollback",
    "do not implement",
    "cannot approve",
    "critical blocker",
    "stop",
)

ANALYSIS_TARGET_FILES = [
    "backend/agents/unified_agent_interface.py",
    "backend/agents/models.py",
    "backend/agents/key_manager.py",
]

PROPOSAL_TARGET_FILES = [
    "backend/agents/unified_agent_interface.py",
]

class AutonomousSelfImprovement:
    def __init__(self):
        self.cycle_history = []
        self.improvements_made = []
        self.files_modified = []
        self.memory_context: str | None = None
        self.memory_loaded: bool = False
        self.memory_insights: str | None = None
        self._memory_snapshot_path = project_root / "AGENT_MEMORY_CACHE.json"
        self.memory_manager = AgentMemoryManager(project_root)
        self.health_monitor = get_health_monitor()
        self.file_editor = FileDirectEditor(
            project_root,
            default_test_command="pytest tests/backend/test_autonomous_self_improvement_phase5.py -q",
        )
        self.phase5_direct_editor = Phase5DirectEditor(self.file_editor, self.memory_manager)
        self.file_ops_controller = FileOperationController(
            project_root,
            self.memory_manager,
            self.health_monitor,
        )
        self.communicator = get_communicator()
        self.consensus_history: List[Dict[str, Any]] = []
        self.transcripts_dir = project_root / "autonomous_logs" / "consensus_transcripts"
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        self.segment_registry = PromptSegmentRegistry(project_root)
        self.prompt_manager = HierarchicalPromptManager(self.segment_registry)
        
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

        # Load historical memory once at startup
        try:
            self.memory_context, self.memory_insights = self.memory_manager.load_history(
                max_cycles=5,
                snapshot_path=self._memory_snapshot_path,
            )
            self.memory_loaded = True
            print("🧠 Agent memory loaded.")
            print(self.memory_context)
            if self.memory_insights:
                print(self.memory_insights)
        except Exception as e:
            # Memory is a best-effort feature; do not block cycles on it
            self.memory_context = None
            self.memory_loaded = False
            self.memory_insights = None
            print(f"⚠️ Failed to load agent memory: {e}")
        
        for cycle in range(1, MAX_CYCLES + 1):
            print(f"\n{'#' * 100}")
            print(f"🔄 CYCLE {cycle}/{MAX_CYCLES}")
            print(f"{'#' * 100}")
            
            cycle_result = await self.execute_cycle(cycle)
            self.cycle_history.append(cycle_result)

            # Persist cycle result into a unified memory report for future runs
            try:
                self.memory_manager.save_cycle_result(cycle_result)
            except Exception as e:
                print(f"⚠️ Failed to persist cycle {cycle} to memory: {e}")
            
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
            
            # Multi-turn consensus loop before review
            consensus = await self.run_consensus_loop(cycle_num, phase1, phase2, phase3)
            cycle_data["phases"]["consensus"] = consensus

            # Phase 4: Perplexity Safety Review & Consensus
            phase4 = await self.phase4_perplexity_review(cycle_num, phase3, consensus)
            cycle_data["phases"]["review"] = phase4

            combined_consensus = self._combine_consensus_scores(
                phase4.get("consensus_score"),
                consensus.get("confidence"),
            )
            phase4["combined_consensus_score"] = combined_consensus
            cycle_data["consensus_score"] = combined_consensus

            # Phase 5: DeepSeek Implementation (if approved)
            should_implement = (
                phase4.get("approved", False)
                and combined_consensus >= CONVERGENCE_THRESHOLD
                and not consensus.get("blocked", False)
                and (consensus.get("approved") is not False)
            )

            if should_implement:
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
                print(
                    f"⚠️ Proposal not approved or consensus too low ({combined_consensus:.2%})"
                )
                cycle_data["converged"] = False
            
        except Exception as e:
            print(f"❌ Cycle {cycle_num} exception: {e}")
            cycle_data["critical_error"] = True
            cycle_data["error"] = str(e)
        
        return cycle_data

    def _capture_health_snapshot(self) -> Dict[str, Any]:
        if not hasattr(self, "agent"):
            return {}
        from backend.agents.models import AgentType

        key_manager = getattr(self.agent, "key_manager", None)
        if not key_manager:
            return {}

        deepseek_active = key_manager.count_active(AgentType.DEEPSEEK)
        perplexity_active = key_manager.count_active(AgentType.PERPLEXITY)
        snapshot = capture_system_health_snapshot(
            getattr(self.agent, "mcp_available", False),
            deepseek_active,
            perplexity_active,
        )
        try:
            self.memory_manager.record_event("health_snapshot", snapshot)
        except Exception:
            pass
        return snapshot
    
    def _build_memory_block(self) -> str:
        insights = self.memory_insights or "No aggregated insights yet."
        recent_events = self.memory_manager.render_recent_events() if self.memory_manager else ""
        recent_events_block = recent_events or "No execution telemetry captured yet."

        if self.memory_context:
            return f"""

PRIOR SELF-IMPROVEMENT CONTEXT:
{self.memory_context}

STRATEGIC MEMORY INSIGHTS:
{insights}

RECENT EXECUTION EVENTS:
{recent_events_block}
"""

        if recent_events:
            return f"""

RECENT EXECUTION EVENTS:
{recent_events}
"""

        return ""

    def _manifest_context_block(self, manifest: Dict[str, Any] | None) -> str:
        if not manifest:
            return "No segment manifest recorded. Request access via MCP tools if needed."

        lines = [
            f"Combined Hash: {manifest.get('combined_hash')}",
            f"Total Characters: {manifest.get('total_chars')}",
            "Segments:",
        ]
        for segment in manifest.get("segments", []):
            lines.append(
                f"- id={segment.get('segment_id')} path={segment.get('file_path')} "
                f"part {segment.get('part_index')}/{segment.get('part_count')} "
                f"sha256={str(segment.get('sha256'))[:12]}..."
            )
        return "\n".join(lines)

    def _cache_signature(self, phase: str, *parts: str) -> str:
        material = "||".join(part or "" for part in parts)
        return hashlib.sha1(f"{phase}::{material}".encode("utf-8")).hexdigest()

    def _file_state_signature(self, files: List[str]) -> str:
        digests: List[str] = []
        for rel_path in files:
            target = project_root / rel_path
            try:
                data = target.read_bytes()
            except FileNotFoundError:
                data = f"missing::{rel_path}".encode("utf-8")
            digest = hashlib.sha1(data).hexdigest()
            digests.append(f"{rel_path}:{digest}")
        joined = "||".join(digests)
        return hashlib.sha1(joined.encode("utf-8")).hexdigest()

    def _phase_memory_block(self, phase: str, context: str | None) -> str:
        if not self.memory_manager:
            return ""
        snippet = self.memory_manager.format_memory_snippets(phase, context or phase)
        if not snippet:
            return ""
        return f"""

MEMORY ({phase.upper()}):
{snippet}
"""

    def _trim_text(self, text: str | None, limit: int = 1200) -> str:
        if not text:
            return "(no data)"
        text = text.strip()
        return text if len(text) <= limit else text[:limit] + "..."

    def _build_consensus_prompt(
        self,
        cycle: int,
        phase1: Dict[str, Any] | None,
        phase2: Dict[str, Any] | None,
        phase3: Dict[str, Any] | None,
    ) -> str:
        analysis = phase1.get("content") if phase1 else ""
        research = phase2.get("content") if phase2 else ""
        proposal = phase3.get("content") if phase3 else ""
        memory_block = self._build_memory_block()
        manifest_block = self._manifest_context_block(
            phase3.get("segment_manifest") if phase3 else None
        )

        return f"""🔁 MULTI-AGENT CONSENSUS LOOP — Cycle {cycle}{memory_block}

CONTEXT SNAPSHOT:
1. DeepSeek Analysis Highlights:
{analysis}

2. Perplexity Research Highlights:
{research}

3. Proposed Implementation:
{proposal}

4. Segment Manifest (entire context stored on disk — do not ignore):
{manifest_block}

COLLABORATION RULES:
- DeepSeek starts by restating the proposal, open risks, and expected autonomy gains.
- Perplexity critiques for safety, reliability, and alignment with best practices.
- Alternate responses until Perplexity sends either `APPROVED: <confidence 0-1>` or `BLOCKED: <reason>`.
- Include concrete rollback plan, telemetry updates, and tests required before rollout.
- Keep each turn focused, cite specific files/functions, and avoid repeating identical text.
- Never claim consensus unless every referenced segment has been processed. Report
    `BLOCKED` if any manifest entry could not be reviewed.

GOAL:
Reach an explicit consensus on whether the implementation is safe to execute right now. If changes are needed, clearly enumerate them."""

    def _serialize_message(self, message: CommunicatorMessage) -> Dict[str, Any]:
        return {
            "message_id": message.message_id,
            "from": message.from_agent.value,
            "to": message.to_agent.value,
            "message_type": message.message_type.value,
            "content": self._trim_text(message.content, 600),
            "iteration": message.iteration,
            "confidence": message.confidence_score,
            "timestamp": message.timestamp,
        }

    def _extract_confidence_from_text(self, text: str | None) -> float | None:
        if not text:
            return None
        percent_match = re.search(r"(\d{1,3})%", text)
        if percent_match:
            value = float(percent_match.group(1)) / 100.0
            if 0 <= value <= 1:
                return value
        decimal_match = re.search(r"(0?\.\d+|1(?:\.0+)?)", text)
        if decimal_match:
            try:
                value = float(decimal_match.group(1))
                if 0 <= value <= 1:
                    return value
            except ValueError:
                return None
        return None

    def _contains_keyword(self, text: str | None, keywords: tuple[str, ...]) -> bool:
        if not text:
            return False
        lowered = text.lower()
        return any(keyword in lowered for keyword in keywords)

    def _format_history_snippet(self, history: List[Dict[str, Any]]) -> str:
        if not history:
            return ""
        snippet = history[-CONSENSUS_HISTORY_SNIPPET:]
        return "\n".join(
            f"{entry['from'].upper()}[{entry['iteration']}]: {entry['content']}" for entry in snippet
        )

    def _combine_consensus_scores(self, review_score: float | None, loop_confidence: float | None) -> float:
        scores = [score for score in (review_score, loop_confidence) if score and score > 0]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 4)

    def _consensus_context_excerpt(self, consensus_data: Dict[str, Any] | None) -> str:
        if not consensus_data:
            return "No prior consensus exchange recorded."
        history = consensus_data.get("history")
        if not history:
            return "Consensus history unavailable."
        return self._format_history_snippet(history)

    def _write_consensus_transcript(self, cycle: int, payload: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_path = self.transcripts_dir / f"cycle_{cycle:02d}_{timestamp}.json"
        try:
            transcript_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return str(transcript_path)
        except Exception as exc:  # pragma: no cover - filesystem edge cases
            print(f"⚠️ Failed to write consensus transcript: {exc}")
            return ""

    def _record_consensus_event(self, cycle: int, payload: Dict[str, Any]) -> None:
        if not self.memory_manager:
            return
        event = {
            "cycle": cycle,
            "verdict": payload.get("verdict"),
            "confidence": payload.get("confidence"),
            "approved": payload.get("approved"),
            "blocked": payload.get("blocked"),
            "transcript": payload.get("transcript_path"),
            "summary": payload.get("summary"),
        }
        try:
            self.memory_manager.record_event("consensus_loop", event)
        except Exception as exc:  # pragma: no cover - telemetry best-effort
            print(f"⚠️ Telemetry write skipped (consensus_loop): {exc}")

    def _summarize_consensus_history(
        self, cycle: int, history: List[CommunicatorMessage]
    ) -> Dict[str, Any]:
        from backend.agents.models import AgentType

        serialized = [self._serialize_message(msg) for msg in history]
        peer_messages = [msg for msg in history if msg.from_agent != AgentType.ORCHESTRATOR]
        if not peer_messages:
            peer_messages = history

        final_message = peer_messages[-1]
        approved = (
            final_message.from_agent == AgentType.PERPLEXITY
            and self._contains_keyword(final_message.content, CONSENSUS_APPROVAL_KEYWORDS)
        )
        blocked = self._contains_keyword(final_message.content, CONSENSUS_BLOCKER_KEYWORDS)
        confidence = self._extract_confidence_from_text(final_message.content)
        if confidence is None:
            scores = [msg.confidence_score for msg in peer_messages if msg.confidence_score]
            confidence = round(sum(scores) / len(scores), 3) if scores else 0.0
        confidence = max(0.0, min(1.0, confidence))

        summary_text = self._format_history_snippet(serialized)
        transcript_payload = {
            "cycle": cycle,
            "verdict": "approved" if approved and not blocked else ("blocked" if blocked else "needs_revision"),
            "confidence": confidence,
            "approved": approved and not blocked,
            "blocked": blocked,
            "history": serialized,
        }
        transcript_path = self._write_consensus_transcript(cycle, transcript_payload)

        result = {
            "success": True,
            "history": serialized,
            "deepseek_turns": sum(
                1 for msg in peer_messages if msg.from_agent == AgentType.DEEPSEEK
            ),
            "perplexity_turns": sum(
                1 for msg in peer_messages if msg.from_agent == AgentType.PERPLEXITY
            ),
            "confidence": confidence,
            "approved": approved and not blocked,
            "blocked": blocked,
            "summary": summary_text,
            "verdict": transcript_payload["verdict"],
            "transcript_path": transcript_path,
        }
        self._record_consensus_event(cycle, result)
        return result

    async def run_consensus_loop(
        self,
        cycle: int,
        phase1: Dict[str, Any],
        phase2: Dict[str, Any],
        phase3: Dict[str, Any],
        max_turns: int = CONSENSUS_MAX_TURNS,
    ) -> Dict[str, Any]:
        from backend.agents.models import AgentType

        prompt = self._build_consensus_prompt(cycle, phase1, phase2, phase3)
        initial_message = CommunicatorMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.DEEPSEEK,
            message_type=CommunicatorMessageType.CONSENSUS_REQUEST,
            content=prompt,
            context={
                "task_type": "review",
                "consensus_cycle": cycle,
                "timeout_override": TIMEOUT_STANDARD,
                "consensus_objective": "autonomy_guardrails",
            },
            conversation_id=str(uuid.uuid4()),
            iteration=1,
            max_iterations=max_turns,
        )

        try:
            history = await self.communicator.multi_turn_conversation(
                initial_message,
                max_turns=max_turns,
                pattern=CommunicationPattern.SEQUENTIAL,
            )
        except Exception as exc:
            print(f"⚠️ Consensus loop failed: {exc}")
            result = {
                "success": False,
                "error": str(exc),
                "history": [],
                "approved": False,
                "blocked": False,
                "confidence": 0.0,
            }
            self._record_consensus_event(cycle, result)
            return result

        summary = self._summarize_consensus_history(cycle, history)
        self.consensus_history.append(summary)
        return summary

    async def phase1_deepseek_analysis(self, cycle: int) -> Dict[str, Any]:
        """Phase 1: DeepSeek analyzes agent code with direct file access"""
        from backend.agents.models import AgentRequest, AgentType
        
        print(f"\n{'=' * 100}")
        print(f"📊 PHASE 1: DeepSeek Deep Analysis (Cycle {cycle})")
        print(f"{'=' * 100}")
        print("Reading agent code for analysis...")
        
        # Read current agent code
        agent_file = project_root / "backend" / "agents" / "unified_agent_interface.py"
        # Build optional memory context block
        memory_block = self._build_memory_block()
        phase_memory_block = self._phase_memory_block("analysis", f"cycle_{cycle}")

        analysis_prompt = f"""🔬 DEEP AGENT SELF-ANALYSIS (Cycle {cycle}){memory_block}{phase_memory_block}

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

        state_signature = self._file_state_signature(ANALYSIS_TARGET_FILES)
        cache_signature = self._cache_signature("analysis", state_signature)
        if self.memory_manager:
            cached_analysis = await self.memory_manager.get_cached_analysis(cache_signature, phase="analysis")
            if cached_analysis:
                print("♻️ Analysis cache hit — reusing prior DeepSeek output.")
                return {
                    "success": True,
                    "content": cached_analysis.get("content", ""),
                    "channel": cached_analysis.get("channel", "cache"),
                    "latency_ms": cached_analysis.get("latency_ms", 0.0),
                    "cache_hit": True,
                    "source": cached_analysis.get("source", "memory_cache"),
                }

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="analyze",
            prompt=analysis_prompt,
            code=None,  # No code in prompt - use file_access instead
            context={
                "use_file_access": True,
                "complex_task": True,
                "self_improvement_analysis": True,
                "timeout_override": TIMEOUT_COMPLEX,
            },
        )

        print(f"📤 Sending to DeepSeek (timeout: {TIMEOUT_COMPLEX}s)...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Success: {result.success} | Channel: {result.channel} | Latency: {result.latency_ms:.0f}ms")
        
        if result.success:
            print(f"📄 Analysis (first 500 chars):\n{result.content[:500]}...\n")
            if self.memory_manager:
                try:
                    created_at = datetime.now(timezone.utc).isoformat()
                    payload = {
                        "phase": "analysis",
                        "content": result.content,
                        "files": ANALYSIS_TARGET_FILES,
                        "cycle": cycle,
                        "channel": result.channel.value,
                        "latency_ms": result.latency_ms,
                        "created_at": created_at,
                        "source": "deepseek",
                    }
                    metadata = {
                        "phase": "analysis",
                        "files": ANALYSIS_TARGET_FILES,
                        "tags": self.memory_manager.generate_tags(result.content, "analysis"),
                        "summary": result.content.strip()[:240],
                        "cycle": cycle,
                        "created_at": created_at,
                    }
                    await self.memory_manager.remember_cache_hit(
                        cache_signature,
                        phase="analysis",
                        payload=payload,
                        metadata=metadata,
                    )
                except Exception as exc:
                    print(f"⚠️ Failed to persist analysis cache entry: {exc}")
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

        # Build optional memory context block
        memory_block = self._build_memory_block()
        phase_memory_block = self._phase_memory_block("research", phase1.get("content", ""))

        research_prompt = f"""🔍 AUTONOMOUS AGENT BEST PRACTICES RESEARCH{memory_block}{phase_memory_block}

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
                "timeout_override": TIMEOUT_STANDARD,
            },
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

        # Build optional memory context block
        memory_block = self._build_memory_block()
        combined_context = "\n".join([
            phase1.get("content", ""),
            phase2.get("content", ""),
        ])
        phase_memory_block = self._phase_memory_block("proposal", combined_context)

        proposal_intro = """💡 CONCRETE IMPROVEMENT PROPOSAL

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

        sections: list[Tuple[str, str]] = []
        if memory_block:
            sections.append(("Memory Context", memory_block))
        if phase_memory_block:
            sections.append(("Phase Memory", phase_memory_block))
        sections.append(("Self-Analysis Results", phase1.get("content", "N/A")))
        sections.append(("Best Practices Research", phase2.get("content", "N/A")))

        try:
            package = self.prompt_manager.build_package(
                cycle=cycle,
                phase="proposal",
                intro=proposal_intro,
                sections=sections,
                layer="proposal_context",
            )
        except PromptOverflowError as exc:
            print(f"❌ Proposal context overflow: {exc}")
            return {"success": False, "error": str(exc), "overflow": True}

        cache_signature = self._cache_signature(
            "proposal",
            phase1.get("content", ""),
            phase2.get("content", ""),
        )
        if self.memory_manager:
            cached_proposal = await self.memory_manager.get_cached_analysis(cache_signature, phase="proposal")
            if cached_proposal:
                print("♻️ Proposal cache hit — reusing prior DeepSeek plan.")
                return {
                    "success": True,
                    "content": cached_proposal.get("content", ""),
                    "channel": cached_proposal.get("channel", "cache"),
                    "latency_ms": cached_proposal.get("latency_ms", 0.0),
                    "cache_hit": True,
                    "source": cached_proposal.get("source", "memory_cache"),
                }

        manifest_dict = package.manifest.to_dict()

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="review",
            prompt=package.prompt,
            code=package.code_blob,
            context={
                "use_file_access": True,
                "complex_task": True,
                "timeout_override": TIMEOUT_COMPLEX,
                "segment_manifest": manifest_dict,
            },
        )
        
        print(f"📤 Sending to DeepSeek (timeout: {TIMEOUT_COMPLEX}s)...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Success: {result.success} | Channel: {result.channel} | Latency: {result.latency_ms:.0f}ms")
        
        if result.success:
            print(f"📄 Proposal (first 800 chars):\n{result.content[:800]}...\n")
            if self.memory_manager:
                try:
                    created_at = datetime.now(timezone.utc).isoformat()
                    payload = {
                        "phase": "proposal",
                        "content": result.content,
                        "files": PROPOSAL_TARGET_FILES,
                        "cycle": cycle,
                        "channel": result.channel.value,
                        "latency_ms": result.latency_ms,
                        "created_at": created_at,
                        "source": "deepseek",
                    }
                    metadata = {
                        "phase": "proposal",
                        "files": PROPOSAL_TARGET_FILES,
                        "tags": self.memory_manager.generate_tags(result.content, "proposal"),
                        "summary": result.content.strip()[:240],
                        "cycle": cycle,
                        "created_at": created_at,
                    }
                    await self.memory_manager.remember_cache_hit(
                        cache_signature,
                        phase="proposal",
                        payload=payload,
                        metadata=metadata,
                    )
                except Exception as exc:
                    print(f"⚠️ Failed to persist proposal cache entry: {exc}")
            return {
                "success": True,
                "content": result.content,
                "channel": result.channel.value,
                "latency_ms": result.latency_ms,
                "segment_manifest": manifest_dict,
            }
        else:
            print(f"❌ Proposal failed: {result.error}")
            return {"success": False, "error": result.error}
    
    async def phase4_perplexity_review(
        self, cycle: int, phase3: Dict, consensus_data: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Phase 4: Perplexity reviews proposal and builds consensus"""
        from backend.agents.models import AgentRequest, AgentType
        
        print(f"\n{'=' * 100}")
        print(f"🔍 PHASE 4: Perplexity Safety Review & Consensus (Cycle {cycle})")
        print(f"{'=' * 100}")
        
        if not phase3.get("success"):
            print("⚠️ No proposal to review")
            return {"success": False, "skipped": True, "approved": False}

        consensus_excerpt = self._consensus_context_excerpt(consensus_data)
        phase_memory_block = self._phase_memory_block("review", phase3.get("content", ""))
        memory_block = self._build_memory_block()
        prior_manifest_block = self._manifest_context_block(phase3.get("segment_manifest"))

        review_intro = f"""🛡️ SAFETY REVIEW & CONSENSUS BUILDING — Cycle {cycle}

Your role: act as the autonomous safety officer validating DeepSeek's implementation plan.
Synthesize prior memory, proposal details, and consensus signals, then deliver an evidence-backed verdict.
"""

        review_tasks = """REVIEW TASKS:
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
   - APPROVE: Yes, implement now (score >= 99%)
   - REVISE: Good idea, needs changes (score 50-98%)
   - REJECT: Not safe or needed (score < 50%)

Provide THOROUGH analysis. Consensus score must be justified with evidence.

OUTPUT FORMAT (STRICT):
```json
{
  "decision": "approve|revise|reject",
  "confidence": 0.0 - 1.0,
  "risks": ["..."],
  "required_actions": ["..."],
  "tests": ["pytest -k ..."],
  "segment_hashes_processed": ["<segment_id>"]
}
```
Only emit the JSON block plus a short narrative. Do not truncate or omit any
segment listed in the manifest."""

        review_sections: list[Tuple[str, str]] = []
        if memory_block:
            review_sections.append(("Strategic Memory", memory_block))
        if phase_memory_block:
            review_sections.append(("Phase Memory", phase_memory_block))
        review_sections.append(("Prior Proposal Manifest", prior_manifest_block))
        review_sections.append(("DeepSeek Proposal", phase3.get("content", "")))
        review_sections.append(("Consensus Transcript", consensus_excerpt))
        review_sections.append(("Safety Checklist", review_tasks))

        try:
            review_package = self.prompt_manager.build_package(
                cycle=cycle,
                phase="review",
                intro=review_intro,
                sections=review_sections,
                layer="review_context",
            )
        except PromptOverflowError as exc:
            print(f"❌ Review context overflow: {exc}")
            return {"success": False, "error": str(exc), "approved": False}

        review_manifest = review_package.manifest.to_dict()

        request = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="review",
            prompt=review_package.prompt,
            code=review_package.code_blob,
            context={
                "complex_task": True,
                "timeout_override": TIMEOUT_STANDARD,
                "segment_manifest": review_manifest,
                "proposal_manifest": phase3.get("segment_manifest"),
            }
        )
        
        print(f"📤 Sending to Perplexity (timeout: {TIMEOUT_STANDARD}s)...")
        result = await self.agent.send_request(request)
        
        print(f"✅ Success: {result.success} | Channel: {result.channel} | Latency: {result.latency_ms:.0f}ms")
        
        if result.success:
            print(f"📄 Review (first 500 chars):\n{result.content[:500]}...\n")
            
            # Parse consensus score (simple heuristic)
            content_lower = result.content.lower()
            consensus_score = self._extract_confidence_from_text(result.content) or 0.0
            approved = (
                "approve" in content_lower
                and "reject" not in content_lower
                and consensus_score >= CONVERGENCE_THRESHOLD
            )
            
            print(f"📊 Consensus Score: {consensus_score:.2%} | Approved: {approved}")
            
            return {
                "success": True,
                "content": result.content,
                "consensus_score": consensus_score,
                "approved": approved,
                "channel": result.channel.value,
                "latency_ms": result.latency_ms,
                "consensus_excerpt": consensus_excerpt,
                "segment_manifest": review_manifest,
            }
        else:
            print(f"❌ Review failed: {result.error}")
            return {"success": False, "error": result.error, "approved": False}
    
    async def phase5_deepseek_implement(self, cycle: int, phase3: Dict, phase4: Dict) -> Dict[str, Any]:
        """Phase 5: DeepSeek implements approved changes with backups.

        When MCP is unavailable or degraded we fall back to the new
        :class:`FileDirectEditor`, which expects a strict FILE/FUNCTION/
        REPLACE/WITH schema. If MCP is healthy we keep the legacy
        marker/diff workflow for backwards compatibility.
        """

        from backend.agents.models import AgentRequest, AgentType

        print(f"\n{'=' * 100}")
        print(f"⚙️ PHASE 5: DeepSeek Implementation (Cycle {cycle})")
        print(f"{'=' * 100}")

        agent_file = project_root / "backend" / "agents" / "unified_agent_interface.py"

        implementation_prompt = f"""🔧 IMPLEMENTATION EXECUTION

Approved Proposal:
{phase3['content']}

Perplexity Review:
{phase4['content'][:1000]}

Consensus Score: {phase4.get('combined_consensus_score', phase4.get('consensus_score', 0)):.2%} ✅ APPROVED

TASK: Implement the approved changes NOW.

RESPONSE FORMAT (STRICT):
PATCH 1:
FILE: relative/path/to/file.py
FUNCTION: package.module:FunctionName  # REQUIRED (exactly one function)
REPLACE:
```python
<existing code>
```
WITH:
```python
<new code>
```
SUMMARY: short description
TESTS: pytest -k optional_filter

Return one or more PATCH blocks following this schema.

CRITICAL REQUIREMENTS:
- Preserve existing functionality
- Add inline comments for new logic
- Follow project style
- Provide ready-to-run code (no TODOs)
- Each patch must target a single function and include the full function definition (signature + body)
- Always specify explicit repo-relative file paths
- Prefer targeted pytest commands in TESTS for quick regression coverage
"""

        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="fix",
            prompt=implementation_prompt,
            code=None,
            context={
                "use_file_access": True,
                "complex_task": True,
                "timeout_override": TIMEOUT_COMPLEX,
            },
        )

        print(f"📤 Sending to DeepSeek (timeout: {TIMEOUT_COMPLEX}s)...")
        result = await self.agent.send_request(request)

        print(f"✅ Success: {result.success} | Channel: {result.channel} | Latency: {result.latency_ms:.0f}ms")

        if not result.success:
            print(f"❌ Implementation failed: {result.error}")
            return {"success": False, "error": result.error}

        print(f"📄 Implementation response (first 800 chars):\n{result.content[:800]}...\n")

        strategy_decision = await self.file_ops_controller.determine_strategy(
            getattr(self.agent, "mcp_available", False)
        )
        print(
            f"🧭 File operation strategy: {strategy_decision.strategy.value} ({strategy_decision.reason})"
        )

        health_snapshot = self._capture_health_snapshot()
        direct_outcome = self.phase5_direct_editor.execute(
            cycle=cycle,
            raw_text=result.content,
            strategy=strategy_decision.strategy.value,
            health_snapshot=health_snapshot,
        )

        if direct_outcome.instructions:
            quick_tests_payload = direct_outcome.quick_test_payload()
            validation_summary = {
                "passed": direct_outcome.success,
                "details": direct_outcome.validation_details(),
            }

            for res in direct_outcome.patch_results:
                self.files_modified.append(
                    {
                        "file": str(res.instruction.file_path),
                        "backup": str(res.backup_path) if res.backup_path else None,
                        "changes": res.instruction.new_code,
                        "cycle": cycle,
                        "auto_applied": res.success,
                        "validation": {
                            "passed": res.validation_passed,
                            "error": res.validation_error,
                        },
                        "quick_tests": quick_tests_payload,
                    }
                )

            response_payload = {
                "success": direct_outcome.success,
                "content": result.content,
                "files_touched": direct_outcome.files_touched,
                "backups": direct_outcome.backups,
                "backup_file": direct_outcome.backups[0] if direct_outcome.backups else None,
                "target_file": direct_outcome.files_touched[0] if direct_outcome.files_touched else None,
                "channel": result.channel.value,
                "latency_ms": result.latency_ms,
                "validation": validation_summary,
                "strategy": strategy_decision.strategy.value,
                "quick_tests": quick_tests_payload,
                "auto_applied": direct_outcome.success,
                "rolled_back": direct_outcome.rolled_back,
            }
            if not direct_outcome.success:
                response_payload["error"] = direct_outcome.error or "direct_editor_failed"
            return response_payload

        if direct_outcome.parse_error:
            print(f"⚠️ Patch parsing failed in direct editor: {direct_outcome.parse_error}")
        else:
            print("⚠️ Direct editor produced no runnable instructions; using legacy marker/diff safety net.")

        # Legacy patching path -------------------------------------------------
        print("🔒 Creating fallback backup before legacy patch application...")
        backup_file = agent_file.with_suffix(
            f".py.backup.cycle{cycle}.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        shutil.copy2(agent_file, backup_file)
        pre_metadata = capture_file_metadata(agent_file)
        pre_hash = compute_file_checksum(agent_file)
        print(f"✅ Backup created: {backup_file.name}")

        code_blocks = extract_code_blocks(result.content)
        python_blocks = [text for lang, text in code_blocks if lang == "python"]
        diff_blocks = [text for lang, text in code_blocks if lang == "diff"]

        if not code_blocks:
            print("⚠️ No python/diff code blocks found in implementation response. Keeping safety mode.")
            self.memory_manager.record_event(
                "implementation",
                {
                    "cycle": cycle,
                    "status": "skipped_no_code",
                    "file": str(agent_file),
                    "backup": str(backup_file),
                    "summary": "DeepSeek returned no patch payload",
                },
            )
            self.files_modified.append(
                {
                    "file": str(agent_file),
                    "backup": str(backup_file),
                    "changes": result.content,
                    "cycle": cycle,
                    "auto_applied": False,
                }
            )
            return {
                "success": False,
                "content": result.content,
                "backup_file": str(backup_file),
                "target_file": str(agent_file),
                "auto_applied": False,
                "files_touched": [],
                "channel": result.channel.value,
                "latency_ms": result.latency_ms,
                "validation": {"passed": False, "error": "no_patch_payload"},
                "strategy": strategy_decision.strategy.value,
            }

        try:
            original_text = agent_file.read_text(encoding="utf-8")
        except Exception as e:  # pragma: no cover - catastrophic IO
            print(f"❌ Failed to read target file for implementation: {e}")
            return {"success": False, "error": str(e)}

        modified_text = original_text
        patch_applied = False

        for block in python_blocks:
            modified_text, applied = apply_marker_patches(modified_text, block)
            patch_applied = patch_applied or applied

        for diff_block in diff_blocks:
            modified_text, applied = apply_unified_diff(modified_text, diff_block)
            patch_applied = patch_applied or applied

        if not patch_applied:
            fallback_source = python_blocks[0] if python_blocks else code_blocks[0][1]
            new_block = (
                f"\n\n# === AUTONOMOUS_AGENT_APPLIED_CHANGE (cycle {cycle}) ===\n"
                + fallback_source
                + "\n"
            )
            modified_text = original_text + new_block
            print("⚠️ No structured patches applied; used append-at-end fallback.")
        else:
            print("✅ Applied structured patches to unified_agent_interface.py.")

        try:
            agent_file.write_text(modified_text, encoding="utf-8")
        except Exception as e:  # pragma: no cover - catastrophic IO
            print(f"❌ Failed to write modified target file: {e}")
            try:
                shutil.copy2(backup_file, agent_file)
                print("🔁 Rolled back target file from backup after write failure.")
            except Exception as re_err:
                print(f"❌ Rollback from backup failed: {re_err}")
            return {"success": False, "error": str(e)}

        validation_passed, validation_error = validate_python_file(agent_file)
        validation_summary = {
            "passed": validation_passed,
            "error": validation_error,
        }

        post_metadata = capture_file_metadata(agent_file)
        post_hash = compute_file_checksum(agent_file)
        files_touched = [str(agent_file)]
        health_snapshot = self._capture_health_snapshot()

        event_payload = {
            "cycle": cycle,
            "strategy": strategy_decision.strategy.value,
            "file": str(agent_file),
            "backup": str(backup_file),
            "pre_hash": pre_hash,
            "post_hash": post_hash,
            "pre_meta": pre_metadata,
            "post_meta": post_metadata,
            "validation": validation_summary,
            "summary": "patch_applied" if patch_applied else "appended_snippet",
            "health": health_snapshot,
        }

        if not validation_passed:
            print("❌ Validation failed; restoring from backup.")
            shutil.copy2(backup_file, agent_file)
            event_payload["summary"] = "validation_failed"
            self.memory_manager.record_event("implementation", event_payload)
            return {
                "success": False,
                "content": result.content,
                "backup_file": str(backup_file),
                "target_file": str(agent_file),
                "auto_applied": False,
                "files_touched": files_touched,
                "channel": result.channel.value,
                "latency_ms": result.latency_ms,
                "validation": validation_summary,
                "rolled_back": True,
                "strategy": strategy_decision.strategy.value,
            }

        self.memory_manager.record_event("implementation", event_payload)

        self.files_modified.append(
            {
                "file": str(agent_file),
                "backup": str(backup_file),
                "changes": result.content,
                "cycle": cycle,
                "auto_applied": True,
                "validation": validation_summary,
            }
        )

        print("✅ Auto-applied implementation patches to unified_agent_interface.py with validation.")

        return {
            "success": True,
            "content": result.content,
            "backup_file": str(backup_file),
            "target_file": str(agent_file),
            "auto_applied": True,
            "files_touched": files_touched,
            "channel": result.channel.value,
            "latency_ms": result.latency_ms,
            "validation": validation_summary,
            "pre_hash": pre_hash,
            "post_hash": post_hash,
            "strategy": strategy_decision.strategy.value,
        }

    async def phase6_cross_validation(self, cycle: int, phase5: Dict) -> Dict[str, Any]:
        """Phase 6: Both agents validate the implementation.

        New behaviour:
        - If DeepSeek or Perplexity reports CRITICAL syntax errors or an UNSAFE verdict,
          automatically restore the implementation target file from the Phase 5 backup.
        - Return a rich payload describing validation outcome and whether rollback occurred.
        """

        from backend.agents.models import AgentRequest, AgentType

        print(f"\n{'=' * 100}")
        print(f"✅ PHASE 6: Cross-Validation (Cycle {cycle})")
        print(f"{'=' * 100}")

        if not phase5.get("success"):
            print("⚠️ No implementation to validate")
            return {"success": False, "validated": False}

        backup_file = phase5.get("backup_file")
        target_file = phase5.get("target_file")

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

        communicator = get_communicator()
        validation_result = await communicator.validate_implementation(
            implementation_content=phase5.get("content", ""),
            validation_prompt=validation_prompt,
            backup_file=backup_file,
            target_file=target_file,
            cycle=cycle,
            timeout_seconds=TIMEOUT_STANDARD,
        )

        ds_summary = validation_result.get("deepseek_validation", {})
        pp_summary = validation_result.get("perplexity_validation", {})

        print("\n📊 Validation Results:")
        print(
            f"   DeepSeek: {'✅ ' if ds_summary.get('verdict') == 'VALIDATED' else '❌ '}"
            f"{ds_summary.get('verdict', 'UNKNOWN')} | Critical: {'YES' if ds_summary.get('critical_issues') else 'NO'}"
        )
        print(
            f"   Perplexity: {'✅ ' if pp_summary.get('verdict') == 'VALIDATED' else '❌ '}"
            f"{pp_summary.get('verdict', 'UNKNOWN')} | Critical: {'YES' if pp_summary.get('critical_issues') else 'NO'}"
        )
        print(
            f"   Consensus: {'✅ BOTH AGREE' if validation_result.get('validated') else '⚠️ DISAGREEMENT'}"
        )

        if validation_result.get("rolled_back"):
            print("🔁 Implementation rolled back to backup due to validation failure.")
            if self.memory_manager and phase5.get("files_touched"):
                try:
                    self.memory_manager.invalidate_cache_for_files(
                        phase5.get("files_touched", []),
                        reason="validation_rollback",
                        source="phase6_validation",
                        cycle=cycle,
                    )
                except Exception as exc:
                    self.memory_manager.record_event(
                        "analysis_cache_invalidation_error",
                        {
                            "cycle": cycle,
                            "error": str(exc),
                            "files": phase5.get("files_touched", []),
                            "source": "phase6_validation",
                        },
                    )

        return validation_result

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
            "consensus_history": self.consensus_history,
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
