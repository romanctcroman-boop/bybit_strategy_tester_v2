r"""
AI Agent Memory System Understanding Test v4 — Hierarchical Memory Mastery

Tests whether DeepSeek, Qwen, and Perplexity correctly understand
the 4-tier Hierarchical Memory system: types, operations, importance,
consolidation, forgetting, and trading-context usage patterns.

v2 tests (test_agent_node_understanding.py):
  ✅ RSI params (19 checks)
  ✅ MACD params (18 checks)
  ✅ Optimization ranges (71 checks)

v3 tests (test_agent_comprehensive.py):
  ✅ Strategy Flow (18 checks)
  ✅ Block Wiring (19 checks)
  ✅ Exit/Risk Management (32 checks)
  ✅ Filter Blocks (39 checks)

v4 tests (this file):
  🆕 Memory Types — 4 tiers, TTL, capacity, priority, use cases
  🆕 Memory Operations — store/recall/consolidate/forget workflows
  🆕 Memory Strategy — trading-context usage, importance guidelines

Usage:
    cd D:\bybit_strategy_tester_v2
    .venv\Scripts\python.exe scripts\test_agent_memory.py

    # Test only one agent:
    .venv\Scripts\python.exe scripts\test_agent_memory.py --agent deepseek

    # Test only one scenario:
    .venv\Scripts\python.exe scripts\test_agent_memory.py --node memory_types
    .venv\Scripts\python.exe scripts\test_agent_memory.py --node memory_operations
    .venv\Scripts\python.exe scripts\test_agent_memory.py --node memory_strategy
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.llm.base_client import LLMConfig, LLMMessage, LLMProvider, LLMResponse
from backend.agents.llm.clients.deepseek import DeepSeekClient
from backend.agents.llm.clients.perplexity import PerplexityClient
from backend.agents.llm.clients.qwen import QwenClient

# Use KeyManager for secure API key access
try:
    from backend.security.key_manager import KeyManager, get_key_manager

    _key_manager: KeyManager | None = get_key_manager()
except ImportError:
    _key_manager = None  # type: ignore[assignment]


def _get_api_key(key_name: str) -> str | None:
    """Get API key from KeyManager or environment."""
    if _key_manager:
        try:
            return _key_manager.get_decrypted_key(key_name)
        except Exception:
            pass
    return os.environ.get(key_name)


# ═══════════════════════════════════════════════════════════════════
# Data class
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ValidationResult:
    """Result of a single agent x node test."""

    agent: str
    node: str
    passed: bool
    score: float
    checks: dict[str, bool] = field(default_factory=dict)
    raw_response: str = ""
    parsed_json: dict | None = None
    error: str = ""
    latency_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# System prompts (memory-aware)
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPTS = {
    "deepseek": (
        "You are a quantitative trading analyst with deep knowledge of AI agent memory systems. "
        "You understand hierarchical memory architectures inspired by human cognition: "
        "working memory (short-term), episodic memory (experiences), semantic memory (knowledge), "
        "and procedural memory (skills). "
        "You know how to store, recall, consolidate, and forget memories strategically "
        "for optimal trading analysis across sessions. "
        "Always respond with valid JSON only — no markdown, no extra text."
    ),
    "qwen": (
        "You are a technical analysis expert who uses a hierarchical memory system "
        "to accumulate trading knowledge across sessions. "
        "You understand memory tiers (working/episodic/semantic/procedural), "
        "their TTLs, capacities, importance scoring (0.0-1.0), "
        "consolidation (promoting important memories), and forgetting (TTL + decay). "
        "You know the correct API endpoints and operations for each memory function. "
        "Always respond with valid JSON only — no markdown, no extra text."
    ),
    "perplexity": (
        "You are a market research analyst who leverages hierarchical memory "
        "to build cumulative market knowledge. "
        "You know the 4 memory tiers, their properties (TTL, capacity, priority), "
        "the 6 core operations (store, recall, get, delete, consolidate, forget), "
        "and how to apply them in trading contexts: storing backtest results, "
        "recalling past patterns, consolidating discoveries, and managing importance. "
        "Always respond with valid JSON only — no markdown, no extra text."
    ),
}


# ═══════════════════════════════════════════════════════════════════
# TEST 1: MEMORY TYPES — 4 tiers, TTL, capacity, priority
# ═══════════════════════════════════════════════════════════════════

MEMORY_TYPES_PROMPT = """
You are working with a Hierarchical Memory system for AI trading agents.
The system has EXACTLY 4 memory tiers inspired by human cognition.

=== THE 4 MEMORY TIERS ===

1. WORKING Memory
   - Purpose: Current task context, active conversation, temporary calculations
   - TTL: 5 minutes (shortest — like human working memory)
   - Max capacity: 10 items (very limited)
   - Priority: 1 (lowest — first to be evicted)
   - Example content: "User just asked to analyze BTCUSDT RSI strategy"

2. EPISODIC Memory
   - Purpose: Session experiences, events, specific results
   - TTL: 7 days
   - Max capacity: 1000 items
   - Priority: 2
   - Example content: "Backtest #42: BTCUSDT RSI strategy, Sharpe 1.8, PnL +12.5%"

3. SEMANTIC Memory
   - Purpose: Long-term knowledge, facts, learned rules
   - TTL: 365 days (1 year)
   - Max capacity: 10000 items
   - Priority: 3
   - Example content: "RSI above 70 = overbought, below 30 = oversold"

4. PROCEDURAL Memory
   - Purpose: Skills, patterns, reusable workflows
   - TTL: 10 years (effectively permanent)
   - Max capacity: 500 items
   - Priority: 4 (highest — last to be evicted)
   - Example content: "Mean-reversion strategy template: RSI + Bollinger, SL=1.5%, TP=3%"

=== KEY RULES ===
- Priority determines eviction order: lowest priority evicted first
- TTL determines automatic expiration
- Importance (0.0-1.0) affects retention and consolidation
- Consolidation promotes memories UP the hierarchy (working→episodic→semantic)
- Forgetting removes expired + decayed memories

=== YOUR TASK ===
Answer these questions about the memory system:

1. List ALL 4 memory tiers with their exact TTL, max capacity, and priority
2. Classify WHERE to store each of these items:
   a) "The user wants to analyze ETHUSDT" → which tier?
   b) "Backtest result: RSI(14) on BTCUSDT gave 15% return" → which tier?
   c) "RSI values above 70 indicate overbought conditions" → which tier?
   d) "Always validate with backtests before recommending strategies" → which tier?
3. Which tier has the SHORTEST TTL? Which has the LONGEST?
4. Which tier is evicted FIRST under memory pressure?
5. In what order does consolidation promote memories?

Return ONLY valid JSON:
{
  "tiers": {
    "working": {
      "ttl": "<duration>",
      "max_capacity": <int>,
      "priority": <int>,
      "purpose": "<1-sentence purpose>"
    },
    "episodic": {
      "ttl": "<duration>",
      "max_capacity": <int>,
      "priority": <int>,
      "purpose": "<1-sentence purpose>"
    },
    "semantic": {
      "ttl": "<duration>",
      "max_capacity": <int>,
      "priority": <int>,
      "purpose": "<1-sentence purpose>"
    },
    "procedural": {
      "ttl": "<duration>",
      "max_capacity": <int>,
      "priority": <int>,
      "purpose": "<1-sentence purpose>"
    }
  },
  "classification": {
    "user_wants_ethusdt": "<tier name: working/episodic/semantic/procedural>",
    "backtest_result": "<tier name>",
    "rsi_knowledge": "<tier name>",
    "validation_rule": "<tier name>"
  },
  "shortest_ttl_tier": "<tier name>",
  "longest_ttl_tier": "<tier name>",
  "first_evicted_tier": "<tier name>",
  "consolidation_order": ["<from>→<to>", "<from>→<to>"],
  "total_tiers": <int>,
  "reasoning": "Explain why the hierarchy mirrors human memory"
}
"""


# ═══════════════════════════════════════════════════════════════════
# TEST 2: MEMORY OPERATIONS — store/recall/consolidate/forget
# ═══════════════════════════════════════════════════════════════════

MEMORY_OPERATIONS_PROMPT = """
You are working with a Hierarchical Memory system that has 6 core operations.

=== MEMORY OPERATIONS ===

1. store(content, memory_type, importance=0.5, tags=[], metadata={})
   - Stores content in the specified tier
   - importance: float 0.0-1.0 (higher = more retained during consolidation/forgetting)
   - tags: list of strings for categorization and filtering
   - metadata: dict for extra structured data
   - Returns: MemoryItem with generated ID (format: {type}_{hash}_{timestamp})

2. recall(query, memory_type=None, top_k=5, min_importance=0.0, tags=[], use_semantic=True)
   - Searches memories by text relevance + optional semantic similarity
   - memory_type=None searches ALL tiers simultaneously
   - top_k: maximum number of results to return
   - min_importance: filter out memories below this importance
   - tags: filter by specific tags (AND logic)
   - Returns: list of MemoryItems sorted by relevance

3. get(item_id)
   - Retrieve a specific memory by its exact ID
   - Returns: MemoryItem or None

4. delete(item_id)
   - Remove a specific memory by ID
   - Returns: True (deleted) or False (not found)

5. consolidate()
   - Promotes important memories UP the hierarchy:
     * working → episodic: if importance >= 0.7
     * episodic → semantic: if 3+ items share tags AND avg importance >= 0.6
   - Like "sleep" — strengthens important memories
   - Should be called periodically (e.g., end of task)

6. forget()
   - Intelligent cleanup:
     * Removes expired items (past their tier's TTL)
     * Applies importance decay: 0.1% per hour since last access
     * Evicts items with importance < 0.1 AND access_count < 2
   - Runs automatically but can be triggered manually

=== IMPORTANCE GUIDELINES ===
- 0.9-1.0: Critical — profitable strategy params, key discoveries
- 0.7-0.8: High — user preferences, successful patterns
- 0.5-0.6: Normal — routine observations, standard results
- 0.3-0.4: Low — temporary context, intermediate calcs
- 0.1-0.2: Minimal — noise, superseded info

=== YOUR TASK ===
For each scenario below, specify the EXACT operation call with parameters:

Scenario A: After running multiple backtests, you have identified a GENERAL RULE:
RSI with wider bands (25/75) consistently outperforms standard bands (30/70)
across multiple configurations and periods on BTCUSDT 15m timeframe.
This is reusable KNOWLEDGE (a pattern/rule), not a single backtest result.
→ Which operation? What parameters (memory_type, importance, tags)?
HINT: Single backtest results are episodic experiences.
     Generalized rules/patterns derived from multiple observations belong in SEMANTIC memory.

Scenario B: You need to find all previous backtest results for ETHUSDT.
→ Which operation? What parameters?

Scenario C: After a long analysis session, you want to promote important
short-term memories to longer-term storage.
→ Which operation?

Scenario D: The system is running low on memory and needs cleanup.
→ Which operation?

Scenario E: You want to store the current user request temporarily.
→ Which operation? What parameters (memory_type, importance)?

Scenario F: You need to check if a specific memory item still exists.
→ Which operation?

Also answer:
- What is the consolidation threshold from working → episodic? (importance >= ?)
- What is the consolidation threshold from episodic → semantic? (items sharing tags >= ? AND avg importance >= ?)
- What importance decay rate does forget() apply? (% per hour)
- Below what importance + access_count are items evicted?

Return ONLY valid JSON:
{
  "scenario_a": {
    "operation": "<store/recall/get/delete/consolidate/forget>",
    "memory_type": "<working/episodic/semantic/procedural>",
    "importance": <float>,
    "tags": ["<tag1>", "<tag2>"],
    "reasoning": "Why this tier and importance?"
  },
  "scenario_b": {
    "operation": "<operation name>",
    "query": "<search query>",
    "memory_type": "<tier or null for all>",
    "tags": ["<tag>"],
    "reasoning": "Why this search approach?"
  },
  "scenario_c": {
    "operation": "<operation name>",
    "reasoning": "What does this operation do?"
  },
  "scenario_d": {
    "operation": "<operation name>",
    "reasoning": "What cleanup rules are applied?"
  },
  "scenario_e": {
    "operation": "<operation name>",
    "memory_type": "<tier>",
    "importance": <float>,
    "reasoning": "Why this tier?"
  },
  "scenario_f": {
    "operation": "<operation name>",
    "reasoning": "How does this differ from recall?"
  },
  "consolidation_working_to_episodic_threshold": <float>,
  "consolidation_episodic_to_semantic_min_items": <int>,
  "consolidation_episodic_to_semantic_avg_importance": <float>,
  "forget_decay_rate_per_hour": <float>,
  "forget_eviction_importance_below": <float>,
  "forget_eviction_access_count_below": <int>,
  "total_operations": <int>,
  "reasoning": "Explain the lifecycle of a memory from creation to deletion"
}
"""


# ═══════════════════════════════════════════════════════════════════
# TEST 3: MEMORY STRATEGY — trading context usage
# ═══════════════════════════════════════════════════════════════════

MEMORY_STRATEGY_PROMPT = """
You are an AI trading agent with a 4-tier Hierarchical Memory system.
You must demonstrate HOW to use memory in real trading workflows.

=== MEMORY TIERS (quick reference) ===
- WORKING:    5min TTL, 10 items max, priority 1 — current task
- EPISODIC:   7d TTL, 1000 items max, priority 2 — experiences
- SEMANTIC:   365d TTL, 10000 items max, priority 3 — knowledge
- PROCEDURAL: 10yr TTL, 500 items max, priority 4 — skills

=== OPERATIONS (quick reference) ===
- store(content, memory_type, importance, tags, metadata)
- recall(query, memory_type, top_k, min_importance, tags)
- consolidate() — promote working→episodic (imp≥0.7), episodic→semantic (3+ items, avg≥0.6)
- forget() — TTL expiry + decay 0.1%/hr + evict if imp<0.1 & access<2

=== IMPORTANCE SCALE ===
0.9-1.0 = Critical (profitable discoveries)
0.7-0.8 = High (user preferences, successful patterns)
0.5-0.6 = Normal (routine results)
0.3-0.4 = Low (temp context)
0.1-0.2 = Minimal (noise)

=== YOUR TASK ===
You are given a multi-step trading analysis task. For EACH step,
specify what memory operations you would perform.

TASK: "Optimize RSI strategy for BTCUSDT on 15m timeframe"

Step 1: TASK START
- What do you recall first? From which tier(s)?
- What do you store? In which tier? Importance?

Step 2: RUN FIRST BACKTEST (RSI period=14, levels 30/70)
- Result: PnL=+8%, Sharpe=1.2, Max DD=5%
- This is a COMPLETED backtest — a concrete event/experience with specific results.
- Backtest results are EVENTS that happened, not temporary calculations.
- What do you store? Which tier? Importance? Tags?
- HINT: Completed experiments with measured outcomes are experiences (EPISODIC),
  not temporary working context. Working memory is for in-progress calculations.

Step 3: RUN SECOND BACKTEST (RSI period=21, levels 25/75)
- Result: PnL=+15%, Sharpe=1.8, Max DD=3%
- Again, this is a COMPLETED experiment with concrete measured results.
- What do you store? Which tier? Importance? Tags?
- This result is BETTER than Step 2 — should its importance reflect that?

Step 4: DISCOVER A PATTERN
- You notice that RSI with wider bands (25/75 vs 30/70) consistently
  gives better risk-adjusted returns on BTCUSDT 15m
- What do you store? Which tier? Importance?
- Is this different from the individual backtest results?

Step 5: COMPLETE TASK
- What consolidation do you run?
- What final results do you store? Which tier?
- What would happen to Step 1 working memories after 5 minutes?

Also design a memory strategy for this scenario:
"A user asks you to analyze 5 different symbols with the same RSI strategy"
- How would you use memory across the 5 analyses?
- How would you identify cross-symbol patterns?
- What goes into each tier?

Return ONLY valid JSON:
{
  "step_1_task_start": {
    "recall_operations": [
      {
        "query": "<what to search>",
        "memory_type": "<tier or null>",
        "purpose": "Why recall this?"
      }
    ],
    "store_operations": [
      {
        "content_summary": "<what to store>",
        "memory_type": "<tier>",
        "importance": <float>,
        "tags": ["<tag>"]
      }
    ]
  },
  "step_2_first_backtest": {
    "store_operations": [
      {
        "content_summary": "<what to store>",
        "memory_type": "<tier>",
        "importance": <float>,
        "tags": ["<tag1>", "<tag2>"]
      }
    ]
  },
  "step_3_second_backtest": {
    "store_operations": [
      {
        "content_summary": "<what to store>",
        "memory_type": "<tier>",
        "importance": <float>,
        "tags": ["<tag1>", "<tag2>"]
      }
    ]
  },
  "step_4_pattern_discovery": {
    "store_operations": [
      {
        "content_summary": "<what to store>",
        "memory_type": "<tier>",
        "importance": <float>,
        "tags": ["<tag>"]
      }
    ],
    "tier_difference": "Why is this stored in a different tier than backtests?"
  },
  "step_5_completion": {
    "consolidation": "<what happens during consolidation>",
    "final_store": {
      "content_summary": "<final result>",
      "memory_type": "<tier>",
      "importance": <float>
    },
    "working_memory_fate": "What happens to Step 1 working memories?"
  },
  "multi_symbol_strategy": {
    "per_symbol_tier": "<which tier for individual results>",
    "cross_symbol_pattern_tier": "<which tier for discovered patterns>",
    "workflow_tier": "<which tier for the reusable analysis workflow>",
    "how_to_identify_patterns": "How do you find patterns across symbols?"
  },
  "reasoning": "Explain your overall memory strategy philosophy"
}
"""


# ═══════════════════════════════════════════════════════════════════
# JSON extraction
# ═══════════════════════════════════════════════════════════════════


def _extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try direct parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } balanced
    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[brace_start : i + 1])
                        if isinstance(data, dict):
                            return data
                    except json.JSONDecodeError:
                        pass
                    break

    return None


# ═══════════════════════════════════════════════════════════════════
# Validation helpers
# ═══════════════════════════════════════════════════════════════════


def _tier_match(value: str | None, expected: str) -> bool:
    """Check if a tier value matches expected (case-insensitive)."""
    if not value:
        return False
    return expected.lower() in str(value).lower()


def _ttl_match(value: str | None, expected_keywords: list[str]) -> bool:
    """Check if TTL string contains expected keywords."""
    if not value:
        return False
    v = str(value).lower()
    return any(kw in v for kw in expected_keywords)


def _importance_in_range(value, low: float, high: float) -> bool:
    """Check if importance value is within expected range."""
    if value is None:
        return False
    try:
        v = float(value)
        return low <= v <= high
    except (TypeError, ValueError):
        return False


# ═══════════════════════════════════════════════════════════════════
# MEMORY TYPES Validation
# ═══════════════════════════════════════════════════════════════════


def validate_memory_types_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate understanding of 4 memory tiers."""
    result = ValidationResult(
        agent=agent,
        node="memory_types",
        passed=False,
        score=0.0,
        raw_response=response,
        latency_ms=latency_ms,
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    checks: dict[str, bool] = {}

    tiers = parsed.get("tiers", {})

    # --- WORKING tier ---
    w = tiers.get("working", {})
    checks["01_working_ttl_5min"] = _ttl_match(w.get("ttl"), ["5 min", "5min", "300"])
    checks["02_working_capacity_10"] = w.get("max_capacity") == 10
    checks["03_working_priority_1"] = w.get("priority") == 1
    checks["04_working_has_purpose"] = isinstance(w.get("purpose"), str) and len(w.get("purpose", "")) > 5

    # --- EPISODIC tier ---
    e = tiers.get("episodic", {})
    checks["05_episodic_ttl_7d"] = _ttl_match(e.get("ttl"), ["7 day", "7d", "1 week", "week", "168"])
    checks["06_episodic_capacity_1000"] = e.get("max_capacity") == 1000
    checks["07_episodic_priority_2"] = e.get("priority") == 2
    checks["08_episodic_has_purpose"] = isinstance(e.get("purpose"), str) and len(e.get("purpose", "")) > 5

    # --- SEMANTIC tier ---
    s = tiers.get("semantic", {})
    checks["09_semantic_ttl_365d"] = _ttl_match(s.get("ttl"), ["365", "1 year", "year", "12 month"])
    checks["10_semantic_capacity_10000"] = s.get("max_capacity") == 10000
    checks["11_semantic_priority_3"] = s.get("priority") == 3
    checks["12_semantic_has_purpose"] = isinstance(s.get("purpose"), str) and len(s.get("purpose", "")) > 5

    # --- PROCEDURAL tier ---
    p = tiers.get("procedural", {})
    checks["13_procedural_ttl_10yr"] = _ttl_match(p.get("ttl"), ["10 year", "10yr", "permanent", "3650"])
    checks["14_procedural_capacity_500"] = p.get("max_capacity") == 500
    checks["15_procedural_priority_4"] = p.get("priority") == 4
    checks["16_procedural_has_purpose"] = isinstance(p.get("purpose"), str) and len(p.get("purpose", "")) > 5

    # --- Classification ---
    cl = parsed.get("classification", {})
    checks["17_classify_user_request_working"] = _tier_match(cl.get("user_wants_ethusdt"), "working")
    checks["18_classify_backtest_episodic"] = _tier_match(cl.get("backtest_result"), "episodic")
    checks["19_classify_rsi_knowledge_semantic"] = _tier_match(cl.get("rsi_knowledge"), "semantic")
    checks["20_classify_validation_rule_procedural"] = _tier_match(cl.get("validation_rule"), "procedural")

    # --- Meta questions ---
    checks["21_shortest_ttl_working"] = _tier_match(parsed.get("shortest_ttl_tier"), "working")
    checks["22_longest_ttl_procedural"] = _tier_match(parsed.get("longest_ttl_tier"), "procedural")
    checks["23_first_evicted_working"] = _tier_match(parsed.get("first_evicted_tier"), "working")

    # --- Consolidation order ---
    consol = parsed.get("consolidation_order", [])
    if isinstance(consol, list) and len(consol) >= 2:
        consol_str = " ".join(str(c).lower() for c in consol)
        checks["24_consolidation_working_to_episodic"] = "working" in consol_str and "episodic" in consol_str
        checks["25_consolidation_episodic_to_semantic"] = "episodic" in consol_str and "semantic" in consol_str
    else:
        checks["24_consolidation_working_to_episodic"] = False
        checks["25_consolidation_episodic_to_semantic"] = False

    # --- Total tiers ---
    checks["26_total_tiers_4"] = parsed.get("total_tiers") == 4

    # --- Reasoning ---
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["27_reasoning_mentions_hierarchy"] = any(
            w in r_lower for w in ["hierarch", "tier", "human", "memory", "cognit", "level"]
        )
    else:
        checks["27_reasoning_mentions_hierarchy"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.85

    return result


# ═══════════════════════════════════════════════════════════════════
# MEMORY OPERATIONS Validation
# ═══════════════════════════════════════════════════════════════════


def validate_memory_operations_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate understanding of 6 memory operations and thresholds."""
    result = ValidationResult(
        agent=agent,
        node="memory_operations",
        passed=False,
        score=0.0,
        raw_response=response,
        latency_ms=latency_ms,
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    checks: dict[str, bool] = {}

    # --- Scenario A: store RSI discovery in semantic memory ---
    sa = parsed.get("scenario_a", {})
    checks["01_sa_operation_store"] = str(sa.get("operation", "")).lower() == "store"
    checks["02_sa_tier_semantic"] = _tier_match(sa.get("memory_type"), "semantic")
    checks["03_sa_importance_high"] = _importance_in_range(sa.get("importance"), 0.7, 1.0)
    sa_tags = sa.get("tags", [])
    if isinstance(sa_tags, list):
        sa_tags_lower = [str(t).lower() for t in sa_tags]
        checks["04_sa_has_relevant_tags"] = any(
            kw in tag for tag in sa_tags_lower for kw in ["rsi", "btc", "indicator", "discovery", "pattern"]
        )
    else:
        checks["04_sa_has_relevant_tags"] = False

    # --- Scenario B: recall backtest results → recall ---
    sb = parsed.get("scenario_b", {})
    checks["05_sb_operation_recall"] = str(sb.get("operation", "")).lower() == "recall"
    sb_query = str(sb.get("query", "")).lower()
    checks["06_sb_query_mentions_eth"] = "eth" in sb_query or "backtest" in sb_query
    # memory_type should be episodic or null/None (search all)
    sb_type = sb.get("memory_type")
    checks["07_sb_tier_episodic_or_all"] = (
        sb_type is None
        or str(sb_type).lower() == "null"
        or str(sb_type).lower() == "none"
        or _tier_match(sb_type, "episodic")
    )

    # --- Scenario C: consolidate ---
    sc = parsed.get("scenario_c", {})
    checks["08_sc_operation_consolidate"] = str(sc.get("operation", "")).lower() == "consolidate"

    # --- Scenario D: forget ---
    sd = parsed.get("scenario_d", {})
    checks["09_sd_operation_forget"] = str(sd.get("operation", "")).lower() == "forget"
    sd_reasoning = str(sd.get("reasoning", "")).lower()
    checks["10_sd_mentions_cleanup_rules"] = any(
        w in sd_reasoning for w in ["ttl", "expire", "decay", "evict", "clean", "remove"]
    )

    # --- Scenario E: store current request in working ---
    se = parsed.get("scenario_e", {})
    checks["11_se_operation_store"] = str(se.get("operation", "")).lower() == "store"
    checks["12_se_tier_working"] = _tier_match(se.get("memory_type"), "working")
    checks["13_se_importance_low"] = _importance_in_range(se.get("importance"), 0.1, 0.5)

    # --- Scenario F: get by ID ---
    sf = parsed.get("scenario_f", {})
    checks["14_sf_operation_get"] = str(sf.get("operation", "")).lower() == "get"

    # --- Consolidation thresholds ---
    checks["15_consol_working_episodic_07"] = _importance_in_range(
        parsed.get("consolidation_working_to_episodic_threshold"), 0.7, 0.7
    )
    checks["16_consol_episodic_semantic_3_items"] = parsed.get("consolidation_episodic_to_semantic_min_items") == 3
    checks["17_consol_episodic_semantic_avg_06"] = _importance_in_range(
        parsed.get("consolidation_episodic_to_semantic_avg_importance"), 0.6, 0.6
    )

    # --- Forget thresholds ---
    forget_decay = parsed.get("forget_decay_rate_per_hour")
    # Accept 0.001 (0.1%) or 0.1 (if they interpret "0.1% per hour" as 0.1)
    checks["18_forget_decay_001"] = forget_decay == 0.001 or forget_decay == 0.1
    checks["19_forget_eviction_importance_01"] = _importance_in_range(
        parsed.get("forget_eviction_importance_below"), 0.1, 0.1
    )
    checks["20_forget_eviction_access_2"] = parsed.get("forget_eviction_access_count_below") == 2

    # --- Total operations ---
    checks["21_total_operations_6"] = parsed.get("total_operations") == 6

    # --- Reasoning ---
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["22_reasoning_lifecycle"] = any(
            w in r_lower for w in ["lifecycle", "creat", "store", "recall", "delet", "consol", "forget"]
        )
    else:
        checks["22_reasoning_lifecycle"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.85

    return result


# ═══════════════════════════════════════════════════════════════════
# MEMORY STRATEGY Validation
# ═══════════════════════════════════════════════════════════════════


def validate_memory_strategy_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate trading-context memory usage strategy."""
    result = ValidationResult(
        agent=agent,
        node="memory_strategy",
        passed=False,
        score=0.0,
        raw_response=response,
        latency_ms=latency_ms,
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    checks: dict[str, bool] = {}

    # ═══ Step 1: Task Start ═══
    s1 = parsed.get("step_1_task_start", {})

    # Should recall from semantic/procedural first
    recalls = s1.get("recall_operations", [])
    if isinstance(recalls, list) and len(recalls) > 0:
        recall_types = [str(r.get("memory_type", "null")).lower() for r in recalls if isinstance(r, dict)]
        recall_queries = [str(r.get("query", "")).lower() for r in recalls if isinstance(r, dict)]
        checks["01_s1_recalls_before_starting"] = len(recalls) >= 1
        checks["02_s1_recall_relevant_query"] = any(
            kw in q for q in recall_queries for kw in ["rsi", "btc", "strategy", "optim"]
        )
        checks["03_s1_recall_semantic_or_procedural"] = any(
            t in ("semantic", "procedural", "null", "none") for t in recall_types
        )
    else:
        checks["01_s1_recalls_before_starting"] = False
        checks["02_s1_recall_relevant_query"] = False
        checks["03_s1_recall_semantic_or_procedural"] = False

    # Should store current task in working
    stores = s1.get("store_operations", [])
    if isinstance(stores, list) and len(stores) > 0:
        store_types = [str(s.get("memory_type", "")).lower() for s in stores if isinstance(s, dict)]
        checks["04_s1_stores_task_context"] = len(stores) >= 1
        checks["05_s1_stores_in_working"] = any("working" in t for t in store_types)
    else:
        checks["04_s1_stores_task_context"] = False
        checks["05_s1_stores_in_working"] = False

    # ═══ Step 2: First Backtest (PnL=8%, mediocre) ═══
    s2 = parsed.get("step_2_first_backtest", {})
    s2_stores = s2.get("store_operations", [])
    if isinstance(s2_stores, list) and len(s2_stores) > 0:
        s2_all = [s for s in s2_stores if isinstance(s, dict)]
        s2_types = [str(s.get("memory_type", "")).lower() for s in s2_all]
        checks["06_s2_stores_result"] = len(s2_all) >= 1
        # Accept episodic in ANY position (some agents dual-store working+episodic)
        checks["07_s2_tier_episodic"] = any("episodic" in t for t in s2_types)
        # Check importance on the episodic store, or first store if no episodic
        s2_episodic = next((s for s in s2_all if "episodic" in str(s.get("memory_type", "")).lower()), s2_all[0])
        checks["08_s2_importance_normal"] = _importance_in_range(s2_episodic.get("importance"), 0.4, 0.7)
        s2_tags = s2_episodic.get("tags", [])
        checks["09_s2_has_tags"] = isinstance(s2_tags, list) and len(s2_tags) >= 1
    else:
        checks["06_s2_stores_result"] = False
        checks["07_s2_tier_episodic"] = False
        checks["08_s2_importance_normal"] = False
        checks["09_s2_has_tags"] = False

    # ═══ Step 3: Second Backtest (PnL=15%, much better) ═══
    s3 = parsed.get("step_3_second_backtest", {})
    s3_stores = s3.get("store_operations", [])
    if isinstance(s3_stores, list) and len(s3_stores) > 0:
        s3_all = [s for s in s3_stores if isinstance(s, dict)]
        s3_types = [str(s.get("memory_type", "")).lower() for s in s3_all]
        checks["10_s3_stores_result"] = len(s3_all) >= 1
        # Accept episodic in ANY position (some agents dual-store working+episodic)
        checks["11_s3_tier_episodic"] = any("episodic" in t for t in s3_types)
        # Check importance on the episodic store, or first store if no episodic
        s3_episodic = next((s for s in s3_all if "episodic" in str(s.get("memory_type", "")).lower()), s3_all[0])
        # Better result → higher importance than step 2
        checks["12_s3_importance_higher"] = _importance_in_range(s3_episodic.get("importance"), 0.6, 1.0)
    else:
        checks["10_s3_stores_result"] = False
        checks["11_s3_tier_episodic"] = False
        checks["12_s3_importance_higher"] = False

    # ═══ Step 4: Pattern Discovery → should go to SEMANTIC ═══
    s4 = parsed.get("step_4_pattern_discovery", {})
    s4_stores = s4.get("store_operations", [])
    if isinstance(s4_stores, list) and len(s4_stores) > 0:
        s4_first = s4_stores[0] if isinstance(s4_stores[0], dict) else {}
        checks["13_s4_stores_pattern"] = len(s4_stores) >= 1
        # Pattern → SEMANTIC (not episodic) — this is the key distinction
        checks["14_s4_tier_semantic"] = _tier_match(s4_first.get("memory_type"), "semantic")
        # High importance for a discovered pattern
        checks["15_s4_importance_high"] = _importance_in_range(s4_first.get("importance"), 0.7, 1.0)
    else:
        checks["13_s4_stores_pattern"] = False
        checks["14_s4_tier_semantic"] = False
        checks["15_s4_importance_high"] = False

    # Tier difference explanation
    tier_diff = str(s4.get("tier_difference", "")).lower()
    checks["16_s4_explains_tier_difference"] = any(
        kw in tier_diff for kw in ["knowledge", "pattern", "general", "long", "semantic", "fact", "rule"]
    )

    # ═══ Step 5: Completion ═══
    s5 = parsed.get("step_5_completion", {})

    # Should run consolidation
    consol_text = str(s5.get("consolidation", "")).lower()
    checks["17_s5_runs_consolidation"] = any(
        kw in consol_text for kw in ["consolidat", "promot", "working", "episodic"]
    )

    # Final store
    final = s5.get("final_store", {})
    if isinstance(final, dict):
        checks["18_s5_final_store_exists"] = bool(final.get("content_summary"))
        # Accept episodic (experience), semantic (knowledge), or procedural (reusable strategy)
        final_type = str(final.get("memory_type", "")).lower()
        checks["19_s5_final_tier_long_term"] = any(t in final_type for t in ["episodic", "semantic", "procedural"])
    else:
        checks["18_s5_final_store_exists"] = False
        checks["19_s5_final_tier_long_term"] = False

    # Working memory fate
    fate_text = str(s5.get("working_memory_fate", "")).lower()
    checks["20_s5_working_expires_after_5min"] = any(
        kw in fate_text for kw in ["expir", "ttl", "5 min", "5min", "disappear", "delet", "remov", "lost", "clear"]
    )

    # ═══ Multi-Symbol Strategy ═══
    ms = parsed.get("multi_symbol_strategy", {})

    # Individual results → episodic
    checks["21_ms_per_symbol_episodic"] = _tier_match(ms.get("per_symbol_tier"), "episodic")
    # Cross-symbol patterns → semantic
    checks["22_ms_cross_pattern_semantic"] = _tier_match(ms.get("cross_symbol_pattern_tier"), "semantic")
    # Reusable workflow → procedural
    checks["23_ms_workflow_procedural"] = _tier_match(ms.get("workflow_tier"), "procedural")
    # How to identify patterns (should mention recall, tags, comparison)
    how_text = str(ms.get("how_to_identify_patterns", "")).lower()
    checks["24_ms_pattern_identification"] = any(
        kw in how_text for kw in ["recall", "compar", "tag", "across", "pattern", "similar", "search"]
    )

    # ═══ Reasoning ═══
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["25_reasoning_strategy_philosophy"] = any(
            w in r_lower for w in ["memory", "tier", "store", "recall", "long-term", "knowledge", "pattern"]
        )
    else:
        checks["25_reasoning_strategy_philosophy"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.85

    return result


# ═══════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════


NODE_CONFIG = {
    "memory_types": {
        "prompt": MEMORY_TYPES_PROMPT,
        "validator": validate_memory_types_response,
        "checks_count": 27,
    },
    "memory_operations": {
        "prompt": MEMORY_OPERATIONS_PROMPT,
        "validator": validate_memory_operations_response,
        "checks_count": 22,
    },
    "memory_strategy": {
        "prompt": MEMORY_STRATEGY_PROMPT,
        "validator": validate_memory_strategy_response,
        "checks_count": 25,
    },
}


async def test_agent(agent_name: str, client: Any, node: str) -> ValidationResult:
    """Send test prompt to agent and validate response."""
    system_prompt: str = SYSTEM_PROMPTS.get(agent_name, SYSTEM_PROMPTS["deepseek"])
    config: dict[str, Any] = NODE_CONFIG[node]
    prompt_text: str = str(config["prompt"])

    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=prompt_text),
    ]

    start = time.perf_counter()
    try:
        response: LLMResponse = await client.chat(messages)  # type: ignore[union-attr]
        latency = (time.perf_counter() - start) * 1000
        validator: Any = config["validator"]
        result: ValidationResult = validator(agent_name, response.content, latency)  # type: ignore[misc]
        return result
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ValidationResult(
            agent=agent_name,
            node=node,
            passed=False,
            score=0.0,
            error=str(e),
            latency_ms=latency,
        )


def print_result(result: ValidationResult) -> None:
    """Print formatted test result with per-check breakdown."""
    status = "✅ PASS" if result.passed else "❌ FAIL"
    print(f"\n{'=' * 70}")
    print(f"  {status}  {result.agent.upper()} → {result.node.upper()}")
    print(
        f"  Score: {result.score:.0%} ({sum(v for v in result.checks.values())}/{len(result.checks)}) | Latency: {result.latency_ms:.0f}ms"
    )
    print(f"{'=' * 70}")

    if result.error:
        print(f"  ⚠ Error: {result.error}")
        return

    if result.checks:
        print(f"  {'#':<4} {'Check':<55} {'Result':>8}")
        print(f"  {'─' * 67}")
        for i, (check, passed) in enumerate(result.checks.items(), 1):
            icon = "✅" if passed else "❌"
            print(f"  {i:<4} {check:<55} {icon:>8}")

    if result.parsed_json:
        reasoning = result.parsed_json.get("reasoning", "")
        if reasoning:
            truncated = reasoning[:300] + ("..." if len(reasoning) > 300 else "")
            print(f"\n  💬 Reasoning: {truncated}")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AI Agent Memory System Understanding Test v4")
    parser.add_argument(
        "--agent",
        choices=["deepseek", "qwen", "perplexity", "all"],
        default="all",
        help="Which agent to test (default: all)",
    )
    parser.add_argument(
        "--node",
        choices=["memory_types", "memory_operations", "memory_strategy", "all"],
        default="all",
        help="Which test scenario (default: all)",
    )
    args = parser.parse_args()

    print("\n" + "═" * 70)
    print("  🧪 AI Agent Memory System Understanding Test v4")
    print("  Memory Types: 27 checks | Operations: 22 checks | Strategy: 25 checks")
    print("  Total: 74 checks per agent x 3 agents = 222 checks")
    print("═" * 70)

    # Initialize clients
    clients: dict[str, object] = {}

    deepseek_key = _get_api_key("DEEPSEEK_API_KEY")
    if deepseek_key:
        clients["deepseek"] = DeepSeekClient(
            LLMConfig(
                provider=LLMProvider.DEEPSEEK,
                api_key=deepseek_key,
                model="deepseek-chat",
                temperature=0.1,
                max_tokens=4096,
            )
        )
        print("  ✅ DeepSeek ready")
    else:
        print("  ⚠️  DeepSeek: no API key found")

    qwen_key = _get_api_key("QWEN_API_KEY")
    if qwen_key:
        clients["qwen"] = QwenClient(
            LLMConfig(
                provider=LLMProvider.QWEN,
                api_key=qwen_key,
                model="qwen-plus",
                temperature=0.1,
                max_tokens=4096,
            )
        )
        print("  ✅ Qwen ready")
    else:
        print("  ⚠️  Qwen: no API key found")

    perplexity_key = _get_api_key("PERPLEXITY_API_KEY")
    if perplexity_key:
        clients["perplexity"] = PerplexityClient(
            LLMConfig(
                provider=LLMProvider.PERPLEXITY,
                api_key=perplexity_key,
                model=os.getenv("PERPLEXITY_MODEL", "sonar-pro"),
                temperature=0.1,
                max_tokens=4096,
            )
        )
        print("  ✅ Perplexity ready")
    else:
        print("  ⚠️  Perplexity: no API key found")

    if not clients:
        print("\n  ❌ No API keys found!")
        sys.exit(1)

    # Filter agents
    if args.agent != "all":
        if args.agent not in clients:
            print(f"\n  ❌ Agent '{args.agent}' not available")
            sys.exit(1)
        clients = {args.agent: clients[args.agent]}

    # Determine nodes
    nodes = list(NODE_CONFIG.keys()) if args.node == "all" else [args.node]

    # Run tests
    results: list[ValidationResult] = []

    for node in nodes:
        config = NODE_CONFIG[node]
        print(f"\n{'─' * 70}")
        print(f"  Testing {node.upper()} — {config['checks_count']} checks per agent...")
        print(f"{'─' * 70}")

        for agent_name, client in clients.items():
            print(f"\n  ⏳ {agent_name}...")
            result = await test_agent(agent_name, client, node)
            results.append(result)
            print_result(result)

    # Summary
    print(f"\n\n{'═' * 70}")
    print("  📊 FINAL SUMMARY")
    print(f"{'═' * 70}")
    print(f"  {'Agent':<15} {'Node':<22} {'Score':>10} {'Checks':>12} {'Status':>10} {'Latency':>10}")
    print(f"  {'─' * 79}")

    total_passed = 0
    total_tests = 0

    for r in results:
        passed_checks = sum(1 for v in r.checks.values() if v) if r.checks else 0
        total_checks = len(r.checks) if r.checks else 0
        status = "PASS ✅" if r.passed else "FAIL ❌"
        latency = f"{r.latency_ms:.0f}ms" if r.latency_ms > 0 else "N/A"
        print(
            f"  {r.agent:<15} {r.node:<22} {r.score:>9.0%} "
            f"{passed_checks:>5}/{total_checks:<5} {status:>10} {latency:>10}"
        )
        total_tests += 1
        if r.passed:
            total_passed += 1

    # Per-agent summary
    print(f"\n  {'─' * 79}")
    agents_seen = list(dict.fromkeys(r.agent for r in results))
    for agent in agents_seen:
        agent_results = [r for r in results if r.agent == agent]
        total_agent_checks = sum(len(r.checks) for r in agent_results if r.checks)
        passed_agent_checks = sum(sum(1 for v in r.checks.values() if v) for r in agent_results if r.checks)
        agent_pass = sum(1 for r in agent_results if r.passed)
        agent_total = len(agent_results)
        pct = passed_agent_checks / total_agent_checks * 100 if total_agent_checks > 0 else 0
        print(
            f"  {agent.upper():<15} TOTAL                "
            f"{pct:>8.0f}% {passed_agent_checks:>5}/{total_agent_checks:<5} "
            f"{'  ' + str(agent_pass) + '/' + str(agent_total) + ' ✅':>10}"
        )

    print(f"\n  Overall: {total_passed}/{total_tests} tests passed (85% threshold)")

    if total_passed == total_tests:
        print("\n  🎉 All agents demonstrate comprehensive Memory System understanding!")
    else:
        failed = [r for r in results if not r.passed]
        print(f"\n  ⚠️  {len(failed)} test(s) failed:")
        for r in failed:
            failed_checks = [k for k, v in r.checks.items() if not v] if r.checks else []
            print(f"     {r.agent}/{r.node}: {r.error or ', '.join(failed_checks[:5])}")

    # Cleanup clients
    for client in clients.values():
        if hasattr(client, "close"):
            await client.close()  # type: ignore[union-attr]

    # Save results
    results_path = Path(__file__).parent.parent / "logs" / "agent_memory_test_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    results_data = []
    for r in results:
        results_data.append(
            {
                "agent": r.agent,
                "node": r.node,
                "passed": r.passed,
                "score": round(r.score, 4),
                "checks": r.checks,
                "failed_checks": [k for k, v in r.checks.items() if not v] if r.checks else [],
                "latency_ms": round(r.latency_ms, 1),
                "error": r.error,
                "reasoning": r.parsed_json.get("reasoning", "") if r.parsed_json else "",
                "parsed_json": r.parsed_json,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    print(f"\n  📁 Results saved to: {results_path}")
    sys.exit(0 if total_passed == total_tests else 1)


if __name__ == "__main__":
    asyncio.run(main())
