"""
Autonomous Workflow Engine for AI Agents.

Provides multi-step, self-coordinating pipelines:
- AutonomousBacktestingWorkflow: fetch → evolve → backtest → report → learn
- BuilderWorkflow: create → add blocks → connect → validate → backtest → evaluate
- WorkflowStatus: track pipeline progress
- WorkflowResult: collect full pipeline output

Added 2026-02-12 per Agent Ecosystem Audit — Additional Directions.
Updated 2026-02-14 — Builder Workflow for Strategy Builder integration.
"""

from backend.agents.workflows.autonomous_backtesting import (
    AutonomousBacktestingWorkflow,
    PipelineStage,
    WorkflowConfig,
    WorkflowResult,
    WorkflowStatus,
)
from backend.agents.workflows.builder_workflow import (
    BuilderStage,
    BuilderWorkflow,
    BuilderWorkflowConfig,
    BuilderWorkflowResult,
)

__all__ = [
    "AutonomousBacktestingWorkflow",
    "BuilderStage",
    "BuilderWorkflow",
    "BuilderWorkflowConfig",
    "BuilderWorkflowResult",
    "PipelineStage",
    "WorkflowConfig",
    "WorkflowResult",
    "WorkflowStatus",
]
