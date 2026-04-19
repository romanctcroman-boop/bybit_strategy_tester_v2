"""
Graph Parser — connection normalization utilities.

Handles the 5+ connection schemas that the frontend, AI Builder,
and tests can produce.  All are converted to a flat canonical dict:

    {"source_id": str, "target_id": str, "source_port": str, "target_port": str}

Used by StrategyBuilderAdapter.__init__ via normalize_connections().
"""

from __future__ import annotations

from typing import Any


def parse_source_id(conn: dict[str, Any]) -> str:
    """Extract source block ID from any known connection format."""
    if "source" in conn and isinstance(conn["source"], dict):
        return str(conn["source"].get("blockId", ""))
    if "source" in conn and isinstance(conn["source"], str):
        return conn["source"]
    if "source_id" in conn:
        return str(conn["source_id"])
    if "source_block" in conn:
        return str(conn["source_block"])
    return str(conn.get("from", ""))


def parse_target_id(conn: dict[str, Any]) -> str:
    """Extract target block ID from any known connection format."""
    if "target" in conn and isinstance(conn["target"], dict):
        return str(conn["target"].get("blockId", ""))
    if "target" in conn and isinstance(conn["target"], str):
        return conn["target"]
    if "target_id" in conn:
        return str(conn["target_id"])
    if "target_block" in conn:
        return str(conn["target_block"])
    return str(conn.get("to", ""))


def parse_source_port(conn: dict[str, Any]) -> str:
    """Extract source port from any known connection format."""
    if "source" in conn and isinstance(conn["source"], dict):
        # Bug #6 fix: use "" not "value" so missing portId doesn't silently
        # match a real port named "value" and lose the signal.
        return str(conn["source"].get("portId", ""))
    if "source_port" in conn:
        return str(conn["source_port"])
    if "source_output" in conn:
        return str(conn["source_output"])
    if "sourcePort" in conn:
        return str(conn["sourcePort"])
    return str(conn.get("fromPort", ""))


def parse_target_port(conn: dict[str, Any]) -> str:
    """Extract target port from any known connection format."""
    if "target" in conn and isinstance(conn["target"], dict):
        # Bug #6 fix: use "" not "value" so missing portId doesn't silently
        # match a real port named "value" and lose the signal.
        return str(conn["target"].get("portId", ""))
    if "target_port" in conn:
        return str(conn["target_port"])
    if "target_input" in conn:
        return str(conn["target_input"])
    if "targetPort" in conn:
        return str(conn["targetPort"])
    return str(conn.get("toPort", ""))


def normalize_connections(raw_connections: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize a list of connections to canonical format.

    Supports 5+ connection schemas (old nested, AI Build, frontend camelCase,
    etc.) and converts each to a flat dict with 4 string keys:
    ``source_id``, ``target_id``, ``source_port``, ``target_port``.

    Args:
        raw_connections: List of connection dicts in any supported format.

    Returns:
        List of normalized connection dicts.
    """
    return [
        {
            "source_id": parse_source_id(conn),
            "target_id": parse_target_id(conn),
            "source_port": parse_source_port(conn),
            "target_port": parse_target_port(conn),
        }
        for conn in raw_connections
    ]
