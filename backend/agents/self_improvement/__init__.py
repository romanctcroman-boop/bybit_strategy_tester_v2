"""
Self-Improvement Engine for AI Agents

This package provides autonomous self-improvement capabilities:
- RLHF/RLAIF Module: Learning from preferences
- Self-Reflection: Metacognitive analysis (heuristic + LLM-backed)
- Performance Evaluation: Continuous quality monitoring
- Feedback Loop: Automatic backtest → analysis → prompt improvement
- Agent Tracking: Per-agent performance for dynamic consensus weights
- Meta-Learning: Learning to learn

Based on 2025 research:
- "Agents That Learn to Self-Improve" (Nakajima, 2025)
- "Reinforcement Learning from AI Feedback" (Anthropic, 2024)
- "Self-Refine: Iterative Refinement with Self-Feedback" (2023)
"""

from backend.agents.self_improvement.agent_tracker import (
    AgentPerformanceTracker,
    AgentProfile,
    AgentRecord,
)
from backend.agents.self_improvement.feedback_loop import (
    FeedbackEntry,
    FeedbackLoop,
    FeedbackLoopResult,
    PromptImprovementEngine,
)
from backend.agents.self_improvement.llm_reflection import (
    LLMReflectionProvider,
    LLMSelfReflectionEngine,
)
from backend.agents.self_improvement.performance_evaluator import (
    PerformanceEvaluator,
    PerformanceMetrics,
)
from backend.agents.self_improvement.rlhf_module import (
    FeedbackSample,
    PreferenceType,
    RLHFModule,
)
from backend.agents.self_improvement.self_reflection import (
    ReflectionResult,
    SelfReflectionEngine,
)
from backend.agents.self_improvement.strategy_evolution import (
    EvolutionResult,
    GenerationRecord,
    StrategyEvolution,
    compute_fitness,
)

__all__ = [
    "AgentPerformanceTracker",
    "AgentProfile",
    "AgentRecord",
    "EvolutionResult",
    "FeedbackEntry",
    "FeedbackLoop",
    "FeedbackLoopResult",
    "FeedbackSample",
    "GenerationRecord",
    "LLMReflectionProvider",
    "LLMSelfReflectionEngine",
    "PerformanceEvaluator",
    "PerformanceMetrics",
    "PreferenceType",
    "PromptImprovementEngine",
    "RLHFModule",
    "ReflectionResult",
    "SelfReflectionEngine",
    "StrategyEvolution",
    "compute_fitness",
]
