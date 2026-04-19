#!/usr/bin/env python3
"""
Multi-Agent Research Analysis — Phase 13b

Sends state-of-the-art memory architecture research (GAM, Memp, Repos, Vector Store)
to DeepSeek, Qwen, and Perplexity. Each agent compares these approaches with our
current HierarchicalMemory system and recommends concrete adoption paths.

Builds on Phase 13 audit findings (4/4 consensus on top 5 issues).

Usage:
    cd d:\\bybit_strategy_tester_v2
    .venv\\Scripts\\python.exe scripts/test_agent_research_analysis.py
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
# Research Document — state-of-the-art memory architectures
# ═══════════════════════════════════════════════════════════════════

RESEARCH_DOC = """
# STATE-OF-THE-ART AI AGENT MEMORY ARCHITECTURES

## Context
Modern AI agents require sophisticated multi-layer memory systems that solve:
- Context window limitations (information loss in long interactions)
- "Context rot" (progressive degradation of early context)
- Dynamic memory management (what to remember, forget, consolidate)
- Efficient retrieval (semantic vs keyword vs structured search)

Below are 4 cutting-edge architectures, followed by our current system for comparison.

---

## 1. GAM (General Agentic Memory)
**Origin**: Researchers from China & Hong Kong (2025)
**Goal**: Minimize information loss in long dialogues

### Architecture:
Two specialized components working in tandem:

**Memorizer** (Background Process):
- Runs continuously during agent interactions
- Creates concise summaries of conversation chunks
- Simultaneously preserves FULL dialogue history in a "Page Store" database
- Conversation is broken into individual "pages" with contextual labels/tags
- Each page is indexed for efficient retrieval
- Key insight: summaries for speed, full pages for accuracy

**Researcher** (On-Demand Query Engine):
- Activated only when a specific query arrives
- Performs "deep investigation" instead of simple memory lookup
- Plans a search strategy before executing
- Uses THREE retrieval methods:
  1. Vector search — for thematic/semantic similarity
  2. BM25 search — for exact keyword matching
  3. Direct page access — via page identifiers
- Combines results from all methods for comprehensive recall

### Results:
- In RULER benchmark (tracking variables across many steps): >90% accuracy
- Traditional RAG and large-context models mostly failed the same tests
- Key advantage: scales to arbitrarily long conversations without quality loss

### Key Innovation:
Separation of concerns — writing (Memorizer) is decoupled from reading (Researcher).
Both are specialized, unlike our system where store/recall are symmetric operations.

---

## 2. Memp (Memory Management Platform)
**Origin**: AI coding agent memory system (2025)
**Goal**: Version-controlled memory for autonomous coding agents

### Architecture:
- Git-style storage with push/pull operations
- Lightweight branching for spawning sub-agents
- Automatic indexing for two-stage retrieval
- Full codebase search in <2 seconds

### Key Features:
- **Push/Pull**: Agents push memories (findings, decisions) and pull context
- **Branching**: Sub-agents get a "branch" of parent's memory, can merge back
- **Two-Stage Retrieval**:
  Stage 1: Fast index scan (keyword/metadata)
  Stage 2: Deep semantic matching on candidates
- **Semantic search** built into the indexing layer

### Key Innovation:
Version control metaphor — memory has branches, merges, and history.
Sub-agents don't need full memory copy, just a branch.
This is relevant for our multi-agent system (DeepSeek/Qwen/Perplexity).

---

## 3. Repos (Repository-based Long-term Memory)
**Origin**: Vector store-based agent memory pattern (2025)
**Goal**: Semantic long-term memory using embeddings

### Architecture:
- Text, images, and events encoded as embeddings (numerical vectors)
- Stored in vector databases (ChromaDB, FAISS, Pinecone, etc.)
- Retrieval based on semantic similarity, not exact matches

### Use Cases:
- **Conversational agents**: Natural recall of previous conversations, citing them
- **Knowledge systems**: Vector store as "external brain" supplementing model knowledge

### Limitations (important!):
- Vector search is based on SIMILARITY, not TRUE UNDERSTANDING
- Most similar embedding may not be most RELEVANT or USEFUL in context
- No temporal ordering (can't say "what happened before X")
- No causal reasoning (can't say "X caused Y")
- Works best with supplementary structured metadata

### Key Innovation:
Simplicity — any content can be embedded and retrieved semantically.
But needs complementary structured search for production quality.

---

## 4. Hybrid Memory Architecture (Emerging Pattern)
**Origin**: Multiple research groups (2025-2026)
**Goal**: Combine strengths of all approaches

### Emerging Best Practices:
1. **Multi-method retrieval** (like GAM): vector + BM25 + structured
2. **Tiered storage** (like our system): short→long term with consolidation
3. **Agent-specific views** (like Memp): branches per agent role
4. **Background processing** (like GAM Memorizer): async consolidation
5. **Importance scoring** (like our system): priority-based retention
6. **Auto-tagging/categorization** (GAM pages): contextual metadata

---

## OUR CURRENT SYSTEM (for comparison)

### HierarchicalMemory (811 lines)
```
4 Tiers:
  WORKING  — max 10 items, TTL 5min, threshold 0.7
  EPISODIC — max 1000 items, TTL 7d, threshold 0.6
  SEMANTIC — max 10000 items, TTL 365d, threshold 0.5
  PROCEDURAL — max 500 items, TTL 10yr, threshold 0.8

Operations: store, recall, get, delete, consolidate, forget
Retrieval: 0.3*keyword + 0.5*cosine + 0.1*importance + 0.1*recency
Consolidation: working→episodic (importance≥0.7), episodic→semantic (3+ same-tag, avg≥0.6)
Forgetting: TTL + importance decay (0.1%/hr) + evict if importance<0.1 & access<2
```

### Known Issues (from Phase 13 audit — all 4 reviewers agreed):
1. Dual MemoryItem dataclasses (HierarchicalMemory vs SQLiteBackend — different schemas)
2. No MCP tools for agents — they can't self-invoke store/recall
3. Tag inconsistency breaks consolidation — no auto-tagging
4. Single retrieval method (keyword OR cosine) — no hybrid like GAM
5. No background Memorizer — consolidation is periodic, not event-driven
6. No agent-specific memory views — all agents share flat store
7. Vector search silently degrades when ChromaDB not installed
"""

# ═══════════════════════════════════════════════════════════════════
# Prompts
# ═══════════════════════════════════════════════════════════════════

RESEARCH_SYSTEM_PROMPT = """You are a senior AI systems architect specializing in agent memory systems.

Your task: Compare state-of-the-art memory architectures (GAM, Memp, Repos) with our current
HierarchicalMemory system and recommend concrete improvements.

IMPORTANT RULES:
1. Be SPECIFIC — recommend exact changes to our architecture, not vague "consider X"
2. Consider our TRADING CONTEXT — memory must serve backtest analysis, strategy learning, market context
3. Prioritize PRACTICAL improvements over theoretical elegance
4. Consider COST — we use 3 paid LLM APIs, so minimize unnecessary calls
5. Consider our STACK — Python 3.13, FastAPI, SQLite, ChromaDB optional

RESPOND IN EXACTLY THIS FORMAT:

## BEST IDEAS TO ADOPT FROM EACH ARCHITECTURE

### From GAM:
1. [idea]: [how to implement in our system, effort S/M/L]
2. ...

### From Memp:
1. [idea]: [how to implement in our system, effort S/M/L]
2. ...

### From Repos:
1. [idea]: [how to implement in our system, effort S/M/L]
2. ...

## PROPOSED NEW ARCHITECTURE (concrete design)
[Describe the improved HierarchicalMemory v2 with specific components,
data flow, and how it addresses the 7 known issues]

## IMPLEMENTATION ROADMAP (ordered by impact)
1. [step]: [what to build, estimated effort, expected impact]
2. ...
(max 8 steps)

## RISK ASSESSMENT
[What could go wrong with these changes? What should we NOT adopt and why?]
"""

RESEARCH_USER_PROMPT = f"""Please analyze these state-of-the-art AI agent memory architectures and compare
them with our current system:

{RESEARCH_DOC}

Based on this analysis:
1. What are the best ideas we should adopt from each architecture?
2. Design a concrete "HierarchicalMemory v2" that combines the best ideas
3. Create an implementation roadmap (prioritized by impact)
4. Assess risks of the proposed changes

Focus on our TRADING DOMAIN context — agents analyze strategies, run backtests,
learn from results, and need to remember market patterns and strategy performance.
"""


# ═══════════════════════════════════════════════════════════════════
# Agent Runner
# ═══════════════════════════════════════════════════════════════════


async def run_agent(agent_name: str, client, system_prompt: str, user_prompt: str) -> dict:
    """Run research analysis with a single agent."""
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
    """Run research analysis across all 3 agents."""
    print("=" * 80)
    print("🔬  MULTI-AGENT RESEARCH ANALYSIS — Phase 13b")
    print("   Comparing GAM / Memp / Repos with our HierarchicalMemory")
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

    if not clients:
        print("\n❌ No API keys found. Cannot run analysis.")
        return

    print(f"\n📡 Running research analysis with {len(clients)} agents...")
    print("-" * 80)

    # Run all agents in parallel
    tasks = [run_agent(name, client, RESEARCH_SYSTEM_PROMPT, RESEARCH_USER_PROMPT) for name, client in clients.items()]
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
    print("📊 ANALYSIS SUMMARY")
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

    print("\n✅ Research analysis complete!")


if __name__ == "__main__":
    asyncio.run(main())
