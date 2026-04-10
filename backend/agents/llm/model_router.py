"""
Model Router — maps task types to Claude model tiers.

Haiku:  fast/cheap  — validation, parsing, formatting, memory ops
Sonnet: main tier   — strategy generation, analysis, refinement (iter 1-2)
Opus:   escalation  — refinement iter 3, novel market conditions, confidence < 0.4
"""

from __future__ import annotations


class ClaudeModel:
    HAIKU = "claude-haiku-4-5-20251001"  # $0.25/$1.25 per 1M
    SONNET = "claude-sonnet-4-6"  # $3/$15 per 1M
    OPUS = "claude-opus-4-6"  # $15/$75 per 1M


class TaskType:
    # Haiku tier
    FORMAT_VALIDATION = "format_validation"
    MEMORY_RECALL = "memory_recall"
    MEMORY_UPDATE = "memory_update"
    REGIME_LABEL = "regime_label"
    REPORT = "report"
    SYNTHESIS_CRITIC = "synthesis_critic"  # quick JSON synthesis

    # Sonnet tier (default for strategy work)
    STRATEGY_GENERATION = "strategy_generation"
    BACKTEST_ANALYSIS = "backtest_analysis"
    REFINEMENT = "refinement"
    REFLECTION = "reflection"
    ANALYSIS = "analysis"

    # Opus tier (escalation only)
    REFINEMENT_ESCALATED = "refinement_escalated"  # iter 3 of refine loop
    STRATEGY_ESCALATED = "strategy_escalated"  # novel/unknown regime
    UNKNOWN = "unknown"


_TASK_MODEL_MAP: dict[str, str] = {
    # Haiku
    TaskType.FORMAT_VALIDATION: ClaudeModel.HAIKU,
    TaskType.MEMORY_RECALL: ClaudeModel.HAIKU,
    TaskType.MEMORY_UPDATE: ClaudeModel.HAIKU,
    TaskType.REGIME_LABEL: ClaudeModel.HAIKU,
    TaskType.REPORT: ClaudeModel.HAIKU,
    TaskType.SYNTHESIS_CRITIC: ClaudeModel.HAIKU,
    # Sonnet
    TaskType.STRATEGY_GENERATION: ClaudeModel.SONNET,
    TaskType.BACKTEST_ANALYSIS: ClaudeModel.SONNET,
    TaskType.REFINEMENT: ClaudeModel.SONNET,
    TaskType.REFLECTION: ClaudeModel.SONNET,
    TaskType.ANALYSIS: ClaudeModel.SONNET,
    # Opus
    TaskType.REFINEMENT_ESCALATED: ClaudeModel.OPUS,
    TaskType.STRATEGY_ESCALATED: ClaudeModel.OPUS,
    TaskType.UNKNOWN: ClaudeModel.SONNET,  # safe default
}


class ModelRouter:
    """Select Claude model tier based on task type."""

    @staticmethod
    def get_model(task: str) -> str:
        """Return Claude model ID for the given task type. Defaults to Sonnet."""
        return _TASK_MODEL_MAP.get(task, ClaudeModel.SONNET)

    @staticmethod
    def escalate(task: str) -> str:
        """Return next tier up. Haiku->Sonnet, Sonnet->Opus, Opus stays."""
        model = ModelRouter.get_model(task)
        if model == ClaudeModel.HAIKU:
            return ClaudeModel.SONNET
        if model == ClaudeModel.SONNET:
            return ClaudeModel.OPUS
        return ClaudeModel.OPUS


__all__ = ["ClaudeModel", "ModelRouter", "TaskType"]
