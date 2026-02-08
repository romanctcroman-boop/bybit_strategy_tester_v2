"""
Reasoning Trace Database Models
Models for storing reasoning chains, chain-of-thought steps, and strategy evolution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ThoughtType(str, Enum):
    """Types of reasoning steps"""

    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    ANALYSIS = "analysis"
    DECISION = "decision"
    CONCLUSION = "conclusion"


@dataclass
class ChainOfThought:
    """
    Represents a single step in a chain-of-thought reasoning process.

    Attributes:
        id: Unique identifier for this thought step
        step_number: Sequential step number in the chain
        thought_type: Type of thought (observation, hypothesis, etc.)
        content: Main content of the thought
        intermediate_conclusion: Interim conclusion at this step
        confidence_score: Confidence level (0-1)
        citations: References or sources
        created_at: Timestamp
    """

    id: str
    step_number: int
    thought_type: str
    content: str
    intermediate_conclusion: str | None = None
    confidence_score: float | None = None
    citations: dict | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "step_number": self.step_number,
            "thought_type": self.thought_type,
            "content": self.content,
            "intermediate_conclusion": self.intermediate_conclusion,
            "confidence_score": self.confidence_score,
            "citations": self.citations,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class StrategyEvolution:
    """
    Represents the evolution of a strategy over time.

    Attributes:
        id: Unique identifier
        strategy_id: Strategy identifier
        version: Version number
        changes: Description of changes
        performance_delta: Change in performance metrics
        reasoning: Reasoning behind the evolution
        created_at: Timestamp
    """

    id: str
    strategy_id: str
    version: int
    changes: str
    performance_delta: dict | None = None
    reasoning: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "version": self.version,
            "changes": self.changes,
            "performance_delta": self.performance_delta,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class ReasoningTrace:
    """
    Represents a complete reasoning trace including chain-of-thought steps.

    Attributes:
        id: Unique identifier
        agent_type: Type of agent (e.g., 'optimizer', 'tournament')
        task_type: Type of task performed
        input_prompt: Original input/prompt
        chain_of_thought: List of thought steps
        final_conclusion: Final conclusion reached
        processing_time: Time taken (seconds)
        metadata: Additional metadata
        created_at: Timestamp
    """

    id: str
    agent_type: str
    task_type: str
    input_prompt: str
    final_conclusion: str
    processing_time: float
    chain_of_thought: list = field(default_factory=list)
    strategy_evolution: StrategyEvolution | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "task_type": self.task_type,
            "input_prompt": self.input_prompt,
            "final_conclusion": self.final_conclusion,
            "processing_time": self.processing_time,
            "chain_of_thought": [
                step.to_dict() if hasattr(step, "to_dict") else step
                for step in self.chain_of_thought
            ],
            "strategy_evolution": (
                self.strategy_evolution.to_dict()
                if self.strategy_evolution
                and hasattr(self.strategy_evolution, "to_dict")
                else self.strategy_evolution
            ),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def add_thought_step(
        self,
        step_number: int,
        thought_type: str,
        content: str,
        intermediate_conclusion: str | None = None,
        confidence_score: float | None = None,
    ) -> ChainOfThought:
        """Add a thought step to the chain"""
        step = ChainOfThought(
            id=f"{self.id}_step_{step_number}",
            step_number=step_number,
            thought_type=thought_type,
            content=content,
            intermediate_conclusion=intermediate_conclusion,
            confidence_score=confidence_score,
        )
        self.chain_of_thought.append(step)
        return step
