"""Human-in-the-loop & reflection nodes.

* :class:`HITLCheckNode`           — optional human approval gate.
* :class:`PostRunReflectionNode`   — self-critique at end of pipeline.
* :class:`MemoryUpdateNode`        — persists lessons to the long-term store.
"""

from backend.agents.trading_strategy_graph import (
    HITLCheckNode,
    MemoryUpdateNode,
    PostRunReflectionNode,
)

__all__ = [
    "HITLCheckNode",
    "MemoryUpdateNode",
    "PostRunReflectionNode",
]
