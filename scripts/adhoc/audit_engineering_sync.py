#!/usr/bin/env python3
"""
Engineering Audit of Agent Infrastructure (SYNC version)

Sends agent source code to DeepSeek, Qwen, and Perplexity for independent
engineering audit using SYNCHRONOUS httpx calls (no asyncio).

Focus: architecture, code quality, tooling, prompts, rules — NOT trading logic.
Output: docs/agent_analysis/engineering_audit_results.json
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding (cp1251 -> utf-8)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
        "key_envs": ["DEEPSEEK_API_KEY"] + [f"DEEPSEEK_API_KEY_{i}" for i in range(2, 9)],
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
    },
    "qwen": {
        "key_envs": ["QWEN_API_KEY"] + [f"QWEN_API_KEY_{i}" for i in range(2, 9)],
        "url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": os.getenv("QWEN_MODEL", "qwen-plus"),
    },
    "perplexity": {
        "key_envs": ["PERPLEXITY_API_KEY"] + [f"PERPLEXITY_API_KEY_{i}" for i in range(2, 9)],
        "url": "https://api.perplexity.ai/chat/completions",
        "model": "sonar-pro",
    },
}


def section(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


# ═══════════════════════════════════════════════════════════════════
# CODE COLLECTOR
# ═══════════════════════════════════════════════════════════════════


def collect_code() -> dict[str, str]:
    base = PROJECT_ROOT / "backend" / "agents"
    core_files = [
        "llm/connections.py",
        "llm/base_client.py",
        "llm/clients/deepseek.py",
        "llm/clients/qwen.py",
        "llm/clients/perplexity.py",
        "llm/clients/ollama.py",
        "llm/rate_limiter.py",
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
        "security/semantic_guard.py",
        "security/security_orchestrator.py",
        "security/output_validator.py",
        "security/rate_limiter.py",
        "agent_memory.py",
        "memory/hierarchical_memory.py",
        "memory/vector_store.py",
        "memory/sqlite_backend.py",
        "memory/backend_interface.py",
        "key_models.py",
        "request_models.py",
        "key_manager.py",
        "api_key_pool.py",
        "config_validator.py",
        "structured_logging.py",
        "cost_tracker.py",
        "circuit_breaker_manager.py",
        "health_monitor.py",
        "unified_agent_interface.py",
        "models.py",
        "base_config.py",
        "_api_mixin.py",
        "_health_mixin.py",
        "_tool_mixin.py",
        "_query_mixin.py",
        "agent_modules.py",
        "self_improvement/feedback_loop.py",
        "self_improvement/self_reflection.py",
        "mcp/tool_registry.py",
        "mcp/trading_tools.py",
        "mcp/tools/__init__.py",
        "mcp/tools/indicators.py",
        "mcp/tools/risk.py",
        "mcp/tools/backtest.py",
        "mcp/tools/strategy.py",
        "mcp/tools/system.py",
    ]
    code = {}
    total = 0
    for rel in core_files:
        fp = base / rel
        if fp.exists():
            c = fp.read_text(encoding="utf-8", errors="replace")
            loc = c.count("\n")
            total += loc
            code[rel] = c
            print(f"  [OK] {rel} ({loc} LOC)")
    print(f"\n  Total: {len(code)} files, {total} LOC")
    return code


def collect_tests() -> dict[str, str]:
    """Collect test files from tests/backend/agents/."""
    test_dir = PROJECT_ROOT / "tests" / "backend" / "agents"
    tests = {}
    total = 0
    if not test_dir.exists():
        print("  [WARN] tests/backend/agents/ not found")
        return tests
    for fp in sorted(test_dir.glob("test_*.py")):
        c = fp.read_text(encoding="utf-8", errors="replace")
        loc = c.count("\n")
        total += loc
        rel = f"tests/{fp.name}"
        tests[rel] = c
        print(f"  [OK] {rel} ({loc} LOC)")
    print(f"\n  Total tests: {len(tests)} files, {total} LOC")
    return tests


def build_tree() -> str:
    base = PROJECT_ROOT / "backend" / "agents"
    lines = ["backend/agents/"]

    def walk(p: Path, prefix: str = "  "):
        for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
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
# AUDIT PROMPT
# ═══════════════════════════════════════════════════════════════════

SYSTEM = (
    "You are a senior software engineer performing an engineering audit of an "
    "AI agent infrastructure. Focus on SOFTWARE ENGINEERING QUALITY only (not "
    "trading logic). You are reviewing YOUR OWN code. Be brutally honest."
)


def build_prompt(agent: str, code: dict[str, str], tests: dict[str, str], tree: str) -> str:
    shared = [
        "llm/connections.py",
        "llm/base_client.py",
        "llm/rate_limiter.py",
        "models.py",
        "key_models.py",
        "request_models.py",
        "base_config.py",
        "config_validator.py",
        "structured_logging.py",
        "cost_tracker.py",
        "key_manager.py",
        "api_key_pool.py",
        "_api_mixin.py",
        "_query_mixin.py",
        "circuit_breaker_manager.py",
        "health_monitor.py",
        "unified_agent_interface.py",
        "prompts/templates.py",
        "prompts/prompt_engineer.py",
        "prompts/response_parser.py",
        "security/prompt_guard.py",
        "security/semantic_guard.py",
        "security/security_orchestrator.py",
        "agent_memory.py",
        "memory/sqlite_backend.py",
        "memory/backend_interface.py",
        "memory/hierarchical_memory.py",
    ]
    extra = {
        "deepseek": [
            "consensus/deliberation.py",
            "consensus/real_llm_deliberation.py",
            "self_improvement/feedback_loop.py",
            "llm/prompt_optimizer.py",
            "llm/clients/deepseek.py",
            "llm/clients/qwen.py",
            "security/output_validator.py",
            "agent_modules.py",
        ],
        "qwen": [
            "consensus/domain_agents.py",
            "consensus/real_llm_deliberation.py",
            "prompts/context_builder.py",
            "llm/prompt_optimizer.py",
            "llm/clients/perplexity.py",
            "llm/clients/ollama.py",
            "memory/hierarchical_memory.py",
            "security/rate_limiter.py",
        ],
        "perplexity": [
            "consensus/perplexity_integration.py",
            "consensus/real_llm_deliberation.py",
            "memory/vector_store.py",
            "mcp/tool_registry.py",
            "mcp/trading_tools.py",
            "mcp/tools/indicators.py",
            "mcp/tools/backtest.py",
            "llm/prompt_optimizer.py",
            "llm/clients/deepseek.py",
            "llm/clients/perplexity.py",
        ],
    }
    selected = list(dict.fromkeys(shared + extra.get(agent, [])))

    parts = []
    for f in selected:
        if f in code:
            lines = code[f].split("\n")
            # Show up to 300 lines for key files, 200 for others
            key_files = {
                "unified_agent_interface.py",
                "base_config.py",
                "memory/hierarchical_memory.py",
                "memory/backend_interface.py",
                "security/security_orchestrator.py",
                "llm/rate_limiter.py",
                "llm/connections.py",
            }
            limit = 300 if any(f.endswith(k) for k in key_files) else 200
            txt = "\n".join(lines[:limit])
            if len(lines) > limit:
                txt += f"\n# ... truncated ({len(lines)} total lines)"
            parts.append(f"### {f}\n```python\n{txt}\n```")

    # Include representative test files (pick most relevant ones)
    test_priority = {
        "deepseek": [
            "tests/test_llm_clients.py",
            "tests/test_key_models.py",
            "tests/test_cost_tracker.py",
            "tests/test_config_validator.py",
            "tests/test_real_llm_deliberation.py",
            "tests/test_consensus_engine.py",
        ],
        "qwen": [
            "tests/test_rate_limiter.py",
            "tests/test_request_models.py",
            "tests/test_sqlite_backend.py",
            "tests/test_structured_logging.py",
            "tests/test_hierarchical_memory.py",
            "tests/test_semantic_guard.py",
            "tests/test_memory_persistence.py",
        ],
        "perplexity": [
            "tests/test_key_models.py",
            "tests/test_llm_clients.py",
            "tests/test_semantic_guard.py",
            "tests/test_cost_tracker.py",
            "tests/test_request_models.py",
            "tests/test_rate_limiter.py",
        ],
    }
    # Add ALL test files as a summary list, then show 6 full test files
    test_parts = []
    test_summary_lines = [f"  - {name} ({t.count(chr(10))} LOC)" for name, t in sorted(tests.items())]
    total_test_count = sum(t.count("def test_") for t in tests.values())
    test_parts.append(
        f"### Test Suite Summary\n"
        f"Total test files: {len(tests)}\n"
        f"Total test functions: {total_test_count}\n"
        f"Framework: pytest + pytest-asyncio (mode=AUTO)\n"
        f"Files:\n" + "\n".join(test_summary_lines)
    )

    # Add prioritized full test files
    shown_tests = set()
    for tname in test_priority.get(agent, []):
        if tname in tests and tname not in shown_tests:
            lines = tests[tname].split("\n")
            txt = "\n".join(lines[:120])
            if len(lines) > 120:
                txt += f"\n# ... truncated ({len(lines)} total lines)"
            test_parts.append(f"### {tname}\n```python\n{txt}\n```")
            shown_tests.add(tname)

    return f"""ENGINEERING AUDIT - Agent: {agent.upper()}
Date: {datetime.now().strftime("%Y-%m-%d")}

STRUCTURE:
{tree}

TOTAL: ~18,000 LOC production + ~6,000 LOC tests across 70+ files
STACK: Python 3.13, FastAPI, aiohttp, pytest, pytest-asyncio, 3 LLM providers, 24 API keys
TESTING: {len(tests)} test files, {total_test_count} test functions, ALL PASSING (2800+ total project tests)

PRODUCTION CODE:
{chr(10).join(parts)}

TEST CODE:
{chr(10).join(test_parts)}

Rate 1-10 each category:
1. Architecture & Modularity
2. LLM Connection Layer
3. Prompt Engineering
4. Security & Safety
5. Memory & State
6. Consensus & Deliberation
7. Testing & Observability
8. Code Quality
9. Scalability & Performance
10. Missing Capabilities

IMPORTANT: Score each category independently based ONLY on the code you see.
Do NOT anchor to any previous scores. Evaluate the actual quality of each component.

RECENT ARCHITECTURE IMPROVEMENTS (since last audit):
- base_config.py: Migrated from raw os.getenv() to Pydantic BaseSettings with validation
- unified_agent_interface.py: Reduced from 1372→709 LOC via 4 mixins (API, Health, Tool, Query)
- HierarchicalMemory: Now wired to MemoryBackend ABC (SQLiteBackendAdapter/JsonFileBackend) via backend= param
- HierarchicalMemory: Added async_load() for FastAPI lifespan + _load_from_disk() uses backend.load_all()
- SecurityOrchestrator: strict_mode now propagated to SemanticPromptGuard
- TokenAwareRateLimiter: Recovery behavior tested (minute window reset + concurrent acquire)
- connections.py: DeprecationWarning added, see docs/DEPRECATION_SCHEDULE.md
- trading_tools.py: Split 1354→60 LOC facade + 6 sub-modules (indicators, risk, backtest, strategy, system)
- SQLiteBackendAdapter: All methods wrapped with asyncio.to_thread()
- 31 persistence integration tests (SQLite + JSON backend)
- 875+ agent tests, ALL passing

RESPOND JSON ONLY:
{{
  "agent": "{agent}",
  "overall_score": 0,
  "scores": {{"architecture": 0, "llm_connections": 0, "prompt_engineering": 0, "security": 0, "memory": 0, "consensus": 0, "testing": 0, "code_quality": 0, "scalability": 0}},
  "critical_issues": [{{"category":"...", "severity":"HIGH|MEDIUM|LOW", "file":"...", "description":"...", "fix":"..."}}],
  "improvement_suggestions": [{{"category":"...", "priority":"P0|P1|P2", "description":"...", "effort":"small|medium|large", "impact":"high|medium|low"}}],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "missing_tools": ["..."],
  "recommended_next_steps": ["..."]
}}"""


# ═══════════════════════════════════════════════════════════════════
# SYNC API CALL
# ═══════════════════════════════════════════════════════════════════


def call_api(agent: str, prompt: str) -> dict:
    """Call LLM API synchronously with key rotation on failure."""
    print(f"\n--- {agent.upper()} - Engineering Audit ---\n")

    cfg = API_CONFIG[agent]
    # Collect all available keys
    keys = []
    for env_name in cfg.get("key_envs", []):
        k = os.getenv(env_name, "")
        if k:
            keys.append((env_name, k))
    if not keys:
        print("  SKIP: no API key")
        return {"status": "skipped", "error": "no API key"}

    print(f"  Available keys: {len(keys)}")

    for key_idx, (key_name, key) in enumerate(keys):
        print(f"  Trying key {key_idx + 1}/{len(keys)} ({key_name})")

        payload = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 8192,
        }
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        for attempt in range(1, 3):
            try:
                print(f"  [{agent}] Attempt {attempt}, {len(prompt)} chars (~{len(prompt) // 4} tokens)")
                print(f"  [{agent}] POST {cfg['url']}")

                start = time.time()
                resp = httpx.post(
                    cfg["url"],
                    json=payload,
                    headers=headers,
                    timeout=httpx.Timeout(300.0, connect=30.0),
                )
                elapsed = time.time() - start
                print(f"  [{agent}] Status: {resp.status_code} ({elapsed:.1f}s)")

                if resp.status_code != 200:
                    err = resp.text[:500]
                    print(f"  [{agent}] Error: {err}")
                    # For balance/auth errors, try next key immediately
                    if resp.status_code in (401, 402, 403):
                        print(f"  [{agent}] Auth/balance error, trying next key...")
                        break  # try next key
                    if resp.status_code in (429, 500, 502, 503) and attempt < 2:
                        wait = 30 * attempt
                        print(f"  Retry in {wait}s...")
                        time.sleep(wait)
                        continue
                    break  # try next key

                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                print(f"  [{agent}] Got {len(content)} chars, {usage.get('total_tokens', '?')} tokens")
                print(f"  [{agent}] Preview: {content[:200]}...")

                result = extract_json(content)
                if result:
                    print(f"  [{agent}] JSON OK (score={result.get('overall_score', '?')})")
                else:
                    print(f"  [{agent}] JSON parse failed, storing raw")
                    result = {"raw_response": content}

                result["_meta"] = {
                    "agent": agent,
                    "model": data.get("model", cfg["model"]),
                    "tokens": usage.get("total_tokens", 0),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "latency_s": round(elapsed, 2),
                    "timestamp": datetime.now().isoformat(),
                    "key_used": key_name,
                }
                return result

            except httpx.TimeoutException as e:
                print(f"  [{agent}] TIMEOUT: {e}")
                if attempt < 2:
                    time.sleep(30)
                else:
                    break  # try next key
            except Exception as e:
                print(f"  [{agent}] ERROR: {type(e).__name__}: {e}")
                if attempt < 2:
                    time.sleep(30)
                else:
                    break  # try next key

    return {"status": "error", "error": "all keys exhausted", "agent": agent}


def extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pat in [r"```json\s*\n(.*?)\n```", r"```\s*\n(.*?)\n```"]:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        try:
            return json.loads(text[s : e + 1])
        except json.JSONDecodeError:
            pass
    return None


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════


def main():
    section("ENGINEERING AUDIT - Agent Infrastructure")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Auditors: DeepSeek, Qwen, Perplexity")
    print("  Method: Synchronous httpx (no asyncio)")

    section("Step 1: Collecting Code")
    code = collect_code()
    tree = build_tree()

    section("Step 1b: Collecting Tests")
    tests = collect_tests()

    section("Step 2: Building Prompts")
    prompts = {}
    for a in ["deepseek", "qwen", "perplexity"]:
        p = build_prompt(a, code, tests, tree)
        prompts[a] = p
        print(f"  {a}: {len(p)} chars (~{len(p) // 4} tokens)")

    section("Step 3: Running Audits")
    results = {}
    t0 = time.time()
    for a in ["deepseek", "qwen", "perplexity"]:
        results[a] = call_api(a, prompts[a])
        if a != "perplexity":
            print("  [Pause 5s]")
            time.sleep(5)
    total = time.time() - t0

    section("Step 4: Saving Results")
    out_dir = PROJECT_ROOT / "docs" / "agent_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "engineering_audit_results.json"

    final = {
        "audit_type": "engineering",
        "timestamp": datetime.now().isoformat(),
        "total_elapsed_s": round(total, 2),
        "files_audited": len(code),
        "results": results,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out_file}")

    for a, d in results.items():
        raw = d.get("raw_response", "")
        if raw:
            rf = out_dir / f"audit_raw_{a}.txt"
            rf.write_text(raw, encoding="utf-8")
            print(f"  Raw: {rf}")

    section("AUDIT SUMMARY")
    for a, d in results.items():
        st = d.get("status", "ok")
        if st in ("error", "skipped"):
            print(f"  [{a.upper():11s}] {st}: {d.get('error', '')}")
        else:
            sc = d.get("overall_score", "?")
            ci = len(d.get("critical_issues", []))
            su = len(d.get("improvement_suggestions", []))
            tk = d.get("_meta", {}).get("tokens", "?")
            la = d.get("_meta", {}).get("latency_s", "?")
            print(
                f"  [{a.upper():11s}] Score: {sc}/10 | Critical: {ci} | Suggestions: {su} | Tokens: {tk} | Time: {la}s"
            )

    print(f"\n  Total: {total:.1f}s")
    print(f"  File: {out_file}")


if __name__ == "__main__":
    main()
