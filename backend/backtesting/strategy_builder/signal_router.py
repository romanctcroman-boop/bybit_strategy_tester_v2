"""
Signal routing constants for the Strategy Builder.

Provides the canonical port-alias maps that the adapter uses to resolve
connections when the frontend port name doesn't match the backend output key.

Port alias lookup order in the adapter:
1. Exact match (source_port == key in source_outputs)
2. PORT_ALIASES[source_port] for general data ports (value, output, etc.)
3. SIGNAL_PORT_ALIASES[source_port] for signal-bearing ports (long, short, etc.)

See CLAUDE.md §6 for the full port alias documentation.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# General data port aliases
# ---------------------------------------------------------------------------

PORT_ALIASES: dict[str, list[str]] = {
    "output": ["value", "close"],
    "value": ["output", "close"],
    "result": ["signal", "output"],
    "signal": ["result", "output"],
    "input": ["value", "close"],
    # MACD histogram port: frontend used 'hist', backend returns 'histogram'
    "hist": ["histogram"],
    "histogram": ["hist"],
}

# ---------------------------------------------------------------------------
# Signal-bearing port aliases (long/short entry/exit)
# ---------------------------------------------------------------------------

SIGNAL_PORT_ALIASES: dict[str, list[str]] = {
    "long": ["bullish", "entry_long", "signal"],
    "short": ["bearish", "entry_short", "signal"],
    "bullish": ["long", "entry_long", "signal"],
    "bearish": ["short", "entry_short", "signal"],
    "output": ["value", "result", "signal"],
    "value": ["output", "result", "signal"],
    "result": ["signal", "output", "value"],
    "signal": ["result", "output", "value"],
    # Close-condition blocks expose "config" as their single output port on the frontend.
    # Resolve it to the actual signal keys present in the cached output.
    "config": ["exit_long", "exit_short", "exit", "signal"],
}
