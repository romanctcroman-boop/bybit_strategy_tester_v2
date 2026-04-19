#!/usr/bin/env python3
"""
Multi-Agent Architecture Audit — Phase 13

Sends the actual system architecture to DeepSeek, Qwen, and Perplexity
for independent collaborative review. Each agent receives the same
comprehensive architecture document and is asked to:

1. Identify architectural strengths
2. Spot weaknesses, risks, and gaps
3. Suggest concrete improvements
4. Rate overall maturity (1-10)

Results are printed per-agent, then a synthesis summary is shown.

Usage:
    cd d:\\bybit_strategy_tester_v2
    .venv\\Scripts\\python.exe scripts/test_agent_architecture_audit.py
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.llm.base_client import LLMConfig, LLMMessage, LLMProvider
from backend.agents.llm.clients.deepseek import DeepSeekClient
from backend.agents.llm.clients.perplexity import PerplexityClient
from backend.agents.llm.clients.qwen import QwenClient
from backend.security.key_manager import get_key_manager

# ═══════════════════════════════════════════════════════════════════
# Architecture Document — comprehensive system description
# ═══════════════════════════════════════════════════════════════════

ARCHITECTURE_DOC = """
# BYBIT STRATEGY TESTER v2 — Multi-Agent AI Architecture

## System Overview
A production trading strategy backtesting system with a 3-agent AI layer
(DeepSeek, Qwen, Perplexity) for strategy building, optimization, and analysis.
Stack: Python 3.13, FastAPI, SQLAlchemy, SQLite, Pandas, NumPy, Bybit API v5.

---

## 1. MEMORY SYSTEM

### 1.1 HierarchicalMemory (811 lines, core memory engine)
```
4 Tiers:
  WORKING  — max 10 items, TTL 5 min, consolidation_threshold 0.7, priority 1
  EPISODIC — max 1000 items, TTL 7 days, consolidation_threshold 0.6, priority 2
  SEMANTIC — max 10000 items, TTL 365 days, consolidation_threshold 0.5, priority 3
  PROCEDURAL — max 500 items, TTL 10 years, consolidation_threshold 0.8, priority 4

Operations:
  store(content, memory_type, importance, tags, metadata, source) → MemoryItem
  recall(query, memory_type, top_k, min_importance, tags, use_semantic) → list[MemoryItem]
  get(item_id) → MemoryItem | None
  delete(item_id) → bool
  consolidate() → dict  # working→episodic (importance≥0.7), episodic→semantic (3+ items, avg_importance≥0.6)
  forget() → dict  # TTL expiration + importance decay (0.1%/hour) + evict if importance<0.1 & access_count<2

Data Model:
  MemoryItem: id, content, memory_type, created_at, accessed_at, access_count,
              importance (0.0-1.0), embedding (optional), metadata, tags, source, related_ids

Relevance Scoring (for recall):
  0.3 * keyword_overlap + 0.5 * cosine_similarity + 0.1 * importance + 0.1 * recency_decay

Eviction: When tier is full, evict item with lowest (importance, -access_count)
```

### 1.2 SharedMemory (624 lines, cross-agent state)
```
Thread-safe shared state for multi-agent coordination.
Features:
  - Optimistic locking (version checking)
  - Pessimistic locking (with timeout)
  - Transactions (atomic multi-key operations)
  - Event subscriptions (key-level + global callbacks)
  - Conflict resolution: LAST_WRITE_WINS, FIRST_WRITE_WINS, MERGE, REJECT, CUSTOM

SharedValue: value, version, created_at, updated_at, updated_by, lock_holder, lock_expires_at
Transaction: id, agent_id, operations[(op, key, value)], started_at, committed
```

### 1.3 Persistence Backends (backend_interface.py)
```
ABC: MemoryBackend
  save_item(item_id, tier, data)
  load_item(item_id, tier) → dict | None
  delete_item(item_id, tier)
  load_all(tier) → list[dict]
  close()

Implementations:
  JsonFileBackend — file-per-item under <persist_path>/<tier>/<item_id>.json (legacy default)
  SQLiteBackendAdapter — wraps SQLiteMemoryBackend via asyncio.to_thread

HierarchicalMemory boots with backend.load_all(), auto-detects if event loop is running.
```

### 1.4 SQLiteMemoryBackend (352 lines, standalone)
```
Direct SQLite with WAL mode.
Table: memory_items (id, content, memory_type, importance, created_at, accessed_at,
                     access_count, ttl_seconds, tags JSON, metadata JSON)
Indexes: memory_type, importance DESC, accessed_at DESC
Operations: store, query, get_by_id, delete, cleanup_expired, export_all, import_from_dict
Note: This has its OWN PersistentMemoryItem dataclass — separate from MemoryItem in hierarchical_memory.py
```

### 1.5 VectorMemoryStore (602 lines, semantic search)
```
ChromaDB for local vector storage.
Embedding options:
  1. Custom function (injected)
  2. Local sentence-transformers (all-MiniLM-L6-v2, 384 dim)
  3. ChromaDB default

Supports: add, query, delete, update, count, clear
Collection metadata: hnsw:space=cosine
```

### 1.6 MemoryConsolidator (background process)
```
Runs periodically:
  consolidation_interval = 1 hour
  forgetting_interval = 15 min
Calls: memory.consolidate() and memory.forget()
```

---

## 2. ORCHESTRATION SYSTEM

### 2.1 Multi-Agent Deliberation (deliberation.py, 1411 lines)
```
Phases: INITIAL → CROSS_EXAMINATION → REFINEMENT → FINAL_VOTE

Voting Strategies: MAJORITY, WEIGHTED, UNANIMOUS, RANKED_CHOICE, SUPERMAJORITY

Data Models:
  AgentVote: agent_id, agent_type, position, confidence, reasoning, evidence, dissent_points
  Critique: critic_agent, target_agent, agrees, agreement_points, disagreement_points,
            suggested_improvements, confidence_adjustment (-0.5 to +0.5)
  DeliberationRound: round_number, phase, opinions, critiques, consensus_emerging, convergence_score
  DeliberationResult: id, question, decision, confidence, rounds, final_votes,
                      dissenting_opinions, evidence_chain, duration_seconds

Flow:
  1. Collect initial opinions from all agents
  2. Each agent critiques others' positions
  3. Agents refine positions based on feedback
  4. Final vote with convergence scoring
```

### 2.2 RealLLMDeliberation (real_llm_deliberation.py, 554 lines)
```
Extends MultiAgentDeliberation with actual API calls:
  DeepSeek: deepseek-chat, temp 0.7, 2048 tokens — quantitative analyst
  Qwen: qwen-plus, temp 0.4, 2048 tokens — technical analyst
  Perplexity: sonar-pro, temp 0.4, 2048 tokens — market researcher

Deep Perplexity Integration:
  1. enrich_for_deliberation() — Perplexity called FIRST for real-time market context
  2. Enriched context injected into DeepSeek/Qwen prompts automatically
  3. Structured AgentSignal exchange between agents
  4. cross_validate() — detects conflicts, calculates agreement score
  5. Adaptive routing — Perplexity skipped for backtest-only tasks

Singleton: get_real_deliberation()
Convenience: deliberate_with_llm(question, agents, symbol, ...)
```

### 2.3 ConsensusEngine (consensus_engine.py, 838 lines)
```
Strategy-level consensus (operates on StrategyDefinition objects, not text).

Methods:
  weighted_voting — signal-level aggregation by agent weight
  bayesian_aggregation — posterior-based combination with prior performance
  best_of — pick single best strategy by heuristic score

Agent weights: Calculated from historical AgentPerformance
  (total_strategies, successful_backtests, avg_sharpe, avg_profit_factor, avg_win_rate)

Output: ConsensusResult with consensus strategy, agreement_score, agent_weights, signal_votes
```

### 2.4 PerplexityIntegration (perplexity_integration.py, 701 lines)
```
Adaptive routing:
  PERPLEXITY_TRIGGER_KEYWORDS: sentiment, news, macro, fed, halving, etc.
  PERPLEXITY_SKIP_KEYWORDS: backtest, historical, calculate, rsi, etc.

AgentSignal: agent, signal_type, direction, confidence, reasoning, data
CrossValidationResult: agents_agree, agreement_score, conflicts, resolution

Prompt templates: ENRICHMENT_PROMPT_TEMPLATE (structured JSON market context),
                  CROSS_VALIDATION_PROMPT (conflict mediation)
```

### 2.5 LangGraph Orchestrator (langgraph_orchestrator.py, 699 lines)
```
Directed graph-based agent execution:
  AgentState: messages, context, visited_nodes, execution_path, results, errors
  AgentNode (ABC): execute(state) → state, with timeout + retry
  FunctionAgent: wraps a callable
  LLMAgent: calls DeepSeek/Perplexity via agent_to_agent_communicator

  AgentGraph: nodes, edges (DIRECT/CONDITIONAL/PARALLEL), routers
    entry_point → edges → exit_points
    ConditionalRouter: routes based on state conditions

  Execution: BFS traversal, parallel execution for PARALLEL edges
```

### 2.6 Agent-to-Agent Communicator (724 lines)
```
Cross-agent messaging with Redis-backed queue:
  AgentMessage: from_agent, to_agent, message_type, content, conversation_id,
                iteration, max_iterations, confidence_score
  Supports: send_message, async_send_message, broadcast, multi-turn conversations
  Integrates: AgentMemoryManager, AgentChannel, FORCE_DIRECT_AGENT_API flag
```

### 2.7 Builder Workflow (989 lines)
```
8-stage pipeline for AI-driven strategy creation through REST API:
  PLANNING → CREATING → ADDING_BLOCKS → CONNECTING → VALIDATING →
  GENERATING_CODE → BACKTESTING → EVALUATING

Uses MCP tools: builder_create_strategy, builder_add_block, builder_connect_blocks,
                builder_validate_strategy, builder_generate_code, builder_run_backtest

Config: commission=0.0007, max_iterations=3, min_acceptable_sharpe=0.5
```

---

## 3. VALIDATION & SECURITY

### 3.1 StrategyValidator (320 lines)
```
Validates strategy parameters before agent-driven backtests:
  - Risk classification: SAFE, MODERATE, HIGH, EXTREME, REJECTED
  - Strategy-specific constraints (RSI, MACD, SMA, BB period ranges)
  - Leverage limits (Bybit max 125x)
  - Date range validation (DATA_START_DATE=2025-01-01)
  - Commission enforcement (0.0007)
```

### 3.2 OutputValidator (274 lines)
```
Validates LLM responses for safety:
  - Sensitive data leakage (API keys, passwords, env vars)
  - Hallucinated financial advice
  - Dangerous trading recommendations
  - Code execution attempts
  - Length validation (empty/excessive)

Regex-based rules with severity: CRITICAL (block), WARNING (log), INFO
```

### 3.3 Evaluation System (evals/)
```
StrategyEval (413 lines):
  evaluate_signal_analysis — direction, indicators, risk, confidence, actionability
  Grades: EXCELLENT (≥0.90), GOOD (≥0.75), ACCEPTABLE (≥0.60), POOR (≥0.40), FAIL

BenchmarkSuite (495 lines):
  Standardized test cases with expected_patterns, max_latency_ms, quality_threshold
  Categories: RESPONSE_QUALITY, LATENCY, ACCURACY, CONSISTENCY, SAFETY, TRADING_DOMAIN
  ScoreCard: overall_score, letter grades (A+ to F), pass_rate, category_scores
```

---

## 4. SELF-IMPROVEMENT SYSTEM (self_improvement/)
```
8 modules:
  agent_tracker.py — tracks agent performance over time
  feedback_loop.py — collects and processes user/system feedback
  llm_reflection.py — LLM-based self-analysis of past decisions
  pattern_extractor.py — identifies recurring patterns in agent behavior
  performance_evaluator.py — evaluates agent quality metrics
  rlhf_module.py — reinforcement learning from human feedback
  self_reflection.py — agent self-evaluation
  strategy_evolution.py — evolutionary optimization of strategies
```

## 5. MONITORING (monitoring/)
```
7 modules:
  alerting.py — threshold-based alerts
  dashboard.py — agent system dashboard
  metrics_collector.py — collects system metrics
  ml_anomaly.py — ML-based anomaly detection
  prometheus_grafana.py — Prometheus/Grafana integration
  system_monitor.py — system resource monitoring
  tracing.py — request tracing
```

---

## 6. KEY ARCHITECTURAL OBSERVATIONS

1. **Dual Memory Systems**: HierarchicalMemory (4-tier, async, with backends) AND
   SQLiteMemoryBackend (standalone, sync, different data model) exist side by side.
   SQLiteBackendAdapter bridges them, but there are 2 MemoryItem dataclasses.

2. **Dual Orchestration**: Both deliberation.py (text-based debate) AND
   consensus_engine.py (structured strategy voting) exist — different levels of abstraction.

3. **3 Communication Paths**: agent_to_agent_communicator (Redis), SharedMemory (in-process),
   LangGraph orchestrator (graph-based). When to use which?

4. **Memory Not Connected to Agents**: Agents have memory system prompts but
   no MCP tools for actual memory operations. They can't self-invoke store/recall.

5. **Consolidation Logic**: episodic→semantic requires 3+ items with same tag AND
   avg_importance≥0.6 — but who assigns consistent tags?

6. **VectorStore Optional**: ChromaDB + sentence-transformers are optional dependencies.
   If not installed, semantic search silently degrades to keyword-only.
"""

# ═══════════════════════════════════════════════════════════════════
# Audit Prompt
# ═══════════════════════════════════════════════════════════════════

AUDIT_SYSTEM_PROMPT = """You are a senior AI systems architect conducting a thorough architecture review.

Your task: Review the multi-agent AI architecture below and provide a structured analysis.

IMPORTANT RULES:
1. Be brutally honest — identify real problems, not just praise
2. Focus on PRODUCTION-READINESS, not academic elegance
3. Consider failure modes, edge cases, and scalability
4. Provide CONCRETE recommendations (not vague "consider X")
5. Rate overall maturity on a 1-10 scale with justification

RESPOND IN EXACTLY THIS FORMAT:

## STRENGTHS (top 5)
1. [strength]: [brief explanation]
2. ...

## WEAKNESSES (top 5)
1. [weakness]: [brief explanation + impact]
2. ...

## RISKS (top 3 production risks)
1. [risk]: [probability HIGH/MED/LOW] — [impact description]
2. ...

## TOP 5 CONCRETE IMPROVEMENTS (prioritized)
1. [improvement]: [what to do, why, estimated effort S/M/L]
2. ...

## ARCHITECTURE MATURITY: X/10
[2-3 sentence justification]

## WILD CARD IDEA
[One unconventional/creative suggestion that could significantly improve the system]
"""

AUDIT_USER_PROMPT = f"""Please review this multi-agent AI architecture for a trading strategy system:

{ARCHITECTURE_DOC}

Provide your structured analysis following the format in the system prompt.
Focus on memory system design, orchestration patterns, validation gaps, and production readiness.
"""


# ═══════════════════════════════════════════════════════════════════
# Agent Runner
# ═══════════════════════════════════════════════════════════════════


async def run_agent_audit(agent_name: str, client, system_prompt: str, user_prompt: str) -> dict:
    """Run audit with a single agent."""
    start = time.time()
    try:
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]
        response = await client.chat(messages)
        elapsed = time.time() - start
        return {
            "agent": agent_name,
            "response": response.content,
            "tokens": response.total_tokens,
            "latency_ms": elapsed * 1000,
            "success": True,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "agent": agent_name,
            "response": f"ERROR: {e}",
            "tokens": 0,
            "latency_ms": elapsed * 1000,
            "success": False,
        }


async def main():
    """Run architecture audit across all 3 agents."""
    print("=" * 80)
    print("🏗️  MULTI-AGENT ARCHITECTURE AUDIT — Phase 13")
    print("=" * 80)
    print()

    # Get API keys via KeyManager
    km = get_key_manager()

    clients = {}

    # DeepSeek
    ds_key = km.get_decrypted_key("DEEPSEEK_API_KEY")
    if ds_key:
        clients["deepseek"] = DeepSeekClient(
            LLMConfig(
                provider=LLMProvider.DEEPSEEK,
                api_key=ds_key,
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=4096,
            )
        )
        print("✅ DeepSeek ready")
    else:
        print("❌ DeepSeek: no API key")

    # Qwen
    qw_key = km.get_decrypted_key("QWEN_API_KEY")
    if qw_key:
        clients["qwen"] = QwenClient(
            LLMConfig(
                provider=LLMProvider.QWEN,
                api_key=qw_key,
                model="qwen-plus",
                temperature=0.3,
                max_tokens=4096,
            )
        )
        print("✅ Qwen ready")
    else:
        print("❌ Qwen: no API key")

    # Perplexity
    pp_key = km.get_decrypted_key("PERPLEXITY_API_KEY")
    if pp_key:
        clients["perplexity"] = PerplexityClient(
            LLMConfig(
                provider=LLMProvider.PERPLEXITY,
                api_key=pp_key,
                model="sonar-pro",
                temperature=0.3,
                max_tokens=4096,
            )
        )
        print("✅ Perplexity ready")
    else:
        print("❌ Perplexity: no API key")

    if not clients:
        print("\n❌ No API keys found. Cannot run audit.")
        return

    print(f"\n📡 Running audit with {len(clients)} agents...")
    print("-" * 80)

    # Run all agents in parallel
    tasks = [run_agent_audit(name, client, AUDIT_SYSTEM_PROMPT, AUDIT_USER_PROMPT) for name, client in clients.items()]
    results = await asyncio.gather(*tasks)

    # Display results
    for result in results:
        agent = result["agent"]
        status = "✅" if result["success"] else "❌"
        tokens = result["tokens"]
        latency = result["latency_ms"]

        print(f"\n{'=' * 80}")
        print(f"{status} {agent.upper()} — {tokens} tokens, {latency:.0f}ms")
        print(f"{'=' * 80}")
        print(result["response"])
        print()

    # Summary table
    print("\n" + "=" * 80)
    print("📊 AUDIT SUMMARY")
    print("=" * 80)
    print(f"{'Agent':<15} {'Status':<10} {'Tokens':<10} {'Latency':<12}")
    print("-" * 47)
    for r in results:
        status = "✅ OK" if r["success"] else "❌ FAIL"
        print(f"{r['agent']:<15} {status:<10} {r['tokens']:<10} {r['latency_ms']:.0f}ms")

    # Close clients
    for client in clients.values():
        with contextlib.suppress(Exception):
            await client.close()

    print("\n✅ Audit complete!")


if __name__ == "__main__":
    asyncio.run(main())
