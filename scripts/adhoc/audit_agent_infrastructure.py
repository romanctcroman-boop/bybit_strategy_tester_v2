#!/usr/bin/env python3
"""
Engineering Audit of Agent Infrastructure

Sends agent source code to DeepSeek, Qwen, and Perplexity for independent
engineering audit. Each agent reviews its own code + shared infrastructure.

Focus: architecture, code quality, tooling, prompts, rules — NOT trading logic.

Output: docs/agent_analysis/engineering_audit_results.json
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding (cp1251 -> utf-8)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Project setup
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv()

from backend.agents.llm.connections import (
    DeepSeekClient,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    PerplexityClient,
    QwenClient,
)


def section(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def subsection(title: str):
    print(f"\n--- {title} ---\n")


# ═══════════════════════════════════════════════════════════════════
# CODE COLLECTOR — reads key files and builds audit context
# ═══════════════════════════════════════════════════════════════════


def collect_code_for_audit() -> dict[str, str]:
    """Read all key agent files and return as dict[filename -> content]."""
    base = PROJECT_ROOT / "backend" / "agents"

    # Core files every agent should review
    core_files = [
        # LLM connections & optimization
        "llm/connections.py",
        "llm/prompt_optimizer.py",
        # Consensus & deliberation
        "consensus/deliberation.py",
        "consensus/real_llm_deliberation.py",
        "consensus/perplexity_integration.py",
        "consensus/domain_agents.py",
        # Prompts system
        "prompts/templates.py",
        "prompts/prompt_engineer.py",
        "prompts/response_parser.py",
        "prompts/context_builder.py",
        # Security
        "security/prompt_guard.py",
        "security/output_validator.py",
        "security/rate_limiter.py",
        # Memory
        "agent_memory.py",
        "memory/hierarchical_memory.py",
        "memory/vector_store.py",
        # Key management & resilience
        "key_manager.py",
        "api_key_pool.py",
        "circuit_breaker_manager.py",
        "health_monitor.py",
        # Core interface
        "unified_agent_interface.py",
        "models.py",
        "base_config.py",
        # Self-improvement
        "self_improvement/feedback_loop.py",
        "self_improvement/self_reflection.py",
        # MCP
        "mcp/tool_registry.py",
        "mcp/trading_tools.py",
    ]

    code = {}
    total_lines = 0
    for rel_path in core_files:
        full_path = base / rel_path
        if full_path.exists():
            content = full_path.read_text(encoding="utf-8", errors="replace")
            lines = content.count("\n")
            total_lines += lines
            code[rel_path] = content
            print(f"  [OK] {rel_path} ({lines} LOC)")
        else:
            print(f"  [--] {rel_path} (not found)")

    print(f"\n  Total: {len(code)} files, {total_lines} LOC")
    return code


def build_file_tree() -> str:
    """Build a tree representation of backend/agents/."""
    base = PROJECT_ROOT / "backend" / "agents"
    lines = ["backend/agents/"]

    def walk(path: Path, prefix: str = "  "):
        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        for item in items:
            if item.name.startswith("__"):
                continue
            if item.is_dir():
                lines.append(f"{prefix}{item.name}/")
                walk(item, prefix + "  ")
            elif item.suffix == ".py":
                loc = item.read_text(errors="replace").count("\n")
                lines.append(f"{prefix}{item.name} ({loc} LOC)")

    walk(base)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# AUDIT PROMPTS — engineering-focused, NOT trading
# ═══════════════════════════════════════════════════════════════════

AUDIT_SYSTEM_PROMPT = """You are a senior software engineer performing a comprehensive
engineering audit of an AI agent infrastructure for a trading strategy backtesting platform.

CRITICAL: This audit is about SOFTWARE ENGINEERING QUALITY, not trading strategy logic.
Focus on: architecture, code quality, patterns, tooling, security, scalability, testing.

You are reviewing YOUR OWN code — the agent system that YOU run on.
Be brutally honest about what works, what doesn't, and what needs fixing."""


def build_audit_prompt(agent_name: str, code_files: dict[str, str], file_tree: str) -> str:
    """Build the full audit prompt for a specific agent."""

    # Select files most relevant to this agent + shared files
    shared_files = [
        "llm/connections.py",
        "models.py",
        "base_config.py",
        "key_manager.py",
        "api_key_pool.py",
        "circuit_breaker_manager.py",
        "health_monitor.py",
        "unified_agent_interface.py",
        "prompts/templates.py",
        "prompts/prompt_engineer.py",
        "prompts/response_parser.py",
        "security/prompt_guard.py",
        "agent_memory.py",
    ]

    agent_specific = {
        "deepseek": [
            "consensus/deliberation.py",
            "consensus/real_llm_deliberation.py",
            "self_improvement/feedback_loop.py",
            "self_improvement/self_reflection.py",
            "llm/prompt_optimizer.py",
            "security/output_validator.py",
        ],
        "qwen": [
            "consensus/domain_agents.py",
            "consensus/real_llm_deliberation.py",
            "prompts/context_builder.py",
            "llm/prompt_optimizer.py",
            "memory/hierarchical_memory.py",
            "security/rate_limiter.py",
        ],
        "perplexity": [
            "consensus/perplexity_integration.py",
            "consensus/real_llm_deliberation.py",
            "memory/vector_store.py",
            "mcp/tool_registry.py",
            "mcp/trading_tools.py",
            "llm/prompt_optimizer.py",
        ],
    }

    selected = list(dict.fromkeys(shared_files + agent_specific.get(agent_name, [])))

    # Build code context (truncate huge files to first 200 lines to fit context windows)
    code_sections = []
    for fname in selected:
        if fname in code_files:
            content = code_files[fname]
            lines = content.split("\n")
            if len(lines) > 200:
                content = "\n".join(lines[:200]) + f"\n\n# ... truncated ({len(lines)} total lines)"
            code_sections.append(f"### FILE: backend/agents/{fname}\n```python\n{content}\n```")

    code_block = "\n\n".join(code_sections)

    return f"""ENGINEERING AUDIT — Agent Infrastructure
Agent performing audit: {agent_name.upper()}
Date: {datetime.now().strftime("%Y-%m-%d")}

PROJECT STRUCTURE:
{file_tree}

TOTAL: ~28,000 LOC across 75 Python files in backend/agents/

TECHNOLOGY STACK:
- Python 3.13, FastAPI, SQLAlchemy, SQLite
- 3 LLM providers: DeepSeek (deepseek-chat), Qwen (qwen-plus), Perplexity (sonar-pro)
- 24 API keys (8 per provider) with rotation pool
- aiohttp for async LLM calls
- Circuit breaker pattern, health monitoring
- Prompt injection guard, output validation
- Agent memory (JSON persistence + hierarchical)
- Multi-agent deliberation with cross-examination

YOUR CODE TO AUDIT:
{code_block}

AUDIT CATEGORIES — evaluate each 1-10 and provide specific findings:

1. **Architecture & Modularity** (1-10)
   - Separation of concerns, dependency management
   - Import chain health (circular deps?)
   - Module cohesion vs coupling
   - Are there dead/unused modules?

2. **LLM Connection Layer** (1-10)
   - Error handling, retry logic, circuit breakers
   - Key rotation robustness
   - Token tracking accuracy
   - Rate limiting effectiveness

3. **Prompt Engineering System** (1-10)
   - Template quality and maintainability
   - Context building completeness
   - Response parsing robustness
   - Few-shot example quality
   - Are prompts tested? Versioned?

4. **Security & Safety** (1-10)
   - Prompt injection protection coverage
   - Output validation completeness
   - API key security (encryption, rotation)
   - Rate limiting granularity
   - Are there gaps in the security layer?

5. **Memory & State Management** (1-10)
   - Conversation persistence reliability
   - Memory retrieval efficiency
   - State consistency across agents
   - Is there memory leak risk?

6. **Consensus & Deliberation** (1-10)
   - Deliberation protocol quality
   - Cross-validation logic correctness
   - Confidence scoring reliability
   - Does the voting system produce good decisions?

7. **Testing & Observability** (1-10)
   - Are there enough tests? What's missing?
   - Logging quality (too much? too little?)
   - Metrics collection usefulness
   - Error tracing capability

8. **Code Quality & Maintainability** (1-10)
   - Type annotations coverage
   - Docstring quality
   - Dead code presence
   - Naming consistency
   - DRY violations

9. **Scalability & Performance** (1-10)
   - Async patterns correctness
   - Connection pooling efficiency
   - Memory usage concerns
   - Bottleneck identification

10. **Missing Capabilities** (critical gaps)
    - What essential tools/features are missing?
    - What integrations should exist but don't?
    - What would break first in production?

RESPONSE FORMAT — return JSON:
{{
  "agent": "{agent_name}",
  "overall_score": 7.5,
  "scores": {{
    "architecture": 7,
    "llm_connections": 8,
    "prompt_engineering": 6,
    "security": 7,
    "memory": 5,
    "consensus": 8,
    "testing": 4,
    "code_quality": 7,
    "scalability": 6,
    "missing_capabilities": "N/A"
  }},
  "critical_issues": [
    {{
      "category": "security",
      "severity": "HIGH",
      "file": "security/prompt_guard.py",
      "description": "...",
      "fix": "..."
    }}
  ],
  "improvement_suggestions": [
    {{
      "category": "prompt_engineering",
      "priority": "P0|P1|P2",
      "description": "...",
      "effort": "small|medium|large",
      "impact": "high|medium|low"
    }}
  ],
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "missing_tools": ["...", "..."],
  "recommended_next_steps": ["...", "...", "..."]
}}

Be thorough. Be specific. Reference actual files and line numbers where possible.
This is YOUR infrastructure — your audit determines what gets fixed."""


# ═══════════════════════════════════════════════════════════════════
# AUDIT EXECUTION
# ═══════════════════════════════════════════════════════════════════


async def run_agent_audit(
    agent_name: str,
    prompt: str,
) -> dict:
    """Run audit for a single agent."""
    subsection(f"{agent_name.upper()} - Engineering Audit")

    key_env = {
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen": "QWEN_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
    }
    models = {
        "deepseek": "deepseek-chat",
        "qwen": "qwen-plus",
        "perplexity": "sonar-pro",
    }
    providers = {
        "deepseek": LLMProvider.DEEPSEEK,
        "qwen": LLMProvider.QWEN,
        "perplexity": LLMProvider.PERPLEXITY,
    }
    clients = {
        "deepseek": DeepSeekClient,
        "qwen": QwenClient,
        "perplexity": PerplexityClient,
    }

    api_key = os.environ.get(key_env[agent_name], "")
    if not api_key:
        print(f"  SKIP: no API key for {agent_name}")
        return {"status": "skipped", "error": "no API key"}

    config = LLMConfig(
        provider=providers[agent_name],
        model=models[agent_name],
        api_key=api_key,
        max_tokens=8192,
        temperature=0.3,
        timeout_seconds=300,  # 5 min — large prompts need more time
    )

    client = clients[agent_name](config)
    max_retries = 3
    try:
        for attempt in range(1, max_retries + 1):
            try:
                start = time.time()
                if attempt > 1:
                    print(f"  Retry {attempt}/{max_retries}...")
                response = await client.chat(
                    [
                        LLMMessage(role="system", content=AUDIT_SYSTEM_PROMPT),
                        LLMMessage(role="user", content=prompt),
                    ]
                )
                elapsed = time.time() - start

                content = response.content.strip()
                print(f"  Response: {len(content)} chars, {response.total_tokens} tokens, {elapsed:.1f}s")
                print(f"  First 500 chars:\n    {content[:500]}...")

                # Try to parse JSON from response
                audit_data = extract_json(content)
                if audit_data:
                    print(f"  JSON parsed: OK (overall_score={audit_data.get('overall_score', '?')})")
                else:
                    print("  JSON parsed: FAILED (storing raw text)")
                    audit_data = {"raw_response": content}

                audit_data["_meta"] = {
                    "agent": agent_name,
                    "model": response.model,
                    "tokens": response.total_tokens,
                    "latency_s": round(elapsed, 2),
                    "timestamp": datetime.now().isoformat(),
                }

                return audit_data

            except Exception as e:
                err_str = str(e).lower()
                is_retryable = any(
                    kw in err_str for kw in ["high demand", "rate limit", "429", "503", "overloaded", "timeout"]
                )
                print(f"  ERROR (attempt {attempt}): {e}")
                if is_retryable and attempt < max_retries:
                    wait = 30 * attempt
                    print(f"  Retryable error. Waiting {wait}s before retry...")
                    await asyncio.sleep(wait)
                else:
                    import traceback

                    traceback.print_exc()
                    return {"status": "error", "error": str(e), "agent": agent_name}

        return {"status": "error", "error": "max retries exceeded", "agent": agent_name}
    finally:
        await client.close()


def extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response text."""
    import re

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    patterns = [
        r"```json\s*\n(.*?)\n```",
        r"```\s*\n(.*?)\n```",
        r"\{[\s\S]*\}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                candidate = match.group(1) if match.lastindex else match.group(0)
                return json.loads(candidate)
            except (json.JSONDecodeError, IndexError):
                continue

    return None


async def main():
    section("ENGINEERING AUDIT - Agent Infrastructure")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Auditors: DeepSeek, Qwen, Perplexity")
    print("  Focus: Software engineering (NOT trading logic)")

    # Step 1: Collect code
    section("Step 1: Collecting Code")
    code_files = collect_code_for_audit()
    file_tree = build_file_tree()

    # Step 2: Build per-agent prompts
    section("Step 2: Building Audit Prompts")
    prompts = {}
    for agent in ["deepseek", "qwen", "perplexity"]:
        prompt = build_audit_prompt(agent, code_files, file_tree)
        prompts[agent] = prompt
        print(f"  {agent}: {len(prompt)} chars ({len(prompt.split())} words)")

    # Step 3: Run audits sequentially (to avoid rate limits)
    section("Step 3: Running Audits")
    results = {}
    total_start = time.time()

    for agent_name in ["deepseek", "qwen", "perplexity"]:
        result = await run_agent_audit(agent_name, prompts[agent_name])
        results[agent_name] = result
        print()  # spacing between agents

    total_elapsed = time.time() - total_start

    # Step 4: Save results
    section("Step 4: Saving Results")
    output_dir = PROJECT_ROOT / "docs" / "agent_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "engineering_audit_results.json"

    final = {
        "audit_type": "engineering",
        "timestamp": datetime.now().isoformat(),
        "total_elapsed_s": round(total_elapsed, 2),
        "files_audited": len(code_files),
        "results": results,
    }

    def safe_serialize(obj):
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False, default=safe_serialize)

    print(f"  Saved to: {output_file}")

    # Step 5: Print summary
    section("AUDIT SUMMARY")
    for agent, data in results.items():
        score = data.get("overall_score", "?")
        status = data.get("status", "ok")
        if status in ("error", "skipped"):
            print(f"  [{agent.upper():11s}] {status}: {data.get('error', '')}")
        else:
            critical = len(data.get("critical_issues", []))
            suggestions = len(data.get("improvement_suggestions", []))
            strengths = len(data.get("strengths", []))
            weaknesses = len(data.get("weaknesses", []))
            print(
                f"  [{agent.upper():11s}] Score: {score}/10 | "
                f"Critical: {critical} | Suggestions: {suggestions} | "
                f"Strengths: {strengths} | Weaknesses: {weaknesses}"
            )

    print(f"\n  Total time: {total_elapsed:.1f}s")
    print(f"  Results: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
