"""
Self-Improvement Engine for AI Agents

This package provides autonomous self-improvement capabilities:
- RLHF/RLAIF Module: Learning from preferences
- Self-Reflection: Metacognitive analysis
- Performance Evaluation: Continuous quality monitoring
- Meta-Learning: Learning to learn

Based on 2025 research:
- "Agents That Learn to Self-Improve" (Nakajima, 2025)
- "Reinforcement Learning from AI Feedback" (Anthropic, 2024)
- "Self-Refine: Iterative Refinement with Self-Feedback" (2023)
"""

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

__all__ = [
    "FeedbackSample",
    "PerformanceEvaluator",
    "PerformanceMetrics",
    "PreferenceType",
    "RLHFModule",
    "ReflectionResult",
    "SelfReflectionEngine",
]
