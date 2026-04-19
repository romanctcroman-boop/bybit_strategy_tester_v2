"""Human-in-the-loop & reflection nodes.

Canonical home for three pipeline nodes that do not participate in strategy
synthesis — they pause the pipeline for human approval or persist end-of-run
metadata:

* :class:`HITLCheckNode`           — optional human approval gate
                                     (**physical implementation**, ADR-010 Stage 2).
* :class:`PostRunReflectionNode`   — self-critique at end of pipeline (re-export).
* :class:`MemoryUpdateNode`        — persists lessons to long-term store (re-export).

ADR-010 Stage 2 migration note
------------------------------
``HITLCheckNode`` is the first class physically moved out of the monolithic
``trading_strategy_graph`` module (2026-04-18).  It was chosen as proof-of-
concept because it has zero cross-class dependencies and does not touch any
module-level globals in the monolith.

The other two classes remain re-exported from the monolith for now.  Follow-up
PRs migrate them one by one using the same pattern:

1. Read the class source from ``trading_strategy_graph.py``.
2. Copy it verbatim into this file, rewriting imports as needed.
3. Replace the class definition in the monolith with a re-export::

       from backend.agents.nodes.control import HITLCheckNode  # noqa: F401

4. Run ``pytest tests/backend/agents`` to prove zero regressions.
"""

from __future__ import annotations

from loguru import logger

from backend.agents.langgraph_orchestrator import AgentNode, AgentState

# ---------------------------------------------------------------------------
# Physical implementation: HITLCheckNode (migrated 2026-04-18, ADR-010 Stage 2)
# ---------------------------------------------------------------------------


class HITLCheckNode(AgentNode):
    """
    P2-3: Human-in-the-loop checkpoint before memory is updated (optional).

    When enabled, the node inspects ``state.context["hitl_approved"]``:
    - If ``True``  → pipeline continues normally (human approved)
    - If ``False`` or missing → sets ``state.context["hitl_pending"] = True``
      and ``state.context["hitl_payload"]`` with the strategy summary for
      review, then returns early.  ``run_strategy_pipeline()`` callers can
      detect this and pause/resume by re-calling with
      ``hitl_approved=True`` in context.

    The node is wired between ``ml_validation`` and ``memory_update`` when
    ``build_trading_strategy_graph(hitl_enabled=True)`` is called.
    """

    def __init__(self) -> None:
        super().__init__(
            name="hitl_check",
            description="HITL: pause pipeline for human review before memory update",
            timeout=5.0,
        )

    async def execute(self, state: AgentState) -> AgentState:
        approved: bool = bool(state.context.get("hitl_approved", False))

        if approved:
            logger.info("✅ [HITL] Human approved — continuing to memory_update")
            state.context.pop("hitl_pending", None)
            return state

        # Build a compact summary for the human reviewer
        best = state.get_result("select_best") or {}
        bt = state.get_result("backtest") or {}
        bt_metrics = bt.get("metrics", {}) or {}  # Bug C1 fix: metrics nested under "metrics"
        wf = state.get_result("wf_validation") or {}

        payload = {
            "strategy_name": (best.get("strategy", {}) or {}).get("strategy_name", "unknown"),
            "backtest_summary": {
                "trades": bt_metrics.get("total_trades", 0),
                "sharpe": round(bt_metrics.get("sharpe_ratio", 0.0), 3),
                "max_dd": round(bt_metrics.get("max_drawdown", 0.0), 2),
                "net_profit": round(bt_metrics.get("net_profit", 0.0), 2),
            },
            "wf_passed": wf.get("wf_passed", None),
            "regime": state.context.get("regime_classification", {}).get("regime", "unknown"),
            "message": (
                "Pipeline paused for human review. Set state.context['hitl_approved'] = True and re-run to continue."
            ),
        }

        state.context["hitl_pending"] = True
        state.context["hitl_payload"] = payload
        logger.info(
            f"⏸️ [HITL] Pipeline paused — strategy='{payload['strategy_name']}' "
            f"sharpe={payload['backtest_summary']['sharpe']}. "
            f"Set hitl_approved=True to continue."
        )
        state.set_result(self.name, payload)
        return state


# ---------------------------------------------------------------------------
# Re-exports (physical migration deferred to future PRs)
# ---------------------------------------------------------------------------

from backend.agents.trading_strategy_graph import (
    MemoryUpdateNode,
    PostRunReflectionNode,
)

__all__ = [
    "HITLCheckNode",
    "MemoryUpdateNode",
    "PostRunReflectionNode",
]
