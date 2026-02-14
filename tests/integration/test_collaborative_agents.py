"""
Test: AI Agents Collaboratively Solve a Trading Strategy Task

This integration test verifies that multiple AI agents (simulated) can work
together to solve a complex trading strategy optimization problem through:

1. Domain Expert Analysis — TradingStrategyAgent + RiskManagementAgent + CodeAuditAgent
   each analyze the same strategy from their own perspective.
2. Multi-Agent Deliberation — agents debate which stop-loss approach is best
   (trailing vs fixed), refine positions, and reach consensus.
3. Consensus Engine — combines two separate strategy definitions proposed by
   different "LLM agents" into a single consensus strategy via weighted voting.

The test uses mock ask_fn / simulated responses (no real LLM calls) so it runs
fast and deterministically.

Run:
    pytest tests/integration/test_collaborative_agents.py -v
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest

from backend.agents.consensus.consensus_engine import ConsensusEngine, ConsensusResult
from backend.agents.consensus.deliberation import (
    AgentVote,
    Critique,
    DeliberationResult,
    MultiAgentDeliberation,
    VotingStrategy,
)
from backend.agents.consensus.domain_agents import (
    AgentExpertise,
    AnalysisResult,
    CodeAuditAgent,
    RiskManagementAgent,
    TradingStrategyAgent,
    ValidationResult,
)
from backend.agents.prompts.response_parser import (
    ExitCondition,
    ExitConditions,
    Filter,
    Signal,
    StrategyDefinition,
)

# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

# Simulated LLM responses per domain, keyed by substring in the prompt.
_MOCK_RESPONSES: dict[str, str] = {
    # TradingStrategyAgent.analyze prompt contains "trading strategy analyst"
    "trading strategy analyst": (
        "SUMMARY: The RSI+MACD momentum strategy shows solid performance on BTCUSDT 15m "
        "with a Sharpe of 1.62 and a win rate of 58%. However, drawdown at 18% is concerning.\n"
        "STRENGTHS:\n"
        "- Good risk-adjusted returns (Sharpe > 1.5)\n"
        "- Consistent signals across regimes\n"
        "WEAKNESSES:\n"
        "- Max drawdown near 20% limit\n"
        "- Underperforms in ranging markets\n"
        "RISK_LEVEL: medium\n"
        "SHARPE_ASSESSMENT: good\n"
        "RECOMMENDATIONS:\n"
        "1. Add ATR-based trailing stop to reduce drawdown\n"
        "2. Reduce position size by 20% in low-volatility regimes\n"
        "CONFIDENCE: 0.82\n"
    ),
    # RiskManagementAgent.analyze prompt contains "risk management expert"
    "risk management expert": (
        "SUMMARY: Portfolio risk is moderate. 3x leverage with 2% stop loss is acceptable, "
        "but concentration in a single pair adds tail risk.\n"
        "RISK_LEVEL: medium\n"
        "EXPOSURE_ISSUES:\n"
        "- Single asset concentration (BTCUSDT)\n"
        "CONCENTRATION_RISKS:\n"
        "- 100% exposure to crypto-major\n"
        "RECOMMENDATIONS:\n"
        "1. Diversify across 2-3 uncorrelated pairs\n"
        "2. Set max daily drawdown limit at 5%\n"
        "MAX_RECOMMENDED_POSITION_SIZE: 5%\n"
        "SUGGESTED_STOP_LOSS: 1.5%\n"
        "CONFIDENCE: 0.78\n"
    ),
    # CodeAuditAgent.analyze prompt contains "senior code auditor"
    "senior code auditor": (
        "SUMMARY: Strategy code is clean; no security issues. Minor performance opportunity.\n"
        "SECURITY_ISSUES:\n"
        "- None found\n"
        "PERFORMANCE_ISSUES:\n"
        "- DataFrame copy on every candle is wasteful\n"
        "QUALITY_ISSUES:\n"
        "- Magic number 14 should be a named constant\n"
        "RECOMMENDATIONS:\n"
        "1. Cache indicator values to avoid recomputation\n"
        "2. Extract magic numbers into strategy_params\n"
        "RISK_LEVEL: low\n"
        "CODE_QUALITY_SCORE: 85\n"
        "CONFIDENCE: 0.90\n"
    ),
    # Deliberation — initial opinion
    "provide your position": (
        "POSITION: Use a trailing stop with ATR multiplier for better risk management\n"
        "CONFIDENCE: 0.80\n"
        "REASONING: Trailing stop adapts to volatility and locks in profits.\n"
        "EVIDENCE: TradingView backtests show 12% drawdown reduction with trailing stops\n"
    ),
    # Deliberation — critique
    "reviewing another agent": (
        "AGREES: yes\n"
        "AGREEMENT_POINTS: Trailing stop does reduce drawdown\n"
        "DISAGREEMENT_POINTS: Fixed stop is simpler to implement and test\n"
        "IMPROVEMENTS: Consider hybrid approach — fixed initial stop, then trail after +1R\n"
        "CONFIDENCE_ADJUSTMENT: 0.05\n"
    ),
    # Deliberation — refine
    "refining your position": (
        "POSITION: Use hybrid stop — fixed initial stop-loss at 1.5%, switch to trailing after +1R\n"
        "CONFIDENCE: 0.88\n"
        "REASONING: Hybrid approach combines simplicity of fixed stop with upside protection.\n"
        "MAINTAINED_POINTS: ATR-based trailing remains optimal for trend capture\n"
    ),
    # Validation prompt
    "validating a trading strategy": (
        "IS_VALID: yes\n"
        "ISSUES:\n"
        "- None critical\n"
        "WARNINGS:\n"
        "- Consider adding time-based exit for stagnant trades\n"
        "SUGGESTIONS:\n"
        "- Add maximum hold period of 48 candles\n"
        "VALIDATION_SCORE: 0.85\n"
    ),
}


def _mock_ask_fn(prompt: str) -> str:
    """Return canned response based on prompt content (case-insensitive match)."""
    prompt_lower = prompt.lower()
    for key, response in _MOCK_RESPONSES.items():
        if key.lower() in prompt_lower:
            return response
    return f"Simulated generic response for: {prompt[:60]}..."


async def _async_mock_ask(prompt: str) -> str:
    """Async wrapper around _mock_ask_fn."""
    return _mock_ask_fn(prompt)


async def _async_mock_ask_agent(agent_type: str, prompt: str) -> str:
    """Deliberation-compatible ask_fn(agent_type, prompt) → response."""
    return _mock_ask_fn(prompt)


def _make_strategy(
    name: str,
    signals: list[tuple[str, str, float]],
    filters: list[tuple[str, str]] | None = None,
    stop_loss: float = 0.02,
    take_profit: float = 0.04,
) -> StrategyDefinition:
    """Helper to build a StrategyDefinition quickly."""
    sig_objs = [
        Signal(
            id=f"signal_{i + 1}",
            type=s[0],
            params={"indicator": s[1], "threshold": s[2]},
            condition=f"{s[1]} threshold {s[2]}",
        )
        for i, s in enumerate(signals)
    ]
    flt_objs = [Filter(id=f"filter_{i + 1}", type=f[0], condition=f[1]) for i, f in enumerate(filters or [])]
    return StrategyDefinition(
        strategy_name=name,
        signals=sig_objs,
        filters=flt_objs,
        exit_conditions=ExitConditions(
            stop_loss=ExitCondition(type="fixed_pct", value=stop_loss),
            take_profit=ExitCondition(type="fixed_pct", value=take_profit),
        ),
    )


# ---------------------------------------------------------------------------
# 1. Domain Expert Analysis Phase
# ---------------------------------------------------------------------------


class TestDomainExpertAnalysis:
    """Multiple domain-expert agents analyze the same strategy independently."""

    @pytest.fixture
    def strategy_context(self) -> dict[str, Any]:
        """Shared context: an RSI+MACD strategy with backtest results."""
        return {
            "strategy": {
                "type": "rsi_macd",
                "params": {"rsi_period": 14, "macd_fast": 12, "macd_slow": 26},
                "symbol": "BTCUSDT",
                "timeframe": "15",
            },
            "results": {
                "sharpe_ratio": 1.62,
                "win_rate": 0.58,
                "max_drawdown": 0.18,
                "profit_factor": 1.75,
                "total_trades": 142,
                "net_profit": 3240.0,
            },
        }

    @pytest.fixture
    def risk_context(self) -> dict[str, Any]:
        return {
            "portfolio": {"initial_capital": 10_000, "leverage": 3},
            "positions": [{"symbol": "BTCUSDT", "size": 0.05, "direction": "long"}],
            "market": {"regime": "trending", "volatility": "medium"},
        }

    @pytest.fixture
    def code_context(self) -> dict[str, Any]:
        return {
            "language": "python",
            "code": (
                "def generate_signals(df):\n"
                "    df = df.copy()\n"
                "    df['rsi'] = ta.rsi(df['close'], length=14)\n"
                "    df['signal'] = 0\n"
                "    df.loc[df['rsi'] < 30, 'signal'] = 1\n"
                "    df.loc[df['rsi'] > 70, 'signal'] = -1\n"
                "    return df\n"
            ),
            "purpose": "RSI mean-reversion signal generator",
        }

    @pytest.mark.asyncio
    async def test_all_domain_agents_analyze_concurrently(self, strategy_context, risk_context, code_context):
        """Three domain agents analyze concurrently and produce complementary insights."""

        trading_agent = TradingStrategyAgent(ask_fn=_async_mock_ask)
        risk_agent = RiskManagementAgent(ask_fn=_async_mock_ask)
        code_agent = CodeAuditAgent(ask_fn=_async_mock_ask)

        # Run all three analyses in parallel
        trading_result, risk_result, code_result = await asyncio.gather(
            trading_agent.analyze(strategy_context),
            risk_agent.analyze(risk_context),
            code_agent.analyze(code_context),
        )

        # -- Trading Strategy Agent --
        assert isinstance(trading_result, AnalysisResult)
        assert trading_result.expertise == AgentExpertise.TRADING_STRATEGY
        assert trading_result.confidence > 0.7
        assert trading_result.risk_level in ("low", "medium", "high", "critical")
        assert len(trading_result.recommendations) >= 1

        # -- Risk Management Agent --
        assert isinstance(risk_result, AnalysisResult)
        assert risk_result.expertise == AgentExpertise.RISK_MANAGEMENT
        assert risk_result.confidence > 0.5
        assert risk_result.risk_level in ("low", "medium", "high", "critical")

        # -- Code Audit Agent --
        assert isinstance(code_result, AnalysisResult)
        assert code_result.expertise == AgentExpertise.CODE_AUDIT
        assert code_result.score is not None and code_result.score >= 70

    @pytest.mark.asyncio
    async def test_trading_agent_validates_strategy_proposal(self):
        """TradingStrategyAgent validates a strategy proposal."""
        agent = TradingStrategyAgent(ask_fn=_async_mock_ask)
        result = await agent.validate(
            proposal="RSI(14) with 2% stop loss and 4% take profit on BTCUSDT 15m",
            context={"symbol": "BTCUSDT", "timeframe": "15"},
        )
        assert isinstance(result, ValidationResult)
        assert isinstance(result.is_valid, bool)
        assert 0.0 <= result.validation_score <= 1.0

    @pytest.mark.asyncio
    async def test_risk_agent_rejects_dangerous_leverage(self):
        """RiskManagementAgent detects dangerous leverage."""
        agent = RiskManagementAgent(ask_fn=_async_mock_ask)
        result = await agent.validate(
            proposal="Open 10x leveraged BTCUSDT position",
            context={"leverage": 10, "position_size": 0.15, "stop_loss": 0.08},
        )
        assert isinstance(result, ValidationResult)
        # 10x leverage should be flagged as critical
        critical_issues = [i for i in result.issues if i.get("severity") == "critical"]
        assert len(critical_issues) >= 1, "Should flag 10x leverage as critical"
        assert not result.is_valid, "Should reject dangerous leverage"

    @pytest.mark.asyncio
    async def test_code_agent_detects_dangerous_patterns(self):
        """CodeAuditAgent detects eval() and other dangerous code."""
        agent = CodeAuditAgent(ask_fn=_async_mock_ask)
        result = await agent.validate(
            proposal="result = eval(user_input); exec(compile_code)",
        )
        assert isinstance(result, ValidationResult)
        assert not result.is_valid, "Should reject code with eval/exec"
        critical_issues = [i for i in result.issues if i.get("severity") == "critical"]
        assert len(critical_issues) >= 2, "Should flag both eval() and exec()"


# ---------------------------------------------------------------------------
# 2. Multi-Agent Deliberation Phase
# ---------------------------------------------------------------------------


class TestMultiAgentDeliberation:
    """Agents debate a trading question and converge on a consensus answer."""

    @pytest.mark.asyncio
    async def test_deliberation_reaches_consensus(self):
        """Three agents deliberate on stop-loss approach and reach consensus."""
        deliberation = MultiAgentDeliberation(
            ask_fn=_async_mock_ask_agent,
            enable_parallel_calls=True,
            enable_confidence_calibration=False,
        )

        result = await deliberation.deliberate(
            question="Should we use a trailing stop or fixed stop loss for the RSI+MACD strategy on BTCUSDT 15m?",
            agents=["deepseek", "perplexity", "qwen"],
            context={
                "strategy": "rsi_macd",
                "timeframe": "15m",
                "current_stop_loss": "fixed 2%",
                "backtest_drawdown": "18%",
            },
            voting_strategy=VotingStrategy.WEIGHTED,
            max_rounds=3,
            min_confidence=0.6,
            convergence_threshold=0.7,
        )

        assert isinstance(result, DeliberationResult)
        assert result.decision, "Must produce a decision"
        assert result.confidence > 0.0, "Confidence must be positive"
        assert len(result.rounds) >= 1, "At least one round"
        assert len(result.final_votes) == 3, "All 3 agents must vote"
        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_deliberation_produces_evidence_chain(self):
        """Deliberation produces an evidence chain tracing reasoning."""
        deliberation = MultiAgentDeliberation(
            ask_fn=_async_mock_ask_agent,
            enable_parallel_calls=False,
        )

        result = await deliberation.deliberate(
            question="Is RSI period 14 optimal for BTC on 15m timeframe?",
            agents=["deepseek", "perplexity"],
            max_rounds=2,
        )

        assert isinstance(result.evidence_chain, list)
        # Evidence chain should be serialisable
        json_str = json.dumps(result.to_dict())
        assert len(json_str) > 100, "Serialized result should be substantial"

    @pytest.mark.asyncio
    async def test_deliberation_identifies_dissent(self):
        """When agents disagree, dissenting opinions are captured."""
        deliberation = MultiAgentDeliberation(
            ask_fn=_async_mock_ask_agent,
            enable_parallel_calls=True,
        )

        result = await deliberation.deliberate(
            question="Should we increase leverage from 3x to 5x?",
            agents=["deepseek", "perplexity"],
            voting_strategy=VotingStrategy.MAJORITY,
            max_rounds=2,
        )

        assert isinstance(result.dissenting_opinions, list)
        # The result should have final_votes for all agents
        assert len(result.final_votes) == 2

    @pytest.mark.asyncio
    async def test_deliberation_statistics_update(self):
        """Deliberation stats are tracked across multiple runs."""
        deliberation = MultiAgentDeliberation(
            ask_fn=_async_mock_ask_agent,
        )

        for _ in range(3):
            await deliberation.deliberate(
                question="Best indicator combo for scalping?",
                agents=["deepseek", "perplexity"],
                max_rounds=1,
            )

        assert deliberation.stats["total_deliberations"] == 3
        assert deliberation.stats["avg_rounds"] > 0


# ---------------------------------------------------------------------------
# 3. Consensus Engine Phase — Merge Strategies
# ---------------------------------------------------------------------------


class TestConsensusEngine:
    """Consensus engine merges strategy proposals from multiple agents."""

    @pytest.fixture
    def deepseek_strategy(self) -> StrategyDefinition:
        return _make_strategy(
            name="DeepSeek_RSI_MACD",
            signals=[
                ("RSI", "RSI", 30.0),
                ("MACD", "MACD", 0.0),
            ],
            filters=[("Volume", "volume > sma(volume, 20)")],
            stop_loss=0.015,
            take_profit=0.04,
        )

    @pytest.fixture
    def qwen_strategy(self) -> StrategyDefinition:
        return _make_strategy(
            name="Qwen_RSI_BB",
            signals=[
                ("RSI", "RSI", 25.0),
                ("Bollinger", "BollingerBands", -2.0),
            ],
            filters=[("Trend", "close > ema(close, 200)")],
            stop_loss=0.02,
            take_profit=0.05,
        )

    @pytest.fixture
    def perplexity_strategy(self) -> StrategyDefinition:
        return _make_strategy(
            name="Perplexity_Momentum",
            signals=[
                ("RSI", "RSI", 28.0),
                ("MACD", "MACD", 0.0),
                ("ADX", "ADX", 25.0),
            ],
            stop_loss=0.018,
            take_profit=0.045,
        )

    def test_weighted_voting_consensus(self, deepseek_strategy, qwen_strategy, perplexity_strategy):
        """Weighted voting merges three strategies into one consensus."""
        engine = ConsensusEngine()

        # Register historical performance to influence weights
        engine.update_performance("deepseek", sharpe=1.8, win_rate=0.58)
        engine.update_performance("qwen", sharpe=1.2, win_rate=0.55)
        engine.update_performance("perplexity", sharpe=1.5, win_rate=0.56)

        result = engine.aggregate(
            strategies={
                "deepseek": deepseek_strategy,
                "qwen": qwen_strategy,
                "perplexity": perplexity_strategy,
            },
            method="weighted_voting",
        )

        assert isinstance(result, ConsensusResult)
        assert result.method == "weighted_voting"
        assert 0.0 <= result.agreement_score <= 1.0
        assert len(result.input_agents) == 3
        assert result.strategy is not None
        assert len(result.strategy.signals) >= 1

        # RSI was proposed by ALL three agents → must survive consensus
        signal_types = [s.type for s in result.strategy.signals]
        assert "RSI" in signal_types, "RSI signal was proposed by all 3 agents and must appear in consensus"

    def test_bayesian_aggregation(self, deepseek_strategy, qwen_strategy):
        """Bayesian method combines two strategies."""
        engine = ConsensusEngine()
        engine.update_performance("deepseek", sharpe=2.0, win_rate=0.60)
        engine.update_performance("qwen", sharpe=1.0, win_rate=0.50)

        result = engine.aggregate(
            strategies={"deepseek": deepseek_strategy, "qwen": qwen_strategy},
            method="bayesian_aggregation",
        )

        assert isinstance(result, ConsensusResult)
        assert result.method == "bayesian_aggregation"
        # DeepSeek has higher performance → should have higher weight
        assert result.agent_weights["deepseek"] >= result.agent_weights["qwen"]

    def test_best_of_picks_strongest_strategy(self, deepseek_strategy, qwen_strategy):
        """best_of method picks the single best strategy by heuristic."""
        engine = ConsensusEngine()
        engine.update_performance("deepseek", sharpe=2.5, win_rate=0.62)
        engine.update_performance("qwen", sharpe=0.8, win_rate=0.48)

        result = engine.aggregate(
            strategies={"deepseek": deepseek_strategy, "qwen": qwen_strategy},
            method="best_of",
        )

        assert isinstance(result, ConsensusResult)
        assert result.method == "best_of"
        # Best-of should pick deepseek (higher perf)
        assert result.strategy.strategy_name == deepseek_strategy.strategy_name

    def test_single_agent_passthrough(self, deepseek_strategy):
        """Single agent strategy is returned as-is."""
        engine = ConsensusEngine()
        result = engine.aggregate(strategies={"deepseek": deepseek_strategy})

        assert result.method == "single_agent"
        assert result.agreement_score == 1.0
        assert result.strategy.strategy_name == deepseek_strategy.strategy_name

    def test_empty_strategies_raises(self):
        """Empty strategies dict raises ValueError."""
        engine = ConsensusEngine()
        with pytest.raises(ValueError, match="empty"):
            engine.aggregate(strategies={})

    def test_signal_votes_count(self, deepseek_strategy, qwen_strategy, perplexity_strategy):
        """Signal vote counts reflect how many agents proposed each signal."""
        engine = ConsensusEngine()
        result = engine.aggregate(
            strategies={
                "deepseek": deepseek_strategy,
                "qwen": qwen_strategy,
                "perplexity": perplexity_strategy,
            },
        )

        # RSI proposed by all 3
        assert result.signal_votes.get("RSI", 0) == 3
        # MACD proposed by deepseek + perplexity = 2
        assert result.signal_votes.get("MACD", 0) == 2
        # Bollinger only by qwen = 1
        assert result.signal_votes.get("Bollinger", 0) == 1


# ---------------------------------------------------------------------------
# 4. Full Collaborative Pipeline
# ---------------------------------------------------------------------------


class TestFullCollaborativePipeline:
    """
    End-to-end: domain experts analyse → agents deliberate → consensus merges.

    This simulates the real workflow where AI agents cooperatively build
    a trading strategy: experts assess quality, agents debate parameters,
    and a consensus engine merges the final strategy.
    """

    @pytest.mark.asyncio
    async def test_full_collaborative_solve(self):
        """
        Full pipeline:
        1. Domain experts analyse a backtest in parallel
        2. Agents deliberate on the best stop-loss approach
        3. Two proposed strategies are merged via consensus
        """

        # ── Step 1: Domain expert analysis ──────────────────────────
        trading_agent = TradingStrategyAgent(ask_fn=_async_mock_ask)
        risk_agent = RiskManagementAgent(ask_fn=_async_mock_ask)
        code_agent = CodeAuditAgent(ask_fn=_async_mock_ask)

        strategy_ctx = {
            "strategy": {"type": "rsi_macd", "params": {"rsi_period": 14}},
            "results": {
                "sharpe_ratio": 1.62,
                "win_rate": 0.58,
                "max_drawdown": 0.18,
                "profit_factor": 1.75,
            },
        }
        risk_ctx = {
            "portfolio": {"initial_capital": 10_000, "leverage": 3},
            "positions": [{"symbol": "BTCUSDT", "size": 0.05}],
            "market": {"regime": "trending"},
        }
        code_ctx = {
            "language": "python",
            "code": "def generate_signals(df): ...",
            "purpose": "RSI momentum signals",
        }

        expert_results = await asyncio.gather(
            trading_agent.analyze(strategy_ctx),
            risk_agent.analyze(risk_ctx),
            code_agent.analyze(code_ctx),
        )

        # All experts must return valid results
        for r in expert_results:
            assert isinstance(r, AnalysisResult)
            assert r.confidence > 0.0

        # ── Step 2: Deliberation on stop-loss ───────────────────────
        deliberation = MultiAgentDeliberation(
            ask_fn=_async_mock_ask_agent,
            enable_parallel_calls=True,
        )

        delib_result = await deliberation.deliberate(
            question=(
                "Given the expert analysis results, should we use a trailing stop "
                "or fixed stop for the RSI+MACD strategy?"
            ),
            agents=["deepseek", "perplexity"],
            context={
                "trading_analysis": expert_results[0].to_dict(),
                "risk_analysis": expert_results[1].to_dict(),
            },
            voting_strategy=VotingStrategy.WEIGHTED,
            max_rounds=2,
        )

        assert isinstance(delib_result, DeliberationResult)
        assert delib_result.decision

        # ── Step 3: Consensus merges two proposed strategies ────────
        strategy_a = _make_strategy(
            name="Agent_A_Trailing_Stop",
            signals=[
                ("RSI", "RSI", 30.0),
                ("MACD", "MACD", 0.0),
            ],
            stop_loss=0.015,
            take_profit=0.04,
        )
        strategy_b = _make_strategy(
            name="Agent_B_Hybrid_Stop",
            signals=[
                ("RSI", "RSI", 28.0),
                ("Bollinger", "BollingerBands", -2.0),
            ],
            stop_loss=0.02,
            take_profit=0.045,
        )

        engine = ConsensusEngine()
        engine.update_performance("agent_a", sharpe=1.6, win_rate=0.57)
        engine.update_performance("agent_b", sharpe=1.4, win_rate=0.55)

        consensus = engine.aggregate(
            strategies={"agent_a": strategy_a, "agent_b": strategy_b},
            method="weighted_voting",
        )

        assert isinstance(consensus, ConsensusResult)
        assert consensus.strategy is not None
        assert len(consensus.input_agents) == 2
        assert consensus.agreement_score >= 0.0

        # ── Verify end-to-end coherence ─────────────────────────────
        # The final strategy should contain the RSI signal
        # (proposed by both agents)
        consensus_signal_types = [s.type for s in consensus.strategy.signals]
        assert "RSI" in consensus_signal_types, "RSI should survive consensus since both agents proposed it"

        # The pipeline should have produced:
        # - 3 expert analyses
        # - 1 deliberation with decision
        # - 1 consensus strategy
        assert len(expert_results) == 3
        assert delib_result.decision
        assert consensus.strategy.strategy_name
