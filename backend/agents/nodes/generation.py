"""Strategy synthesis nodes — turn ideas into concrete graph-based strategies.

* :class:`GenerateStrategiesNode` — LLM call that emits N strategy drafts.
* :class:`ParseResponsesNode`     — validates + normalises LLM output.
* :class:`ConsensusNode`          — debate/vote across multiple drafts.
* :class:`BuildGraphNode`         — materialises the winning draft into a
                                    Strategy Builder graph (block library).
"""

from backend.agents.trading_strategy_graph import (
    BuildGraphNode,
    ConsensusNode,
    GenerateStrategiesNode,
    ParseResponsesNode,
)

__all__ = [
    "BuildGraphNode",
    "ConsensusNode",
    "GenerateStrategiesNode",
    "ParseResponsesNode",
]
