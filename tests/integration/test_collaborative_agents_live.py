"""
Test: AI Agents Collaboratively Solve a Trading Strategy Task — LIVE API

Real DeepSeek + Qwen API calls. Two AI agent "personas" powered by
DIFFERENT LLM providers debate and collaborate on a trading strategy:

  - Agent-Q (Quantitative Analyst) → DeepSeek
  - Agent-T (Technical Analyst)    → Qwen (Alibaba Cloud Model Studio)

Pipeline:
1. Domain Expert Analysis — Agent-Q (DeepSeek) + Agent-T (Qwen) in parallel
2. Multi-Agent Deliberation — 2-round structured debate with cross-examination
3. Consensus Engine — merges the resulting strategy proposals

Requirements:
    - DEEPSEEK_API_KEY with balance
    - QWEN_API_KEY with balance (Singapore region: dashscope-intl)

Run:
    pytest tests/integration/test_collaborative_agents_live.py -v -s --timeout=180

Markers:
    @pytest.mark.slow   — excluded from fast test runs
    @pytest.mark.live   — requires real API keys
"""

from __future__ import annotations

import asyncio
import os
import time

import aiohttp
import pytest
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from backend.agents.consensus.consensus_engine import ConsensusEngine, ConsensusResult
from backend.agents.consensus.deliberation import (
    DeliberationResult,
    MultiAgentDeliberation,
    VotingStrategy,
)
from backend.agents.consensus.domain_agents import (
    AnalysisResult,
    RiskManagementAgent,
    TradingStrategyAgent,
)
from backend.agents.llm.connections import (
    DeepSeekClient,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    QwenClient,
)
from backend.agents.prompts.response_parser import (
    ExitCondition,
    ExitConditions,
    Signal,
    StrategyDefinition,
)

# ---------------------------------------------------------------------------
# Key detection + live probes
# ---------------------------------------------------------------------------

_DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
_QWEN_KEY = os.getenv("QWEN_API_KEY", "")
_HAS_DEEPSEEK = bool(_DEEPSEEK_KEY) and "YOUR" not in _DEEPSEEK_KEY
_HAS_QWEN = bool(_QWEN_KEY) and "YOUR" not in _QWEN_KEY


async def _probe_deepseek() -> tuple[bool, str]:
    """Minimal probe to verify the DeepSeek key has balance."""
    if not _HAS_DEEPSEEK:
        return False, "DEEPSEEK_API_KEY not set or placeholder"
    headers = {
        "Authorization": f"Bearer {_DEEPSEEK_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.deepseek.com/v1/chat/completions",
                json=body,
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    return True, "OK"
                text = await resp.text()
                return False, f"{resp.status}: {text[:120]}"
    except Exception as e:
        return False, str(e)


async def _probe_qwen() -> tuple[bool, str]:
    """Minimal probe to verify the Qwen key works (Singapore region)."""
    if not _HAS_QWEN:
        return False, "QWEN_API_KEY not set or placeholder"
    headers = {
        "Authorization": f"Bearer {_QWEN_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
                json=body,
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    return True, "OK"
                text = await resp.text()
                return False, f"{resp.status}: {text[:120]}"
    except Exception as e:
        return False, str(e)


# Module-level caches so we probe only once per session
_ds_probe: tuple[bool, str] | None = None
_qw_probe: tuple[bool, str] | None = None


async def _ensure_deepseek() -> None:
    """Skip the test if DeepSeek is not reachable."""
    global _ds_probe
    if _ds_probe is None:
        _ds_probe = await _probe_deepseek()
    ok, reason = _ds_probe
    if not ok:
        pytest.skip(f"DeepSeek API not available: {reason}")


async def _ensure_qwen() -> None:
    """Skip the test if Qwen is not reachable."""
    global _qw_probe
    if _qw_probe is None:
        _qw_probe = await _probe_qwen()
    ok, reason = _qw_probe
    if not ok:
        pytest.skip(f"Qwen API not available: {reason}")


async def _ensure_both() -> None:
    """Skip the test if either provider is not reachable."""
    await _ensure_deepseek()
    await _ensure_qwen()


# ---------------------------------------------------------------------------
# Client + ask_fn factories  (fresh per test — avoids closed-loop issues)
# ---------------------------------------------------------------------------

# Two distinct agent personas backed by DIFFERENT LLM providers
QUANT_SYSTEM = (
    "You are Agent-Q, a **quantitative trading analyst** powered by DeepSeek. "
    "Your expertise: statistical edge detection, Sharpe ratio optimisation, "
    "drawdown control, position sizing, Monte-Carlo simulation. "
    "You ALWAYS back claims with numbers. You prefer conservative approaches. "
    "Follow the EXACT response format specified in the user prompt."
)

TECH_SYSTEM = (
    "You are Agent-T, a **technical analysis expert** powered by Qwen. "
    "Your expertise: RSI, MACD, Bollinger Bands, momentum indicators, "
    "candlestick patterns, support/resistance, volume analysis. "
    "You focus on signal quality vs trade frequency trade-offs. "
    "You are willing to accept more risk for higher returns. "
    "Follow the EXACT response format specified in the user prompt."
)


def _make_deepseek_client(temperature: float = 0.7) -> DeepSeekClient:
    """Create a DeepSeek client for Agent-Q."""
    return DeepSeekClient(
        LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            api_key=_DEEPSEEK_KEY,
            model="deepseek-chat",
            temperature=temperature,
            max_tokens=1024,
            timeout_seconds=60,
        )
    )


def _make_qwen_client(temperature: float = 0.7) -> QwenClient:
    """Create a Qwen client for Agent-T (Singapore region)."""
    return QwenClient(
        LLMConfig(
            provider=LLMProvider.QWEN,
            api_key=_QWEN_KEY,
            model="qwen-plus",
            temperature=temperature,
            max_tokens=1024,
            timeout_seconds=60,
        )
    )


def _make_ask_fn(client: DeepSeekClient | QwenClient, system_prompt: str):
    """ask_fn(prompt) -> str  for domain agents."""
    provider_name = "DeepSeek" if isinstance(client, DeepSeekClient) else "Qwen"

    async def _ask(prompt: str) -> str:
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=prompt),
        ]
        resp = await client.chat(messages)
        logger.info(
            f"🤖 [{provider_name}] {resp.total_tokens} tok, {resp.latency_ms:.0f}ms, ${resp.estimated_cost:.4f}"
        )
        return resp.content

    return _ask


def _make_deliberation_ask_fn():
    """ask_fn(agent_type, prompt) -> str  for deliberation.

    Agent-Q uses DeepSeek, Agent-T uses Qwen — TRUE multi-provider debate.
    """
    clients: dict[str, DeepSeekClient | QwenClient] = {}
    prompts = {"agent_q": QUANT_SYSTEM, "agent_t": TECH_SYSTEM}

    async def _ask(agent_type: str, prompt: str) -> str:
        key = agent_type.lower()
        if key not in clients:
            if key == "agent_q":
                clients[key] = _make_deepseek_client(temperature=0.5)
            else:
                clients[key] = _make_qwen_client(temperature=0.8)

        sys = prompts.get(key, prompts["agent_q"])
        messages = [
            LLMMessage(role="system", content=sys),
            LLMMessage(role="user", content=prompt),
        ]
        resp = await clients[key].chat(messages)
        provider = "DeepSeek" if isinstance(clients[key], DeepSeekClient) else "Qwen"
        logger.info(
            f"🤖 [{agent_type}|{provider}] {len(resp.content)} chars, {resp.total_tokens} tok, {resp.latency_ms:.0f}ms"
        )
        return resp.content

    return _ask


def _make_strategy(
    name: str,
    signals: list[tuple[str, str, float]],
    stop_loss: float = 0.02,
    take_profit: float = 0.04,
) -> StrategyDefinition:
    sigs = [
        Signal(
            id=f"signal_{i + 1}",
            type=s[0],
            params={"indicator": s[1], "threshold": s[2]},
            condition=f"{s[1]} threshold {s[2]}",
        )
        for i, s in enumerate(signals)
    ]
    return StrategyDefinition(
        strategy_name=name,
        signals=sigs,
        filters=[],
        exit_conditions=ExitConditions(
            stop_loss=ExitCondition(type="fixed_pct", value=stop_loss),
            take_profit=ExitCondition(type="fixed_pct", value=take_profit),
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Smoke — DeepSeek connectivity
# ═══════════════════════════════════════════════════════════════════════════


class TestLiveSmoke:
    @pytest.mark.slow
    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_deepseek_responds(self):
        """DeepSeek returns a non-empty response."""
        await _ensure_deepseek()
        client = _make_deepseek_client()
        resp = await client.chat(
            [
                LLMMessage(role="system", content="Reply in one word."),
                LLMMessage(role="user", content="Say hello."),
            ]
        )
        assert resp.content, "Must return content"
        assert resp.total_tokens > 0
        logger.info(f"✅ DeepSeek: '{resp.content.strip()}' ({resp.total_tokens} tok)")

    @pytest.mark.slow
    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_qwen_responds(self):
        """Qwen returns a non-empty response (Singapore region)."""
        await _ensure_qwen()
        client = _make_qwen_client()
        resp = await client.chat(
            [
                LLMMessage(role="system", content="Reply in one word."),
                LLMMessage(role="user", content="Say hello."),
            ]
        )
        assert resp.content, "Must return content"
        assert resp.total_tokens > 0
        logger.info(f"✅ Qwen: '{resp.content.strip()}' ({resp.total_tokens} tok)")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Domain Expert Analysis  (Agent-Q + Agent-T, parallel)
# ═══════════════════════════════════════════════════════════════════════════


class TestLiveDomainAnalysis:
    @pytest.mark.slow
    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_quant_agent_analyses_strategy(self):
        """Agent-Q (quant, DeepSeek) analyses a strategy via real API call."""
        await _ensure_deepseek()
        agent = TradingStrategyAgent(ask_fn=_make_ask_fn(_make_deepseek_client(0.5), QUANT_SYSTEM))
        result = await agent.analyze(
            {
                "strategy": {
                    "type": "rsi_macd",
                    "params": {"rsi_period": 14, "macd_fast": 12, "macd_slow": 26},
                    "symbol": "BTCUSDT",
                    "timeframe": "15m",
                },
                "results": {
                    "sharpe_ratio": 1.62,
                    "win_rate": 0.58,
                    "max_drawdown": 0.18,
                    "profit_factor": 1.75,
                    "total_trades": 142,
                },
            }
        )
        assert isinstance(result, AnalysisResult)
        assert result.summary
        assert result.confidence > 0
        logger.info(
            f"📊 Agent-Q analysis:\n"
            f"   {result.summary}\n"
            f"   risk={result.risk_level}  confidence={result.confidence:.2f}"
        )

    @pytest.mark.slow
    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_tech_agent_analyses_risk(self):
        """Agent-T (technical, Qwen) analyses risk via real API call."""
        await _ensure_qwen()
        agent = RiskManagementAgent(ask_fn=_make_ask_fn(_make_qwen_client(0.8), TECH_SYSTEM))
        result = await agent.analyze(
            {
                "portfolio": {"initial_capital": 10_000, "leverage": 5},
                "positions": [{"symbol": "BTCUSDT", "size": 0.1, "direction": "long"}],
                "market": {"regime": "trending", "volatility": "high"},
            }
        )
        assert isinstance(result, AnalysisResult)
        assert result.summary
        logger.info(
            f"⚠️ Agent-T risk analysis:\n"
            f"   {result.summary}\n"
            f"   risk={result.risk_level}  confidence={result.confidence:.2f}"
        )

    @pytest.mark.slow
    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_parallel_expert_analysis(self):
        """Agent-Q (DeepSeek) + Agent-T (Qwen) analyse in parallel via real APIs."""
        await _ensure_both()
        quant = TradingStrategyAgent(ask_fn=_make_ask_fn(_make_deepseek_client(0.5), QUANT_SYSTEM))
        tech = RiskManagementAgent(ask_fn=_make_ask_fn(_make_qwen_client(0.8), TECH_SYSTEM))

        t0 = time.time()
        q_res, t_res = await asyncio.gather(
            quant.analyze(
                {
                    "strategy": {"type": "rsi", "params": {"rsi_period": 21}},
                    "results": {
                        "sharpe_ratio": 1.4,
                        "win_rate": 0.55,
                        "max_drawdown": 0.22,
                    },
                }
            ),
            tech.analyze(
                {
                    "portfolio": {"initial_capital": 10_000, "leverage": 3},
                    "positions": [{"symbol": "BTCUSDT", "size": 0.05}],
                    "market": {"regime": "volatile"},
                }
            ),
        )
        elapsed = time.time() - t0

        assert q_res.summary and t_res.summary
        logger.info(
            f"✅ Parallel analysis in {elapsed:.1f}s\n"
            f"   Agent-Q: {q_res.summary[:100]}...\n"
            f"   Agent-T: {t_res.summary[:100]}..."
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Multi-Agent Deliberation  (Agent-Q vs Agent-T debate)
# ═══════════════════════════════════════════════════════════════════════════


class TestLiveDeliberation:
    @pytest.mark.slow
    @pytest.mark.live
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_two_agent_debate(self):
        """
        Agent-Q (DeepSeek, quant, conservative) and Agent-T (Qwen, technical, aggressive)
        debate trailing-stop vs fixed-stop over 2 rounds of real cross-provider API calls.
        """
        await _ensure_both()

        ask_fn = _make_deliberation_ask_fn()
        deliberation = MultiAgentDeliberation(
            ask_fn=ask_fn,
            enable_parallel_calls=True,
            enable_confidence_calibration=False,
        )

        t0 = time.time()
        result = await deliberation.deliberate(
            question=(
                "For a BTC/USDT 15-minute RSI+MACD strategy with Sharpe 1.62 "
                "and 18% max drawdown, should we use a trailing stop-loss or "
                "a fixed stop-loss?  Commission is 0.07% per trade."
            ),
            agents=["agent_q", "agent_t"],
            context={
                "strategy": "RSI(14) + MACD(12,26,9)",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "sharpe": 1.62,
                "max_drawdown": "18%",
                "commission": "0.07%",
            },
            voting_strategy=VotingStrategy.WEIGHTED,
            max_rounds=2,
            min_confidence=0.5,
            convergence_threshold=0.6,
        )
        elapsed = time.time() - t0

        assert isinstance(result, DeliberationResult)
        assert result.decision
        assert result.confidence > 0
        assert len(result.rounds) >= 1
        assert len(result.final_votes) == 2

        logger.info(
            f"\n{'=' * 70}\n"
            f"🎭  DELIBERATION  ({elapsed:.1f}s, {len(result.rounds)} rounds)\n"
            f"{'=' * 70}\n"
            f"Decision : {result.decision}\n"
            f"Confidence: {result.confidence:.0%}\n"
            f"Dissent  : {len(result.dissenting_opinions)} opinions\n"
        )
        for v in result.final_votes:
            logger.info(f"  [{v.agent_type}] confidence={v.confidence:.2f}  position: {v.position[:120]}...")
        logger.info(f"{'=' * 70}")


# ═══════════════════════════════════════════════════════════════════════════
# 4. Full Pipeline  (analysis → debate → consensus)
# ═══════════════════════════════════════════════════════════════════════════


class TestLiveFullPipeline:
    @pytest.mark.slow
    @pytest.mark.live
    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_full_collaborative_pipeline(self):
        """
        Complete pipeline with REAL multi-provider API calls:
          Step 1: Agent-Q (DeepSeek) analyses strategy, Agent-T (Qwen) analyses risk (parallel)
          Step 2: Agent-Q & Agent-T debate stop-loss approach (2 rounds, cross-provider)
          Step 3: Consensus engine merges two proposals
        """
        await _ensure_both()
        t_start = time.time()

        # ── Step 1 ──────────────────────────────────────────────────
        logger.info("\n📋 STEP 1: Expert analysis (Agent-Q [DeepSeek] + Agent-T [Qwen])...")
        quant = TradingStrategyAgent(ask_fn=_make_ask_fn(_make_deepseek_client(0.5), QUANT_SYSTEM))
        tech = RiskManagementAgent(ask_fn=_make_ask_fn(_make_qwen_client(0.8), TECH_SYSTEM))

        q_res, t_res = await asyncio.gather(
            quant.analyze(
                {
                    "strategy": {
                        "type": "rsi_macd",
                        "params": {"rsi_period": 14, "macd_fast": 12, "macd_slow": 26},
                    },
                    "results": {
                        "sharpe_ratio": 1.62,
                        "win_rate": 0.58,
                        "max_drawdown": 0.18,
                        "profit_factor": 1.75,
                    },
                }
            ),
            tech.analyze(
                {
                    "portfolio": {"initial_capital": 10_000, "leverage": 3},
                    "positions": [{"symbol": "BTCUSDT", "size": 0.05}],
                    "market": {"regime": "trending", "volatility": "medium"},
                }
            ),
        )
        logger.info(
            f"  Agent-Q: risk={q_res.risk_level} conf={q_res.confidence:.2f}\n"
            f"           {q_res.summary}\n"
            f"  Agent-T: risk={t_res.risk_level} conf={t_res.confidence:.2f}\n"
            f"           {t_res.summary}"
        )

        # ── Step 2 ──────────────────────────────────────────────────
        logger.info("\n🎭 STEP 2: Deliberation (Agent-Q vs Agent-T)...")
        ask_fn = _make_deliberation_ask_fn()
        delib = MultiAgentDeliberation(
            ask_fn=ask_fn,
            enable_parallel_calls=True,
            enable_confidence_calibration=False,
        )
        delib_result = await delib.deliberate(
            question=(
                "Given the expert analyses, what stop-loss approach is best for "
                "the RSI+MACD strategy on BTCUSDT 15m?  "
                "Options: fixed 2%, trailing ATR(14), or hybrid.  "
                "Consider 18% drawdown and 0.07% commission."
            ),
            agents=["agent_q", "agent_t"],
            context={
                "quant_summary": q_res.summary,
                "tech_summary": t_res.summary,
                "quant_risk": q_res.risk_level,
                "tech_risk": t_res.risk_level,
            },
            voting_strategy=VotingStrategy.WEIGHTED,
            max_rounds=2,
            min_confidence=0.5,
        )
        logger.info(
            f"  Decision: {delib_result.decision}\n"
            f"  Confidence: {delib_result.confidence:.0%}\n"
            f"  Rounds: {len(delib_result.rounds)}"
        )
        for v in delib_result.final_votes:
            logger.info(f"  [{v.agent_type}] {v.position[:150]}")

        # ── Step 3 ──────────────────────────────────────────────────
        logger.info("\n🔀 STEP 3: Consensus merge...")
        s_q = _make_strategy(
            "Quant_Conservative",
            signals=[("RSI", "RSI", 30.0), ("MACD", "MACD", 0.0)],
            stop_loss=0.015,
            take_profit=0.04,
        )
        s_t = _make_strategy(
            "Tech_Aggressive",
            signals=[("RSI", "RSI", 25.0), ("Bollinger", "BB", -2.0)],
            stop_loss=0.025,
            take_profit=0.06,
        )

        engine = ConsensusEngine()
        engine.update_performance("agent_q", sharpe=1.8, win_rate=0.58)
        engine.update_performance("agent_t", sharpe=1.4, win_rate=0.55)

        consensus = engine.aggregate(
            strategies={"agent_q": s_q, "agent_t": s_t},
            method="weighted_voting",
        )
        total = time.time() - t_start
        c_sigs = [s.type for s in consensus.strategy.signals]

        logger.info(
            f"\n{'=' * 70}\n"
            f"🏆  PIPELINE COMPLETE  ({total:.1f}s)\n"
            f"{'=' * 70}\n"
            f"Expert Analysis:\n"
            f"  Agent-Q (quant):  risk={q_res.risk_level}  conf={q_res.confidence:.2f}\n"
            f"  Agent-T (tech) :  risk={t_res.risk_level}  conf={t_res.confidence:.2f}\n"
            f"\nDeliberation:\n"
            f"  Decision : {delib_result.decision}\n"
            f"  Confidence: {delib_result.confidence:.0%}\n"
            f"  Rounds   : {len(delib_result.rounds)}\n"
            f"  Dissent  : {len(delib_result.dissenting_opinions)}\n"
            f"\nConsensus Strategy:\n"
            f"  Name     : {consensus.strategy.strategy_name}\n"
            f"  Signals  : {c_sigs}\n"
            f"  Agreement: {consensus.agreement_score:.0%}\n"
            f"  Weights  : {consensus.agent_weights}\n"
            f"{'=' * 70}"
        )

        assert isinstance(consensus, ConsensusResult)
        assert consensus.strategy is not None
        assert "RSI" in c_sigs, "RSI must survive — both agents proposed it"
