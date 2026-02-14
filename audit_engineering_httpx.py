#!/usr/bin/env python3
"""
Engineering Audit of Agent Infrastructure (httpx version)

Sends agent source code to DeepSeek, Qwen, and Perplexity for independent
engineering audit using direct httpx calls (bypassing connections.py).

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

import httpx
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════════
# API CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

API_CONFIG = {
    "deepseek": {
        "key_env": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
    },
    "qwen": {
        "key_env": "QWEN_API_KEY",
        "url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": os.getenv("QWEN_MODEL", "qwen-plus"),
    },
    "perplexity": {
        "key_env": "PERPLEXITY_API_KEY",
        "url": "https://api.perplexity.ai/chat/completions",
        "model": "sonar-pro",
    },
}


def section(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def subsection(title: str):
    print(f"\n--- {title} ---\n")


# ═══════════════════════════════════════════════════════════════════
# CODE COLLECTOR
# ═══════════════════════════════════════════════════════════════════


def collect_code_for_audit() -> dict[str, str]:
    """Read all key agent files and return as dict[filename -> content]."""
    base = PROJECT_ROOT / "backend" / "agents"

    core_files = [
        "llm/connections.py",
        "llm/prompt_optimizer.py",
        "consensus/deliberation.py",
        "consensus/real_llm_deliberation.py",
        "consensus/perplexity_integration.py",
        "consensus/domain_agents.py",
        "prompts/templates.py",
        "prompts/prompt_engineer.py",
        "prompts/response_parser.py",
        "prompts/context_builder.py",
        "security/prompt_guard.py",
        "security/output_validator.py",
        "security/rate_limiter.py",
        "agent_memory.py",
        "memory/hierarchical_memory.py",
        "memory/vector_store.py",
        "key_manager.py",
        "api_key_pool.py",
        "circuit_breaker_manager.py",
        "health_monitor.py",
        "unified_agent_interface.py",
        "models.py",
        "base_config.py",
        "self_improvement/feedback_loop.py",
        "self_improvement/self_reflection.py",
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
    """Build a tree of backend/agents/."""
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
# AUDIT PROMPTS
# ═══════════════════════════════════════════════════════════════════

AUDIT_SYSTEM_PROMPT = (
    "You are a senior software engineer performing a comprehensive "
    "engineering audit of an AI agent infrastructure for a trading strategy "
    "backtesting platform.\n\n"
    "CRITICAL: This audit is about SOFTWARE ENGINEERING QUALITY, not trading "
    "strategy logic. Focus on: architecture, code quality, patterns, tooling, "
    "security, scalability, testing.\n\n"
    "You are reviewing YOUR OWN code - the agent system that YOU run on. "
    "Be brutally honest about what works, what doesn't, and what needs fixing."
)


def build_audit_prompt(agent_name: str, code_files: dict[str, str], file_tree: str) -> str:
    """Build the audit prompt for a specific agent."""

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

    # Build code context — truncate large files to 150 lines
    code_sections = []
    for fname in selected:
        if fname in code_files:
            content = code_files[fname]
            lines = content.split("\n")
            if len(lines) > 150:
                content = "\n".join(lines[:150]) + f"\n# ... truncated ({len(lines)} total lines)"
            code_sections.append(f"### FILE: {fname}\n```python\n{content}\n```")

    code_block = "\n\n".join(code_sections)

    return f"""ENGINEERING AUDIT - Agent Infrastructure
Agent: {agent_name.upper()}
Date: {datetime.now().strftime("%Y-%m-%d")}

PROJECT STRUCTURE:
{file_tree}

TOTAL: ~28,000 LOC across 75 Python files

STACK: Python 3.13, FastAPI, SQLAlchemy, SQLite, aiohttp
3 LLM providers: DeepSeek, Qwen, Perplexity (24 API keys with rotation)

CODE TO AUDIT:
{code_block}

AUDIT CATEGORIES (rate 1-10 each):

1. Architecture & Modularity - separation, deps, circular imports, dead modules
2. LLM Connection Layer - error handling, retry, circuit breakers, key rotation
3. Prompt Engineering - templates, context building, parsing, few-shot examples
4. Security & Safety - injection protection, output validation, key security
5. Memory & State - persistence, retrieval, consistency, leak risk
6. Consensus & Deliberation - protocol, cross-validation, confidence scoring
7. Testing & Observability - coverage, logging, metrics, tracing
8. Code Quality - types, docstrings, dead code, naming, DRY
9. Scalability & Performance - async, pooling, memory, bottlenecks
10. Missing Capabilities - critical gaps, missing tools, production risks

RESPOND IN JSON FORMAT ONLY:
{{
  "agent": "{agent_name}",
  "overall_score": 7.5,
  "scores": {{
    "architecture": 7, "llm_connections": 8, "prompt_engineering": 6,
    "security": 7, "memory": 5, "consensus": 8, "testing": 4,
    "code_quality": 7, "scalability": 6
  }},
  "critical_issues": [
    {{"category": "...", "severity": "HIGH|MEDIUM|LOW", "file": "...", "description": "...", "fix": "..."}}
  ],
  "improvement_suggestions": [
    {{"category": "...", "priority": "P0|P1|P2", "description": "...", "effort": "small|medium|large", "impact": "high|medium|low"}}
  ],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "missing_tools": ["..."],
  "recommended_next_steps": ["..."]
}}

Be thorough. Reference actual files where possible."""


# ═══════════════════════════════════════════════════════════════════
# DIRECT API CALLS (httpx, bypassing connections.py)
# ═══════════════════════════════════════════════════════════════════


async def call_api(agent_name: str, prompt: str) -> dict:
    """Call LLM API directly via httpx."""
    subsection(f"{agent_name.upper()} - Engineering Audit")

    cfg = API_CONFIG[agent_name]
    api_key = os.getenv(cfg["key_env"], "")
    if not api_key:
        print("  SKIP: no API key")
        return {"status": "skipped", "error": "no API key"}

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"  [{agent_name}] Sending request (attempt {attempt})...")
            print(f"  [{agent_name}] URL: {cfg['url']}")
            print(f"  [{agent_name}] Model: {cfg['model']}")
            print(f"  [{agent_name}] Prompt: {len(prompt)} chars (~{len(prompt) // 4} tokens)")

            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
                start = time.time()
                resp = await client.post(cfg["url"], json=payload, headers=headers)
                elapsed = time.time() - start

            print(f"  [{agent_name}] Status: {resp.status_code} ({elapsed:.1f}s)")

            if resp.status_code != 200:
                error_text = resp.text[:500]
                print(f"  [{agent_name}] Error body: {error_text}")

                is_retryable = resp.status_code in (429, 503, 502, 500)
                if is_retryable and attempt < max_retries:
                    wait = 30 * attempt
                    print(f"  Retryable ({resp.status_code}). Waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue

                return {
                    "status": "error",
                    "error": f"HTTP {resp.status_code}: {error_text}",
                    "agent": agent_name,
                }

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            print(f"  [{agent_name}] Response: {len(content)} chars")
            print(f"  [{agent_name}] Tokens: {usage.get('total_tokens', '?')}")
            print(f"  [{agent_name}] First 300 chars: {content[:300]}...")

            # Parse JSON from response
            audit_data = extract_json(content)
            if audit_data:
                print(f"  [{agent_name}] JSON parsed: OK (score={audit_data.get('overall_score', '?')})")
            else:
                print(f"  [{agent_name}] JSON parse FAILED, storing raw text")
                audit_data = {"raw_response": content}

            audit_data["_meta"] = {
                "agent": agent_name,
                "model": data.get("model", cfg["model"]),
                "tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "latency_s": round(elapsed, 2),
                "timestamp": datetime.now().isoformat(),
            }

            return audit_data

        except httpx.TimeoutException as e:
            print(f"  [{agent_name}] TIMEOUT (attempt {attempt}): {e}")
            if attempt < max_retries:
                wait = 30 * attempt
                print(f"  Waiting {wait}s before retry...")
                await asyncio.sleep(wait)
            else:
                return {"status": "error", "error": f"timeout: {e}", "agent": agent_name}

        except Exception as e:
            print(f"  [{agent_name}] ERROR (attempt {attempt}): {type(e).__name__}: {e}")
            if attempt < max_retries:
                wait = 30 * attempt
                print(f"  Waiting {wait}s before retry...")
                await asyncio.sleep(wait)
            else:
                import traceback

                traceback.print_exc()
                return {"status": "error", "error": str(e), "agent": agent_name}

    return {"status": "error", "error": "max retries exceeded", "agent": agent_name}


def extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response text."""
    import re

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for pattern in [r"```json\s*\n(.*?)\n```", r"```\s*\n(.*?)\n```"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════


async def main():
    section("ENGINEERING AUDIT - Agent Infrastructure")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Auditors: DeepSeek, Qwen, Perplexity")
    print("  Focus: Software engineering (NOT trading logic)")
    print("  Method: Direct httpx calls (no connections.py)")

    # Step 1: Collect code
    section("Step 1: Collecting Code")
    code_files = collect_code_for_audit()
    file_tree = build_file_tree()

    # Step 2: Build prompts
    section("Step 2: Building Audit Prompts")
    prompts = {}
    for agent in ["deepseek", "qwen", "perplexity"]:
        prompt = build_audit_prompt(agent, code_files, file_tree)
        prompts[agent] = prompt
        est_tokens = len(prompt) // 4
        print(f"  {agent}: {len(prompt)} chars (~{est_tokens} tokens)")

    # Step 3: Run audits sequentially
    section("Step 3: Running Audits")
    results = {}
    total_start = time.time()

    for agent_name in ["deepseek", "qwen", "perplexity"]:
        result = await call_api(agent_name, prompts[agent_name])
        results[agent_name] = result
        if agent_name != "perplexity":
            print("  [Pause 5s between agents]")
            await asyncio.sleep(5)

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

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)

    print(f"  Saved to: {output_file}")

    for agent_name, data in results.items():
        raw = data.get("raw_response", "")
        if raw:
            raw_file = output_dir / f"audit_raw_{agent_name}.txt"
            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(raw)
            print(f"  Raw text: {raw_file}")

    # Step 5: Summary
    section("AUDIT SUMMARY")
    for agent, data in results.items():
        status = data.get("status", "ok")
        if status in ("error", "skipped"):
            print(f"  [{agent.upper():11s}] {status}: {data.get('error', '')}")
        else:
            score = data.get("overall_score", "?")
            critical = len(data.get("critical_issues", []))
            suggestions = len(data.get("improvement_suggestions", []))
            strengths = len(data.get("strengths", []))
            weaknesses = len(data.get("weaknesses", []))
            tokens = data.get("_meta", {}).get("tokens", "?")
            latency = data.get("_meta", {}).get("latency_s", "?")
            print(
                f"  [{agent.upper():11s}] Score: {score}/10 | "
                f"Critical: {critical} | Suggestions: {suggestions} | "
                f"Strengths: {strengths} | Weaknesses: {weaknesses} | "
                f"Tokens: {tokens} | Time: {latency}s"
            )

    print(f"\n  Total time: {total_elapsed:.1f}s")
    print(f"  Results: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
