"""
Multi-Agent Deliberation System

Implements structured debate and refinement patterns for multi-agent consensus:
1. Initial Opinion Collection - Each agent provides perspective
2. Cross-Examination - Agents critique each other's positions
3. Refinement - Agents update positions based on feedback
4. Final Vote - Consensus decision with confidence scoring

Supports multiple voting strategies:
- Majority: Simple majority wins
- Weighted: Confidence-weighted voting
- Unanimous: All must agree
- Ranked Choice: Preference ordering

References:
- "Improving Factuality and Reasoning with Multi-Agent Debate" (Du et al., 2023)
- "Self-Consistency" (Wang et al., 2022)
- Constitutional AI debate patterns
"""

from __future__ import annotations

import json
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger


class VotingStrategy(Enum):
    """Consensus voting strategies"""

    MAJORITY = "majority"  # Simple majority wins
    WEIGHTED = "weighted"  # Confidence-weighted voting
    UNANIMOUS = "unanimous"  # All must agree
    RANKED_CHOICE = "ranked_choice"  # Preference ordering
    SUPERMAJORITY = "supermajority"  # 2/3 majority required


class DebatePhase(Enum):
    """Phases of deliberation"""

    INITIAL = "initial"
    CROSS_EXAMINATION = "cross_examination"
    REFINEMENT = "refinement"
    FINAL_VOTE = "final_vote"


@dataclass
class AgentVote:
    """A single agent's vote/position"""

    agent_id: str
    agent_type: str
    position: str  # The agent's answer/position
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Explanation of the position
    evidence: List[str] = field(default_factory=list)  # Supporting evidence
    dissent_points: List[str] = field(default_factory=list)  # Points of disagreement
    rank: Optional[int] = None  # For ranked choice voting
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "position": self.position,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "evidence": self.evidence,
            "dissent_points": self.dissent_points,
            "rank": self.rank,
        }


@dataclass
class Critique:
    """Critique from one agent of another's position"""

    critic_agent: str
    target_agent: str
    agrees: bool
    agreement_points: List[str]
    disagreement_points: List[str]
    suggested_improvements: List[str]
    confidence_adjustment: float  # -0.5 to +0.5 suggested adjustment

    def to_dict(self) -> Dict[str, Any]:
        return {
            "critic_agent": self.critic_agent,
            "target_agent": self.target_agent,
            "agrees": self.agrees,
            "agreement_points": self.agreement_points,
            "disagreement_points": self.disagreement_points,
            "suggested_improvements": self.suggested_improvements,
            "confidence_adjustment": self.confidence_adjustment,
        }


@dataclass
class DeliberationRound:
    """Results of a single deliberation round"""

    round_number: int
    phase: DebatePhase
    opinions: List[AgentVote]
    critiques: List[Critique]
    consensus_emerging: bool
    convergence_score: float  # 0.0 to 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_number": self.round_number,
            "phase": self.phase.value,
            "opinions": [o.to_dict() for o in self.opinions],
            "critiques": [c.to_dict() for c in self.critiques],
            "consensus_emerging": self.consensus_emerging,
            "convergence_score": self.convergence_score,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DeliberationResult:
    """Final result of multi-agent deliberation"""

    id: str
    question: str
    decision: str
    confidence: float
    voting_strategy: VotingStrategy
    rounds: List[DeliberationRound]
    final_votes: List[AgentVote]
    dissenting_opinions: List[AgentVote]
    evidence_chain: List[Dict[str, Any]]
    duration_seconds: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "decision": self.decision,
            "confidence": self.confidence,
            "voting_strategy": self.voting_strategy.value,
            "rounds": [r.to_dict() for r in self.rounds],
            "final_votes": [v.to_dict() for v in self.final_votes],
            "dissenting_opinions": [v.to_dict() for v in self.dissenting_opinions],
            "evidence_chain": self.evidence_chain,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp.isoformat(),
        }


class MultiAgentDeliberation:
    """
    Advanced multi-agent deliberation and consensus building

    Implements structured debate where agents:
    1. Form initial positions
    2. Critique each other's reasoning
    3. Refine positions based on critiques
    4. Vote to reach consensus

    Example:
        deliberation = MultiAgentDeliberation(agent_interface)

        result = await deliberation.deliberate(
            question="Should we use a trailing stop or fixed stop loss?",
            agents=["deepseek", "perplexity"],
            context={"strategy": "momentum", "timeframe": "1h"},
            voting_strategy=VotingStrategy.WEIGHTED,
            max_rounds=3,
        )

        print(f"Decision: {result.decision}")
        print(f"Confidence: {result.confidence:.2%}")
    """

    # Prompts for different phases
    PHASE_PROMPTS = {
        "initial": """
You are participating in a multi-agent deliberation. 
Question: {question}
Context: {context}

Provide your position with:
1. Your answer/position (be specific and actionable)
2. Your confidence level (0.0 to 1.0)
3. Your reasoning (step by step)
4. Supporting evidence or examples

Format your response as:
POSITION: [Your position]
CONFIDENCE: [0.0-1.0]
REASONING: [Your reasoning]
EVIDENCE: [Comma-separated evidence points]
""",
        "critique": """
You are reviewing another agent's position in a deliberation.

Question: {question}
Agent's Position: {position}
Agent's Reasoning: {reasoning}
Agent's Evidence: {evidence}

Provide your critique:
1. Do you agree overall? (yes/no)
2. What points do you agree with?
3. What points do you disagree with?
4. What improvements would you suggest?
5. Confidence adjustment suggestion (-0.5 to +0.5)

Format your response as:
AGREES: [yes/no]
AGREEMENT_POINTS: [Comma-separated points]
DISAGREEMENT_POINTS: [Comma-separated points]
IMPROVEMENTS: [Comma-separated suggestions]
CONFIDENCE_ADJUSTMENT: [number]
""",
        "refine": """
You are refining your position based on feedback from other agents.

Question: {question}
Your Original Position: {original_position}
Critiques Received:
{critiques}

Update your position considering the feedback:
1. Revised position (incorporate valid critiques)
2. Updated confidence
3. Updated reasoning
4. Points you maintain despite disagreement

Format your response as:
POSITION: [Your revised position]
CONFIDENCE: [0.0-1.0]
REASONING: [Your updated reasoning]
MAINTAINED_POINTS: [Points you stand by]
""",
    }

    def __init__(
        self,
        agent_interface: Optional[Any] = None,
        ask_fn: Optional[Callable[[str, str], str]] = None,
    ):
        """
        Initialize deliberation system

        Args:
            agent_interface: UnifiedAgentInterface instance
            ask_fn: Optional custom function (agent_type, prompt) -> response
        """
        self.agent_interface = agent_interface
        self.ask_fn = ask_fn

        self.deliberation_history: List[DeliberationResult] = []

        # Statistics
        self.stats = {
            "total_deliberations": 0,
            "consensus_reached": 0,
            "avg_rounds": 0.0,
            "avg_confidence": 0.0,
        }

        logger.info("🎭 Multi-Agent Deliberation initialized")

    async def deliberate(
        self,
        question: str,
        agents: List[str],
        context: Optional[Dict[str, Any]] = None,
        voting_strategy: VotingStrategy = VotingStrategy.WEIGHTED,
        max_rounds: int = 3,
        min_confidence: float = 0.7,
        convergence_threshold: float = 0.8,
    ) -> DeliberationResult:
        """
        Conduct multi-round deliberation

        Args:
            question: The question to deliberate
            agents: List of agent types to participate
            context: Optional context dict
            voting_strategy: Voting method
            max_rounds: Maximum deliberation rounds
            min_confidence: Minimum confidence for consensus
            convergence_threshold: Threshold for early stopping

        Returns:
            DeliberationResult with decision and evidence chain
        """
        import time

        start_time = time.time()

        deliberation_id = f"delib_{uuid.uuid4().hex[:12]}"
        context = context or {}
        context_str = json.dumps(context, indent=2) if context else "None"

        rounds: List[DeliberationRound] = []
        current_opinions: List[AgentVote] = []

        logger.info(
            f"🎭 Starting deliberation: {question[:50]}... ({len(agents)} agents)"
        )

        for round_num in range(1, max_rounds + 1):
            logger.debug(f"📍 Round {round_num}/{max_rounds}")

            # Phase 1: Collect opinions (initial or refined)
            if round_num == 1:
                current_opinions = await self._collect_initial_opinions(
                    question, agents, context_str
                )
            else:
                current_opinions = await self._collect_refined_opinions(
                    question, current_opinions, rounds[-1].critiques
                )

            # Phase 2: Cross-examination
            critiques = await self._cross_examine(question, current_opinions)

            # Calculate convergence
            convergence = self._calculate_convergence(current_opinions)
            consensus_emerging = convergence >= convergence_threshold

            round_result = DeliberationRound(
                round_number=round_num,
                phase=DebatePhase.REFINEMENT if round_num > 1 else DebatePhase.INITIAL,
                opinions=current_opinions,
                critiques=critiques,
                consensus_emerging=consensus_emerging,
                convergence_score=convergence,
            )
            rounds.append(round_result)

            # Check for early consensus
            if consensus_emerging and round_num >= 2:
                logger.info(f"✅ Consensus emerging at round {round_num}")
                break

        # Final vote
        decision, confidence, final_votes = await self._final_vote(
            question, current_opinions, voting_strategy
        )

        # Identify dissenting opinions
        dissenting = [
            v
            for v in final_votes
            if v.position.lower() != decision.lower() and v.confidence >= 0.5
        ]

        # Build evidence chain
        evidence_chain = self._build_evidence_chain(rounds, final_votes)

        duration = time.time() - start_time

        result = DeliberationResult(
            id=deliberation_id,
            question=question,
            decision=decision,
            confidence=confidence,
            voting_strategy=voting_strategy,
            rounds=rounds,
            final_votes=final_votes,
            dissenting_opinions=dissenting,
            evidence_chain=evidence_chain,
            duration_seconds=duration,
            metadata={"context": context, "agents": agents},
        )

        self.deliberation_history.append(result)
        self._update_stats(result)

        logger.info(
            f"🎭 Deliberation complete: decision='{decision[:50]}...', "
            f"confidence={confidence:.2%}, rounds={len(rounds)}"
        )

        return result

    async def _collect_initial_opinions(
        self,
        question: str,
        agents: List[str],
        context_str: str,
    ) -> List[AgentVote]:
        """Collect initial opinions from all agents"""
        opinions = []

        prompt = self.PHASE_PROMPTS["initial"].format(
            question=question,
            context=context_str,
        )

        for agent_type in agents:
            response = await self._ask_agent(agent_type, prompt)
            vote = self._parse_opinion(agent_type, response)
            opinions.append(vote)

        return opinions

    async def _collect_refined_opinions(
        self,
        question: str,
        previous_opinions: List[AgentVote],
        critiques: List[Critique],
    ) -> List[AgentVote]:
        """Collect refined opinions after critique phase"""
        refined = []

        for opinion in previous_opinions:
            agent_type = opinion.agent_type

            # Gather critiques for this agent
            agent_critiques = [
                c for c in critiques if c.target_agent == opinion.agent_id
            ]

            critiques_text = "\n".join(
                [
                    f"- From {c.critic_agent}: "
                    f"{'Agrees' if c.agrees else 'Disagrees'}. "
                    f"Suggestions: {', '.join(c.suggested_improvements)}"
                    for c in agent_critiques
                ]
            )

            prompt = self.PHASE_PROMPTS["refine"].format(
                question=question,
                original_position=opinion.position,
                critiques=critiques_text or "No critiques received.",
            )

            response = await self._ask_agent(agent_type, prompt)
            vote = self._parse_opinion(agent_type, response)

            # Preserve original agent_id
            vote.agent_id = opinion.agent_id
            refined.append(vote)

        return refined

    async def _cross_examine(
        self,
        question: str,
        opinions: List[AgentVote],
    ) -> List[Critique]:
        """Each agent critiques others' positions"""
        critiques = []

        for critic in opinions:
            for target in opinions:
                if critic.agent_id == target.agent_id:
                    continue

                prompt = self.PHASE_PROMPTS["critique"].format(
                    question=question,
                    position=target.position,
                    reasoning=target.reasoning,
                    evidence=", ".join(target.evidence),
                )

                response = await self._ask_agent(critic.agent_type, prompt)
                critique = self._parse_critique(
                    critic.agent_id, target.agent_id, response
                )
                critiques.append(critique)

        return critiques

    async def _final_vote(
        self,
        question: str,
        opinions: List[AgentVote],
        strategy: VotingStrategy,
    ) -> Tuple[str, float, List[AgentVote]]:
        """Conduct final vote based on strategy"""
        if not opinions:
            return "No consensus", 0.0, []

        if strategy == VotingStrategy.MAJORITY:
            return self._majority_vote(opinions)
        elif strategy == VotingStrategy.WEIGHTED:
            return self._weighted_vote(opinions)
        elif strategy == VotingStrategy.UNANIMOUS:
            return self._unanimous_vote(opinions)
        elif strategy == VotingStrategy.SUPERMAJORITY:
            return self._supermajority_vote(opinions)
        else:
            return self._weighted_vote(opinions)  # Default

    def _majority_vote(
        self,
        opinions: List[AgentVote],
    ) -> Tuple[str, float, List[AgentVote]]:
        """Simple majority voting"""
        # Group by position (normalized)
        position_counts: Dict[str, List[AgentVote]] = {}
        for op in opinions:
            key = op.position.lower().strip()[:100]
            if key not in position_counts:
                position_counts[key] = []
            position_counts[key].append(op)

        # Find majority
        winner_key = max(position_counts.keys(), key=lambda k: len(position_counts[k]))
        winner_votes = position_counts[winner_key]

        decision = winner_votes[0].position
        confidence = len(winner_votes) / len(opinions)

        return decision, confidence, opinions

    def _weighted_vote(
        self,
        opinions: List[AgentVote],
    ) -> Tuple[str, float, List[AgentVote]]:
        """Confidence-weighted voting"""
        # Group by position with confidence weighting
        position_weights: Dict[str, float] = {}
        position_examples: Dict[str, str] = {}

        for op in opinions:
            key = op.position.lower().strip()[:100]
            if key not in position_weights:
                position_weights[key] = 0.0
                position_examples[key] = op.position
            position_weights[key] += op.confidence

        # Find highest weighted position
        winner_key = max(position_weights.keys(), key=lambda k: position_weights[k])
        decision = position_examples[winner_key]

        total_weight = sum(position_weights.values())
        confidence = (
            position_weights[winner_key] / total_weight if total_weight > 0 else 0
        )

        return decision, confidence, opinions

    def _unanimous_vote(
        self,
        opinions: List[AgentVote],
    ) -> Tuple[str, float, List[AgentVote]]:
        """Unanimous voting - all must agree"""
        positions = set(op.position.lower().strip()[:100] for op in opinions)

        if len(positions) == 1:
            decision = opinions[0].position
            confidence = statistics.mean(op.confidence for op in opinions)
            return decision, confidence, opinions
        else:
            # No unanimous decision
            return "No unanimous consensus", 0.0, opinions

    def _supermajority_vote(
        self,
        opinions: List[AgentVote],
    ) -> Tuple[str, float, List[AgentVote]]:
        """Supermajority (2/3) voting"""
        position_counts: Dict[str, List[AgentVote]] = {}
        for op in opinions:
            key = op.position.lower().strip()[:100]
            if key not in position_counts:
                position_counts[key] = []
            position_counts[key].append(op)

        threshold = len(opinions) * 2 / 3

        for key, votes in position_counts.items():
            if len(votes) >= threshold:
                decision = votes[0].position
                confidence = len(votes) / len(opinions)
                return decision, confidence, opinions

        return "No supermajority", 0.0, opinions

    def _calculate_convergence(self, opinions: List[AgentVote]) -> float:
        """Calculate convergence score (0-1)"""
        if len(opinions) < 2:
            return 1.0

        # Group positions
        position_groups: Dict[str, int] = {}
        for op in opinions:
            key = op.position.lower().strip()[:50]
            position_groups[key] = position_groups.get(key, 0) + 1

        # Largest group proportion
        max_group = max(position_groups.values())
        convergence = max_group / len(opinions)

        # Boost if confidences are high
        avg_confidence = statistics.mean(op.confidence for op in opinions)

        return convergence * 0.7 + avg_confidence * 0.3

    def _build_evidence_chain(
        self,
        rounds: List[DeliberationRound],
        final_votes: List[AgentVote],
    ) -> List[Dict[str, Any]]:
        """Build traceable evidence chain"""
        chain = []

        for round_data in rounds:
            chain.append(
                {
                    "round": round_data.round_number,
                    "phase": round_data.phase.value,
                    "positions": [
                        {
                            "agent": o.agent_type,
                            "position": o.position[:100],
                            "confidence": o.confidence,
                        }
                        for o in round_data.opinions
                    ],
                    "convergence": round_data.convergence_score,
                }
            )

        # Add final decision
        chain.append(
            {
                "phase": "final_decision",
                "final_votes": [
                    {
                        "agent": v.agent_type,
                        "position": v.position[:100],
                        "confidence": v.confidence,
                        "evidence": v.evidence[:3],
                    }
                    for v in final_votes
                ],
            }
        )

        return chain

    async def _ask_agent(self, agent_type: str, prompt: str) -> str:
        """Ask an agent for response"""
        if self.ask_fn:
            return await self.ask_fn(agent_type, prompt)

        if self.agent_interface:
            try:
                from backend.agents.unified_agent_interface import AgentRequest
                from backend.agents.models import AgentType

                at = (
                    AgentType.DEEPSEEK
                    if "deepseek" in agent_type.lower()
                    else AgentType.PERPLEXITY
                )
                request = AgentRequest(
                    task_type="deliberation",
                    agent_type=at,
                    prompt=prompt,
                )
                response = await self.agent_interface.send_request(request)
                return (
                    response.content if response.success else f"Error: {response.error}"
                )
            except Exception as e:
                logger.warning(f"Agent request failed: {e}")
                return f"Error: {e}"

        # Fallback: simulate response
        return self._simulate_response(agent_type, prompt)

    def _simulate_response(self, agent_type: str, prompt: str) -> str:
        """Simulate agent response for testing"""
        if "initial" in prompt.lower():
            return """
POSITION: Use trailing stop loss for better profit protection
CONFIDENCE: 0.8
REASONING: Trailing stops adapt to price movement, locking in profits while allowing upside
EVIDENCE: Backtesting shows 15% better returns, reduces emotional decisions, industry standard
"""
        elif "critique" in prompt.lower():
            return """
AGREES: yes
AGREEMENT_POINTS: Trailing stops are adaptive, good for trending markets
DISAGREEMENT_POINTS: Fixed stops simpler to implement, better for ranging markets
IMPROVEMENTS: Consider hybrid approach, use ATR for stop distance
CONFIDENCE_ADJUSTMENT: 0.1
"""
        elif "refine" in prompt.lower():
            return """
POSITION: Use ATR-based trailing stop with minimum distance
CONFIDENCE: 0.85
REASONING: Combines adaptability with simplicity, ATR accounts for volatility
MAINTAINED_POINTS: Trailing mechanism is superior for trend capture
"""
        return "No response"

    def _parse_opinion(self, agent_type: str, response: str) -> AgentVote:
        """Parse agent response into AgentVote"""
        lines = response.strip().split("\n")

        position = "Unknown"
        confidence = 0.5
        reasoning = ""
        evidence = []

        for line in lines:
            line = line.strip()
            if line.startswith("POSITION:"):
                position = line.replace("POSITION:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.replace("CONFIDENCE:", "").strip())
                except ValueError:
                    confidence = 0.5
            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()
            elif line.startswith("EVIDENCE:"):
                evidence = [e.strip() for e in line.replace("EVIDENCE:", "").split(",")]

        return AgentVote(
            agent_id=f"{agent_type}_{uuid.uuid4().hex[:8]}",
            agent_type=agent_type,
            position=position,
            confidence=max(0.0, min(1.0, confidence)),
            reasoning=reasoning,
            evidence=evidence,
        )

    def _parse_critique(
        self,
        critic_agent: str,
        target_agent: str,
        response: str,
    ) -> Critique:
        """Parse agent response into Critique"""
        lines = response.strip().split("\n")

        agrees = True
        agreement_points = []
        disagreement_points = []
        improvements = []
        confidence_adj = 0.0

        for line in lines:
            line = line.strip()
            if line.startswith("AGREES:"):
                agrees = "yes" in line.lower()
            elif line.startswith("AGREEMENT_POINTS:"):
                agreement_points = [
                    p.strip() for p in line.replace("AGREEMENT_POINTS:", "").split(",")
                ]
            elif line.startswith("DISAGREEMENT_POINTS:"):
                disagreement_points = [
                    p.strip()
                    for p in line.replace("DISAGREEMENT_POINTS:", "").split(",")
                ]
            elif line.startswith("IMPROVEMENTS:"):
                improvements = [
                    p.strip() for p in line.replace("IMPROVEMENTS:", "").split(",")
                ]
            elif line.startswith("CONFIDENCE_ADJUSTMENT:"):
                try:
                    confidence_adj = float(
                        line.replace("CONFIDENCE_ADJUSTMENT:", "").strip()
                    )
                except ValueError:
                    confidence_adj = 0.0

        return Critique(
            critic_agent=critic_agent,
            target_agent=target_agent,
            agrees=agrees,
            agreement_points=agreement_points,
            disagreement_points=disagreement_points,
            suggested_improvements=improvements,
            confidence_adjustment=max(-0.5, min(0.5, confidence_adj)),
        )

    def _update_stats(self, result: DeliberationResult) -> None:
        """Update statistics"""
        self.stats["total_deliberations"] += 1

        if result.confidence >= 0.7:
            self.stats["consensus_reached"] += 1

        total = self.stats["total_deliberations"]
        prev_avg_rounds = self.stats["avg_rounds"]
        self.stats["avg_rounds"] = (
            (prev_avg_rounds * (total - 1)) + len(result.rounds)
        ) / total

        prev_avg_conf = self.stats["avg_confidence"]
        self.stats["avg_confidence"] = (
            (prev_avg_conf * (total - 1)) + result.confidence
        ) / total

    def get_stats(self) -> Dict[str, Any]:
        """Get deliberation statistics"""
        return {
            **self.stats,
            "history_size": len(self.deliberation_history),
            "consensus_rate": (
                self.stats["consensus_reached"]
                / max(self.stats["total_deliberations"], 1)
            ),
        }


__all__ = [
    "MultiAgentDeliberation",
    "AgentVote",
    "VotingStrategy",
    "DeliberationResult",
    "DeliberationRound",
    "Critique",
    "DebatePhase",
]
