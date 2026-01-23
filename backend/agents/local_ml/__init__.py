"""
Local ML Model Integration

This package provides local ML model capabilities for autonomous operation:
- LocalReasonerEngine: Local LLM for offline reasoning
- RLIntegration: AI-guided reinforcement learning
- PredictionEngine: Ensemble prediction models

Enables the agent system to operate without external API dependencies.
"""

from backend.agents.local_ml.local_reasoner import (
    LocalReasonerEngine,
    ReasoningResult,
)
from backend.agents.local_ml.rl_integration import (
    RLAgentIntegration,
    AIGuidedTrainingConfig,
)
from backend.agents.local_ml.prediction_engine import (
    PredictionEngine,
    PredictionResult,
)

__all__ = [
    "LocalReasonerEngine",
    "ReasoningResult",
    "RLAgentIntegration",
    "AIGuidedTrainingConfig",
    "PredictionEngine",
    "PredictionResult",
]
