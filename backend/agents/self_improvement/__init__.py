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

from backend.agents.self_improvement.rlhf_module import (
    RLHFModule,
    FeedbackSample,
    PreferenceType,
)
from backend.agents.self_improvement.self_reflection import (
    SelfReflectionEngine,
    ReflectionResult,
)
from backend.agents.self_improvement.performance_evaluator import (
    PerformanceEvaluator,
    PerformanceMetrics,
)

__all__ = [
    "RLHFModule",
    "FeedbackSample",
    "PreferenceType",
    "SelfReflectionEngine",
    "ReflectionResult",
    "PerformanceEvaluator",
    "PerformanceMetrics",
]
