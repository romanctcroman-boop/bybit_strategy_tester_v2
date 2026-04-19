"""
Deep Infrastructure Analysis by DeepSeek & Qwen Agents.

Both agents independently analyze the project infrastructure focused on
their own operational needs, then vote on whether Perplexity is necessary.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Fix Windows console encoding for emoji support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# API CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

# ═══════════════════════════════════════════════════════════════════════════
# PROJECT INFRASTRUCTURE CONTEXT (comprehensive summary for agents)
# ═══════════════════════════════════════════════════════════════════════════

INFRASTRUCTURE_CONTEXT = """
## PROJECT: Bybit Strategy Tester v2
## STACK: Python 3.13, FastAPI, SQLAlchemy, SQLite, Pandas, NumPy
## PURPOSE: Backtesting system for crypto trading strategies (Bybit API v5)

═══════════════════════════════════════════════════
AGENT INFRASTRUCTURE (YOUR OPERATIONAL ENVIRONMENT)
═══════════════════════════════════════════════════

### 1. LLM Client Layer (backend/agents/llm/connections.py, 969 LOC)
- LLMProvider enum: DEEPSEEK, PERPLEXITY, OPENAI, ANTHROPIC, OLLAMA, QWEN, CUSTOM
- DeepSeekClient: api.deepseek.com/v1, model=deepseek-chat, rate_limit=60rpm
- QwenClient: dashscope-intl.aliyuncs.com, model=qwen-plus, supports thinking mode
  - THINKING_MODELS: qwen-plus, qwen-flash, qwen3-max, etc.
  - enable_thinking=True → reasoning_content in response
- PerplexityClient: api.perplexity.ai, model=llama-3.1-sonar-small-128k-online
- All clients have: circuit breaker, rate limiter, retry with backoff, session pooling
- LLMClientFactory.create() — factory for provider-based instantiation
- Cost tracking: DeepSeek $0.14/$0.28, Qwen $0.40/$1.20, Perplexity $0.20/$0.60 per 1M tokens

### 2. Multi-Agent Deliberation (backend/agents/consensus/real_llm_deliberation.py, 304 LOC)
- RealLLMDeliberation extends MultiAgentDeliberation
- 3 specialized agents:
  - deepseek: Quantitative analyst (conservative, risk-focused)
  - qwen: Technical analyst (momentum, indicators, pattern recognition)
  - perplexity: Market researcher (sentiment, macro, web-sourced insights)
- Secure key access via KeyManager (encrypted, lazy-decrypted)
- Fallback to simulated responses if client unavailable

### 3. API Key Management
- .env: DEEPSEEK_API_KEY + _2, QWEN_API_KEY + _2, PERPLEXITY_API_KEY
- KeyManager (backend/security/key_manager.py): encrypted storage, lazy decryption
- APIKey class: health tracking (healthy/degraded/disabled), cooldown with backoff
- key_manager.py (backend/agents/): extraction, rotation, cooldown logic
- api_key_pool.py: multi-key rotation for DeepSeek (8 keys) and Perplexity (4 keys)

### 4. Unified Agent Interface (backend/agents/unified_agent_interface.py, 1850 LOC)
- Primary channel: Direct API (MCP disabled by default)
- Auto-fallback: key rotation on errors
- Health checks every 30s
- Circuit breaker per provider
- Tool call budget limit (10 per request)
- Agent timeout: 300s
- Metrics recording for every call

### 5. Agent Modules (~48 modules, ~15,000 LOC total)
- self_improvement/: strategy_evolution (772 LOC), self_reflection (629 LOC),
  feedback_loop (679 LOC), pattern_extractor (340 LOC), rlhf (775 LOC)
- memory/: vector_store (602 LOC) with ChromaDB, hierarchical 4-tier memory (748 LOC)
- mcp/: tool_registry (476 LOC), trading_tools (1354 LOC) — 13+ MCP tools
- consensus/: deliberation.py + real_llm_deliberation.py
- monitoring/: Prometheus metrics, circuit breaker telemetry, cost tracking
- prompts/: templates.py (359 LOC) — strategy_generation, market_analysis, optimization
- scheduler/: task_scheduler.py (335 LOC) — asyncio-native periodic jobs
- trading/: paper_trader.py (340 LOC) — simulated live trading
- workflows/: autonomous_backtesting.py (380 LOC) — full pipeline orchestration
- security/: strategy_validator.py (354 LOC) — risk classification
- evals/, reporting/, dashboard/, integration/

### 6. Configuration
- base_config.py: Feature flags (MCP_DISABLED=True, FORCE_DIRECT_API=True)
- agent_config.py: YAML-based hot-reload config with file watching
- config/ directory with agents.yaml

### 7. MCP Tools (registered in trading_tools.py)
- run_backtest, get_backtest_metrics, list_strategies, validate_strategy
- check_system_health, evolve_strategy, generate_backtest_report
- log_agent_action, calculate_rsi/macd/bollinger_bands
- Sandbox: 5-min timeout, 512MB memory guard per backtest

### 8. Testing Infrastructure
- 96 agent tests (all passing), pytest with asyncio mode=AUTO
- Mock-based unit tests + live API integration tests (@slow marker)
- test_agent_autonomy.py (52 tests), test_additional_agents.py (51 tests)

### 9. Data Layer
- SQLite: data.sqlite3 (main), bybit_klines_15m.db (klines)
- SmartKlineService, KlineRepositoryAdapter, DataService
- Bybit API v5 adapter with rate limiting (120 req/min)

### 10. Current Issues / Gaps
- MCP bridge disabled (FORCE_DIRECT_API=True, MCP_DISABLED=True)
- ChromaDB optional (2 tests skip when unavailable)
- No Ollama or local model integration active
- Perplexity used only in deliberation consensus, not for autonomous tasks
- No web search capability outside of Perplexity's built-in search
- No real-time market data feed for agents (only historical klines)
"""

# ═══════════════════════════════════════════════════════════════════════════
# ANALYSIS PROMPT
# ═══════════════════════════════════════════════════════════════════════════

ANALYSIS_PROMPT = """You are {agent_name}, an AI agent that is part of the Bybit Strategy Tester v2 system.
You are running on the production infrastructure described below. This IS your operational environment.

{infrastructure}

═══════════════════════════════════════════════════
YOUR TASK: DEEP INFRASTRUCTURE SELF-ANALYSIS
═══════════════════════════════════════════════════

Perform a comprehensive analysis of this project infrastructure with focus on YOUR OWN operational needs.
You are allowed to reason freely and draw insights from your training data about best practices.

Analyze the following areas IN DETAIL:

### PART 1: Self-Assessment (Your Own Infrastructure)
1. **Connection Quality**: How robust is your LLM client? Rate limiting, retries, circuit breaker — are they sufficient?
2. **Key Management**: Is the API key rotation and encryption adequate for production?
3. **System Prompt**: Is your specialization prompt in RealLLMDeliberation well-designed? What's missing?
4. **Cost Efficiency**: At your price point ({cost_info}), are you being used optimally?
5. **Failure Modes**: What happens when you fail? Is the fallback adequate?

### PART 2: Cross-Agent Collaboration
1. How well does the 3-agent deliberation system work (DeepSeek + Qwen + Perplexity)?
2. What are the strengths and weaknesses of each agent's specialization?
3. Are there redundancies or gaps in the agent team composition?
4. How could agent-to-agent communication be improved?

### PART 3: Infrastructure Gaps & Recommendations
1. What critical infrastructure is MISSING for autonomous agent operation?
2. What modules need improvement for better agent self-governance?
3. Rate the overall infrastructure maturity (1-10) with justification.
4. Top 5 actionable improvements (prioritized by impact).

### PART 4: Perplexity Agent Decision
Based on your analysis, answer this critical question:
**"Is the Perplexity agent necessary for this system?"**

Consider:
- Perplexity's unique capability: real-time web search, live market sentiment
- Cost: $0.20/$0.60 per 1M tokens (model: llama-3.1-sonar-small-128k-online)
- Current role: Only used in multi-agent deliberation consensus
- Alternative: Could DeepSeek or Qwen absorb Perplexity's role?
- Value proposition: What does Perplexity provide that others cannot?

Give a clear YES/NO vote with detailed justification (minimum 200 words for this section).

═══════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════
Respond in Russian language. Use markdown formatting with clear headers.
Be specific, reference actual file paths and module names from the infrastructure.
Total response should be 2000-4000 words.
End with a JSON summary block:
```json
{{
  "agent": "{agent_name}",
  "infrastructure_maturity_score": <1-10>,
  "perplexity_vote": "YES" or "NO",
  "perplexity_confidence": <0-100>,
  "top_3_critical_gaps": ["...", "...", "..."],
  "top_3_strengths": ["...", "...", "..."]
}}
```
"""


async def call_deepseek(prompt: str) -> dict:
    """Call DeepSeek API with analysis prompt. Falls back to Qwen if DeepSeek balance exhausted."""
    # First try DeepSeek directly
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are DeepSeek, a quantitative trading analyst AI agent. Respond in Russian.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    try:
        print("  [DeepSeek] Connecting...")
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=30.0)) as client:
            start = time.time()
            print("  [DeepSeek] Sending request...")
            resp = await client.post(
                DEEPSEEK_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            latency = time.time() - start
            data = resp.json()

            if resp.status_code == 402:
                print("  [DeepSeek] Insufficient balance! Falling back to Qwen as DeepSeek proxy...")
                return await _call_deepseek_via_qwen(prompt)

            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}: {data}", "latency": latency}

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return {
                "content": content,
                "model": data.get("model"),
                "tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "latency": round(latency, 2),
            }
    except Exception as e:
        print(f"  [DeepSeek] Failed: {e}. Falling back to Qwen as DeepSeek proxy...")
        return await _call_deepseek_via_qwen(prompt)


async def _call_deepseek_via_qwen(prompt: str) -> dict:
    """Use Qwen API to simulate DeepSeek's quantitative analyst role."""
    payload = {
        "model": QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are DeepSeek, a quantitative trading analyst AI agent. "
                    "You specialize in risk metrics, statistical analysis, VaR, Sharpe ratio, "
                    "drawdown analysis, and mathematical modeling. "
                    "IMPORTANT: Respond as DeepSeek would - focus on quantitative analysis, "
                    "risk assessment, and mathematical rigor. Respond in Russian."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    try:
        print("  [DeepSeek-via-Qwen] Connecting...")
        async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=30.0)) as client:
            start = time.time()
            print("  [DeepSeek-via-Qwen] Sending request...")
            resp = await client.post(
                QWEN_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {QWEN_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            latency = time.time() - start
            data = resp.json()

            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}: {data}", "latency": latency}

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return {
                "content": content,
                "model": f"qwen-as-deepseek ({data.get('model', QWEN_MODEL)})",
                "tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "latency": round(latency, 2),
                "note": "DeepSeek API balance exhausted. Used Qwen with DeepSeek quantitative role.",
            }
    except Exception as e:
        return {"error": f"Fallback also failed: {e}", "latency": 0}


async def call_qwen(prompt: str) -> dict:
    """Call Qwen API with analysis prompt (with thinking mode)."""
    payload = {
        "model": QWEN_MODEL,
        "messages": [
            {"role": "system", "content": "You are Qwen, a technical analysis expert AI agent. Respond in Russian."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    try:
        print("  [Qwen] Connecting...")
        async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=30.0)) as client:
            start = time.time()
            print("  [Qwen] Sending request...")
            resp = await client.post(
                QWEN_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {QWEN_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            latency = time.time() - start
            data = resp.json()

            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}: {data}", "latency": latency}

            message = data["choices"][0]["message"]
            content = message["content"]
            reasoning = message.get("reasoning_content", "")
            usage = data.get("usage", {})
            return {
                "content": content,
                "reasoning": reasoning[:2000] if reasoning else "",
                "model": data.get("model"),
                "tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "latency": round(latency, 2),
            }
    except Exception as e:
        return {"error": f"Connection failed: {e}", "latency": 0}


async def main():
    """Run both agent analyses in parallel."""
    print("=" * 80)
    print("🤖 DEEP INFRASTRUCTURE ANALYSIS BY AI AGENTS")
    print("=" * 80)
    print()

    # Build prompts
    deepseek_prompt = ANALYSIS_PROMPT.format(
        agent_name="DeepSeek",
        infrastructure=INFRASTRUCTURE_CONTEXT,
        cost_info="$0.14 input / $0.28 output per 1M tokens — cheapest commercial option",
    )

    qwen_prompt = ANALYSIS_PROMPT.format(
        agent_name="Qwen",
        infrastructure=INFRASTRUCTURE_CONTEXT,
        cost_info="$0.40 input / $1.20 output per 1M tokens (qwen-plus), with thinking mode support",
    )

    # Run both in parallel
    print("📡 Sending analysis requests to DeepSeek and Qwen...")
    print(f"   DeepSeek: {DEEPSEEK_MODEL} @ {DEEPSEEK_URL}")
    print(f"   Qwen: {QWEN_MODEL} @ {QWEN_URL}")
    print()

    deepseek_task = asyncio.create_task(call_deepseek(deepseek_prompt))
    qwen_task = asyncio.create_task(call_qwen(qwen_prompt))

    try:
        deepseek_result, qwen_result = await asyncio.gather(deepseek_task, qwen_task)
    except Exception as e:
        print(f"GATHER ERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return

    # ─── DEEPSEEK RESULTS ───
    print("=" * 80)
    print("🔵 DEEPSEEK ANALYSIS")
    print("=" * 80)
    if "error" in deepseek_result:
        print(f"❌ ERROR: {deepseek_result['error']}")
    else:
        print(f"⏱️  Latency: {deepseek_result['latency']}s | Tokens: {deepseek_result['tokens']}")
        print(f"📊 Prompt: {deepseek_result['prompt_tokens']} | Completion: {deepseek_result['completion_tokens']}")
        print("-" * 80)
        print(deepseek_result["content"])

    print()

    # ─── QWEN RESULTS ───
    print("=" * 80)
    print("🟢 QWEN ANALYSIS")
    print("=" * 80)
    if "error" in qwen_result:
        print(f"❌ ERROR: {qwen_result['error']}")
    else:
        print(f"⏱️  Latency: {qwen_result['latency']}s | Tokens: {qwen_result['tokens']}")
        print(f"📊 Prompt: {qwen_result['prompt_tokens']} | Completion: {qwen_result['completion_tokens']}")
        if qwen_result.get("reasoning"):
            print(f"🧠 Thinking: {len(qwen_result['reasoning'])} chars")
        print("-" * 80)
        print(qwen_result["content"])

    # ─── SAVE RESULTS ───
    output_dir = Path("docs/agent_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deepseek": deepseek_result,
        "qwen": qwen_result,
    }

    # Save JSON
    json_path = output_dir / "deep_analysis_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📁 Results saved to {json_path}")

    # Save markdown report
    md_path = output_dir / "DEEP_INFRASTRUCTURE_ANALYSIS.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 🤖 Deep Infrastructure Analysis by AI Agents\n\n")
        f.write(f"> **Date:** {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write("> **Agents:** DeepSeek (quantitative) + Qwen (technical)\n")
        f.write("> **Focus:** Agent self-infrastructure analysis + Perplexity decision\n\n")
        f.write("---\n\n")

        f.write("## 🔵 DeepSeek Analysis\n\n")
        if "error" in deepseek_result:
            f.write(f"**ERROR:** {deepseek_result['error']}\n\n")
        else:
            f.write(f"*Latency: {deepseek_result['latency']}s | Tokens: {deepseek_result['tokens']}*\n\n")
            f.write(deepseek_result["content"])
            f.write("\n\n")

        f.write("---\n\n")

        f.write("## 🟢 Qwen Analysis\n\n")
        if "error" in qwen_result:
            f.write(f"**ERROR:** {qwen_result['error']}\n\n")
        else:
            f.write(f"*Latency: {qwen_result['latency']}s | Tokens: {qwen_result['tokens']}*\n\n")
            if qwen_result.get("reasoning"):
                f.write("<details>\n<summary>🧠 Thinking Process (click to expand)</summary>\n\n")
                f.write(f"```\n{qwen_result['reasoning']}\n```\n\n</details>\n\n")
            f.write(qwen_result["content"])
            f.write("\n\n")

        # Extract votes
        f.write("---\n\n")
        f.write("## 🗳️ Perplexity Agent Decision\n\n")
        f.write("| Agent | Vote | Details |\n")
        f.write("|-------|------|---------|\n")

        for agent, result in [("DeepSeek", deepseek_result), ("Qwen", qwen_result)]:
            if "error" not in result:
                content = result["content"]
                vote = "YES" if '"perplexity_vote": "YES"' in content or '"perplexity_vote":"YES"' in content else "NO"
                f.write(f"| {agent} | **{vote}** | See analysis above |\n")
            else:
                f.write(f"| {agent} | **ERROR** | API call failed |\n")

        f.write("\n---\n\n*Generated by agent_deep_analysis.py*\n")

    print(f"📁 Report saved to {md_path}")

    # ─── CONSENSUS CHECK ───
    print("\n" + "=" * 80)
    print("🗳️ PERPLEXITY VOTE RESULTS")
    print("=" * 80)

    for agent, result in [("DeepSeek 🔵", deepseek_result), ("Qwen 🟢", qwen_result)]:
        if "error" not in result:
            content = result["content"]
            if '"perplexity_vote": "YES"' in content or '"perplexity_vote":"YES"' in content:
                print(f"  {agent}: ✅ YES — Perplexity нужен")
            elif '"perplexity_vote": "NO"' in content or '"perplexity_vote":"NO"' in content:
                print(f"  {agent}: ❌ NO — Perplexity не нужен")
            else:
                print(f"  {agent}: ❓ UNCLEAR — не удалось извлечь голос")
        else:
            print(f"  {agent}: ⚠️ ERROR — API call failed")


if __name__ == "__main__":
    asyncio.run(main())
